# Atlassian Wiki Page 轻量设计

本文档定义第一版 Confluence wiki page 能力。目标是让 agent 可以安全地读取、搜索和创建 Confluence 页面，同时保持参数结构化，不暴露任意 CQL、任意 HTML 或底层 API 细节。

## 设计目标

- 支持通过页面 URL 或 page id 读取完整 Wiki 页面。
- 支持按关键词搜索 Wiki 页面标题或正文。
- 支持限定在某个父页面及其所有子页面范围内搜索。
- 支持在指定父 page 或 folder 下创建新的子页面。
- 支持用新的 Markdown 正文替换已有 Wiki 页面内容。
- 创建页面时支持常用富文本结构，而不是只能写纯文本。
- 不要求调用方理解 Confluence `spaceId`、storage XHTML、CQL 等底层概念。
- 凭证按 local tool 安全模式通过 `user_id` 解析，不暴露 token 给 agent。

## 凭证与 User Secret

正式 `servers/atlassian` service 采用和 CPMS、Datawarehouse 相同的 local tool 凭证模式。Agent 可见的是用户 `readonly/local-tools/` 下的 wrapper；wrapper 固定当前用户，不让 agent 传 `--user-id`。

```text
wrapper.sh
  -> 固定传入 --user-id <current user>
  -> AtlassianSettings(user_id=...)
  -> UBI_AI_AGENT_ROOT/users/<user_id>/secrets/personal-secrets.env
  -> 读取 ATLASSIAN_* credential
```

Atlassian 标准 credential key：

```text
ATLASSIAN_BASE_URL=https://ubitricity.atlassian.net
ATLASSIAN_EMAIL=<user email>
ATLASSIAN_API_TOKEN=<api token>
```

这些 credential key 放在 `UBI_AI_AGENT_ROOT/users/<user_id>/secrets/personal-secrets.env` 中，按 `user_id` 解析。

非 secret 的工具运行配置放在工具本地环境或 `.env` 中，例如：

```text
ATLASSIAN_TIMEOUT_SECONDS=30
```

该区分与现有 CPMS、Datawarehouse MCP server 的 Settings 模式一致：用户级 token/credential 从 personal secrets 补齐，非敏感运行参数由工具环境配置。

解析顺序：

1. 优先使用运行环境中已注入的 `ATLASSIAN_*` credential。
2. 如果 credential 不完整，并且调用方提供了 `user_id`，则通过 `UBI_AI_AGENT_ROOT` 读取该用户的 `personal-secrets.env` 补齐。
3. 如果仍不完整，Settings/client 返回明确认证配置失败。

实现约束：

- 只有 `AtlassianSettings` 读取环境变量或 personal secrets。
- wiki read/search/create service 不直接读取 env。
- wrapper 不写 token、password、secret 文件路径。
- 日志、stdout、JSON result 不输出 `ATLASSIAN_API_TOKEN`。
- personal secrets 读取复用 `ubi_mcp_common.load_personal_secret_values`，保持 user id 校验和路径边界一致。

## Local Tool Wrapper 分组

Atlassian local tools 使用两个 grouped wrappers，而不是一个方法一个 `.sh`。这样可以避免未来工具数量增加后 prompt 和 wrapper 列表过长，同时保留读写风险边界。

```text
readonly/local-tools/atlassian-read.sh
readonly/local-tools/atlassian-read.readme.md

readonly/local-tools/atlassian-write.sh
readonly/local-tools/atlassian-write.readme.md
```

read wrapper 只放查询和读取类命令：

```bash
atlassian-read.sh search-tickets ...
atlassian-read.sh read-ticket ...
atlassian-read.sh search-wiki-pages ...
atlassian-read.sh read-wiki-page ...
```

write wrapper 放会修改 Atlassian 的命令：

```bash
atlassian-write.sh create-wiki-child-page ...
atlassian-write.sh update-wiki-page ...
```

