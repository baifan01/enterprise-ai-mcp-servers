"""Format raw OCPP events into compact analysis sequences."""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any, Optional

from .models import MergedChargingAttempt, OCPPEvent, OCPPSequenceResult


class OCPPFormatter:
    """OCPP 序列格式化 API：把原始 request/response 压缩成适合人工和 AI 阅读的事件时间线。"""

    CONNECTOR_ID_KEYS = ("connectorId", "connector_id", "connectorID")

    def extract_connector_id(self, body: Optional[str]) -> Optional[int]:
        """从 OCPP 消息体中提取 connector 编号，用于区分设备级事件和插座级事件。"""
        if not body:
            return None

        try:
            parsed = json.loads(body)
            payloads = parsed if isinstance(parsed, list) else [parsed]
            for payload in payloads:
                if not isinstance(payload, dict):
                    continue
                for key in self.CONNECTOR_ID_KEYS:
                    if key in payload:
                        return int(payload[key])
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

        for pattern in (
            r'"connectorId"\s*:\s*(\d+)',
            r'"connector_id"\s*:\s*(\d+)',
            r'"connectorID"\s*:\s*(\d+)',
        ):
            match = re.search(pattern, body, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return None

    def extract_status_notification(self, request_body: Optional[str]) -> dict[str, str]:
        """从 StatusNotification 请求中提取状态和错误码，形成诊断状态变化的核心字段。"""
        if not request_body:
            return {"errorCode": "Unknown", "status": "Unknown"}

        return {
            "errorCode": self._extract_string_field(request_body, "errorCode") or "Unknown",
            "status": self._extract_string_field(request_body, "status") or "Unknown",
        }

    def format_events(self, events: list[OCPPEvent]) -> list[dict[str, Any]]:
        """将一组 OCPP 原始事件转为按时间排序、带相对 offset 的紧凑事件列表。"""
        if not events:
            return []

        ordered = sorted(events, key=lambda event: event.operation_timestamp)
        anchor_time = ordered[0].operation_timestamp
        return [self.format_event(event, anchor_time) for event in ordered]

    def format_sequence(
        self,
        attempt: MergedChargingAttempt,
        events: list[OCPPEvent],
    ) -> OCPPSequenceResult:
        """把 attempt 和它的 OCPP 事件打包为完整调研结果，保留原始数据和格式化视图。"""
        return OCPPSequenceResult(
            attempt=attempt,
            raw_events=events,
            formatted_events=self.format_events(events),
        )

    def format_event(
        self,
        event: OCPPEvent,
        anchor_time: dt.datetime,
    ) -> dict[str, Any]:
        """格式化单条 OCPP 事件，突出消息类型、相对时间、connector 和关键 payload。"""
        offset = round((event.operation_timestamp - anchor_time).total_seconds(), 3)
        result: dict[str, Any] = {
            "time_offset_seconds": offset,
            "operation_timestamp": event.operation_timestamp.isoformat(),
            "ocpp_type": event.ocpp_message_type,
        }

        connector_id = self.extract_connector_id(event.ocpp_request_body)
        if connector_id is None:
            connector_id = self.extract_connector_id(event.ocpp_response_body)
        if connector_id is not None:
            result["connector_id"] = connector_id

        if event.ocpp_message_type == "StatusNotification":
            result["status_info"] = self.extract_status_notification(event.ocpp_request_body)
        elif event.ocpp_message_type == "MeterValues":
            pass
        else:
            if event.ocpp_request_body:
                result["request"] = event.ocpp_request_body
            if event.ocpp_response_body:
                result["response"] = event.ocpp_response_body

        return result

    def _extract_string_field(self, body: str, field_name: str) -> Optional[str]:
        pattern = rf'"{re.escape(field_name)}"\s*:\s*"([^"]*)"'
        match = re.search(pattern, body)
        return match.group(1) if match else None
