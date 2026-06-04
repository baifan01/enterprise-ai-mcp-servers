# 代码生成规范

本文用于约束代码生成质量。它只定义长期有效的工程规范、包边界原则、测试要求、日志要求和安全要求；具体实现步骤、阶段拆分、接入顺序和任务范围由对应的详细设计文档或当次任务说明决定。

## 包边界

1. 按高内聚、低耦合规划 package。
2. package 之间优先通过 interface / protocol / service facade 调用。
3. 包内实现细节对包外不可见，不跨包调用内部 helper、私有函数或具体实现类。
4. 上层业务包通过 service / protocol / repository interface 调用下层能力，不直接依赖具体数据库、具体 CLI、具体 HTTP client 或具体平台 SDK。
5. 持久化实现属于 `storage` 或对应基础设施包的职责，业务包不直接管理数据库连接和 migration。
6. `channels` 作为前端入口抽象保留，不把 Telegram、Teams、Web 等平台特殊逻辑写进 agent runtime、orchestrator 或其他核心业务包。
7. 新增跨包依赖前，先确认依赖方向是否符合详细设计文档；禁止为了方便从低层包反向调用高层包。

## 代码组织

1. 代码必须逻辑清晰，避免重复实现相同逻辑。
2. 相似逻辑应抽成 helper、私有方法或小型协作类，但不要为了抽象而抽象。
3. 一个方法不能过长。优先拆成“章节、段落、小节”式结构：

```text
public method
  -> validate input
  -> prepare model/request
  -> call collaborator
  -> transform result
  -> persist/log/return
```

4. 一个类只承担一个明确职责；如果类名需要用 “and” 描述，通常说明边界太大。
5. 避免在 service/facade 方法里堆 CLI 命令拼接、数据库 SQL、JSONL parser 等底层细节。
6. 高层入口方法、route handler、lifespan、CLI command 只表达主流程和边界协调；复杂依赖组装、请求转换、资源清理、外部 IO 细节应拆到命名清楚的 helper、builder、context 或 service 方法中，避免把所有逻辑堆在入口函数里。

## 命名

1. agent runtime 相关模型、接口和类统一使用 `AgentRuntime` 前缀。
2. 不使用裸 `Runtime` 表示 Copilot CLI 这层，避免和 Python runtime、部署 runtime、服务 runtime 混淆。
3. SQLite 实现类使用 `SQLite...Repository` 命名。
4. interface / protocol 命名描述能力，不绑定具体实现。
5. 变量名应表达业务含义，例如 `runtime_session_id`、`conversation_id`、`turn_id`，不要用模糊名称如 `sid`、`data`、`obj`。

## 配置

1. 配置只从 `Settings` 进入系统，不在业务代码里散落读取 env。
2. `Settings` 只保存 root 或明确的外部参数；目录细节交给 `DataLayout` 和 `AgentRuntimeEnvironmentResolver`。
3. 不把 secrets 写入日志、异常消息、测试快照或文档示例。
4. 目录子结构和 env key 必须以设计文档为准，不新增不必要的配置项。

## Async

1. 涉及外部 IO 的接口优先使用 async：

```text
数据库读写
子进程启动和 stdout/stderr 读取
外部 API 调用
channel/frontend 消息发送
```

2. async 方法调用方必须 `await`，不要返回未消费的 coroutine。
3. 不在 async 主路径里使用长时间阻塞调用。
4. 如果必须使用同步库，确保调用范围短且不会阻塞核心服务；必要时以后再隔离到 thread executor。

## 日志

1. 重点调用必须有 INFO 日志：

```text
启动外部 CLI 子进程
CLI 调用完成
创建/读取 agent runtime session
写入 turn metadata
外部 API 调用开始和结束
重要服务启动/停止
```

2. 异常必须有合适等级日志：

```text
WARNING: 可恢复异常、单条 JSONL 解析失败、可降级处理
ERROR: 当前请求失败、数据库写入失败、CLI 调用失败
CRITICAL: 服务无法继续启动或核心依赖不可用
```

