# Local Tool 权限模型设计

本文档记录在 GitHub Copilot CLI 组织策略禁用 third-party MCP 后，平台如何用本地脚本工具临时替代 MCP tool 调用，并保留用户级权限控制。

## 背景

Shell Copilot policy 当前禁用了 third-party MCP servers。验证结果显示，不仅 remote MCP 被禁，本地 stdio MCP server 也会被 Copilot CLI 拦截。

因此，短期内不能依赖 Copilot CLI 的 MCP 注册机制直接调用：

```text
Driivz CPMS MCP
Datawarehouse MCP
Salesforce MCP
Atlassian MCP
```

但 Copilot CLI 仍可以读取授权目录中的文件，并执行本地命令。因此第一阶段采用 local tool wrapper 方案：由 agent 调用用户可见的 wrapper script，wrapper 再调用平台控制的真实 Python tool。

## 设计目标

- 支持在 MCP 被禁的情况下继续访问企业系统。
- 保留按用户控制 tool 可见性的能力。
- 不把 secret、token、password 暴露给 agent。
- 不把所有工具脚本直接放到 shared 目录。
- 让未来切回 MCP server 时，核心业务代码可以复用。

## 目录结构

运行时数据目录：

```text
ubi-personal-assistant-data/
  users/
    <user_id>/
      workspace/
      readonly/
        local-tools/
          review-site-runtime-by-device.sh
          review-site-runtime-by-device.readme.md
          query-ocpp-sequence.sh
          query-ocpp-sequence.readme.md
      secrets/
        personal-secrets.env
```

工具代码目录：

```text
ubi-personal-assistant-mcp-servers/
  servers/
    driivz-cpms/
      .venv/
      pyproject.toml
      mcp_driivz/
        ...

    datawarehouse/
      ...

    salesforce/
      ...
```

目录含义：

- `users/<user_id>/readonly/local-tools/` 放该用户可见、可调用的 wrapper 和同名说明文件。
- `users/<user_id>/secrets/personal-secrets.env` 放该用户自己的平台级 secret/token，不暴露给 agent。
- `ubi-personal-assistant-mcp-servers/servers/<tool>/` 放真实工具代码和该工具自己的 `.venv`，不加入 Copilot CLI 的 `--add-dir`。
- `shared/` 只放公共 instructions、skills、mcp-config 等，不放所有用户都可见的真实工具入口。

## 执行链路

```text
Agent
  -> 看到 users/<user_id>/readonly/local-tools/
  -> 根据可见 .sh 判断该用户有哪些 local tools 可用
  -> 读取目标 wrapper 的同名 .readme.md
  -> 调用某个 wrapper.sh
  -> wrapper.sh 使用对应工具目录自己的 .venv/bin/python 调用真实 Python CLI
  -> Python tool 接收 --user-id
  -> Python tool 根据 agent root 定位用户 secret
  -> 读取 users/<user_id>/secrets/personal-secrets.env
  -> 根据 tool 所属平台读取对应的标准环境变量
  -> 调用企业系统 API
  -> 输出结构化 JSON
  -> Agent 使用 JSON 作为上下文继续推理
```

## Wrapper 示例

以 Driivz CPMS 为例：

```bash
#!/usr/bin/env bash
set -euo pipefail

TOOL_ROOT="/path/to/ubi-personal-assistant-mcp-servers/servers/driivz-cpms"
PYTHON="$TOOL_ROOT/.venv/bin/python"
export PYTHONPATH="$TOOL_ROOT${PYTHONPATH:+:$PYTHONPATH}"

exec "$PYTHON" -m mcp_driivz.cli \
  review-site-runtime-by-device \
  --user-id "andreas.a.weber@shell.com" \
  "$@"
```

Agent 看到和调用的是：

```bash
readonly/local-tools/review-site-runtime-by-device.sh suby1100008277
```

Agent 不需要知道 secret 文件在哪里，也不需要知道真实 Python package 的内部结构。Agent 需要先读取同名说明文件，例如 `review-site-runtime-by-device.readme.md`，了解参数、限制和使用场景。

## Wrapper 和说明文件生成规则

`readonly/local-tools/` 下不放综合 README。原因是未来 wrapper 由平台按用户权限自动生成，工具可见性应由文件对本身表达，避免综合 README 与实际 wrapper 列表发生漂移。

每个可调用工具由一对同名文件组成：

```text
<tool-name>.sh
<tool-name>.readme.md
```

例如：

```text
review-site-runtime-by-device.sh
review-site-runtime-by-device.readme.md

query-ocpp-sequence.sh
query-ocpp-sequence.readme.md
```

如果同一平台下 tool 数量较多，可以使用平台级 grouped wrapper，通过 subcommand 区分方法。为了控制风险，推荐至少按读写分组：

```text
atlassian-read.sh
atlassian-read.readme.md

atlassian-write.sh
atlassian-write.readme.md
```

例如：

