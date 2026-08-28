"""
Analytics/Observability nodes — log LLM traces and runs to monitoring platforms.

Nodes:
  analytic.langsmith.log_run      — LangSmith run logging
  analytic.langfuse.log_trace     — Langfuse trace + generation logging
  analytic.langwatch.log          — LangWatch trace logging
  analytic.arize.log              — Arize Phoenix REST logging
  analytic.lunary.log             — Lunary (OpenLLMetry-compatible) logging
  analytic.opik.log               — Opik / Comet LLM trace logging
  analytic.phoenix.log            — Arize Phoenix HTTP collector
  analytic.log_llm_call           — generic structured LLM trace logger
"""
import json
import time
import uuid
from datetime import datetime, timezone

import httpx
import structlog

from core.config import settings
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trace_id() -> str:
    return str(uuid.uuid4())


# ─── analytic.langsmith.log_run ──────────────────────────────────────────────

@register_node("analytic.langsmith.log_run")
async def analytic_langsmith_log_run(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Log an LLM run to LangSmith.
    config: project_name, run_type, name, tags, api_key
    input_data: inputs, outputs, error, start_time, end_time
    """
    api_key = config.get("api_key") or getattr(settings, "LANGCHAIN_API_KEY", "") or getattr(settings, "LANGSMITH_API_KEY", "")
    project = config.get("project_name") or getattr(settings, "LANGCHAIN_PROJECT", "autoflow")
    api_url = config.get("api_url", "https://api.smith.langchain.com")
    run_type = config.get("run_type", "llm")
    run_name = config.get("name", "AutoFlow Run")
    tags = config.get("tags", [])

    if not api_key:
        return {"logged": False, "error": "LANGCHAIN_API_KEY or LANGSMITH_API_KEY required"}

    run_id = _trace_id()
    start_time = input_data.get("start_time", _now_iso())
    end_time = input_data.get("end_time", _now_iso())
    inputs = input_data.get("inputs", {"input": input_data.get("input", "")})
    outputs = input_data.get("outputs", {"output": input_data.get("output", "")})
    error = input_data.get("error")

    payload = {
        "id": run_id,
        "name": run_name,
        "run_type": run_type,
        "inputs": inputs,
        "outputs": outputs,
        "start_time": start_time,
        "end_time": end_time,
        "project_name": project,
        "tags": tags,
        "extra": config.get("extra", {}),
    }
    if error:
        payload["error"] = error

    headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{api_url}/runs", headers=headers, json=payload)
            r.raise_for_status()
        return {"logged": True, "run_id": run_id, "project": project}
    except Exception as e:
        log.warning("langsmith_log_failed", error=str(e))
        return {"logged": False, "error": str(e)}


# ─── analytic.langfuse.log_trace ─────────────────────────────────────────────

@register_node("analytic.langfuse.log_trace")
async def analytic_langfuse_log_trace(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Log a trace + generation to Langfuse.
    config: public_key, secret_key, host, trace_name, user_id, session_id, tags
    input_data: input, output, model, usage (dict), metadata
    """
    import base64
    public_key = config.get("public_key") or getattr(settings, "LANGFUSE_PUBLIC_KEY", "")
    secret_key = config.get("secret_key") or getattr(settings, "LANGFUSE_SECRET_KEY", "")
    host = (config.get("host") or getattr(settings, "LANGFUSE_HOST", "https://cloud.langfuse.com")).rstrip("/")

    if not public_key or not secret_key:
        return {"logged": False, "error": "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY required"}

    token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

    trace_id = _trace_id()
    generation_id = _trace_id()
    now = _now_iso()

    user_id = config.get("user_id") or input_data.get("user_id")
    session_id = config.get("session_id") or input_data.get("session_id")
    trace_name = config.get("trace_name", "AutoFlow Trace")
    model = input_data.get("model") or config.get("model", "gpt-4o-mini")
    usage = input_data.get("usage", {})
    inp = input_data.get("input", "")
    out = input_data.get("output", "")

    batch = [
        {
            "id": _trace_id(),
            "type": "trace-create",
            "timestamp": now,
            "body": {
                "id": trace_id,
                "name": trace_name,
                "userId": user_id,
                "sessionId": session_id,
                "input": inp,
                "output": out,
                "tags": config.get("tags", []),
                "metadata": input_data.get("metadata", {}),
            },
        },
        {
            "id": _trace_id(),
            "type": "generation-create",
            "timestamp": now,
            "body": {
                "id": generation_id,
                "traceId": trace_id,
                "name": f"{trace_name} - Generation",
                "model": model,
                "input": inp,
                "output": out,
                "usage": usage,
                "startTime": now,
                "endTime": now,
            },
        },
    ]

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{host}/api/public/ingestion", headers=headers, json={"batch": batch})
            r.raise_for_status()
        return {"logged": True, "trace_id": trace_id, "generation_id": generation_id}
    except Exception as e:
        log.warning("langfuse_log_failed", error=str(e))
        return {"logged": False, "error": str(e)}


# ─── analytic.langwatch.log ───────────────────────────────────────────────────

@register_node("analytic.langwatch.log")
async def analytic_langwatch_log(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Log a trace to LangWatch.
    config: api_key, endpoint
    input_data: input, output, model, span_type, thread_id, user_id
    """
    api_key = config.get("api_key") or getattr(settings, "LANGWATCH_API_KEY", "")
    endpoint = (config.get("endpoint") or "https://app.langwatch.ai").rstrip("/")

    if not api_key:
        return {"logged": False, "error": "LANGWATCH_API_KEY required"}

    trace_id = _trace_id()
    span_id = _trace_id()
    now = _now_iso()

    payload = {
        "trace_id": trace_id,
        "spans": [{
            "type": config.get("span_type", "llm"),
            "span_id": span_id,
            "trace_id": trace_id,
            "name": config.get("name", "AutoFlow Span"),
            "input": {"type": "text", "value": input_data.get("input", "")},
            "outputs": [{"type": "text", "value": input_data.get("output", "")}],
            "model": input_data.get("model") or config.get("model"),
            "timestamps": {"started_at": int(time.time() * 1000), "finished_at": int(time.time() * 1000)},
            "params": config.get("params", {}),
        }],
        "thread_id": input_data.get("thread_id") or config.get("thread_id"),
        "user_id": input_data.get("user_id") or config.get("user_id"),
        "metadata": input_data.get("metadata", {}),
    }

    headers = {"X-Auth-Token": api_key, "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{endpoint}/api/collector", headers=headers, json=payload)
            r.raise_for_status()
        return {"logged": True, "trace_id": trace_id}
    except Exception as e:
        log.warning("langwatch_log_failed", error=str(e))
        return {"logged": False, "error": str(e)}


# ─── analytic.arize.log ───────────────────────────────────────────────────────

@register_node("analytic.arize.log")
async def analytic_arize_log(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Log spans to Arize Phoenix OTLP HTTP endpoint.
    config: endpoint (default localhost:6006), api_key, space_id
    input_data: input, output, model, prompt_tokens, completion_tokens
    """
    endpoint = (config.get("endpoint") or getattr(settings, "ARIZE_PHOENIX_ENDPOINT", "http://localhost:6006")).rstrip("/")
    api_key = config.get("api_key") or getattr(settings, "ARIZE_API_KEY", "")
    space_id = config.get("space_id") or getattr(settings, "ARIZE_SPACE_ID", "")

    trace_id = trace_id_hex = uuid.uuid4().hex
    span_id = uuid.uuid4().hex[:16]
    now_ns = int(time.time() * 1e9)

    otlp_body = {
        "resourceSpans": [{
            "resource": {"attributes": [
                {"key": "service.name", "value": {"stringValue": "autoflow"}},
            ]},
            "scopeSpans": [{
                "scope": {"name": "autoflow"},
                "spans": [{
                    "traceId": trace_id_hex,
                    "spanId": span_id,
                    "name": config.get("span_name", "llm"),
                    "kind": 3,
                    "startTimeUnixNano": str(now_ns - 1_000_000),
                    "endTimeUnixNano": str(now_ns),
                    "attributes": [
                        {"key": "llm.model_name", "value": {"stringValue": input_data.get("model", "")}},
                        {"key": "input.value", "value": {"stringValue": str(input_data.get("input", ""))[:2048]}},
                        {"key": "output.value", "value": {"stringValue": str(input_data.get("output", ""))[:2048]}},
                        {"key": "llm.token_count.prompt", "value": {"intValue": input_data.get("prompt_tokens", 0)}},
                        {"key": "llm.token_count.completion", "value": {"intValue": input_data.get("completion_tokens", 0)}},
                    ],
                    "status": {"code": 1},
                }]
            }]
        }]
    }

    headers: dict = {"Content-Type": "application/json"}
    if api_key and space_id:
        headers["api_key"] = api_key
        headers["space_id"] = space_id

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{endpoint}/v1/traces", headers=headers, json=otlp_body)
            r.raise_for_status()
        return {"logged": True, "trace_id": trace_id_hex}
    except Exception as e:
        log.warning("arize_log_failed", error=str(e))
        return {"logged": False, "error": str(e)}


# ─── analytic.lunary.log ──────────────────────────────────────────────────────

@register_node("analytic.lunary.log")
async def analytic_lunary_log(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Log an LLM run event to Lunary.
    config: app_id (public key), api_url
    input_data: run_id, input, output, model, user_id, thread_id
    """
    app_id = config.get("app_id") or getattr(settings, "LUNARY_APP_ID", "")
    api_url = (config.get("api_url") or "https://api.lunary.ai").rstrip("/")

    if not app_id:
        return {"logged": False, "error": "LUNARY_APP_ID required"}

    run_id = input_data.get("run_id") or _trace_id()
    now = _now_iso()

    events = [
        {
            "event": "start",
            "type": "llm",
            "runId": run_id,
            "name": config.get("name", "AutoFlow LLM"),
            "userId": input_data.get("user_id"),
            "threadId": input_data.get("thread_id"),
            "timestamp": now,
            "input": input_data.get("input", ""),
            "extra": {"model": input_data.get("model", ""), **config.get("extra", {})},
            "tags": config.get("tags", []),
            "appId": app_id,
        },
        {
            "event": "end",
            "runId": run_id,
            "output": input_data.get("output", ""),
            "tokensUsage": input_data.get("usage", {}),
            "timestamp": now,
            "appId": app_id,
        },
    ]

    headers = {"Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(f"{api_url}/v1/runs/ingest", headers=headers, json={"events": events})
            r.raise_for_status()
        return {"logged": True, "run_id": run_id}
    except Exception as e:
        log.warning("lunary_log_failed", error=str(e))
        return {"logged": False, "error": str(e)}


# ─── analytic.opik.log ───────────────────────────────────────────────────────

@register_node("analytic.opik.log")
async def analytic_opik_log(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Log a trace to Opik (Comet LLM observability).
    config: api_key, workspace, project_name, api_url
    input_data: input, output, model, tags, metadata
    """
    api_key = config.get("api_key") or getattr(settings, "OPIK_API_KEY", "") or getattr(settings, "COHERE_API_KEY", "")
    workspace = config.get("workspace") or getattr(settings, "OPIK_WORKSPACE", "default")
    project = config.get("project_name", "autoflow")
    api_url = (config.get("api_url") or "https://www.comet.com/opik/api").rstrip("/")

    if not api_key:
        return {"logged": False, "error": "OPIK_API_KEY required"}

    trace_id = _trace_id()
    span_id = _trace_id()
    now = _now_iso()

    headers = {"Authorization": api_key, "Content-Type": "application/json",
               "Comet-Workspace": workspace}

    trace_payload = {
        "id": trace_id,
        "name": config.get("name", "AutoFlow Trace"),
        "project_name": project,
        "input": {"value": input_data.get("input", "")},
        "output": {"value": input_data.get("output", "")},
        "start_time": now,
        "end_time": now,
        "tags": config.get("tags", []),
        "metadata": input_data.get("metadata", {}),
    }

    span_payload = {
        "id": span_id,
        "trace_id": trace_id,
        "parent_span_id": None,
        "name": "llm",
        "type": "llm",
        "input": {"value": input_data.get("input", "")},
        "output": {"value": input_data.get("output", "")},
        "model": input_data.get("model") or config.get("model", ""),
        "start_time": now,
        "end_time": now,
        "usage": input_data.get("usage", {}),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(f"{api_url}/v1/private/traces", headers=headers, json=trace_payload)
            await c.post(f"{api_url}/v1/private/spans", headers=headers, json=span_payload)
        return {"logged": True, "trace_id": trace_id}
    except Exception as e:
        log.warning("opik_log_failed", error=str(e))
        return {"logged": False, "error": str(e)}


# ─── analytic.phoenix.log ─────────────────────────────────────────────────────

@register_node("analytic.phoenix.log")
async def analytic_phoenix_log(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Log spans to Arize Phoenix via OTLP HTTP endpoint (same as arize.log but separate node).
    config: endpoint (http://localhost:6006), api_key
    """
    # Phoenix uses same OTLP endpoint as Arize Phoenix
    return await analytic_arize_log(config, input_data, credential_id, db)


# ─── analytic.log_llm_call ───────────────────────────────────────────────────

@register_node("analytic.log_llm_call")
async def analytic_log_llm_call(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Generic structured LLM call logger — writes to structlog (captured by
    OTEL/Prometheus exporters if configured).
    config: platform (langsmith|langfuse|langwatch|arize|lunary|opik|log), ...
    """
    platform = config.get("platform", "log").lower()

    if platform == "langsmith":
        return await analytic_langsmith_log_run(config, input_data, credential_id, db)
    if platform == "langfuse":
        return await analytic_langfuse_log_trace(config, input_data, credential_id, db)
    if platform == "langwatch":
        return await analytic_langwatch_log(config, input_data, credential_id, db)
    if platform in ("arize", "phoenix"):
        return await analytic_arize_log(config, input_data, credential_id, db)
    if platform == "lunary":
        return await analytic_lunary_log(config, input_data, credential_id, db)
    if platform == "opik":
        return await analytic_opik_log(config, input_data, credential_id, db)

    # Fallback: structured local log
    log.info(
        "llm_call_logged",
        model=input_data.get("model", config.get("model", "")),
        input_preview=str(input_data.get("input", ""))[:200],
        output_preview=str(input_data.get("output", ""))[:200],
        usage=input_data.get("usage", {}),
        tags=config.get("tags", []),
        metadata=input_data.get("metadata", {}),
    )
    return {"logged": True, "platform": "structlog"}
