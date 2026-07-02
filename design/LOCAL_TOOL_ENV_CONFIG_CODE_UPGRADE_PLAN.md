# Local Tool 环境变量配置代码升级计划

日期：2026-06-26

本文把 local tool broker 方案拆成 `ubi-personal-assistant-mcp-servers` 代码升级任务。目标是让 MCP servers 工具不再根据 `user_id` 读取用户目录下的 `personal-secrets.env`，而是只从真实 tool 子进程环境变量读取 catalog 声明的配置。

本文基于：

- `design/LOCAL_TOOL_DOCSTRING_METADATA.md`
- `../ubi-personal-assistant/design/LOCAL_TOOL_PUBLISH_CONTRACT.md`
- `../ubi-personal-assistant/design/LOCAL_TOOL_WRAPPER_CONFIG_AND_BROKER_DESIGN.md`
- `design/CODE_GENERATION_GUIDELINES.md`

## 目标链路

升级后：

```text
ubi-ai broker
  -> 从 DB 读取 user/system scope 配置
  -> 按 catalog config_keys[].key 注入真实 tool 子进程 env
  -> 执行 <tool_root>/.venv/bin/python -m <python_module> <subcommand> [args...]
  -> MCP servers Settings 只从环境变量构造 typed settings
```

MCP servers 工具不再做：

```text
Settings(user_id=...)
  -> UBI_AI_AGENT_ROOT/users/<user_id>/secrets/personal-secrets.env
```

`user_id` 是 `ubi-ai` broker 的授权和 DB 配置查询上下文，不是 MCP servers 工具侧 credential lookup 输入。

## 代码范围

第一批需要迁移的 server：

```text
servers/atlassian
servers/datawarehouse
servers/driivz-cpms
```

共享代码：

```text
servers/common/ubi_mcp_common/personal_secrets.py
```

发布产物：

```text
servers/*/published/catalog.json
servers/*/published/doc/<wrapper_id>/<subcommand>.md
```

注意：`published/doc` 是生成产物，不能手工改作为 source of truth。必须先改公开方法签名和 docstring metadata，再重新生成发布文档。

## Catalog 约定

每个 server 的 `published/catalog.json` 应包含 server-level `config_keys`：

```json
{
  "config_keys": [
    {
      "key": "ATLASSIAN_API_TOKEN",
      "scope": "user",
      "description": "User-specific Atlassian API token.",
      "secret": true,
      "required": true
    }
  ]
}
```

规则：

- `key` 同时是环境变量名。
- 不再有 `config_keys[].display_name`。
- `scope` 只能是 `user` 或 `system`。
- catalog 不包含真实 token、password、默认 secret 或 secret 文件路径。
- `server_id` 不写入 catalog，由 server 目录名决定。
- 新工具默认 `requires_user_id=false`。

当前建议 config keys：

| Server | Keys |
| --- | --- |
| `atlassian` | `ATLASSIAN_BASE_URL`, `ATLASSIAN_EMAIL`, `ATLASSIAN_API_TOKEN` |
| `datawarehouse` | `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN` |
| `driivz-cpms` | `DRIIVZ_BASE_URL`, `DRIIVZ_USERNAME`, `DRIIVZ_PASSWORD` |

如果某个配置是 system-level shared connection，将对应 key 的 `scope` 设为 `system`。

## Settings 迁移

每个 server 的 Settings 仍是唯一读取环境变量的边界，但要移除 personal secrets fallback。

### Atlassian

当前相关文件：

```text
servers/atlassian/mcp_atlassian/settings.py
servers/atlassian/mcp_atlassian/service.py
servers/atlassian/mcp_atlassian/cli.py
servers/atlassian/tests/test_settings.py
servers/atlassian/tests/test_cli.py
```

目标：

- `AtlassianSettings` 不接收 `user_id`。
- 删除 `_load_personal_credentials()`。
- 删除 `agent_root` credential lookup 语义。
- `validate_auth()` 只提示从环境变量注入配置。
- 服务层不再把 `user_id` 传给 `AtlassianSettings`。
- CLI subcommands 不再定义 `--user-id`。
- 测试改为通过 env 或 pydantic settings values 构造配置。

保留：

- `ATLASSIAN_ENV_FILE` 作为本地开发 env file override 可以暂时保留。
- `ATLASSIAN_TIMEOUT_SECONDS` 等非 secret runtime settings 可继续从 env/.env 读取。

### Datawarehouse

当前相关文件：

```text
servers/datawarehouse/mcp_datawarehouse/settings.py
servers/datawarehouse/mcp_datawarehouse/service.py
servers/datawarehouse/mcp_datawarehouse/cli.py
servers/datawarehouse/tests/test_settings.py
servers/datawarehouse/tests/test_cli.py
servers/datawarehouse/tests/test_personal_secrets.py
```

目标：

- `DatawarehouseSettings` 不接收 `user_id`。
- 删除 `_load_personal_credentials()`。
- 删除 `agent_root` credential lookup 语义。
- 服务层不再校验 `user_id is required for personal secrets lookup`。
- CLI subcommands 不再定义 `--user-id`。
- 删除或重写 `test_personal_secrets.py`。
- docstring metadata 里删除 `user_id` 参数说明。

