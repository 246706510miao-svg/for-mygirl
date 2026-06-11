# runagent 提示词目录

这个目录是业务 Agent 提示词的文件来源。运行时不直接读取这里；先执行 seed 脚本把 YAML 同步到 MySQL `prompt_registry`，workflowagent 和 Agent Runner 都只读数据库。

## YAML 字段

每个 `*.yaml` 必须包含：

- `prompt_key`：提示词主键，也是 workflow_plan.step.prompt_ref。
- `agent_name`：执行该提示词的 Agent 名，例如 `business_agent`。
- `role_name`：提示词角色名。
- `description`：给 workflowagent 看的能力说明。
- `db_address`：数据库地址，格式必须是 `prompt_registry.prompt_key=<prompt_key>`。
- `input_schema_json`：该 Agent 需要的输入结构。
- `output_schema_json`：该 Agent 输出结构。
- `prompt_text`：真正传给 LLM 的提示词正文。
- `version`：提示词版本。
- `enabled`：是否启用。

## 同步命令

先确保数据库表结构已升级到最新 migration：

```bash
alembic upgrade head
```

再同步提示词：

```bash
python -m third.scripts.seed_runagent_prompts
```

脚本按 `prompt_key` 覆盖更新数据库记录。新增或修改提示词后，需要重新执行脚本。若提示 `prompt_registry` 缺少字段，说明 migration 尚未执行成功。

## 新增 Agent

1. 新增一个 YAML 文件，填完整上述字段。
2. 执行 migration 和 seed 脚本。
3. 确保 `workflowagent` 生成的 `agent_name` 和 `prompt_ref` 与数据库记录一致。
4. 确保 Agent Runner 已支持该 `agent_name/prompt_ref` 对应的执行逻辑。
