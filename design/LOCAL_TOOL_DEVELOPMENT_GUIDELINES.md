# Local Tool 开发指南

日期：2026-07-02

本文档面向未来开发或维护 `ubi-personal-assistant-mcp-servers` 中 local tool 的 agent 和人类工程师。它说明新增、修改、发布 local tool 时必须遵循的工程要求和推荐实践。

开发前必须同时阅读：

- `design/CODE_GENERATION_GUIDELINES.md`
- `design/LOCAL_TOOLS_PERMISSION_MODEL.md`
- `design/LOCAL_TOOL_DOCSTRING_METADATA.md`
- 目标业务域的设计文档，例如 `design/atlassian/*`、`design/datawarehouse/*` 或 `design/driivz/*`

`design/LOCAL_TOOL_ENV_CONFIG_CODE_UPGRADE_PLAN.md` 是历史迁移计划，不是新增 local tool 的日常开发入口。

## 核心心智模型

本仓库只负责真实 tool 代码和发布产物。运行时用户授权、wrapper materialization、配置存储、secret 解密、invocation token 和 broker 审计由 `ubi-ai` 负责。

当前链路是：

```text
ubi-ai broker
  -> 读取 user/system scope config
  -> 注入真实 tool 子进程 env
  -> <server_root>/.venv/bin/python -m <python_module> <subcommand> [business args...]
  -> server Settings 从 env 构造 typed settings
  -> service/client 调外部系统
  -> stdout/stderr/return_code 回到 broker/wrapper/agent
```

生产 local tool 不得通过 `--user-id`、`UBI_AI_AGENT_ROOT` 或 `personal-secrets.env` 查找 credential。`user_id` 只属于 `ubi-ai` 的授权和配置查询上下文。

## 开发流程

### 1. 明确业务能力和风险

先决定 tool 的业务语义，而不是先写 CLI 参数。必须明确：

- tool 解决哪个业务问题。
- 是否会修改外部系统。
- 属于 read wrapper 还是 write wrapper。
- 需要哪些外部 credential/config。
- 输出给 agent 的 JSON 应该保留哪些核心字段，哪些字段必须隐藏或压缩。
- 是否存在时间窗口、结果数量、对象类型、项目/站点范围等安全限制。

如果某个参数会让 agent 直接传任意 SQL、JQL、CQL、URL、HTML、Python 表达式或 shell 片段，必须先有明确设计说明和安全限制。默认不要暴露这类自由参数。

### 2. 选择或创建 server 包

优先把能力放入已有 server：

```text
servers/atlassian/
servers/datawarehouse/
servers/driivz-cpms/
```

只有当外部系统、credential 集合、依赖或部署边界明显不同，才创建新的 `servers/<server_id>/`。每个 server 使用自己的 `pyproject.toml`、`.venv`、Settings、CLI 和 tests。不要依赖 agent runtime venv。

推荐包结构：

```text
servers/<server_id>/
  pyproject.toml
  README.md
  <python_package>/
    settings.py
    cli.py
    service.py
    client.py
    models.py
  tests/
  published/
    catalog.json
    doc/<wrapper_id>/<subcommand>.md
```

按现有 server 的风格保守扩展，不为了单个 tool 引入大型框架。

### 3. Settings 和配置契约

Settings 是读取环境变量的唯一边界。业务 service、client、query builder、formatter 不直接读取 env。

必须遵守：

- credential/config key 使用清晰的大写环境变量名。
- `published/catalog.json` 的 `config_keys` 必须和 Settings 实际读取的 env key 一致。
- token/password 通常 `secret=true`，URL、catalog/schema、timeout 通常 `secret=false`。
- `scope` 按实际归属选择 `user` 或 `system`。共享 endpoint/root URL 通常是 `system`，个人账号、token、password 通常是 `user`。
- 缺少 required config 时返回明确错误，但错误消息不包含 secret 值、secret 文件路径或过时的 `personal-secrets.env` 指引。
- `.env` 或 `*_ENV_FILE` 可以作为本地开发便利保留，但不能成为 production credential lookup 模型。

如果要改变已有 `config_keys[].secret` 语义，不能静默修改 catalog；这会影响 `ubi-ai` 已存配置的加解密语义，必须先设计人工迁移方案。

### 4. Service 和 client 边界

公开 tool 方法应该表达业务动作，内部再组合 Settings、client、query builder 和 formatter。

推荐：

- service 方法只接受业务参数，不接受 credential、secret path、`user_id` 或 track id。
- client 封装外部 API/DB 细节和认证 header/session。
- query builder 只从白名单参数构造查询，不拼接未限制的用户输入。
- result model/formatter 控制输出大小和字段，避免把外部系统原始大 JSON 直接吐给 agent。
- 第三方边界异常转换为明确失败，不泄露 secret。

对会修改外部系统的 write tool，还应设计幂等性、失败语义、是否需要先读取当前状态、是否添加 AI-generated 标识或审计可识别 metadata。

### 5. CLI subcommand

`ubi-ai` broker 执行形式固定为：

