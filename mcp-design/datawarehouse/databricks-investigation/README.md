# Databricks 数据仓库调研

本目录用于调研 Databricks 中的充电尝试记录和 OCPP 事件序列。代码保持在独立 investigation 目录下，方便通过 Codex 直接 import 调用；等查询流程验证稳定后，再迁移到正式 MCP server。

## 目录结构

- `src/databricks_investigation/`：可 import 的调研代码包；
- `docs/`：中文调研背景、表说明、查询流程和抽取记录；
- `references/`：从旧项目复制过来的原始参考资料；
- `.env.example`：Databricks 连接配置示例。

## 当前能力

1. 从 `.env` 读取 Databricks 连接配置；
2. 根据 `sso_id` 或 `evse_id` + 时间范围查询充电尝试；
3. 对同一用户尝试产生的多行 attempt 做合并；
4. 根据 `sso_id` + 时间范围查询 OCPP 序列；
5. 对 OCPP 序列做适合 MCP/AI 消费的轻量摘要；
6. 根据 Heartbeat 查询设备在线质量和疑似掉线区间。

## 文档入口

- [调研背景](docs/background.md)
- [数据表说明](docs/tables.md)
- [查询流程](docs/query-flow.md)
- [业务 API 调用入口](docs/business-api-entrypoints.md)
- [抽取记录与调研发现](docs/findings.md)

## 代码调用示例

从 `servers/datawarehouse` 项目根目录运行：

```bash
PYTHONPATH=databricks-investigation/src uv run python
```

```python
from datetime import datetime
from databricks_investigation import (
    AttemptFinder,
    ChargingAttemptsQuery,
    DatabricksClient,
    DeviceOnlineStatusQuery,
    OCPPSequenceQuery,
)

with DatabricksClient.from_env("databricks-investigation/.env") as client:
    attempts = ChargingAttemptsQuery(client).query(
        sso_id="sebe1100000591",
        time_from=datetime(2026, 3, 1, 14, 0),
        time_to=datetime(2026, 3, 1, 15, 0),
    )

    ocpp = OCPPSequenceQuery(client).query(
        sso_id="sebe1100000591",
        time_from=datetime(2026, 3, 1, 14, 0),
        time_to=datetime(2026, 3, 1, 15, 0),
    )

    online = DeviceOnlineStatusQuery(client).query(
        sso_id="sebe1100000591",
        time_from=datetime(2026, 3, 1, 0, 0),
        time_to=datetime(2026, 3, 2, 0, 0),
    )
```

`AttemptFinder`、`OCPPFetcher` 和 `OCPPFormatter` 仍然保留，主要用于更细的临时调试；优先给 MCP 使用的是 `ChargingAttemptsQuery`、`OCPPSequenceQuery` 和 `DeviceOnlineStatusQuery`。
