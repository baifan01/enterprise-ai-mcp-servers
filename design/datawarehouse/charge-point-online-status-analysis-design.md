# 充电桩在线状态分析设计文档

## 1. 背景

旧项目中已有一段基于 OCPP Heartbeat 的充电桩掉线分析逻辑，目前作为调研参考代码保留在：

```text
design/datawarehouse/databricks-investigation/src/databricks_investigation/cp_heartbeat_analysis_db.py
```

该脚本的核心类是 `ChargerHeartbeatAnalyzerDB`，核心方法是 `update_device_state()`。它按设备扫描 OCPP 事件流，使用以下规则判断疑似掉线：

```text
两个相邻 Heartbeat 间隔超过阈值；
并且上一个 Heartbeat 之后到当前 Heartbeat 之前没有其他 OCPP event；
则认为中间存在疑似掉线。
```

这份调研文档当前不再设计完整的状态时间线，也不接入 charging attempt 表。BI team 后续可能会提供更完整的数据源；在此之前，我们只实现一个足够简单、可解释、贴近旧代码逻辑的临时分析能力。

## 2. 目标

在 `databricks-investigation` 目录中实现一个按单个设备和时间窗口查询疑似掉线的能力。

输入参数不可为空：

```text
device_id / sso_id
analysis_start
analysis_end
```

输出：

```text
设备在该时间窗口内是否发生疑似掉线
疑似掉线区间列表
每个掉线区间的开始时间、恢复时间、持续时间
requested range 内第一条和最后一条可见 OCPP 事件
用于解释判断结果的 evidence
```

## 3. 当前参考逻辑

旧代码核心状态字段：

```python
self.device_state[sso_id] = {
    "last_heartbeat_time": None,
    "last_event_time": None,
    "last_event_type": None,
    "first_heartbeat_seen": False,
    "first_event_type": None,
}
```

旧代码核心判断逻辑：

```python
if event_type == "Heartbeat":
    if state["last_heartbeat_time"] is not None:
        time_diff = (event_time - state["last_heartbeat_time"]).total_seconds()

        if (
            time_diff > self.offline_threshold_seconds
            and state["last_heartbeat_time"] == state["last_event_time"]
        ):
            self.offline_periods.append((sso_id, state["last_heartbeat_time"], event_time))

    state["last_heartbeat_time"] = event_time

state["last_event_time"] = event_time
state["last_event_type"] = event_type
```

含义：

```text
Heartbeat 是默认通信健康信号。
如果两个 Heartbeat 间隔超过阈值，说明可能掉线。
但如果两个 Heartbeat 之间存在任何其他 OCPP event，说明设备仍与平台通信。
因此，只在 previous Heartbeat 之后没有其他 OCPP event 时，才输出疑似掉线。
```

简化业务解释：

```text
如果上一个 Heartbeat 后出现了 OCPP charger 相关 event，
那么直到下一个 Heartbeat 之间不管间隔多长，当前临时逻辑都不判定掉线。
```

这不是最终 BI 口径，只是当前调研阶段的保守近似。

## 4. 核心规则

### 4.1 Heartbeat 正常周期

当前业务假设：

```text
正常情况下每 15 分钟发送一次 Heartbeat。
```

即：

```text
heartbeat_interval_seconds = 900
```

### 4.2 掉线阈值

如果丢失一个 Heartbeat，则认为可能掉线。默认阈值：

```text
offline_threshold_seconds = 1800
```

也可以用公式表达：

```python
offline_threshold_seconds = heartbeat_interval_seconds * (missed_heartbeat_tolerance + 1)
```

默认配置：

```python
heartbeat_interval_seconds = 900
missed_heartbeat_tolerance = 1
offline_threshold_seconds = 1800
```

### 4.3 疑似掉线判断

当遇到当前事件为 `Heartbeat` 时：

```text
如果存在 previous Heartbeat；
并且 current Heartbeat - previous Heartbeat > offline_threshold_seconds；
并且 previous Heartbeat 之后没有任何其他 OCPP event；
则输出一个疑似掉线区间。
```

第一版继续使用旧代码的隐含判断：

```python
last_heartbeat_time == last_event_time
```

后续如果需要更清晰 evidence，可以改成显式字段：

```python
events_since_last_heartbeat: list[ConnectivityEvent]
```

但第一版不必扩大实现范围。

### 4.4 掉线开始时间

为了贴近旧代码，第一版使用：

```text
offline_start = previous_heartbeat_time
offline_restore = current_heartbeat_time
```

也就是说，如果：

```text
previous Heartbeat: 10:00
current Heartbeat: 10:50
threshold: 30 分钟
```

输出：

```text
offline_start = 10:00
offline_restore = 10:50
```

