"""LLM provider routing, probing, and fallback for third service."""

from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable


PRIMARY_PROVIDER = "openai"
FALLBACK_ELIGIBLE_ERROR_TYPES = {"connection_error", "timeout", "server_error", "proxy_error"}
PROBE_PROMPT = (
    "Return exactly this JSON and nothing else: "
    '{"status":"ok","source":"third_llm_probe"}'
)
_PROBE_CACHE: dict[str, "CachedProbeResult"] = {}
_CACHE_LOCK = threading.Lock()


@dataclass(frozen=True)
class LlmProviderSpec:
    name: str
    model: str
    api_key: str
    base_url: str = ""
    proxy_url: str = ""
    timeout_seconds: int = 60
    max_retries: int = 2
    no_proxy: bool = False

    @property
    def ready(self) -> bool:
        if self.name == PRIMARY_PROVIDER:
            return bool(self.api_key and self.model)
        return bool(self.api_key and self.base_url and self.model)


@dataclass(frozen=True)
class ProbeResult:
    provider: str
    status: str
    ready: bool
    samples: int
    successes: int
    min_successes: int
    latency_ms: int | None
    error_type: str
    message: str
    checked_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "ready": self.ready,
            "samples": self.samples,
            "successes": self.successes,
            "min_successes": self.min_successes,
            "latency_ms": self.latency_ms,
            "error_type": self.error_type,
            "message": self.message,
            "checked_at": self.checked_at,
        }


@dataclass(frozen=True)
class CachedProbeResult:
    result: ProbeResult
    expires_at_monotonic: float


