"""Small Databricks SQL client wrapper used by investigation code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

from .config import DatabricksSettings


@dataclass(frozen=True)
class QueryResult:
    """Databricks SQL 查询结果容器，保留列名和行数据，便于调研代码在 tuple 与 dict 两种形态间切换。"""

    columns: list[str]
    rows: list[tuple[Any, ...]]

    def as_dicts(self) -> list[dict[str, Any]]:
        """将查询结果转为按列名索引的字典列表，适合后续构造成领域模型或直接查看样本。"""
        return [dict(zip(self.columns, row)) for row in self.rows]


class DatabricksClient:
    """Databricks SQL 连接入口，用于调研阶段执行参数化 SQL 并返回结构化结果。"""

    def __init__(self, settings: DatabricksSettings):
        self.settings = settings
        self._connection: Any = None

    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "DatabricksClient":
        """从 `.env` 或当前环境变量创建客户端，用于本地调研时隔离凭证和查询配置。"""
        return cls(DatabricksSettings.from_env(env_file=env_file))

    def connect(self) -> Any:
        """建立并复用 Databricks SQL warehouse 连接，供后续查询共享同一个会话。"""
        if self._connection is not None:
            return self._connection

        try:
            from databricks import sql as databricks_sql
        except ImportError as exc:
            raise ImportError(
                "databricks-sql-connector is required. Install it with "
                "`uv add databricks-sql-connector`."
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

        self._connection = databricks_sql.connect(
            server_hostname=self.settings.server_hostname,
            http_path=self.settings.http_path,
            access_token=self.settings.access_token,
            **kwargs,
        )
        return self._connection

    def close(self) -> None:
        """关闭当前 Databricks 连接，释放本地调研进程持有的远端会话资源。"""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def execute(
        self,
        query: str,
        parameters: Optional[Sequence[Any] | Iterable[Any]] = None,
    ) -> QueryResult:
        """执行一条 SQL 并返回列名与全部结果行；用户输入应通过 `parameters` 传入。"""
        connection = self.connect()
        with connection.cursor() as cursor:
            if parameters is None:
                cursor.execute(query)
            else:
                cursor.execute(query, list(parameters))

            description = cursor.description or []
            columns = [column[0] for column in description]
            rows = [tuple(row) for row in cursor.fetchall()]
            return QueryResult(columns=columns, rows=rows)

    def __enter__(self) -> "DatabricksClient":
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
