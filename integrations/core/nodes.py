"""
Core nodes — production version.

Changes vs previous version:
  - core.condition  → emits branch: "true"|"false" (engine routes downstream)
  - core.split_in_batches → emits items list; engine drives loop via LOOP_ITEM edges
  - core.foreach    → alias for split_in_batches (one item per iteration)
  - core.switch     → multi-way branch (branch: "case_0" | "case_1" | "default")
  - core.human_approval → handled by engine; node just declares intent
  - core.error_handler  → catches errors from upstream, normalizes payload
  - core.wait_for_webhook → suspends until a matching inbound webhook arrives
  - All config values support {{ expr }} interpolation (resolved by engine)
"""
import asyncio
import json
import re
import smtplib
import xmltodict
from datetime import datetime
from email.mime.text import MIMEText

import arrow
import httpx
import structlog

from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)


# ─── HTTP ──────────────────────────────────────────────────────────────────────

@register_node("http.request")
async def http_request(config: dict, input_data: dict, credential_id: str, db) -> dict:
    method = (config.get("method") or input_data.get("method", "GET")).upper()
    url = config.get("url") or input_data.get("url")
    if not url:
        raise ValueError("http.request: 'url' is required")

    from core.ssrf_guard import assert_safe_url, SSRFSafeTransport
    assert_safe_url(url)

    headers = dict(config.get("headers") or input_data.get("headers") or {})
    params = config.get("params") or input_data.get("params") or {}
    body = config.get("body") or input_data.get("body")
    timeout = float(config.get("timeout", 30))
    follow_redirects = config.get("follow_redirects", True)

    auth = config.get("auth")
    if auth:
        if auth.get("type") == "bearer":
            headers["Authorization"] = f"Bearer {auth['token']}"
        elif auth.get("type") == "basic":
            import base64
            creds = base64.b64encode(
                f"{auth['username']}:{auth['password']}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {creds}"

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=follow_redirects,
        transport=SSRFSafeTransport(),
    ) as client:
        kwargs: dict = {"headers": headers, "params": params}
        if isinstance(body, dict):
            kwargs["json"] = body
        elif isinstance(body, str):
            kwargs["content"] = body.encode()
        r = await client.request(method, url, **kwargs)

    try:
        response_body = r.json()
    except Exception:
        response_body = r.text

    if config.get("raise_for_status", False):
        r.raise_for_status()

    return {
        "status_code": r.status_code,
        "headers": dict(r.headers),
        "body": response_body,
        "ok": r.is_success,
        "url": str(r.url),
    }


# ─── Condition / Branching ─────────────────────────────────────────────────────

