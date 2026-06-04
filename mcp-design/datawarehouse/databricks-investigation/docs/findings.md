# 抽取记录与调研发现

## 已从旧项目复用的内容

- `data/databricks_client.py` 的 Databricks 连接生命周期结构；
- `core/direct_attempt_finder.py` 的 attempt 查询、anchor 选择和相邻记录合并思路；
- `core/direct_ocpp_fetcher.py` 的 OCPP 时间窗口查询和边界扩展逻辑；
- `core/ocpp_processor.py` 的 OCPP 消息格式化逻辑；
- `data/models.py` 中 `DirectMergedAttempt` 的数据模型思路。

## 已经调整的地方

- 移除了 reference client 中硬编码的 Databricks hostname/http_path/token；
- Databricks 凭证只从 `.env` 或环境变量读取；
- 用户输入相关 SQL 使用参数化查询；
- 不迁移旧项目的 CLI 脚本；
- 不迁移 DuckDB 结果保存；
- 不迁移 AI 分析层；
- 不迁移 feedback/proxy/firmware/retry 等与当前目标无关的分析器。

## 当前已验证

- 使用新的 token 后，`SELECT 1 AS ok` 能通过新 `DatabricksClient` 成功返回：

```text
['ok']
[(1,)]
```

## 需要继续确认

- `charger_ocpp_operations_v` 的完整字段清单；
- `charger_location_charger_v` 的完整字段清单；
- `operation_timestamp` 与 `charging_attempt_start/end` 在实际查询中的时区显示行为；
- 不同市场/source 下 `sso_id` 是否总能通过 `REGEXP_EXTRACT(sso_id, '^([^_]+)', 1)` 归一化；
- OCPP 表是否需要按 `ocpp_message_type` 以外的字段过滤噪声数据。
