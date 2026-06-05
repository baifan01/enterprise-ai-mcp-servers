# Driivz CPMS MCP Tool 设计

本文档记录第一版 Driivz CPMS MCP Server 的 tool 设计。当前重点是通过公司 `deviceID` 获取 site/runtime 相关上下文。

## 设计边界

MCP Server 只做业务语义化的数据获取层。

MCP 负责：

- 调用 Driivz CPMS REST API。
- 按单个 `deviceID` 聚合 profile、site、site program、location、status、recent sessions。
- 标明每段数据来自哪个 REST API。
- 保留 CPMS 原始字段，避免过度解释。

MCP 不负责：

- 判断设备正常或异常。
- 生成故障原因。
- 定义运营规则。
- 解释 `updateStatus`、`chargerStatus`、`errorCode` 等字段的业务含义。
- 输出维修建议。

具体运营分析逻辑放在 Skill 中定义。

## 第一版 MCP Tool

```text
review_site_runtime_by_device
```

## MCP Server 实现方式

第一版 MCP Server 使用 stdio 进程级实现，不做 HTTP 常驻服务。

当前 Agent Runtime 使用 `copilot -p` 冷启动模式，每个 Copilot turn 会启动一个新的 Copilot CLI 子进程；当 Copilot CLI 需要调用 Driivz MCP tool 时，再按 MCP 配置启动 stdio MCP server 子进程。

设计含义：

- MCP Server 进程生命周期通常只覆盖一次 Copilot turn。
- `dmsTicket` 只做进程内缓存，不跨 turn 持久化。
- 第一版不引入数据库、Redis 或长期 session store 保存 CPMS ticket。
- MCP Server 代码在主平台 repo 外的 `ubi-personal-assistant-mcp-servers` 目录下开发。该目录作为多个 MCP server 的软件部署区，和 `ubi-personal-assistant-data` runtime data 目录分开。
- Driivz CPMS MCP Server 第一版代码目录为 `ubi-personal-assistant-mcp-servers/servers/driivz-cpms`。代码目录内可放 ignored `.env` 文件，用于本地或部署时读取 Driivz 凭证。

建议目录边界：

```text
ubi-personal-assistant/
  主平台代码与设计文档

ubi-personal-assistant-data/
  runtime data、users、sessions、shared/mcp/mcp-config.json

ubi-personal-assistant-mcp-servers/
  mcp-design/
    driivz/
      ...

  servers/
    driivz-cpms/
      pyproject.toml
      uv.lock
      .venv/
      .env
      mcp_driivz/
        server.py
        settings.py
        client.py
        tools.py
        models.py
        errors.py

    datawarehouse/
      ...

    salesforce/
      ...
```

每个 MCP server 使用独立 uv project。第一版先实现 `servers/driivz-cpms`，`datawarehouse` 和 `salesforce` 仅保留目录占位。

实际 Driivz server 目录：

```text
servers/driivz-cpms/
    pyproject.toml
    uv.lock
    .venv/
    .env
    mcp_driivz/
      server.py
      settings.py
      client.py
      tools.py
```

## MCP 注册配置

当前 Copilot CLI 通过 shared MCP 配置加载 MCP server：

```text
<agent_runtime_data_root>/shared/mcp/mcp-config.json
```

对应启动参数：

```text
--additional-mcp-config @<shared_root>/mcp/mcp-config.json
```

第一版注册示例：

```json
{
  "mcpServers": {
    "driivz-cpms": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/ubi-personal-assistant-mcp-servers/servers/driivz-cpms",
        "run",
        "python",
        "-m",
        "mcp_driivz.server"
      ],
      "env": {
        "DRIIVZ_ENV_FILE": "/absolute/path/to/ubi-personal-assistant-mcp-servers/servers/driivz-cpms/.env"
      }
    }
  }
}
```

说明：

- `mcp-config.json` 中不直接写 Driivz username/password。
- Driivz 凭证由 MCP Server 读取 `DRIIVZ_ENV_FILE` 指向的 `.env` 文件。
- `.env` 文件必须被 git ignore。
- 实际注册时应在 `args` 中加入 `uv --directory /absolute/path/to/ubi-personal-assistant-mcp-servers/servers/driivz-cpms`，确保 MCP Server 使用自己的 uv project 和 `.venv`，而不是 Copilot CLI 当前 workspace。

## 凭证配置

MCP Server 从环境变量或 `.env` 文件读取 Driivz REST 配置。

建议变量：

