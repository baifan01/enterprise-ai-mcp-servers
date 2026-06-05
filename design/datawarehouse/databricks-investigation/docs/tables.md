# 数据表说明

本文件面向 Databricks 调研和 SQL 生成。优先记录当前“充电尝试 + OCPP 序列”链路所需的数据表、字段、关联方式和查询注意事项。

## 表清单

| 用途 | 表名 |
|------|------|
| 充电尝试汇总 | `emobility-uc-prd`.`curated-emob-ubitricity-core`.kpi_charging_attempts_enriched_v |
| OCPP 操作事件 | `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_ocpp_operations_v |
| EVSE 与 SSO 映射 | `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_location_charger_v |

---

## kpi_charging_attempts_enriched_v

### 表名（全限定）

```sql
`emobility-uc-prd`.`curated-emob-ubitricity-core`.kpi_charging_attempts_enriched_v
```

### 表用途

按 Connector 粒度的充电尝试汇总视图。每行表示一次充电枪上的充电尝试。由于设备状态抖动或业务数据质量问题，同一次用户充电行为可能产生多行，调研时通常需要结合 `source_device_id + ocpi_connector_id + 时间` 合并理解。

适合查询：

- 某个设备在某段时间附近的充电尝试；
- 充电会话状态；
- 事务停止原因；
- 授权状态；
- 远程启动状态；
- 会话充电量；
- 异常/无效 session 的来源原因；
- 进一步定位对应 OCPP 事件序列的时间窗口。

### 规模与类型

- 类型：视图。
- 规模：约 685 万行（截至 2026-03 的历史统计，仅作量级参考，实际会持续增长）。
- 数据时间特征：按时间逐步递增，历史数据保留，新记录持续入库。

### 关联关系

- 与 OCPP 操作事件表 `charger_ocpp_operations_v` 关联：
  - `kpi_charging_attempts_enriched_v.source_device_id` 对应 OCPP 表中的归一化 `sso_id`；
  - 时间范围使用 `charging_attempt_start` / `charging_attempt_end` 对应 `operation_timestamp`。
- 与设备位置/映射表 `charger_location_charger_v` 关联：
  - attempt 表没有 `evse_id` 字段；
  - 如果用户只提供 `evse_id`，需要先通过 `charger_location_charger_v` 查到 `sso_id`，再用 `source_device_id` 查 attempt。

### 重要注意事项

- 本表无 `evse_id` 列，按设备过滤时优先使用 `source_device_id`。
- 同一次真实用户充电行为可能有多行。经验规则：同一 `source_device_id + ocpi_connector_id` 下，启动时间相差不超过 60 秒的记录，业务上可视为一次用户尝试。
- 时间戳带时区存储，默认会话下通常显示为 UTC；如果用户问题使用本地时间，需要显式澄清或转换。
- catalog 和 schema 含连字符，SQL 必须使用反引号。

### 主要列

