# Databricks 数据仓库调研背景

本目录用于支持面向业务人员的实时数据调研：业务人员提出问题，AI 辅助理解需求、生成 SQL、调用 Databricks 查询、展示结果，然后继续追问下一个问题。这个过程的核心目标不是完成某一个固定分析任务，而是验证哪些业务问题真实、高频、重要，并判断哪些能力值得沉淀为 MCP 工具或 Skill。

## 项目目标

这个项目的主要工作方式是和业务人员坐在一起，围绕真实业务问题即时探索：

1. 业务人员提出一个想看的数据问题；
2. AI 根据表说明、上下文和业务语言生成 SQL；
3. 调用 Databricks 查询并展示结果；
4. 根据结果继续追问、改条件、换维度或钻取明细；
5. 记录哪些问题反复出现、哪些查询模式有价值、哪些能力应该产品化；
6. 将成熟能力沉淀为 MCP server API、Codex Skill 或更稳定的数据查询模板。

因此，本目录不会把查询范围限制在 OCPP 或充电尝试。任何 Databricks 中与业务需求相关的数据表都可以进入调研范围。当前只是先把“充电尝试 + OCPP 序列”这条链路用代码实现出来，因为它是一个高频且查询链路较长的场景，适合先加速。

## 当前优先实现的加速能力

虽然整体目标是开放式业务 SQL 调研，但当前代码优先支持：

- 根据 `sso_id` 或 `evse_id` 定位设备；
- 查询某个设备在某个时间点附近的充电尝试；
- 将同一次真实用户行为产生的多行 attempt 合并为一次用户级尝试；
- 根据 attempt 时间窗取出相关 OCPP 消息序列；
- 将 OCPP 原始 request/response 格式化成便于人工和 AI 阅读的事件时间线。

这些能力不是最终目的，而是第一批被代码化的调研捷径。它们可以帮助快速回答一些充电过程诊断类问题，也可以作为后续判断 MCP/Skill 能力边界的样板。

## 调研产出

调研过程中需要持续沉淀三类信息：

- 表理解：哪些表回答哪些业务问题，关键字段是什么，常见过滤条件是什么；
- 查询模式：哪些 SQL 模板会反复出现，哪些参数经常由业务人员提供；
- 产品化候选：哪些查询值得封装成 MCP 工具，哪些解释流程值得封装成 Skill。

当某个查询模式满足以下特征时，优先考虑沉淀：

- 多个业务人员都会问；
- 查询逻辑稳定但 SQL 较复杂；
- 需要跨表关联或多步查询；
- 结果解释需要固定业务知识；
- 人工重复执行成本高；
- 对决策或问题定位有直接价值。

## 核心业务概念

- `sso_id`：设备内部标识。attempt 表中对应字段是 `source_device_id`，OCPP 表中通常也有 `sso_id`，但可能带后缀，因此查询时会用 `REGEXP_EXTRACT(sso_id, '^([^_]+)', 1)` 归一化。
- `evse_id`：对外 EVSE 标识。attempt 表没有 `evse_id` 字段，只有 `source_device_id`；如果用户只提供 `evse_id`，需要通过 `charger_location_charger_v` 映射到 `sso_id`。
- `connector_id`：充电枪/插座编号。attempt 表中字段是 `ocpi_connector_id`。
- 充电尝试：`kpi_charging_attempts_enriched_v` 中的一行记录，表示某个 connector 上的一次尝试。受状态抖动影响，同一次真实用户行为可能产生多行。
- OCPP 序列：`charger_ocpp_operations_v` 中某个设备在某个时间范围内的 OCPP 消息，按 `operation_timestamp` 排序。

## SQL 生成原则

- SQL 服务于业务问题验证，不预设固定查询范围；先理解用户想验证什么，再选择表和字段。
- 生成 SQL 前优先查阅 `docs/tables.md` 和 reference 中的表说明。
- catalog 和 schema 含连字符，SQL 中必须用反引号包裹，例如：

```sql
`emobility-uc-prd`.`curated-emob-ubitricity-core`.kpi_charging_attempts_enriched_v
```

- 时间默认按 UTC 理解；如果用户提供的是本地时间，需要先澄清或显式转换。
- 用户输入不要直接拼接 SQL；调研代码里应使用参数化查询。
- 对于探索性问题，优先先查小样本、聚合统计或加 `LIMIT`，确认方向后再扩大范围。
- 每次查询结果都要反过来服务下一轮业务问题，而不是只停留在“SQL 成功执行”。

## 当前代码范围

当前代码保留在范围内：

- Databricks SQL 连接；
- 任意 SQL 执行入口；
- attempt 查询和合并；
- OCPP 事件查询；
- OCPP 序列格式化；
- 支持 AI 根据表说明生成 SQL。

暂不纳入当前调研目录：

- AI 自动分析结论入库；
- DuckDB 本地持久化；
- feedback/proxy/firmware/retry 等旧项目分析器；
- CLI 脚本。

## 连接注意事项

- Databricks 凭证必须来自 `.env` 或环境变量，不写入代码。
- Databricks SQL connector 4.x 默认可能重试数分钟；调研时可以在 `.env` 中使用较小的超时/重试配置，让 token 或网络问题快速暴露：

```env
DATABRICKS_SOCKET_TIMEOUT_SECONDS=10
DATABRICKS_RETRY_STOP_AFTER_ATTEMPTS_COUNT=1
DATABRICKS_RETRY_STOP_AFTER_ATTEMPTS_DURATION_SECONDS=15
```
