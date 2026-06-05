# 直连数据仓库 OCPP 事件分析重构计划

> 状态：实施中  
> 创建时间：2026-02  
> 更新时间：2026-03-03

## 进度概览

| 任务 | 状态 |
|------|------|
| 创建 DirectAttemptFinder 类（core/） | ✅ 完成 |
| 创建 DirectOCPPFetcher 类（core/） | ✅ 完成 |
| 创建 DirectAnalyzer 类（analyzers/） | ✅ 完成 |
| 扩展数据模型（data/models.py） | ✅ 完成 |
| 创建入口脚本（scripts/） | ✅ 完成 |
| 编写测试用例 | ⏳ 待完成 |

---

## 一、背景与问题

### 现有问题

1. **kpi_charging_attempts_enriched_v 数据质量问题**：
  - 同一次用户尝试可能出现多条记录（事件抖动）
  - 需要合并处理才能得到真正的"用户尝试"
2. **charger_ocpp_operations_v 事件顺序问题**：
  - 事件顺序可能因通讯/硬件延迟而混乱
  - 例如：RemoteStartTransaction 可能出现在 StatusNotification.Preparing 之前
  - 两个事件可能只差几毫秒

### 解决方案

直连数据仓库，对少量尝试或用户反馈进行实时分析，包含合并逻辑和 OCPP 事件整理。

---

## 二、核心逻辑流程

```
输入: 时间戳 + EVSE_ID/SSO_ID
         ↓
步骤1: 查找附近的充电尝试记录（每个 Connector 一条）
         ↓
步骤2: 向前向后搜索临近记录（相差 ≤1 分钟）
         ↓
步骤3: 合并为用户尝试记录（内存模型）
         ↓
步骤4: 查找对应 OCPP 事件（±3秒范围 + 500ms 边界扩展）
         ↓
步骤5: 整理 OCPP 事件（offset 计算、简化 StatusNotification/MeterValues）
         ↓
步骤6: 提交 AI 分析
         ↓
步骤7: 写入结果表
```

---

## 三、详细设计

### 步骤1：查找附近的充电尝试记录

**输入**：

- `input_timestamp`: 用户指定的时间戳
- `evse_id` 或 `sso_id`: 设备标识

**查询逻辑**：

```sql
SELECT * FROM kpi_charging_attempts_enriched_v
WHERE (evse_id = ? OR source_device_id = ?)
  AND (
    -- 条件1: charging_attempt_start 在输入时间戳前后30分钟内
    charging_attempt_start BETWEEN (input_timestamp - 30min) AND (input_timestamp + 30min)
    OR
    -- 条件2: 输入时间戳在 start 和 end 之间
    (input_timestamp BETWEEN charging_attempt_start AND charging_attempt_end)
    OR
    -- 条件3: charging_attempt_end 在输入时间戳前后30分钟内
    charging_attempt_end BETWEEN (input_timestamp - 30min) AND (input_timestamp + 30min)
  )
ORDER BY ocpi_connector_id, charging_attempt_start
```

**输出**：每个 Connector 至少一条记录（可能多条）

---

### 步骤2：向前向后搜索临近记录

**逻辑**：

- 从步骤1找到的记录出发
- 向前搜索：找 `charging_attempt_start` 与当前记录相差 ≤1 分钟的记录
- 向后搜索：同理
- 递归/迭代直到没有更多临近记录

---

### 步骤3：合并为用户尝试记录

**使用现有数据模型** (`src/heartbeat_analysis/data/models.py`)：

```python
@dataclass
class DirectMergedAttempt:
    """直连查询合并后的充电尝试"""
    evse_id: str
    sso_id: str
    connector_id: int
    attempt_start: datetime
    attempt_end: datetime
    total_consumption_kwh: float
    attempt_count: int
    duration_seconds: int
    original_records: List[Dict]
    raw_ocpp_events: List[Dict] = field(default_factory=list)
    processed_events: List[Dict] = field(default_factory=list)
```

