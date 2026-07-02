# Agent Instructions

This repository is a Python async service for channel-based AI assistant orchestration.

Before code changes, read and follow:

- `design/CODE_GENERATION_GUIDELINES.md`
- For local tool work, `design/LOCAL_TOOL_DEVELOPMENT_GUIDELINES.md`
- Relevant design documents under `design/`


Before creating Git commits, read `design/AGENT_GIT_COMMIT_GUIDELINES.md`

Hard rules:

- Keep package boundaries cohesive and interface-based.
- Do not read environment variables directly outside `Settings`.
- Do not put SQLite details into `agent_runtime`.
- Do not put channel-specific logic into `agent_runtime`.
- Prefer async for database, subprocess, filesystem, and external API work.
- Log important external calls and lifecycle events, but never log secrets.
- Catch third-party boundary exceptions and convert them into explicit failures.
- Add focused unit tests and integration tests for core behavior.
- Keep changes scoped to the requested feature or fix.
- When creating public methods exposed as local tools or wrapper subcommands, write docstrings that follow `design/LOCAL_TOOL_DOCSTRING_METADATA.md`.
- If a design choice is unclear, stop and ask before implementing.
