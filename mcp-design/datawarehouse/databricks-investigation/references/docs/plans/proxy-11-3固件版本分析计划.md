# proxy-11-3 固件版本分析计划

> 状态：新建
> 创建时间：2026-03-11

## 一、目标与范围

### 第一章节：目标

基于 `data/input/proxy-11-3.log` 中的设备重试统计结果，批量查询数据仓库里的最近一条 `BootNotification` 与最近一条 `GetConfiguration` 事件，解析每个设备对应的 `firmwareVersion` 与关键配置字段，并将结果输出到 `output/proxy-11-3-analysis.csv`。

### 第二章节：目标产物

输出 CSV 包含以下八列：

1. `device_id`
2. `number of retry within 10h`
3. `firmwareVersion`
4. `ConnectorConnetionTimout`
5. `HeartbeatInterval`
6. `ConnectionTimeout`
7. `BootNotification_ocpp_request_body`
8. `GetConfiguration_ocpp_response_body`

最终结果按 `number of retry within 10h` 倒序排序。

### 第三章节：本次计划的边界

本次功能只关注：

1. 输入文件读取与解析
2. 按设备批量查询最近一条 `BootNotification`
3. 按设备批量查询最近一条 `GetConfiguration`
4. 从 `ocpp_request_body` 中提取 `firmwareVersion`
5. 从 `ocpp_response_body` 中提取配置字段
6. 保留 `BootNotification.ocpp_request_body` 与 `GetConfiguration.ocpp_response_body` 原文
7. 结果落盘到指定 CSV

本次不包含：

1. AI 分析
2. 充电尝试合并
3. OCPP 全事件时序整理
4. 写入 DuckDB

---

## 二、输入与输出定义

### 第一章节：输入文件

输入文件路径：

`data/input/proxy-11-3.log`

文件内容格式为：

```text
155 CityEV.10570.70
149 scit0100000035
145 scit0100000044
...
```

解析规则：

1. 第一列为重试次数，对应输出列 `number of retry within 10h`
2. 第二列为设备标识，对应数据仓库查询条件里的 `sso_id`
3. 输入文件可能存在空行，需要跳过

### 第二章节：数据仓库查询目标

查询表：

`emobility-uc-prd.curated-emob-ubitricity-core.charger_ocpp_operations_v`

过滤条件：

1. `sso_id` 属于输入设备列表
2. `operation_timestamp > '2026-01-01T00:00:00.000+0000'`
3. `ocpp_message_type` 属于 `BootNotification`、`GetConfiguration`
4. 每个设备每种事件只取最近一条

### 第三章节：输出文件

输出文件路径：

`output/proxy-11-3-analysis.csv`

输出规则：

1. 保留输入文件中的所有设备
2. 若查询不到 `BootNotification`，则 `firmwareVersion` 置空
3. 若查询不到 `GetConfiguration`，则三个配置字段置空
4. 若存在记录但字段无法解析，则对应列置空

---

## 三、核心实现思路

### 第一部分：读取与标准化输入

建议新增一个专用分析脚本，例如：

`scripts/analyze_proxy_firmware.py`

脚本主流程只保留高层编排：

1. 读取 `proxy-11-3.log`
2. 解析设备列表与重试次数
3. 分批查询最近一条 `BootNotification` 与最近一条 `GetConfiguration`
4. 提取 `firmwareVersion` 与配置字段
5. 保留两类事件原文
6. 汇总并写出 CSV

### 第二部分：批量查询策略

#### 第一小节：为什么不建议逐设备单查

当前输入文件约有 8700+ 行。若每个设备单独执行一条 SQL，会产生大量往返请求，执行时间长，也更容易失败。

#### 第二小节：建议方案

采用“分批查询”的方式，每批带入一组设备 ID。

建议批大小：

`500` 个设备 / 批

建议 SQL 形态：

