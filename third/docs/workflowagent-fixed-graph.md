# workflowagent 固定执行图

## 固定图

说明：这张图描述的是固定 LangGraph 结构。动态变化的不是节点，而是 `workflowagent` 生成的 `workflow_plan.steps`。

```mermaid
flowchart TD
    U["用户输入：content[0].text<br/>非 Agent"] -->|"生成规划请求"| W["workflowagent<br/>Agent：生成 workflow_plan"]

    W -->|"输出 workflow_plan"| PV["Plan Validator<br/>非 Agent：校验计划可执行性"]
    PV -->|"保存 session / plan"| DB[("Workflow DB<br/>非 Agent：保存会话、计划、步骤和中间结果")]

    DB -->|"读取当前步骤"| EX["Workflow Executor<br/>非 Agent：解释并执行 workflow_plan"]
    EX -->|"准备步骤输入"| CB["Step Context Builder<br/>非 Agent：组装本步骤上下文"]

    CB -->|"按 step.kind 分流"| R{"step.kind<br/>非 Agent：步骤类型路由"}

    R -->|"tool"| TD["Tool Dispatcher<br/>非 Agent：按 tool_name 分发工具"]
    R -->|"agent"| AR["Agent Runner<br/>非 Agent：加载 prompt_ref 并调用业务 Agent"]
    R -->|"validation"| VA["Validation Node<br/>非 Agent：字段、风险和唯一性校验"]

    AR -->|"本步上下文 + prompt"| BA["业务 Agent<br/>Agent：解析、转换或总结"]
    BA -->|"调用模型"| LLM["LLM<br/>非 Agent：模型能力"]

    TD -->|"飞书操作"| FT["Feishu Tools<br/>非 Agent：读字段、查询、新增、更新、删除"]
    TD -->|"本地数据操作"| ST["SQL / Memory Tools<br/>非 Agent：读取数据库或记忆"]

    FT -->|"工具输出"| SAVE["Artifact Writer<br/>非 Agent：保存 output.save_as"]
    ST -->|"工具输出"| SAVE
    LLM -->|"Agent 输出"| SAVE
    VA -->|"校验结果"| SAVE

    SAVE -->|"写入 artifact"| DB
    SAVE -->|"检查计划进度"| NEXT{"是否还有步骤<br/>非 Agent"}
    NEXT -->|"有"| EX
    NEXT -->|"无"| FA["Final Answer<br/>可复用 workflowagent answer 模式"]
    FA -->|"最终输出"| OUT["content[0].text"]
```

## 节点职责

| 节点 | 是否 Agent | 作用 |
|---|---|---|
| 用户输入 | 否 | 接收外部自然语言请求，入口仍然只使用 `content[0].text`。 |
| `workflowagent` | 是 | 只负责生成 `workflow_plan`，说明目标、步骤、输入依赖、输出位置和校验要求。 |
| `Plan Validator` | 否 | 校验计划是否能执行，防止不存在的 Tool、错误依赖、写入前缺少字段读取等问题。 |
| `Workflow DB` | 否 | 保存系统状态，包括 session、plan、step、artifact。Agent 不保存长期状态。 |
| `Workflow Executor` | 否 | 固定执行器，读取当前步骤并决定进入 Tool、Agent 或 Validation。 |
| `Step Context Builder` | 否 | 从 DB 取出本步骤需要的 artifact，只把当前步骤需要的信息交给执行对象。 |
| `step.kind` 路由 | 否 | 根据步骤类型分流，例如 `tool`、`agent`、`validation`。 |
| `Tool Dispatcher` | 否 | 根据 `tool_name` 调用对应 Tool，不做语义判断。 |
| `Agent Runner` | 否 | 加载 `prompt_ref`、拼接上下文、调用业务 Agent。它是运行容器，不是 Agent。 |
| 业务 Agent | 是 | 每次只处理当前步骤，例如解析自然语言、按字段 schema 生成 payload、总结中间结果。 |
| `LLM` | 否 | 模型能力本身，不等于 Agent。 |
| `Validation Node` | 否 | 写入前做硬校验，例如字段是否存在、字段类型是否可写、更新或删除是否唯一定位。 |
| `Feishu Tools` | 否 | 执行飞书多维表格能力，包括读字段、查记录、新增、更新、删除。 |
| `SQL / Memory Tools` | 否 | 读取本地数据库、历史对话或用户记忆。 |
| `Artifact Writer` | 否 | 把每一步输出保存到 `session_artifacts`，供后续步骤按 key 引用。 |
| 是否还有步骤 | 否 | 判断计划是否继续执行，决定回到 Executor 或进入最终回答。 |
| `Final Answer` | 可选 | 可以是确定性格式化节点，也可以复用 `workflowagent` 的 answer 模式。最终只输出 `content[0].text`。 |

## 无状态 Agent 的执行方式

Agent 每一轮都可以是无知的，但 `Workflow DB` 和 `Executor` 不能无状态。执行每一步前，`Step Context Builder` 会把当前步骤需要的内容裁剪出来。

示例：字段转换步骤只会拿到当前任务、飞书字段 schema、记忆查询结果和输出约束。

```json
{
  "step_id": "2",
  "task": "把用户今早记录转换成飞书写入 payload",
  "input_artifacts": {
    "feishu.table_schema": {
      "fields": ["标题", "日期", "内容", "状态"]
    },
    "memory.morning_events": {
      "content": "今天早上完成了项目第三方服务模块工作流设计"
    }
  },
  "output_schema": {
    "artifact_key": "feishu.record_payload",
    "fields": {
      "标题": "string",
      "日期": "date",
      "内容": "string",
      "状态": "string"
    }
  },
  "constraints": {
    "reject_unknown_fields": true,
    "must_match_feishu_schema": true,
    "only_output_json": true
  }
}
```

这样业务 Agent 不需要知道完整历史，也不能越过当前步骤直接写入。写入必须等字段读取、字段转换和校验步骤都完成后，由 Executor 调用写入 Tool。