| 列名 | 类型 | 含义 | 查询备注 |
|------|------|------|----------|
| `table_name` | string | 该行数据所来自的原始表名 | 通常可忽略 |
| `source` | string | 数据来源环境 | 可用于区分历史/市场 |
| `source_device_id` | string | 设备唯一标识，即业务中的 `sso_id`，如 `sebe1100000591` | 设备过滤首选字段；与 OCPP 和位置映射表关联 |
| `ocpi_connector_id` | string | OCPI 充电枪编号，同一 EVSE 内唯一，如 `1`、`2` | 与 `source_device_id` 一起标识 connector 上的一次尝试 |
| `charging_attempt_start` | timestamp | 充电尝试开始时间，通常对应状态 Available -> Preparing | 时间过滤和 OCPP 关联常用 |
| `charging_attempt_end` | timestamp | 充电尝试结束时间，通常对应状态回到 Available | 时间过滤和 OCPP 关联常用 |
| `transaction_id` | string | 充电尝试事务 ID，来自 OCPP StartTransaction | 可用于与 OCPP Start/StopTransaction 交叉验证 |
| `transaction_id_tag` | string | 事务的 ID Tag | 授权/用户标识相关调研可能用到 |
| `transaction_stop_reason` | string | 事务停止原因，来自 OCPP StopTransaction | 故障分析常用 |
| `authorization_status` | string | 授权状态，可能为空 | 远程启动/授权失败调研常用 |
| `session_status` | string | 充电会话状态 | 常见为 `COMPLETED`、`INVALID`、`ACTIVE` |
| `session_charging_duration_seconds` | int | 会话充电时长，单位秒 | 与 OCPP Charging 状态持续时间对照 |
| `session_consumption_kwh` | decimal(7,3) | 会话充电量，单位 kWh | 判断是否实际充电 |
| `seconds_to_next_charging_attempt_at_same_connector` | int | 同一 connector 距下一次充电尝试的秒数 | 判断连续尝试/抖动 |
| `seconds_to_next_charging_attempt_at_same_device` | int | 同一设备距下一次充电尝试的秒数 | 判断多枪/设备级连续尝试 |
| `ts_created` | timestamp | 记录创建时间 | 数据新鲜度/入库调研 |
| `ts_updated` | timestamp | 记录最后更新时间 | 数据更新调研 |
| `ts_last_seen_date` | timestamp | 来源抽取中最后见到该记录的日期 | 数据同步调研 |
| `remote_start_status` | string | 远程启动状态，可能为空 | 远程启动失败调研常用 |
| `charging_attempt_rank_by_device_and_time` | int | 同一 EVSE 多 connector 下按设备与时间排序的尝试序号 | 区分同一时刻多枪 Preparing |
| `authorization_source_id` | string | 授权来源 ID，可能为空 | 授权链路调研可能用到 |
| `follow_up_charging_attempt` | boolean | 是否存在紧随其后的下一次用户尝试 | 间隔很近时可能表示信号抖动或用户重试 |
| `seconds_in_preparing` | bigint | 本次尝试处于 Preparing 阶段的时长，单位秒 | 插枪/准备阶段问题调研 |
| `seconds_in_charging` | bigint | 本次尝试处于 Charging 阶段的时长，单位秒 | 实际充电阶段调研 |
| `has_connector_lock_failure` | boolean | 是否发生连接锁失败的业务故障 | 锁枪失败调研常用 |
| `attempt_with_alfen_error_304_timeout` | boolean | Alfen 专有充电桩 304 超时故障标识 | Alfen 设备专项调研 |
| `invalid_session_reasons_from_source` | string | 来源分析出的无效会话/故障原因，多个原因逗号分隔 | INVALID session 调研常用 |
| `connection_timeout` | string | 连接超时时的超时秒数，如 `140`、`311` | 数值字符串 |

### 枚举和常见取值

| 列名 | 常见取值/说明 |
|------|---------------|
| `source` | `GCP-UBITRICITY`（历史 GCP 旧 CPMS，已停用）、`DRIIVZ-UBITRICITY-PROD-UB2`（荷兰市场）、`DRIIVZ-UBITRICITY-PROD-UBI`（Apex/核心市场） |
| `transaction_stop_reason` | `EVDisconnected`、`Local`、`Remote`、`N/A - No stop transaction available`、`DeAuthorized`、`Other`、`PowerLoss`、`EmergencyStop`、`HardReset`、`UnlockCommand`、`SoftReset`、`Reboot` |
| `authorization_status` | `Accepted`、`Invalid`、`Blocked`、`Expired`，也可能为空 |
| `session_status` | `COMPLETED`、`INVALID`、`ACTIVE` |
| `remote_start_status` | `Accepted`、`No OCPP Response`、`Rejected`，也可能为空 |
| `invalid_session_reasons_from_source` | 常见 label 包括 `CORRUPTED_BY_POWER_NOT_SUPPLY_TRANSACTIONS`、`CORRUPTED_BY_SHORT_TRANSACTIONS`、`CORRUPTED_BY_CLOSED_WITH_METER`、`CORRUPTED_BY_LONG_FAST_TRANSACTION`、`CORRUPTED_BY_INCLUDE_DIMINISHING_METERS`、`CORRUPTED_BY_DURATION`、`CORRUPTED_BY_CLOSED_WITHOUT_METER`、`CORRUPTED_BY_NEGATIVE_TRANSACTIONS`、`CORRUPTED_BY_LARGE_TRANSACTIONS`、`CORRUPTED_BY_WRONG_START_END_DATE_TRANSACTIONS`、`CORRUPTED_BY_WRONG_POWER_PER_HOUR_TRANSACTIONS` |

### 常用查询

#### 按 SSO 和时间范围查 attempt

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
  session_consumption_kwh,
  seconds_in_preparing,
  seconds_in_charging,
  invalid_session_reasons_from_source
FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.kpi_charging_attempts_enriched_v
WHERE source_device_id = ?
  AND charging_attempt_start >= ?
  AND charging_attempt_end <= ?
ORDER BY ocpi_connector_id, charging_attempt_start
```

#### 查某时间点附近的候选 attempt

```sql
SELECT
  source_device_id,
  ocpi_connector_id,
  charging_attempt_start,
  charging_attempt_end,
  session_status,
  transaction_stop_reason,
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

#### 按无效 session 原因过滤