未来如果新增 Jira ticket 创建、更新、评论、附件上传，或者 Confluence 页面评论、附件上传，也放入 write wrapper。

两个 wrapper 都固定当前 `user_id`，调用方不传 `--user-id`。`.readme.md` 必须清楚标记每个 subcommand 的用途、参数、是否会修改外部系统、示例和返回值重点。

## 1. 读取 Wiki 页面

### 方法

```python
read_wiki_page(
    page_id: str | None = None,
    page_url: str | None = None,
    include_footer_comments: bool = False,
) -> dict
```

### 参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `page_id` | 否 | `None` | Confluence page id。通常来自 search 返回结果。 |
| `page_url` | 否 | `None` | 用户从浏览器复制的 Confluence 页面 URL。 |
| `include_footer_comments` | 否 | `False` | 是否读取页面底部 root comments。第一版不读取 inline comments，也不递归读取 comment replies。 |

### 规则

- `page_id` 和 `page_url` 必须二选一。
- 如果传 `page_url`，service 负责从 URL 中解析 page id。
- 如果 URL 无法解析 page id，返回明确的 invalid request。
- service 内部固定使用 `body-format=storage` 读取页面正文，不把该格式选项暴露给调用方。
- 返回标准化 JSON，不直接透传 Confluence 原始大 JSON。
- `ownerId` 和 `authorId` 需要 enrich 为 display name。
- 默认不读取 comments；只有 `include_footer_comments=True` 时才读取页面底部 root footer comments。
- 第一版不读取 inline comments，不读取 nested comment replies。

### 标准返回值

