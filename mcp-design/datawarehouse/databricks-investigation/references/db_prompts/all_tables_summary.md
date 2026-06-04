# 数据表全表摘要（查询 Agent 选表用）

本文件用于**级联文档**的第一阶段：仅将本摘要注入系统提示，由模型根据用户意图判断需要哪些表，再按需加载对应表的完整说明文档（如 `kpi_charging_attempts_enriched_v.md`），避免一次性注入所有表详情导致上下文污染。

每行一条表记录，格式：表名（全限定）、用途（一句）、关键过滤列、适合查询（一句）、详细说明文件名。

---

- **表名（全限定）**：`emobility-uc-prd`.`curated-emob-ubitricity-core`.kpi_charging_attempts_enriched_v
- **用途（一句）**：按 Connector 粒度的充电尝试汇总视图，一行一次充电枪尝试，同一次用户充电可能多行。
- **关键过滤列**：source_device_id, charging_attempt_start, charging_attempt_end, source, session_status, transaction_stop_reason
- **适合查询**：按设备/时间范围的充电尝试、会话状态与停止原因、消费量、授权与远程启动状态、来源市场等。
- **详细说明**：kpi_charging_attempts_enriched_v.md
