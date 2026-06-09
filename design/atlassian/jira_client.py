"""Jira Basic Auth client for local engineering agents."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# Part 1: Environment and exceptions


class JiraClientError(Exception):
    """Indicates Jira API call failure."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class DotenvLoader:
    """Loads a simple .env file from the project root."""

    @classmethod
    def load(cls, env_path: str | Path) -> dict[str, str]:
        """Read the .env file and return a key-value dictionary."""
        path = Path(env_path)
        if not path.exists():
            raise JiraClientError(f".env file not found: {path}")

        values: dict[str, str] = {}
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            parsed = cls._parse_line(raw_line)
            if parsed is not None:
                key, value = parsed
                values[key] = value
        return values

    @staticmethod
    def _parse_line(raw_line: str) -> tuple[str, str] | None:
        """Parse a single configuration line; ignore empty lines and comments."""
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            return None

        key, value = line.split("=", 1)
        return key.strip(), DotenvLoader._strip_quotes(value.strip())

    @staticmethod
    def _strip_quotes(value: str) -> str:
        """Remove surrounding paired quotes."""
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            return value[1:-1]
        return value


class JiraSettings:
    """Holds basic settings required for Jira connection."""

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        timeout_seconds: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env_file(cls, env_path: str | Path = ".env") -> "JiraSettings":
        """Build a settings object from the .env file."""
        values = DotenvLoader.load(env_path)
        base_url = values.get("JIRA_BASE_URL", "")
        email = values.get("JIRA_EMAIL", "")
        api_token = values.get("JIRA_API_TOKEN", "")
        timeout = int(values.get("JIRA_TIMEOUT_SECONDS", "30"))

        missing = [
            key
            for key, value in {
                "JIRA_BASE_URL": base_url,
                "JIRA_EMAIL": email,
                "JIRA_API_TOKEN": api_token,
            }.items()
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise JiraClientError(f"Missing Jira settings in .env: {joined}")

        return cls(
            base_url=base_url,
            email=email,
            api_token=api_token,
            timeout_seconds=timeout,
        )


# Part 2: Document structure helpers


class JiraDocumentBuilder:
    """
    Converts text into a Jira ADF document structure.

    Notes
    - Jira Cloud uses Atlassian Document Format (ADF) for rich text fields.
    - This project historically wrote description/comment as plain text paragraphs,
      which does not render Markdown syntax.
    - We now support a small, template-oriented Markdown subset and map it to ADF.
    """

    @staticmethod
    def from_plain_text(text: str) -> dict[str, Any]:
        """Convert multi-paragraph plain text into Jira-supported description/comment format."""
        paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
        if not paragraphs:
            paragraphs = [""]

        content = [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": paragraph}],
            }
            for paragraph in paragraphs
        ]
        return {"type": "doc", "version": 1, "content": content}

    @classmethod
    def from_markdown_subset(cls, markdown_text: str) -> dict[str, Any]:
        """
        Convert a limited Markdown subset (template-oriented) into Jira ADF.

        Supported subset
        - Headings: '#', '##', ... '######'
        - Bullet list items: '- ' (continuous lines become a bulletList)
        - Inline marks: **bold**, `inline code`
        - Mermaid fenced block: ```mermaid ... ``` -> codeBlock(language="mermaid")

        Fallback
        - If parsing fails for any reason, callers should fall back to from_plain_text.
        """
        blocks = cls._parse_markdown_blocks(markdown_text or "")
        if not blocks:
            blocks = cls.from_plain_text(markdown_text or "")["content"]
        return {"type": "doc", "version": 1, "content": blocks}

    @classmethod
    def _parse_markdown_blocks(cls, markdown_text: str) -> list[dict[str, Any]]:
        lines = (markdown_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        content: list[dict[str, Any]] = []

        paragraph_buf: list[str] = []
        bullet_buf: list[str] = []

        def flush_paragraph() -> None:
            nonlocal paragraph_buf
            if not paragraph_buf:
                return
            text = " ".join(part.strip() for part in paragraph_buf if part.strip()).strip()
            if text:
                content.append(cls._paragraph_node(text))
            paragraph_buf = []

        def flush_bullets() -> None:
            nonlocal bullet_buf
            if not bullet_buf:
                return
            items = []
            for raw_item in bullet_buf:
                items.append(
                    {
                        "type": "listItem",
                        "content": [cls._paragraph_node(raw_item)],
                    }
                )
            content.append({"type": "bulletList", "content": items})
            bullet_buf = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # Mermaid fenced block: ```mermaid ... ```
            if line.strip().lower() == "```mermaid":
                flush_paragraph()
                flush_bullets()
                i += 1
                mermaid_lines: list[str] = []
                while i < len(lines) and lines[i].strip() != "```":
                    mermaid_lines.append(lines[i])
                    i += 1
                # Skip closing fence if present
                if i < len(lines) and lines[i].strip() == "```":
                    i += 1
                content.append(cls._code_block_node("\n".join(mermaid_lines).rstrip("\n"), language="mermaid"))
                continue

            stripped = line.rstrip()
            if not stripped.strip():
                flush_paragraph()
                flush_bullets()
                i += 1
                continue

            # Heading: ^#{1,6} <text>
            if stripped.startswith("#"):
                level = 0
                while level < len(stripped) and level < 6 and stripped[level] == "#":
                    level += 1
                if level > 0 and len(stripped) > level and stripped[level] == " ":
                    flush_paragraph()
                    flush_bullets()
                    heading_text = stripped[level + 1 :].strip()
                    content.append(cls._heading_node(heading_text, level=level))
                    i += 1
                    continue

            # Bullet item: "- "
            if stripped.lstrip().startswith("- "):
                flush_paragraph()
                item_text = stripped.lstrip()[2:].strip()
                bullet_buf.append(item_text)
                i += 1
                continue

            # Default: part of paragraph
            flush_bullets()
            paragraph_buf.append(stripped)
            i += 1

        flush_paragraph()
        flush_bullets()
        return content

    @classmethod
    def _heading_node(cls, text: str, level: int) -> dict[str, Any]:
        return {
            "type": "heading",
            "attrs": {"level": max(1, min(6, int(level)))},
            "content": cls._parse_inline(text),
        }

    @classmethod
    def _paragraph_node(cls, text: str) -> dict[str, Any]:
        return {"type": "paragraph", "content": cls._parse_inline(text)}

    @staticmethod
    def _code_block_node(text: str, language: str) -> dict[str, Any]:
        return {
            "type": "codeBlock",
            "attrs": {"language": language},
            "content": [{"type": "text", "text": text or ""}],
        }

    @classmethod
    def _parse_inline(cls, text: str) -> list[dict[str, Any]]:
        """
        Parse inline subset: **bold** and `code`.
        Returns a list of ADF 'text' nodes with marks.
        """
        s = text or ""
        nodes: list[dict[str, Any]] = []

        def push(raw: str, marks: list[dict[str, Any]] | None = None) -> None:
            if raw == "":
                return
            node: dict[str, Any] = {"type": "text", "text": raw}
            if marks:
                node["marks"] = marks
            nodes.append(node)

        i = 0
        while i < len(s):
            # Inline code
            if s[i] == "`":
                end = s.find("`", i + 1)
                if end != -1:
                    push(s[i + 1 : end], marks=[{"type": "code"}])
                    i = end + 1
                    continue

            # Bold
            if s.startswith("**", i):
                end = s.find("**", i + 2)
                if end != -1:
                    push(s[i + 2 : end], marks=[{"type": "strong"}])
                    i = end + 2
                    continue

            # Plain text run until next marker
            next_code = s.find("`", i)
            next_bold = s.find("**", i)
            candidates = [pos for pos in [next_code, next_bold] if pos != -1]
            next_pos = min(candidates) if candidates else len(s)
            push(s[i:next_pos])
            i = next_pos

        return nodes or [{"type": "text", "text": ""}]


# Part 3: Jira client


class JiraClient:
    """Wraps common read/write operations for the Jira REST API."""

    def __init__(self, settings: JiraSettings) -> None:
        self.settings = settings

    @classmethod
    def from_env_file(cls, env_path: str | Path = ".env") -> "JiraClient":
        """Construct a client directly from the .env file."""
        return cls(JiraSettings.from_env_file(env_path))

    def verify_connection(self) -> dict[str, Any]:
        """Verify that the current email and token can access Jira."""
        return self._request_json("GET", "/rest/api/3/myself")

    def get_issue(
        self,
        issue_key: str,
        fields: list[str] | None = None,
        expand: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch the given Jira issue."""
        query = self._build_issue_query(fields=fields, expand=expand)
        return self._request_json("GET", f"/rest/api/3/issue/{issue_key}", query=query)

    def create_issue(
        self,
        project_key: str,
        issue_type: str,
        summary: str,
        description: str | None = None,
        parent_key: str | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new Jira issue."""
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "issuetype": {"name": issue_type},
            "summary": summary,
        }
        if description:
            fields["description"] = self._build_rich_text_document(description)
        if parent_key:
            fields["parent"] = {"key": parent_key}
        if extra_fields:
            fields.update(extra_fields)

        payload = {"fields": fields}
        return self._request_json("POST", "/rest/api/3/issue", payload=payload)

    def update_issue(
        self,
        issue_key: str,
        summary: str | None = None,
        description: str | None = None,
        parent_key: str | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update common fields on a Jira issue."""
        fields: dict[str, Any] = {}
        if summary is not None:
            fields["summary"] = summary
        if description is not None:
            fields["description"] = self._build_rich_text_document(description)
        if parent_key is not None:
            fields["parent"] = {"key": parent_key}
        if extra_fields:
            fields.update(extra_fields)
        if not fields:
            raise JiraClientError("No fields provided for update")

        payload = {"fields": fields}
        self._request_json("PUT", f"/rest/api/3/issue/{issue_key}", payload=payload)
        return self.get_issue(issue_key, fields=["summary", "status", "parent"])

    def add_comment(self, issue_key: str, comment_text: str) -> dict[str, Any]:
        """Add a comment to the issue."""
        payload = {"body": self._build_rich_text_document(comment_text)}
        return self._request_json(
            "POST",
            f"/rest/api/3/issue/{issue_key}/comment",
            payload=payload,
        )

    @staticmethod
    def _build_rich_text_document(text: str) -> dict[str, Any]:
        """
        Default write mode: render Markdown subset into Jira ADF.

        If the subset parser fails, fall back to plain text paragraphs to avoid data loss.
        """
        try:
            return JiraDocumentBuilder.from_markdown_subset(text)
        except Exception:
            return JiraDocumentBuilder.from_plain_text(text)

    def upload_attachment(self, issue_key: str, file_path: str | Path) -> dict[str, Any]:
        """Upload a local file to the given Jira issue."""
        path = Path(file_path)
        if not path.exists():
            raise JiraClientError(f"Attachment file not found: {path}")

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        body, boundary = self._build_multipart_body(path, content_type)
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-Atlassian-Token": "no-check",
        }
        return self._request_json(
            "POST",
            f"/rest/api/3/issue/{issue_key}/attachments",
            payload=body,
            extra_headers=headers,
            is_json_payload=False,
        )

    def create_story_under_epic(
        self,
        epic_key: str,
        project_key: str,
        summary: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a Story under an Epic."""
        return self.create_issue(
            project_key=project_key,
            issue_type="Story",
            summary=summary,
            description=description,
            parent_key=epic_key,
        )

    def create_subtask(
        self,
        parent_key: str,
        project_key: str,
        summary: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a Sub-task under a parent issue."""
        return self.create_issue(
            project_key=project_key,
            issue_type="Sub-task",
            summary=summary,
            description=description,
            parent_key=parent_key,
        )

    def _build_issue_query(
        self,
        fields: list[str] | None,
        expand: list[str] | None,
    ) -> dict[str, str]:
        """Build query parameters for an issue request."""
        query: dict[str, str] = {}
        if fields:
            query["fields"] = ",".join(fields)
        if expand:
            query["expand"] = ",".join(expand)
        return query

    def _request_json(
        self,
        method: str,
        path: str,
        query: dict[str, str] | None = None,
        payload: dict[str, Any] | bytes | None = None,
        extra_headers: dict[str, str] | None = None,
        is_json_payload: bool = True,
    ) -> dict[str, Any]:
        """Perform a Jira HTTP request and return the JSON result."""
        url = self._build_url(path, query)
        headers = self._build_headers(extra_headers, is_json_payload, payload)
        data = self._encode_payload(payload, is_json_payload)
        request = Request(url, data=data, headers=headers, method=method)

        try:
            with urlopen(request, timeout=self.settings.timeout_seconds) as response:
                raw_text = response.read().decode("utf-8") if method != "PUT" else ""
                return json.loads(raw_text) if raw_text else {}
        except HTTPError as error:
            raise self._build_http_error(error) from error
        except URLError as error:
            raise JiraClientError(f"Network error while calling Jira: {error}") from error

    def _build_url(self, path: str, query: dict[str, str] | None = None) -> str:
        """Compose the Jira API URL."""
        query_string = f"?{urlencode(query)}" if query else ""
        return f"{self.settings.base_url}{path}{query_string}"

    def _build_headers(
        self,
        extra_headers: dict[str, str] | None,
        is_json_payload: bool,
        payload: dict[str, Any] | bytes | None,
    ) -> dict[str, str]:
        """Build base request headers."""
        auth = base64.b64encode(
            f"{self.settings.email}:{self.settings.api_token}".encode("utf-8")
        ).decode("utf-8")
        headers = {
            "Accept": "application/json",
            "Authorization": f"Basic {auth}",
        }
        if is_json_payload and payload is not None:
            headers["Content-Type"] = "application/json"
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _encode_payload(
        self,
        payload: dict[str, Any] | bytes | None,
        is_json_payload: bool,
    ) -> bytes | None:
        """Encode the request body according to the request type."""
        if payload is None:
            return None
        if isinstance(payload, bytes):
            return payload
        if not is_json_payload:
            raise JiraClientError("Non-JSON payload must be bytes")
        return json.dumps(payload).encode("utf-8")

    def _build_http_error(self, error: HTTPError) -> JiraClientError:
        """Turn a Jira HTTP error into a readable exception."""
        raw_body = error.read().decode("utf-8", errors="replace")
        message = self._extract_error_message(raw_body)
        return JiraClientError(
            message=f"Jira API error {error.code}: {message}",
            status_code=error.code,
        )

    def _extract_error_message(self, raw_body: str) -> str:
        """Extract the main error message from the Jira response body."""
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return raw_body[:300]

        messages = payload.get("errorMessages") or []
        if messages:
            return "; ".join(messages)
        errors = payload.get("errors") or {}
        if errors:
            return "; ".join(f"{key}: {value}" for key, value in errors.items())
        return raw_body[:300]

    def _build_multipart_body(
        self,
        file_path: Path,
        content_type: str,
    ) -> tuple[bytes, str]:
        """Build a multipart/form-data body for attachment uploads."""
        boundary = uuid.uuid4().hex
        file_bytes = file_path.read_bytes()
        segments = [
            f"--{boundary}\r\n".encode("utf-8"),
            (
                'Content-Disposition: form-data; name="file"; '
                f'filename="{file_path.name}"\r\n'
            ).encode("utf-8"),
            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
            file_bytes,
            f"\r\n--{boundary}--\r\n".encode("utf-8"),
        ]
        return b"".join(segments), boundary


# Part 4: Command-line application


class JiraCliApplication:
    """Lightweight CLI entry point for engineers to verify capabilities."""

    def __init__(self) -> None:
        self.parser = self._build_parser()

    def run(self, argv: list[str] | None = None) -> int:
        """Parse commands and dispatch to the matching handler."""
        args = self.parser.parse_args(argv)
        client = JiraClient.from_env_file(args.env_file)

        try:
            result = self._dispatch(client, args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        except JiraClientError as error:
            print(str(error), file=sys.stderr)
            return 1

    def _dispatch(self, client: JiraClient, args: argparse.Namespace) -> dict[str, Any]:
        """Run the Jira operation for the given command."""
        if args.command == "verify":
            return client.verify_connection()
        if args.command == "get":
            return client.get_issue(args.issue, self._split_csv(args.fields))
        if args.command == "create":
            return client.create_issue(
                project_key=args.project,
                issue_type=args.type,
                summary=args.summary,
                description=args.description,
                parent_key=args.parent,
            )
        if args.command == "update":
            return client.update_issue(
                issue_key=args.issue,
                summary=args.summary,
                description=args.description,
                parent_key=args.parent,
            )
        if args.command == "comment":
            return client.add_comment(args.issue, args.text)
        if args.command == "attach":
            return client.upload_attachment(args.issue, args.file)
        raise JiraClientError(f"Unsupported command: {args.command}")

    def _build_parser(self) -> argparse.ArgumentParser:
        """Create the command-line argument parser."""
        parser = argparse.ArgumentParser(description="Jira helper for engineering agents")
        parser.add_argument("--env-file", default=".env", help="Path to the .env file")
        subparsers = parser.add_subparsers(dest="command", required=True)

        self._add_verify_parser(subparsers)
        self._add_get_parser(subparsers)
        self._add_create_parser(subparsers)
        self._add_update_parser(subparsers)
        self._add_comment_parser(subparsers)
        self._add_attach_parser(subparsers)
        return parser

    def _add_verify_parser(self, subparsers: argparse._SubParsersAction) -> None:
        """Register the verify command."""
        subparsers.add_parser("verify", help="Verify Jira connectivity")

    def _add_get_parser(self, subparsers: argparse._SubParsersAction) -> None:
        """Register the get command."""
        parser = subparsers.add_parser("get", help="Read a Jira issue")
        parser.add_argument("--issue", required=True, help="Issue key, for example CTI-15")
        parser.add_argument("--fields", default="", help="Comma-separated issue fields")

    def _add_create_parser(self, subparsers: argparse._SubParsersAction) -> None:
        """Register the create command."""
        parser = subparsers.add_parser("create", help="Create a Jira issue")
        parser.add_argument("--project", required=True, help="Project key")
        parser.add_argument("--type", required=True, help="Issue type name")
        parser.add_argument("--summary", required=True, help="Issue summary")
        parser.add_argument("--parent", help="Parent issue key")
        parser.add_argument("--description", default="", help="Plain text description")

    def _add_update_parser(self, subparsers: argparse._SubParsersAction) -> None:
        """Register the update command."""
        parser = subparsers.add_parser("update", help="Update a Jira issue")
        parser.add_argument("--issue", required=True, help="Issue key")
        parser.add_argument("--summary", help="New summary")
        parser.add_argument("--parent", help="New parent issue key")
        parser.add_argument("--description", help="New plain text description")

    def _add_comment_parser(self, subparsers: argparse._SubParsersAction) -> None:
        """Register the comment command."""
        parser = subparsers.add_parser("comment", help="Add a comment to an issue")
        parser.add_argument("--issue", required=True, help="Issue key")
        parser.add_argument("--text", required=True, help="Comment plain text")

    def _add_attach_parser(self, subparsers: argparse._SubParsersAction) -> None:
        """Register the attach command."""
        parser = subparsers.add_parser("attach", help="Upload an attachment")
        parser.add_argument("--issue", required=True, help="Issue key")
        parser.add_argument("--file", required=True, help="Attachment file path")

    def _split_csv(self, raw_value: str) -> list[str] | None:
        """Turn a comma-separated string into a field list."""
        values = [item.strip() for item in raw_value.split(",") if item.strip()]
        return values or None


# Part 5: Main entry


def main() -> int:
    """Main entry: start the CLI application only."""
    app = JiraCliApplication()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