```text
<server_root>/.venv/bin/python -m <python_module> <subcommand> [business args...]
```

CLI 要求：

- subcommand 名称稳定，并与 docstring `Tool.name`、catalog subcommand `name` 一致。
- 只接受业务参数。
- 不接受 `--user-id`。
- 不接受 token/password/secret 文件路径。
- 支持机器可读输出，通常为 JSON。
- 非零退出、stderr 和错误 JSON 不得泄露 secret。

### 6. Docstring metadata

每个公开 tool/subcommand 方法必须有符合 `design/LOCAL_TOOL_DOCSTRING_METADATA.md` 的 docstring metadata。

必须包含：

```text
Tool
When to use
Parameters
Examples
Output
Safety
```

重点规则：

- `Tool.name` 与 CLI subcommand 完全一致。
- `Tool.wrapper` 是目标 wrapper，不带 `.sh` 后缀。
- `Tool.mode` 只能是 `read` 或 `write`，并与 wrapper 风险一致。
- `Parameters` 覆盖所有公开参数，不虚构签名里不存在的参数。
- `Examples` 使用 wrapper 形态示例，不包含 `--user-id`、token、password、secret path 或 track id。
- `Safety` 对 write tool 必须说明会修改哪个外部系统和修改范围。

### 7. Published catalog 和 docs

当前没有专门 publish 命令。Codex/agent 修改公开 tool、CLI、Settings、docstring metadata 或 wrapper 分组时，必须同步维护：

```text
servers/<server_id>/published/catalog.json
servers/<server_id>/published/doc/<wrapper_id>/<subcommand>.md
```

`catalog.json` 必须包含：

- `schema_version`
- `display_name`
- `python_module`
- `config_keys`
- `wrappers`

`server_id` 由目录名决定，不写入 catalog。catalog 不包含真实配置值、secret、用户 id、secret 文件路径或 wrapper token。

`published/doc` 是 agent 运行时会读到的 subcommand 详细说明。它必须和代码、CLI、docstring metadata 保持一致。不要只改 service 或 CLI 而忘记更新 published docs。

### 8. 测试和质量门

每次新增或修改 local tool，至少考虑以下测试：

- Settings 能从 env 读取 required config。
- Settings 缺 required config 时失败且错误不泄露 secret。
- CLI parser 接受合法业务参数。
- CLI parser 不接受 `--user-id`。
- service 调 Settings 时不传 `user_id`。
- query builder 或 request builder 不允许任意查询/URL/表达式越界。
- 外部 API/DB client 用 mock/fake 覆盖成功、失败、timeout、认证失败。
- 输出 JSON 字段稳定，不含 token/password。

提交前按 `design/AGENT_GIT_COMMIT_GUIDELINES.md` 跑受影响 server 的 gate：

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run bandit -r <package_name> -c pyproject.toml
uv run pip-audit
```

如果是文档-only 改动，可以不跑测试，但提交说明必须写明。

## 最佳实践

- 先写或更新业务设计，再写代码。对于 write tool、安全边界不清楚的 read tool、或会扩大外部访问范围的 tool，必须先确认设计。
- 用结构化参数代替自由文本查询。让 service 构造受限查询。
- 输出面向 agent 使用的摘要和关键字段，不默认返回外部系统完整响应。
- 为 read tool 设置 `max_results`、时间窗口或对象范围上限。
- 为 write tool 要求明确目标对象 URL/ID，并在修改前读取当前状态。
- 错误消息要可行动，但不能泄露 credential、完整请求、完整外部响应或内部路径。
- README 可以说明本地开发方式，但不要把 README 当作运行时契约；运行时契约是 `published/catalog.json` 和 `published/doc`。
- 对已有 local tool 的 behavior、参数、config key、wrapper 分组或风险模式做变更时，把它当作兼容性变更处理。

## 常见反模式

不要这样做：

- 在 service/client 里直接 `os.getenv()`。
- 给 CLI 加 `--user-id`、`--token`、`--password` 或 `--secret-file`。
- 在 catalog 或 published docs 中写真实 endpoint token、个人账号 token、默认 password。
- 让 agent 传任意 SQL/JQL/CQL，然后原样执行。
- 把会修改外部系统的 tool 放进 read wrapper。
- 只更新代码，不更新 `published/catalog.json` 和 `published/doc`。
- 修改 `config_keys[].secret` 语义但不写迁移说明。
- 在普通 unit test 中调用真实外部 API 或真实企业数据。

## 快速 Checklist

新增或更新 local tool 完成前，确认：

1. 业务设计和风险分组清楚。
2. Settings/env key 与 catalog `config_keys` 一致。
3. CLI subcommand、docstring `Tool.name`、catalog subcommand 名称一致。
4. Docstring metadata 完整。
5. Published catalog 和 docs 已更新。
6. 示例不包含 `--user-id`、token、password、secret path。
7. read/write wrapper 分组正确。
8. 输出不泄露 secret，大小可控。
9. 相关测试和质量门已运行，或提交说明解释未运行原因。