```json
{
  "id": "5781061778",
  "parent_id": "5342330881",
  "space_id": "5022482379",
  "status": "current",
  "title": "DevOps Workshop Nov 2023",
  "created_at": "2023-11-03T13:01:09.284Z",
  "owner": {
    "account_id": "712020:701204fc-931b-432f-843b-8b2ea52793c7",
    "display_name": "Fan Bai"
  },
  "author": {
    "account_id": "712020:701204fc-931b-432f-843b-8b2ea52793c7",
    "display_name": "Fan Bai"
  },
  "version_number": 6,
  "body": {
    "representation": "storage",
    "value": "<p>...</p>"
  },
  "footer_comments": [
    {
      "id": "123456",
      "author": {
        "account_id": "712020:...",
        "display_name": "Fan Bai"
      },
      "created_at": "2023-11-07T11:29:23.700Z",
      "updated_at": "2023-11-07T11:29:23.700Z",
      "body": {
        "representation": "storage",
        "value": "<p>...</p>"
      }
    }
  ],
  "web_url": "https://ubitricity.atlassian.net/wiki/spaces/UM/pages/5781061778/DevOps+Workshop+Nov+2023",
  "warnings": []
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `id` | 当前页面 id。 |
| `parent_id` | 父页面 id，表示该页面挂在哪个父节点下面。 |
| `space_id` | 当前页面所属 Confluence space id。 |
| `status` | 页面状态，例如 `current`。 |
| `title` | 页面标题。 |
| `created_at` | 页面创建时间。 |
| `owner.account_id` | Confluence owner account id。 |
| `owner.display_name` | owner 的人类可读名称。 |
| `author.account_id` | Confluence author account id。 |
| `author.display_name` | author 的人类可读名称。 |
| `version_number` | 当前页面版本号。只保留 number，不返回完整 version object。 |
| `body.representation` | 第一版固定为 `storage`。 |
| `body.value` | Confluence storage XHTML 正文。 |
| `footer_comments` | 只有 `include_footer_comments=True` 时返回页面底部 root comments；否则返回空列表。 |
| `web_url` | 可在浏览器打开的页面链接。只保留 `_links.webui` 对应的完整 URL。 |
| `warnings` | 非致命降级信息，例如 user enrich 失败。 |

### User Enrich

Confluence page API 返回的是 `ownerId`、`authorId` 这类 account id。`read_wiki_page` 需要额外调用用户 API，将它们转成人可读 display name。

```text
GET /wiki/rest/api/user?accountId=<accountId>
```

enrich 规则：

- 对 `ownerId` enrich 出 `owner.display_name`。
- 对 `authorId` enrich 出 `author.display_name`。
- 如果 `ownerId` 和 `authorId` 相同，只调用一次 user API。
- 如果 user API 失败，不让整个 page read 失败；返回 `display_name: null`，并在 `warnings` 里记录降级原因。
- 不需要返回 email、avatar、locale、timezone 等其他 user profile 字段。
- footer comment 的 author 也按同样规则 enrich 为 display name。

### Footer Comments

第一版只支持读取页面底部的 root footer comments。

```text
GET /wiki/api/v2/pages/{id}/footer-comments?body-format=storage
```

读取规则：

- 仅当 `include_footer_comments=True` 时调用 comments API。
- 只读取 root footer comments。
- 不读取 inline comments。
- 不递归读取 nested replies。
- 每条 comment 只保留 `id`、`author.account_id`、`author.display_name`、`created_at`、`updated_at` 和 `body`。
- 如果 comments API 失败，不让页面主体读取失败；返回 `footer_comments: []`，并在 `warnings` 里记录降级原因。

### API

```text
GET /wiki/api/v2/pages/{id}?body-format=storage
```

## 2. 搜索 Wiki 页面

### 方法

```python
search_wiki_pages(
    text: str | list[str] | None = None,
    search_field: str = "text",
    parent_url: str | None = None,
    agent_friendly_only: bool = False,
    match: str = "all",
    max_results: int = 10,
) -> dict
```

### 参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `text` | 否 | `None` | 搜索关键词。可以是一个字符串或多个关键词。 |
| `search_field` | 否 | `text` | 搜索字段。支持 `text` 和 `title`。 |
| `parent_url` | 否 | `None` | 限定在某个父页面及其所有子页面下搜索。调用方传浏览器 URL，不直接传 id。 |
| `agent_friendly_only` | 否 | `False` | 是否只搜索带 `ubitricity-agent-friendly` label 的页面。 |
| `match` | 否 | `all` | 多关键词匹配方式。`all` 表示全部命中，`any` 表示任意命中。 |
| `max_results` | 否 | `10` | 最大返回数量。第一版上限为 `50`。 |

### 父节点搜索规则

如果传入 `parent_url`：

- 搜索范围固定为该父页面本身，以及它下面所有子页面。
- 对调用方不暴露“是否包含父节点”的参数，第一版总是包含父节点。
- 不暴露 `space_keys` 参数；如果需要限定范围，就通过 parent page 来限定。
- service 从 `parent_url` 解析 parent page id。
- Confluence CQL 的 `ancestor = <page_id>` 只覆盖子孙页面时，service 需要额外读取/匹配父页面本身，再与子孙搜索结果合并去重。

第一版固定只查 Confluence page：

```text
type = "page"
```

不暴露 content type 参数，不查 blogpost、comment、attachment。

### Label 搜索规则

通过本工具创建的页面使用以下 labels：

| Label | 说明 |
| --- | --- |
| `ubitricity-ai-generated` | 默认添加。页面由 ubitricity AI assistant local tool 生成。 |
| `ubitricity-agent-friendly` | 可选添加。仅当 `mark_agent_friendly=True` 且页面适合 agent 后续读取、总结和引用时添加。 |

`search_wiki_pages` 第一版只暴露一个布尔参数：

```python
agent_friendly_only: bool = False
```

如果 `agent_friendly_only=True`，service 自动添加：

```text
label = "ubitricity-agent-friendly"
```

不暴露任意 label 查询参数，避免 agent 用该入口扫描无关 label。

### CQL 映射

全局正文搜索：

```text
type = "page" AND text ~ "UI" ORDER BY lastmodified DESC
```

标题搜索：

```text
type = "page" AND title ~ "Design System" ORDER BY lastmodified DESC
```

父节点子树搜索：

```text
type = "page"
AND ancestor = 5449416785
AND text ~ "UI"
ORDER BY lastmodified DESC
```

只查 agent-friendly 页面：

```text
type = "page"
AND label = "ubitricity-agent-friendly"
AND text ~ "runbook"
ORDER BY lastmodified DESC
```

多关键词：

```text
# match="all"
text ~ "charger" AND text ~ "heartbeat"