```sql
SELECT
  source_device_id,
  ocpi_connector_id,
  charging_attempt_start,
  charging_attempt_end,
  session_status,
  invalid_session_reasons_from_source
FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.kpi_charging_attempts_enriched_v
WHERE invalid_session_reasons_from_source LIKE ?
ORDER BY charging_attempt_start DESC
LIMIT 100
```

---

## charger_ocpp_operations_v

### 表名（全限定）

```sql
`emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_ocpp_operations_v
```

### 表用途

OCPP 操作事件视图，用于查看充电桩与后台之间的 OCPP 消息。当前调研主要用它在 attempt 时间窗口内取出消息序列，以解释启动、授权、状态变化、交易开始/结束和异常。

### 已由旧代码验证使用的列

| 列名 | 含义 | 查询备注 |
|------|------|----------|
| `sso_id` | 设备内部标识 | 可能带后缀，旧代码使用 `REGEXP_EXTRACT(sso_id, '^([^_]+)', 1)` 取基础 SSO |
| `operation_timestamp` | OCPP 操作时间 | 与 attempt 的 `charging_attempt_start/end` 关联 |
| `ocpp_message_type` | OCPP 消息类型 | 常见如 `StatusNotification`、`RemoteStartTransaction`、`StartTransaction`、`StopTransaction`、`MeterValues`、`Heartbeat` |
| `ocpp_request_body` | OCPP request 内容 | JSON/类 JSON 字符串，常用于提取 `connectorId`、状态、事务等 |
| `ocpp_response_body` | OCPP response 内容 | 用于查看 Accepted/Rejected、响应缺失等 |

### 查询注意事项

- 诊断单次充电尝试时，通常过滤 `Heartbeat`，因为心跳消息噪声很大。
- 为避免边界事件丢失，查询时间范围建议使用 attempt 起止时间前后各扩展 3 秒。
- 如果事件刚好在 attempt 边界外 500 ms 内，仍可能属于该次尝试，需要结合上下文判断。
- `StatusNotification` 重点看 request body 中的 `status` 和 `errorCode`。
- `RemoteStartTransaction` / `StartTransaction` / `StopTransaction` 重点看 request/response 中的事务、授权和状态字段。

### 常用查询

#### 查某设备某时间范围内 OCPP 序列

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

#### 只查状态变化

```sql
SELECT
  operation_timestamp,
  ocpp_message_type,
  ocpp_request_body,
  ocpp_response_body
FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_ocpp_operations_v
WHERE REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) = ?
  AND operation_timestamp >= ?
  AND operation_timestamp <= ?
  AND ocpp_message_type = 'StatusNotification'
ORDER BY operation_timestamp ASC
```

### 待补充

当前新目录中还没有该表的完整 DESCRIBE 结果和枚举统计。后续建议补充：

- 完整字段清单；
- `ocpp_message_type` distinct 值；
- `sso_id` 是否存在多种后缀模式；
- request/response body 的常见结构样例。

---

## charger_location_charger_v

### 表名（全限定）

```sql
`emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_location_charger_v
```

### 表用途

设备与位置/EVSE 映射视图。当前主要用于把用户提供的 `evse_id` 转换为 attempt 表可查询的 `sso_id`。

### 已由旧代码验证使用的列

| 列名 | 含义 | 查询备注 |
|------|------|----------|
| `evse_id` | 对外 EVSE 标识 | 用户常提供该值；可能需要 LIKE 匹配 |
| `sso_id` | 设备内部标识 | 用于关联 attempt 表 `source_device_id` |
| `sso_valid_to` | SSO 映射有效截止日期 | 查询当前有效映射时使用 `sso_valid_to IS NULL OR sso_valid_to > CURRENT_DATE()` |

### 常用查询

#### 根据 EVSE 查当前有效 SSO

```sql
SELECT
  evse_id,
  sso_id,
  sso_valid_to
FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_location_charger_v
WHERE evse_id LIKE ?
  AND (sso_valid_to IS NULL OR sso_valid_to > CURRENT_DATE())
LIMIT 20
```

### 查询注意事项

- attempt 表没有 `evse_id`，不要直接在 attempt 表上按 `evse_id` 过滤。
- 如果一个 `evse_id` 映射出多个 `sso_id`，需要结合 `sso_valid_to`、设备状态和时间范围判断使用哪一个。
- 旧代码使用 `LIKE '%evse_id%'`，适合处理同一字段包含多个 EVSE 值的情况；如果后续确认字段格式稳定，可改成精确匹配。

### 待补充

当前新目录中还没有该表的完整字段说明。后续建议补充：

- 完整字段清单；
- `evse_id` 是否可能一行多个值；
- SSO 有效期字段的历史记录规则；
- 与 location、charger information 相关字段。
