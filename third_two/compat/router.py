"""把 third_two Task API 映射为 Spring Boot 当前使用的旧 third 契约。"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from fastapi import APIRouter, HTTPException

from third.Tool.field_context import load_table_fields_context
from third.agents.shared.config import load_config, private_metadata_context

from ..contracts import TaskState
from ..executor import RollingTaskExecutor
from ..repository import InMemoryTaskRepository
from .schemas import FeishuTableCheckRequest, InvokeWorkflowRequest, ResumeWorkflowRequest


def create_compat_router(
    repository: InMemoryTaskRepository,
    executor: RollingTaskExecutor,
) -> APIRouter:
    router = APIRouter(tags=["third compatibility"])

    @router.post("/workflows/invoke")
    def invoke_workflow(request: InvokeWorkflowRequest) -> dict[str, Any]:
        text = _content_text(request.content)
        if not text:
            raise HTTPException(status_code=400, detail="content[0].text 不能为空。")
        state = executor.create_task(
            text,
            goal=_goal(text, request.metadata),
            private_metadata=request.private_metadata,
        )
        return _workflow_response(executor.run_until_boundary(state.task_id))

    @router.get("/workflows/{task_id}")
    def get_workflow(task_id: str) -> dict[str, Any]:
        return _workflow_response(_require_task(repository, task_id))

    @router.post("/workflows/{task_id}/resume")
    def resume_workflow(task_id: str, request: ResumeWorkflowRequest) -> dict[str, Any]:
        state = _require_task(repository, task_id)
        interaction = state.pending_interaction or {}
        if interaction.get("interaction_id") != request.confirmation_id:
            raise HTTPException(status_code=400, detail="confirmation_id 不属于当前 task。")
        content = _content_text(request.content)
        kind = str(interaction.get("kind") or "")
        response = "approve" if request.approved and kind == "confirm" else "answer"
        if not request.approved:
            response = "cancel"
        try:
            resumed = executor.resume(task_id, request.confirmation_id, response, content)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _workflow_response(resumed)

    @router.post("/internal/feishu/table-check")
    def check_feishu_table(request: FeishuTableCheckRequest) -> dict[str, Any]:
        with private_metadata_context(request.private_metadata):
            config = load_config()
            table_fields = load_table_fields_context()
        if table_fields.get("error"):
            return {
                "status": "error",
                "message": table_fields.get("error"),
                "tableName": config.feishu_table_name,
                "fieldCount": 0,
            }
        names = table_fields.get("field_names") or []
        return {
            "status": "ok",
            "message": f"已读取字段 {len(names)} 个。",
            "tableName": table_fields.get("table_name") or config.feishu_table_name,
            "fieldCount": len(names),
            "fieldNames": names,
        }

    @router.get("/internal/workflows/{task_id}/artifacts")
    def workflow_artifacts(task_id: str) -> dict[str, Any]:
        _require_task(repository, task_id)
        artifacts = repository.list_artifacts(task_id)
        return {"session_id": task_id, "artifacts": [_artifact_record(item) for item in artifacts]}

    @router.get("/internal/workflows/{task_id}/timeline")
    def workflow_timeline(task_id: str) -> dict[str, Any]:
        state = _require_task(repository, task_id)
        return {
            "session": _snapshot_session(state),
            "plan": _snapshot_decision(state),
            "steps": [{"step": index, **deepcopy(item)} for index, item in enumerate(state.completed_actions, 1)],
            "confirmations": [_snapshot_confirmation(state)] if state.pending_interaction else [],
            "artifacts": [_artifact_record(item) for item in repository.list_artifacts(task_id)],
        }

    @router.get("/internal/workflows/{task_id}/snapshot")
    def workflow_snapshot(task_id: str) -> dict[str, Any]:
        state = _require_task(repository, task_id)
        artifacts = repository.list_artifacts(task_id)
        by_key = {str(item["artifact_key"]): item for item in artifacts}
        public_by_key = {key: _snapshot_artifact(item) for key, item in by_key.items()}
        return {
            "session": _snapshot_session(state),
            "decision": _snapshot_decision(state),
            "confirmation": _snapshot_confirmation(state),
            "outputs": _snapshot_outputs(by_key),
            "artifactsByKey": public_by_key,
            "artifacts": list(public_by_key.values()),
        }

    return router


def _goal(text: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": text,
        "success_criteria": ["业务请求已完成，或已经返回明确的用户交互。"],
        "business_context": deepcopy(metadata),
    }


def _workflow_response(state: TaskState) -> dict[str, Any]:
    return {
        "session_id": state.task_id,
        "status": _legacy_status(state.status),
        "confirmation": _legacy_confirmation(state),
        "content": [{"text": state.final_answer or ""}],
        "error_text": state.error_text,
    }


def _legacy_status(status: str) -> str:
    return "success" if status == "completed" else status


def _legacy_confirmation(state: TaskState) -> dict[str, Any] | None:
    interaction = state.pending_interaction
    if not interaction:
        return None
    return {
        "confirmation_id": interaction.get("interaction_id"),
        "request_text": interaction.get("question"),
        "preview_json": interaction.get("preview") or {},
        "interaction_kind": interaction.get("kind"),
        "options": interaction.get("options") or [],
    }


def _snapshot_session(state: TaskState) -> dict[str, Any]:
    context = state.goal.get("business_context") if isinstance(state.goal, dict) else {}
    return {
        "sessionId": state.task_id,
        "status": _legacy_status(state.status),
        "currentStepId": (state.pending_decision or {}).get("action_id"),
        "originalInput": state.original_input,
        "finalAnswer": state.final_answer,
        "errorText": state.error_text,
        "metadata": deepcopy(context) if isinstance(context, dict) else {},
        "createdAt": state.created_at,
        "updatedAt": state.updated_at,
    }


def _snapshot_decision(state: TaskState) -> dict[str, Any] | None:
    decision = state.pending_decision or state.last_decision
    if not decision:
        return None
    return {
        "planId": None,
        "planVersion": state.version,
        "templateKey": "third_two.rolling",
        "intent": decision.get("action_name"),
        "riskLevel": "write" if decision.get("action_name") in {"create_record", "update_record", "delete_record", "change_fields"} else "read",
        "requiresConfirmation": bool(state.pending_interaction and state.pending_interaction.get("kind") == "confirm"),
        "final": {"source": "final_answer"},
    }


def _snapshot_confirmation(state: TaskState) -> dict[str, Any] | None:
    interaction = state.pending_interaction
    if not interaction:
        return None
    return {
        "confirmationId": interaction.get("interaction_id"),
        "status": "pending",
        "requestText": interaction.get("question"),
        "previewJson": interaction.get("preview") or {},
        "stepId": (interaction.get("pending_decision") or {}).get("action_id"),
        "userResponse": None,
        "interactionKind": interaction.get("kind"),
        "options": interaction.get("options") or [],
        "createdAt": interaction.get("created_at"),
        "decidedAt": None,
        "expiresAt": None,
    }


def _snapshot_outputs(by_key: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "draft": _artifact_data(by_key, "record_draft"),
        "writePayload": _write_payload(by_key),
        "writeResult": _artifact_data(by_key, "write_result"),
        "tableSchema": _artifact_data(by_key, "table_schema"),
        "records": _artifact_data(by_key, "candidate_records"),
        "finalAnswer": _artifact_data(by_key, "final_answer"),
    }


def _write_payload(by_key: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    prepared = _artifact_data(by_key, "prepared_operation")
    if not prepared:
        return None
    request = prepared.get("request") if isinstance(prepared.get("request"), dict) else {}
    return {
        **deepcopy(prepared),
        "preview": {
            "operation": prepared.get("operation"),
            "fields": deepcopy(request.get("fields") or {}),
            "record_id": request.get("record_id"),
            "lookup": deepcopy(request.get("lookup") or {}),
        },
        "tool_input_payload": deepcopy(request),
    }


def _artifact_data(by_key: dict[str, dict[str, Any]], key: str) -> dict[str, Any] | None:
    item = by_key.get(key)
    data = (item or {}).get("data")
    return deepcopy(data) if isinstance(data, dict) else None


def _artifact_record(item: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(item.get("data") or {})
    return {
        "artifact_id": item.get("artifact_id"),
        "session_id": item.get("task_id"),
        "source_step_id": None,
        "artifact_key": item.get("artifact_key"),
        "content_text": json.dumps(data, ensure_ascii=False, default=str),
        "data_json": data,
        "schema_json": {},
        "created_at": item.get("created_at"),
        "expires_at": None,
    }


def _snapshot_artifact(item: dict[str, Any]) -> dict[str, Any]:
    record = _artifact_record(item)
    return {
        "artifactId": record["artifact_id"],
        "sessionId": record["session_id"],
        "sourceStepId": None,
        "artifactKey": record["artifact_key"],
        "contentText": record["content_text"],
        "dataJson": record["data_json"],
        "schemaJson": {},
        "createdAt": record["created_at"],
        "expiresAt": None,
    }


def _require_task(repository: InMemoryTaskRepository, task_id: str) -> TaskState:
    state = repository.get_task(task_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"third_two task 不存在：{task_id}")
    return state


def _content_text(content: list[Any]) -> str:
    if not content:
        return ""
    return str(getattr(content[0], "text", "") or "").strip()
