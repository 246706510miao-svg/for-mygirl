"""third Workflow API。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

try:
    from .debug.router import router as debug_router
    from .runtime.factory import get_workflow_runtime_store
    from .storage.factory import get_workflow_repository
    from .storage.repository import now
    from .workflow.api_schema import InvokeWorkflowRequest, ResumeWorkflowRequest, WorkflowResponse
except ImportError:
    from debug.router import router as debug_router
    from runtime.factory import get_workflow_runtime_store
    from storage.factory import get_workflow_repository
    from storage.repository import now
    from workflow.api_schema import InvokeWorkflowRequest, ResumeWorkflowRequest, WorkflowResponse


# 这一段创建 FastAPI 应用，SpringBoot 后续通过 HTTP 调用这里。
app = FastAPI(title="third workflow service", version="0.1.0")


# 这一段挂载本地调试台，是否可访问由 THIRD_DEBUG_ENABLED 控制。
app.include_router(debug_router)


# 这个接口创建 workflow session 并投递异步任务。
@app.post("/workflows/invoke", response_model=WorkflowResponse)
def invoke_workflow(request: InvokeWorkflowRequest) -> WorkflowResponse:
    original_input = _request_text(request.content)
    if not original_input:
        raise HTTPException(status_code=400, detail="content[0].text 不能为空。")
    repository = get_workflow_repository()
    runtime_store = get_workflow_runtime_store()
    session = repository.create_session(original_input, status="queued", metadata_json=request.metadata)
    runtime_store.enqueue_session(session["session_id"])
    return WorkflowResponse(
        session_id=session["session_id"],
        status="queued",
        content=[{"text": ""}],
    )


# 这个接口查询 workflow 当前状态、确认信息和最终答案。
@app.get("/workflows/{session_id}", response_model=WorkflowResponse)
def get_workflow(session_id: str) -> WorkflowResponse:
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


# 这个接口返回 workflow 追踪摘要，供业务后端关联记录追踪。
@app.get("/internal/workflows/{session_id}/timeline")
def internal_workflow_timeline(session_id: str) -> dict[str, Any]:
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
    repository = get_workflow_repository()
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"workflow session 不存在：{session_id}")
    return {"session_id": session_id, "artifacts": repository.list_artifacts(session_id)}


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