# match="any"
text ~ "charger" OR text ~ "heartbeat"
```

### API

```text
GET /wiki/rest/api/search
```

## 3. 创建 Wiki 子页面

### 方法

```python
create_wiki_child_page(
    parent_url: str,
    title: str,
    body_markdown: str,
    mark_agent_friendly: bool = False,
) -> dict
```

### 参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `parent_url` | 是 | 新页面必须创建在这个 Confluence 父 page 或 folder 下面。调用方传浏览器 URL，不直接传 id。 |
| `title` | 是 | 新页面标题。 |
| `body_markdown` | 是 | 页面正文，使用受支持的 Markdown 子集。 |
| `mark_agent_friendly` | 否 | 是否给页面添加 `ubitricity-agent-friendly` label。默认 `False`。 |

### 规则

- 第一版必须指定 `parent_url`，不创建孤立页面。
- `parent_url` 可以是 Confluence page URL，也可以是 folder URL。
- service 从 `parent_url` 解析 parent id。
- resolve parent 时先尝试读取 page：`GET /wiki/api/v2/pages/{id}`。
- 如果 page 读取失败，再尝试读取 folder：`GET /wiki/api/v2/folders/{id}`。
- service 从 page 或 folder 返回中拿到所属 `spaceId`。
- service 将 `body_markdown` 转为 Confluence storage XHTML。
- 不允许调用方直接传任意 HTML 或 storage XHTML。
- 返回新页面 id、title、parent id、parent type、space id、version 和 Web URL。

### 支持的 Markdown 子集

第一版只支持普通文档结构，目标是稳定创建可读、格式整洁的页面，不处理 Confluence 高级宏和附件流程。

支持：

```text
# 一级标题
## 二级标题
### 三级标题

普通段落

- bullet list
1. numbered list

| 表头 A | 表头 B |
| --- | --- |
| 内容 A | 内容 B |

**bold**
`inline code`

```text
code block
```
```

暂不支持：

```text
Mermaid / sequence diagram 渲染
PlantUML / draw.io 等图形宏
本地图片上传和嵌入
远程图片嵌入
状态宏 / info panel / toc
用户 mention
复杂 Confluence layout / columns
```

处理规则：

- fenced code block 第一版全部转为普通 code block。
- 如果 code block 语言是 `mermaid` 或 `plantuml`，也只作为代码块保存，不渲染成图。
- 如果 Markdown 中出现图片语法，例如 `![caption](path/to/image.png)`，第一版不上传、不嵌入图片，但也不让整页创建失败。转换器应在当前位置插入一个醒目的 unsupported placeholder，说明图片未转换及原始引用。
- 表格只支持标准 Markdown pipe table，不支持合并单元格、嵌套表格或复杂富文本单元格。
- 如果某个段落或块无法按预期转换，转换器应尽量保留原始文本，并在页面顶部或底部添加 conversion notification。

后续如果需要支持 sequence diagram 或 picture，单独做第二阶段：

1. 先创建页面；
2. 上传图片或渲染出来的 diagram 作为 attachment；
3. 更新页面 body，插入 Confluence image/attachment macro。

### Markdown 转 Storage XHTML

创建页面时，agent 输出 Markdown，service 内部转换为 Confluence storage XHTML。调用方不直接传 HTML，也不直接传 storage XHTML。

建议模块：

```text
servers/atlassian/mcp_atlassian/markdown_storage.py
```

核心方法：

```python
markdown_to_storage(markdown_text: str) -> ConvertedStorageDocument
```

返回模型：

```python
@dataclass(frozen=True)
class ConvertedStorageDocument:
    value: str
    warnings: list[ConversionWarning]


