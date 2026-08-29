"""
Agentflow nodes — high-level orchestration primitives that mirror Flowise's
agentflow category. These nodes handle conditional routing, direct replies,
sub-flow execution, retrieval, and tool invocation within agent flows.
"""
import asyncio
import json
import re

import httpx
import structlog

from core.execution_engine import register_node, NODE_HANDLERS
from core.config import settings

log = structlog.get_logger(__name__)


def _render(template: str, data: dict) -> str:
    if not isinstance(template, str):
        return template

    def repl(m):
        path = m.group(1).strip().split(".")
        val = data
        for p in path:
            val = val.get(p) if isinstance(val, dict) else None
        return "" if val is None else (val if isinstance(val, str) else json.dumps(val))

    return re.sub(r"\{\{\s*([\w\.]+)\s*\}\}", repl, template)


async def _call_llm(provider: str, model: str, system: str, prompt: str, max_tokens: int = 512) -> str:
    """Minimal LLM caller supporting openai and anthropic."""
    if provider == "anthropic":
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY required")
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                json={
                    "model": model or "claude-3-5-haiku-20241022",
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            r.raise_for_status()
            return r.json()["content"][0]["text"]
    else:
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("OPENAI_API_KEY required")
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model or "gpt-4o-mini",
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]


# ─── ConditionAgent ────────────────────────────────────────────────────────────

