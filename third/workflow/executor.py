"""workflow 固定执行器。"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

try:
    from ..agents.shared.config import load_config
    from ..agents.workflowagent.agent import build_workflow_plan
    from ..agents.workflowagent.agent import WRITE_TOOLS
    from ..runtime.factory import get_workflow_runtime_store
    from ..storage.factory import get_workflow_repository
    from ..storage.repository import WorkflowRepository, now
    from .agent_runner import run_business_agent
    from .content import extract_content_text
    from .plan_validator import PlanValidationError, validate_workflow_plan
    from .tool_dispatcher import dispatch_tool
    from .validation import run_validation_node
except ImportError:
    from agents.shared.config import load_config
    from agents.workflowagent.agent import build_workflow_plan
    from agents.workflowagent.agent import WRITE_TOOLS
    from runtime.factory import get_workflow_runtime_store
    from storage.factory import get_workflow_repository
    from storage.repository import WorkflowRepository, now
    from workflow.agent_runner import run_business_agent
    from workflow.content import extract_content_text
    from workflow.plan_validator import PlanValidationError, validate_workflow_plan
    from workflow.tool_dispatcher import dispatch_tool
    from workflow.validation import run_validation_node


# 这一段定义 workflow 执行日志，worker 和 API 都会通过标准 logging 输出。
LOGGER = logging.getLogger(__name__)


# 这一段定义日志脱敏规则，避免调试 plan 时泄露飞书、OpenAI、数据库或 Redis 凭证。
SENSITIVE_KEY_PATTERN = re.compile(r"(secret|token|api[_-]?key|password|authorization|dsn|redis[_-]?url)", re.IGNORECASE)
SENSITIVE_TEXT_PATTERNS = (
    (re.compile(r"(app_token[\"']?\s*[:=：]\s*[\"']?)([A-Za-z0-9_\-]+)([\"']?)", re.IGNORECASE), r"\1***\3"),
    (re.compile(r"(tenant_access_token[\"']?\s*[:=：]\s*[\"']?)([A-Za-z0-9._\-]+)([\"']?)", re.IGNORECASE), r"\1***\3"),
    (re.compile(r"(app_secret[\"']?\s*[:=：]\s*[\"']?)([A-Za-z0-9._\-]+)([\"']?)", re.IGNORECASE), r"\1***\3"),
    (re.compile(r"(OPENAI_API_KEY[\"']?\s*[:=：]\s*[\"']?)([A-Za-z0-9._\-]+)([\"']?)", re.IGNORECASE), r"\1***\3"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{10,}\b"), "sk-***"),
    (re.compile(r"(mysql\+pymysql://[^:]+:)[^@]+(@)", re.IGNORECASE), r"\1***\2"),
    (re.compile(r"(redis://[^:]*:)[^@]+(@)", re.IGNORECASE), r"\1***\2"),
    (re.compile(r"(/base/)([A-Za-z0-9_\-]+)", re.IGNORECASE), r"\1***"),
)


# 这个类解释并执行 workflow_plan.steps。
class WorkflowExecutor:
    # 这个构造函数注入 Repository 和运行态存储，便于 API、worker 和 LangGraph 共用。
    def __init__(self, repository: WorkflowRepository | None = None, runtime_store: Any | None = None) -> None:
        self.repository = repository or get_workflow_repository()
        self.runtime_store = runtime_store or get_workflow_runtime_store()

    # 这个方法执行指定 session，直到完成、失败或等待用户确认。
    def run_session(self, session_id: str, max_steps: int = 50) -> dict[str, Any]:
        session = self.repository.get_session(session_id)
        if not session:
            raise KeyError(f"workflow session 不存在：{session_id}")
        self.repository.update_session(session_id, status="running")
        try:
            plan = self._ensure_plan(session_id, session["original_input"])
            for _ in range(max_steps):
                next_step = self._next_pending_step(plan["plan_id"])
                if not next_step:
                    return self._finish_session(session_id, plan)
                result = self._run_step(session_id, plan, next_step)
                if result.get("status") in {"waiting_user", "cancelled", "failed"}:
                    return self.repository.get_session(session_id) or result
            raise RuntimeError("workflow 执行超过最大步骤数，已停止。")
        except Exception as exc:
            self.repository.update_session(session_id, status="failed", error_text=str(exc))
            return self.repository.get_session(session_id) or {"status": "failed", "error_text": str(exc)}

    # 这个方法确保 session 已经有可执行计划。
    def _ensure_plan(self, session_id: str, original_input: str) -> dict[str, Any]:
        existing_plan = self.repository.get_plan(session_id)
        if existing_plan:
            return existing_plan
        raw_plan = build_workflow_plan(original_input)
        try:
            plan = validate_workflow_plan(raw_plan)
        except PlanValidationError:
            raise
        _log_workflow_plan(session_id, plan)
        saved_plan = self.repository.save_plan(session_id, plan)
        self.repository.save_artifact(
            session_id,
            "workflow.plan",
            None,
            content_text=json.dumps(plan, ensure_ascii=False, default=str),
            data_json=plan,
            schema_json={"type": "workflow_plan"},
        )
        return saved_plan

    # 这个方法找到下一个 pending 步骤。
    def _next_pending_step(self, plan_id: str) -> dict[str, Any] | None:
        for step in self.repository.list_steps(plan_id):
            if step["status"] == "pending":
                return step
            if step["status"] == "waiting_user":
                return step
        return None

    # 这个方法执行单个步骤。
    def _run_step(self, session_id: str, plan: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        self.repository.update_session(session_id, current_step_id=step["step_id"])
        self.runtime_store.set_cursor(session_id, step["step_id"])
        if step["kind"] == "confirm":
            return self._run_confirm_step(session_id, step)

        self.repository.update_step(step["step_id"], status="running", attempt_count=int(step.get("attempt_count") or 0) + 1, started_at=now())
        context = self._build_step_context(session_id, plan, step)
        try:
            if step["kind"] == "tool":
                output = self._idempotent_tool_output(context) or dispatch_tool(context)
            elif step["kind"] == "agent":
                output = run_business_agent(context)
            elif step["kind"] == "validation":
                output = run_validation_node(context)
            else:
                raise ValueError(f"不支持的 step.kind：{step['kind']}")
            artifact = self._save_step_output(session_id, step, output)
            self._mark_idempotency_success_if_needed(context, artifact)
            self.repository.update_step(step["step_id"], status="success", finished_at=now(), error_text=None)
            return {"status": "success"}
        except Exception as exc:
            _log_step_failure(session_id, step, exc)
            self.repository.update_step(step["step_id"], status="failed", finished_at=now(), error_text=str(exc))
            self.repository.update_session(session_id, status="failed", error_text=str(exc))
            return {"status": "failed", "error_text": str(exc)}

    # 这个方法构造当前步骤上下文。
    def _build_step_context(self, session_id: str, plan: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
        input_spec = step.get("input_spec_json") or {}
        artifacts: dict[str, Any] = {}
        for artifact_key in input_spec.get("from_session") or []:
            artifact = self.repository.get_artifact(session_id, artifact_key)
            if not artifact:
                raise ValueError(f"缺少步骤依赖 artifact：{artifact_key}")
            artifacts[artifact_key] = artifact
        session = self.repository.get_session(session_id) or {}
        return {
            "session_id": session_id,
            "original_input": session.get("original_input", ""),
            "plan": plan.get("plan_json") or plan,
            "step": step,
            "artifacts": artifacts,
        }

    # 这个方法保存步骤输出为 artifact，并写入 Redis 短期缓存。
    def _save_step_output(self, session_id: str, step: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        artifact_key = step.get("output_key") or step["step_id"]
        artifact = self.repository.save_artifact(
            session_id,
            artifact_key,
            step["step_id"],
            content_text=str(output.get("content_text") or ""),
            data_json=output.get("data_json") or {},
            schema_json=output.get("schema_json") or {},
        )
        self.runtime_store.set_temp_artifact(session_id, artifact_key, artifact)
        if artifact_key == "validation.write_payload":
            self._save_idempotency(session_id, artifact)
        return artifact

    # 这个方法把 validation 产出的幂等信息写入 MySQL 和 Redis。
    def _save_idempotency(self, session_id: str, artifact: dict[str, Any]) -> None:
        data_json = artifact.get("data_json") or {}
        idempotency_key = data_json.get("idempotency_key")
        if not idempotency_key:
            return
        existing = self.repository.get_idempotency_key(str(idempotency_key))
        if existing and existing.get("status") == "success":
            return
        saved = self.repository.save_idempotency_key(
            str(idempotency_key),
            session_id,
            str(data_json.get("operation") or ""),
            "feishu_bitable",
            str(data_json.get("payload_hash") or ""),
            "running",
            expires_at=_parse_datetime(data_json.get("expires_at")),
        )
        self.runtime_store.set_idempotency(str(idempotency_key), saved)

    # 这个方法在写入 Tool 调用前检查是否已有成功幂等结果。
    def _idempotent_tool_output(self, context: dict[str, Any]) -> dict[str, Any] | None:
        step = context.get("step") or {}
        if step.get("tool_name") not in WRITE_TOOLS:
            return None
        validation_data = (context.get("artifacts", {}).get("validation.write_payload") or {}).get("data_json") or {}
        idempotency_key = validation_data.get("idempotency_key")
        if not idempotency_key:
            return None
        cached = self.runtime_store.get_idempotency(str(idempotency_key))
        durable = self.repository.get_idempotency_key(str(idempotency_key))
        hit = durable if durable and durable.get("status") == "success" else cached
        if not hit or hit.get("status") != "success":
            return None
        summary = "已命中幂等记录，跳过重复写入飞书。"
        return {
            "content_text": json.dumps({"summary": summary, "idempotency_key": idempotency_key}, ensure_ascii=False),
            "data_json": {"summary": summary, "idempotency_key": idempotency_key, "idempotent": True},
            "schema_json": {"type": "idempotent_tool_result"},
        }

    # 这个方法在写入 Tool 成功后把幂等记录更新为 success。
    def _mark_idempotency_success_if_needed(self, context: dict[str, Any], artifact: dict[str, Any]) -> None:
        step = context.get("step") or {}
        if step.get("tool_name") not in WRITE_TOOLS:
            return
        data_json = (context.get("artifacts", {}).get("validation.write_payload") or {}).get("data_json") or {}
        idempotency_key = data_json.get("idempotency_key")
        if not idempotency_key:
            return
        output_data = artifact.get("data_json") or {}
        if output_data.get("error"):
            return
        saved = self.repository.save_idempotency_key(
            str(idempotency_key),
            str(context.get("session_id")),
            str(data_json.get("operation") or ""),
            "feishu_bitable",
            str(data_json.get("payload_hash") or ""),
            "success",
            result_artifact_id=artifact.get("artifact_id"),
            expires_at=_parse_datetime(data_json.get("expires_at")),
        )
        self.runtime_store.set_idempotency(str(idempotency_key), saved)

    # 这个方法处理确认步骤，首次进入会暂停 workflow。
    def _run_confirm_step(self, session_id: str, step: dict[str, Any]) -> dict[str, Any]:
        existing = self.repository.get_waiting_confirmation(session_id)
        if existing:
            self.repository.update_step(step["step_id"], status="waiting_user")
            self.repository.update_session(session_id, status="waiting_user", current_step_id=step["step_id"])
            return {"status": "waiting_user"}

        context = self._build_step_context(session_id, {"plan_id": step["plan_id"]}, step)
        preview = _confirmation_preview(context)
        confirmation = self.repository.create_confirmation(
            session_id,
            step["step_id"],
            "确认执行以下飞书写入操作吗？",
            preview,
        )
        self.repository.update_step(step["step_id"], status="waiting_user")
        self.repository.update_session(session_id, status="waiting_user", current_step_id=step["step_id"])
        self.repository.save_artifact(
            session_id,
            step.get("output_key") or "confirmation.write",
            step["step_id"],
            content_text=json.dumps(confirmation, ensure_ascii=False, default=str),
            data_json=confirmation,
            schema_json={"type": "confirmation"},
        )
        return {"status": "waiting_user", "confirmation": confirmation}

    # 这个方法生成最终答案并完成 session。
    def _finish_session(self, session_id: str, plan: dict[str, Any]) -> dict[str, Any]:
        source_key = ((plan.get("plan_json") or {}).get("final") or {}).get("source") or "write_result"
        artifact = self.repository.get_artifact(session_id, source_key)
        answer = _answer_from_artifact(artifact)
        self.repository.update_session(session_id, status="success", final_answer=answer, current_step_id=None)
        self.repository.save_artifact(
            session_id,
            "final.answer",
            None,
            content_text=answer,
            data_json={"answer": answer},
            schema_json={"type": "answer"},
        )
        return self.repository.get_session(session_id) or {"status": "success", "final_answer": answer}


# 这个函数从确认步骤依赖中提取展示预览。
def _confirmation_preview(context: dict[str, Any]) -> dict[str, Any]:
    artifact = context.get("artifacts", {}).get("validation.write_payload") or {}
    data_json = artifact.get("data_json") or {}
    return data_json.get("preview") or data_json


# 这个函数把最终 artifact 转成用户可读答案。
def _answer_from_artifact(artifact: dict[str, Any] | None) -> str:
    if not artifact:
        return "workflow 已完成，但没有生成最终结果。"
    data_json = artifact.get("data_json") or {}
    if data_json.get("error"):
        return f"操作失败：{data_json['error']}"
    if data_json.get("summary"):
        return str(data_json["summary"])
    content_text = str(artifact.get("content_text") or "")
    try:
        payload = json.loads(content_text) if content_text.startswith("{") else None
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict) and payload.get("summary"):
        return str(payload["summary"])
    return content_text or "workflow 已完成。"


# 这个函数把 artifact JSON 里的 ISO 时间还原成 MySQL DateTime 列需要的 datetime。
def _parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


# 这个函数在本地调试日志里打印 workflowagent 生成的完整 plan。
def _log_workflow_plan(session_id: str, plan: dict[str, Any]) -> None:
    if not load_config().workflow_debug_log:
        return
    _ensure_debug_logger()
    payload = {
        "event": "workflow_plan_generated",
        "session_id": session_id,
        "intent": plan.get("intent"),
        "risk_level": plan.get("risk_level"),
        "requires_confirmation": plan.get("requires_confirmation"),
        "steps": _step_log_summary(plan.get("steps") or []),
        "workflow_plan": plan,
    }
    LOGGER.info(json.dumps(_redact_for_log(payload), ensure_ascii=False, default=str))


# 这个函数在步骤失败时打印必要上下文，方便直接从 worker/API 控制台定位问题。
def _log_step_failure(session_id: str, step: dict[str, Any], exc: Exception) -> None:
    if not load_config().workflow_debug_log:
        return
    _ensure_debug_logger()
    payload = {
        "event": "workflow_step_failed",
        "session_id": session_id,
        "step_id": step.get("step_id"),
        "local_step_id": step.get("local_step_id"),
        "kind": step.get("kind"),
        "tool_name": step.get("tool_name"),
        "agent_name": step.get("agent_name"),
        "error_text": str(exc),
    }
    LOGGER.error(json.dumps(_redact_for_log(payload), ensure_ascii=False, default=str))


# 这个函数确保 API 或 worker 进程都能输出 workflow 调试日志。
def _ensure_debug_logger() -> None:
    LOGGER.setLevel(logging.INFO)
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )


# 这个函数把 plan 中的步骤压缩成适合日志扫描的摘要。
def _step_log_summary(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "step_id": step.get("step_id"),
            "kind": step.get("kind"),
            "tool_name": step.get("tool_name"),
            "agent_name": step.get("agent_name"),
            "output": step.get("output"),
        }
        for step in steps
    ]


# 这个函数递归清理日志对象中的敏感字段和值。
def _redact_for_log(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if SENSITIVE_KEY_PATTERN.search(key_text):
                cleaned[key_text] = "***"
            else:
                cleaned[key_text] = _redact_for_log(item)
        return cleaned
    if isinstance(value, list):
        return [_redact_for_log(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


# 这个函数对日志文本做补充脱敏，覆盖用户输入里直接携带 token 或链接的情况。
def _redact_text(text: str) -> str:
    redacted = text
    for pattern, replacement in SENSITIVE_TEXT_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


# 这个函数为 LangGraph 同步入口创建并执行一次 workflow。
def invoke_workflow_sync(payload: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    repository = get_workflow_repository()
    original_input = extract_content_text(payload)
    if not original_input:
        return {"content": [{"text": "请输入 content[0].text。"}]}
    session = repository.create_session(original_input, status="running")
    result = WorkflowExecutor(repository=repository).run_session(session["session_id"])
    waiting_confirmation = repository.get_waiting_confirmation(session["session_id"])
    if waiting_confirmation:
        text = f"workflow 已等待用户确认。session_id：{session['session_id']}。{waiting_confirmation['request_text']}"
    else:
        text = str(result.get("final_answer") or result.get("error_text") or result.get("status"))
    return {"content": [{"text": text}]}
