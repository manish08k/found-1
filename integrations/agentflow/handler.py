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


# ─── Start ────────────────────────────────────────────────────────────────────

@register_node("agentflow.start")
async def agentflow_start(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Start node: entry point of an agentflow. Passes through input data,
    optionally merging any static config values. Equivalent to Flowise's
    agentflow/Start/Start.ts.

    config:
      - default_inputs: dict of default key/value pairs merged with input_data
      - input_schema: (informational) JSON schema describing expected inputs
    """
    defaults = config.get("default_inputs") or {}
    output = {**defaults, **input_data}
    output["_flow_started"] = True
    return output


# ─── Agent ────────────────────────────────────────────────────────────────────

@register_node("agentflow.agent")
async def agentflow_agent(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Agent node within an agentflow: runs an LLM-backed agent with optional
    tool use. Equivalent to Flowise's agentflow/Agent/Agent.ts.

    config:
      - provider: openai | anthropic (default: openai)
      - model: LLM model name
      - system_prompt: agent system instructions (supports {{ }} templates)
      - tools: list of tool node IDs available to the agent
      - max_iterations: max tool-call loops (default: 5)
      - input: user message (supports {{ }} templates)
    """
    provider = config.get("provider", "openai")
    model = config.get("model", "")
    system_prompt = _render(config.get("system_prompt", "You are a helpful assistant."), input_data)
    tool_ids = config.get("tools") or []
    max_iter = min(int(config.get("max_iterations", 5)), 10)
    user_input = _render(config.get("input") or config.get("prompt", ""), input_data) or json.dumps(input_data)

    # Build tool call loop
    messages = [{"role": "user", "content": user_input}]
    all_tool_results = []

    for _ in range(max_iter):
        response = await _call_llm(provider, model, system_prompt, "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in messages
        ), max_tokens=2048)

        # Check for tool invocation pattern: Tool: <id>\nInput: <json>
        tool_match = re.search(r"Tool:\s*(\S+)\s*\nInput:\s*(\{.*?\})", response, re.DOTALL)
        if tool_match and tool_match.group(1) in NODE_HANDLERS:
            tool_id = tool_match.group(1)
            try:
                tool_args = json.loads(tool_match.group(2))
            except json.JSONDecodeError:
                tool_args = {}
            tool_result = await NODE_HANDLERS[tool_id](tool_args, tool_args, credential_id, db)
            observation = json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"Observation: {observation}"})
            all_tool_results.append({"tool": tool_id, "result": tool_result})
        else:
            # Final answer
            return {
                **input_data,
                "agent_response": response,
                "tool_calls": all_tool_results,
                "messages": messages,
            }

    return {**input_data, "agent_response": response, "tool_calls": all_tool_results, "messages": messages}


# ─── Condition ────────────────────────────────────────────────────────────────

