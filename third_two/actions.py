"""third_two 原子动作执行器和现有 third 飞书 Tool 适配层。"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Callable

from third.Tool.tool_ChangeFeishuBitableFields import run_tool_ChangeFeishuBitableFields
from third.Tool.tool_CreateFeishuBitableRecord import run_tool_CreateFeishuBitableRecord
from third.Tool.tool_DeleteFeishuBitableRecord import run_tool_DeleteFeishuBitableRecord
from third.Tool.tool_ReadFeishuBitable import run_tool_ReadFeishuBitable
from third.Tool.tool_ReadFeishuBitableSchema import run_tool_ReadFeishuBitableSchema
from third.Tool.tool_UpdateFeishuBitableRecord import run_tool_UpdateFeishuBitableRecord
from third.Tool.write_support import normalize_write_request, safe_request_for_trace
from third.agents.shared.config import load_config, private_metadata_context
from third.workflow.content import load_json_object
from third.workflow.agent_runner import PARSE_RECORD_DRAFT_PROMPT, run_business_agent
from third.workflow.validation import _normalize_schema_change_request

from .contracts import ActionDecision, Observation, TaskState
from .repository import InMemoryTaskRepository


ToolFunction = Callable[[dict[str, Any]], dict[str, Any]]


class ActionDispatcher:
    """一次只执行一个原子动作；用户交互和确认由 Executor 处理。"""

    def dispatch(
        self,
        decision: ActionDecision,
        state: TaskState,
        repository: InMemoryTaskRepository,
    ) -> Observation:
        name = decision.action_name
        if name == "generate_record_draft":
            return self._generate_record_draft(decision, state)
        if name == "read_table_schema":
            return self._read_table_schema(decision, state, repository)
        if name == "read_records":
            return self._read_records(decision, state, repository)
        if name in {
            "prepare_create_record",
            "prepare_update_record",
            "prepare_delete_record",
            "prepare_schema_change",
        }:
            return self._prepare_operation(decision, state, repository)
        if name == "match_record":
            return self._match_record(decision, state, repository)
        if name in {"create_record", "update_record", "delete_record", "change_fields"}:
            return self._execute_write(decision, state, repository)
        raise ValueError(f"ActionDispatcher 不支持动作：{name}")

    def _generate_record_draft(self, decision: ActionDecision, state: TaskState) -> Observation:
        """复用 third 的无状态草稿转换能力，但不进入旧 Template Executor。"""

        result = run_business_agent(
            {
                "original_input": state.original_input,
                "step": {"prompt_ref": PARSE_RECORD_DRAFT_PROMPT},
            }
        )
        data = result.get("data_json") if isinstance(result.get("data_json"), dict) else {}
        return Observation(
            action_id=decision.action_id,
            action_name=decision.action_name,
            status="success",
            summary=str(data.get("previewText") or "记录草稿已生成。"),
            data=deepcopy(data),
            artifact_key="record_draft",
        )

    def _read_table_schema(
        self,
        decision: ActionDecision,
        state: TaskState,
        repository: InMemoryTaskRepository,
    ) -> Observation:
        result = self._call_tool(
            run_tool_ReadFeishuBitableSchema,
            {"content": [{"text": str(decision.arguments.get("query") or "读取当前飞书字段定义")} ]},
            repository.get_private_metadata(state.task_id),
        )
        return _observation_from_tool(decision, result, "table_schema")

    def _read_records(
        self,
        decision: ActionDecision,
        state: TaskState,
        repository: InMemoryTaskRepository,
    ) -> Observation:
        read_request = decision.arguments.get("read_request") if isinstance(decision.arguments.get("read_request"), dict) else None
        if read_request is None:
            read_request = {key: deepcopy(value) for key, value in decision.arguments.items() if key != "query"}
        if not read_request:
            prepared = repository.get_latest_artifact(state.task_id, "prepared_operation")
            prepared_data = (prepared or {}).get("data") or {}
            request = prepared_data.get("request") if isinstance(prepared_data.get("request"), dict) else {}
            lookup = request.get("lookup") if isinstance(request.get("lookup"), dict) else {}
            read_request = {
                "operation": "get_record" if request.get("record_id") else "search_records",
                "record_id": request.get("record_id"),
                "filter": lookup.get("filter") or {"conjunction": "and", "conditions": []},
                "field_names": [],
                "sort": [],
                "page_size": 50,
                "automatic_fields": True,
            }
        payload = {
            "original_input": state.original_input,
            "read_request": read_request,
        }
        result = self._call_tool(
            run_tool_ReadFeishuBitable,
            _json_content(payload),
            repository.get_private_metadata(state.task_id),
        )
        return _observation_from_tool(decision, result, "candidate_records")

    def _prepare_operation(
        self,
        decision: ActionDecision,
        state: TaskState,
        repository: InMemoryTaskRepository,
    ) -> Observation:
        operation_map = {
            "prepare_create_record": "create_record",
            "prepare_update_record": "update_record",
            "prepare_delete_record": "delete_record",
            "prepare_schema_change": "change_fields",
        }
        operation = operation_map[decision.action_name]
        explicit = _unwrap_request(decision.arguments)
        table_schema = repository.get_latest_artifact(state.task_id, "table_schema")
        schema_data = (table_schema or {}).get("data") or {}
        table_fields = schema_data.get("table_fields") if isinstance(schema_data.get("table_fields"), dict) else {}
        if operation == "change_fields":
            actions = explicit.get("actions") if isinstance(explicit.get("actions"), list) else []
            if not actions:
                data = {"operation": operation, "request": {"actions": []}}
                return Observation(
                    action_id=decision.action_id,
                    action_name=decision.action_name,
                    status="needs_input",
                    summary="字段变更缺少具体 actions，需要向用户追问字段名和修改方式。",
                    data=data,
                    artifact_key="prepared_operation",
                    error_code="schema_actions_missing",
                )
            private_metadata = repository.get_private_metadata(state.task_id)
            with private_metadata_context(private_metadata):
                config = load_config()
                normalized, errors = _normalize_schema_change_request(
                    {"actions": deepcopy(actions)},
                    state.original_input,
                    config,
                    table_fields,
                )
            public_request = _public_request(normalized)
            data = {"operation": operation, "request": public_request, "validation_errors": errors}
            if errors:
                return Observation(
                    action_id=decision.action_id,
                    action_name=decision.action_name,
                    status="needs_input",
                    summary="；".join(errors),
                    data=data,
                    artifact_key="prepared_operation",
                    error_code="schema_change_needs_input",
                )
            return Observation(
                action_id=decision.action_id,
                action_name=decision.action_name,
                status="success",
                summary=f"已准备 {len(actions)} 个字段变更动作。",
                data=data,
                artifact_key="prepared_operation",
            )

        require_fields = operation != "delete_record"
        private_metadata = repository.get_private_metadata(state.task_id)
        with private_metadata_context(private_metadata):
            config = load_config()
            normalized = normalize_write_request(
                operation,
                explicit or None,
                state.original_input,
                config,
                table_fields,
                require_fields=require_fields,
            )
        errors = [str(item) for item in normalized.get("validation_errors") or []]
        public_request = _public_request(safe_request_for_trace(normalized))
        data = {"operation": operation, "request": public_request, "validation_errors": errors}
        if errors:
            return Observation(
                action_id=decision.action_id,
                action_name=decision.action_name,
                status="needs_input",
                summary="；".join(errors),
                data=data,
                artifact_key="prepared_operation",
                error_code="payload_needs_input",
            )
        return Observation(
            action_id=decision.action_id,
            action_name=decision.action_name,
            status="success",
            summary=f"已准备 {operation} 候选 payload。",
            data=data,
            artifact_key="prepared_operation",
        )

    def _match_record(
        self,
        decision: ActionDecision,
        state: TaskState,
        repository: InMemoryTaskRepository,
    ) -> Observation:
        artifact = repository.get_latest_artifact(state.task_id, "candidate_records")
        data = (artifact or {}).get("data") or {}
        records = data.get("records") if isinstance(data.get("records"), list) else []
        if not records:
            return Observation(
                action_id=decision.action_id,
                action_name=decision.action_name,
                status="no_match",
                summary="没有候选记录可供匹配。",
                data={"candidate_count": 0},
                artifact_key="selected_record",
                error_code="candidate_records_empty",
            )
        requested_id = str(decision.arguments.get("record_id") or "").strip()
        selected = None
        if requested_id:
            selected = next((record for record in records if str(record.get("record_id") or "") == requested_id), None)
            if selected is None:
                return Observation(
                    action_id=decision.action_id,
                    action_name=decision.action_name,
                    status="conflict",
                    summary="策划选择的 record_id 不在候选记录中。",
                    data={"requested_record_id": requested_id, "candidates": _candidate_summaries(records)},
                    artifact_key="selected_record",
                    error_code="record_id_not_in_candidates",
                )
        elif len(records) == 1:
            selected = records[0]
        else:
            return Observation(
                action_id=decision.action_id,
                action_name=decision.action_name,
                status="needs_input",
                summary="存在多条候选记录，需要让用户选择。",
                data={"candidate_count": len(records), "candidates": _candidate_summaries(records)},
                artifact_key="selected_record",
                error_code="candidate_choice_required",
            )
        return Observation(
            action_id=decision.action_id,
            action_name=decision.action_name,
            status="success",
            summary=f"已选择 record_id={selected.get('record_id')}。",
            data={"record_id": selected.get("record_id"), "record": selected},
            fact_patch={"selected_record_id": selected.get("record_id")},
            artifact_key="selected_record",
        )

    def _execute_write(
        self,
        decision: ActionDecision,
        state: TaskState,
        repository: InMemoryTaskRepository,
    ) -> Observation:
        prepared = repository.get_latest_artifact(state.task_id, "prepared_operation")
        prepared_data = (prepared or {}).get("data") or {}
        prepared_operation = str(prepared_data.get("operation") or "")
        expected_operation = {
            "create_record": "create_record",
            "update_record": "update_record",
            "delete_record": "delete_record",
            "change_fields": "change_fields",
        }[decision.action_name]
        if prepared_operation != expected_operation:
            return Observation(
                action_id=decision.action_id,
                action_name=decision.action_name,
                status="needs_input",
                summary=f"执行 {decision.action_name} 前缺少对应 prepared_operation。",
                error_code="prepared_operation_missing",
            )
        request = deepcopy(prepared_data.get("request") or {})
        if decision.action_name in {"update_record", "delete_record"} and not request.get("record_id"):
            request["record_id"] = state.facts.get("selected_record_id")
        payload_key = {
            "create_record": "create_request",
            "update_record": "update_request",
            "delete_record": "delete_request",
            "change_fields": "schema_change_request",
        }[decision.action_name]
        payload = {"original_input": state.original_input, payload_key: request}
        tool = {
            "create_record": run_tool_CreateFeishuBitableRecord,
            "update_record": run_tool_UpdateFeishuBitableRecord,
            "delete_record": run_tool_DeleteFeishuBitableRecord,
            "change_fields": run_tool_ChangeFeishuBitableFields,
        }[decision.action_name]
        result = self._call_tool(tool, _json_content(payload), repository.get_private_metadata(state.task_id))
        artifact_key = "schema_change_result" if decision.action_name == "change_fields" else "write_result"
        return _observation_from_tool(decision, result, artifact_key)

    @staticmethod
    def _call_tool(tool: ToolFunction, payload: dict[str, Any], private_metadata: dict[str, Any]) -> dict[str, Any]:
        with private_metadata_context(private_metadata):
            raw = tool(payload)
        content = raw.get("content") if isinstance(raw, dict) else None
        text = ""
        if isinstance(content, list) and content and isinstance(content[0], dict):
            text = str(content[0].get("text") or "")
        parsed = load_json_object(text)
        if not parsed:
            return {"error": "Tool 返回内容不是合法 JSON 对象。", "summary": text or "Tool 没有返回内容。"}
        return parsed


def _observation_from_tool(decision: ActionDecision, result: dict[str, Any], artifact_key: str) -> Observation:
    error = str(result.get("error") or "").strip()
    summary = str(result.get("summary") or error or "动作已执行。")
    if error:
        status, error_code, recoverable = _classify_tool_error(error)
    elif artifact_key == "candidate_records" and int(result.get("record_count") or 0) == 0:
        status, error_code, recoverable = "no_match", "records_not_found", True
    else:
        status, error_code, recoverable = "success", None, True
    return Observation(
        action_id=decision.action_id,
        action_name=decision.action_name,
        status=status,
        summary=summary,
        data=deepcopy(result),
        artifact_key=artifact_key,
        error_code=error_code,
        recoverable=recoverable,
    )


def _classify_tool_error(error: str) -> tuple[str, str, bool]:
    lowered = error.lower()
    if any(word in lowered for word in ("timeout", "timed out", "connection", "502", "503", "504")):
        return "retryable_error", "tool_transport_error", True
    if any(word in error for word in ("没有找到", "不存在", "没有候选")):
        return "no_match", "tool_target_not_found", True
    if any(word in error for word in ("必须提供", "请提供", "字段", "定位条件", "多条记录")):
        return "needs_input", "tool_input_invalid", True
    return "terminal_error", "tool_error", False


def _json_content(payload: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    return {"content": [{"text": json.dumps(payload, ensure_ascii=False, default=str)}]}


def _unwrap_request(arguments: dict[str, Any]) -> dict[str, Any]:
    request = arguments.get("request")
    if isinstance(request, dict):
        return deepcopy(request)
    return deepcopy(arguments)


def _public_request(request: dict[str, Any]) -> dict[str, Any]:
    cleaned = deepcopy(request)
    for key in ("app_token", "app_secret", "tenant_access_token", "authorization", "table_fields"):
        cleaned.pop(key, None)
    return cleaned


def _candidate_summaries(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"record_id": record.get("record_id"), "fields": deepcopy(record.get("fields") or {})}
        for record in records[:10]
    ]