@dataclass(frozen=True)
class ConversionWarning:
    type: str
    message: str
    source_excerpt: str
```

转换规则：

| Markdown | Storage XHTML |
| --- | --- |
| `# Heading` | `<h1>Heading</h1>` |
| `## Heading` | `<h2>Heading</h2>` |
| `### Heading` | `<h3>Heading</h3>` |
| 普通段落 | `<p>...</p>` |
| `- item` | `<ul><li><p>item</p></li></ul>` |
| `1. item` | `<ol><li><p>item</p></li></ol>` |
| pipe table | `<table><tbody>...</tbody></table>` |
| `**bold**` | `<strong>bold</strong>` |
| `` `code` `` | `<code>code</code>` |
| fenced code block | Confluence code macro 或普通 `<pre><code>...</code></pre>` |

实现要求：

- 必须 HTML escape 用户内容，例如 `<`, `>`, `&`, `"`.
- 只解析明确支持的 Markdown 子集。
- 不支持的图片语法不应让整页失败；必须生成 placeholder，并写入 `warnings`。
- `mermaid`、`plantuml` 等 fenced code block 只作为普通 code block 保存。
- 空正文返回一个空段落或明确 invalid request，由实现阶段决定，但行为必须有测试覆盖。
- 转换器不调用 Atlassian API，不读取 env，不处理 page id，只做纯文本转换。

### Conversion Notification

如果转换过程中发生非致命降级，例如图片未嵌入、复杂表格退化、未知块语法保留为纯文本，页面正文需要包含一个 notification block。第一版推荐放在页面顶部，避免读者忽略。

示例 storage XHTML：

```xml
<ac:structured-macro ac:name="warning">
  <ac:rich-text-body>
    <p>This page was generated from Markdown. Some content could not be fully converted.</p>
    <ul>
      <li>Unsupported image: ![Architecture](./architecture.png). Images are not uploaded in version 1.</li>
    </ul>
  </ac:rich-text-body>
</ac:structured-macro>
```

如果不使用 Confluence warning macro，至少用普通段落和列表生成同等可见的 warning section。不得静默丢弃不支持的内容。

图片 placeholder 示例：

```xml
<p><strong>[Unsupported image]</strong> alt="Architecture", source="./architecture.png". Images are not uploaded by this tool version.</p>
```

### AI Generated Page Marker

所有通过 Atlassian local tool 创建的 Wiki 页面，都必须带有稳定的 AI-generated 标识，用于和人工创建页面区分。

第一版采用两层标识：

1. 页面正文顶部插入一个固定 notice。
2. 默认给页面添加固定 label：`ubitricity-ai-generated`。

`ubitricity-agent-friendly` 不是默认 label。只有调用方明确传入 `mark_agent_friendly=True`，并且页面内容确实面向 agent 后续读取、总结和引用时，才添加该 label。

正文 notice 使用 Confluence panel macro，放在页面正文最顶部。第一版固定使用蓝色边框和浅蓝背景，让读者能一眼看到这是工具生成内容。

```xml
<ac:structured-macro ac:name="panel">
  <ac:parameter ac:name="title">AI-generated content</ac:parameter>
  <ac:parameter ac:name="borderColor">#1D7AFC</ac:parameter>
  <ac:parameter ac:name="bgColor">#E9F2FF</ac:parameter>
  <ac:rich-text-body>
    <p><strong>This page was generated by the ubitricity AI assistant local tool.</strong></p>
    <p>Please review important details before relying on or sharing this content.</p>
  </ac:rich-text-body>
</ac:structured-macro>
```