```sql
WITH ranked_events AS (
    SELECT
        REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) AS device_id,
        ocpp_message_type,
        CAST(operation_timestamp AS STRING) AS operation_timestamp,
        ocpp_request_body,
        ocpp_response_body,
        ROW_NUMBER() OVER (
            PARTITION BY REGEXP_EXTRACT(sso_id, '^([^_]+)', 1), ocpp_message_type
            ORDER BY operation_timestamp DESC
        ) AS row_num
    FROM `emobility-uc-prd`.`curated-emob-ubitricity-core`.charger_ocpp_operations_v
    WHERE REGEXP_EXTRACT(sso_id, '^([^_]+)', 1) IN ('scit0100000043', 'suby1100006758', ...)
      AND operation_timestamp > '2026-01-01T00:00:00.000+0000'
      AND ocpp_message_type IN ('BootNotification', 'GetConfiguration')
)
SELECT
    device_id,
    ocpp_message_type,
    operation_timestamp,
    ocpp_request_body,
    ocpp_response_body
FROM ranked_events
WHERE row_num = 1
ORDER BY device_id ASC, ocpp_message_type ASC
```

说明：

1. 继续沿用现有代码中对 `sso_id` 的标准化方式：`REGEXP_EXTRACT(sso_id, '^([^_]+)', 1)`
2. 使用窗口函数按 `device_id + ocpp_message_type` 分组，只保留最近一条记录
3. 这样可以显著减少返回行数与传输量

### 第三部分：字段提取策略

#### 第一小节：主要问题

`ocpp_request_body` 很可能不是严格 JSON，而是类似下面这种 OCPP 数组字符串：

```text
[2, 1f5d8b9b-8842-41cb-87a0-dfb3f338ad6d, BootNotification, {"chargeBoxSerialNumber":"suby1100006758","firmwareVersion":"b1000c_mmsda-fs-3.0.3"}]
```

其中第 2、3 个元素未必总是标准 JSON 字符串，因此字段提取应以正则表达式为主，不依赖 JSON 解析。

#### 第二小节：建议解析顺序

按以下方式提取：

1. 对 `BootNotification.ocpp_request_body` 用正则匹配 `firmwareVersion`
2. 对 `GetConfiguration.ocpp_response_body` 用正则匹配 `configurationKey` 数组里的目标 `key/value`
3. 解析失败时返回空字符串

建议正则示例：

```python
r'"firmwareVersion"\s*:\s*"([^"]+)"'
```

#### 第三小节：GetConfiguration 字段提取

目标字段：

1. `ConnectorConnetionTimout`
2. `HeartbeatInterval`
3. `ConnectionTimeout`

兼容性处理：

1. `ConnectorConnetionTimout` 同时兼容 `ConnectorConnectionTimeout`
2. `ConnectionTimeout` 同时兼容 `ConnectionTimeOut`

建议正则思路：

```python
r'"key"\s*:\s*"HeartbeatInterval"\s*,\s*"readonly"\s*:\s*(?:true|false)\s*,\s*"value"\s*:\s*"([^"]*)"'
```

#### 第四小节：多条记录时的选择规则

建议默认规则：

1. 对同一 `device_id + ocpp_message_type`，按 `operation_timestamp` 倒序排列
2. 只取最近一条记录
3. 若该记录无法解析，则该字段输出空值

---

## 四、建议代码结构

### 第一章节：脚本层

建议新增：

`scripts/analyze_proxy_firmware.py`

职责：

1. 处理命令行参数
2. 调用分析类
3. 输出最终统计信息

### 第二章节：核心类

建议新增单文件类，例如：

`src/heartbeat_analysis/analyzers/proxy_firmware_analyzer.py`

建议类名：

`ProxyFirmwareAnalyzer`

#### 建议职责拆分

1. `run()`
   负责主流程编排
2. `_read_retry_file()`
   读取并解析 `proxy-11-3.log`
3. `_build_device_batches()`
   将设备列表按批次切分
4. `_query_latest_device_events()`
   执行单批 SQL 查询
5. `_extract_named_value()`
   用正则提取字段值
6. `_merge_single_event()`
   按事件类型填充设备结果与原文
7. `_build_output_rows()`
   组装输出行
8. `_write_output_csv()`
   写入结果文件

### 第三章节：依赖复用

直接复用已有：

1. `src/heartbeat_analysis/data/databricks_client.py`
2. 项目现有日志配置方式

不建议复用：