---

### 步骤4：查找对应 OCPP 事件

**查询范围**：

- 开始时间：`attempt_start - 3秒`
- 结束时间：`attempt_end + 3秒`

**边界扩展逻辑**（处理毫秒级延迟）：

- 向前扩展：检查相邻事件时间差 ≤500ms
- 向后扩展：同理

---

### 步骤5：整理 OCPP 事件

**复用现有逻辑** (`src/heartbeat_analysis/core/ocpp_processor.py`)：

```python
from src.heartbeat_analysis.core.ocpp_processor import OCPPProcessor

processor = OCPPProcessor()
anchor_time, processed_events = processor.process_events_batch(raw_events)
```

---

### 步骤6：提交 AI 分析

**复用现有逻辑** (`src/heartbeat_analysis/core/ai_analyzer.py`)：

```python
from src.heartbeat_analysis.core.ai_analyzer import AIAnalyzer

analyzer = AIAnalyzer()
result = analyzer.analyze_attempt_only(attempt_info, processed_events)
```

---

### 步骤7：写入结果表

**结果表设计**（本地 DuckDB）：

```sql
CREATE TABLE IF NOT EXISTS ocpp_ai_analysis_results (
    id BIGINT PRIMARY KEY,
    analysis_timestamp TIMESTAMP NOT NULL,
    input_timestamp TIMESTAMP,
    evse_id VARCHAR,
    sso_id VARCHAR NOT NULL,
    connector_id INTEGER,
    attempt_start TIMESTAMP,
    attempt_end TIMESTAMP,
    total_consumption_kwh DOUBLE,
    attempt_count INTEGER,
    ocpp_event_count INTEGER,
    ai_analysis_result TEXT,
    raw_ocpp_events TEXT
);
```

---

## 四、代码架构设计（基于新目录结构）

### 目录结构

```
src/heartbeat_analysis/
├── core/
│   ├── attempt_merger.py          # 现有：充电尝试合并
│   ├── ocpp_processor.py          # 现有：OCPP事件处理（复用）
│   ├── ai_analyzer.py             # 现有：AI分析（复用）
│   ├── direct_attempt_finder.py   # 【新增】直连查询尝试查找器
│   └── direct_ocpp_fetcher.py     # 【新增】直连OCPP事件获取器
├── data/
│   ├── databricks_client.py       # 现有：Databricks客户端（复用）
│   ├── duckdb_client.py           # 现有：DuckDB客户端（复用）
│   └── models.py                  # 现有 + 新增数据模型
├── analyzers/
│   ├── ocpp_analyzer.py           # 现有：本地OCPP分析
│   ├── feedback_analyzer.py       # 现有：用户反馈分析
│   └── direct_analyzer.py         # 【新增】直连数据仓库分析器
└── utils/
    ├── datetime_utils.py          # 现有：时间处理（复用）
    └── ...

scripts/
└── analyze_direct.py              # 【新增】直连分析入口脚本
```

### 新增类设计

#### 1. `DirectAttemptFinder` (core/direct_attempt_finder.py)

负责从Databricks直连查询和合并充电尝试记录。

```python
class DirectAttemptFinder:
    """
    直连数据仓库的充电尝试查找器
    
    职责：
    - 从Databricks查询附近的充电尝试
    - 搜索并合并临近记录
    - 生成合并后的用户尝试模型
    """
    
    SEARCH_WINDOW_MINUTES = 30    # 搜索窗口：±30分钟
    MERGE_THRESHOLD_SECONDS = 60  # 合并阈值：1分钟
    
    def find_nearby_attempts(input_timestamp, evse_id, sso_id) -> List[Dict]
    def find_adjacent_records(anchor_records, connector_id, all_records) -> List[Dict]
    def merge_to_user_attempt(records, evse_id, sso_id, connector_id) -> DirectMergedAttempt
    def find_and_merge(input_timestamp, evse_id, sso_id) -> List[DirectMergedAttempt]
```

