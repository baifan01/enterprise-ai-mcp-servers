# Driivz REST 认证验证记录

本文档记录 Driivz CPMS REST API 在 investigation 阶段验证通过的登录模式和 `dmsTicket` 使用方式。

本文档是设计研究记录，不参与代码生成，也不作为生产 MCP Server 的实现规范。它的作用是保留 investigation 过程中验证过的事实、实验结论和背景线索，帮助后续设计工作理解认证方案来源。

第一版 MCP Server 的实现决策以 `mcp-tool-design.md` 为准；如果本文档中的探索性策略与 tool design 不一致，采用 tool design。

## 验证日期

`2026-06-02`

## 生产环境 Base URL

```text
https://apex-prod.driivz.com:8103/api-gateway
```

注意：之前测试过 `https://cpms-global.ubitricity.com:8103/api-gateway`，但当前生产 REST 登录验证通过的是 `apex-prod.driivz.com:8103`。

## 登录 API

```text
POST /v1/authentication/operator/login
```

完整 URL：

```text
https://apex-prod.driivz.com:8103/api-gateway/v1/authentication/operator/login
```

请求 headers：

```text
Content-Type: application/json
Accept: application/json
```

请求 body：

```json
{
  "password": "<password>",
  "userName": "<email>"
}
```

返回结果中包含 `ticket` 字段。该值用于后续 REST API 请求的 `dmsTicket` header。

## 后续 API 认证方式

Swagger 中 REST API 的 security scheme 是：

```text
dmsTicket header
```

后续 REST API 请求应带：

```text
dmsTicket: <ticket from login response>
```

浏览器 cookie 在 production REST API 验证中没有通过 `POST /v1/chargers/profiles/filter`，返回 `403 Forbidden`。因此，第一版 REST client 应优先实现 `userName/password -> dmsTicket` 的登录流程，而不是依赖 browser cookie。

## Ticket 生命周期与缓存策略

Swagger 中没有说明 `dmsTicket` 的有效期限。当前已检查到的信息包括：

- Login response 只定义 `ticket` 字段。
- REST API security scheme 使用 `dmsTicket` header。
- Swagger 中没有看到 `expires`、`expiration`、`ttl`、`refresh`、`logout` 等字段或接口。
- 错误信息中存在 `invalid.ticket`，说明服务端会判断 ticket 失效，但文档没有说明失效规则。

第一版 MCP 不做跨 turn 的 ticket 持久化。原因是当前 Agent Runtime 使用 `copilot -p` 冷启动模式，每个 turn 启动新的 Copilot CLI 子进程；stdio MCP server 也会在该 turn 内由 Copilot CLI 启动。因此，MCP 进程内状态通常只能覆盖一次 turn。

第一版采用 turn-local ticket cache：

1. MCP tool 第一次需要访问 Driivz REST API 时调用 login。
2. 当前 MCP 进程内缓存拿到的 `dmsTicket`。
3. 同一个 turn 内后续 REST API 调用复用该 `dmsTicket`。
4. 如果 REST API 返回 `403` 或明确的 `invalid.ticket`，重新 login 一次，并重试当前 REST 请求一次。
5. turn 结束后 MCP 进程退出，ticket 随进程内存一起释放，不写入数据库或本地文件。

该策略能避免 `review_site_runtime_by_device` 内部的多个 REST API 各自重复 login，同时避免第一版引入额外的 secret/session 存储责任。

后续第一版 MCP tool 设计采用了更保守的认证失败处理：如果后续 REST API 返回 `403` 或明确的 `invalid.ticket`，直接返回 `auth_failed`，不自动重新 login 重试。实现时以 `mcp-tool-design.md` 为准。

## 本地 Investigation 脚本

脚本位置：

```text
mcp-design/driivz/restapi-investigation/probe_device.py
```

本地 `.env` 配置示例：

```text
DRIIVZ_BASE_URL=https://apex-prod.driivz.com:8103/api-gateway
DRIIVZ_USERNAME="<email>"
DRIIVZ_PASSWORD="<password>"
DRIIVZ_TIMEOUT_SECONDS=30
```

注意：

- `.env` 和 `.env.local` 不应提交。
- 密码如果包含特殊字符，应使用普通英文双引号 `"` 包裹。
- 不要使用中文/弯引号 `“` 或 `”`。
- 脚本不会打印 password、cookie 或 ticket。

只验证登录：

```bash
uv run python mcp-design/driivz/restapi-investigation/probe_device.py sebe1100000213 --login-only
```

验证结果：

```text
登录 API 调用成功，已拿到 dmsTicket。未调用其他 API。
```

## 第一个 Device Profile API 验证

验证 API：

```text
POST /v1/chargers/profiles/filter?pageSize=20&pageNumber=0
```

请求 body：

```json
{
  "identityKey": "sebe1100000213"
}
```

认证 header：

```text
dmsTicket: <ticket from login response>
```

验证结果：

```text
status=200
count=1
```

关键返回字段：

```text
charger id: 3035
identityKey/deviceID: sebe1100000213
siteId: 107
status: AVAILABLE
provisionStatus: PROVISIONED
serialNumber: H1610-220217
additionalSerialNumber: 2208545855
chargingSpeed: SLOW
inMaintenance: false
```

返回中已验证 charger -> EVSE -> connector 层级：

```text
charger 3035
  EVSE: DE*UBI*E10043108
    connector id: 169
    connector status: AVAILABLE
    connector type: TYPE_2_MENNEKES
    maxPowerKw: 3.7
```

## MCP 设计含义

- 第一版 CPMS REST client 应支持登录并在 turn 内缓存 `dmsTicket`。
- 认证配置未来应通过项目 `Settings` 注入，不要在业务代码里直接读取环境变量。
- 第一版不持久化 ticket；如果未来发现每个 turn login 一次存在限流或性能问题，再设计跨 turn session cache。
- `POST /v1/chargers/profiles/filter` 可以作为 `resolve_device_context(device_id)` 的第一步。
- 公司 `deviceID` 对应 CPMS `identityKey` / `Charger identity key`。
- 该 API 能直接返回 charger、siteId、EVSE、connector、当前 status、provisionStatus 等上下文。