```bash
readonly/local-tools/atlassian-read.sh search-tickets ...
readonly/local-tools/atlassian-read.sh read-ticket ...
readonly/local-tools/atlassian-read.sh search-wiki-pages ...
readonly/local-tools/atlassian-read.sh read-wiki-page ...

readonly/local-tools/atlassian-write.sh create-wiki-child-page ...
readonly/local-tools/atlassian-write.sh update-wiki-page ...
```

读写 wrapper 分离后：

- read wrapper 只包含查询和读取类 subcommands。
- write wrapper 包含创建、更新、评论、上传附件等会修改外部系统的 subcommands。
- wrapper 仍然固定写入当前 `user_id`，调用方不传 `--user-id`。
- `.readme.md` 必须列出该 grouped wrapper 支持的 subcommands、参数、风险等级和示例。
- 未来如需更细权限，可在 Python CLI 或 wrapper 生成策略中按 subcommand 校验。

Grouped wrapper 的 `.readme.md` 不应承载所有 subcommand 的完整说明，避免 prompt 注入内容过长。推荐使用两层文档：

```text
readonly/local-tools/
  atlassian-read.sh
  atlassian-read.readme.md
  atlassian-write.sh
  atlassian-write.readme.md
  docs/
    atlassian/
      search-tickets.md
      read-ticket.md
      search-wiki-pages.md
      read-wiki-page.md
      create-wiki-child-page.md
      update-wiki-page.md
```

同名 `.readme.md` 作为轻量索引，只包含：

- wrapper 是 read 还是 write；
- 通用命令格式，例如 `<wrapper>.sh <subcommand> [args...]`；
- 支持的 subcommand 列表；
- 每个 subcommand 的一句话用途；
- 对应详细说明文档路径；
- 使用前必须读取目标 subcommand 详细文档的要求；
- write wrapper 的外部系统修改风险提醒。

详细参数、限制、示例、输出字段说明放在 `docs/<platform>/<subcommand>.md` 中。AgentRuntime prompt 只需要告诉 agent 先读取 wrapper 同名 readme，再按 readme 引用读取目标 subcommand 文档，不把所有 subcommand 细节直接注入 prompt。

## Tool Docstring Metadata

未来 wrapper index README、subcommand 详细说明和平台 tool registry 应从公开 tool/subcommand 方法的 docstring metadata 生成，而不是手工维护多份文档。内部规范见 `design/LOCAL_TOOL_DOCSTRING_METADATA.md`。

该规范固定少量机器可解析块：

```text
Tool
When to use
Parameters
Examples
Output
Safety
```

平台生成器的大致解析流程：

1. 从 CLI registry 或显式 tool registry 找到公开 subcommands。
2. 读取对应 Python callable 的函数签名、类型注解和默认值。
3. 读取 docstring，并按固定块名解析 `Tool`、`When to use`、`Parameters`、`Examples`、`Output`、`Safety`。
4. 校验 `Tool.name`、`Tool.wrapper`、`Tool.mode`、`Tool.summary` 等必填 metadata。
5. 校验 `Parameters` 块和真实函数签名一致。
6. 按 `Tool.wrapper` 分组生成 grouped wrapper index README。
7. 按 `Tool.platform` 和 `Tool.name` 生成 `docs/<platform>/<subcommand>.md` 详细说明。
8. 如果 docstring 缺失必填块或 metadata 与 CLI 注册不一致，构建或发布流程失败。

解析实现可以复用 `griffe`、`docstring-parser` 或等价 Python docstring 解析库。若库不能直接理解自定义块，生成器可以先取得 docstring 原文，再按固定块标题做轻量切分；业务语义以 `design/LOCAL_TOOL_DOCSTRING_METADATA.md` 为准。

生成要求：

- `.sh` 是唯一可执行入口，文件存在表示该用户可以调用该 local tool。
- 单命令 wrapper 的 `.readme.md` 是该 wrapper 的完整说明，必须与 `.sh` 同名。
- grouped wrapper 的 `.readme.md` 是轻量索引；详细参数、限制、示例、输出字段说明放在 `docs/<platform>/<subcommand>.md`。
- `.sh` 内固定写入当前 `user_id`，调用方不传 `--user-id`。
- `.sh` 使用对应工具代码目录自己的 `.venv/bin/python`，不使用统一 runtime venv，也不依赖 `uv run`。
- `.sh` 不写入 token、password、secret 文件路径或其他敏感值。

AgentRuntime 的提示词应告诉 agent：

```text
User-approved local tools may exist under readonly/local-tools/.
Each callable tool is a .sh file.
Before using a tool, read its same-name .readme.md file.
For grouped wrappers, read the referenced docs/<platform>/<subcommand>.md before calling a subcommand.
Do not pass --user-id; wrappers already bind the current user.
```

## Secret 约定

每个用户有自己的 secret 目录，目录下只放一个用户级 personal secrets 文件：

```text
ubi-personal-assistant-data/users/<user_id>/secrets/personal-secrets.env
```

