"""Safe error helpers for data warehouse service boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class DatawarehouseServiceError(Exception):
    """Safe error object that can be returned to an agent."""

    type: str
    message: str
    segment: str | None = None
    source_query: str | None = None
    retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment": self.segment,
            "source_query": self.source_query,
            "type": self.type,
            "message": self.message,
            "retryable": self.retryable,
        }