```text
DRIIVZ_BASE_URL=https://apex-prod.driivz.com:8103/api-gateway
DRIIVZ_USERNAME=<operator email>
DRIIVZ_PASSWORD=<operator password>
DRIIVZ_TIMEOUT_SECONDS=30
```

实现要求：

- 不在代码中硬编码用户名、密码或 ticket。
- 不在日志、错误返回、MCP result 中输出 password 或 `dmsTicket`。
- 生产代码中配置读取应集中在 MCP Server 自己的 Settings/Config 类中，不在业务调用函数里直接散落读取环境变量。

### 用途

通过一个公司 `deviceID` 查询对应 charger/site 的运行上下文。

公司 `deviceID` 对应 CPMS 中的 `Charger identity key` / `identityKey`。

### 输入参数

```json
{
  "device_id": "suby1100008277",
  "include_recent_sessions": true
}
```

字段说明：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `device_id` | `str` | 是 | 无 | 公司 device ID，对应 CPMS `identityKey`。 |
| `include_recent_sessions` | `bool` | 否 | `true` | 是否查询最近 7 天 EV transaction/session。 |

### 输入约束

- `device_id` 不能为空字符串。
- `include_recent_sessions=true` 时，recent sessions 固定查询最近 7 天。
- recent sessions 的 `fromDate` / `toDate` 使用 UTC 时间，格式化为 ISO 8601，例如 `2026-06-03T08:00:00Z`。
- 面向德国运营用户展示时，时区转换由上层 Skill 或 agent response 负责，MCP 返回值保留 CPMS/UTC 原始时间。
- CPMS EV transaction API 单次时间范围最多 7 天，第一版不做自动分段查询。
- 第一版不支持一次 MCP tool 调用查询多个 device。原因是 CPMS profile API 当前使用单值 `identityKey` 查询，并且单 device 入口更容易控制 CPMS REST 调用压力。

## 返回值结构

MCP 返回 JSON。返回值只做语义聚合，不做正常/异常判断。

```json
{
  "device_id": "suby1100008277",
  "resolved": true,
  "profile": {
    "source_api": "POST /v1/chargers/profiles/filter",
    "request_id": "evLXSganpo",
    "count": 1,
    "data": [{}]
  },
  "location": {
    "source_api": "POST /v1/chargers/locations/filter",
    "request_id": "g5MPSa0m50",
    "count": 1,
    "data": [{}]
  },
  "site": {
    "source_api": "GET /v1/sites/{siteId}",
    "request_id": "D6pDHtoYia",
    "count": 1,
    "data": {}
  },
  "site_program": {
    "source_api": "GET /v1/companies/{site.companyId}",
    "request_id": "FxFOr0cdx0",
    "count": 1,
    "data": {}
  },
  "status": {
    "source_api": "POST /v1/chargers/statuses/filter",
    "request_id": "XzqrrVVSX0",
    "count": 1,
    "data": [{}]
  },
  "recent_sessions": {
    "source_api": "POST /v1/ev-transactions/chargers/{identityKey}/filter",
    "request_id": "r3quNgkNb9",
    "window_days": 7,
    "count": 3,
    "data": []
  }
}
```

### 顶层字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `device_id` | `str` | 输入的公司 device ID。 |
| `resolved` | `bool` | 是否成功通过 profile API 找到 charger。 |
| `profile` | `object` | Charger profile REST segment；内部 `data` 保留 CPMS filter API 的 list 形状。 |
| `site` | `object \| null` | Site REST segment；如果没有 site id，则为 `null`。 |
| `site_program` | `object \| null` | Site 所属 program/project segment；数据来自 CPMS company API，但 MCP 对外使用 program 术语。 |
| `location` | `object \| null` | Charger location REST segment；如果没有 charger id，则为 `null`。 |
| `status` | `object \| null` | Charger status REST segment；如果没有 charger id，则为 `null`。 |
| `recent_sessions` | `object \| null` | 最近 7 天 EV transaction/session segment；如果 `include_recent_sessions=false`，则为 `null`。 |

第一版只返回 CPMS 当前 REST API 返回的 site/location 关联，不额外推断历史安装地点、warehouse 状态或迁移过程。历史位置关系由 CPMS 数据本身负责，MCP 不在 `review_site_runtime_by_device` 中进行二次解释。

### REST Segment 字段

每个 REST segment 使用统一结构：

