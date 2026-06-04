# Driivz CPMS 业务背景

本文档记录公司业务语境下的 Driivz CPMS 背景知识，用于设计第一版 Driivz CPMS MCP Server。阅读时应结合本目录下的本地 OpenAPI/Swagger 快照。

## 平台目标

第一版 Driivz MCP Server 的目标，是为 agent 提供一个 Site Context Layer。

它不应该把原始 REST endpoint 直接暴露成通用 tools，而应该暴露面向业务的读取能力，帮助 agent 理解一个充电地点、安装在那里的物理充电桩，以及相关运营状态信号。

第一阶段的重点是上下文检索，不是自治调查，也不是完整企业门户。

## CPMS 对象含义

在 CPMS 领域里，`site` 和 `charger` 是两个不同的物理概念。

`Site` 表示一个地理位置或区域。它可以是地图上的一个点，但 CPMS 模型也支持更大的区域，例如停车场或场站。

`Charger` 表示安装在某个地点的物理充电桩硬件。

在通用 CPMS 模型里，一个 site 可以包含多个 charger。例如，一个停车场 site 里可以有 10 个、20 个，甚至超过 100 个 charger。

## Charger、EVSE、Connector 层级

一个 charger 里可能包含一个或两个 EVSE。

`EVSE ID` 表示 EVSE 层级的标识，但它不是一个绝对稳定不变的业务主键。当前 Driivz 系统里记录的是当前正在使用的 EVSE ID；在实际运营过程中，EVSE ID 可能发生变化。

一个 EVSE 下面可能有一个或两个 connector。Connector 更接近具体插头/接口层级，很多实时状态、交易、启动/停止充电等操作可能会落在 connector 层级。

设计含义：

- MCP 不应把 EVSE ID 当成长期稳定的唯一设备身份。
- 公司 `deviceID` 更适合作为物理设备查询入口，CPMS charger ID / identity key 更适合作为系统内查询锚点。
- 返回模型中应明确区分 charger、EVSE、connector 三个层级。
- 当返回 connector 状态或交易信息时，应保留其所属 EVSE 和 charger 上下文。
- 如果未来需要展示历史，必须注意 EVSE ID 变化可能导致同一物理设备在不同时期有不同 EVSE 标识。

## 公司当前业务模型

在公司当前业务模型里，一个 site 通常对应一个 charger。

运营用户在日常沟通中往往不会严格区分 site、charger 和 device。用户问一个 charger 时，通常也期待得到 site/location 信息；用户问一个 site 时，实际也可能是在问安装在那里的那台物理设备。

MCP 内部应该保留 CPMS 的对象区分，但对外使用体验要适配公司“一 site 一 charger”的业务现实。

设计含义：

- 用 site-oriented tools 表达地理位置上下文。
- 用 charger/device-oriented tools 表达硬件和实时运营状态。
- tools 应支持从 device identity 解析到 charger 和 site 上下文。
- 即使大多数公司 site 只有一个 charger，返回模型里仍建议把 chargers 设计成列表。
- 如果某个 site 有多个 chargers，应在返回结果中明确说明。

## Device ID

公司有自己的 `deviceID` 来标识物理充电设备。当前已知在 CPMS device 数据里，它对应字段是 `Charger identity key`。

在业务对话中，`deviceID` 往往是最主要的查询入口。用户可能提供一个 device ID，并期待 agent 回答：

- 这是什么 charger？
- 它安装在哪里？
- 它属于哪个 site？
- 它当前运营状态如何？
- 这是一个真实安装地点，还是仓库/暂存地点？

例如，CPMS 中的 `Charger identity key` 可能是 `sebe1100000213`。这类值就是公司当前最关心、最常用的 device ID。

设计含义：

- 第一版 tools 应重点考虑 `device_id` 输入路径。
- MCP 应包含一个 resolver 能力，把公司 device ID，也就是 CPMS `Charger identity key`，映射到 CPMS charger 记录和当前 site 上下文。
- 返回模型应分别保留 `device_id`、CPMS charger ID、charger identity key、site ID 和 site location 数据。

## Warehouse Site 行为

计划安装但尚未实际安装的设备，可能已经存在于 CPMS 中。

安装之前，这些设备会关联到一个固定的 warehouse site/location，而不是未来真实安装位置。安装完成后，硬件才会移动或关联到实际 site 位置。

此外，一个已经安装过的 device 也可能从原 site 拆除，再安装到另一个 site。也就是说，device 与 site 的关系不是永久固定的一对一关系，而是有生命周期和迁移历史的关系。

这意味着 CPMS 返回的 site/location 可能代表：

