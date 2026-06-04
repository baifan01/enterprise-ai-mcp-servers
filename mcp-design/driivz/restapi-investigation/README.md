# Driivz REST API Investigation

这个目录用于编写一次性/探索性的 Python 脚本，验证 Driivz CPMS REST API 的真实返回结构，再反推第一版 MCP tools 的设计。

这里的脚本不是最终 MCP Server 实现。目标是小步验证：

- 哪个 API 能通过公司 `deviceID`，也就是 CPMS `Charger identity key`，找到 charger。
- charger profile/location/status 的真实返回字段是什么。
- site、EVSE、connector 信息出现在返回值的哪个层级。
- 历史、交易、维护、状态类接口是否适合做第一版 Site Context MCP tools。

## 凭证处理

不要把用户名、密码、cookie、ticket 写进代码或文档。

本目录支持本地 `.env.local` 或 `.env` 文件。它们已被 `.gitignore` 忽略，不会进入 git。

初始化方式：

```bash
cp mcp-design/driivz/restapi-investigation/.env.example mcp-design/driivz/restapi-investigation/.env.local
```

如果你已经使用 `.env`，也可以继续使用；脚本会优先读 `.env.local`，如果不存在则读 `.env`。

然后在 `.env.local` 中填写以下三种认证方式之一：

```text
DRIIVZ_COOKIE=...
DRIIVZ_DMS_TICKET=...
DRIIVZ_USERNAME=...
DRIIVZ_PASSWORD=...
```

如果密码中包含 `#`、空格、`$`、引号等特殊字符，建议在 env 文件里用引号包起来：

```text
DRIIVZ_PASSWORD="..."
```

优先级是：

```text
DRIIVZ_COOKIE > DRIIVZ_DMS_TICKET > DRIIVZ_USERNAME/DRIIVZ_PASSWORD
```

脚本不会打印 cookie、password 或 ticket。

## Probe Device

用一个真实 `Charger identity key` 探测候选 API：

```bash
uv run python mcp-design/driivz/restapi-investigation/probe_device.py sebe1100000213
```

默认只打印摘要。需要保存完整响应时：

```bash
uv run python mcp-design/driivz/restapi-investigation/probe_device.py sebe1100000213 --save-responses
```

完整响应会保存到 `responses/`，该目录已被 `.gitignore` 忽略。注意真实响应可能包含业务数据，不要提交。

## 第一批候选 API

当前脚本会先试：

| 目的 | REST API |
| --- | --- |
| 通过 identity key 找 charger profile | `POST /v1/chargers/profiles/filter` |
| 通过 charger id 找 location | `POST /v1/chargers/locations/filter` |
| 通过 charger id 找 status | `POST /v1/chargers/statuses/filter` |
| 通过 charger id 找 status 明细 | `GET /v1/chargers/{id}/status` |
| 通过 identity key 找 charger history | `POST /v1/chargers/identity-key/{identityKey}/history/filter` |
| 通过 identity key 找 EV transactions | `POST /v1/ev-transactions/chargers/{identityKey}/filter` |
