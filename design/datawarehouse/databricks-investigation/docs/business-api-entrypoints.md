# 业务 API 调用入口

本文档整理当前调研阶段建议沉淀的 4 个业务语义 API 入口。这里的 API 不是底层 REST 或 SQL，而是 AI/MCP 可以按诊断任务直接选择调用的能力。

## 总览

| API | 数据来源 | 当前状态 | 主要用途 |
| --- | --- | --- | --- |
| `get_cpms_device_context` | CPMS / Driivz | 需要从 `probe_device.py` 抽取结构化函数 | 获取设备、站点、EVSE、connector 和 CPMS 当前状态 |
| `query_charging_attempts` | Databricks | 已有 `ChargingAttemptsQuery.query()` | 查询时间范围内的充电尝试，并合并相邻 attempt |
| `query_ocpp_sequence` | Databricks | 已有 `OCPPSequenceQuery.query()` | 查询时间范围内的 OCPP 时序摘要 |
| `query_device_online_status` | Databricks | 已有 `DeviceOnlineStatusQuery.query()` | 查询 Heartbeat、最近 OCPP 事件和疑似掉线区间 |

## 1. get_cpms_device_context

### 业务语义

获取 CPMS 中某个充电桩的基础上下文和当前状态，回答：

- 这个 `device_id` 在 CPMS 里是否存在；
- 对应的 `charger_id`、`site_id`、`evse_id`、`connector_id` 是什么；
- 桩和 connector 当前是否 `AVAILABLE`、是否有 error；
- 是否 disabled、in maintenance、blocked；
- 固件版本、功率、connector 类型、认证方式、支付方式是什么；
- 位置和地址是什么。

### 输入

```json
{
  "device_id": "suby1100012048"
}
```

可选参数：

```json
{
  "include_location": true,
  "include_status_detail": true
}
```

### 输出重点

```json
{
  "device_id": "suby1100012048",
  "charger_id": 242977,
  "site_id": 8113,
  "evse_id": "GB*UBI*E10050732",
  "connector_id": 8328,
  "charger_status": "AVAILABLE",
  "connector_status": "AVAILABLE",
  "error_code": "NO_ERROR",
  "provision_status": "PROVISIONED",
  "disabled": false,
  "in_maintenance": false,
  "managed": true,
  "firmware_version": "b1000c_mmsda-fs-3.0.6",
  "max_power_kw": 5.0,
  "connector_type": "TYPE_2_MENNEKES",
  "location": {
    "address1": "14A Knoclaid Road",
    "city": "Liverpool",
    "zip_code": "L13 8DB",
    "country_code": "GBR",
    "zone_id": "Europe/London"
  }
}
```

### 当前代码来源

当前还不是干净的业务函数，逻辑在：

- `mcp-design/driivz/restapi-investigation/probe_device.py`

可复用的脚本入口是：

- `probe_device(args)`：完整探测入口；
- `InvestigationSettings`：读取 CPMS 配置；
- `DriivzClient`：底层 REST client；
- `ApiResult`：统一响应对象。

### 需要抽取

建议新增结构化函数：

```python
async def get_cpms_device_context(device_id: str) -> dict:
    ...
```

CLI 的 `probe_device(args)` 后续只负责调用该函数并打印，不再承载业务结构。

## 2. query_charging_attempts

### 业务语义

查询某个设备或 EVSE 在时间范围内的充电尝试，并把同一次真实用户行为产生的相邻 attempt 合并。

### 输入

```json
{
  "sso_id": "suby1100012048",
  "time_from": "2026-06-03T19:00:04.531Z",
  "time_to": "2026-06-03T19:30:49.982Z"
}
```

或者：

```json
{
  "evse_id": "GB*UBI*E10050732",
  "time_from": "2026-06-03T19:00:04.531Z",
  "time_to": "2026-06-03T19:30:49.982Z"
}
```

### 当前代码入口

```python
ChargingAttemptsQuery(client).query(...)
```

文件：

- `servers/datawarehouse/databricks-investigation/src/databricks_investigation/charging_attempts_query.py`

### 输出重点

- `raw_attempt_count`
- `merged_attempt_count`
- `had_adjacent_merge`
- `raw_attempts`
- `merged_attempts`
- `raw_attempts[].remote_start_status`
- `raw_attempts[].seconds_in_preparing`
- `raw_attempts[].seconds_in_charging`
- `raw_attempts[].transaction_stop_reason`

状态、停止原因和 remote start 结果保留在 `raw_attempts` 中；`merged_attempts` 只表达合并后的时间范围、attempt 数量和总电量。

## 3. query_ocpp_sequence

### 业务语义

查询某个设备在时间范围内的 OCPP 消息时序，返回紧凑摘要，让 AI 快速判断启动、授权、交易、充电、停止等流程是否发生。

### 输入

```json
{
  "sso_id": "suby1100012048",
  "time_from": "2026-06-03T19:00:04.531Z",
  "time_to": "2026-06-03T19:30:49.982Z",
  "include_heartbeats": false,
  "include_raw_payload": false
}
```

时间范围限制：

```text
include_heartbeats = true:
最大查询窗口 48 小时

include_heartbeats = false:
最大查询窗口 31 天
```

原因：Heartbeat 噪声很大，长窗口会产生过多 Databricks 结果和大体积 tool response，容易拖慢或打爆调用链。

### 当前代码入口

```python
OCPPSequenceQuery(client).query(...)
```

文件：

- `servers/datawarehouse/mcp_datawarehouse/ocpp.py`

### 输出重点

- `event_count`
- `event_type_counts`
- `events[].timestamp`
- `events[].ocpp_type`
- `events[].status`
- `events[].error_code`
- `events[].request_summary`
- `events[].response_summary`

默认不返回完整原始 payload，避免 MCP 上下文被大字段占满。

## 4. query_device_online_status

### 业务语义

根据 OCPP Heartbeat 和最近 OCPP 事件判断设备在某个时间范围内的在线质量，回答：

- 时间范围内有没有 heartbeat；
- 最近一次 heartbeat 是什么时候；
- 最近一次 OCPP 消息是什么；
- 是否出现疑似掉线区间；
- 当前窗口内在线状态是否正常。

### 输入

```json
{
  "sso_id": "suby1100012048",
  "time_from": "2026-06-03T19:00:04.531Z",
  "time_to": "2026-06-03T19:30:49.982Z",
  "expected_heartbeat_interval_minutes": 15,
  "missing_heartbeat_threshold": 2
}
```

### 当前代码入口

```python
DeviceOnlineStatusQuery(client).query(...)
```

文件：

- `servers/datawarehouse/databricks-investigation/src/databricks_investigation/online_status.py`

### 输出重点

- `latest_ocpp_event`
- `latest_heartbeat`
- `heartbeat_count`
- `heartbeat_samples`
- `offline_periods`
- `online_summary.status`

## AI 调用建议

一次典型“用户启动失败”诊断可以这样选择：

1. 先调用 `get_cpms_device_context`，确认 CPMS 中设备存在、状态正常、connector 可用；
2. 调用 `query_charging_attempts`，看用户时间附近是否有 attempt，以及 attempt 是否进入 charging；
3. 调用 `query_ocpp_sequence`，看 OCPP 是否出现 RemoteStartTransaction、StartTransaction、StatusNotification、MeterValues；
4. 只有当怀疑通信问题时，再调用 `query_device_online_status`，检查 heartbeat 和掉线区间。

这 4 个入口保持相互独立，AI 可以按问题选择性调用，不强制包成一个大诊断函数。