- 真实已安装的充电地点。
- 尚未安装设备的仓库/暂存地点。
- 未知或含义不明确的位置状态。

设计含义：

- MCP 不应把每个当前 site 关联都直接当作真实安装地点。
- Device/site context 的返回结果应包含位置解释，例如 `installed_site`、`warehouse_site` 或 `unknown`。
- 如果设备仍在 warehouse site，agent 应说明这个位置是仓库/暂存分配，不是面向客户的真实安装地点。
- 后续应评估 site-charger history API，看看能否用它识别设备从 warehouse 移动到真实安装 site 的过程。
- MCP 查询当前上下文时，应明确这是“当前关联 site”，不是该 device 的永久 site。
- 后续如果做历史调查，应把 device-site 迁移历史作为独立证据，而不是只看当前 site。

## Program / Project Company

CPMS 的 site 数据里有 `companyId` 字段，并且可以通过 `/v1/companies/{id}` 读取对应详情。

在公司业务语境中，这个对象不是普通意义上的 company，而是项目/计划归属。当前 CPMS 使用 `PROJECT_COMPANY` 类型的 company 来记录这类 project/program 信息。

设计含义：

- MCP 内部可以调用 CPMS company API。
- MCP 对外返回时不要使用 `company` 作为业务字段名。
- 面向 agent 的返回值应使用 `program` 术语，例如 `site_program`。
- `site_program` 的数据来源可以标明为 `GET /v1/companies/{site.companyId}`，但语义上表示 program/project。

## Charger 本地诊断 Log

充电桩本地 log 目前在 CPMS 端不是普通的同步下载 REST 数据。

当前已知流程是：

```text
CPMS 后端发送 get diagnostics / log 请求
  -> 充电桩收到请求
  -> 充电桩把本地 log 打包上传到 FTP server
  -> 运维人员人工从 FTP server 下载压缩包
  -> 解压后分析其中的文件
```

Swagger 中相关 API 是：

```text
POST /v1/chargers/{identityKey}/remote-operations/get-diagnostics
```

该 API 的作用是向真实 charger 发送 `Get Diagnostics` 远程命令。它的返回值只表示命令发送后的状态，例如 `PENDING`、`SUCCESS`、`FAILURE`、`REJECTED`，不直接返回 log 文件内容。

设计含义：

- 本地诊断 log 不是第一版 Site Runtime Review 的普通读取字段。
- `get-diagnostics` 会对真实设备发送远程命令，属于触发型操作，不应混入纯读取 MCP tool。
- 触发诊断 log 上传属于敏感操作。charger 上传诊断包会占用现场网络带宽，可能影响用户充电体验或设备在线稳定性。
- 如果未来需要支持，应设计成单独 tool，例如 `request_charger_diagnostics_log(device_id, from, to)`。
- 该 tool 必须在代码层校验 `from` / `to` 时间范围，默认单次请求最多允许 2 小时；超出范围应拒绝请求，而不是拆分成多次自动触发。
- 该 tool 的返回值应说明请求状态，以及 log 文件需要从 FTP 或未来的文件系统集成中获取。
- 如果未来 MCP 需要直接读取诊断包，需要另行接入 FTP server、文件命名规则、权限控制和大文件处理流程。

## 建议的第一版核心能力

第一版可以考虑把以下能力作为核心 business capability：

```text
resolve_device_context(device_id)
```

它的目的，是用公司 device ID，也就是 CPMS `Charger identity key`，查出 CPMS charger 和 site 上下文。

预期高层返回结构：

```text
device_id
charger
current_site
location_interpretation
relationship_notes
source_rest_operations
```

这个能力可以支撑后续 tools，例如：

```text
get_device_status(device_id)
get_device_location_context(device_id)
get_device_recent_sessions(device_id)
get_site_chargers(site_id)
get_site_current_status(site_id)
```

## 待确认问题

- 哪个 REST filter endpoint 最适合通过 `Charger identity key` 解析 charger？
- MCP 如何稳定识别固定 warehouse site？
- CPMS 暴露的 site-charger relationship history 是否足够区分 warehouse 暂存和实际安装？
- CPMS 中 EVSE ID 变化是否有历史记录？如果有，哪个 API 能查？
- 哪些接口能稳定返回 charger、EVSE、connector 的层级关系？
- 当一个 device 从一个 site 迁移到另一个 site 时，哪个字段/API 能表达迁移时间线？
- 哪些 status/log 字段应被视为 alarm 或 active operational issue？
- Charger 本地诊断 log 上传到 FTP 后，是否有稳定的文件命名规则或索引系统可供未来 MCP 查询？