3. 日志不输出 API key、token、完整 prompt、完整附件内容或大段模型输出。
4. 日志应带上可追踪但不敏感的字段，例如 `user_id`、`conversation_id`、`turn_id`、`runtime_session_id`。

## 异常处理

1. 所有第三方或外部边界调用必须有异常处理：

```text
启动子进程
读取 stdout/stderr
JSON parse
数据库读写
文件系统创建/读取/写入
外部 HTTP/API 调用
```

2. 不允许异常一路炸到 server 层导致核心服务当机。
3. 不允许吞掉异常让用户以为请求成功。
4. 异常处理要同时做到：

```text
写日志
转换成明确的业务失败结果
保留必要的 error_message
不泄露 secret
```

5. parser 对单条坏 JSONL 应记录 WARNING 并跳过；executor 整体失败才返回 failed result。
6. 数据库写入失败应让当前操作失败，并由 service 返回明确错误，不做静默降级。

## 数据库

1. 是否实现 migration 由详细设计文档决定；不要在没有需求时临时引入迁移框架。
2. 新表初始化可以由 SQLite repository/database helper 在 `initialize()` 中保证。
3. 表结构属于 storage 实现细节，业务层只依赖 repository interface。
4. 数据库模型和业务模型字段映射要清楚，避免用无结构 JSON 替代核心字段。
5. `metadata_json` 只放扩展信息，不放可以成为查询条件的核心字段。

## 测试

1. 核心方法必须有 unit test。
2. 涉及多组件协作的路径要有 integration test。
3. 测试优先覆盖：

```text
核心数据模型校验
service / manager 编排逻辑
repository interface 的读写语义
parser / adapter 的输入输出转换
executor / 外部边界的成功、失败、timeout 和坏数据场景
错误处理和日志关键路径
```

4. 外部 CLI、真实 BYOK、真实平台 API 调用默认不放普通 unit test；用 fake subprocess、fake executor、fake channel 或 fake repository。
5. live test 必须显式标记或放入 integration，并允许在缺配置时 skip。
6. 每次实现完成后运行相关测试；影响面大时运行全量 pytest。

## 文档和注释

1. 核心 Python 模块头部写面向 agent 的高语义密度 docstring。
2. docstring 重点说明：

```text
这个模块负责什么
不负责什么
它依赖哪些 interface
哪些逻辑不能放进这里
未来扩展点在哪里
```

3. 注释只解释不明显的设计原因，不复述代码表面行为。
4. 修改关键边界时，同步更新设计文档或新增实现说明文档。

## 安全

1. 不记录、不打印、不提交 secrets。
2. `.env` 不进入 git。
3. CLI 参数和日志中避免暴露 BYOK token。
4. 对用户输入、文件路径和附件路径保持边界意识：

```text
只能传入用户 workspace、readonly、attachments、shared 中被设计允许的路径。
不要默认使用 --allow-all-paths，除非设计文档明确要求。
```

5. tool 参数和 tool result 的持久化、展示和日志策略必须以设计文档为准；默认不记录详细参数和完整结果。

## 兼容旧代码

1. 兼容策略由详细设计文档或当次任务说明决定，不在本规范中固定接入顺序。
2. 不把新职责塞进旧类或旧模块来“省事”；如果语义已经变化，应创建清晰的新接口或新模块。
3. 迁移旧代码时保持可回滚、可测试，不做无关重构。
4. 删除旧代码必须是明确任务，不在实现新功能时顺手删除。
5. 如果旧接口需要兼容导出，应在代码注释或模块 docstring 中说明迁移原因和目标替代物。

## 不确定性处理

1. 如果设计文档没有覆盖关键选择，先停下来确认。
2. 不凭想象补充重大 assumption，尤其是：

```text
包边界变化
数据库表结构变化
session 创建规则变化
CLI 参数变化
安全权限变化
是否接入旧 Orchestrator
是否删除旧代码
具体实现阶段和接入顺序
```

3. 对小型、局部、可逆的实现细节，可以按现有代码风格做保守选择。
4. 一旦发现实现和设计冲突，先说明冲突，再决定改设计还是改实现。
