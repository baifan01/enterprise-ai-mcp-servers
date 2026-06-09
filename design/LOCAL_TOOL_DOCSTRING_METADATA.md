# Local Tool Docstring Metadata 规范

本文档定义 local tool 公开方法的轻量级内部 docstring metadata 规范。它用于从真实 Python tool/subcommand 方法生成 grouped wrapper README、subcommand 详细说明和未来平台维护所需的 tool registry 信息。

这不是外部标准协议。它采用 Python docstring、类型注解和少量固定块组成，底层解析可以使用 `griffe`、`docstring-parser` 或等价库，业务语义由本文档固定。

## 设计目标

- 让 tool 的调用说明靠近实现代码，减少 README、wrapper 注册信息和真实参数之间的漂移。
- 支持平台从代码自动生成用户可见的 `*.readme.md` 和 `docs/<platform>/<subcommand>.md`。
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
| `platform` | 建议 | `atlassian` | 平台名，用于生成 `docs/<platform>/...`。 |

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
        platform: atlassian
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

校验失败时，平台生成器或发布流程应失败，不生成新的 wrapper/readme。

## 生成器输出

生成器根据该规范产生两类文档：

```text
readonly/local-tools/
  atlassian-read.sh
  atlassian-read.readme.md
  atlassian-write.sh
  atlassian-write.readme.md
  docs/
    atlassian/
      search-wiki-pages.md
      read-wiki-page.md
      create-wiki-child-page.md
      update-wiki-page.md
```

同名 `*.readme.md` 是 grouped wrapper index，应包含：

- wrapper 是 read 还是 write；
- 通用命令格式；
- subcommand 列表；
- 每个 subcommand 的 `Tool.summary`；
- 对应详细文档路径；
- 使用前读取详细文档的提醒；
- write wrapper 的外部系统修改风险提醒。

`docs/<platform>/<subcommand>.md` 是 subcommand 详细说明，应包含：

- `When to use`；
- 参数表，来自函数签名和 `Parameters` 块；
- `Examples`；
- `Output`；
- `Safety`。

## 解析建议

第一版生成器可以按以下步骤实现：

1. 从 CLI registry 或显式 tool registry 找到公开 subcommand 和对应 Python callable。
2. 用 `inspect.signature()` 读取函数签名、默认值和类型注解。
3. 用 `griffe` 或 `docstring-parser` 读取 docstring 原文和结构。
4. 按固定块名切分 `Tool`、`When to use`、`Parameters`、`Examples`、`Output`、`Safety`。
5. 解析 `Tool` 块里的 `key: value` 字段。
6. 执行校验规则。
7. 按 `Tool.wrapper` 分组生成 wrapper index。
8. 按 `Tool.platform` 和 `Tool.name` 生成 subcommand 详细文档。

如果底层 docstring parser 不能直接识别自定义块，生成器可以在拿到 docstring 原文后，用固定块标题做轻量切分；不要把解析逻辑绑定到自然语言内容。

## 和外部工具的关系

该规范不要求引入完整文档站点工具。可选工具定位如下：

- `griffe`：适合读取 Python 对象、签名、docstring 和类型信息。
- `docstring-parser`：适合解析常见 docstring 风格。
- `Sphinx Napoleon`：可作为 Google-style / NumPy-style docstring 的参考格式。
- `Click` / `Typer`：如果未来 CLI 迁移到这些框架，可以复用函数 docstring 生成 CLI help。

本项目的业务 metadata 仍以本文档定义的固定块为准。