```json
{
  "source_api": "POST /v1/chargers/profiles/filter",
  "request_id": "evLXSganpo",
  "count": 1,
  "data": [{}]
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `source_api` | `str` | 数据来源 REST API。 |
| `request_id` | `str \| null` | CPMS response 中的 `requestId`。 |
| `count` | `int \| null` | CPMS response 中的 `count`。 |
| `data` | `object \| list \| null` | CPMS response 中的 `data`，尽量保留原始字段。Filter API 的 `data` 保留为 list，即使通常只有一条。GET detail API 如果 CPMS 返回 object，则保留 object。 |

### 错误返回结构草案

MCP tool 不应因为某个非关键下游 REST segment 失败就丢弃所有已获取数据。建议返回顶层 `errors` 列表，并在失败 segment 中保留错误摘要。

顶层结构：

```json
{
  "device_id": "suby1100008277",
  "resolved": false,
  "profile": {
    "source_api": "POST /v1/chargers/profiles/filter",
    "request_id": null,
    "count": 0,
    "data": null,
    "error": {
      "type": "not_found",
      "message": "No charger profile found for device_id.",
      "retryable": false
    }
  },
  "location": null,
  "site": null,
  "site_program": null,
  "status": null,
  "recent_sessions": null,
  "errors": [
    {
      "segment": "profile",
      "source_api": "POST /v1/chargers/profiles/filter",
      "type": "not_found",
      "message": "No charger profile found for device_id.",
      "retryable": false
    }
  ]
}
```

错误对象字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `segment` | `str` | 出错的数据段，例如 `profile`、`site`、`status`。 |
| `source_api` | `str \| null` | 出错 REST API。 |
| `type` | `str` | 错误类型，例如 `not_found`、`ambiguous_result`、`timeout`、`auth_failed`、`rest_error`、`invalid_response`。 |
| `message` | `str` | 可给 agent 阅读的安全错误摘要，不包含 secret。 |
| `http_status` | `int \| null` | REST HTTP 状态码；无 HTTP response 时为 `null`。 |
| `request_id` | `str \| null` | CPMS response 中的 `requestId`，如果有。 |
| `retryable` | `bool` | 是否理论上可重试。 |

错误处理建议：

- `profile` 查不到时：`resolved=false`，其他依赖 profile 的 segment 为 `null`。
- `profile` 返回多条时：`resolved=false`，错误类型为 `ambiguous_result`。这表示输入的 `device_id` 在 CPMS 中解析到了多个候选 charger，结果不唯一；MCP 不应自动选择第一条，避免把后续 site/status/session 绑定到错误设备上。
- `site` 失败时：仍返回 profile、location、status、recent_sessions；`site_program=null`。
- `site_program` 失败时：只影响 `site_program` segment。
- `location`、`status`、`recent_sessions` 失败时：对应 segment 带 error，其他 segment 正常返回。
- 认证失败时：返回 `auth_failed`，不要返回 ticket 或 password。

## 底层 REST 调用顺序

对输入的 `device_id` 执行以下流程。

### 0. REST Authentication

第一版 MCP 使用 turn-local ticket cache。

```text
POST /v1/authentication/operator/login
```

用途：

- 获取后续 REST API 使用的 `dmsTicket`。
- 同一个 MCP 进程 / Copilot turn 内复用该 ticket。
- 如果后续 REST API 返回 `403` 或明确的 `invalid.ticket`，直接返回认证错误，不重新 login 重试。

实现约束：

- 不为每个 REST API 单独 login。
- 不把 `dmsTicket` 写入数据库、本地文件或日志。
- 不在第一版做跨 turn ticket cache。
- Swagger 未说明 ticket TTL；第一版每个 MCP 进程第一次访问 REST 时 login 一次，并在该进程内复用 ticket。
- 如果拿到的 ticket 后续返回 `invalid.ticket`，直接返回认证错误，不做重新 login 重试。该情况更可能代表凭证、权限或环境配置问题，不应靠重试掩盖。

### 1. Charger Profile

```text
POST /v1/chargers/profiles/filter?pageSize=20&pageNumber=0
```

Request body：

```json
{
  "identityKey": "<device_id>"
}
```

用途：

- 通过公司 `deviceID` / CPMS `identityKey` 找 charger。
- 获取 charger id、site id、基础状态、EVSE、connector 等信息。

关键字段示例：

```text
id
identityKey
siteId
status
provisionStatus
serialNumber
additionalSerialNumber
inMaintenance
disabled
managed
evses
evses[].connectors
```

### 2. Site Detail

仅当 profile 返回 `siteId` 时调用。

```text
GET /v1/sites/{siteId}
```

用途：

- 获取 site 业务对象信息。
- 获取 site `companyId`，该字段在当前业务中代表 program/project 归属。

关键字段示例：

```text
id
name
displayName
legacyId
externalId
companyId
propertyId
chargerIds
provisioningStatus
locationType
chargerHostId
sourceType
inMaintenance
comments
address
```

### 3. Site Program

仅当 site detail 返回 `companyId` 时调用。

```text
GET /v1/companies/{site.companyId}
```

用途：

- 读取 site 对应的 program/project 信息。
- 注意：底层 CPMS 使用 company API 和 `PROJECT_COMPANY` 类型保存该信息，但 MCP 对外字段命名必须使用 `site_program`，不要使用 `company`。

关键字段示例：

```text
id
name
businessId
type
address
```

### 4. Charger Location

仅当 profile 返回 charger id 时调用。

```text
POST /v1/chargers/locations/filter?pageSize=20&pageNumber=0
```

Request body：

```json
{
  "ids": [214627]
}
```

用途：

- 获取 charger 当前地理位置和地址。

关键字段示例：

```text
id
latitude
longitude
address.address1
address.city
address.zipCode
address.countryCode
address.zoneId
address.municipality
groupIds
```

### 5. Charger Status

仅当 profile 返回 charger id 时调用。

```text
POST /v1/chargers/statuses/filter?pageSize=20&pageNumber=0
```

Request body：

```json
{
  "ids": [214627]
}
```

用途：

- 获取 charger 当前状态详情。

关键字段示例：

```text
id
chargerStatus
errorCode
provisionStatus
firmwareVersion
installationDate
provisioningDate
updateStatus
siteId
evses
evses[].connectors
```

### 6. Recent EV Sessions

仅当 `include_recent_sessions=true` 时调用。

```text
POST /v1/ev-transactions/chargers/{identityKey}/filter?pageSize=20&pageNumber=0&sortBy=id:desc
```

Request body：

```json
{
  "fromDate": "<now - 7 days>",
  "toDate": "<now>",
  "transactionBillingStatus": "FINAL_COST"
}
```

用途：

- 获取最近 7 天 EV transaction/session。

关键字段示例：

```text
id
chargerId
connectorId
evseId
transactionStatus
transactionBillingStatus
startedOn
stoppedOn
stopReason
chargePower
totalEnergy
cost
connectorStatus
connectorType
```

## REST 并发策略

该 tool 内部会调用多个 REST API。第一版可以使用 Python async I/O 提高响应速度，但需要保留 REST API 之间的依赖关系。

推荐流程：

```text
login once
  -> profile by identityKey
      -> site detail, charger location, charger status, recent sessions 可并发
          -> site program 依赖 site detail 返回的 companyId
