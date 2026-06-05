# Local Tool 权限模型设计

本文档记录在 GitHub Copilot CLI 组织策略禁用 third-party MCP 后，平台如何用本地脚本工具临时替代 MCP tool 调用，并保留用户级权限控制。

## 背景

Shell Copilot policy 当前禁用了 third-party MCP servers。验证结果显示，不仅 remote MCP 被禁，本地 stdio MCP server 也会被 Copilot CLI 拦截。

因此，短期内不能依赖 Copilot CLI 的 MCP 注册机制直接调用：

```text
Driivz CPMS MCP
Datawarehouse MCP
Salesforce MCP
Atlassian / Jira MCP
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
          README.md
          review-site-runtime-by-device.sh
          review-site-runtime-by-device.readme.md
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
  -> 读取 README.md 和同名 .readme.md
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

例如 Driivz 工具读取 `DRIIVZ_*` credential，Datawarehouse 工具读取 `DATABRICKS_*` credential，Salesforce 工具读取 `SALESFORCE_*` credential。未来如果每个用户运行在自己的 Docker/container 中，平台可以直接把同一组标准 credential 变量注入容器；本地 local tool 模式下则使用 personal secrets 文件作为 fallback。

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
