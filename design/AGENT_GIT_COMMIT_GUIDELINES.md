# Agent Git Commit Guidelines

This document defines how agents should prepare Git commits in this repository.
The commit message is not only for human review: it is also a durable context
artifact that future agents can read from Git history to reconstruct why the
project changed.

## Goal

Every agent-authored commit should help a future fresh conversation answer:

- What problem was being solved?
- Which design documents or architectural decisions shaped the work?
- What changed in code, tests, docs, and wiring?
- What explicitly did not change?
- How was the change validated?
- What should the next agent be careful about?

## Before Committing

Before creating a commit, the agent should:

1. Inspect `git status --short`.
2. Review the diff for files it touched.
3. Avoid staging unrelated user changes.
4. Run focused tests for behavior changes.
5. Run broader tests when package boundaries, storage schema, runtime behavior,
   channel flow, or audit behavior changed.
6. Run the local quality and security gate for each affected server:

   ```bash
   cd servers/atlassian
   uv run ruff check .
   uv run ruff format --check .
   uv run pytest
   uv run bandit -r mcp_atlassian -c pyproject.toml
   uv run pip-audit

   cd ../datawarehouse
   uv run ruff check .
   uv run ruff format --check .
   uv run pytest
   uv run bandit -r mcp_datawarehouse -c pyproject.toml
   uv run pip-audit

   cd ../driivz-cpms
   uv run ruff check .
   uv run ruff format --check .
   uv run pytest
   uv run bandit -r mcp_driivz -c pyproject.toml
   uv run pip-audit
   ```

7. Note any tests or scans that were not run and why.

If the worktree contains unrelated modifications, do not revert them. Commit
only the files that belong to the requested change.

## Commit Message Shape

Use a concise title plus a structured body.

```text
Short imperative title

Context:
- Why this change exists.
- Which design document, task, bug, or architectural decision it follows.

Changes:
- Concrete files, modules, or behaviors changed.
- Important package-boundary or data-flow changes.
- Any intentionally small scope choices.

Validation:
- Commands run and their result.
- If tests were not run, state why.

Agent Notes:
- Information future agents need when reconstructing history.
- Follow-up work, stale docs, risks, assumptions, or constraints.
```

The body can be detailed. Prefer enough context for future agents over a terse
human-only summary. For routine commits, 10-40 body lines is usually enough.
For large architecture or migration commits, a longer body is acceptable.

## Title Rules

- Use imperative mood when natural, for example `Add audit repository`.
- Keep the title specific and short.
- Do not hide multi-area work behind a vague title such as `Update files`.
- Do not include test output, issue essays, or implementation details in the
  title.

## Body Rules

- Write for future agents that may only have Git history plus the current tree.
- Mention the authoritative design documents when relevant.
- Mention when a document is stale or intentionally not authoritative.
- Record important negative scope, for example:
  - `Does not add audit querying.`
  - `Does not change Telegram transport behavior.`
  - `Does not introduce a SQLite migration.`
- Record validation honestly.
- Do not include secrets, API keys, tokens, full prompts, or large model output.
- Do not paste long command output. Summarize the result.

## Recommended Commit Command

Use multiple `-m` blocks or an editor. Example:

```bash
git commit \
  -m "Mark architecture doc stale and update TODOs" \
  -m "Context:
- design/ARCHITECTURE.md still described the old Home AI / Codex CLI path.
- Current implementation uses conversation dispatch, agent_runtime, audit, and
  ResponseSink boundaries.

Changes:
- Added a stale-document notice to design/ARCHITECTURE.md.
- Marked completed TODO items as done.
- Added a TODO for user-uploaded attachments and file downloads.

Validation:
- Documentation-only change; tests were not run.

Agent Notes:
- Do not treat design/ARCHITECTURE.md as authoritative until rewritten.
- Prefer focused design docs under design/ for future architecture decisions."
```

## Example For Code Changes

```text
Record runtime audit events from AgentRuntimeService

Context:
- AUDIT_SERVICE_DESIGN.md says runtime completion/failure should be recorded
  once, preferably in AgentRuntimeService.
- The audit event must share track_id and turn_id with agent_runtime_turns.

Changes:
- Injected optional AuditService into AgentRuntimeService.
- Recorded agent_runtime_completed and agent_runtime_failed after executor
  results.
- Preserved channel-neutral boundaries; no Telegram details enter
  agent_runtime.

Validation:
- uv run pytest tests/test_agent_runtime_service.py
- uv run pytest
- Result: all tests passed.

Agent Notes:
- Audit writes are side-channel and should not fail the user request path.
- Do not duplicate the same runtime completion event in UbiOrchestrator.
```

## When Not To Commit

Do not create a commit if:

- The user only asked for analysis or review.
- Tests reveal a failure that the user has not accepted.
- Required design choices are unclear and the repository instructions say to
  stop and ask.
- The only available commit would mix unrelated user changes with agent changes.
