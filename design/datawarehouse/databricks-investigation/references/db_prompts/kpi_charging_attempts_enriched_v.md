# 数据表说明：kpi_charging_attempts_enriched_v

（本说明面向查询 Agent，用于用户意图转 SQL。依据 `config/prompts/dbtable_prompt_generate.md` 生成。）

---

## 表名（全限定）

`emobility-uc-prd`.`curated-emob-ubitricity-core`.kpi_charging_attempts_enriched_v

- **规模**：约 685 万行（截至 2026-03 统计；行数会随数据入库增长，仅作量级参考）。该表按时间逐步递增（历史数据保留，新记录持续写入）。
- **用途**：按 Connector 粒度的充电尝试汇总视图，每条记录对应一次充电枪上的充电尝试；同一次用户充电行为可能产生多条记录（事件抖动），需按业务规则合并后使用。适合查询：按设备/时间范围的充电尝试、会话状态与停止原因、消费量、授权与远程启动状态、来源市场等。
- **类型**：视图。一行表示一次 Connector 上的充电尝试，多行可能属于同一次用户充电。
- **关联**：与 `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_ocpp_operations_v 通过 source_device_id（即 sso_id）及时间范围（charging_attempt_start / charging_attempt_end）关联，用于查询对应 OCPP 事件；与 `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_location_charger_v 通过 source_device_id 与 evse_id 映射关联（该视图无 evse_id 列，仅含 source_device_id）。
- **注意**：① 重要说明：同一次业务可能多行，同一 source_device_id + ocpi_connector_id 下启动时间相差≤60 秒的记录在业务上可视为一次用户尝试（合并规则供参考，查询时不必强制体现合并逻辑）。② 本表无 evse_id 列，按设备过滤需使用 source_device_id（即业务中的 sso_id），evse_id 需通过 charger_location_charger_v 的对应列关联得到。③ 时间戳带时区存储，默认会话下显示为 UTC；需其他时区显示时在查询端使用 SET TIME ZONE 或配置客户端（见数据仓库背景业务介绍）。

### 主要列

| 列名 | 类型 | 含义 | 备注 |
|------|------|------|------|
| table_name | string | 该行数据所来自的原始表名 | 查询时可忽略 |
| source | string | 数据来源环境（枚举，见下方「枚举型列」） | 查询时可忽略；可过滤历史/市场 |
| source_device_id | string | 设备唯一标识（即业务中的 sso_id，如 sebe1100000591） | 过滤优先使用；与 charger_ocpp_operations_v、charger_location_charger_v 关联键 |
| ocpi_connector_id | string | OCPI 充电枪编号，同一 EVSE 内唯一（如 1、2） | 与 source_device_id 共同标识一次尝试 |
| charging_attempt_start | timestamp | 充电尝试开始时间（状态由 Available→Preparing，UTC） | 过滤与关联常用 |
| charging_attempt_end | timestamp | 充电尝试结束时间（状态回到 Available，UTC） | 过滤与关联常用 |
| transaction_id | string | 充电尝试的事务 ID（来自 OCPP StartTransaction） | - |
| transaction_id_tag | string | 事务的 ID Tag | - |
| transaction_stop_reason | string | 事务停止原因（来自 OCPP StopTransaction） | - |
| authorization_status | string | 授权状态（可能为空） | 可空 |
| session_status | string | 充电会话状态 | - |
| session_charging_duration_seconds | int | 会话充电时长（秒） | 单位：秒 |
| session_consumption_kwh | decimal(7,3) | 会话充电量（kWh） | 单位：kWh |
| seconds_to_next_charging_attempt_at_same_connector | int | 同一 Connector 上距下一次充电尝试的秒数 | - |
| seconds_to_next_charging_attempt_at_same_device | int | 同一设备上距下一次充电尝试的秒数 | - |
| ts_created | timestamp | 记录创建时间（UTC） | - |
| ts_updated | timestamp | 记录最后更新时间（UTC） | - |
| ts_last_seen_date | timestamp | 来源抽取中最后见到该记录的日期（UTC） | - |
| remote_start_status | string | 远程启动状态（可能为空） | 可空 |
| charging_attempt_rank_by_device_and_time | int | 同一 EVSE 多 Connector 下按设备与时间排序的尝试序号，用于区分同一时刻多枪 Preparing | - |
| authorization_source_id | string | 授权来源 ID（可能为空） | 可空 |
| follow_up_charging_attempt | boolean | 是否存在紧随其后的下一次用户尝试；间隔很近时可能为信号抖动。间隔时长（秒，可精确到毫秒）见 seconds_to_next_charging_attempt_at_same_connector / seconds_to_next_charging_attempt_at_same_device | - |
| seconds_in_preparing | bigint | 本次尝试处于 Preparing 阶段的时长（秒） | - |
| seconds_in_charging | bigint | 本次尝试处于 Charging 阶段的时长（秒） | - |
| has_connector_lock_failure | boolean | 是否发生连接锁失败的业务故障 | - |
| attempt_with_alfen_error_304_timeout | boolean | Alfen 为专有充电桩设备型号，该型号存在 304 超时业务故障；本列表示本次尝试是否发生该故障 | - |
| invalid_session_reasons_from_source | string | 来源分析出的无效会话/故障原因，多个原因用逗号分隔，取值为 label，例如 CORRUPTED_BY_POWER_NOT_SUPPLY_TRANSACTIONS, CORRUPTED_BY_SHORT_TRANSACTIONS | - |
| connection_timeout | string | 连接超时时的超时秒数（如 140、311） | 数值字符串，非枚举 |

