# third_two：滚动策划 Agent 对照实现

`third_two` 是与现有 `third` 并列的实验实现，用于对比两种调度方式：

- `third`：一次选择 Workflow Template，再线性执行固定 `steps`。
- `third_two`：策划 LLM 每轮只选择一个原子动作，动作结果以 `Observation` 回流到结构化 `TaskState`，再进行下一轮策划。

现有 `third` 没有被替换。`third_two` 只通过适配层复用已有飞书 Tool、私有飞书配置上下文和共享 LLM 出口。

架构边界见 [docs/architecture.md](docs/architecture.md)，Docker 默认链路见 [docs/docker.md](docs/docker.md)。

## 主循环

```text
用户事件
  -> TaskState
  -> Planner 决定一个 ActionDecision
  -> ActionGuard
  -> 执行一个原子动作
  -> Observation
  -> TaskStateReducer
  -> 下一轮 Planner
```

Planner 每次都会看到最新用户补充、最后一次 Observation 和最新 Artifact。`no_match`、`needs_input`、`conflict` 都会回到 Planner，而不是直接让整个任务失败。

## 原子动作

```text
generate_record_draft
read_table_schema
read_records
prepare_create_record
prepare_update_record
prepare_delete_record
prepare_schema_change
match_record
ask_user
create_record
update_record
delete_record
change_fields
finish
```

`validation` 和 `confirmation` 不是 Planner 可以自由选择的动作。有外部副作用的动作会被 Executor 强制暂停，向用户提供 `approve / modify / cancel` 三种选择；确认绑定实际待执行 payload 的 hash。

## 运行

先安装现有 third 依赖：

```powershell
pip install -r third/requirements.txt
```

配置 LLM 时继续使用现有 `OPENAI_API_KEY`、`THIRD_LLM_ROUTE_MODE`、DeepSeek/Minimax 等 third 出口变量。third_two 只增加：

```text
THIRD_TWO_PLANNER_MODE=llm
THIRD_TWO_PLANNER_MODEL=
THIRD_TWO_MAX_STEPS=20
```

本地直接启动 API：

```powershell
uvicorn third_two.api:app --host 0.0.0.0 --port 8001
```

完整本地应用默认使用 `third_two`：

```powershell
docker compose --profile app up -d --build
```

浏览器打开 `http://localhost:8001/debug` 可以使用对话调试台。页面直接沿用 `third` 的 LLM、飞书和 `THIRD_DEBUG_ENABLED` 配置，不保存另一套配置，也不会显示密钥。调试台包含：

- 左侧最近任务及状态、已走步骤数。
- 中间对话、追问回答、候选选择以及写操作的确认/修改/取消。
- 右侧步骤时间线、完整 `TaskState`、最近 `ActionDecision` / `Observation` 和 Artifact。

当 `THIRD_DEBUG_ENABLED=0` 时，调试页面和任务观测 API 返回 404，`/debug/health` 只报告调试未启用。默认内存 Repository 只保留当前进程内的任务，重启后任务列表会清空。

提交任务：

```http
POST /tasks/invoke
Content-Type: application/json

{
  "content": [{"text": "完成了服务器更新，写到飞书"}],
  "privateMetadata": {
    "feishu": {
      "account": {},
      "table": {}
    }
  }
}
```

任务可能直接完成，也可能返回：

```json
{
  "status": "waiting_user",
  "interaction": {
    "kind": "clarify | choose_candidate | confirm",
    "question": "...",
    "options": []
  }
}
```

恢复任务：

```http
POST /tasks/{taskId}/resume

{
  "interactionId": "interaction_xxx",
  "response": "approve | modify | cancel | answer",
  "content": [{"text": "用户补充或修改的内容"}]
}
```

## 当前边界

- 重点实现用户追问、候选选择、修改、确认、取消与结果回流。
- 保留动作白名单、写操作确认、payload hash 幂等和重复动作检测。
- 暂不实现长期记忆、并行 Action、多个 Task 并发编排和生产数据库持久化。
- 默认 Repository 是进程内实现，接口已独立，后续可以增加 MySQL Repository 而不改变 Planner/Executor 契约。
- Spring Boot 通过 `compat/` 继续消费原 `/workflows/*` 契约，默认 Docker 已接到 `third-two-api`。
- 当前只切换本地 Docker；生产部署配置尚未切换。

## 测试

```powershell
python -m unittest discover third_two\tests
```

测试覆盖：

- 0 候选记录回流后再次策划。
- 用户追问回答后恢复同一 Task。
- 写动作必须先确认且只执行一次。
- 重复动作防循环。
- 私有飞书配置不进入公开 TaskState。
- 空字段 actions 返回 `needs_input`。