@register_node("agentflow.condition")
async def agentflow_condition(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Rule-based condition node (no LLM): evaluates a simple expression against
    input_data and routes to 'true' or 'false' branch.
    Equivalent to Flowise's agentflow/Condition/Condition.ts.

    config:
      - field: the input_data field to test
      - operator: equals | not_equals | contains | not_contains | gt | lt |
                  gte | lte | is_empty | is_not_empty | exists
      - value: the value to compare against (supports {{ }} templates)
      - case_sensitive: bool (default True)
    """
    field = config.get("field", "")
    operator = config.get("operator", "equals")
    expected = _render(str(config.get("value", "")), input_data)
    case_sensitive = config.get("case_sensitive", True)

    actual = input_data.get(field)
    actual_str = str(actual) if actual is not None else ""
    if not case_sensitive:
        actual_str = actual_str.lower()
        expected = expected.lower()

    result = False
    if operator == "equals":
        result = actual_str == expected
    elif operator == "not_equals":
        result = actual_str != expected
    elif operator == "contains":
        result = expected in actual_str
    elif operator == "not_contains":
        result = expected not in actual_str
    elif operator == "gt":
        try:
            result = float(actual_str) > float(expected)
        except (ValueError, TypeError):
            result = False
    elif operator == "lt":
        try:
            result = float(actual_str) < float(expected)
        except (ValueError, TypeError):
            result = False
    elif operator == "gte":
        try:
            result = float(actual_str) >= float(expected)
        except (ValueError, TypeError):
            result = False
    elif operator == "lte":
        try:
            result = float(actual_str) <= float(expected)
        except (ValueError, TypeError):
            result = False
    elif operator == "is_empty":
        result = not actual_str
    elif operator == "is_not_empty":
        result = bool(actual_str)
    elif operator == "exists":
        result = field in input_data and input_data[field] is not None

    branch = "true" if result else "false"
    return {
        **input_data,
        "condition_result": result,
        "branch": branch,
        "evaluated_field": field,
        "operator": operator,
    }


# ─── CustomFunction ───────────────────────────────────────────────────────────

@register_node("agentflow.custom_function")
async def agentflow_custom_function(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    CustomFunction node: executes a user-defined Python function within a
    restricted sandbox. Equivalent to Flowise's agentflow/CustomFunction/CustomFunction.ts.

    config:
      - code: Python source code. Must define a function named 'run(input_data: dict) -> dict'
      - timeout: max execution time in seconds (default: 10)
    """
    code = config.get("code", "")
    timeout = int(config.get("timeout", 10))

    if not code:
        return {**input_data, "custom_function_result": None, "error": "No code provided"}

    # Ensure the code defines a 'run' function
    if "def run(" not in code and "async def run(" not in code:
        return {**input_data, "custom_function_result": None,
                "error": "Code must define a function named 'run(input_data: dict) -> dict'"}

    # Restricted execution environment
    safe_globals = {
        "__builtins__": {
            "len": len, "str": str, "int": int, "float": float, "bool": bool,
            "list": list, "dict": dict, "tuple": tuple, "set": set,
            "range": range, "enumerate": enumerate, "zip": zip, "map": map,
            "filter": filter, "sorted": sorted, "reversed": reversed,
            "sum": sum, "min": min, "max": max, "abs": abs, "round": round,
            "isinstance": isinstance, "type": type, "print": print,
            "json": __import__("json"), "re": __import__("re"),
        }
    }

    local_ns: dict = {}
    exec(compile(code, "<agentflow_custom_function>", "exec"), safe_globals, local_ns)

    run_fn = local_ns.get("run")
    if not callable(run_fn):
        return {**input_data, "custom_function_result": None, "error": "'run' is not callable"}

    try:
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, run_fn, dict(input_data)),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return {**input_data, "custom_function_result": None, "error": f"Execution timed out after {timeout}s"}

    if isinstance(result, dict):
        return {**input_data, **result, "custom_function_result": result}
    return {**input_data, "custom_function_result": result}


# ─── HTTP ─────────────────────────────────────────────────────────────────────