这是 legacy-compatible 口径。更精确的 `threshold_exceeded` 起点策略暂不实现。

## 5. 时间窗口边界处理

用户输入窗口：

```text
analysis_start -> analysis_end
```

当前生产工具优先保证响应时间，只查询用户输入窗口内的 OCPP event，不再额外查询窗口前或窗口后的事件。

为避免长窗口打爆 Databricks 查询和 tool response，当前在线状态查询最大时间窗口为 31 天。超过该范围的请求直接返回 invalid request，不执行 SQL。

因此返回结果必须同时说明：

```text
requested_time_from / requested_time_to:
用户请求的时间范围

observed_time_from / observed_time_to:
本次 SQL 在 requested range 内实际查到的第一条和最后一条 OCPP event 时间
```

如果 `requested_time_from` 是 `2026-01-01 08:00:00`，但第一条可见事件是 `2026-01-02 07:00:00`，工具不推断 `2026-01-01 08:00:00 -> 2026-01-02 07:00:00` 之间是否掉线，只在 coverage metadata 中说明第一条可见事件时间。

同理，如果 `requested_time_to` 是 `2026-01-10 20:00:00`，但最后一条可见事件是 `2026-01-07 10:00:00`，工具不推断 `2026-01-07 10:00:00 -> 2026-01-10 20:00:00` 之间是否掉线，只在 coverage metadata 中说明最后一条可见事件时间。

### 5.1 窗口内实际事件

只执行一条 SQL：

```text
WHERE sso_id = ?
  AND operation_timestamp >= ?
  AND operation_timestamp <= ?
ORDER BY operation_timestamp ASC
```

分析逻辑只基于这条 SQL 返回的事件流：

```text
analysis_start = first_event_in_window.operation_timestamp
analysis_end = last_event_in_window.operation_timestamp
```

如果窗口内没有任何事件：

```text
has_offline = false
offline_periods = []
observed_time_from = null
observed_time_to = null
```

### 5.2 不再查询窗口前后事件

早期设计曾计划额外查询：

```text
analysis_start 之前最近一条 OCPP event
analysis_end 之后最近一条 OCPP event
```

这会让一次在线状态分析变成多条 Databricks SQL，实际运行时响应时间和稳定性不可接受。当前实现不做这两个 edge lookup，也不返回跨 requested range 边界的掉线推断。

返回结果不再保留窗口前后事件占位字段。调用方应读取 `coverage.first_event_in_window` 和 `coverage.last_event_in_window` 来理解本次分析实际覆盖到的事件边界。

### 5.3 输出区间范围

由于当前只分析窗口内实际查到的事件，`offline_start` 和 `offline_restore` 都来自 range 内事件流，不输出跨 requested range 边界裁剪后的掉线区间。

## 6. Databricks 查询设计

### 6.1 窗口内 OCPP events

```sql
SELECT
    sso_id,
    operation_timestamp,
    ocpp_message_type
FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_ocpp_operations_v
WHERE sso_id = ?
  AND operation_timestamp >= ?
  AND operation_timestamp <= ?
ORDER BY operation_timestamp ASC
```

当前不再执行窗口前或窗口后的 edge lookup SQL。

## 7. 建议数据结构

### 7.1 请求对象

```python
@dataclass
class DeviceHeartbeatAnalysisRequest:
    device_id: str
    analysis_start: datetime
    analysis_end: datetime
    heartbeat_interval_seconds: int = 900
    missed_heartbeat_tolerance: int = 1
    recent_end_grace_seconds: int = 1800
```

校验：

```text
device_id 不可为空
analysis_start 不可为空
analysis_end 不可为空
analysis_start <= analysis_end
heartbeat_interval_seconds > 0
missed_heartbeat_tolerance >= 1
recent_end_grace_seconds >= 0
analysis_end - analysis_start <= 31 天
```

### 7.2 OCPP 事件对象

```python
@dataclass(frozen=True)
class ConnectivityEvent:
    device_id: str
    event_time: datetime
    event_type: str
```

### 7.3 疑似掉线区间

```python
@dataclass
class OfflinePeriod:
    device_id: str
    offline_start: datetime
    offline_restore: Optional[datetime]
    duration_seconds: int
    reason: str
    evidence: dict
```

### 7.4 分析结果

```python
@dataclass
class DeviceHeartbeatAnalysisResult:
    device_id: str
    analysis_start: datetime
    analysis_end: datetime
    coverage: dict
    has_offline: bool
    offline_periods: list[OfflinePeriod]
    event_count_in_window: int
    heartbeat_count_in_window: int
    summary: dict
```

## 8. 推荐模块拆分

当前实现已经进入 `servers/datawarehouse`，调研目录仅作为历史参考。

