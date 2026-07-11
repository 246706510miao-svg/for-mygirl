# third_two 模块导航

`third_two` 是滚动策划对照版，不修改现有 `third` Template Executor。

阅读顺序：

1. `README.md`：范围、运行方式和与 `third` 的差异。
2. `docs/architecture.md`：对象流、用户边界以及与 `third` 的逐项对照。
3. `contracts.py`：`TaskState`、`ActionDecision`、`Observation`、`InteractionRequest`。
4. `action_catalog.py`：策划 LLM 可以选择的 14 个原子动作。
5. `Prompt/planner.md`：每轮只选择一个动作的策划提示词。
6. `planner.py`：LLM Planner、保守 Planner 和测试 Scripted Planner。
7. `executor.py`：滚动策划循环、确认恢复、幂等和防循环。
8. `reducer.py`：把本轮 Decision/Observation 归约进 TaskState。
9. `actions.py`：原子动作实现和现有 third 飞书 Tool 适配。
10. `repository.py`：TaskState、Artifact 和 private metadata 存储边界。
11. `policy.py`：后端明确业务操作的最小强制策略。
12. `compat/`：Spring Boot 旧 API、状态和 snapshot 兼容层。
13. `api.py`：任务 API、兼容 API 和调试路由装配。
14. `debug/`：`/debug` 对话调试台、脱敏配置状态、任务列表和步骤时间线。
15. `tests/`：回流、兼容契约、用户交互、确认与边界测试。

核心约束：

- Planner 只能选择 Action Catalog 中的一个动作。
- `no_match`、`needs_input` 和 `conflict` 必须回流，不直接当作任务终态。
- 写操作确认属于执行器边界，Planner 不能绕过。
- TaskState 只保存紧凑公开状态，完整结果放 Artifact，飞书密钥只放 private metadata。
