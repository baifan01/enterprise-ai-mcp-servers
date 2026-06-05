# Driivz CPMS MCP 设计资料

Swagger 快照来源：`https://apex-migration.driivz.com:8103/api-gateway/swagger-ui/index.html`
抓取时间：`2026-06-02T12:14:24Z`

这个目录保存 Driivz CPMS MCP 的设计背景，以及一份已经登录后抓取下来的本地 OpenAPI/Swagger 快照。这样人和 agent 都可以在本地查看 API，不需要反复打开浏览器登录 Swagger。

这里不保存浏览器 session cookie、token、密码或其他 secret。

## 文件

| 文件 | 用途 |
| --- | --- |
| `business-context.md` | 公司业务语境下 Site、Charger、Device 的关系说明，用于 MCP 设计。 |
| `mcp-tool-design.md` | 第一版 MCP tool 的入口参数、返回值结构和底层 REST 调用顺序。 |
| `rest-auth-investigation.md` | REST 登录、`dmsTicket` 使用方式，以及第一个 device profile API 验证记录。 |
| `swagger/` | 本地 Swagger/OpenAPI 快照，以及从 OpenAPI 中抽取出来的 operation 目录。 |

## OpenAPI 分组

| 分组 | Paths | Operations | 来源 URL |
| --- | ---: | ---: | --- |
| `Admin-Operators` | 366 | 449 | `/api-gateway/v3/api-docs/Admin-Operators` |
| `Customers` | 1 | 1 | `/api-gateway/v3/api-docs/Customers` |

## MCP 设计注意事项

- 这里的 Swagger 文件只是文档快照，不是认证信息来源。
- 提议或实现 MCP tools 之前，先阅读 `business-context.md`；虽然 CPMS 把 device、charger、site 建模为不同对象，但公司日常业务语境里经常会混用。
- 当前线上服务访问 Swagger 依赖浏览器 session cookie，例如 `JSESSIONID`；未来 MCP 运行时认证配置应通过 `Settings` 注入，不要在业务代码里直接读取环境变量。
- 初版 MCP read tools 可以从 `swagger/operations-catalog.json` 里筛选候选 REST API，再收敛到 charger、site、reservation、transaction、tariff 等业务对象。
