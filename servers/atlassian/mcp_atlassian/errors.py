"""Safe error helpers for Atlassian service boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AtlassianServiceError(Exception):
    """Safe error object that can be returned to an agent."""

    type: str
    message: str
    segment: str | None = None
    source_api: str | None = None
    http_status: int | None = None
    retryable: bool = False

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment": self.segment,
            "source_api": self.source_api,
            "http_status": self.http_status,
            "type": self.type,
            "message": self.message,
            "retryable": self.retryable,
        }
