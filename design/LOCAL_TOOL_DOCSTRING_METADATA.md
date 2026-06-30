# Local Tool Docstring Metadata 规范

本文档定义 local tool 公开方法的轻量级内部 docstring metadata 规范。它用于从真实 Python tool/subcommand 方法生成 grouped wrapper README、subcommand 详细说明和未来平台维护所需的 tool registry 信息。

这不是外部标准协议。它采用 Python docstring、类型注解和少量固定块组成，底层解析可以使用 `griffe`、`docstring-parser` 或等价库，业务语义由本文档固定。

## 设计目标

- 让 tool 的调用说明靠近实现代码，减少 README、wrapper 注册信息和真实参数之间的漂移。
- 支持平台从代码自动生成用户可见的 `*.readme.md` 和 `published/doc/<wrapper_id>/<subcommand>.md`。
- 让 agent 看到简洁、稳定的工具说明，而不是把所有工具细节一次性注入 prompt。
- 让发布流程可以校验公开 tool 是否具备必要的安全说明和输出说明。

## 适用范围

该规范适用于所有会暴露给 local tool wrapper 的公开 Python 方法或 CLI subcommand handler，例如：

```text
atlassian-read.sh search-wiki-pages ...
atlassian-read.sh read-wiki-page ...
atlassian-write.sh create-wiki-child-page ...
atlassian-write.sh update-wiki-page ...
```

不直接暴露给 agent 的内部 helper、adapter、HTTP client、converter 私有方法不需要遵守该规范。

## 信息来源

生成器必须组合两个信息来源：

| 来源 | 用途 |
| --- | --- |
| Python 函数签名和类型注解 | 参数名、必填/可选、默认值、类型。 |
| Docstring metadata 块 | tool 名称、wrapper 分组、使用场景、示例、输出、安全边界。 |

参数的真实存在性以函数签名为准。docstring 里的 `Parameters` 块用于补充业务含义、枚举值、限制和示例，不应虚构函数签名中不存在的参数。

## 必填块

每个公开 tool/subcommand 方法必须包含以下块，块名大小写固定：

```text
Tool
When to use
Parameters
Examples
Output
Safety
```

块含义：

| 块 | 必填 | 用途 |
| --- | --- | --- |
| `Tool` | 是 | 机器可解析的基础元数据。 |
| `When to use` | 是 | 告诉 agent 何时应该调用该方法。 |
| `Parameters` | 是 | 参数业务含义、默认值、枚举值和限制。 |
| `Examples` | 是 | CLI 或 wrapper 调用示例。 |
| `Output` | 是 | 返回 JSON 的关键字段和解释。 |
| `Safety` | 是 | 权限、安全边界、是否会修改外部系统。 |

## Tool 块字段

`Tool` 块必须使用简单的 `key: value` 格式。第一版支持以下字段：

| 字段 | 必填 | 示例 | 说明 |
| --- | --- | --- | --- |
| `name` | 是 | `search-wiki-pages` | wrapper subcommand 名称。 |
| `wrapper` | 是 | `atlassian-read` | 所属 grouped wrapper，不含 `.sh` 后缀。 |
| `mode` | 是 | `read` | 权限模式。第一版使用 `read` 或 `write`。 |
| `summary` | 是 | `Search Confluence pages by title or body text.` | 一句话用途，会进入 wrapper index。 |

`mode` 必须和 `wrapper` 一致：`read` 方法不能进入 write wrapper；会修改外部系统的方法不能标记为 `read`。

## 块格式约定

推荐使用 Google-style docstring，并在其基础上保留固定块。生成器只依赖固定块名和 `Tool` 块中的 `key: value` 字段，不依赖自然语言段落的具体措辞。

示例：

