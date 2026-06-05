# 充电桩在线状态分析设计文档

## 1. 背景

旧项目中已有一段基于 OCPP Heartbeat 的充电桩掉线分析逻辑，目前作为调研参考代码保留在：

```text
mcp-design/datawarehouse/databricks-investigation/src/databricks_investigation/cp_heartbeat_analysis_db.py
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
窗口内最后一次可见 OCPP 事件
截止 analysis_end 的最近 OCPP 事件
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

实际分析时需要额外处理窗口前和窗口后的事件，否则无法判断跨窗口掉线。

### 5.1 窗口前最近事件

必须查询 `analysis_start` 之前最近的一条 OCPP event。

目的：

```text
判断窗口开始时设备是否已经处于一个 Heartbeat gap 中；
识别从窗口开始前持续到窗口内的疑似掉线。
```

示例：

```text
analysis_start: 2026-01-01 00:00:00
previous event before start: 2025-12-01 14:20:00 Heartbeat
first event in window: 2026-01-05 00:00:00 Heartbeat
```

如果中间没有其他 OCPP event，且 gap 超过阈值，则返回一条跨窗口疑似掉线：

```text
raw offline period:
2025-12-01 14:20:00 -> 2026-01-05 00:00:00

clipped to requested window:
2026-01-01 00:00:00 -> 2026-01-05 00:00:00
```

evidence 中保留真实上一条事件：

```text
previous_heartbeat_time = 2025-12-01 14:20:00
restore_heartbeat_time = 2026-01-05 00:00:00
```

### 5.2 窗口后最近事件

如果 `analysis_end` 距离当前时间足够远，需要查询 `analysis_end` 之后最近的一条 OCPP event。

目的：

```text
判断窗口结束后是否出现恢复 Heartbeat；
识别跨过 analysis_end 的疑似掉线；
为 offline_restore 提供 evidence。
```

但如果 `analysis_end` 接近当前时间，不需要往后查询，因为未来数据本来还没有产生。

建议规则：

```text
now - analysis_end <= recent_end_grace_seconds:
    不查询窗口后事件

now - analysis_end > recent_end_grace_seconds:
    查询 analysis_end 后最近一条 OCPP event
```

默认：

```text
recent_end_grace_seconds = 1800
```

也就是：如果结束时间距离当前时刻不到约 30 分钟，视为近实时查询，不额外找窗口后的恢复事件。

### 5.3 输出区间裁剪

内部可以使用窗口前/窗口后的事件判断 raw offline period，但最终面向用户的 `offline_start` / `offline_restore` 需要裁剪到用户输入窗口。

示例：

```text
analysis_start: 10:00
analysis_end: 11:00
raw offline period: 09:45 -> 10:50
output period: 10:00 -> 10:50
```

如果 raw offline period 跨过窗口结束：

```text
analysis_start: 10:00
analysis_end: 11:00
raw offline period: 10:30 -> 12:00
output period: 10:30 -> 11:00
```

evidence 中仍保留真实恢复时间：

```text
raw_restore_time = 12:00
```

## 6. Databricks 查询设计

### 6.1 窗口内 OCPP events

```sql
SELECT
    REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) AS sso_id,
    operation_timestamp,
    ocpp_message_type
FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_ocpp_operations_v
WHERE REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) = ?
  AND operation_timestamp >= ?
  AND operation_timestamp <= ?
ORDER BY operation_timestamp ASC
```

### 6.2 窗口前最近 OCPP event

```sql
SELECT
    REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) AS sso_id,
    operation_timestamp,
    ocpp_message_type
FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_ocpp_operations_v
WHERE REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) = ?
  AND operation_timestamp < ?
ORDER BY operation_timestamp DESC
LIMIT 1
```

### 6.3 窗口后最近 OCPP event

仅当 `analysis_end` 距离当前时间超过 `recent_end_grace_seconds` 时执行：

```sql
SELECT
    REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) AS sso_id,
    operation_timestamp,
    ocpp_message_type
FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_ocpp_operations_v
WHERE REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) = ?
  AND operation_timestamp > ?
ORDER BY operation_timestamp ASC
LIMIT 1
```

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
    has_offline: bool
    offline_periods: list[OfflinePeriod]
    latest_event_before_or_at_end: Optional[ConnectivityEvent]
    previous_event_before_window: Optional[ConnectivityEvent]
    next_event_after_window: Optional[ConnectivityEvent]
    event_count_in_window: int
    heartbeat_count_in_window: int
    summary: dict
```

## 8. 推荐模块拆分

当前仍在调研目录内验证，不进入生产代码。

### 8.1 核心纯逻辑模块

路径：

```text
mcp-design/datawarehouse/databricks-investigation/src/databricks_investigation/heartbeat_gap_analyzer.py
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
mcp-design/datawarehouse/databricks-investigation/src/databricks_investigation/online_status.py
```

说明：

```text
当前已有 DeviceOnlineStatusQuery。
可以在该类中替换现有轻量 Heartbeat-only 实现，
让它查询窗口内事件、窗口前事件、必要时窗口后事件，
然后调用 heartbeat_gap_analyzer.py。
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

参与分析的 `events` 应包含：

```text
previous_event_before_window，若存在
window_events
next_event_after_window，若需要查询且存在
```

## 10. 输出示例

```json
{
  "device_id": "suby1100012048",
  "analysis_start": "2026-01-01T00:00:00Z",
  "analysis_end": "2026-01-10T00:00:00Z",
  "has_offline": true,
  "offline_periods": [
    {
      "offline_start": "2026-01-01T00:00:00Z",
      "offline_restore": "2026-01-05T00:00:00Z",
      "duration_seconds": 345600,
      "evidence": {
        "raw_offline_start": "2025-12-01T14:20:00Z",
        "raw_offline_restore": "2026-01-05T00:00:00Z",
        "previous_heartbeat_time": "2025-12-01T14:20:00Z",
        "restore_heartbeat_time": "2026-01-05T00:00:00Z",
        "threshold_seconds": 1800,
        "clipped_to_requested_window": true
      }
    }
  ],
  "latest_event_before_or_at_end": {
    "event_time": "2026-01-09T23:45:00Z",
    "event_type": "Heartbeat"
  },
  "previous_event_before_window": {
    "event_time": "2025-12-01T14:20:00Z",
    "event_type": "Heartbeat"
  },
  "next_event_after_window": null,
  "event_count_in_window": 864,
  "heartbeat_count_in_window": 860,
  "summary": {
    "offline_period_count": 1,
    "total_offline_seconds": 345600,
    "total_offline_minutes": 5760.0
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
窗口开始前上一条 Heartbeat 与窗口内第一条 Heartbeat 构成跨窗口掉线
窗口结束后下一条 Heartbeat 与窗口内最后一条 Heartbeat 构成跨窗口掉线
analysis_end 接近当前时间时，不查询窗口后事件
完全没有窗口前事件时，只基于窗口内事件判断
窗口内没有任何事件，但窗口前后 Heartbeat 构成 gap 时，输出裁剪后的掉线
```

## 12. 关键设计结论

当前阶段只实现 legacy-compatible 的简化逻辑：

```text
以 Heartbeat gap 为核心；
如果两个 Heartbeat 之间出现任何其他 OCPP event，则不判掉线；
不接入 charging attempt；
不输出完整状态时间线；
通过窗口前后一条事件补足边界判断。
```

这样可以快速得到一个可用的临时分析工具。等 BI team 的正式结果或更稳定数据源可用后，再用正式口径替换当前逻辑。
