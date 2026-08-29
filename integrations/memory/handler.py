"""
Memory backend nodes — persistent conversation history stores.

Nodes:
  memory.buffer_window          — keep last N message pairs (in-process)
  memory.summary                — LLM summarizes old messages
  memory.summary_buffer         — hybrid: summary of old + recent window
  memory.dynamodb               — AWS DynamoDB per-session store
  memory.mongodb                — MongoDB collection
  memory.redis                  — Redis list per session
  memory.upstash_redis          — Upstash Redis REST API
  memory.zep                    — Zep memory service
  memory.get                    — retrieve messages for a session
  memory.add                    — add a message to a session
  memory.clear                  — clear a session's history
"""
import json
import time
from collections import defaultdict
from typing import Any

import httpx
import structlog

from core.config import settings
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

# ─── In-process buffer store ─────────────────────────────────────────────────
_SESSIONS: dict[str, list[dict]] = defaultdict(list)


async def _llm_summarize(messages: list[dict], provider: str, model: str) -> str:
    """Summarize a list of messages using an LLM."""
    text = "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in messages)
    prompt = f"Please summarize the following conversation concisely:\n\n{text}\n\nSummary:"
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        return f"[Summary of {len(messages)} messages]"
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.3, "max_tokens": 256},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


# ─── memory.buffer_window ────────────────────────────────────────────────────