```python
def search_wiki_pages(
    text: str | None = None,
    *,
    search_field: str = "text",
    parent_page_id: str | None = None,
    agent_friendly_only: bool = False,
    max_results: int = 10,
) -> dict:
    """Search Confluence wiki pages.

    Tool:
        name: search-wiki-pages
        wrapper: atlassian-read
        mode: read
        summary: Search Confluence pages by title or body text.

    When to use:
        Use when the user wants to find wiki pages by keywords, optionally under
        a parent page. Use this before read-wiki-page when the page id or URL is
        not known.

    Parameters:
        text:
            Optional keywords. Supports one or multiple terms.
        search_field:
            One of: text, title. Defaults to text.
        parent_page_id:
            Optional parent page id. Limits search to this page and descendants.
        agent_friendly_only:
            If true, only search pages labeled ubitricity-agent-friendly.
        max_results:
            Maximum number of results. Capped at 50.

    Examples:
        atlassian-read.sh search-wiki-pages "design system" --search-field title
        atlassian-read.sh search-wiki-pages "runbook" --agent-friendly-only
        atlassian-read.sh search-wiki-pages "release" --parent-page-id 123456789

    Output:
        JSON with query metadata, result_count, and page summaries including
        page id, title, web URL, space id, and excerpt.

    Safety:
        Read-only. Does not expose arbitrary CQL. The service builds CQL from
        structured parameters and always limits content type to page.
    """
```

## 校验规则

发布或生成 wrapper 前必须执行 docstring 校验：

1. 公开 tool/subcommand 必须有 docstring。
2. 必填块必须全部存在。
3. `Tool.name`、`Tool.wrapper`、`Tool.mode`、`Tool.summary` 必须存在且非空。
4. `Tool.name` 必须和 CLI subcommand 注册名一致。
5. `Tool.wrapper` 必须是平台允许生成的 wrapper 名称。
6. `Tool.mode` 必须是允许值，第一版为 `read` 或 `write`。
7. `Tool.mode` 必须和 wrapper 风险分组一致。
8. `Parameters` 中出现的参数必须能在函数签名或 CLI schema 中找到。
9. 函数签名中的公开参数必须在 `Parameters` 中有说明。
10. `Safety` 对 write 方法必须明确说明会修改哪个外部系统。

校验失败时，平台生成器或发布流程应失败，不生成新的 catalog 或 subcommand 文档。

## 生成器输出

MCP servers 项目的发布生成器根据该规范产生两类环境无关的发布产物：

```text
servers/<server_id>/
  published/
    catalog.json
    doc/
      atlassian-read/
        search-wiki-pages.md
        read-wiki-page.md
      atlassian-write/
        create-wiki-child-page.md
        update-wiki-page.md
```

`published/catalog.json` 是 `ubi-ai` 可读取的结构化 tool catalog，应包含：

- `schema_version`；
- `display_name`；
- `python_module`；
- `config_keys[].key`；
- `config_keys[].scope`；
- `config_keys[].description`；
- `config_keys[].secret`；
- `config_keys[].required`；
- `wrappers[].wrapper_id`；
- `wrappers[].mode`；
- `wrappers[].display_name`；
- `wrappers[].summary`；
- `wrappers[].requires_user_id`；
- `wrappers[].subcommands[].name`；
- `wrappers[].subcommands[].summary`；
- `wrappers[].subcommands[].published_at`。

`server_id` 不写入 catalog；`ubi-ai` 通过扫描 `<mcp_servers_root>/<server_id>/published/catalog.json`，使用 server 子目录名作为 `server_id`。

`published/catalog.json` 的整体结构固定为：

```json
{
  "schema_version": "1",
  "display_name": "Atlassian",
  "python_module": "mcp_atlassian.cli",
  "config_keys": [
    {
      "key": "ATLASSIAN_BASE_URL",
      "scope": "system",
      "description": "Atlassian site base URL.",
      "secret": false,
      "required": true
    },
    {
      "key": "ATLASSIAN_API_TOKEN",
      "scope": "user",
      "description": "User-specific Atlassian API token.",
      "secret": true,
      "required": true
    }
  ],
  "wrappers": [
    {
      "wrapper_id": "atlassian-read",
      "mode": "read",
      "display_name": "Atlassian Read",
      "summary": "Read-only Atlassian wiki and ticket tools.",
      "requires_user_id": false,
      "subcommands": [
        {
          "name": "search-wiki-pages",
          "summary": "Search Confluence pages by title or body text.",
          "published_at": "2026-06-23T11:29:06Z"
        }
      ]
    }
  ]
}
```

Catalog 字段规则：

