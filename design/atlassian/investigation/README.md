# Atlassian 调研

本目录用于调研 Atlassian Jira / Confluence API。当前先验证 Jira ticket 和 Confluence wiki 的基础能力：

1. 按 issue key 读取单个 ticket；
2. 按结构化条件搜索可能相关的 ticket；
3. 按结构化条件搜索 Confluence wiki 内容。

代码保持在独立 investigation 目录下，方便直接用本地 `.env` 验证 API 可用性。等查询流程稳定后，再迁移到正式 `servers/atlassian` local tool / MCP service。

轻量设计见 [`../ticket-search-design.md`](../ticket-search-design.md) 和 [`../wiki-page-design.md`](../wiki-page-design.md)。

## 目录结构

- `src/atlassian_investigation/`：可 import 的调研代码包；
- `.env`：本地凭证文件，不进入 git；
- `.env.example`：凭证 key 示例。

## 环境变量

当前兼容两组命名：

```text
ATLASSIAN_BASE_URL=https://your-domain.atlassian.net
ATLASSIAN_EMAIL=you@example.com
ATLASSIAN_API_TOKEN=...

# 兼容旧 Jira 脚本
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=...
```

## 运行示例

从仓库根目录运行：

```bash
PYTHONPATH=design/atlassian/investigation/src python -m atlassian_investigation.cli read-ticket CTI-15 --pretty
```

```bash
PYTHONPATH=design/atlassian/investigation/src python -m atlassian_investigation.cli search-tickets charger heartbeat --match all --max-results 20 --pretty
```

也可以指定项目范围：

```bash
PYTHONPATH=design/atlassian/investigation/src python -m atlassian_investigation.cli search-tickets firmware --project CTI --project OPS --pretty
```

结构化筛选示例：

```bash
PYTHONPATH=design/atlassian/investigation/src python -m atlassian_investigation.cli search-tickets suby1100001940 \
  --project CTI \
  --status "In Progress" \
  --issue-type Bug \
  --assignee user@example.com \
  --text-field text \
  --pretty
```

搜索 Confluence wiki：

```bash
PYTHONPATH=design/atlassian/investigation/src python -m atlassian_investigation.cli search-wiki charger heartbeat \
  --space OPS \
  --search-field text \
  --match all \
  --max-results 10 \
  --pretty
```

## 当前 API

- 读取 ticket：`GET /rest/api/3/issue/{issueKey}`
- 搜索 ticket：`GET /rest/api/3/search/jql`
- 搜索 wiki：`GET /wiki/rest/api/search`

搜索使用受控 JQL builder，不接受任意 JQL 字符串。这样后续迁移到正式 agent tool 时，可以避免 agent 构造过宽或高风险查询。
