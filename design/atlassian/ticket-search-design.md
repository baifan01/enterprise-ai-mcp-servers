# Atlassian Ticket Search 轻量设计

本文档定义第一版 Atlassian Jira ticket search 的调研和未来 local tool 语义。目标是支持 agent 按结构化条件查找可能相关的 Jira work items，同时避免暴露任意 JQL。

## 设计目标

- 支持类似 Jira UI Basic search 的文本检索。
- 支持按常用结构化字段收窄查询范围。
- 返回字段可控，避免一次返回过大的 ticket JSON。
- 不允许调用方直接传任意 JQL；由 service 根据白名单参数生成 JQL。
- 凭证按 local tool 安全模式通过 `user_id` 解析，不暴露 token 给 agent。

## 凭证与 User Secret

正式 `servers/atlassian` service 采用和 CPMS、Datawarehouse 相同的 local tool 凭证模式：

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
- service、client 和 query builder 不直接读取 env。
- wrapper 不写 token、password、secret 文件路径。
- 日志、stdout、JSON result 不输出 `ATLASSIAN_API_TOKEN`。
- personal secrets 读取复用 `ubi_mcp_common.load_personal_secret_values`，保持 user id 校验和路径边界一致。

## Local Tool Wrapper 分组

Atlassian local tools 使用两个 grouped wrappers，而不是一个方法一个 `.sh`：

```text
readonly/local-tools/atlassian-read.sh
readonly/local-tools/atlassian-read.readme.md

readonly/local-tools/atlassian-write.sh
readonly/local-tools/atlassian-write.readme.md
```

ticket search 属于 read wrapper：

```bash
atlassian-read.sh search-tickets ...
atlassian-read.sh read-ticket ...
```

未来如果增加 ticket 创建、更新、评论、附件上传等修改 Jira 的能力，应放入 write wrapper：

```bash
atlassian-write.sh create-ticket ...
atlassian-write.sh update-ticket ...
atlassian-write.sh add-ticket-comment ...
atlassian-write.sh upload-ticket-attachment ...
```

wrapper 仍然只负责绑定 `--user-id` 和调用真实 Python CLI；具体 subcommand 权限和参数校验由 Atlassian CLI/service 负责。

## 第一版方法

```python
search_tickets(
    text: str | None = None,
    text_field: str = "text",
    project_keys: list[str] | None = None,
    creators: list[str] | None = None,
    assignees: list[str] | None = None,
    statuses: list[str] | None = None,
    issue_types: list[str] | None = None,
    match: str = "all",
    max_results: int = 20,
    fields: list[str] | None = None,
) -> dict
```

## 参数语义

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `text` | 否 | `None` | 文本关键词。用于查设备号、报错片段、客户名、地址片段等。 |
| `text_field` | 否 | `text` | 文本检索字段。第一版支持 `text`、`summary`、`description`。 |
| `project_keys` | 否 | `None` | Jira project key 列表，例如 `["CTI"]`。 |
| `creators` | 否 | `None` | Jira creator account/email 标识列表。 |
| `assignees` | 否 | `None` | Jira assignee account/email 标识列表。 |
| `statuses` | 否 | `None` | Jira status 名称列表，例如 `["In Progress"]`。 |
| `issue_types` | 否 | `None` | Jira issue type 名称列表，例如 `["Bug", "Task"]`。 |
| `match` | 否 | `all` | 多个 `text` 关键词的匹配方式。`all` 表示全部命中，`any` 表示任意命中。 |
| `max_results` | 否 | `20` | 最大返回数量。第一版上限为 `100`。 |
| `fields` | 否 | 默认字段集合 | 控制 Jira API 返回哪些字段，不作为查询条件。 |

## JQL 映射

文本检索：

```text
text ~ "suby1100001940"
summary ~ "heartbeat"
description ~ "firmware"
```

结构化条件：

```text
project in (CTI)
creator in ("user@example.com")
assignee in ("engineer@example.com")
status in ("In Progress", "Review Ubitricity")
issuetype in ("Bug", "Task")
```

组合查询示例：

```text
project in (CTI)
AND status in ("In Progress")
AND issuetype in ("Bug", "Task")
AND text ~ "suby1100001940"
ORDER BY updated DESC
```

多个文本关键词：

```text
# match="all"
text ~ "charger" AND text ~ "heartbeat"

# match="any"
text ~ "charger" OR text ~ "heartbeat"
```

## 默认文本字段

默认使用 `text`，对应 Jira 全局文本搜索，行为接近 UI Basic search。它通常覆盖 summary、description、comments 和其他 text fields。若用户明确要求只查描述，则使用 `description`；若只查标题，则使用 `summary`。

## 返回字段

`fields` 只控制返回内容，不影响查询条件。搜索默认返回轻量字段：

```text
summary,status,issuetype,project,priority,assignee,reporter,created,updated,labels,parent
```

读取单个 ticket 时可以使用更完整字段集合，例如：

```text
summary,status,issuetype,project,priority,assignee,reporter,created,updated,labels,components,parent,subtasks,description,comment,attachment
```

## 安全约束

- 不暴露任意 JQL 输入。
- `project_keys` 必须符合 Jira project key 格式。
- `text_field` 只能是 `text`、`summary`、`description`。
- `match` 只能是 `all` 或 `any`。
- `max_results` 必须为正数，且最多 `100`。
- 文本和字段值需要做 JQL 字符串转义。
- 凭证只从 Settings / `.env` / personal secrets 读取，不写入 wrapper、日志或输出。

## Investigation 状态

当前 `design/atlassian/investigation` 已实现初始版本：

- 按 issue key 读取 ticket；
- 按结构化条件搜索 ticket；
- 支持 `text`、`text_field`、`project_keys`、`creators`、`assignees`、`statuses`、`issue_types`、`match`、`max_results`、`fields`。