### 8.1 核心纯逻辑模块

路径：

```text
servers/datawarehouse/mcp_datawarehouse/heartbeat_gap.py
```

职责：

```text
输入已排序 OCPP events、窗口起止时间和阈值
使用 legacy-compatible Heartbeat gap 逻辑输出疑似掉线区间
不直接访问 Databricks
不直接读写文件
```

### 8.2 Databricks 查询入口

路径：

```text
servers/datawarehouse/mcp_datawarehouse/online_status.py
```

说明：

```text
当前已有 DeviceOnlineStatusQuery。
该类只查询窗口内事件，然后调用 heartbeat_gap_analyzer.py。
```

## 9. 核心算法草案

伪代码：

```python
def analyze_heartbeat_gaps(events, analysis_start, analysis_end, threshold):
    sorted_events = sorted(events, key=lambda event: event.event_time)

    last_heartbeat_time = None
    last_event_time = None
    last_event_type = None
    offline_periods = []

    for event in sorted_events:
        if event.event_type == "Heartbeat":
            if last_heartbeat_time is not None:
                gap_seconds = (event.event_time - last_heartbeat_time).total_seconds()

                if gap_seconds > threshold and last_heartbeat_time == last_event_time:
                    raw_start = last_heartbeat_time
                    raw_restore = event.event_time
                    clipped = clip_to_window(raw_start, raw_restore, analysis_start, analysis_end)
                    if clipped is not None:
                        offline_periods.append(
                            build_offline_period(
                                clipped=clipped,
                                raw_start=raw_start,
                                raw_restore=raw_restore,
                                previous_event_type=last_event_type,
                            )
                        )

            last_heartbeat_time = event.event_time

        last_event_time = event.event_time
        last_event_type = event.event_type

    return offline_periods
```

参与分析的 `events` 只包含：

```text
window_events
```

## 10. 输出示例

```json
{
  "device_id": "suby1100012048",
  "analysis_start": "2026-01-01T00:00:00Z",
  "analysis_end": "2026-01-10T00:00:00Z",
  "coverage": {
    "requested_time_from": "2026-01-01T00:00:00Z",
    "requested_time_to": "2026-01-10T00:00:00Z",
    "observed_time_from": "2026-01-02T07:00:00Z",
    "observed_time_to": "2026-01-09T23:45:00Z",
    "first_event_in_window": {
      "event_time": "2026-01-02T07:00:00Z",
      "event_type": "Heartbeat"
    },
    "last_event_in_window": {
      "event_time": "2026-01-09T23:45:00Z",
      "event_type": "Heartbeat"
    }
  },
  "has_offline": true,
  "offline_periods": [
    {
      "offline_start": "2026-01-02T07:00:00Z",
      "offline_restore": "2026-01-02T08:00:00Z",
      "duration_seconds": 3600,
      "evidence": {
        "raw_offline_start": "2026-01-02T07:00:00Z",
        "raw_offline_restore": "2026-01-02T08:00:00Z",
        "previous_heartbeat_time": "2026-01-02T07:00:00Z",
        "restore_heartbeat_time": "2026-01-02T08:00:00Z",
        "threshold_seconds": 1800,
        "clipped_to_requested_window": false
      }
    }
  ],
  "event_count_in_window": 864,
  "heartbeat_count_in_window": 860,
  "summary": {
    "offline_period_count": 1,
    "total_offline_seconds": 3600,
    "total_offline_minutes": 60.0
  }
}
```

## 11. 测试用例

建议覆盖：

```text
device_id 为空时报错
analysis_start 为空时报错
analysis_end 为空时报错
analysis_start 晚于 analysis_end 时报错
正常每 15 分钟 Heartbeat，不输出掉线
两个 Heartbeat 间隔超过阈值，且中间没有其他 OCPP event，输出掉线
两个 Heartbeat 间隔超过阈值，但中间有非 Heartbeat OCPP event，不输出掉线
第一条窗口内事件晚于 requested start 时，coverage 说明 observed start
最后一条窗口内事件早于 requested end 时，coverage 说明 observed end
窗口内没有任何事件时，coverage observed 字段为 null 且不输出掉线
```

## 12. 关键设计结论

当前阶段只实现 legacy-compatible 的简化逻辑：

```text
以 Heartbeat gap 为核心；
如果两个 Heartbeat 之间出现任何其他 OCPP event，则不判掉线；
不接入 charging attempt；
不输出完整状态时间线；
只查询 requested range 内事件；
通过 coverage 字段说明 range 内第一条和最后一条可见事件。
```

这样可以快速得到一个可用的临时分析工具。等 BI team 的正式结果或更稳定数据源可用后，再用正式口径替换当前逻辑。
