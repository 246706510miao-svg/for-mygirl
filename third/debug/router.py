"""workflow 调试 API 和页面路由。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

try:
    from ..agents.shared.config import ThirdServiceConfig, load_config
    from ..runtime.factory import get_workflow_runtime_store
    from ..storage.factory import get_workflow_repository
    from ..storage.repository import WorkflowRepository, now
    from .page import debug_page_html
except ImportError:
    from agents.shared.config import ThirdServiceConfig, load_config
    from runtime.factory import get_workflow_runtime_store
    from storage.factory import get_workflow_repository
    from storage.repository import WorkflowRepository, now
    from debug.page import debug_page_html


# 这一段创建调试路由，所有接口都挂在 /debug 下。
router = APIRouter(prefix="/debug", tags=["debug"])


# 这个接口返回内置调试页面，浏览器直接访问 /debug 即可。
@router.get("", response_class=HTMLResponse, include_in_schema=False)
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def debug_page() -> HTMLResponse:
    _ensure_debug_enabled()
    return HTMLResponse(debug_page_html())


# 这个接口检查运行模式和关键配置，不输出任何密钥明文。
@router.get("/health")
def debug_health() -> dict[str, Any]:
    config = load_config()
    if not config.debug_enabled:
        return {"debug_enabled": False, "mode": {}, "checks": []}
    checks, storage_mode, runtime_mode = _build_health_checks(config)
    return {
        "debug_enabled": True,
        "mode": {
            "feishu": "real" if config.feishu_use_real else "mock",
            "workflowagent": "llm" if config.workflowagent_use_llm else "rule",
            "model": config.workflowagent_model,
            "storage": storage_mode,
            "runtime": runtime_mode,
        },
        "checks": checks,
    }


# 这个接口返回最近 workflow session 列表。
@router.get("/workflows")
def debug_workflows(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    _ensure_debug_enabled()
    config = load_config()
    repository = get_workflow_repository()
    try:
        sessions = [_session_summary(row) for row in repository.list_sessions(limit)]
    except Exception as exc:
        return {"sessions": [], "error_text": _safe_error(exc, config)}
    return {"sessions": sessions, "error_text": ""}


# 这个接口返回最近一个 workflow session。
@router.get("/workflows/latest")
def debug_latest_workflow() -> dict[str, Any]:
    _ensure_debug_enabled()
    config = load_config()
    repository = get_workflow_repository()
    try:
        sessions = repository.list_sessions(1)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=_safe_error(exc, config)) from exc
    if not sessions:
        raise HTTPException(status_code=404, detail="暂无 workflow session。")
    return {"session": _session_summary(sessions[0])}


# 这个接口把 session 的计划、步骤、确认和产物整理成时间线。
@router.get("/workflows/{session_id}/timeline")
def debug_workflow_timeline(session_id: str) -> dict[str, Any]:
    _ensure_debug_enabled()
    repository = get_workflow_repository()
    session = _require_session(repository, session_id)
    plan = repository.get_plan(session_id)
    steps = repository.list_steps(plan["plan_id"]) if plan else []
    artifacts = repository.list_artifacts(session_id)
    confirmations = repository.list_confirmations(session_id)
    artifacts_by_step = _artifacts_by_step(artifacts)
    return {
        "session": _session_summary(session),
        "plan": _plan_summary(plan),
        "steps": [_step_summary(step, artifacts_by_step.get(step["step_id"], [])) for step in steps],
        "artifacts": [_artifact_preview(artifact) for artifact in artifacts],
        "confirmation": _selected_confirmation(confirmations),
        "confirmations": [_confirmation_summary(confirmation) for confirmation in confirmations],
    }


# 这个接口返回 session 下的完整 artifact 列表，用于检查上下文传递。
@router.get("/workflows/{session_id}/artifacts")
def debug_workflow_artifacts(session_id: str) -> dict[str, Any]:
    _ensure_debug_enabled()
    repository = get_workflow_repository()
    _require_session(repository, session_id)
    return {
        "session_id": session_id,
        "artifacts": [_artifact_full(artifact) for artifact in repository.list_artifacts(session_id)],
    }


# 这个接口根据 workflow_plan.steps 生成动态图节点和 Mermaid 文本。
@router.get("/workflows/{session_id}/graph")
def debug_workflow_graph(session_id: str) -> dict[str, Any]:
    _ensure_debug_enabled()
    repository = get_workflow_repository()
    _require_session(repository, session_id)
    plan = repository.get_plan(session_id)
    steps = repository.list_steps(plan["plan_id"]) if plan else []
    nodes = [_graph_node(step) for step in steps]
    return {
        "session_id": session_id,
        "nodes": nodes,
        "mermaid": _build_mermaid(nodes),
    }


# 这个函数在调试功能关闭时阻止访问页面和调试数据。
def _ensure_debug_enabled() -> None:
    if not load_config().debug_enabled:
        raise HTTPException(status_code=404, detail="debug 接口未启用。")


# 这个函数构建健康检查项，并返回实际存储和运行态模式。
def _build_health_checks(config: ThirdServiceConfig) -> tuple[list[dict[str, str]], str, str]:
    checks: list[dict[str, str]] = []
    mysql_check, storage_mode = _check_mysql(config)
    redis_check, runtime_mode = _check_redis(config)
    checks.extend([mysql_check, redis_check])
    checks.append(_check_openai(config))
    checks.append(_check_feishu_table(config))
    checks.append(_check_feishu_auth(config))
    checks.append(_check_memory_fallback(config))
    return checks, storage_mode, runtime_mode


# 这个函数检查 MySQL Repository 是否能完成一次只读查询。
def _check_mysql(config: ThirdServiceConfig) -> tuple[dict[str, str], str]:
    if not config.mysql_dsn:
        status = "warning" if config.allow_in_memory_fallback else "error"
        mode = "memory" if config.allow_in_memory_fallback else "mysql"
        return _check("mysql", status, "THIRD_MYSQL_DSN 未配置。"), mode
    try:
        repository = get_workflow_repository()
        repository.list_sessions(1)
        mode = "memory" if repository.__class__.__name__.startswith("InMemory") else "mysql"
        return _check("mysql", "ok", "connected"), mode
    except Exception as exc:
        return _check("mysql", "error", _safe_error(exc, config)), "mysql"


# 这个函数检查 Redis Runtime 是否能完成一次只读连接。
def _check_redis(config: ThirdServiceConfig) -> tuple[dict[str, str], str]:
    if not config.redis_url:
        status = "warning" if config.allow_in_memory_fallback else "error"
        mode = "memory" if config.allow_in_memory_fallback else "redis"
        return _check("redis", status, "THIRD_REDIS_URL 未配置。"), mode
    try:
        runtime = get_workflow_runtime_store()
        runtime.get_cursor("__debug_health__")
        mode = "memory" if runtime.__class__.__name__.startswith("InMemory") else "redis"
        status = "warning" if mode == "memory" and config.redis_url else "ok"
        message = "fallback to memory" if mode == "memory" and config.redis_url else "connected"
        return _check("redis", status, message), mode
    except Exception as exc:
        return _check("redis", "error", _safe_error(exc, config)), "redis"


# 这个函数检查 LLM 模式下 OpenAI key 是否配置。
def _check_openai(config: ThirdServiceConfig) -> dict[str, str]:
    if config.openai_api_key:
        return _check("openai_api_key", "ok", "configured")
    if config.workflowagent_use_llm:
        return _check("openai_api_key", "error", "THIRD_WORKFLOWAGENT_USE_LLM=1 但 OPENAI_API_KEY 未配置。")
    return _check("openai_api_key", "missing", "OPENAI_API_KEY 未配置，当前使用规则 workflowagent。")


# 这个函数检查飞书表格定位信息是否满足当前模式。
def _check_feishu_table(config: ThirdServiceConfig) -> dict[str, str]:
    if not config.feishu_use_real:
        return _check("feishu_table", "ok", "mock 模式使用默认表配置。")
    missing = []
    if not config.feishu_app_token:
        missing.append("THIRD_FEISHU_APP_TOKEN")
    if not config.feishu_table_id:
        missing.append("THIRD_FEISHU_TABLE_ID")
    if missing:
        return _check("feishu_table", "error", f"缺少：{', '.join(missing)}")
    return _check("feishu_table", "ok", "configured")


# 这个函数检查飞书鉴权信息是否满足当前模式。
def _check_feishu_auth(config: ThirdServiceConfig) -> dict[str, str]:
    if not config.feishu_use_real:
        return _check("feishu_auth", "skipped", "mock 模式不需要飞书鉴权。")
    if config.feishu_tenant_access_token:
        return _check("feishu_auth", "ok", "tenant_access_token configured")
    if config.feishu_app_id and config.feishu_app_secret:
        return _check("feishu_auth", "ok", "app_id/app_secret configured")
    return _check("feishu_auth", "error", "缺少 THIRD_FEISHU_TENANT_ACCESS_TOKEN 或 THIRD_FEISHU_APP_ID/APP_SECRET。")


# 这个函数展示内存兜底开关，真实联调建议关闭。
def _check_memory_fallback(config: ThirdServiceConfig) -> dict[str, str]:
    if config.allow_in_memory_fallback:
        return _check("in_memory_fallback", "warning", "enabled，MySQL/Redis 失败时可能回退到进程内内存。")
    return _check("in_memory_fallback", "ok", "disabled，MySQL/Redis 失败会直接暴露错误。")


# 这个函数生成统一健康检查项。
def _check(name: str, status: str, message: str) -> dict[str, str]:
    return {"name": name, "status": status, "message": message}


# 这个函数读取 session，不存在时返回 404。
def _require_session(repository: WorkflowRepository, session_id: str) -> dict[str, Any]:
    session = repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"workflow session 不存在：{session_id}")
    return session


# 这个函数压缩 session 字段，供列表和时间线展示。
def _session_summary(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session.get("session_id"),
        "status": session.get("status"),
        "original_input": session.get("original_input"),
        "current_step_id": session.get("current_step_id"),
        "final_answer": session.get("final_answer") or "",
        "error_text": session.get("error_text") or "",
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
    }


# 这个函数压缩计划字段，同时保留完整 plan_json 便于排查 LLM 输出。
def _plan_summary(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    return {
        "plan_id": plan.get("plan_id"),
        "intent": plan.get("intent"),
        "risk_level": plan.get("risk_level"),
        "requires_confirmation": plan.get("requires_confirmation"),
        "plan_version": plan.get("plan_version"),
        "status": plan.get("status"),
        "plan_json": plan.get("plan_json") or {},
    }


# 这个函数把 artifacts 按来源步骤分组。
def _artifacts_by_step(artifacts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for artifact in artifacts:
        source_step_id = artifact.get("source_step_id")
        if source_step_id:
            grouped.setdefault(str(source_step_id), []).append(artifact)
    return grouped


# 这个函数压缩步骤字段，补充耗时和步骤产物摘要。
def _step_summary(step: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "step_id": step.get("step_id"),
        "local_step_id": step.get("local_step_id"),
        "step_seq": step.get("step_seq"),
        "kind": step.get("kind"),
        "name": _step_name(step),
        "tool_name": step.get("tool_name"),
        "agent_name": step.get("agent_name"),
        "prompt_ref": step.get("prompt_ref"),
        "status": step.get("status"),
        "output_key": step.get("output_key"),
        "duration_ms": _duration_ms(step.get("started_at"), step.get("finished_at"), step.get("status")),
        "attempt_count": step.get("attempt_count"),
        "error_text": step.get("error_text") or "",
        "input_spec_json": step.get("input_spec_json") or {},
        "validation_json": step.get("validation_json") or {},
        "artifacts": [_artifact_preview(artifact) for artifact in artifacts],
    }


# 这个函数选择当前应展示的确认请求，优先等待中的确认。
def _selected_confirmation(confirmations: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not confirmations:
        return None
    waiting = [item for item in confirmations if item.get("status") == "waiting"]
    selected = waiting[-1] if waiting else confirmations[-1]
    return _confirmation_summary(selected)


# 这个函数压缩确认请求字段。
def _confirmation_summary(confirmation: dict[str, Any]) -> dict[str, Any]:
    return {
        "confirmation_id": confirmation.get("confirmation_id"),
        "session_id": confirmation.get("session_id"),
        "step_id": confirmation.get("step_id"),
        "status": confirmation.get("status"),
        "request_text": confirmation.get("request_text"),
        "preview_json": confirmation.get("preview_json") or {},
        "user_response": confirmation.get("user_response") or "",
        "created_at": confirmation.get("created_at"),
        "decided_at": confirmation.get("decided_at"),
    }


# 这个函数生成 artifact 摘要，避免时间线页面一次性展示过长文本。
def _artifact_preview(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": artifact.get("artifact_id"),
        "session_id": artifact.get("session_id"),
        "source_step_id": artifact.get("source_step_id"),
        "artifact_key": artifact.get("artifact_key"),
        "content_preview": _shorten(str(artifact.get("content_text") or ""), 800),
        "data_preview": _shorten(json.dumps(artifact.get("data_json") or {}, ensure_ascii=False, default=str), 1200),
        "schema_json": artifact.get("schema_json") or {},
        "created_at": artifact.get("created_at"),
    }


# 这个函数返回完整 artifact，供专门的 Artifacts 视图展开排查。
def _artifact_full(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": artifact.get("artifact_id"),
        "session_id": artifact.get("session_id"),
        "source_step_id": artifact.get("source_step_id"),
        "artifact_key": artifact.get("artifact_key"),
        "content_text": artifact.get("content_text") or "",
        "data_json": artifact.get("data_json") or {},
        "schema_json": artifact.get("schema_json") or {},
        "expires_at": artifact.get("expires_at"),
        "created_at": artifact.get("created_at"),
    }


# 这个函数把步骤转换为动态图节点。
def _graph_node(step: dict[str, Any]) -> dict[str, str]:
    name = _step_name(step)
    return {
        "id": str(step.get("local_step_id") or step.get("step_id") or ""),
        "label": f"{step.get('step_seq')}. {name}",
        "status": str(step.get("status") or ""),
    }


# 这个函数生成 Mermaid 文本，调试页面同时展示节点链和源码。
def _build_mermaid(nodes: list[dict[str, str]]) -> str:
    if not nodes:
        return "flowchart TD\n  empty[\"暂无 workflow_plan.steps\"]"
    lines = ["flowchart TD"]
    mermaid_ids: list[str] = []
    for index, node in enumerate(nodes, start=1):
        node_id = f"n{index}"
        mermaid_ids.append(node_id)
        label = _escape_mermaid_label(f"{node.get('label', '')}<br/>{node.get('status', '')}")
        lines.append(f"  {node_id}[\"{label}\"]")
    for left, right in zip(mermaid_ids, mermaid_ids[1:]):
        lines.append(f"  {left} --> {right}")
    return "\n".join(lines)


# 这个函数计算步骤耗时；运行中的步骤用当前时间估算。
def _duration_ms(started_at: Any, finished_at: Any, status: Any) -> int | None:
    if not isinstance(started_at, datetime):
        return None
    end_time = finished_at if isinstance(finished_at, datetime) else now() if status == "running" else None
    if not isinstance(end_time, datetime):
        return None
    return max(0, int((end_time - started_at).total_seconds() * 1000))


# 这个函数生成步骤名称，优先展示 tool 或 agent。
def _step_name(step: dict[str, Any]) -> str:
    return str(step.get("tool_name") or step.get("agent_name") or step.get("kind") or step.get("local_step_id") or "")


# 这个函数截断过长文本，避免调试列表页面渲染过重。
def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


# 这个函数转义 Mermaid 标签中的特殊字符。
def _escape_mermaid_label(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "<br/>")


# 这个函数清理异常文本，避免把 DSN、token 或密钥泄露到调试健康检查。
def _safe_error(exc: Exception, config: ThirdServiceConfig) -> str:
    text = str(exc)
    sensitive_values = [
        config.openai_api_key,
        config.feishu_app_secret,
        config.feishu_tenant_access_token,
        config.feishu_app_token,
        config.mysql_dsn,
        config.redis_url,
    ]
    for value in sensitive_values:
        if value:
            text = text.replace(value, "***")
    text = re.sub(r"(mysql\+pymysql://[^:]+:)[^@]+(@)", r"\1***\2", text)
    text = re.sub(r"(redis://[^:]*:)[^@]+(@)", r"\1***\2", text)
    return _shorten(text, 500)