### 枚举型列（建议按取值过滤时使用）

以下列为**枚举或有限取值**。下述“常用值”来自对该视图的聚合统计（按出现频次 Top），可直接用于 WHERE 过滤与分组统计。

| 列名 | 说明与已知取值 |
|------|----------------|
| **source** | 数据来源环境（distinct=3）。常用值：`GCP-UBITRICITY`（历史：GCP 上的旧 CPMS，已停用）、`DRIIVZ-UBITRICITY-PROD-UB2`（荷兰市场）、`DRIIVZ-UBITRICITY-PROD-UBI`（Apex/核心市场）。 |
| **transaction_stop_reason** | 事务停止原因（distinct=12，来自 OCPP StopTransaction）。常用值：`EVDisconnected`、`Local`、`Remote`、`N/A - No stop transaction available`、`DeAuthorized`、`Other`、`PowerLoss`、`EmergencyStop`、`HardReset`、`UnlockCommand`、`SoftReset`、`Reboot`。 |
| **authorization_status** | 授权状态（distinct=4，可空）。常用值：`Accepted`、`Invalid`、`Blocked`、`Expired`。 |
| **session_status** | 充电会话状态（distinct=3）。常用值：`COMPLETED`、`INVALID`、`ACTIVE`。 |
| **remote_start_status** | 远程启动状态（distinct=3，可空）。常用值：`Accepted`、`No OCPP Response`、`Rejected`。 |
| **invalid_session_reasons_from_source** | 无效会话原因 label（distinct 组合=43，逗号分隔多值）。常见 label（按拆分后频次 Top）：`CORRUPTED_BY_POWER_NOT_SUPPLY_TRANSACTIONS`、`CORRUPTED_BY_SHORT_TRANSACTIONS`、`CORRUPTED_BY_CLOSED_WITH_METER`、`CORRUPTED_BY_LONG_FAST_TRANSACTION`、`CORRUPTED_BY_INCLUDE_DIMINISHING_METERS`、`CORRUPTED_BY_DURATION`、`CORRUPTED_BY_CLOSED_WITHOUT_METER`、`CORRUPTED_BY_NEGATIVE_TRANSACTIONS`、`CORRUPTED_BY_LARGE_TRANSACTIONS`、`CORRUPTED_BY_WRONG_START_END_DATE_TRANSACTIONS`、`CORRUPTED_BY_WRONG_POWER_PER_HOUR_TRANSACTIONS`。 |

### 查询提示

- **表名书写**：catalog 与 schema 含连字符，在 SQL 中须用反引号包裹，例如 \`emobility-uc-prd\`.\`curated-emob-ubitricity-core\`.kpi_charging_attempts_enriched_v。
- **过滤优先用**：source_device_id（按设备）、charging_attempt_start / charging_attempt_end（按时间范围）；该表无 evse_id，若只有 evse_id 需先通过 charger_location_charger_v 解析出 source_device_id 再查本表。
- **时间列**：charging_attempt_start、charging_attempt_end、ts_created、ts_updated、ts_last_seen_date 带时区存储，默认会话下显示为 UTC；需按其他时区显示时使用 SET TIME ZONE 或查 current_timezone()。
- **多值列过滤**：invalid_session_reasons_from_source 为逗号分隔多值；按单个 label 过滤时可用 LIKE '%label_name%' 或 CONTAINS(column, 'label_name')（视引擎语法而定）。
- **示例**（占位符 ? 在实际执行时替换为具体值）：`SELECT source_device_id, ocpi_connector_id, charging_attempt_start, charging_attempt_end, session_consumption_kwh FROM \`emobility-uc-prd\`.\`curated-emob-ubitricity-core\`.kpi_charging_attempts_enriched_v WHERE source_device_id = ? AND charging_attempt_start >= ? AND charging_attempt_end <= ? ORDER BY ocpi_connector_id, charging_attempt_start`