如果 Confluence label API 写入失败，不回滚页面创建；返回 warning。正文 notice 仍必须写入。

### API

```text
POST /wiki/api/v2/pages
```

请求体由 service 生成：

```json
{
  "spaceId": "<parent page or folder space id>",
  "status": "current",
  "title": "New child page title",
  "parentId": "<resolved parent id>",
  "body": {
    "representation": "storage",
    "value": "<converted storage XHTML>"
  }
}
```

## 4. 更新 Wiki 页面

### 方法

```python
update_wiki_page(
    page_url: str,
    body_markdown: str,
    title: str | None = None,
    version_message: str | None = None,
) -> dict
```

### 参数

| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `page_url` | 是 | 要更新的 Confluence 页面浏览器 URL。必须是 page URL，不支持 folder URL。 |
| `body_markdown` | 是 | 新页面正文，使用受支持的 Markdown 子集。该正文会替换原页面正文。 |
| `title` | 否 | 新标题。如果不传，保留当前页面标题。 |
| `version_message` | 否 | 可选 Confluence version message。 |

### 规则

- `page_url` 必须能解析出 page id。
- 不支持 folder URL，因为 update 的目标必须是已有 page。
- service 先读取当前页面，拿到当前 `title`、`spaceId`、`version.number` 和 Web URL。
- service 将 `body_markdown` 转为 Confluence storage XHTML。
- update 请求使用 `version.number + 1`。
- update 会替换页面正文，不做 append/merge。
- 更新后的正文顶部同样插入 AI-generated notice。
- 默认确保页面带有 `ubitricity-ai-generated` label；如果 label API 失败，不回滚页面更新，只返回 warning。
- 不允许调用方直接传任意 HTML 或 storage XHTML。

### API

```text
PUT /wiki/api/v2/pages/{id}
```

请求体由 service 生成：

```json
{
  "id": "<page id>",
  "status": "current",
  "title": "<current or replacement title>",
  "body": {
    "representation": "storage",
    "value": "<converted storage XHTML>"
  },
  "version": {
    "number": "<current version + 1>",
    "message": "<optional version message>"
  }
}
```

## 安全约束

- 不暴露任意 CQL 输入。
- 不暴露任意 HTML/storage XHTML 输入。
- `search_field` 只能是 `text` 或 `title`。
- Wiki search 第一版固定 `type = "page"`，不暴露 content type 参数。
- Wiki search 不暴露 `space_keys` 参数；需要限定范围时使用 parent page。
- `max_results` 必须为正数，且最多 `50`。
- 创建页面必须指定父 page 或 folder 的浏览器 URL。
- 创建页面前必须读取父 page 或 folder，确认用户凭证可访问父节点，并获取 `spaceId`。
- 更新页面必须指定 page URL，不支持 folder URL。
- 更新页面前必须读取当前页面，确认用户凭证可访问页面，并获取当前 `version.number`。
- 更新页面会替换原页面正文，不做自动合并。
- 凭证只从 Settings / `.env` / personal secrets 读取，不写入 wrapper、日志或输出。

## Investigation 实现顺序

1. 实现 `read_wiki_page`，支持 `page_id` 和 `page_url`。
2. 扩展 `search_wiki_pages`，支持 `parent_url` 子树查询，并固定包含父页面。
3. 实现 Markdown 到 Confluence storage XHTML 的转换器。
4. 实现 `create_wiki_child_page`。
5. 实现 `update_wiki_page`。

## 测试策略

第一版测试以本地 unit test 为主，live Atlassian API 测试只放在显式 integration/live 测试里。

### Markdown 转换器 Unit Tests

重点测试 `markdown_to_storage()`，因为这是最容易出现格式回归的部分。

建议覆盖：

