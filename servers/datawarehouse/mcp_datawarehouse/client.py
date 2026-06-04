"""Databricks SQL client boundary for data warehouse services.

The Databricks SQL connector is synchronous. This module contains that detail
and exposes an async facade so service and future MCP tool code can stay
awaitable. Query modules depend on this client contract, not on Databricks SDK
types or connection internals.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Iterable, Sequence

from mcp_datawarehouse.errors import DatawarehouseServiceError
from mcp_datawarehouse.models import QueryResult
from mcp_datawarehouse.settings import DatawarehouseSettings

logger = logging.getLogger(__name__)


class DatabricksClient:
    """Thin async facade over the synchronous Databricks SQL connector."""

    def __init__(self, settings: DatawarehouseSettings) -> None:
        self.settings = settings
        self._connection: Any = None
        self._lock = threading.RLock()

    async def __aenter__(self) -> DatabricksClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def connect(self) -> None:
        await asyncio.to_thread(self._connect_sync)

    async def aclose(self) -> None:
        await asyncio.to_thread(self._close_sync)

    async def execute(
        self,
        query: str,
        parameters: Sequence[Any] | Iterable[Any] | None = None,
        *,
        source_query: str,
    ) -> QueryResult:
        parameter_list = list(parameters) if parameters is not None else None
        parameter_count = len(parameter_list) if parameter_list is not None else 0
        logger.info(
            "Starting Databricks query",
            extra={"source_query": source_query, "parameter_count": parameter_count},
        )
        try:
            result = await asyncio.to_thread(
                self._execute_sync,
                query,
                parameter_list,
                source_query,
            )
        except DatawarehouseServiceError:
            raise
        except Exception as exc:
            logger.exception(
                "Databricks query failed",
                extra={"source_query": source_query},
            )
            raise DatawarehouseServiceError(
                type="warehouse_query_failed",
                message=f"Databricks query failed: {type(exc).__name__}",
                segment="databricks",
                source_query=source_query,
                retryable=True,
            ) from exc

        logger.info(
            "Databricks query completed",
            extra={"source_query": source_query, "row_count": len(result.rows)},
        )
        return result

    def _connect_sync(self) -> Any:
        with self._lock:
            if self._connection is not None:
                return self._connection
            try:
                self.settings.validate_databricks_auth()
            except ValueError as exc:
                raise DatawarehouseServiceError(
                    type="auth_failed",
                    message=str(exc),
                    segment="auth",
                    retryable=False,
                ) from exc
            try:
                from databricks import sql as databricks_sql
            except ImportError as exc:
                raise DatawarehouseServiceError(
                    type="dependency_missing",
                    message="databricks-sql-connector is required.",
                    segment="databricks",
                    retryable=False,
                ) from exc

            kwargs: dict[str, Any] = {}
            if self.settings.socket_timeout_seconds is not None:
                kwargs["_socket_timeout"] = self.settings.socket_timeout_seconds
            if self.settings.retry_stop_after_attempts_count is not None:
                kwargs["_retry_stop_after_attempts_count"] = (
                    self.settings.retry_stop_after_attempts_count
                )
            if self.settings.retry_stop_after_attempts_duration_seconds is not None:
                kwargs["_retry_stop_after_attempts_duration"] = (
                    self.settings.retry_stop_after_attempts_duration_seconds
                )

            try:
                self._connection = databricks_sql.connect(
                    server_hostname=self.settings.databricks_server_hostname,
                    http_path=self.settings.databricks_http_path,
                    access_token=self.settings.databricks_token.get_secret_value()
                    if self.settings.databricks_token
                    else "",
                    **kwargs,
                )
            except Exception as exc:
                logger.exception("Databricks connection failed")
                raise DatawarehouseServiceError(
                    type="warehouse_connection_failed",
                    message=f"Databricks connection failed: {type(exc).__name__}",
                    segment="databricks",
                    retryable=True,
                ) from exc
            return self._connection

    def _close_sync(self) -> None:
        with self._lock:
            if self._connection is None:
                return
            try:
                self._connection.close()
            finally:
                self._connection = None

    def _execute_sync(
        self,
        query: str,
        parameters: list[Any] | None,
        source_query: str,
    ) -> QueryResult:
        with self._lock:
            connection = self._connect_sync()
            with connection.cursor() as cursor:
                if parameters is None:
                    cursor.execute(query)
                else:
                    cursor.execute(query, parameters)
                description = cursor.description or []
                columns = [column[0] for column in description]
                rows = [tuple(row) for row in cursor.fetchall()]
                return QueryResult(columns=columns, rows=rows)
