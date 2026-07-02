# Local Tool 权限与安全模型设计

日期：2026-07-02

本文档是 `ubi-personal-assistant-mcp-servers` 侧 local tool 设计的总体规范。它取代早期“wrapper 直接执行 Python CLI 并通过 `--user-id` 读取 `personal-secrets.env`”的过渡模型。当前权威链路是 `ubi-ai` broker/config 架构：本仓库只发布可被 `ubi-ai` 扫描的 tool catalog、subcommand 文档和真实 Python CLI；用户授权、wrapper materialization、配置存储、secret 解密和审计由 `ubi-ai` 负责。

## 目标

- 在 Copilot CLI 无法直接使用 third-party MCP server 时，仍能通过 local tool 访问企业系统。
- 让 agent 只看到已授权 wrapper 和文档，不看到 token、password、secret 文件路径或真实工具代码细节。
- 用 read/write wrapper 分组表达风险边界，并保留按 `server_id + wrapper_id + subcommand` 授权的能力。
- 让每个 MCP server 使用自己的 `.venv` 和 Python module，避免混用 agent runtime venv。
- 让所有 credential 通过 `ubi-ai` 的 user/system scope config 注入真实 tool 子进程环境。

## 当前执行链路

```text
agent
  -> users/<user_id>/readonly/local-tools/<wrapper_id>.sh
  -> wrapper 调用 ubi-ai localhost broker
  -> broker 解码 invocation token 得到 user_id/server_id/wrapper_id
  -> broker 校验用户状态、catalog、wrapper、subcommand 和授权 grant
  -> broker 从 DB 合并 user/system scope config
  -> broker 构造真实 tool 子进程 env
  -> <server_root>/.venv/bin/python -m <python_module> <subcommand> [business args...]
  -> tool Settings 只从环境变量构造 typed settings
  -> tool 输出 stdout/stderr/return_code，由 broker/wrapper 等价转发给 agent
```

本仓库不得让生产 local tool 通过 `--user-id`、`UBI_AI_AGENT_ROOT` 或 `users/<user_id>/secrets/personal-secrets.env` 查找 credential。`user_id` 是 `ubi-ai` broker 的授权和配置查询上下文，不是 MCP server 工具侧 credential lookup 输入。

## 仓库职责

本仓库负责：

- 在 `servers/<server_id>/published/catalog.json` 发布 server-level catalog。
- 在 `servers/<server_id>/published/doc/<wrapper_id>/<subcommand>.md` 发布 agent 可读的 subcommand 说明。
- 在 `servers/<server_id>/<python_package>/` 实现真实业务 tool、CLI subcommand 和 typed Settings。
- 在每个 server 自己的 `pyproject.toml` 中维护依赖、测试和质量门配置。
- 让公开 tool 方法的 docstring metadata 符合 `design/LOCAL_TOOL_DOCSTRING_METADATA.md`。

本仓库不负责：

- 生成用户目录下的 `readonly/local-tools/*.sh` wrapper。
- 按用户授权裁剪 wrapper/subcommand。
- 保存或解密 user/system config value。
- 生成或验证 invocation token。
- 记录 broker 执行审计。
- 在 production local tool 路径读取 personal secrets 文件。

这些运行时职责归 `ubi-ai`。

## Published Catalog 规范

每个 server 必须发布：

```text
servers/<server_id>/published/catalog.json
servers/<server_id>/published/doc/<wrapper_id>/<subcommand>.md
```

`server_id` 由 `servers/<server_id>` 目录名决定，不写入 catalog。`published/catalog.json` 必须包含：

- `schema_version`：第一版固定为 `"1"`。
- `display_name`：给 admin/UI 展示的 server 名称，不作为 ID。
- `python_module`：broker 执行的模块，例如 `mcp_atlassian.cli`。
- `config_keys`：server-level 配置项全集。
- `wrappers`：按 read/write 风险边界分组的 wrapper 和 subcommand 列表。

`config_keys` 是 credential/config 契约。每个 item 必须包含：

- `key`：真实 tool 子进程读取的环境变量名。
- `scope`：`user` 或 `system`。
- `description`：配置说明，不包含真实值或 secret 示例。
- `secret`：是否加密存储且不回显明文。
- `required`：缺失时是否阻止真实 tool 执行。

`config_keys` 不从 subcommand 参数猜测，也不由单个 docstring 推导；它来自 server Settings/config 定义。catalog 不得包含真实 token、password、默认 secret、用户 id、secret 文件路径或 wrapper materialization token。