保留：

- `DATAWAREHOUSE_ENV_FILE` 作为本地开发 env file override 可以暂时保留。
- `DATABRICKS_CATALOG`、`DATABRICKS_SCHEMA`、retry/timeout 等非 secret settings 可继续从 env/.env 读取。

### Driivz CPMS

当前相关文件：

```text
servers/driivz-cpms/mcp_driivz/settings.py
servers/driivz-cpms/mcp_driivz/service.py
servers/driivz-cpms/mcp_driivz/cli.py
servers/driivz-cpms/tests/test_settings.py
servers/driivz-cpms/tests/test_cli.py
```

目标：

- `DriivzSettings` 不接收 `user_id`。
- 删除 `_load_personal_credentials()`。
- 删除 `agent_root` credential lookup 语义。
- CLI subcommands 不再定义 `--user-id`。
- docstring metadata 里删除 `user_id` 参数说明。

保留：

- `DRIIVZ_TIMEOUT_SECONDS` 等非 secret settings。
- `DRIIVZ_BASE_URL` 是否 user/system scope 由 catalog 决定；Settings 只关心 env 中是否存在。

## CLI 和 Service 迁移

CLI 目标形态：

```text
python -m <python_module> <subcommand> [business args...]
```

不再有：

```text
--user-id <user_id>
```

Service 目标：

- 公开 tool 方法不再有 `user_id` 参数，除非确有业务语义需要当前用户上下文。
- Settings 构造不传 `user_id`。
- 缺配置时返回明确错误，但不提 personal secrets 文件路径。
- 日志保留 `has_config` 或 `has_user_id` 这类布尔字段时需要同步改名，避免继续表达 user_id credential lookup。

示意：

```python
async def read_wiki_page(...):
    async with AtlassianClient(AtlassianSettings()) as client:
        ...
```

## Docstring 和发布文档

公开方法的 docstring metadata 是 source of truth。

升级步骤：

1. 删除函数签名中的 `user_id` 参数。
2. 删除 docstring `Parameters` 里的 `user_id` 行。
3. 确认 examples 不包含 `--user-id`。
4. 重新运行发布生成器，生成 `published/doc`。
5. 校验 `published/doc` 不再包含 `personal secrets lookup`。

不要手工编辑 `published/doc` 来绕过 docstring。

## Common personal_secrets 模块

`servers/common/ubi_mcp_common/personal_secrets.py` 第一版可以保留但不应被生产 local tool Settings 使用。

迁移后要求：

- `servers/atlassian/mcp_atlassian/settings.py` 不 import `load_personal_secret_values`。
- `servers/datawarehouse/mcp_datawarehouse/settings.py` 不 import `load_personal_secret_values`。
- `servers/driivz-cpms/mcp_driivz/settings.py` 不 import `load_personal_secret_values`。

是否删除 common 模块单独确认。为降低风险，第一版建议只断开引用，不删除模块。

## Published catalog 更新

现有 `published/catalog.json` 应保持：

- server-level `config_keys`。
- no `config_keys[].display_name`。
- config key scope 正确。
- no real secret values。

`requires_user_id`：

- 新工具默认 `false`。
- 当前 catalog 可以作为迁移步骤改为 `false`。
- 如果保留字段，是兼容字段，不代表 credential lookup。

## 测试计划

每个 server 的 unit tests：

- Settings 从 env 读取 required credential。
- Settings 缺 required credential 时失败。
- Settings 错误消息不包含 `personal-secrets.env`。
- CLI parser 不接受或不需要 `--user-id`。
- Service 调 Settings 时不传 `user_id`。
- Service 缺配置返回 explicit failure。

Repo 级检查：

```text
rg "personal secrets lookup" servers/*/published/doc
rg "personal-secrets.env" servers/*/mcp_*
rg "load_personal_secret_values" servers/atlassian servers/datawarehouse servers/driivz-cpms
rg "--user-id" servers/*/mcp_* servers/*/published/doc
```

JSON 校验：

```text
python -m json.tool servers/atlassian/published/catalog.json
python -m json.tool servers/datawarehouse/published/catalog.json
python -m json.tool servers/driivz-cpms/published/catalog.json
```

## 分阶段实现

阶段 1：Atlassian

- 改 Settings。
- 改 CLI。
- 改 service。
- 改 tests。
- 改 docstring metadata。
- 重新生成 published docs。

阶段 2：Datawarehouse

- 改 Settings。
- 改 CLI。
- 改 service。
- 删除或重写 personal secrets tests。
- 改 docstring metadata。
- 重新生成 published docs。

阶段 3：Driivz CPMS

- 改 Settings。
- 改 CLI。
- 改 service。
- 改 tests。
- 改 docstring metadata。
- 重新生成 published docs。

阶段 4：Repo 级清理

- 确认三个 server 不再 import personal secrets helper。
- 确认 generated docs 不再出现 `user_id` credential lookup。
- 确认 catalog `config_keys` 与 Settings env names 一致。
- 保留或删除 `ubi_mcp_common.personal_secrets` 另行确认。

