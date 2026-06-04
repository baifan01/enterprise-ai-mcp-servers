"""探索 Driivz CPMS 里 Charger identity key 相关 REST API 的真实返回。

这个脚本只用于 MCP 设计阶段的 live investigation，不是生产 MCP Server。
它通过本地 Settings 类读取 `.env.local` 或 `.env`，避免把 cookie、ticket、用户名或密码写入代码。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = SCRIPT_DIR / ".env.local"
FALLBACK_ENV_FILE = SCRIPT_DIR / ".env"
DEFAULT_BASE_URL = "https://apex-migration.driivz.com:8103/api-gateway"


class InvestigationSettings(BaseSettings):
    """REST investigation 配置，只从环境或本地 env 文件读取。"""

    model_config = SettingsConfigDict(
        env_prefix="DRIIVZ_",
        env_file=DEFAULT_ENV_FILE,
        extra="ignore",
    )

    def __init__(self, **values: Any) -> None:
        env_file = os.environ.get("DRIIVZ_ENV_FILE")
        if env_file:
            values.setdefault("_env_file", env_file)
        elif not DEFAULT_ENV_FILE.exists() and FALLBACK_ENV_FILE.exists():
            values.setdefault("_env_file", FALLBACK_ENV_FILE)
        super().__init__(**values)

    base_url: str = DEFAULT_BASE_URL
    cookie: SecretStr | None = None
    dms_ticket: SecretStr | None = None
    username: str | None = None
    password: SecretStr | None = None
    timeout_seconds: float = Field(default=30, gt=0)

    def validate_auth(self) -> None:
        if self.cookie or self.dms_ticket:
            return
        if self.username and self.password:
            return
        raise SystemExit(
            "缺少认证配置。请在 .env.local 中配置 DRIIVZ_COOKIE、"
            "DRIIVZ_DMS_TICKET，或 DRIIVZ_USERNAME/DRIIVZ_PASSWORD。"
        )


class DriivzClient:
    """薄封装 httpx，用于统一认证、请求和安全摘要输出。"""

    def __init__(self, settings: InvestigationSettings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.base_url.rstrip("/"),
            timeout=settings.timeout_seconds,
            follow_redirects=True,
            headers={"Accept": "application/json"},
        )
        if settings.cookie:
            self._client.headers["Cookie"] = _validate_header_value(
                "DRIIVZ_COOKIE",
                settings.cookie.get_secret_value(),
            )
        if settings.dms_ticket:
            self._client.headers["dmsTicket"] = _validate_header_value(
                "DRIIVZ_DMS_TICKET",
                settings.dms_ticket.get_secret_value(),
            )

    async def __aenter__(self) -> DriivzClient:
        await self.login_if_needed()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self._client.aclose()

    async def login_if_needed(self) -> None:
        if "dmsTicket" in self._client.headers:
            return
        if self._settings.cookie or self._settings.dms_ticket:
            return
        if not self._settings.username or not self._settings.password:
            return

        response = await self._client.post(
            "/v1/authentication/operator/login",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            content=json.dumps(
                {
                    "password": self._settings.password.get_secret_value(),
                    "userName": self._settings.username,
                },
                ensure_ascii=False,
            ).encode("utf-8"),
        )
        if response.status_code >= 400:
            raise RuntimeError(
                "登录失败："
                f"status={response.status_code} "
                f"body={_safe_error_preview(response)}"
            )
        body = response.json()
        ticket = _find_first_key(body, "ticket")
        if not isinstance(ticket, str) or not ticket:
            raise RuntimeError("登录响应中没有找到 ticket，需检查认证流程。")
        self._client.headers["dmsTicket"] = ticket

    async def login_probe(self) -> None:
        await self.login_if_needed()

    async def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> ApiResult:
        response = await self._client.get(path, params=params)
        return await ApiResult.from_response("GET", path, response)

    async def post_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> ApiResult:
        response = await self._client.post(path, params=params, json=body or {})
        return await ApiResult.from_response("POST", path, response)


class ApiResult:
    def __init__(self, method: str, path: str, status_code: int, body: Any) -> None:
        self.method = method
        self.path = path
        self.status_code = status_code
        self.body = body

    @classmethod
    async def from_response(cls, method: str, path: str, response: httpx.Response) -> ApiResult:
        try:
            body: Any = response.json()
        except json.JSONDecodeError:
            body = {"raw_text_preview": response.text[:500]}
        return cls(method, path, response.status_code, body)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def count(self) -> Any:
        if isinstance(self.body, dict):
            return self.body.get("count")
        return None

    @property
    def request_id(self) -> Any:
        if isinstance(self.body, dict):
            return self.body.get("requestId")
        return None

    @property
    def data(self) -> Any:
        if isinstance(self.body, dict):
            return self.body.get("data")
        return None

    def print_summary(self) -> None:
        print(f"\n== {self.method} {self.path}")
        print(f"status={self.status_code} requestId={self.request_id} count={self.count}")
        if not self.ok:
            print(_json_preview(self.body, max_chars=1200))
            return
        data = self.data
        if isinstance(data, list):
            print(f"data=list[{len(data)}]")
            if data:
                print("first_item_keys=", _top_level_keys(data[0]))
                print(_json_preview(_compact_sample(data[0]), max_chars=2200))
        elif isinstance(data, dict):
            print("data=dict keys=", _top_level_keys(data))
            print(_json_preview(_compact_sample(data), max_chars=2200))
        else:
            print("body_keys=", _top_level_keys(self.body))
            print(_json_preview(_compact_sample(self.body), max_chars=2200))


async def probe_device(args: argparse.Namespace) -> None:
    settings = InvestigationSettings()
    settings.validate_auth()

    if args.auth_diagnostics:
        print_auth_diagnostics(settings)
        return

    if args.login_only:
        client = DriivzClient(settings)
        try:
            await client.login_probe()
        finally:
            await client._client.aclose()
        print("登录 API 调用成功，已拿到 dmsTicket。未调用其他 API。")
        return

    until = _parse_datetime_arg(args.date_to) if args.date_to else datetime.now(UTC)
    since = _parse_datetime_arg(args.date_from) if args.date_from else until - timedelta(days=args.days)
    transaction_since = max(since, until - timedelta(days=7))
    output_dir = SCRIPT_DIR / "responses"
    if args.save_responses:
        output_dir.mkdir(exist_ok=True)

    async with DriivzClient(settings) as client:
        results: list[tuple[str, ApiResult]] = []

        profile = await client.post_json(
            "/v1/chargers/profiles/filter",
            params={"pageSize": args.page_size, "pageNumber": 0},
            body={"identityKey": args.device_id},
        )
        results.append(("charger-profile-by-identity-key", profile))
        charger_ids = _extract_unique_ints(profile.body, preferred_keys=("id", "chargerId"))

        if args.detailed_logs_only:
            if charger_ids and args.detailed_log_endpoint in ("both", "filter"):
                detailed_by_charger_id = await client.post_json(
                    "/v1/chargers/detailed-log/filter",
                    params={"pageSize": args.page_size, "pageNumber": 0, "sortBy": "id:desc"},
                    body={
                        "chargerId": charger_ids[0],
                        "dateFrom": since.isoformat().replace("+00:00", "Z"),
                        "dateTo": until.isoformat().replace("+00:00", "Z"),
                    },
                )
                results.append(("charger-detailed-log-by-charger-id", detailed_by_charger_id))

            if args.detailed_log_endpoint in ("both", "identity"):
                detailed_by_identity_key = await client.post_json(
                    f"/v1/chargers/detailed-log/chargers/{args.device_id}",
                    params={"pageSize": args.page_size, "pageNumber": 0, "sortBy": "id:desc"},
                    body={
                        "dateFrom": since.isoformat().replace("+00:00", "Z"),
                        "dateTo": until.isoformat().replace("+00:00", "Z"),
                    },
                )
                results.append(("charger-detailed-log-by-identity-key", detailed_by_identity_key))

            print(f"device_id / Charger identity key: {args.device_id}")
            print(f"date range UTC: {since.isoformat()} -> {until.isoformat()}")
            print(f"candidate charger ids from profile response: {charger_ids}")
            for name, result in results:
                result.print_summary()
                if args.save_responses:
                    await _write_json(output_dir / f"{name}.response.json", result.body)
            return

        if args.profile_only:
            print(f"device_id / Charger identity key: {args.device_id}")
            print(f"candidate charger ids from profile response: {charger_ids}")
            profile.print_summary()
            if args.save_responses:
                await _write_json(output_dir / "charger-profile-by-identity-key.response.json", profile.body)
            return

        if charger_ids:
            body_by_ids = {"ids": charger_ids[:20]}
            location = await client.post_json(
                "/v1/chargers/locations/filter",
                params={"pageSize": args.page_size, "pageNumber": 0},
                body=body_by_ids,
            )
            results.append(("charger-location-by-id", location))

            status = await client.post_json(
                "/v1/chargers/statuses/filter",
                params={"pageSize": args.page_size, "pageNumber": 0},
                body=body_by_ids,
            )
            results.append(("charger-status-by-id", status))

            status_detail = await client.get_json(f"/v1/chargers/{charger_ids[0]}/status")
            results.append(("charger-status-detail", status_detail))

        history = await client.post_json(
            f"/v1/chargers/identity-key/{args.device_id}/history/filter",
            params={"pageSize": args.page_size, "pageNumber": 0, "sortBy": "id:desc"},
            body={
                "dateFrom": since.isoformat().replace("+00:00", "Z"),
                "dateTo": until.isoformat().replace("+00:00", "Z"),
            },
        )
        results.append(("charger-history-by-identity-key", history))

        transactions = await client.post_json(
            f"/v1/ev-transactions/chargers/{args.device_id}/filter",
            params={"pageSize": args.page_size, "pageNumber": 0, "sortBy": "id:desc"},
            body={
                "fromDate": transaction_since.isoformat().replace("+00:00", "Z"),
                "toDate": until.isoformat().replace("+00:00", "Z"),
                "transactionBillingStatus": "FINAL_COST",
            },
        )
        results.append(("ev-transactions-by-identity-key", transactions))

        print(f"device_id / Charger identity key: {args.device_id}")
        print(f"candidate charger ids from profile response: {charger_ids}")
        for name, result in results:
            result.print_summary()
            if args.save_responses:
                await _write_json(output_dir / f"{name}.response.json", result.body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="通过 Charger identity key 探测 Driivz CPMS 候选 REST API。"
    )
    parser.add_argument("device_id", help="公司 deviceID，也就是 CPMS Charger identity key")
    parser.add_argument("--days", type=int, default=7, help="历史查询回看天数；交易查询最多使用最近 7 天")
    parser.add_argument("--date-from", help="历史查询开始时间，ISO 8601，例如 2026-06-01T00:00:00Z")
    parser.add_argument("--date-to", help="历史查询结束时间，ISO 8601，例如 2026-06-03T23:59:59Z")
    parser.add_argument("--page-size", type=int, default=20, help="分页大小")
    parser.add_argument(
        "--save-responses",
        action="store_true",
        help="保存完整 JSON 响应到 responses/，该目录不进 git",
    )
    parser.add_argument(
        "--profile-only",
        action="store_true",
        help="只调用第一个候选 API：POST /v1/chargers/profiles/filter",
    )
    parser.add_argument(
        "--detailed-logs-only",
        action="store_true",
        help="只调用 charger detailed-log 相关 API，并先用 profile 解析 charger id",
    )
    parser.add_argument(
        "--detailed-log-endpoint",
        choices=("both", "filter", "identity"),
        default="both",
        help="选择 detailed-log endpoint：both、filter 或 identity",
    )
    parser.add_argument(
        "--login-only",
        action="store_true",
        help="只调用登录 API，不调用任何 device/profile API",
    )
    parser.add_argument(
        "--auth-diagnostics",
        action="store_true",
        help="只打印认证配置诊断信息，不调用任何 API，不打印密码/cookie/ticket",
    )
    return parser


def _parse_datetime_arg(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _find_first_key(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            found = _find_first_key(child, key)
            if found is not None:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_first_key(child, key)
            if found is not None:
                return found
    return None


def print_auth_diagnostics(settings: InvestigationSettings) -> None:
    password = settings.password.get_secret_value() if settings.password else ""
    quote_chars = ('"', "'")
    print("认证配置诊断（不显示 secret）：")
    print(f"base_url={settings.base_url}")
    print(f"username={settings.username}")
    print(f"has_cookie={settings.cookie is not None}")
    print(f"has_dms_ticket={settings.dms_ticket is not None}")
    print(f"has_password={settings.password is not None}")
    print(f"password_length={len(password)}")
    print(f"password_has_non_ascii={any(ord(ch) > 127 for ch in password)}")
    print(f"password_starts_with_quote={password[:1] in quote_chars}")
    print(f"password_ends_with_quote={password[-1:] in quote_chars}")
    print(f"password_contains_newline={chr(10) in password or chr(13) in password}")


def _extract_unique_ints(value: Any, *, preferred_keys: tuple[str, ...]) -> list[int]:
    found: list[int] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key in preferred_keys:
                item = node.get(key)
                if isinstance(item, int) and item not in found:
                    found.append(item)
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return found


def _top_level_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        return sorted(str(key) for key in value.keys())
    return []


def _compact_sample(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _compact_sample(child) for key, child in list(value.items())[:24]}
    if isinstance(value, list):
        return [_compact_sample(child) for child in value[:3]]
    return value


def _json_preview(value: Any, *, max_chars: int) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... <truncated>"


def _validate_header_value(name: str, value: str) -> str:
    try:
        value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise SystemExit(
            f"{name} 包含非 ASCII 字符，无法作为 HTTP header 发送。"
            "请检查是否使用了中文/弯引号，例如 `“` 或 `”`，"
            "并改成普通英文引号 `\"`。"
        ) from exc
    return value


def _safe_error_preview(response: httpx.Response) -> str:
    try:
        body = response.json()
    except json.JSONDecodeError:
        return response.text[:500]
    if isinstance(body, dict):
        safe_keys = (
            "requestId",
            "code",
            "reason",
            "message",
            "httpStatusCode",
            "errors",
            "messages",
        )
        safe_body = {key: body.get(key) for key in safe_keys if key in body}
        return json.dumps(safe_body, ensure_ascii=False, default=str)
    return json.dumps(body, ensure_ascii=False, default=str)[:500]


async def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


if __name__ == "__main__":
    asyncio.run(probe_device(build_parser().parse_args()))