@register_node("agentflow.http")
async def agentflow_http(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    HTTP node: makes an HTTP request within an agentflow.
    Equivalent to Flowise's agentflow/HTTP/HTTP.ts.

    config:
      - url: target URL (supports {{ }} templates)
      - method: GET | POST | PUT | PATCH | DELETE (default: GET)
      - headers: dict of request headers
      - body: request body (dict for JSON, string for raw)
      - params: query parameters dict
      - timeout: seconds (default: 30)
      - response_format: json | text | auto (default: auto)
    """
    url = _render(config.get("url", ""), input_data)
    if not url:
        raise ValueError("agentflow.http requires 'url'")

    method = config.get("method", "GET").upper()
    headers = config.get("headers") or {}
    body = config.get("body")
    params = config.get("params") or {}
    timeout = float(config.get("timeout", 30))
    response_format = config.get("response_format", "auto")

    # Render template values in headers and params
    headers = {k: _render(str(v), input_data) for k, v in headers.items()}
    params = {k: _render(str(v), input_data) for k, v in params.items()}

    if isinstance(body, str):
        body = _render(body, input_data)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        if method in ("GET", "DELETE"):
            r = await client.request(method, url, headers=headers, params=params)
        else:
            if isinstance(body, dict):
                r = await client.request(method, url, headers=headers, params=params, json=body)
            else:
                r = await client.request(method, url, headers=headers, params=params, content=body)

    status = r.status_code
    content_type = r.headers.get("content-type", "")

    if response_format == "json" or (response_format == "auto" and "application/json" in content_type):
        try:
            response_body = r.json()
        except Exception:
            response_body = r.text
    else:
        response_body = r.text

    return {
        **input_data,
        "status_code": status,
        "response": response_body,
        "headers": dict(r.headers),
        "url": url,
        "method": method,
    }


# ─── HumanInput ───────────────────────────────────────────────────────────────

@register_node("agentflow.human_input")
async def agentflow_human_input(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    HumanInput node: pauses the flow and waits for human input.
    Equivalent to Flowise's agentflow/HumanInput/HumanInput.ts.

    In production, this creates a pending approval record and raises a
    HumanInputRequired exception. The orchestrator captures this and
    resumes the flow when input is provided via the approval API.

    config:
      - prompt: message shown to the human operator (supports {{ }} templates)
      - input_key: key under which the human's reply will be stored (default: "human_input")
      - timeout: max wait seconds (default: 3600)
    """
    prompt_msg = _render(config.get("prompt", "Please provide input to continue."), input_data)
    input_key = config.get("input_key", "human_input")
    timeout = int(config.get("timeout", 3600))

    # Check if human input has already been provided (flow resumed)
    if input_key in input_data:
        return {**input_data, "human_input_received": True, "human_input_prompt": prompt_msg}

    # Try to create an approval record via the approval node
    if "approval.wait" in NODE_HANDLERS:
        approval_result = await NODE_HANDLERS["approval.wait"](
            {"prompt": prompt_msg, "timeout": timeout, "input_key": input_key},
            input_data, credential_id, db,
        )
        return {**input_data, **approval_result, "human_input_received": False, "human_input_prompt": prompt_msg}

    # Fallback: return a signal that human input is required
    return {
        **input_data,
        "human_input_required": True,
        "human_input_prompt": prompt_msg,
        "human_input_key": input_key,
        "human_input_received": False,
    }


# ─── Iteration ────────────────────────────────────────────────────────────────

@register_node("agentflow.iteration")
async def agentflow_iteration(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Iteration node: iterates over a list in input_data, dispatching a sub-node
    for each item. Equivalent to Flowise's agentflow/Iteration/Iteration.ts.

    config:
      - items_key: key in input_data containing the list to iterate (default: "items")
      - item_key: key used to pass each item to the sub-node (default: "item")
      - sub_node_id: node ID to call for each item
      - sub_config: config passed to the sub-node
      - output_key: key for collecting results (default: "iteration_results")
    """
    items_key = config.get("items_key", "items")
    item_key = config.get("item_key", "item")
    sub_node_id = config.get("sub_node_id")
    sub_config = config.get("sub_config") or {}
    output_key = config.get("output_key", "iteration_results")

    items = input_data.get(items_key, [])
    if not isinstance(items, list):
        items = [items]

    results = []
    for i, item in enumerate(items):
        item_input = {**input_data, item_key: item, "_iteration_index": i}

        if sub_node_id and sub_node_id in NODE_HANDLERS:
            try:
                sub_result = await NODE_HANDLERS[sub_node_id](sub_config, item_input, credential_id, db)
                results.append(sub_result)
            except Exception as e:
                results.append({"error": str(e), "item": item, "index": i})
        else:
            # No sub-node: just collect items
            results.append(item_input)

    return {
        **input_data,
        output_key: results,
        "_iteration_count": len(items),
        "_iteration_completed": True,
    }


# ─── LLM ──────────────────────────────────────────────────────────────────────

@register_node("agentflow.llm")
async def agentflow_llm(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    LLM node: direct LLM call within an agentflow. Equivalent to
    Flowise's agentflow/LLM/LLM.ts.

    config:
      - provider: openai | anthropic (default: openai)
      - model: LLM model name
      - system_prompt: system instructions (supports {{ }} templates)
      - prompt: user message (supports {{ }} templates)
      - max_tokens: max tokens in response (default: 1024)
      - temperature: sampling temperature (default: 0.7)
      - output_key: key to store LLM output (default: "llm_output")
    """
    provider = config.get("provider", "openai")
    model = config.get("model", "")
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    prompt = _render(config.get("prompt", ""), input_data) or json.dumps(input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    output_key = config.get("output_key", "llm_output")

    response = await _call_llm(provider, model, system_prompt, prompt, max_tokens)

    return {
        **input_data,
        output_key: response,
        "llm_provider": provider,
        "llm_model": model,
    }


# ─── Loop ─────────────────────────────────────────────────────────────────────

@register_node("agentflow.loop")
async def agentflow_loop(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Loop node: repeats a sub-node until a condition is met or max iterations
    reached. Equivalent to Flowise's agentflow/Loop/Loop.ts.

    config:
      - sub_node_id: node ID to execute each iteration
      - sub_config: config for the sub-node
      - condition_field: field in sub-node output to check for loop exit
      - condition_value: value that, when matched, exits the loop
      - max_iterations: max loop iterations (default: 10)
      - output_key: key for collecting iteration outputs (default: "loop_results")
    """
    sub_node_id = config.get("sub_node_id")
    sub_config = config.get("sub_config") or {}
    condition_field = config.get("condition_field", "done")
    condition_value = config.get("condition_value", True)
    max_iter = int(config.get("max_iterations", 10))
    output_key = config.get("output_key", "loop_results")

    if not sub_node_id or sub_node_id not in NODE_HANDLERS:
        return {**input_data, output_key: [], "error": f"Sub-node '{sub_node_id}' not found"}

    current_data = dict(input_data)
    results = []
    for i in range(max_iter):
        result = await NODE_HANDLERS[sub_node_id](sub_config, current_data, credential_id, db)
        results.append(result)
        current_data = {**current_data, **result, "_loop_iteration": i + 1}

        # Check exit condition
        actual = result.get(condition_field)
        if actual == condition_value or str(actual) == str(condition_value):
            break

    return {
        **current_data,
        output_key: results,
        "_loop_iterations_run": len(results),
        "_loop_completed": True,
    }


# ─── StickyNote ───────────────────────────────────────────────────────────────

@register_node("agentflow.sticky_note")
async def agentflow_sticky_note(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    StickyNote node: a visual annotation node with no execution effect.
    Passes input data through unchanged. Equivalent to Flowise's
    agentflow/StickyNote/StickyNote.ts.

    config:
      - text: the note text content
      - color: background color (informational)
    """
    # Pure pass-through — sticky notes are UI-only
    return {**input_data, "_sticky_note": config.get("text", "")}


# ─── New AgentFlow Nodes ───────────────────────────────────────────────────────

@register_node("agentflow.planner")
async def agentflow_planner(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Planner node — uses an LLM to break a goal into ordered subtasks.
    config: model, goal_field (default "goal"), output_field (default "plan")
    """
    import json, re
    goal_field = config.get("goal_field", "goal")
    output_field = config.get("output_field", "plan")
    goal = input_data.get(goal_field) or input_data.get("input") or str(input_data)
    provider = "anthropic" if __import__("core.config", fromlist=["settings"]).settings.ANTHROPIC_API_KEY else "openai"
    model = config.get("model", "")
    system = (
        "You are a task planner. Given a goal, produce a numbered list of clear, actionable subtasks.\n"
        "Respond with ONLY a JSON array of strings: [\"step 1\", \"step 2\", ...]"
    )
    raw = await _call_llm(provider, model, system, f"Goal: {goal}", max_tokens=512)
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        plan = json.loads(cleaned)
        if not isinstance(plan, list):
            plan = [cleaned]
    except Exception:
        plan = [s.strip("- ").strip() for s in cleaned.split("\n") if s.strip()]
    return {**input_data, output_field: plan}


@register_node("agentflow.router")
async def agentflow_router(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Router node — uses an LLM to classify the input and pick a route.
    config: model, routes (list of {"label": str, "description": str}), input_field
    """
    import json, re
    routes = config.get("routes", [])
    input_field = config.get("input_field", "input")
    inp = input_data.get(input_field) or str(input_data)
    provider = "anthropic" if __import__("core.config", fromlist=["settings"]).settings.ANTHROPIC_API_KEY else "openai"
    model = config.get("model", "")
    routes_desc = "\n".join(f"- {r['label']}: {r.get('description', '')}" for r in routes) if routes else "default"
    system = (
        "You are a router. Given the input, choose the most appropriate route from the list.\n"
        "Respond with ONLY a JSON object: {\"route\": \"<route_label>\", \"reason\": \"...\"}"
    )
    prompt = f"Input: {inp}\n\nAvailable routes:\n{routes_desc}"
    raw = await _call_llm(provider, model, system, prompt, max_tokens=200)
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        result = json.loads(cleaned)
        route = result.get("route", routes[0]["label"] if routes else "default")
        reason = result.get("reason", "")
    except Exception:
        route = routes[0]["label"] if routes else "default"
        reason = raw.strip()
    return {**input_data, "route": route, "route_reason": reason}


@register_node("agentflow.memory_read")
async def agentflow_memory_read(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Memory Read — reads recent messages from MemoryMessage store.
    config: conversation_id_field, limit
    """
    from sqlalchemy import select
    from storage.models import MemoryMessage
    conv_id_field = config.get("conversation_id_field", "conversation_id")
    conv_id = input_data.get(conv_id_field) or config.get("_workflow_id")
    limit = int(config.get("limit", 20))
    messages = []
    if conv_id and db:
        result = await db.execute(
            select(MemoryMessage)
            .where(MemoryMessage.conversation_id == str(conv_id))
            .order_by(MemoryMessage.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        messages = [{"role": m.role, "content": m.content} for m in reversed(rows)]
    return {**input_data, "memory_messages": messages, "memory_count": len(messages)}


@register_node("agentflow.memory_write")
async def agentflow_memory_write(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Memory Write — persists a message to MemoryMessage store.
    config: conversation_id_field, role, content_field
    """
    from storage.models import MemoryMessage
    conv_id_field = config.get("conversation_id_field", "conversation_id")
    conv_id = input_data.get(conv_id_field) or config.get("_workflow_id")
    role = config.get("role", "assistant")
    content_field = config.get("content_field", "output")
    content = input_data.get(content_field) or str(input_data)
    if conv_id and db and content:
        msg = MemoryMessage(
            workflow_id=config.get("_workflow_id"),
            conversation_id=str(conv_id),
            role=role,
            content=str(content),
        )
        db.add(msg)
        await db.flush()
    return {**input_data, "_memory_written": True}


@register_node("agentflow.parallel_agents")
async def agentflow_parallel_agents(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Parallel Agents — executes multiple sub-workflows concurrently.
    config: workflow_ids (list of workflow IDs)
    """
    import asyncio, uuid
    from storage.models import Execution, ExecutionStatus, Workflow
    from sqlalchemy import select
    from core.execution_engine import execute_workflow
    workflow_ids = config.get("workflow_ids", [])
    if not workflow_ids:
        return {**input_data, "parallel_results": {}}
    results = {}

    async def run_one(wf_id: str):
        wf_result = await db.execute(select(Workflow).where(Workflow.id == wf_id))
        wf = wf_result.scalar_one_or_none()
        if not wf:
            return wf_id, {"error": f"Workflow {wf_id} not found"}
        exec_id = str(uuid.uuid4())
        execution = Execution(
            id=exec_id, workflow_id=wf_id,
            status=ExecutionStatus.queued, trigger_type="parallel_agent",
            trigger_data=input_data,
        )
        db.add(execution)
        await db.flush()
        await execute_workflow(exec_id, wf.definition, input_data)
        await db.refresh(execution)
        return wf_id, {"status": execution.status.value, "node_results": execution.node_results}

    tasks = [run_one(wf_id) for wf_id in workflow_ids]
    resolved = await asyncio.gather(*tasks, return_exceptions=True)
    for item in resolved:
        if isinstance(item, Exception):
            results[str(item)] = {"error": str(item)}
        else:
            wf_id, res = item
            results[wf_id] = res

    return {**input_data, "parallel_results": results}


@register_node("agentflow.sequential_agents")
async def agentflow_sequential_agents(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Sequential Agents — runs sub-workflows in sequence, passing output forward.
    config: workflow_ids (list of workflow IDs)
    """
    import uuid
    from storage.models import Execution, ExecutionStatus, Workflow
    from sqlalchemy import select
    from core.execution_engine import execute_workflow
    workflow_ids = config.get("workflow_ids", [])
    current_data = dict(input_data)
    results = []
    for wf_id in workflow_ids:
        wf_result = await db.execute(select(Workflow).where(Workflow.id == wf_id))
        wf = wf_result.scalar_one_or_none()
        if not wf:
            results.append({"workflow_id": wf_id, "error": "Not found"})
            continue
        exec_id = str(uuid.uuid4())
        execution = Execution(
            id=exec_id, workflow_id=wf_id,
            status=ExecutionStatus.queued, trigger_type="sequential_agent",
            trigger_data=current_data,
        )
        db.add(execution)
        await db.flush()
        await execute_workflow(exec_id, wf.definition, current_data)
        await db.refresh(execution)
        # Merge outputs into current_data for next agent
        node_results = execution.node_results or {}
        for nr in node_results.values():
            if isinstance(nr, dict) and nr.get("status") == "success":
                out = nr.get("output", {})
                if isinstance(out, dict):
                    current_data.update(out)
        results.append({"workflow_id": wf_id, "status": execution.status.value})
    return {**current_data, "sequential_results": results}


@register_node("agentflow.tool_caller")
async def agentflow_tool_caller(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Tool Caller — calls any registered node handler by type name with LLM-generated arguments.
    config: tool_name (node type), tool_description
    """
    import json, re
    from core.execution_engine import NODE_HANDLERS
    tool_name = config.get("tool_name", "")
    if not tool_name or tool_name not in NODE_HANDLERS:
        raise ValueError(f"Tool '{tool_name}' is not registered. Available: {list(NODE_HANDLERS.keys())[:20]}")
    tool_desc = config.get("tool_description", f"Tool: {tool_name}")
    provider = "anthropic" if __import__("core.config", fromlist=["settings"]).settings.ANTHROPIC_API_KEY else "openai"
    system = (
        f"You are calling the tool: {tool_name}\n"
        f"Description: {tool_desc}\n"
        "Based on the input data, generate the config arguments for this tool.\n"
        "Respond with ONLY a valid JSON object of config parameters."
    )
    raw = await _call_llm(provider, "", system, f"Input: {json.dumps(input_data)[:2000]}", max_tokens=512)
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        generated_config = json.loads(cleaned)
    except Exception:
        generated_config = {}
    merged_config = {**generated_config, **config}
    handler = NODE_HANDLERS[tool_name]
    result = await handler(config=merged_config, input_data=input_data, credential_id=credential_id, db=db)
    return {**input_data, "tool_result": result, "_tool_called": tool_name}
