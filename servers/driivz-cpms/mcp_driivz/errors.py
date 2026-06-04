"""Driivz CPMS error helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class DriivzServiceError(Exception):
    """Safe error object that can be returned to an agent."""

    type: str
    message: str
    segment: str | None = None
    source_api: str | None = None
    http_status: int | None = None
    request_id: str | None = None
    retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment": self.segment,
            "source_api": self.source_api,
            "type": self.type,
            "message": self.message,
            "http_status": self.http_status,
            "request_id": self.request_id,
            "retryable": self.retryable,
        }
