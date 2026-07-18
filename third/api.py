"""third Workflow API。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException

try:
    from .debug.router import router as debug_router
    from .runtime.factory import get_workflow_runtime_store
    from .storage.factory import get_workflow_repository
    from .storage.repository import now
    from .agents.shared.config import load_config, private_metadata_context
    from .Tool.field_context import load_table_fields_context
    from .workflow.api_schema import FeishuTableCheckRequest, InvokeWorkflowRequest, ResumeWorkflowRequest, WorkflowResponse
    from .workflow.v1_contract import (
        FeishuTableCheckV1Request,
        FeishuTableCheckV1Response,
        InvokeWorkflowV1Request,
        ResumeWorkflowV1Request,
        WorkflowArtifactV1,
        WorkflowArtifactsV1,
        WorkflowConfirmationV1,
        WorkflowResponseV1,
        WorkflowSnapshotV1,
        WorkflowTimelineV1,
    )
except ImportError:
    from debug.router import router as debug_router
    from runtime.factory import get_workflow_runtime_store
    from storage.factory import get_workflow_repository
    from storage.repository import now
    from agents.shared.config import load_config, private_metadata_context
    from Tool.field_context import load_table_fields_context
    from workflow.api_schema import FeishuTableCheckRequest, InvokeWorkflowRequest, ResumeWorkflowRequest, WorkflowResponse
    from workflow.v1_contract import (
        FeishuTableCheckV1Request,
        FeishuTableCheckV1Response,
        InvokeWorkflowV1Request,
        ResumeWorkflowV1Request,
        WorkflowArtifactV1,
        WorkflowArtifactsV1,
        WorkflowConfirmationV1,
        WorkflowResponseV1,
        WorkflowSnapshotV1,
        WorkflowTimelineV1,
    )


# 这一段创建 FastAPI 应用，SpringBoot 后续通过 HTTP 调用这里。
app = FastAPI(title="third workflow service", version="0.1.0")
LOGGER = logging.getLogger(__name__)


# 这一段挂载本地调试台，是否可访问由 THIRD_DEBUG_ENABLED 控制。
app.include_router(debug_router)


# 这个接口创建 workflow session 并投递异步任务。
@app.post("/workflows/invoke", response_model=WorkflowResponse)
def invoke_workflow(request: InvokeWorkflowRequest) -> WorkflowResponse:
    _log_deprecated("POST /workflows/invoke")
    original_input = _request_text(request.content)
    if not original_input:
        raise HTTPException(status_code=400, detail="content[0].text 不能为空。")
    repository = get_workflow_repository()
    runtime_store = get_workflow_runtime_store()
    session = repository.create_session(original_input, status="queued", metadata_json=request.metadata, private_metadata_json=request.private_metadata)
    runtime_store.enqueue_session(session["session_id"])
    return WorkflowResponse(
        session_id=session["session_id"],
        status="queued",
        content=[{"text": ""}],
    )


# 这个接口查询 workflow 当前状态、确认信息和最终答案。
@app.get("/workflows/{session_id}", response_model=WorkflowResponse)
def get_workflow(session_id: str) -> WorkflowResponse:
    _log_deprecated("GET /workflows/{sessionId}")
    repository = get_workflow_repository()
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"workflow session 不存在：{session_id}")
    confirmation = repository.get_waiting_confirmation(session_id) if session["status"] == "waiting_user" else None
    return WorkflowResponse(
        session_id=session_id,
        status=session["status"],
        confirmation=_safe_confirmation(confirmation),
        content=[{"text": session.get("final_answer") or ""}],
        error_text=session.get("error_text"),
    )


# 这个接口接收用户确认或拒绝，并在确认后重新投递 workflow。
@app.post("/workflows/{session_id}/resume", response_model=WorkflowResponse)
def resume_workflow(session_id: str, request: ResumeWorkflowRequest) -> WorkflowResponse:
    _log_deprecated("POST /workflows/{sessionId}/resume")
    repository = get_workflow_repository()
    runtime_store = get_workflow_runtime_store()
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"workflow session 不存在：{session_id}")
    try:
        confirmation = repository.resolve_confirmation(request.confirmation_id, request.approved, _request_text(request.content))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if confirmation["session_id"] != session_id:
        raise HTTPException(status_code=400, detail="confirmation_id 不属于当前 session。")

    if request.approved:
        repository.update_step(confirmation["step_id"], status="success", finished_at=now(), error_text=None)
        repository.update_session(session_id, status="queued", current_step_id=None, error_text=None)
        runtime_store.enqueue_session(session_id)
        return WorkflowResponse(session_id=session_id, status="queued", content=[{"text": "已确认，workflow 将继续执行。"}])

    repository.update_step(confirmation["step_id"], status="failed", finished_at=now(), error_text="用户拒绝确认。")
    repository.update_session(session_id, status="cancelled", final_answer="已取消本次写入操作。", error_text=None)
    return WorkflowResponse(session_id=session_id, status="cancelled", content=[{"text": "已取消本次写入操作。"}])


# 这个接口提供简单健康检查，方便 Docker 和后端探活。
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# 这个接口使用后端下发的私有飞书配置检查目标表字段。
@app.post("/internal/feishu/table-check")
def internal_feishu_table_check(request: FeishuTableCheckRequest) -> dict[str, Any]:
    _log_deprecated("POST /internal/feishu/table-check")
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
    return {
        "status": "ok",
        "message": f"已读取字段 {len(table_fields.get('field_names') or [])} 个。",
        "tableName": table_fields.get("table_name") or config.feishu_table_name,
        "fieldCount": len(table_fields.get("field_names") or []),
        "fieldNames": table_fields.get("field_names") or [],
    }


@app.post("/v1/workflows/invoke", response_model=WorkflowResponseV1)
def invoke_workflow_v1(request: InvokeWorkflowV1Request) -> WorkflowResponseV1:
    original_input = _request_text(request.content)
    if not original_input:
        raise HTTPException(status_code=400, detail="content[0].text 不能为空。")
    repository = get_workflow_repository()
    runtime_store = get_workflow_runtime_store()
    session = repository.create_session(
        original_input,
        status="queued",
        metadata_json=request.metadata.model_dump(by_alias=True, exclude_none=True),
        private_metadata_json=request.private_metadata.to_internal_dict(),
    )
    runtime_store.enqueue_session(session["session_id"])
    return WorkflowResponseV1.from_internal(
        session_id=session["session_id"],
        status="queued",
        content=[{"text": ""}],
    )


@app.get("/v1/workflows/{session_id}", response_model=WorkflowResponseV1)
def get_workflow_v1(session_id: str) -> WorkflowResponseV1:
    repository = get_workflow_repository()
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"workflow session 不存在：{session_id}")
    return _workflow_response_v1(session)


@app.post("/v1/workflows/{session_id}/resume", response_model=WorkflowResponseV1)
def resume_workflow_v1(session_id: str, request: ResumeWorkflowV1Request) -> WorkflowResponseV1:
    repository = get_workflow_repository()
    runtime_store = get_workflow_runtime_store()
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"workflow session 不存在：{session_id}")
    try:
        confirmation = repository.resolve_confirmation(
            request.confirmation_id,
            request.approved,
            _request_text(request.content),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if confirmation["session_id"] != session_id:
        raise HTTPException(status_code=400, detail="confirmationId 不属于当前 session。")
    if request.approved:
        repository.update_step(confirmation["step_id"], status="success", finished_at=now(), error_text=None)
        repository.update_session(session_id, status="queued", current_step_id=None, error_text=None)
        runtime_store.enqueue_session(session_id)
        return WorkflowResponseV1.from_internal(
            session_id=session_id,
            status="queued",
            content=[{"text": "已确认，workflow 将继续执行。"}],
        )
    repository.update_step(confirmation["step_id"], status="failed", finished_at=now(), error_text="用户拒绝确认。")
    repository.update_session(session_id, status="cancelled", final_answer="已取消本次写入操作。", error_text=None)
    return WorkflowResponseV1.from_internal(
        session_id=session_id,
        status="cancelled",
        content=[{"text": "已取消本次写入操作。"}],
    )


@app.post("/v1/feishu/table-check", response_model=FeishuTableCheckV1Response)
def internal_feishu_table_check_v1(request: FeishuTableCheckV1Request) -> FeishuTableCheckV1Response:
    with private_metadata_context(request.private_metadata.to_internal_dict()):
        config = load_config()
        table_fields = load_table_fields_context()
    names = [str(name) for name in (table_fields.get("field_names") or [])]
    if table_fields.get("error"):
        return FeishuTableCheckV1Response.from_internal(
            status="error",
            message=str(table_fields.get("error") or ""),
            table_name=config.feishu_table_name,
            field_count=0,
        )
    return FeishuTableCheckV1Response.from_internal(
        status="ok",
        message=f"已读取字段 {len(names)} 个。",
        table_name=str(table_fields.get("table_name") or config.feishu_table_name),
        field_count=len(names),
        field_names=names,
    )


@app.get("/v1/workflows/{session_id}/timeline", response_model=WorkflowTimelineV1)
def internal_workflow_timeline_v1(session_id: str) -> WorkflowTimelineV1:
    repository = get_workflow_repository()
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"workflow session 不存在：{session_id}")
    plan = repository.get_plan(session_id)
    steps = repository.list_steps(plan["plan_id"]) if plan else []
    artifacts = repository.list_artifacts(session_id)
    confirmation = repository.get_waiting_confirmation(session_id) if session.get("status") == "waiting_user" else None
    public_confirmation = _confirmation_v1(confirmation)
    return WorkflowTimelineV1.from_internal(
        session=_snapshot_session(session),
        decision=_snapshot_decision(plan),
        steps=steps,
        confirmations=[public_confirmation] if public_confirmation else [],
        artifacts=[_artifact_v1(artifact) for artifact in artifacts],
    )


@app.get("/v1/workflows/{session_id}/artifacts", response_model=WorkflowArtifactsV1)
def internal_workflow_artifacts_v1(session_id: str) -> WorkflowArtifactsV1:
    repository = get_workflow_repository()
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"workflow session 不存在：{session_id}")
    return WorkflowArtifactsV1.from_internal(
        session_id=session_id,
        artifacts=[_artifact_v1(artifact) for artifact in repository.list_artifacts(session_id)],
    )


@app.get("/v1/workflows/{session_id}/snapshot", response_model=WorkflowSnapshotV1)
def internal_workflow_snapshot_v1(session_id: str) -> WorkflowSnapshotV1:
    repository = get_workflow_repository()
    try:
        return build_workflow_snapshot_v1(repository, session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# 这个接口返回 workflow 追踪摘要，供业务后端关联记录追踪。
@app.get("/internal/workflows/{session_id}/timeline")
def internal_workflow_timeline(session_id: str) -> dict[str, Any]:
    _log_deprecated("GET /internal/workflows/{sessionId}/timeline")
    repository = get_workflow_repository()
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"workflow session 不存在：{session_id}")
    plan = repository.get_plan(session_id)
    steps = repository.list_steps(plan["plan_id"]) if plan else []
    confirmations = repository.list_confirmations(session_id)
    artifacts = repository.list_artifacts(session_id)
    return {
        "session": session,
        "plan": plan,
        "steps": steps,
        "confirmations": confirmations,
        "artifacts": [_artifact_preview(artifact) for artifact in artifacts],
    }


# 这个接口返回 workflow artifact 明细，供后端提取草稿或同步结果。
@app.get("/internal/workflows/{session_id}/artifacts")
def internal_workflow_artifacts(session_id: str) -> dict[str, Any]:
    _log_deprecated("GET /internal/workflows/{sessionId}/artifacts")
    repository = get_workflow_repository()
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"workflow session 不存在：{session_id}")
    return {"session_id": session_id, "artifacts": repository.list_artifacts(session_id)}


# 这个接口返回后端接入 third 所需的统一全量快照。
@app.get("/internal/workflows/{session_id}/snapshot")
def internal_workflow_snapshot(session_id: str) -> dict[str, Any]:
    _log_deprecated("GET /internal/workflows/{sessionId}/snapshot")
    repository = get_workflow_repository()
    try:
        return build_workflow_snapshot(repository, session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# 这个函数聚合 session、plan、confirmation 和 artifacts，供 SpringBoot 稳定消费。
def build_workflow_snapshot(repository: Any, session_id: str) -> dict[str, Any]:
    session = repository.get_session(session_id)
    if not session:
        raise KeyError(f"workflow session 不存在：{session_id}")
    plan = repository.get_plan(session_id)
    artifacts = repository.list_artifacts(session_id)
    artifacts_by_key = {str(artifact.get("artifact_key")): _artifact_full(artifact) for artifact in artifacts}
    confirmation = repository.get_waiting_confirmation(session_id) if session.get("status") == "waiting_user" else None
    return {
        "session": _snapshot_session(session),
        "decision": _snapshot_decision(plan),
        "confirmation": _snapshot_confirmation(confirmation),
        "outputs": _snapshot_outputs(artifacts_by_key),
        "artifactsByKey": artifacts_by_key,
        "artifacts": [_artifact_full(artifact) for artifact in artifacts],
    }


def build_workflow_snapshot_v1(repository: Any, session_id: str) -> WorkflowSnapshotV1:
    session = repository.get_session(session_id)
    if not session:
        raise KeyError(f"workflow session 不存在：{session_id}")
    plan = repository.get_plan(session_id)
    artifacts = repository.list_artifacts(session_id)
    public_artifacts = [_artifact_v1(artifact) for artifact in artifacts]
    artifacts_by_key = {artifact.artifact_key: artifact for artifact in public_artifacts}
    legacy_artifacts_by_key = {str(artifact.get("artifact_key")): _artifact_full(artifact) for artifact in artifacts}
    confirmation = repository.get_waiting_confirmation(session_id) if session.get("status") == "waiting_user" else None
    return WorkflowSnapshotV1.from_internal(
        session=_snapshot_session(session),
        decision=_snapshot_decision(plan),
        confirmation=_confirmation_v1(confirmation),
        outputs=_snapshot_outputs(legacy_artifacts_by_key),
        artifacts_by_key=artifacts_by_key,
        artifacts=public_artifacts,
    )


def _workflow_response_v1(session: dict[str, Any]) -> WorkflowResponseV1:
    return WorkflowResponseV1.from_internal(
        session_id=str(session.get("session_id") or ""),
        status=str(session.get("status") or ""),
        content=[{"text": str(session.get("final_answer") or "")}],
        error_text=session.get("error_text"),
    )


def _confirmation_v1(confirmation: dict[str, Any] | None) -> WorkflowConfirmationV1 | None:
    if not confirmation:
        return None
    return WorkflowConfirmationV1.from_internal(
        confirmation_id=str(confirmation.get("confirmation_id") or ""),
        status=str(confirmation.get("status") or "pending"),
        request_text=str(confirmation.get("request_text") or ""),
        preview=confirmation.get("preview_json") or {},
        step_id=confirmation.get("step_id"),
        user_response=confirmation.get("user_response"),
        interaction_kind="confirm",
        options=[],
        created_at=_string_or_none(confirmation.get("created_at")),
        decided_at=_string_or_none(confirmation.get("decided_at")),
        expires_at=_string_or_none(confirmation.get("expires_at")),
    )


# 这个函数读取 API 请求中的 content[0].text。
def _request_text(content: list[Any]) -> str:
    if not content:
        return ""
    first = content[0]
    if hasattr(first, "text"):
        return str(first.text or "").strip()
    if isinstance(first, dict):
        return str(first.get("text") or "").strip()
    return ""


# 这个函数压缩确认记录，避免 API 暴露内部字段。
def _safe_confirmation(confirmation: dict[str, Any] | None) -> dict[str, Any] | None:
    if not confirmation:
        return None
    return {
        "confirmation_id": confirmation.get("confirmation_id"),
        "request_text": confirmation.get("request_text"),
        "preview_json": confirmation.get("preview_json") or {},
    }


# 这个函数转换 snapshot 中的 session 字段。
def _snapshot_session(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "sessionId": session.get("session_id"),
        "status": session.get("status"),
        "currentStepId": session.get("current_step_id"),
        "originalInput": session.get("original_input"),
        "finalAnswer": session.get("final_answer"),
        "errorText": session.get("error_text"),
        "metadata": session.get("metadata_json") or {},
        "createdAt": session.get("created_at"),
        "updatedAt": session.get("updated_at"),
    }


# 这个函数转换 snapshot 中的 workflowagent 决策字段。
def _snapshot_decision(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    plan_json = plan.get("plan_json") or {}
    return {
        "planId": plan.get("plan_id"),
        "planVersion": plan.get("plan_version"),
        "templateKey": plan_json.get("template_key"),
        "intent": plan.get("intent") or plan_json.get("intent"),
        "riskLevel": plan.get("risk_level") or plan_json.get("risk_level"),
        "requiresConfirmation": plan.get("requires_confirmation"),
        "final": plan_json.get("final") or {},
    }


# 这个函数转换 snapshot 中的等待确认字段。
def _snapshot_confirmation(confirmation: dict[str, Any] | None) -> dict[str, Any] | None:
    if not confirmation:
        return None
    return {
        "confirmationId": confirmation.get("confirmation_id"),
        "status": confirmation.get("status"),
        "requestText": confirmation.get("request_text"),
        "previewJson": confirmation.get("preview_json") or {},
        "stepId": confirmation.get("step_id"),
        "userResponse": confirmation.get("user_response"),
        "createdAt": confirmation.get("created_at"),
        "decidedAt": confirmation.get("decided_at"),
        "expiresAt": confirmation.get("expires_at"),
    }


# 这个函数按稳定 key 暴露后端要消费的主要产物。
def _snapshot_outputs(artifacts_by_key: dict[str, dict[str, Any]]) -> dict[str, Any]:
    table_schema = _artifact_data(artifacts_by_key, "feishu.table_schema_after") or _artifact_data(artifacts_by_key, "feishu.table_schema")
    return {
        "draft": _artifact_data(artifacts_by_key, "record.draft"),
        "writePayload": _write_payload_data(artifacts_by_key),
        "writeResult": _artifact_data(artifacts_by_key, "write_result"),
        "tableSchema": table_schema,
        "records": _artifact_data(artifacts_by_key, "feishu.records") or _artifact_data(artifacts_by_key, "feishu.candidate_records"),
        "finalAnswer": _artifact_data(artifacts_by_key, "final.answer"),
    }


def _write_payload_data(artifacts_by_key: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    direct = _artifact_data(artifacts_by_key, "validation.write_payload")
    if direct is not None:
        return direct
    for key, artifact in artifacts_by_key.items():
        if key.startswith("validation."):
            data = artifact.get("dataJson") or {}
            if isinstance(data, dict) and data.get("tool_input_payload"):
                return data
    return None


def _artifact_data(artifacts_by_key: dict[str, dict[str, Any]], key: str) -> dict[str, Any] | None:
    artifact = artifacts_by_key.get(key)
    if not artifact:
        return None
    data = artifact.get("dataJson")
    return data if isinstance(data, dict) else {}


# 这个函数返回完整 artifact，不截断 content_text。
def _artifact_full(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifactId": artifact.get("artifact_id"),
        "sessionId": artifact.get("session_id"),
        "sourceStepId": artifact.get("source_step_id"),
        "artifactKey": artifact.get("artifact_key"),
        "contentText": artifact.get("content_text") or "",
        "dataJson": artifact.get("data_json") or {},
        "schemaJson": artifact.get("schema_json") or {},
        "createdAt": artifact.get("created_at"),
        "expiresAt": artifact.get("expires_at"),
    }


def _artifact_v1(artifact: dict[str, Any]) -> WorkflowArtifactV1:
    return WorkflowArtifactV1.from_internal(
        artifact_id=str(artifact.get("artifact_id") or ""),
        session_id=str(artifact.get("session_id") or ""),
        source_step_id=artifact.get("source_step_id"),
        artifact_key=str(artifact.get("artifact_key") or ""),
        content_text=str(artifact.get("content_text") or ""),
        data=artifact.get("data_json") or {},
        schema_data=artifact.get("schema_json") or {},
        created_at=_string_or_none(artifact.get("created_at")),
        expires_at=_string_or_none(artifact.get("expires_at")),
    )


def _string_or_none(value: Any) -> str | None:
    return None if value is None else str(value)


def _log_deprecated(route: str) -> None:
    LOGGER.warning("deprecated third workflow route used: %s; migrate caller to /v1", route)


# 这个函数压缩 artifact，避免追踪接口默认返回过大的上下文。
def _artifact_preview(artifact: dict[str, Any]) -> dict[str, Any]:
    content_text = str(artifact.get("content_text") or "")
    return {
        "artifact_id": artifact.get("artifact_id"),
        "session_id": artifact.get("session_id"),
        "source_step_id": artifact.get("source_step_id"),
        "artifact_key": artifact.get("artifact_key"),
        "content_preview": content_text[:800],
        "data_json": artifact.get("data_json") or {},
        "schema_json": artifact.get("schema_json") or {},
        "created_at": artifact.get("created_at"),
    }