该文件按平台定义标准环境变量。多个 local tool 命令可以复用同一组平台凭据，不为每个 MCP 或每个命令单独创建 env 文件。

示例结构：

```text
# Driivz CPMS
DRIIVZ_BASE_URL=...
DRIIVZ_USERNAME=...
DRIIVZ_PASSWORD=...

# Datawarehouse
DATABRICKS_SERVER_HOSTNAME=...
DATABRICKS_HTTP_PATH=...
DATABRICKS_TOKEN=...

# Salesforce
SALESFORCE_CLIENT_ID=...
SALESFORCE_CLIENT_SECRET=...
SALESFORCE_USERNAME=...

# Atlassian
ATLASSIAN_BASE_URL=...
ATLASSIAN_EMAIL=...
ATLASSIAN_API_TOKEN=...
```

推荐权限：

```bash
chmod 700 users/<user_id>/secrets
chmod 600 users/<user_id>/secrets/personal-secrets.env
```

Secret 文件不放在以下目录：

```text
shared/
users/<user_id>/workspace/
users/<user_id>/readonly/
users/<user_id>/attachments/
```

这些目录可能被 agent 看到或使用。

## Settings 约定

真实 Python tool 需要知道平台 runtime data root。

建议配置：

```text
UBI_AI_AGENT_ROOT=/Users/F.Bai/Documents/Cursor Projects/ubi-personal-assistant-data
```

工具根据 `--user-id` 推导 secret 路径：

```text
{UBI_AI_AGENT_ROOT}/users/{user_id}/secrets/personal-secrets.env
```

工具自己的 `Settings` 集中负责 secret 解析，业务函数和 client 不直接读取环境变量或 secret 文件。credential 解析顺序：

```text
1. 优先使用真实运行环境变量中已经注入的标准平台 credential。
2. 如果 credential 不完整，并且调用方提供了 user_id，则根据 UBI_AI_AGENT_ROOT 和 user_id 读取 personal-secrets.env 补齐。
3. 如果仍不完整，则由 client/auth 校验返回明确失败。
```

例如 Driivz 工具读取 `DRIIVZ_*` credential，Datawarehouse 工具读取 `DATABRICKS_*` credential，Salesforce 工具读取 `SALESFORCE_*` credential，Atlassian 工具读取 `ATLASSIAN_*` credential。未来如果每个用户运行在自己的 Docker/container 中，平台可以直接把同一组标准 credential 变量注入容器；本地 local tool 模式下则使用 personal secrets 文件作为 fallback。

实现要求：

- 不在工具代码中硬编码 token。
- 不在 wrapper 中写 token。
- 不在 stdout、stderr、日志或 JSON result 中输出 token。
- Settings/Config 负责集中读取 env，不在业务函数中散落读取环境变量。
- local tool 命令之间可以复用同一平台凭据，但不能跨用户复用 personal secrets 文件。
- 不从 wrapper 参数读取 password、token 或 secret 文件路径。

## 权限模型

核心规则：

```text
某用户 readonly/local-tools 下有哪些 wrapper
  = 该用户有哪些 local tools 可见和可调用
```

例如：

```text
users/andreas.../readonly/local-tools/review-site-runtime-by-device.sh
```

表示 Andreas 用户可以使用 Driivz CPMS runtime review。

如果某用户没有 Salesforce 权限，则不要在该用户的 `readonly/local-tools/` 下生成 Salesforce wrapper。

该方案把 MCP 的“tool 可见性控制”转换为文件系统层面的“用户级 wrapper 可见性控制”。

## 安全边界

- `shared/` 不放真实工具入口，避免所有用户都看到所有工具。
- `readonly/local-tools/` 只放 wrapper 和说明文件，不放 secret。
- `secrets/` 不加入 Copilot CLI 的 `--add-dir`。
- 真实工具代码不加入 Copilot CLI 的 `--add-dir`。
- 工具只接受白名单参数，不接受任意 URL、任意 SQL、任意 Python 表达式。
- 工具输出 JSON，避免输出大段日志和敏感信息。
- wrapper 应尽量薄，只负责传递固定 user id 和调用真实工具。

## 与 MCP 的关系

该 local tool 方案是 MCP 被组织策略禁用后的过渡方案，不改变业务 tool 的核心语义。

核心业务函数应保持可复用：

```text
review_site_runtime_by_device(device_id, include_recent_sessions)
```

未来可以有两个 adapter：

```text
local CLI wrapper adapter
stdio MCP server adapter
```

当 Copilot policy 允许 MCP 后，可以继续用同一套 client/tools 代码包装成 MCP server。

## 待确认问题

- wrapper 由平台自动生成，还是先手工放到用户 `readonly/local-tools/`？
- `UBI_AI_AGENT_ROOT` 是由 wrapper 固定传入，还是由部署环境统一注入？
- 是否需要一个 `ubi-tool-runner` gatekeeper 来进一步校验 user/tool 权限？
- wrapper 是否需要记录审计日志，例如 user、tool、参数摘要、执行时间、成功/失败？
