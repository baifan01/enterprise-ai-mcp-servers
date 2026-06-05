# Driivz CPMS Swagger 快照

这个目录保存用于 MCP 设计的本地 Swagger/OpenAPI 快照。快照是在浏览器已登录的前提下抓取的。

这里不保存浏览器 session cookie、token、密码或其他 secret。

## 文件

| 文件 | 用途 |
| --- | --- |
| `swagger-config.json` | Swagger UI 配置，以及可用的 OpenAPI 分组。 |
| `admin-operators.json` | `Admin-Operators` 分组的 OpenAPI JSON，已格式化。 |
| `customers.json` | `Customers` 分组的 OpenAPI JSON，已格式化。 |
| `operations-catalog.json` | 从 OpenAPI 文档抽取出来的扁平 operation 列表，适合脚本或 agent 读取。 |
| `operations-catalog.md` | 按 OpenAPI 分组整理的人类可读 operation 目录。 |

## 来源

Swagger 快照来源：`https://apex-migration.driivz.com:8103/api-gateway/swagger-ui/index.html`

抓取时间：`2026-06-02T12:14:24Z`

## OpenAPI 分组

| 分组 | Paths | Operations | 来源 URL |
| --- | ---: | ---: | --- |
| `Admin-Operators` | 366 | 449 | `/api-gateway/v3/api-docs/Admin-Operators` |
| `Customers` | 1 | 1 | `/api-gateway/v3/api-docs/Customers` |