```

说明：

- `profile` 必须先调用，因为后续 API 需要 `charger id`、`siteId`、`identityKey`。
- `site detail`、`charger location`、`charger status`、`recent sessions` 在拿到 profile 后可以并发调用。
- `site_program` 需要等 `site detail` 返回 `companyId` 后再调用。
- 第一版 tool 只接受一个 `device_id`，因此不做跨 device 并发。
- 单个 device 内部并发也应有固定上限。当前流程最多并发 4 个 REST 请求：site detail、charger location、charger status、recent sessions。
- 实现代码应在并发处保留注释，提醒未来维护 agent 不要无脑增加并发 REST 调用；新增并发必须考虑 CPMS 压力、依赖关系和 timeout 行为。

## Timeout / Retry 策略

第一版建议：

- 每个 REST 请求使用固定 timeout，默认可从 `DRIIVZ_TIMEOUT_SECONDS` 配置，当前 investigation 默认是 30 秒。
- 普通 REST 调用最多尝试 3 次。
- 只对网络瞬断、连接错误、read timeout、部分 5xx 等可能临时恢复的错误重试。
- `4xx` 业务错误不重试。
- `invalid.ticket` 不重试，直接返回 `auth_failed`。
- 每次重试不得重新 login，除非当前请求本身是 login。
- retry 之间使用短暂 backoff，避免瞬时连续打满 CPMS。

## 第一版测试策略草案

第一版测试以离线单元测试为主，不把 live CPMS 调用作为默认测试路径。

建议测试层级：

- Settings 测试：验证 `DRIIVZ_ENV_FILE`、环境变量读取、必填凭证缺失、timeout 默认值和非法值。
- REST client 测试：使用 mocked HTTP response 验证登录、`dmsTicket` header 注入、安全错误摘要、timeout/retry、`4xx` 不重试、`invalid.ticket` 返回 `auth_failed`。
- Tool 聚合测试：mock Driivz client，验证成功路径、`include_recent_sessions=false`、profile not found、profile 多条 `ambiguous_result`、site/location/status/recent_sessions 局部失败时仍返回其他 segment。
- 返回结构测试：确认 filter API segment 的 `data` 保留为 list；GET detail API 按 CPMS 返回保留 object；错误对象不包含 password、ticket、cookie。
- 时间窗口测试：确认 recent sessions 使用 UTC `fromDate` / `toDate`，窗口固定 7 天，不自动分段。

Live CPMS 测试只作为显式 opt-in：

- 默认 CI 和本地 `pytest` 不调用真实 Driivz。
- 如果需要 live smoke test，应使用单独标记或环境变量启用，例如 `DRIIVZ_RUN_LIVE_TESTS=1`。
- live test 只验证登录和一个只读 profile 查询，不触发 remote operation。
- live test 输出必须脱敏，不打印 password、`dmsTicket`、cookie 或完整业务响应。

## 未纳入第一版 Tool 的内容

### Charger data change history

```text
POST /v1/chargers/identity-key/{identityKey}/history/filter
```

这是 charger 数据修改历史，记录字段变更、修改人、修改时间，不是 runtime 主数据。

暂不纳入第一版 `review_site_runtime_by_device`。

### Site assignment history

```text
POST /v1/sites/history/charger/filter
```

这是 charger 与 site 的绑定历史，可用于未来分析 warehouse site、site 迁移等场景。

暂不纳入第一版。

### 48 小时全局掉线列表

```text
POST /v1/chargers/connection-log/filter
```

该 API 可查单个 charger 的 WebSocket open/closed 连接日志。

实验中不传 `chargerId`、只按时间范围全局查询会超时。因此暂不纳入第一版。

未来需要另行寻找轻量数据源或专门接口。

### Charger local diagnostics log

```text
POST /v1/chargers/{identityKey}/remote-operations/get-diagnostics
```

该 API 用于向 charger 发送 `Get Diagnostics` 远程命令。当前业务流程是：CPMS 后端发送请求，charger 收到后把本地 log 打包上传到 FTP server，运维人员再人工从 FTP 下载压缩包并解压分析。

这不是一个普通读取接口，也不会直接返回 log 文件内容。Swagger 中该 API 返回的是命令状态，例如：

```text
SUCCESS
FAILURE
PENDING
REJECTED
```

暂不纳入第一版 `review_site_runtime_by_device`。

原因：

- 它会对真实 charger 发起远程命令，不属于纯读取 context retrieval。
- 返回值不是诊断文件内容，而是命令状态。
- 文件实际落在 FTP server，需要额外的 FTP/文件索引集成才能形成完整闭环。
- charger 上传诊断包会占用现场网络带宽，可能影响用户充电体验或设备在线稳定性。
- 该操作可能影响现场设备或运维流程，未来应作为单独的高意图 tool 设计。

未来可单独考虑：

```text
request_charger_diagnostics_log(device_id, from, to)
```

该 tool 应明确返回“请求已发送/被拒绝/等待中”等状态，并说明诊断包需要从 FTP 或后续文件集成中获取。

输入约束：

- `from` 和 `to` 必须是明确的 ISO 8601 时间。
- `to` 必须晚于 `from`。
- 单次请求时间窗口默认最多 2 小时。
- 超过最大时间窗口时，tool 应拒绝请求并返回安全错误，不应自动拆成多次请求。
- 该限制必须在 MCP Server 代码中实现，不能只依赖 agent prompt 或 Skill 说明。

### Charger detailed logs

```text
POST /v1/chargers/detailed-log/chargers/{identityKey}
POST /v1/chargers/detailed-log/filter
```

Swagger 中这两个 API 返回的是 CPMS charger detailed log 记录，字段包括 `eventDate`、`eventSource`、`eventType`、`eventLogLevel`、`eventActionResult`、`relevantData`、`extraData`、`transactionId` 等。

它们看起来更像 CPMS 事件/操作日志，不是 charger 本地诊断文件。生产环境试验中，即使限制到单个 charger、短时间范围和 `pageSize=1`，仍出现读取超时。因此暂不纳入第一版主 review tool。