#### 2. `DirectOCPPFetcher` (core/direct_ocpp_fetcher.py)

负责从Databricks查询OCPP事件并处理边界扩展。

```python
class DirectOCPPFetcher:
    """
    直连数据仓库的OCPP事件获取器
    
    职责：
    - 查询指定时间范围的OCPP事件
    - 处理边界扩展逻辑
    """
    
    TIME_BUFFER_SECONDS = 3       # 时间缓冲：±3秒
    BOUNDARY_EXPAND_MS = 500      # 边界扩展：500ms
    
    def fetch_events(sso_id, start_time, end_time, connector_id) -> List[Dict]
    def expand_boundaries(events, merged_attempt) -> Tuple[datetime, datetime]
    def fetch_and_expand(merged_attempt) -> List[Dict]
```

#### 3. `DirectAnalyzer` (analyzers/direct_analyzer.py)

主分析器，协调整个分析流程。

```python
class DirectAnalyzer:
    """
    直连数据仓库分析器
    
    职责：
    - 协调各组件完成完整分析流程
    - 调用AI分析
    - 存储分析结果
    
    依赖：
    - DatabricksClient: 数据仓库连接
    - LegacyDuckDBClient: 本地数据库连接
    - DirectAttemptFinder: 尝试查找器
    - DirectOCPPFetcher: OCPP事件获取器
    - OCPPProcessor: OCPP事件处理器（复用）
    - AIAnalyzer: AI分析器（复用）
    """
    
    def analyze(input_timestamp, evse_id, sso_id, save_result) -> List[Dict]
    def analyze_batch(inputs, save_results) -> List[Dict]
```

---

## 五、与现有代码的关系

| 功能 | 现有代码位置 | 操作 | 说明 |
|------|-------------|------|------|
| Databricks 连接 | `data/databricks_client.py` | **复用** | 使用现有的 DatabricksClient |
| DuckDB 连接 | `data/duckdb_client.py` | **复用** | 使用现有的 LegacyDuckDBClient |
| OCPP 事件处理 | `core/ocpp_processor.py` | **复用** | 使用 OCPPProcessor.process_events_batch() |
| AI 分析 | `core/ai_analyzer.py` | **复用** | 使用 AIAnalyzer |
| 充电尝试合并 | `core/attempt_merger.py` | **参考** | 新逻辑，但参考现有合并思路 |
| 直连尝试查找 | 无 | **新增** | DirectAttemptFinder |
| OCPP 边界扩展 | 无 | **新增** | DirectOCPPFetcher |
| 直连分析器 | 无 | **新增** | DirectAnalyzer |
| 结果存储 | 无 | **新增** | 在 DirectAnalyzer 中实现 |

---

## 六、测试用例

### 用例1：正常充电

- **输入**：某个正常充电的时间戳和 EVSE
- **预期**：找到完整的尝试记录和 OCPP 事件流

### 用例2：事件抖动

- **输入**：有多条 kpi 记录的情况
- **预期**：正确合并为一条用户尝试

### 用例3：事件顺序混乱

- **输入**：RemoteStartTransaction 在 Preparing 之前的情况
- **预期**：边界扩展逻辑正确处理

### 用例4：无匹配记录

- **输入**：不存在的时间/设备
- **预期**：返回空结果，不报错

### 用例5：跨Connector

- **输入**：同一充电桩两个Connector同时使用
- **预期**：分别返回两个Connector的分析结果

---

## 七、入口脚本使用方式

```bash
# 单个分析
python scripts/analyze_direct.py \
    --timestamp "2026-03-01 14:30:00" \
    --evse DE*UBI*E10071616 \
    --ai

# 使用SSO ID
python scripts/analyze_direct.py \
    --timestamp "2026-03-01 14:30:00" \
    --sso sebe1100000591 \
    --ai

# 交互模式
python scripts/analyze_direct.py --interactive

# 批量分析（从文件读取）
python scripts/analyze_direct.py --batch input.csv --output results/
```