- 标题转换：`#`、`##`、`###`。
- 普通段落和多段落。
- bullet list。
- numbered list。
- `**bold**` inline mark。
- `` `inline code` ``。
- fenced code block。
- `mermaid` fenced block 保留为普通 code block，不渲染。
- 标准 Markdown pipe table。
- HTML escaping：输入 `<script>`、`&`、`"` 不应变成可执行 HTML。
- 图片语法 `![caption](path.png)` 生成 warning、页面顶部 notification 和当前位置 placeholder。
- 空正文行为。
- 混合文档：标题 + 段落 + list + table + code block。

这些测试不需要网络，也不需要 `.env`。

### Wiki Read Unit Tests

用 fake Atlassian client 测：

- `page_id` 读取时调用 `/wiki/api/v2/pages/{id}`，并固定 `body-format=storage`。
- `page_url` 能解析 `/wiki/spaces/.../pages/{id}/...`。
- `page_id` 与 `page_url` 都为空时返回 invalid request。
- owner/author account id 会调用 user API enrich display name。
- owner/author 相同只调用一次 user API。
- user enrich 失败时保留 account id、display name 为 `null`，并写入 `warnings`。
- 默认不读取 footer comments。
- `include_footer_comments=True` 时读取 root footer comments，并 enrich comment author。
- comments API 失败时页面主体仍成功，`footer_comments=[]`，并写入 `warnings`。
- 标准返回值只包含设计字段，不透传原始大 JSON。

### Wiki Search Unit Tests

用 fake client 或纯 CQL builder 测：

- 默认固定 `type = "page"`。
- `search_field=text` 生成 `text ~ ...`。
- `search_field=title` 生成 `title ~ ...`。
- `match=all` 使用 `AND` 连接多关键词。
- `match=any` 使用 `OR` 连接多关键词。
- `parent_url` 能解析 page id 后生成 `ancestor = ...` 子树查询。
- 不暴露 space/content type 参数。
- `max_results` 上限为 `50`。
- CQL 字符串转义。

### Wiki Create Unit Tests

用 fake Atlassian client 测：

- 必须提供 `parent_url`。
- `parent_url` 支持 page URL 和 folder URL。
- 创建前会先尝试按 page 读取 parent，再 fallback 到 folder，并使用 parent 的 `space_id`。
- 创建请求调用 `POST /wiki/api/v2/pages`。
- 请求体包含 `spaceId`、`parentId`、`title`、`status=current`、`body.representation=storage`。
- body 来自 `markdown_to_storage()`。
- Markdown 转换产生 warning 时仍可调用 create API，但页面正文必须包含 conversion notification 和对应 placeholder。
- 只有不可恢复错误才不调用 create API，例如 title 为空、parent 不存在、Markdown 输入不是字符串、storage 生成结果为空且无法恢复。
- 创建出来的页面正文必须包含 AI-generated notice。
- 返回新页面 id、title、parent id、parent type、space id、version 和 Web URL。

### Wiki Update Unit Tests

用 fake Atlassian client 测：

- 必须提供 `page_url`。
- `page_url` 必须是 page URL，folder URL 返回 invalid request。
- 更新前读取当前页面并使用当前 `version.number + 1`。
- 不传 `title` 时保留当前页面标题。
- 传 `title` 时使用新标题。
- 请求体包含 `id`、`title`、`status=current`、`body.representation=storage`、`version.number`。
- body 来自 `markdown_to_storage()`，并包含 AI-generated notice。
- Markdown 转换产生 warning 时仍可调用 update API，但页面正文必须包含 conversion notification 和对应 placeholder。
- 默认确保页面带有 `ubitricity-ai-generated` label；label 失败只返回 warning，不回滚页面更新。
- 返回更新后页面 id、title、parent id、parent type、space id、version 和 Web URL。

### Live Tests

可选 live tests 必须显式标记，且在缺少 Atlassian credential 时 skip：

- 使用测试父 page 或 folder 创建一个短页面。
- 读取刚创建的页面。
- 更新刚创建的页面。
- 用标题关键词搜索到该页面。

live tests 不应默认运行，避免污染真实 Confluence。