class RouteAwareChatModel:
    """Small wrapper that preserves ChatOpenAI.invoke while adding route fallback."""

    def __init__(
        self,
        config: Any,
        model: str,
        temperature: float = 0,
        primary_client: Any | None = None,
        chat_openai_cls: Any | None = None,
        httpx_client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config
        self.model = model
        self.temperature = temperature
        self._chat_openai_cls = chat_openai_cls
        self._httpx_client_factory = httpx_client_factory
        self.primary_spec = primary_provider_spec(config, model)
        self.primary_client = primary_client
        if self.primary_client is None and self.primary_spec.ready and not route_domestic_enabled(config):
            self.primary_client = create_provider_client(
                self.primary_spec,
                temperature,
                chat_openai_cls=chat_openai_cls,
                httpx_client_factory=httpx_client_factory,
            )

    def invoke(self, prompt: Any, *args: Any, **kwargs: Any) -> Any:
        if route_domestic_enabled(self.config):
            return self._invoke_fallbacks(prompt, None, *args, **kwargs)
        if not route_auto_enabled(self.config) or not ready_fallback_provider_specs(self.config):
            if self.primary_client is None:
                raise RuntimeError("LLM 主通道未配置 OPENAI_API_KEY，且当前路由模式没有可用备用模型。")
            return self.primary_client.invoke(prompt, *args, **kwargs)

        if not self.primary_spec.ready:
            return self._invoke_fallbacks(prompt, None, *args, **kwargs)
        if should_skip_provider(self.config, self.primary_spec):
            return self._invoke_fallbacks(prompt, None, *args, **kwargs)

        try:
            if self.primary_client is None:
                raise RuntimeError("LLM 主通道未配置 OPENAI_API_KEY。")
            return self.primary_client.invoke(prompt, *args, **kwargs)
        except Exception as exc:
            classification = classify_llm_exception(exc)
            if classification not in FALLBACK_ELIGIBLE_ERROR_TYPES:
                raise
            mark_provider_unhealthy(self.config, self.primary_spec, classification, exc)
            return self._invoke_fallbacks(prompt, exc, *args, **kwargs)

    def _invoke_fallbacks(self, prompt: Any, primary_error: Exception | None, *args: Any, **kwargs: Any) -> Any:
        attempted: list[str] = []
        fallback_errors: list[str] = []
        last_error: Exception | None = None
        for spec in fallback_provider_specs(self.config):
            attempted.append(spec.name)
            if not spec.ready:
                fallback_errors.append(f"{spec.name}: skipped_missing_config")
                continue
            try:
                client = create_provider_client(
                    spec,
                    self.temperature,
                    chat_openai_cls=self._chat_openai_cls,
                    httpx_client_factory=self._httpx_client_factory,
                )
                return client.invoke(prompt, *args, **kwargs)
            except Exception as exc:
                last_error = exc
                classification = classify_llm_exception(exc)
                error_text = safe_exception_text(exc, self.config)
                fallback_errors.append(f"{spec.name}: {classification}: {error_text}")
                if classification not in FALLBACK_ELIGIBLE_ERROR_TYPES:
                    raise RuntimeError(f"LLM 备用通道 {spec.name} 调用失败：{safe_exception_text(exc, self.config)}") from exc
                mark_provider_unhealthy(self.config, spec, classification, exc)

        if primary_error is not None:
            raise RuntimeError(
                "LLM 主通道失败，且没有可用备用模型。"
                f" primary_error={safe_exception_text(primary_error, self.config)}"
                f" attempted_fallbacks={','.join(attempted) or 'none'}"
                f" fallback_errors={'; '.join(fallback_errors) or 'none'}"
            ) from last_error or primary_error
        raise RuntimeError(
            "LLM 主通道当前不健康，且没有可用备用模型。"
            f" attempted_fallbacks={','.join(attempted) or 'none'}"
            f" fallback_errors={'; '.join(fallback_errors) or 'none'}"
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self.primary_client, name)


def primary_provider_spec(config: Any, model: str) -> LlmProviderSpec:
    return LlmProviderSpec(
        name=PRIMARY_PROVIDER,
        model=model,
        api_key=str(getattr(config, "openai_api_key", "") or ""),
        proxy_url=str(getattr(config, "openai_proxy_url", "") or "").strip(),
        timeout_seconds=int(getattr(config, "openai_timeout_seconds", 60) or 60),
        max_retries=int(getattr(config, "openai_max_retries", 2) or 2),
    )


def fallback_provider_specs(config: Any) -> list[LlmProviderSpec]:
    providers: list[LlmProviderSpec] = []
    seen: set[str] = set()
    for name in getattr(config, "llm_fallback_providers", ["deepseek", "minimax"]) or []:
        normalized = str(name).strip().lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        spec = _fallback_provider_spec(config, normalized)
        if spec:
            providers.append(spec)
    return providers


def ready_fallback_provider_specs(config: Any) -> list[LlmProviderSpec]:
    return [spec for spec in fallback_provider_specs(config) if spec.ready]


def all_provider_specs(config: Any, model: str | None = None) -> list[LlmProviderSpec]:
    primary_model = model or str(getattr(config, "workflowagent_model", "") or "gpt-4o-mini")
    return [primary_provider_spec(config, primary_model), *fallback_provider_specs(config)]


def create_provider_client(
    spec: LlmProviderSpec,
    temperature: float = 0,
    chat_openai_cls: Any | None = None,
    httpx_client_factory: Callable[..., Any] | None = None,
) -> Any:
    if chat_openai_cls is None:
        from langchain_openai import ChatOpenAI

        chat_openai_cls = ChatOpenAI
    kwargs: dict[str, Any] = {
        "model": spec.model,
        "temperature": temperature,
        "api_key": spec.api_key,
        "request_timeout": spec.timeout_seconds,
        "max_retries": spec.max_retries,
    }
    if spec.base_url:
        kwargs["base_url"] = spec.base_url
    if spec.proxy_url and not spec.no_proxy:
        kwargs["openai_proxy"] = spec.proxy_url
    if spec.no_proxy:
        if httpx_client_factory is None:
            import httpx

            httpx_client_factory = httpx.Client
        kwargs["http_client"] = httpx_client_factory(trust_env=False)
    return chat_openai_cls(**kwargs)


def route_auto_enabled(config: Any) -> bool:
    return _route_mode(config) == "auto"


def route_domestic_enabled(config: Any) -> bool:
    return _route_mode(config) in {"domestic", "fallback", "fallback_only"}


def _route_mode(config: Any) -> str:
    mode = str(getattr(config, "llm_route_mode", "auto") or "auto").strip().lower()
    return mode


def should_skip_primary(config: Any, refresh: bool = False) -> bool:
    if not route_auto_enabled(config) or not bool(getattr(config, "llm_probe_enabled", True)):
        return False
    if not ready_fallback_provider_specs(config):
        return False
    spec = primary_provider_spec(config, str(getattr(config, "workflowagent_model", "") or "gpt-4o-mini"))
    result = get_cached_probe_result(spec, config, refresh=refresh)
    return result.status != "healthy"


def should_skip_provider(config: Any, spec: LlmProviderSpec, refresh: bool = False) -> bool:
    if not route_auto_enabled(config) or not bool(getattr(config, "llm_probe_enabled", True)):
        return False
    if not ready_fallback_provider_specs(config):
        return False
    result = get_cached_probe_result(spec, config, refresh=refresh)
    return result.status != "healthy"


def probe_llm_routes(config: Any, samples: int | None = None, refresh: bool = False) -> dict[str, Any]:
    results = []
    for spec in all_provider_specs(config):
        result = get_cached_probe_result(spec, config, samples=samples, refresh=refresh)
        results.append(result.to_dict())
    return {
        "route_mode": str(getattr(config, "llm_route_mode", "auto") or "auto"),
        "fallback_providers": [spec.name for spec in fallback_provider_specs(config)],
        "results": results,
    }


def get_cached_probe_result(
    spec: LlmProviderSpec,
    config: Any,
    samples: int | None = None,
    refresh: bool = False,
) -> ProbeResult:
    cache_key = _cache_key(spec)
    now_monotonic = time.monotonic()
    with _CACHE_LOCK:
        cached = _PROBE_CACHE.get(cache_key)
        if not refresh and cached and cached.expires_at_monotonic > now_monotonic:
            return cached.result

    result = probe_provider(spec, config, samples=samples)
    ttl_seconds = _probe_ttl_seconds(config)
    with _CACHE_LOCK:
        _PROBE_CACHE[cache_key] = CachedProbeResult(result=result, expires_at_monotonic=now_monotonic + ttl_seconds)
    return result


def probe_provider(spec: LlmProviderSpec, config: Any, samples: int | None = None) -> ProbeResult:
    checked_at = _utc_now()
    sample_count = max(1, int(samples if samples is not None else getattr(config, "llm_probe_samples", 3) or 3))
    min_successes = max(1, int(getattr(config, "llm_probe_min_successes", 2) or 2))
    if min_successes > sample_count:
        min_successes = sample_count
    if not spec.ready:
        return ProbeResult(
            provider=spec.name,
            status="misconfigured",
            ready=False,
            samples=sample_count,
            successes=0,
            min_successes=min_successes,
            latency_ms=None,
            error_type="missing_config",
            message=f"{spec.name} 配置不完整，已跳过。",
            checked_at=checked_at,
        )

    successes = 0
    latency_values: list[int] = []
    last_error_type = ""
    last_error_text = ""
    for _ in range(sample_count):
        start = time.perf_counter()
        try:
            client = create_provider_client(spec, temperature=0)
            response = client.invoke(PROBE_PROMPT)
            content = str(getattr(response, "content", "") or "")
            if _probe_content_ok(content):
                successes += 1
                latency_values.append(int((time.perf_counter() - start) * 1000))
            else:
                last_error_type = "invalid_response"
                last_error_text = "探测响应不是预期 JSON。"
        except Exception as exc:
            last_error_type = classify_llm_exception(exc)
            last_error_text = safe_exception_text(exc, config)

    if successes >= min_successes:
        return ProbeResult(
            provider=spec.name,
            status="healthy",
            ready=True,
            samples=sample_count,
            successes=successes,
            min_successes=min_successes,
            latency_ms=_average_latency(latency_values),
            error_type="",
            message="healthy",
            checked_at=checked_at,
        )
    status = "auth_error" if last_error_type in {"auth_error", "permission_error"} else "unhealthy"
    return ProbeResult(
        provider=spec.name,
        status=status,
        ready=True,
        samples=sample_count,
        successes=successes,
        min_successes=min_successes,
        latency_ms=_average_latency(latency_values),
        error_type=last_error_type or "unknown_error",
        message=last_error_text or "探测失败。",
        checked_at=checked_at,
    )


def mark_provider_unhealthy(config: Any, spec: LlmProviderSpec, error_type: str, exc: Exception) -> None:
    result = ProbeResult(
        provider=spec.name,
        status="unhealthy",
        ready=spec.ready,
        samples=0,
        successes=0,
        min_successes=0,
        latency_ms=None,
        error_type=error_type,
        message=safe_exception_text(exc, config),
        checked_at=_utc_now(),
    )
    ttl_seconds = max(1, int(getattr(config, "llm_unhealthy_ttl_seconds", 120) or 120))
    with _CACHE_LOCK:
        _PROBE_CACHE[_cache_key(spec)] = CachedProbeResult(result=result, expires_at_monotonic=time.monotonic() + ttl_seconds)


def clear_probe_cache() -> None:
    with _CACHE_LOCK:
        _PROBE_CACHE.clear()


def classify_llm_exception(exc: Exception) -> str:
    status_code = getattr(exc, "status_code", None)
    if status_code in {401, 403}:
        return "auth_error"
    if status_code == 429:
        return "rate_limit"
    if isinstance(status_code, int) and status_code >= 500:
        return "server_error"
    class_name = exc.__class__.__name__.lower()
    text = str(exc).lower()
    if "authentication" in class_name or "permissiondenied" in class_name:
        return "auth_error"
    if "ratelimit" in class_name:
        return "rate_limit"
    if "badrequest" in class_name or "invalidrequest" in class_name:
        return "bad_request"
    if "timeout" in class_name or "timeout" in text or isinstance(exc, TimeoutError):
        return "timeout"
    if "proxy" in class_name or "proxy" in text:
        return "proxy_error"
    if "connection" in class_name or "connect" in class_name or "connection" in text:
        return "connection_error"
    if isinstance(exc, (OSError, socket.error)):
        return "connection_error"
    if "internalserver" in class_name or "servererror" in class_name:
        return "server_error"
    return "unknown_error"


def safe_exception_text(exc: Exception, config: Any) -> str:
    text = str(exc)
    sensitive_values = [
        getattr(config, "openai_api_key", ""),
        getattr(config, "openai_proxy_url", ""),
        getattr(config, "deepseek_api_key", ""),
        getattr(config, "deepseek_base_url", ""),
        getattr(config, "minimax_api_key", ""),
        getattr(config, "minimax_base_url", ""),
    ]
    for value in sensitive_values:
        if value:
            text = text.replace(str(value), "***")
    return _redact_text(text)


def _fallback_provider_spec(config: Any, name: str) -> LlmProviderSpec | None:
    if name == "deepseek":
        return LlmProviderSpec(
            name="deepseek",
            model=str(getattr(config, "deepseek_model", "") or ""),
            api_key=str(getattr(config, "deepseek_api_key", "") or ""),
            base_url=str(getattr(config, "deepseek_base_url", "") or "").strip(),
            timeout_seconds=int(getattr(config, "deepseek_timeout_seconds", 60) or 60),
            max_retries=int(getattr(config, "deepseek_max_retries", 0) or 0),
            no_proxy=True,
        )
    if name == "minimax":
        return LlmProviderSpec(
            name="minimax",
            model=str(getattr(config, "minimax_model", "") or ""),
            api_key=str(getattr(config, "minimax_api_key", "") or ""),
            base_url=str(getattr(config, "minimax_base_url", "") or "").strip(),
            timeout_seconds=int(getattr(config, "minimax_timeout_seconds", 60) or 60),
            max_retries=int(getattr(config, "minimax_max_retries", 0) or 0),
            no_proxy=True,
        )
    return None


def _probe_ttl_seconds(config: Any) -> int:
    return max(1, int(getattr(config, "llm_probe_ttl_seconds", 60) or 60))


def _cache_key(spec: LlmProviderSpec) -> str:
    signature = json.dumps(
        {
            "name": spec.name,
            "model": spec.model,
            "base_url": spec.base_url,
            "proxy_url": spec.proxy_url,
            "no_proxy": spec.no_proxy,
        },
        sort_keys=True,
    )
    return signature


def _probe_content_ok(content: str) -> bool:
    if not content.strip():
        return False
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return "third_llm_probe" in content
    return isinstance(parsed, dict) and parsed.get("status") == "ok"


def _average_latency(values: list[int]) -> int | None:
    if not values:
        return None
    return int(sum(values) / len(values))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact_text(text: str) -> str:
    import re

    redacted = re.sub(r"(?i)((?:OPENAI|DEEPSEEK|MINIMAX|LLM)[A-Z0-9_]*API_KEY[\"']?\s*[:=：]\s*[\"']?)([^\s\"',}]+)([\"']?)", r"\1***\3", text)
    redacted = re.sub(r"(?i)(https?://)[^/\s:@]+:[^@\s/]+@([^/\s]+)", r"\1***:***@\2", redacted)
    redacted = re.sub(r"\bsk-[A-Za-z0-9_\-]{10,}\b", "sk-***", redacted)
    return redacted
