# 查询流程

本文件描述当前调研代码默认采用的查询流程。它既可以作为人工查询指南，也可以作为 AI 生成 SQL 的上下文。

## 输入参数

至少需要一个设备标识：

- `sso_id`：推荐，最直接；
- `evse_id`：如果只有该值，需要先映射到 `sso_id`。

MCP 候选 API 优先使用时间范围：

- `time_from`：查询开始时间，默认按 UTC 理解；
- `time_to`：查询结束时间，默认按 UTC 理解。

旧的点位调试代码仍然支持：

- `timestamp`：用户关心的时间点，默认按 UTC 理解；
- 时间窗口：默认 `timestamp ± 30 分钟`。

常用可选条件：

- 是否包含 `Heartbeat`：诊断 OCPP 序列时默认过滤；
- 是否只查原始 attempt 行，还是合并成用户尝试。

## MCP 候选查询入口

当前调研代码里，优先面向 MCP 沉淀的查询入口是：

- `ChargingAttemptsQuery.query()`：输入 `sso_id` 或 `evse_id`、`time_from`、`time_to`，返回原始 attempt 和合并后的用户级 attempt；
- `OCPPSequenceQuery.query()`：输入 `sso_id`、`time_from`、`time_to`，返回按时间排序的 OCPP 事件摘要，默认不返回大体积原始 payload；
- `DeviceOnlineStatusQuery.query()`：输入 `sso_id`、`time_from`、`time_to`，返回最近 OCPP 事件、Heartbeat 样本、疑似掉线区间和在线状态摘要。

## timestamp 调试流程

1. 如果只有 `evse_id`，先查 `charger_location_charger_v`，解析出有效 `sso_id`。
2. 用 `source_device_id = sso_id` 查询 `kpi_charging_attempts_enriched_v` 中时间附近的候选 attempt。
3. 选择 anchor attempt：
   - 优先选择包含输入时间点的记录；
   - 如果没有包含时间点的记录，选择与输入时间点距离最近的记录。
4. 在同一 `source_device_id + ocpi_connector_id` 下合并相邻 attempt：
   - `charging_attempt_start` 相差不超过 60 秒；
   - 或前一条 `charging_attempt_end` 到后一条 `charging_attempt_start` 间隔不超过 5 分钟。
5. 根据合并后的 `attempt_start` / `attempt_end` 查询 `charger_ocpp_operations_v`：
   - 查询范围默认向前/向后各扩展 3 秒；
   - 默认过滤 `Heartbeat`；
   - 按 `operation_timestamp` 升序排序。
6. 检查 OCPP 边界：
   - 如果 attempt 边界外的相邻事件距离边界不超过 500 ms，则把边界扩展到该事件。
7. 格式化 OCPP 序列：
   - 计算相对第一条事件的秒级 offset；
   - `StatusNotification` 提取 `status` 和 `errorCode`；
   - `MeterValues` 默认简化；
   - 其他消息保留 request/response 原文。

## 典型 SQL 片段

### 查某设备某时间附近的 attempt

```sql
SELECT
  source_device_id,
  ocpi_connector_id,
  charging_attempt_start,
  charging_attempt_end,
  session_status,
  transaction_stop_reason,
  authorization_status,
  remote_start_status,
  session_consumption_kwh
FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.kpi_charging_attempts_enriched_v
WHERE source_device_id = ?
  AND (
    charging_attempt_start BETWEEN ? AND ?
    OR ? BETWEEN charging_attempt_start AND charging_attempt_end
    OR charging_attempt_end BETWEEN ? AND ?
  )
ORDER BY ocpi_connector_id, charging_attempt_start
```

### 查某 attempt 的 OCPP 序列

```sql
SELECT
  REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) AS normalized_sso_id,
  operation_timestamp,
  ocpp_message_type,
  ocpp_request_body,
  ocpp_response_body
FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_ocpp_operations_v
WHERE REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) = ?
  AND operation_timestamp >= ?
  AND operation_timestamp <= ?
  AND ocpp_message_type != 'Heartbeat'
ORDER BY operation_timestamp ASC
```

## 输出结果

旧调试链路中的主要输出是 `OCPPSequenceResult`：

- 合并后的 attempt 元数据；
- 原始 OCPP 事件；
- 格式化后的 OCPP 事件序列。

MCP 候选查询入口返回的是 JSON-friendly `dict`，字段命名尽量贴近业务判断：

- `raw_attempts` / `merged_attempts`：支持 AI 判断一次用户行为是否被多行 attempt 拆开；
- `event_type_counts` / `events`：支持 AI 快速看 OCPP 流程是否进入 StartTransaction、Charging、StopTransaction；
- `online_summary` / `offline_periods` / `latest_heartbeat`：支持 AI 判断设备通信是否正常。