1. `DirectAnalyzer`
2. `DirectAttemptFinder`
3. `DirectOCPPFetcher`

原因是当前需求只需要查最近一条 `BootNotification/GetConfiguration` 并提取字段，路径更短，单独实现更清晰。

---

## 五、详细执行流程

### 第一部分：第一阶段，读取文件

步骤：

1. 打开 `data/input/proxy-11-3.log`
2. 逐行拆分为 `retry_count` 与 `device_id`
3. 转成内存列表，结构例如：

```python
[
    {"device_id": "scit0100000043", "retry_count": 140},
    {"device_id": "suby1100006758", "retry_count": 91},
]
```

### 第二部分：第二阶段，批量查数仓

步骤：

1. 从解析结果中提取全部 `device_id`
2. 分批构造 `IN (...)` 查询
3. 执行查询并收集每个设备最近一条 `BootNotification` 与最近一条 `GetConfiguration`
4. 在内存中按 `device_id` 汇总字段

### 第三部分：第三阶段，解析固件版本

步骤：

1. 遍历每个设备对应的最近一条 `BootNotification`
2. 从 `ocpp_request_body` 提取 `firmwareVersion`
3. 遍历每个设备对应的最近一条 `GetConfiguration`
4. 从 `ocpp_response_body` 提取三个配置字段
5. 生成设备最终结果映射

输出结构例如：

```python
{
    "scit0100000043": {
        "firmwareVersion": "b1000c_mmsda-fs-3.0.3",
        "ConnectorConnetionTimout": "",
        "HeartbeatInterval": "900",
        "ConnectionTimeout": "0"
    }
}
```

### 第四部分：第四阶段，生成结果文件

步骤：

1. 将输入文件中的每个设备与固件版本映射做左连接
2. 生成三列输出
3. 按 `retry_count` 倒序排序
4. 写出到 `output/proxy-11-3-analysis.csv`

---

## 六、异常与边界处理

### 第一章节：输入异常

1. 行格式不合法时，记录 warning 并跳过
2. 空行直接跳过
3. 若输入文件不存在，直接报错退出

### 第二章节：查询异常

1. 单批查询失败时，记录失败批次
2. 可选支持简单重试一次
3. 若部分批次失败，最终结果仍可输出，但需要在控制台汇总失败数量

### 第三章节：数据异常

1. 同一设备无任何 `BootNotification` 时，`firmwareVersion` 为空
2. 同一设备无任何 `GetConfiguration` 时，三个配置字段为空
3. `ocpp_request_body` 或 `ocpp_response_body` 为空时，对应字段为空
4. 文本格式异常时，对应字段为空
5. 不依赖 JSON 解析，避免非标准 OCPP 文本导致失败

---

## 七、验收标准

### 第一章节：功能验收

满足以下条件即可认为完成：

1. 能成功读取 `proxy-11-3.log`
2. 能连接 Databricks 并查询最近一条 `BootNotification` 与最近一条 `GetConfiguration`
3. 能从样例 `ocpp_request_body` 中提取出 `firmwareVersion`
4. 能从样例 `ocpp_response_body` 中提取出 `HeartbeatInterval`、`ConnectionTimeout` 等字段
5. 能生成 `output/proxy-11-3-analysis.csv`
6. CSV 列名与顺序完全符合要求
7. CSV 结果按重试次数倒序排序

### 第二章节：抽样校验

至少抽查以下几类样本：

1. 高重试设备，例如文件前几行设备
2. 中间段设备
3. 尾部仅出现 1 次的设备
4. 查不到 `BootNotification` 的设备
5. 查不到 `GetConfiguration` 的设备
6. 有记录但字段缺失的设备

---

## 八、实施建议

### 第一章节：建议实施顺序

1. 先实现输入文件解析与 CSV 输出骨架
2. 再接入 Databricks 批量查询
3. 再实现 `firmwareVersion` 与配置字段正则提取
4. 最后做抽样验证和性能观察

### 第二章节：当前默认业务假设

为了让实现可以直接开始，先采用以下假设：

1. `proxy-11-3.log` 第二列就是查询用的 `sso_id`
2. 同一设备每种事件只取最近一条记录
3. 若没有结果或无法解析，对应字段留空