| 字段 | 必填 | 来源 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | 是 | server-level publish metadata/template | Catalog schema 版本。第一版固定为字符串 `"1"`。 |
| `display_name` | 是 | server-level publish metadata/template | 给 admin/UI 展示的 server 名称。不得作为 `server_id` 使用。 |
| `python_module` | 是 | server-level publish metadata/template | broker/local execution 调用的 Python module，例如 `mcp_atlassian.cli`。 |
| `config_keys` | 是 | Settings-derived publish metadata/template | server 级配置项数组。没有配置项时使用空数组。 |
| `wrappers` | 是 | subcommand docstring metadata 分组 + server-level wrapper metadata | wrapper/grouped command 数组。 |

Wrapper 字段规则：

| 字段 | 必填 | 来源 | 说明 |
| --- | --- | --- | --- |
| `wrapper_id` | 是 | `Tool.wrapper` | wrapper 名称，不含 `.sh` 后缀；在当前 server 内唯一。 |
| `mode` | 是 | `Tool.mode` | 权限模式。第一版使用 `read` 或 `write`。同一 wrapper 下所有 subcommands 必须一致。 |
| `display_name` | 是 | server-level wrapper metadata 或由 `wrapper_id` 稳定生成 | UI 展示名。 |
| `summary` | 是 | server-level wrapper metadata 或 wrapper 下 subcommand summary 聚合 | wrapper 一句话说明。 |
| `requires_user_id` | 是 | server-level wrapper metadata/template | 兼容字段。新 broker/config 方案下默认 `false`，不代表 credential lookup。 |
| `subcommands` | 是 | subcommand docstring metadata | wrapper 下公开 subcommand 数组。 |

Subcommand 字段规则：

| 字段 | 必填 | 来源 | 说明 |
| --- | --- | --- | --- |
| `name` | 是 | `Tool.name` | CLI subcommand 名称，必须和真实 CLI 注册名一致。 |
| `summary` | 是 | `Tool.summary` | subcommand 一句话说明。 |
| `published_at` | 是 | 发布生成器运行时写入 | ISO-8601 UTC 时间戳，用于追踪发布产物生成时间。 |

生成器必须校验 catalog：

1. 顶层只能包含 `schema_version`、`display_name`、`python_module`、`config_keys`、`wrappers`。
2. `schema_version` 必须是支持的版本，第一版为 `"1"`。
3. `python_module` 非空，且不能包含 shell 参数、空白分隔命令或文件系统路径。
4. `wrappers[].wrapper_id` 在同一 server 内唯一。
5. `wrappers[].mode` 必须是允许值，且与该 wrapper 下所有 subcommand 的 `Tool.mode` 一致。
6. `wrappers[].subcommands[].name` 在同一 wrapper 内唯一，并与真实 CLI subcommand 注册名一致。
7. `published_at` 必须是 UTC ISO-8601 字符串。
8. catalog 不包含真实配置值、secret、用户 id、wrapper materialization token 或本地用户目录路径。

`config_keys` 是 server 级配置项定义。配置 UI 直接展示 `config_keys[].key`，catalog 不提供 `config_keys[].display_name`。catalog 只声明配置 metadata，不包含真实 token、password、默认 secret 值或 secret 文件路径。

`config_keys` 不从单个 subcommand docstring 自动推导，也不由发布生成器根据参数名猜测。每个 server 的 Settings / 配置定义是 config key 的源头；Settings 声明真实 tool 子进程会读取哪些环境变量、这些变量是否为 secret、是否 required，以及建议的 user/system scope。发布生成器生成 `published/catalog.json` 时，必须从 server-level Settings-derived publish metadata/template 读取 `config_keys`，再和 subcommand docstring metadata 生成的 wrapper/subcommand 信息合并成完整 catalog。subcommand docstring 只负责公开命令的 `Tool`、参数、示例、输出和安全说明，不负责声明连接凭据。

`config_keys` 数据结构固定为：

```json
{
  "key": "ATLASSIAN_API_TOKEN",
  "scope": "user",
  "description": "User-specific Atlassian API token.",
  "secret": true,
  "required": true
}
```

字段规则：

| 字段 | 必填 | 示例 | 说明 |
| --- | --- | --- | --- |
| `key` | 是 | `ATLASSIAN_API_TOKEN` | 配置 key，同时也是真实 tool 子进程读取的环境变量名。必须在同一个 server catalog 内唯一。 |
| `scope` | 是 | `user` | 配置值归属范围。只能是 `user` 或 `system`。`user` 由用户维护，`system` 由管理员维护。 |
| `description` | 是 | `User-specific Atlassian API token.` | 给配置页面展示的说明。不得包含 token、password、默认值或其他 secret。 |
| `secret` | 是 | `true` | 是否需要加密存储并在前端隐藏明文。token/password 通常为 `true`；URL、catalog/schema 等非敏感配置通常为 `false`。 |
| `required` | 是 | `true` | 该 key 是否为工具执行所需配置。缺失 required config 时，真实 tool 执行应返回明确配置错误。 |