@register_node("core.condition")
async def core_condition(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Evaluates ONE condition. Downstream nodes connected via edge label
    "true" or "false" are routed accordingly by the execution engine.
    """
    conditions = config.get("conditions") or [config]  # support multi-condition OR/AND

    logic = config.get("logic", "AND").upper()  # AND | OR
    results = []
    for cond in conditions:
        results.append(_eval_condition(cond, input_data))

    if logic == "OR":
        overall = any(results)
    else:
        overall = all(results)

    return {
        **input_data,
        "condition_result": overall,
        "branch": "true" if overall else "false",
    }


def _eval_condition(cond: dict, data: dict) -> bool:
    field = cond.get("field")
    operator = cond.get("operator", "equals")
    value = cond.get("value")

    # Support nested field paths: "user.age"
    item_val = _deep_get(data, field.split(".")) if field else None

    if operator == "equals":
        return item_val == value
    if operator == "not_equals":
        return item_val != value
    if operator == "contains":
        return str(value) in str(item_val or "")
    if operator == "not_contains":
        return str(value) not in str(item_val or "")
    if operator == "greater_than":
        return float(item_val or 0) > float(value)
    if operator == "less_than":
        return float(item_val or 0) < float(value)
    if operator == "greater_than_or_equal":
        return float(item_val or 0) >= float(value)
    if operator == "less_than_or_equal":
        return float(item_val or 0) <= float(value)
    if operator == "is_empty":
        return not item_val
    if operator == "is_not_empty":
        return bool(item_val)
    if operator == "is_true":
        return bool(item_val)
    if operator == "is_false":
        return not bool(item_val)
    if operator == "regex":
        return bool(re.search(str(value), str(item_val or "")))
    if operator == "in":
        return item_val in (value if isinstance(value, list) else [value])
    if operator == "not_in":
        return item_val not in (value if isinstance(value, list) else [value])
    return True


def _deep_get(obj, keys):
    for k in keys:
        if isinstance(obj, dict):
            obj = obj.get(k)
        else:
            return None
    return obj


# ─── Switch (multi-way branch) ─────────────────────────────────────────────────

@register_node("core.switch")
async def core_switch(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Evaluates multiple cases in order; first match wins.
    Edge labels should be "case_0", "case_1", ..., "default".
    """
    cases = config.get("cases", [])
    field = config.get("field")
    subject = _deep_get(input_data, field.split(".")) if field else input_data

    for idx, case in enumerate(cases):
        if _eval_condition({**case, "field": None}, {"__subject__": subject}):
            return {**input_data, "branch": f"case_{idx}", "matched_case": case.get("label", f"case_{idx}")}

    return {**input_data, "branch": "default", "matched_case": "default"}


# ─── Split / Loop ──────────────────────────────────────────────────────────────

@register_node("core.split_in_batches")
async def core_split_in_batches(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Splits a list into batches. The execution engine drives iteration:
    connect downstream nodes with edge label "loop_item" to iterate per batch.
    """
    items = config.get("items") or input_data.get("items", [])
    batch_size = int(config.get("batch_size", 1))

    if not isinstance(items, list):
        items = [items]

    batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
    return {
        "items": batches if batch_size > 1 else items,
        "batches": batches,
        "total": len(items),
        "batch_count": len(batches),
    }


@register_node("core.foreach")
async def core_foreach(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Alias for split_in_batches with batch_size=1 (one item per iteration)."""
    items = config.get("items") or input_data.get("items", [])
    if not isinstance(items, list):
        items = [items]
    return {
        "items": items,
        "batches": [[item] for item in items],
        "total": len(items),
        "batch_count": len(items),
    }


# ─── Filter ───────────────────────────────────────────────────────────────────

@register_node("core.filter")
async def core_filter(config: dict, input_data: dict, credential_id: str, db) -> dict:
    items = config.get("items") or input_data.get("items", [])
    if not isinstance(items, list):
        items = [items]

    conditions = config.get("conditions") or [config]
    logic = config.get("logic", "AND").upper()

    def match(item):
        results = [_eval_condition(cond, item if isinstance(item, dict) else {"value": item})
                   for cond in conditions]
        return any(results) if logic == "OR" else all(results)

    filtered = [i for i in items if match(i)]
    return {"items": filtered, "count": len(filtered), "original_count": len(items)}


# ─── Transform ────────────────────────────────────────────────────────────────

@register_node("core.transform")
async def core_transform(config: dict, input_data: dict, credential_id: str, db) -> dict:
    mapping = config.get("mapping") or {}
    output = {}
    for out_key, expr in mapping.items():
        if isinstance(expr, str):
            # Simple dot-path resolution without full interpolation
            # (engine already resolved {{ }} in config before calling)
            output[out_key] = expr
        else:
            output[out_key] = expr
    return output


# ─── Set Variables ─────────────────────────────────────────────────────────────

@register_node("core.set_variables")
async def core_set_variables(config: dict, input_data: dict, credential_id: str, db) -> dict:
    variables = config.get("variables") or {}
    # Engine picks this up and stores in ctx.vars
    return {**input_data, **variables}


# ─── Merge ────────────────────────────────────────────────────────────────────

@register_node("core.merge")
async def core_merge(config: dict, input_data: dict, credential_id: str, db) -> dict:
    mode = config.get("mode", "merge")
    inputs = config.get("inputs") or [input_data]

    if mode == "merge":
        result: dict = {}
        for inp in inputs:
            if isinstance(inp, dict):
                result.update(inp)
        return result
    elif mode == "append":
        all_items = []
        for inp in inputs:
            items = inp.get("items", [inp]) if isinstance(inp, dict) else [inp]
            all_items.extend(items)
        return {"items": all_items}
    elif mode == "zip":
        lists = [inp.get("items", []) if isinstance(inp, dict) else [] for inp in inputs]
        zipped = [dict(enumerate(row)) for row in zip(*lists)]
        return {"items": zipped}
    return input_data


# ─── Delay ────────────────────────────────────────────────────────────────────

@register_node("core.delay")
async def core_delay(config: dict, input_data: dict, credential_id: str, db) -> dict:
    seconds = float(config.get("seconds") or input_data.get("seconds", 1))
    await asyncio.sleep(seconds)
    return input_data


# ─── Human Approval ────────────────────────────────────────────────────────────

@register_node("core.human_approval")
async def core_human_approval(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Handled by the execution engine directly (_handle_human_approval).
    This stub exists so NODE_HANDLERS contains the key.
    """
    raise RuntimeError("core.human_approval must be handled by the execution engine")


# ─── Error Handler ─────────────────────────────────────────────────────────────

@register_node("core.error_handler")
async def core_error_handler(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Receives error context from an upstream node via an error-branch edge.
    Normalizes and optionally sends an alert.
    """
    error_message = input_data.get("__error__") or input_data.get("error", "Unknown error")
    node_id = input_data.get("__error_node__", "unknown")
    timestamp = datetime.utcnow().isoformat()

    notify_email = config.get("notify_email")
    if notify_email:
        # Best-effort notification; don't let this fail the handler
        try:
            from core.nodes import core_send_email_smtp  # type: ignore
            await core_send_email_smtp(
                config={
                    "to": notify_email,
                    "subject": f"[AutoFlow] Node {node_id} failed",
                    "body": f"Error at {timestamp}:\n{error_message}",
                },
                input_data={},
                credential_id=None,
                db=db,
            )
        except Exception as mail_exc:
            log.warning("error_handler_notify_failed", exc=str(mail_exc))

    return {
        "handled": True,
        "error_message": error_message,
        "failed_node": node_id,
        "timestamp": timestamp,
        "branch": "true",  # allow downstream success routing
    }


# ─── Run Code ─────────────────────────────────────────────────────────────────

@register_node("core.run_code")
async def core_run_code(config: dict, input_data: dict, credential_id: str, db) -> dict:
    from core.sandbox import run_sandboxed
    code = config.get("code", "")
    return await run_sandboxed(code, input_data)


# ─── Email ────────────────────────────────────────────────────────────────────

@register_node("core.send_email_smtp")
async def core_send_email_smtp(config: dict, input_data: dict, credential_id: str, db) -> dict:
    to = config.get("to") or input_data.get("to")
    subject = config.get("subject") or input_data.get("subject", "")
    body = config.get("body") or input_data.get("body", "")
    is_html = config.get("html", False)

    msg = MIMEText(body, "html" if is_html else "plain")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_USERNAME
    msg["To"] = to

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_smtp, msg)
    return {"ok": True, "to": to, "subject": subject}


def _send_smtp(msg):
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(msg)


# ─── Utilities ─────────────────────────────────────────────────────────────────

@register_node("core.format_date")
async def core_format_date(config: dict, input_data: dict, credential_id: str, db) -> dict:
    date_value = config.get("date") or input_data.get("date") or input_data.get("timestamp")
    output_format = config.get("output_format", "YYYY-MM-DD HH:mm:ss")
    input_tz = config.get("input_timezone", "UTC")
    output_tz = config.get("output_timezone", "UTC")

    dt = arrow.get(date_value).to(input_tz).to(output_tz)
    return {
        "formatted": dt.format(output_format),
        "iso": dt.isoformat(),
        "timestamp": dt.timestamp(),
        "date": dt.date().isoformat(),
        "time": dt.time().isoformat(),
    }


@register_node("core.json_parse")
async def core_json_parse(config: dict, input_data: dict, credential_id: str, db) -> dict:
    raw = config.get("json_string") or input_data.get("json_string") or input_data.get("body")
    if isinstance(raw, (dict, list)):
        return {"parsed": raw}
    try:
        return {"parsed": json.loads(raw)}
    except Exception as e:
        return {"parsed": None, "error": str(e)}


@register_node("core.xml_parse")
async def core_xml_parse(config: dict, input_data: dict, credential_id: str, db) -> dict:
    raw = config.get("xml_string") or input_data.get("xml_string") or input_data.get("body", "")
    try:
        return {"parsed": xmltodict.parse(raw)}
    except Exception as e:
        return {"parsed": None, "error": str(e)}


@register_node("core.respond_to_webhook")
async def core_respond_to_webhook(config: dict, input_data: dict, credential_id: str, db) -> dict:
    status_code = config.get("status_code", 200)
    response_body = config.get("body") or input_data.get("response_body", {"ok": True})
    return {"__webhook_response__": True, "status_code": status_code, "body": response_body}


@register_node("core.aggregate")
async def core_aggregate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Aggregate loop_results from a preceding loop node."""
    loop_results = input_data.get("loop_results") or []
    operation = config.get("operation", "collect")  # collect | sum_field | avg_field | count
    field = config.get("field")

    if operation == "collect":
        return {"items": loop_results, "count": len(loop_results)}
    if operation == "count":
        return {"count": len(loop_results)}
    if field and operation == "sum_field":
        total = sum(float(r.get(field, 0) or 0) for r in loop_results if isinstance(r, dict))
        return {"sum": total, "field": field}
    if field and operation == "avg_field":
        values = [float(r.get(field, 0) or 0) for r in loop_results if isinstance(r, dict)]
        avg = sum(values) / len(values) if values else 0
        return {"avg": avg, "count": len(values), "field": field}
    return {"items": loop_results}


@register_node("approval.wait")
async def approval_wait(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Human-in-the-loop. Creates a pending Approval and PAUSES the whole
    execution (not just this node) by raising ExecutionPaused, which
    core/execution_engine.py's main loop catches specially — the
    execution is left in `waiting` status, not failed. A human decides
    via POST /api/approvals/{id}/decide (api/routes/approvals.py), which
    resumes the SAME execution from exactly this point rather than
    starting over (see execute_workflow's resume-from-waiting handling).
    """
    from datetime import timedelta
    from core.execution_engine import ExecutionPaused
    from storage.models import Approval

    execution_id = config.get("_execution_id")
    node_id = config.get("_node_id")
    prompt = config.get("prompt") or input_data.get("prompt") or "Approval requested"
    payload = config.get("payload") or input_data
    timeout_hours = config.get("timeout_hours")

    approval = Approval(
        execution_id=execution_id,
        node_id=node_id,
        status="pending",
        prompt=prompt,
        payload=payload,
        expires_at=(datetime.utcnow() + timedelta(hours=float(timeout_hours))) if timeout_hours else None,
    )
    db.add(approval)
    await db.flush()

    raise ExecutionPaused(approval_id=approval.id, node_id=node_id)