@register_node("agentflow.condition_agent")
async def agentflow_condition_agent(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    ConditionAgent: uses an LLM to evaluate a natural-language condition and
    routes the flow. Returns branch="true" or branch="false" for downstream routing.

    config:
      - condition: natural-language condition to evaluate (supports {{ }} templates)
      - provider: openai | anthropic (default: openai)
      - model: LLM model
      - context_fields: list of input_data keys to include as context
    """
    condition = _render(config.get("condition", "Is the input suitable?"), input_data)
    provider = config.get("provider", "openai")
    model = config.get("model", "")
    context_fields = config.get("context_fields") or []

    context_parts = []
    if context_fields:
        for field in context_fields:
            val = input_data.get(field)
            if val is not None:
                context_parts.append(f"{field}: {val}")
    else:
        # Include all input data as context
        for k, v in input_data.items():
            if not k.startswith("_"):
                context_parts.append(f"{k}: {json.dumps(v) if not isinstance(v, str) else v}")

    context_str = "\n".join(context_parts) if context_parts else json.dumps(input_data)

    system = (
        "You are a condition evaluator. Given a condition and context, answer ONLY 'YES' or 'NO'. "
        "No explanation, no punctuation — just YES or NO."
    )
    prompt = f"Condition: {condition}\n\nContext:\n{context_str}\n\nAnswer (YES or NO):"

    response = await _call_llm(provider, model, system, prompt, 10)
    answer = response.strip().upper()
    result = "true" if "YES" in answer else "false"

    return {
        **input_data,
        "condition": condition,
        "condition_result": result == "true",
        "branch": result,
        "llm_answer": response.strip(),
    }


# ─── DirectReply ───────────────────────────────────────────────────────────────

@register_node("agentflow.direct_reply")
async def agentflow_direct_reply(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    DirectReply: immediately returns a configured message as the final output
    of the agentflow. Optionally formats the response.

    config:
      - message: the reply text (supports {{ }} template interpolation)
      - format: text | json | markdown (default: text)
      - include_input: whether to include input_data in the response (default: False)
    """
    message = _render(config.get("message", ""), input_data)
    fmt = config.get("format", "text")
    include_input = config.get("include_input", False)

    if fmt == "json":
        try:
            parsed = json.loads(message)
            output = parsed
        except (json.JSONDecodeError, ValueError):
            output = {"message": message}
    else:
        output = message

    result = {
        "reply": output,
        "format": fmt,
        "is_final": True,
    }

    if include_input:
        result["input"] = input_data

    return result


# ─── ExecuteFlow ──────────────────────────────────────────────────────────────

@register_node("agentflow.execute_flow")
async def agentflow_execute_flow(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    ExecuteFlow: executes another workflow by ID as a sub-flow.
    Passes mapped inputs and returns the sub-flow's output.

    config:
      - workflow_id: UUID of the workflow to execute
      - input_mapping: dict mapping sub-flow input keys to values or {{ templates }}
      - wait_for_completion: bool (default True)
      - timeout: seconds to wait (default 60)
    """
    workflow_id = config.get("workflow_id") or input_data.get("workflow_id")
    if not workflow_id:
        raise ValueError("agentflow.execute_flow requires 'workflow_id'")

    input_mapping = config.get("input_mapping") or {}
    wait = config.get("wait_for_completion", True)
    timeout = float(config.get("timeout", 60))

    # Build sub-flow inputs
    sub_inputs = {}
    for key, template in input_mapping.items():
        sub_inputs[key] = _render(str(template), input_data) if isinstance(template, str) else template

    # If no mapping, pass full input_data
    if not sub_inputs:
        sub_inputs = {k: v for k, v in input_data.items() if not k.startswith("_")}

    # Call the execution engine directly if available
    try:
        from core.execution_engine import ExecutionEngine
        from storage.database import async_session_maker

        async with async_session_maker() as session:
            engine = ExecutionEngine(db=session)
            # Load workflow definition
            from sqlalchemy import select
            from storage.models import Workflow
            result = await session.execute(
                select(Workflow).where(Workflow.id == workflow_id)
            )
            workflow = result.scalar_one_or_none()
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")

            execution_result = await asyncio.wait_for(
                engine.execute(workflow.definition, sub_inputs),
                timeout=timeout,
            )
        return {
            "workflow_id": workflow_id,
            "result": execution_result,
            "status": "completed",
        }
    except ImportError:
        pass
    except Exception as e:
        log.warning("execute_flow_failed", workflow_id=workflow_id, error=str(e))
        return {
            "workflow_id": workflow_id,
            "result": None,
            "status": "error",
            "error": str(e),
        }

    # Fallback: call via internal API
    base_url = settings.APP_BASE_URL or "http://localhost:8000"
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            f"{base_url}/api/workflows/{workflow_id}/execute",
            json={"input": sub_inputs},
        )
        if r.is_success:
            return {"workflow_id": workflow_id, "result": r.json(), "status": "completed"}
        return {"workflow_id": workflow_id, "result": None, "status": "error", "error": r.text}


# ─── Retriever ────────────────────────────────────────────────────────────────

@register_node("agentflow.retriever")
async def agentflow_retriever(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Retriever node in agentflow: retrieves relevant documents from a vector store.
    Designed to be used within agent flows for RAG context injection.

    config:
      - collection: vector store collection name
      - vectorstore_type: inmemory | faiss | chroma | pinecone | qdrant | weaviate | ...
      - query: search query (supports {{ }} templates, defaults to input_data.query or input_data.input)
      - top_k: number of documents to retrieve (default 4)
      - include_metadata: include document metadata in output (default True)
      - query_from_input: use input_data.query automatically (default True)
    """
    collection = config.get("collection", "default")
    vs_type = config.get("vectorstore_type", "inmemory")
    top_k = int(config.get("top_k", 4))
    include_metadata = config.get("include_metadata", True)

    query = _render(
        config.get("query", ""),
        input_data,
    ) or input_data.get("query") or input_data.get("input") or input_data.get("prompt", "")

    if not query:
        raise ValueError("agentflow.retriever requires a 'query' in config or input_data")

    # Dispatch to the appropriate vector store query node
    query_node_id = f"vectorstore.{vs_type}.query"
    if query_node_id in NODE_HANDLERS:
        result = await NODE_HANDLERS[query_node_id](
            {"collection": collection, "query": query, "top_k": top_k},
            {"query": query},
            credential_id,
            db,
        )
        docs = result.get("results", result.get("documents", []))
    else:
        # Fallback to generic vector search
        if "vector.search" in NODE_HANDLERS:
            result = await NODE_HANDLERS["vector.search"](
                {"collection": collection, "query": query, "top_k": top_k},
                {"query": query},
                credential_id,
                db,
            )
            docs = result.get("results", [])
        else:
            docs = []
            log.warning("agentflow_retriever_no_store", vs_type=vs_type)

    if not include_metadata:
        docs = [{"text": d.get("content", d.get("text", str(d)))} for d in docs]

    context = "\n\n".join(
        d.get("content", d.get("text", str(d))) for d in docs
    )

    return {
        **input_data,
        "documents": docs,
        "context": context,
        "query": query,
        "collection": collection,
        "retrieved_count": len(docs),
    }


# ─── Tool ─────────────────────────────────────────────────────────────────────

@register_node("agentflow.tool")
async def agentflow_tool(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Tool node in agentflow: wraps any registered tool for use within agent flows.
    Dispatches to any tool node by ID with configurable input mapping.

    config:
      - tool_node_id: the node ID to dispatch to (e.g. "tool.calculator")
      - tool_config: config dict to pass to the tool node
      - input_mapping: dict mapping tool input keys from input_data fields
      - output_key: key to store tool result under (default: "tool_result")
    """
    tool_node_id = config.get("tool_node_id") or config.get("tool_type")
    if not tool_node_id:
        raise ValueError("agentflow.tool requires 'tool_node_id'")

    if tool_node_id not in NODE_HANDLERS:
        raise ValueError(f"agentflow.tool: unknown tool node '{tool_node_id}'")

    tool_config = dict(config.get("tool_config") or {})
    input_mapping = config.get("input_mapping") or {}
    output_key = config.get("output_key", "tool_result")

    # Build tool input from mapping
    tool_input = {}
    for tool_key, data_key in input_mapping.items():
        if isinstance(data_key, str) and data_key.startswith("{{"):
            tool_input[tool_key] = _render(data_key, input_data)
        else:
            tool_input[tool_key] = input_data.get(data_key, data_key)

    if not tool_input:
        tool_input = {k: v for k, v in input_data.items() if not k.startswith("_")}

    # Merge with tool_config (config takes precedence over input_data-derived values)
    merged_config = {**tool_input, **tool_config}

    result = await NODE_HANDLERS[tool_node_id](merged_config, tool_input, credential_id, db)

    return {
        **input_data,
        output_key: result,
        "tool_used": tool_node_id,
    }