生成器必须校验：

1. `config_keys` 存在且为数组；没有配置项的 server 使用空数组。
2. 每个 item 只能包含上述字段；不得包含 `display_name`、真实值、默认 secret、文件路径或用户 id。
3. `key` 非空，并符合环境变量命名习惯：大写字母、数字和下划线。
4. 同一 server 内 `key` 不重复。
5. `scope` 只能是 `user` 或 `system`。
6. `description` 非空，且不得包含明显 secret 示例。
7. `secret` 和 `required` 必须是 boolean。
8. 如果 catalog 中已有同名 key 的历史发布约定，不能静默改变 `secret` 语义；这会影响 `ubi-ai` 侧已有数据库值的加解密处理，需要人工迁移。

发布出的 tool 代码必须从 `config_keys[].key` 对应的环境变量读取连接信息、token 和 password。上线 broker 执行路径中，`ubi-ai` 从数据库读取 user/system scope 配置并注入真实 tool 子进程环境；MCP servers 工具不得再根据 `user_id` 或 `UBI_AI_AGENT_ROOT` 读取 `users/<user_id>/secrets/personal-secrets.env`。

`published/doc/<wrapper_id>/<subcommand>.md` 是 subcommand 详细说明，由对应公开方法的 docstring metadata 一比一生成，应包含：

- `When to use`；
- 参数表，来自函数签名和 `Parameters` 块；
- `Examples`；
- `Output`；
- `Safety`。

`published/doc` 是生成产物，不作为人工修改的 source of truth。未来 broker 配置方案落地后，大部分公开工具方法不再需要 `user_id` 参数；应先修改函数签名和 docstring metadata，再重新生成 `published/doc`。配置、token、password 由 `ubi-ai` broker 注入真实 tool 子进程环境，公开方法文档不应再把 `user_id` 描述为 personal secrets lookup 输入。

发布生成器不生成用户目录下的 wrapper 文件或 wrapper readme：

```text
readonly/local-tools/<wrapper>.sh
readonly/local-tools/<wrapper>.readme.md
readonly/local-tools/docs/<wrapper_id>/<subcommand>.md
```

这些文件由 `ubi-ai` 根据 catalog、用户授权、`user_id` 和 MCP servers 根目录动态 materialize。`ubi-ai` 会按实际授权 command 裁剪 wrapper 和 wrapper readme，并从 MCP servers 发布产物中拷贝已授权 subcommand 的详细说明文档。

## 解析建议

第一版生成器可以按以下步骤实现：

1. 从 CLI registry 或显式 tool registry 找到公开 subcommand 和对应 Python callable。
2. 用 `inspect.signature()` 读取函数签名、默认值和类型注解。
3. 用 `griffe` 或 `docstring-parser` 读取 docstring 原文和结构。
4. 按固定块名切分 `Tool`、`When to use`、`Parameters`、`Examples`、`Output`、`Safety`。
5. 解析 `Tool` 块里的 `key: value` 字段。
6. 执行校验规则。
7. 按 `Tool.wrapper` 分组生成 wrapper index。
8. 按 `Tool.wrapper` 和 `Tool.name` 生成 subcommand 详细文档。

如果底层 docstring parser 不能直接识别自定义块，生成器可以在拿到 docstring 原文后，用固定块标题做轻量切分；不要把解析逻辑绑定到自然语言内容。

## 和外部工具的关系

该规范不要求引入完整文档站点工具。可选工具定位如下：

- `griffe`：适合读取 Python 对象、签名、docstring 和类型信息。
- `docstring-parser`：适合解析常见 docstring 风格。
- `Sphinx Napoleon`：可作为 Google-style / NumPy-style docstring 的参考格式。
- `Click` / `Typer`：如果未来 CLI 迁移到这些框架，可以复用函数 docstring 生成 CLI help。

本项目的业务 metadata 仍以本文档定义的固定块为准。