@register_node("memory.buffer_window")
async def memory_buffer_window(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Keep the last k message pairs in process memory.
    config: operation (get|add|clear), session_id, k (window size), role, content
    """
    operation = config.get("operation", "get").lower()
    session_id = str(input_data.get("session_id") or config.get("session_id", "default"))
    k = int(config.get("k", 5))

    if operation == "get":
        msgs = _SESSIONS[session_id][-(k * 2):]
        return {"messages": msgs, "session_id": session_id, "count": len(msgs)}

    if operation == "add":
        role = config.get("role", input_data.get("role", "user"))
        content = input_data.get("content") or config.get("content", "")
        _SESSIONS[session_id].append({"role": role, "content": content, "timestamp": time.time()})
        # trim
        if len(_SESSIONS[session_id]) > k * 2 + 10:
            _SESSIONS[session_id] = _SESSIONS[session_id][-(k * 2):]
        return {"added": True, "session_id": session_id, "message_count": len(_SESSIONS[session_id])}

    if operation == "clear":
        count = len(_SESSIONS[session_id])
        _SESSIONS[session_id].clear()
        return {"cleared": count, "session_id": session_id}

    return {"error": f"Unknown operation: {operation}"}


# ─── memory.summary ──────────────────────────────────────────────────────────

@register_node("memory.summary")
async def memory_summary(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Summarization memory: when history grows beyond threshold, LLM summarizes
    the old messages and keeps only the summary.
    config: operation, session_id, threshold, provider, model
    """
    operation = config.get("operation", "get").lower()
    session_id = str(input_data.get("session_id") or config.get("session_id", "default"))
    threshold = int(config.get("threshold", 10))
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")

    # Each session: {"summary": str, "recent": list[dict]}
    store_key = f"_summary_{session_id}"
    if store_key not in _SESSIONS:
        _SESSIONS[store_key] = []  # type: ignore  # reusing as a flag

    # Use a separate dict for summary memories
    _SUMM_STORE: dict = getattr(memory_summary, "_store", {})
    if not hasattr(memory_summary, "_store"):
        memory_summary._store = {}  # type: ignore
    _SUMM_STORE = memory_summary._store  # type: ignore

    if session_id not in _SUMM_STORE:
        _SUMM_STORE[session_id] = {"summary": "", "recent": []}

    state = _SUMM_STORE[session_id]

    if operation == "get":
        context = []
        if state["summary"]:
            context.append({"role": "system", "content": f"[Previous conversation summary: {state['summary']}]"})
        context.extend(state["recent"])
        return {"messages": context, "summary": state["summary"], "session_id": session_id}

    if operation == "add":
        role = config.get("role", input_data.get("role", "user"))
        content = input_data.get("content") or config.get("content", "")
        state["recent"].append({"role": role, "content": content})
        # summarize when threshold exceeded
        if len(state["recent"]) >= threshold:
            to_summarize = state["recent"][: threshold // 2]
            new_summary_text = await _llm_summarize(to_summarize, provider, model)
            if state["summary"]:
                new_summary_text = f"{state['summary']} | {new_summary_text}"
            state["summary"] = new_summary_text
            state["recent"] = state["recent"][threshold // 2:]
        return {"added": True, "session_id": session_id, "summary": state["summary"]}

    if operation == "clear":
        _SUMM_STORE[session_id] = {"summary": "", "recent": []}
        return {"cleared": True, "session_id": session_id}

    return {"error": f"Unknown operation: {operation}"}


# ─── memory.summary_buffer ───────────────────────────────────────────────────

@register_node("memory.summary_buffer")
async def memory_summary_buffer(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Hybrid: keeps a summary of old messages + a fixed recent window.
    config: operation, session_id, max_token_limit (approx chars), k, provider, model
    """
    operation = config.get("operation", "get").lower()
    session_id = str(input_data.get("session_id") or config.get("session_id", "default"))
    k = int(config.get("k", 6))
    max_chars = int(config.get("max_token_limit", 4000)) * 4  # rough: 1 token ≈ 4 chars
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")

    if not hasattr(memory_summary_buffer, "_store"):
        memory_summary_buffer._store = {}  # type: ignore
    store = memory_summary_buffer._store  # type: ignore
    if session_id not in store:
        store[session_id] = {"summary": "", "recent": []}
    state = store[session_id]

    if operation == "get":
        msgs = []
        if state["summary"]:
            msgs.append({"role": "system", "content": f"[Summary: {state['summary']}]"})
        msgs.extend(state["recent"][-k:])
        return {"messages": msgs, "session_id": session_id, "summary": state["summary"]}

    if operation == "add":
        role = config.get("role", input_data.get("role", "user"))
        content = input_data.get("content") or config.get("content", "")
        state["recent"].append({"role": role, "content": content})
        # Check total recent size
        total_chars = sum(len(m["content"]) for m in state["recent"])
        if total_chars > max_chars and len(state["recent"]) > k:
            overflow = state["recent"][: len(state["recent"]) - k]
            new_sum = await _llm_summarize(overflow, provider, model)
            state["summary"] = (f"{state['summary']} {new_sum}").strip() if state["summary"] else new_sum
            state["recent"] = state["recent"][-k:]
        return {"added": True, "session_id": session_id}

    if operation == "clear":
        store[session_id] = {"summary": "", "recent": []}
        return {"cleared": True, "session_id": session_id}

    return {"error": f"Unknown operation: {operation}"}


# ─── memory.dynamodb ─────────────────────────────────────────────────────────

@register_node("memory.dynamodb")
async def memory_dynamodb(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    AWS DynamoDB-backed conversation memory.
    config: operation, table_name, session_id, region, role, content
    AWS creds from environment (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY).
    """
    import asyncio
    operation = config.get("operation", "get").lower()
    table_name = config.get("table_name", "autoflow_memory")
    session_id = str(input_data.get("session_id") or config.get("session_id", "default"))
    region = config.get("region") or settings.AWS_REGION or "us-east-1"

    try:
        import boto3  # type: ignore
    except ImportError:
        raise ImportError("memory.dynamodb requires boto3")

    loop = asyncio.get_event_loop()

    def _ddb_op():
        ddb = boto3.resource("dynamodb", region_name=region,
                             aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
                             aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None)
        table = ddb.Table(table_name)

        if operation == "get":
            resp = table.get_item(Key={"session_id": session_id})
            item = resp.get("Item", {})
            msgs = item.get("messages", [])
            return {"messages": msgs, "session_id": session_id, "count": len(msgs)}

        if operation == "add":
            role = config.get("role", input_data.get("role", "user"))
            content = input_data.get("content") or config.get("content", "")
            resp = table.get_item(Key={"session_id": session_id})
            msgs = resp.get("Item", {}).get("messages", [])
            msgs.append({"role": role, "content": content, "ts": int(time.time())})
            table.put_item(Item={"session_id": session_id, "messages": msgs})
            return {"added": True, "session_id": session_id, "count": len(msgs)}

        if operation == "clear":
            table.delete_item(Key={"session_id": session_id})
            return {"cleared": True, "session_id": session_id}

        return {"error": f"Unknown operation: {operation}"}

    return await loop.run_in_executor(None, _ddb_op)


# ─── memory.mongodb ──────────────────────────────────────────────────────────

@register_node("memory.mongodb")
async def memory_mongodb(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    MongoDB-backed conversation memory using motor (async MongoDB driver).
    config: operation, mongo_url, database, collection, session_id, role, content
    """
    try:
        from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
    except ImportError:
        raise ImportError("memory.mongodb requires motor: pip install motor")

    operation = config.get("operation", "get").lower()
    mongo_url = config.get("mongo_url") or getattr(settings, "MONGODB_URL", "mongodb://localhost:27017")
    database = config.get("database", "autoflow")
    collection_name = config.get("collection", "memory")
    session_id = str(input_data.get("session_id") or config.get("session_id", "default"))

    client = AsyncIOMotorClient(mongo_url)
    coll = client[database][collection_name]

    try:
        if operation == "get":
            doc = await coll.find_one({"session_id": session_id})
            msgs = doc.get("messages", []) if doc else []
            return {"messages": msgs, "session_id": session_id, "count": len(msgs)}

        if operation == "add":
            role = config.get("role", input_data.get("role", "user"))
            content = input_data.get("content") or config.get("content", "")
            await coll.update_one(
                {"session_id": session_id},
                {"$push": {"messages": {"role": role, "content": content, "ts": int(time.time())}}},
                upsert=True,
            )
            doc = await coll.find_one({"session_id": session_id})
            return {"added": True, "session_id": session_id, "count": len(doc.get("messages", []))}

        if operation == "clear":
            await coll.delete_one({"session_id": session_id})
            return {"cleared": True, "session_id": session_id}

        return {"error": f"Unknown operation: {operation}"}
    finally:
        client.close()


# ─── memory.redis ────────────────────────────────────────────────────────────

@register_node("memory.redis")
async def memory_redis(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Redis-backed conversation memory — messages stored as a JSON list under a key.
    config: operation, redis_url, session_id, role, content, max_messages, ttl_seconds
    """
    try:
        import redis.asyncio as aioredis  # type: ignore
    except ImportError:
        raise ImportError("memory.redis requires redis: pip install redis")

    operation = config.get("operation", "get").lower()
    redis_url = config.get("redis_url") or settings.REDIS_URL or "redis://localhost:6379/0"
    session_id = str(input_data.get("session_id") or config.get("session_id", "default"))
    redis_key = f"autoflow:memory:{session_id}"
    max_msgs = int(config.get("max_messages", 50))
    ttl = int(config.get("ttl_seconds", 86400))

    client = aioredis.from_url(redis_url, decode_responses=True)
    try:
        if operation == "get":
            raw = await client.get(redis_key)
            msgs = json.loads(raw) if raw else []
            return {"messages": msgs, "session_id": session_id, "count": len(msgs)}

        if operation == "add":
            role = config.get("role", input_data.get("role", "user"))
            content = input_data.get("content") or config.get("content", "")
            raw = await client.get(redis_key)
            msgs = json.loads(raw) if raw else []
            msgs.append({"role": role, "content": content, "ts": int(time.time())})
            if len(msgs) > max_msgs:
                msgs = msgs[-max_msgs:]
            await client.setex(redis_key, ttl, json.dumps(msgs))
            return {"added": True, "session_id": session_id, "count": len(msgs)}

        if operation == "clear":
            await client.delete(redis_key)
            return {"cleared": True, "session_id": session_id}

        return {"error": f"Unknown operation: {operation}"}
    finally:
        await client.aclose()


# ─── memory.upstash_redis ─────────────────────────────────────────────────────

@register_node("memory.upstash_redis")
async def memory_upstash_redis(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Upstash Redis REST API-backed memory — no redis-py required.
    config: operation, upstash_url, upstash_token, session_id, role, content, max_messages
    """
    operation = config.get("operation", "get").lower()
    upstash_url = config.get("upstash_url") or getattr(settings, "UPSTASH_REDIS_REST_URL", "")
    upstash_token = config.get("upstash_token") or getattr(settings, "UPSTASH_REDIS_REST_TOKEN", "")
    session_id = str(input_data.get("session_id") or config.get("session_id", "default"))
    redis_key = f"autoflow:memory:{session_id}"
    max_msgs = int(config.get("max_messages", 50))
    ttl = int(config.get("ttl_seconds", 86400))

    if not upstash_url or not upstash_token:
        raise ValueError("memory.upstash_redis requires upstash_url and upstash_token")

    headers = {"Authorization": f"Bearer {upstash_token}"}

    async with httpx.AsyncClient(timeout=15) as c:
        if operation == "get":
            r = await c.get(f"{upstash_url}/get/{redis_key}", headers=headers)
            r.raise_for_status()
            raw = r.json().get("result")
            msgs = json.loads(raw) if raw else []
            return {"messages": msgs, "session_id": session_id, "count": len(msgs)}

        if operation == "add":
            role = config.get("role", input_data.get("role", "user"))
            content = input_data.get("content") or config.get("content", "")
            # Get existing
            r = await c.get(f"{upstash_url}/get/{redis_key}", headers=headers)
            raw = r.json().get("result")
            msgs = json.loads(raw) if raw else []
            msgs.append({"role": role, "content": content, "ts": int(time.time())})
            if len(msgs) > max_msgs:
                msgs = msgs[-max_msgs:]
            encoded = json.dumps(msgs)
            r = await c.get(f"{upstash_url}/setex/{redis_key}/{ttl}/{encoded}", headers=headers)
            r.raise_for_status()
            return {"added": True, "session_id": session_id, "count": len(msgs)}

        if operation == "clear":
            r = await c.get(f"{upstash_url}/del/{redis_key}", headers=headers)
            return {"cleared": True, "session_id": session_id}

    return {"error": f"Unknown operation: {operation}"}


# ─── memory.zep ──────────────────────────────────────────────────────────────

@register_node("memory.zep")
async def memory_zep(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Zep memory service — long-term conversational memory with semantic search.
    config: operation, zep_url, api_key, session_id, role, content
    """
    operation = config.get("operation", "get").lower()
    zep_url = (config.get("zep_url") or getattr(settings, "ZEP_URL", "http://localhost:8000")).rstrip("/")
    api_key = config.get("api_key") or getattr(settings, "ZEP_API_KEY", "")
    session_id = str(input_data.get("session_id") or config.get("session_id", "default"))
    last_n = int(config.get("last_n", 20))

    headers: dict = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=15) as c:
        if operation == "get":
            r = await c.get(f"{zep_url}/api/v1/session/{session_id}/memory", headers=headers,
                            params={"lastn": last_n})
            if r.status_code == 404:
                return {"messages": [], "session_id": session_id, "summary": ""}
            r.raise_for_status()
            data = r.json()
            msgs = [{"role": m.get("role", ""), "content": m.get("content", "")}
                    for m in data.get("messages", [])]
            return {"messages": msgs, "summary": data.get("summary", {}).get("content", ""), "session_id": session_id}

        if operation == "add":
            role = config.get("role", input_data.get("role", "user"))
            content = input_data.get("content") or config.get("content", "")
            # Ensure session exists
            await c.post(f"{zep_url}/api/v1/session", headers=headers,
                         json={"session_id": session_id})
            r = await c.post(f"{zep_url}/api/v1/session/{session_id}/memory", headers=headers,
                             json={"messages": [{"role": role, "content": content}]})
            r.raise_for_status()
            return {"added": True, "session_id": session_id}

        if operation == "search":
            query = input_data.get("query") or config.get("query", "")
            r = await c.post(f"{zep_url}/api/v1/session/{session_id}/search", headers=headers,
                             json={"text": query, "limit": int(config.get("limit", 5))})
            if r.status_code == 404:
                return {"results": [], "session_id": session_id}
            r.raise_for_status()
            results = r.json().get("results", [])
            return {"results": results, "session_id": session_id}

        if operation == "clear":
            r = await c.delete(f"{zep_url}/api/v1/session/{session_id}/memory", headers=headers)
            return {"cleared": True, "session_id": session_id}

    return {"error": f"Unknown operation: {operation}"}


# ─── memory.get / memory.add / memory.clear ─────────────────────────────────

@register_node("memory.get")
async def memory_get(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    session_id = str(input_data.get("session_id") or config.get("session_id", "default"))
    k = int(config.get("k", 20))
    msgs = _SESSIONS[session_id][-k:]
    return {"messages": msgs, "session_id": session_id, "count": len(msgs)}


@register_node("memory.add")
async def memory_add(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    session_id = str(input_data.get("session_id") or config.get("session_id", "default"))
    role = config.get("role", input_data.get("role", "user"))
    content = input_data.get("content") or config.get("content", "")
    _SESSIONS[session_id].append({"role": role, "content": content, "ts": int(time.time())})
    return {"added": True, "session_id": session_id, "count": len(_SESSIONS[session_id])}


@register_node("memory.clear")
async def memory_clear_node(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    session_id = str(input_data.get("session_id") or config.get("session_id", "default"))
    count = len(_SESSIONS[session_id])
    _SESSIONS[session_id].clear()
    return {"cleared": count, "session_id": session_id}


# ─── memory.agent ────────────────────────────────────────────────────────────

@register_node("memory.agent")
async def memory_agent(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Agent Memory: stores and retrieves multi-turn conversation history for agents.
    Provides an agent-optimized interface with system message injection.

    config:
      - operation: get | add | clear | get_with_system (default: get)
      - session_id: unique conversation identifier
      - role: message role (user/assistant/system) — for add
      - content: message content — for add
      - system_prompt: system prompt to prepend — for get_with_system
      - k: max history messages to retrieve (default: 20)
    """
    session_id = str(input_data.get("session_id") or config.get("session_id", "default"))
    operation = config.get("operation", input_data.get("operation", "get"))
    k = int(config.get("k", 20))

    if operation in ("get", "get_with_system"):
        msgs = _SESSIONS[session_id][-k:]
        result = {"messages": msgs, "session_id": session_id, "count": len(msgs)}

        if operation == "get_with_system":
            system_prompt = config.get("system_prompt", "You are a helpful assistant.")
            full_messages = [{"role": "system", "content": system_prompt}] + msgs
            result["full_messages"] = full_messages

        return result

    elif operation == "add":
        role = config.get("role", input_data.get("role", "user"))
        content = input_data.get("content") or config.get("content", "")
        _SESSIONS[session_id].append({"role": role, "content": content, "ts": int(time.time())})
        return {"added": True, "session_id": session_id, "role": role, "count": len(_SESSIONS[session_id])}

    elif operation == "clear":
        count = len(_SESSIONS[session_id])
        _SESSIONS[session_id].clear()
        return {"cleared": count, "session_id": session_id}

    return {"error": f"Unknown operation: {operation}"}


# ─── memory.mem0 ─────────────────────────────────────────────────────────────

@register_node("memory.mem0")
async def memory_mem0(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Mem0 Memory: persistent, AI-powered memory using the Mem0 cloud service.
    Mem0 automatically extracts and stores relevant facts from conversations.

    config:
      - operation: add | search | get_all | delete (default: search)
      - user_id: user identifier for memory isolation
      - messages: list of {role, content} messages to add — for add
      - query: search query — for search
      - memory_id: memory ID — for delete
    """
    from core.config import settings

    api_key = getattr(settings, "MEM0_API_KEY", None)
    if not api_key:
        raise ValueError("memory.mem0 requires MEM0_API_KEY")

    operation = config.get("operation", input_data.get("operation", "search"))
    user_id = config.get("user_id") or input_data.get("user_id", "default")
    headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=30) as client:
        if operation == "add":
            messages = config.get("messages") or input_data.get("messages", [])
            if not messages:
                # Build from single content
                content = input_data.get("content") or config.get("content", "")
                role = input_data.get("role", "user")
                messages = [{"role": role, "content": content}]
            r = await client.post(
                "https://api.mem0.ai/v1/memories/",
                json={"messages": messages, "user_id": user_id},
                headers=headers,
            )
            r.raise_for_status()
            return {"added": True, "memories": r.json(), "user_id": user_id}

        elif operation == "search":
            query = config.get("query") or input_data.get("query") or input_data.get("input", "")
            r = await client.post(
                "https://api.mem0.ai/v1/memories/search/",
                json={"query": query, "user_id": user_id},
                headers=headers,
            )
            r.raise_for_status()
            results = r.json()
            return {"memories": results, "query": query, "user_id": user_id, "count": len(results)}

        elif operation == "get_all":
            r = await client.get(
                "https://api.mem0.ai/v1/memories/",
                params={"user_id": user_id},
                headers=headers,
            )
            r.raise_for_status()
            memories = r.json()
            return {"memories": memories, "user_id": user_id, "count": len(memories)}

        elif operation == "delete":
            memory_id = config.get("memory_id") or input_data.get("memory_id", "")
            r = await client.delete(f"https://api.mem0.ai/v1/memories/{memory_id}/", headers=headers)
            r.raise_for_status()
            return {"deleted": True, "memory_id": memory_id}

    return {"error": f"Unknown operation: {operation}"}


# ─── memory.zep_cloud ────────────────────────────────────────────────────────

@register_node("memory.zep_cloud")
async def memory_zep_cloud(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Zep Cloud Memory: persistent conversational memory using Zep Cloud.
    Zep provides semantic search, entity extraction, and memory synthesis.

    config:
      - operation: add | get | search | delete_session (default: get)
      - session_id: Zep session identifier
      - role: message role — for add
      - content: message content — for add
      - query: search query — for search
      - limit: max results (default: 10)
    """
    from core.config import settings

    api_key = getattr(settings, "ZEP_CLOUD_API_KEY", None)
    if not api_key:
        raise ValueError("memory.zep_cloud requires ZEP_CLOUD_API_KEY")

    session_id = str(input_data.get("session_id") or config.get("session_id", "default"))
    operation = config.get("operation", input_data.get("operation", "get"))
    headers = {"Authorization": f"Api-Key {api_key}", "Content-Type": "application/json"}
    base_url = "https://api.getzep.com/api/v2"

    async with httpx.AsyncClient(timeout=30) as client:
        if operation == "add":
            role = config.get("role", input_data.get("role", "user"))
            content = input_data.get("content") or config.get("content", "")
            role_type = "user" if role == "user" else "assistant"
            r = await client.post(
                f"{base_url}/sessions/{session_id}/messages",
                json={"messages": [{"role": role_type, "role_label": role, "content": content}]},
                headers=headers,
            )
            if r.status_code == 404:
                # Create session first
                await client.post(f"{base_url}/sessions", json={"session_id": session_id}, headers=headers)
                r = await client.post(
                    f"{base_url}/sessions/{session_id}/messages",
                    json={"messages": [{"role": role_type, "role_label": role, "content": content}]},
                    headers=headers,
                )
            r.raise_for_status()
            return {"added": True, "session_id": session_id}

        elif operation == "get":
            limit = int(config.get("limit", 10))
            r = await client.get(
                f"{base_url}/sessions/{session_id}/memory",
                params={"lastn": limit},
                headers=headers,
            )
            if r.status_code == 404:
                return {"messages": [], "session_id": session_id, "count": 0}
            r.raise_for_status()
            data = r.json()
            messages = data.get("messages", [])
            return {"messages": messages, "session_id": session_id, "count": len(messages), "summary": data.get("summary")}

        elif operation == "search":
            query = config.get("query") or input_data.get("query") or input_data.get("input", "")
            limit = int(config.get("limit", 10))
            r = await client.post(
                f"{base_url}/sessions/{session_id}/search",
                json={"text": query, "limit": limit},
                headers=headers,
            )
            r.raise_for_status()
            results = r.json().get("results", [])
            return {"results": results, "query": query, "session_id": session_id, "count": len(results)}

        elif operation == "delete_session":
            r = await client.delete(f"{base_url}/sessions/{session_id}", headers=headers)
            return {"deleted": r.status_code in (200, 204), "session_id": session_id}

    return {"error": f"Unknown operation: {operation}"}