## Wrapper 与权限分组

wrapper 是 agent 可见的能力边界，通常按平台和风险分组：

```text
atlassian-read.sh
atlassian-write.sh
databricks-read.sh
driivz-read.sh
```

规则：

- read wrapper 只包含查询、读取、诊断类 subcommands。
- write wrapper 包含创建、更新、评论、上传附件等会修改外部系统的 subcommands。
- `Tool.mode` 必须与 wrapper 风险一致。会修改外部系统的方法不能标记为 `read`。
- 授权粒度是 `server_id + wrapper_id + subcommand`。
- `requires_user_id` 是兼容字段；当前 broker/config 方案下应为 `false`，不代表 credential lookup。
- wrapper 由 `ubi-ai` 根据 catalog、用户授权和 invocation token 动态 materialize，本仓库不发布用户目录下的 `.sh` 文件。

## Subcommand 文档规范

公开给 agent 的每个 subcommand 必须有对应文档：

```text
servers/<server_id>/published/doc/<wrapper_id>/<subcommand>.md
```

文档应由公开方法的 docstring metadata 维护，至少包含：

- `When to use`：何时使用该 tool。
- `Parameters`：参数名、业务含义、枚举、默认值和限制。
- `Examples`：wrapper 调用示例，不包含 `--user-id`、token、password 或 track id。
- `Output`：关键 JSON 字段和解释。
- `Safety`：读写风险、外部系统影响和安全边界。

详细规范见 `design/LOCAL_TOOL_DOCSTRING_METADATA.md`。当前没有专门发布命令；Codex/agent 修改公开 tool 时必须同步维护 published catalog 和 doc 文件。

## Settings 与 Credential 规则

每个 server 的 Settings 是读取环境变量和构造 typed config 的唯一边界。

生产 local tool 路径中：

- Settings 只读取 broker 注入的环境变量和允许的本地 runtime settings。
- 服务层、client、业务函数不直接读取环境变量。
- CLI 不接受 credential 参数、secret 路径或 `--user-id`。
- 缺少 required config 时返回明确错误，不提 `personal-secrets.env`。
- `.env`/`*_ENV_FILE` 可以作为本地开发便利保留，但不代表 production credential lookup 模型。

## 安全要求

- 不在代码、catalog、published docs、README、测试夹具或示例中写真实 token/password。
- 不在 wrapper、命令行参数、stdout、stderr、日志或 JSON result 中输出 secret。
- 公开参数必须是业务参数；不得暴露任意 SQL、任意 JQL/CQL、任意 URL、任意 Python 表达式或 shell 片段，除非对应 tool 的安全设计明确允许并限制。
- write tool 的 docstring `Safety` 必须说明会修改哪个外部系统、修改范围和失败语义。
- 查询类 tool 应设置合理 limit/window，避免一次返回过大的外部数据。
- 对外部 API、数据库、HTTP client 的异常要转换为明确失败，不泄露 secret。

## 新增或更新 Local Tool Checklist

当新增或更新 local tool 时，agent 必须检查：

1. 公开方法签名只包含业务参数。
2. docstring metadata 符合 `design/LOCAL_TOOL_DOCSTRING_METADATA.md`。
3. CLI subcommand 名称与 `Tool.name`、catalog subcommand 名称一致。
4. wrapper 分组和 `mode` 与风险一致。
5. Settings 中的 env key 与 `published/catalog.json` 的 `config_keys` 一致。
6. `config_keys[].scope/secret/required` 变更不会静默破坏已有配置；如果 secret 语义改变，需要人工迁移方案。
7. `published/doc` 示例不包含 `--user-id`、token、password、secret 文件路径或 track id。
8. 单元测试覆盖 Settings 缺配置、CLI 参数、核心业务行为和安全限制。
9. 受影响 server 通过 commit guideline 中的 ruff、pytest、bandit、pip-audit gate，或在提交说明中解释未运行原因。

## 与 ubi-ai 的契约

`ubi-ai` 依赖本仓库发布产物来完成运行时工作：

- 扫描 `servers/<server_id>/published/catalog.json`。
- 用 `server_id + wrapper_id + subcommand` 展示和保存用户授权。
- 根据 `config_keys` 展示 user/system 配置 UI。
- materialize 用户可见 wrapper/readme/doc。
- broker 执行 `<server_root>/.venv/bin/python -m <python_module> <subcommand> [args...]`。

因此，本仓库的 catalog 和 published docs 是运行时契约，不是普通说明文字。更新公开 tool 行为时必须同步维护它们。
