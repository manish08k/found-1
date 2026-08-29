"""
Agent nodes — ReAct, OpenAI Function Calling, Conversational, SQL, and
multi-step planning agents.

These nodes orchestrate tool use in a loop, deciding which registered
tool nodes to call based on the LLM's guidance.
"""
import json
import re

import httpx
import structlog

from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MAX_ITERATIONS = 10


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


# ─── ReAct Agent ──────────────────────────────────────────────────────────────

@register_node("agent.react")
async def agent_react(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    ReAct (Reason + Act) agent using the Thought/Action/Observation loop.
    The agent uses any LLM provider and calls registered tool nodes.

    config:
      - provider: anthropic | openai (default: auto-detect)
      - model: LLM model name
      - system_prompt: extra system instructions
      - tools: list of tool node IDs available (e.g. ["tool.calculator", "tool.wikipedia"])
      - max_iterations: max Thought/Action cycles (default 10)
      - input: the user question (templated)
    """
    from core.execution_engine import NODE_HANDLERS
    from integrations.ai.handler import _call_anthropic, _call_openai, _pick_provider

    provider = _pick_provider(config)
    model = config.get("model", "")
    max_iter = min(int(config.get("max_iterations", 5)), MAX_ITERATIONS)
    question = _render(config.get("input") or config.get("prompt", ""), input_data)
    if not question:
        question = json.dumps(input_data)

    tool_ids = config.get("tools") or []
    tool_descriptions = []
    for tid in tool_ids:
        if tid in NODE_HANDLERS:
            tool_descriptions.append(f"- {tid}: Available tool")

    tools_str = "\n".join(tool_descriptions) if tool_descriptions else "No tools available."

    system = config.get("system_prompt", "") or (
        "You are a helpful assistant that solves problems step by step.\n"
        "Use the following format:\n"
        "Thought: [your reasoning]\n"
        "Action: [tool_id]\n"
        "Action Input: [JSON object with tool inputs]\n"
        "Observation: [result of the action]\n"
        "... (repeat Thought/Action/Observation as needed)\n"
        "Final Answer: [your final answer to the original question]\n\n"
        f"Available tools:\n{tools_str}"
    )

    messages = [{"role": "user", "content": question}]
    all_thoughts = []
    iterations = 0
    final_answer = None

    async def call_llm(msgs):
        prompt = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in msgs)
        if provider == "anthropic":
            return await _call_anthropic(model, system, prompt, 2048, 0)
        else:
            return await _call_openai(model, system, prompt, 2048, 0)

    # ReAct loop
    running_context = question
    while iterations < max_iter:
        response = await call_llm([{"role": "user", "content": running_context}])
        all_thoughts.append(response)
        iterations += 1

        # Check for Final Answer
        if "Final Answer:" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
            break

        # Parse Action
        action_match = re.search(r"Action:\s*([^\n]+)", response)
        action_input_match = re.search(r"Action Input:\s*(\{.*?\})", response, re.DOTALL)

        if action_match and action_input_match:
            tool_id = action_match.group(1).strip()
            try:
                tool_input = json.loads(action_input_match.group(1))
            except Exception:
                tool_input = {"input": action_input_match.group(1)}

            if tool_id in NODE_HANDLERS:
                try:
                    observation = await NODE_HANDLERS[tool_id](tool_input, tool_input, None, db)
                    obs_str = json.dumps(observation) if isinstance(observation, dict) else str(observation)
                except Exception as e:
                    obs_str = f"Error calling {tool_id}: {e}"
            else:
                obs_str = f"Unknown tool: {tool_id}"

            running_context = (
                f"{running_context}\n"
                f"Thought: {response}\n"
                f"Action: {tool_id}\n"
                f"Observation: {obs_str}"
            )
        else:
            # No action found, treat as final answer
            final_answer = response
            break

    return {
        "answer": final_answer or running_context,
        "thoughts": all_thoughts,
        "iterations": iterations,
        "provider": provider,
    }


# ─── OpenAI Function Calling Agent ────────────────────────────────────────────

@register_node("agent.openai_function")
async def agent_openai_function(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Agent using OpenAI's native function-calling / tool-use API.
    Tool schemas are auto-generated from the tool_ids list.
    Requires OPENAI_API_KEY.
    """
    from core.execution_engine import NODE_HANDLERS

    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("agent.openai_function requires OPENAI_API_KEY")

    model = config.get("model", "gpt-4o-mini")
    question = _render(config.get("input") or config.get("prompt", ""), input_data)
    system_prompt = config.get("system_prompt", "You are a helpful assistant.")
    tool_ids = config.get("tools") or []
    max_iter = min(int(config.get("max_iterations", 5)), MAX_ITERATIONS)

    # Build OpenAI tool schemas
    tool_schemas = []
    for tid in tool_ids:
        name = tid.replace(".", "_")
        tool_schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": f"Call the {tid} tool",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "object", "description": "Tool input parameters"}
                    },
                    "required": ["input"],
                },
            },
        })

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    iterations = 0
    tool_calls_log = []

    async with httpx.AsyncClient(timeout=120) as client:
        while iterations < max_iter:
            payload = {
                "model": model,
                "messages": messages,
                "tools": tool_schemas if tool_schemas else None,
                "tool_choice": "auto" if tool_schemas else None,
            }
            if not tool_schemas:
                payload.pop("tools", None)
                payload.pop("tool_choice", None)

            r = await client.post(
                OPENAI_API_URL,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            r.raise_for_status()
            response = r.json()

            msg = response["choices"][0]["message"]
            messages.append(msg)
            iterations += 1

            if response["choices"][0]["finish_reason"] in ("stop", "length"):
                break

            # Handle tool calls
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"])
                    tool_id = fn_name.replace("_", ".", 1)

                    tool_input = fn_args.get("input") or fn_args

                    if tool_id in NODE_HANDLERS:
                        try:
                            result = await NODE_HANDLERS[tool_id](tool_input, tool_input, None, db)
                        except Exception as e:
                            result = {"error": str(e)}
                    else:
                        result = {"error": f"Unknown tool: {tool_id}"}

                    tool_calls_log.append({"tool": tool_id, "input": tool_input, "result": result})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result),
                    })
            else:
                break

    final_message = messages[-1].get("content", "") if messages else ""
    return {
        "answer": final_message,
        "messages": messages,
        "tool_calls": tool_calls_log,
        "iterations": iterations,
        "model": model,
    }


# ─── Conversational Agent ─────────────────────────────────────────────────────

@register_node("agent.conversational")
async def agent_conversational(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Stateful conversational agent with memory + optional tools.
    Uses ai.chat_with_memory under the hood.
    """
    from integrations.ai.handler import _pick_provider, _call_anthropic, _call_openai, _render_template
    from sqlalchemy import select
    from storage.models import MemoryMessage

    workflow_id = config.get("_workflow_id")
    conversation_id = config.get("conversation_id") or input_data.get("conversation_id", "default")
    provider = _pick_provider(config)
    model = config.get("model", "")
    system_prompt = config.get("system_prompt", "You are a helpful conversational assistant.")
    user_message = _render_template(config.get("input") or config.get("prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    max_history = int(config.get("max_history_messages", 10))

    if not user_message:
        raise ValueError("agent.conversational requires 'input' or 'prompt'")

    # Load history
    history = []
    if workflow_id:
        result = await db.execute(
            select(MemoryMessage)
            .where(MemoryMessage.workflow_id == workflow_id, MemoryMessage.conversation_id == conversation_id)
            .order_by(MemoryMessage.created_at.asc())
            .limit(max_history)
        )
        history = result.scalars().all()

    transcript = "\n".join(f"{m.role}: {m.content}" for m in history)
    full_prompt = f"{transcript}\nuser: {user_message}" if transcript else user_message

    if provider == "anthropic":
        response = await _call_anthropic(model, system_prompt, full_prompt, max_tokens, 0.7)
    else:
        response = await _call_openai(model, system_prompt, full_prompt, max_tokens, 0.7)

    # Persist
    if workflow_id:
        db.add(MemoryMessage(workflow_id=workflow_id, conversation_id=conversation_id, role="user", content=user_message))
        db.add(MemoryMessage(workflow_id=workflow_id, conversation_id=conversation_id, role="assistant", content=response))

    return {
        "response": response,
        "conversation_id": conversation_id,
        "provider": provider,
        "history_length": len(history) + 2,
    }


# ─── SQL Agent ────────────────────────────────────────────────────────────────

@register_node("agent.sql")
async def agent_sql(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Natural-language-to-SQL agent.
    Translates user questions into SQL queries and executes them.

    config:
      - connection_string: SQLAlchemy connection string (or use credential)
      - tables: list of table names to include in schema context
      - question: natural language question
    """
    from integrations.ai.handler import _pick_provider, _call_anthropic, _call_openai

    connection_string = config.get("connection_string") or getattr(settings, "DATABASE_URL", None)
    if not connection_string:
        raise ValueError("agent.sql requires 'connection_string'")

    question = _render(config.get("question") or config.get("input", ""), input_data)
    if not question:
        raise ValueError("agent.sql requires 'question'")

    tables = config.get("tables") or []
    max_rows = int(config.get("max_rows", 100))

    provider = _pick_provider(config)
    model = config.get("model", "")

    # Get schema for context
    schema_info = ""
    try:
        from sqlalchemy import create_engine, inspect, text
        import asyncio
        loop = asyncio.get_event_loop()

        def get_schema():
            eng = create_engine(connection_string)
            insp = inspect(eng)
            info = []
            target_tables = tables if tables else insp.get_table_names()
            for tbl in target_tables[:10]:  # limit to avoid huge prompts
                cols = insp.get_columns(tbl)
                col_strs = ", ".join(f"{c['name']} ({c['type']})" for c in cols)
                info.append(f"Table {tbl}: {col_strs}")
            eng.dispose()
            return "\n".join(info)

        schema_info = await loop.run_in_executor(None, get_schema)
    except Exception as e:
        schema_info = f"Could not introspect schema: {e}"

    system = (
        "You are a SQL expert. Given the database schema, write a single valid SQL query to answer the question. "
        "Return ONLY the SQL query — no explanation, no markdown, no semicolons at the end.\n\n"
        f"Schema:\n{schema_info}"
    )

    prompt = f"Question: {question}\n\nSQL Query:"

    if provider == "anthropic":
        sql = await _call_anthropic(model, system, prompt, 512, 0)
    else:
        sql = await _call_openai(model, system, prompt, 512, 0)

    sql = sql.strip().rstrip(";")

    # Execute query
    rows = []
    columns = []
    try:
        from sqlalchemy import create_engine, text

        def run_query():
            eng = create_engine(connection_string)
            with eng.connect() as conn:
                result = conn.execute(text(sql))
                cols = list(result.keys())
                data = [dict(zip(cols, row)) for row in result.fetchmany(max_rows)]
            eng.dispose()
            return cols, data

        import asyncio
        loop = asyncio.get_event_loop()
        columns, rows = await loop.run_in_executor(None, run_query)
    except Exception as e:
        return {"sql": sql, "error": str(e), "rows": [], "columns": []}

    return {
        "sql": sql,
        "rows": rows,
        "columns": columns,
        "row_count": len(rows),
        "question": question,
    }


# ─── Chain-of-Thought ─────────────────────────────────────────────────────────

@register_node("agent.chain_of_thought")
async def agent_chain_of_thought(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Forces step-by-step reasoning before giving a final answer.
    Uses the "Let's think step by step" prompt enhancement.
    """
    from integrations.ai.handler import _pick_provider, _call_anthropic, _call_openai

    provider = _pick_provider(config)
    model = config.get("model", "")
    question = _render(config.get("input") or config.get("prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 2048))

    system = config.get("system_prompt", "You are a careful, systematic thinker.")
    cot_prompt = f"{question}\n\nLet's think step by step:"

    if provider == "anthropic":
        reasoning = await _call_anthropic(model, system, cot_prompt, max_tokens, 0.3)
    else:
        reasoning = await _call_openai(model, system, cot_prompt, max_tokens, 0.3)

    # Extract final answer from reasoning
    final_system = system
    final_prompt = (
        f"Based on this step-by-step reasoning:\n{reasoning}\n\n"
        f"The final, concise answer to '{question}' is:"
    )

    if provider == "anthropic":
        answer = await _call_anthropic(model, final_system, final_prompt, 512, 0)
    else:
        answer = await _call_openai(model, final_system, final_prompt, 512, 0)

    return {
        "answer": answer.strip(),
        "reasoning": reasoning,
        "question": question,
        "provider": provider,
    }


# ─── Supervisor (Multi-Agent) ─────────────────────────────────────────────────

@register_node("agent.supervisor")
async def agent_supervisor(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Multi-agent supervisor that routes tasks to specialized worker agents.
    Routes based on LLM classification to one of the configured sub-agents.

    config:
      - workers: list of {"name": str, "description": str, "node_id": str}
      - input: task to route
    """
    from integrations.ai.handler import _pick_provider, _call_anthropic, _call_openai
    from core.execution_engine import NODE_HANDLERS

    provider = _pick_provider(config)
    model = config.get("model", "")
    task = _render(config.get("input") or config.get("task", ""), input_data)
    workers = config.get("workers") or []

    if not workers:
        raise ValueError("agent.supervisor requires at least one 'worker'")

    worker_list = "\n".join(f"- {w['name']}: {w.get('description', '')}" for w in workers)
    worker_names = [w["name"] for w in workers]

    system = "You are a routing supervisor. Choose which worker agent should handle the task."
    prompt = (
        f"Task: {task}\n\n"
        f"Available workers:\n{worker_list}\n\n"
        f"Respond with ONLY the worker name from this list: {worker_names}"
    )

    if provider == "anthropic":
        chosen = await _call_anthropic(model, system, prompt, 50, 0)
    else:
        chosen = await _call_openai(model, system, prompt, 50, 0)

    chosen = chosen.strip()

    # Find matching worker
    worker = next((w for w in workers if w["name"].lower() == chosen.lower()), workers[0])
    node_id = worker.get("node_id")

    if node_id and node_id in NODE_HANDLERS:
        worker_config = {**config, **worker.get("config", {}), "input": task}
        result = await NODE_HANDLERS[node_id](worker_config, input_data, credential_id, db)
    else:
        result = {"answer": f"Worker {worker['name']} has no configured node_id"}

    return {
        "chosen_worker": worker["name"],
        "task": task,
        "result": result,
    }

# ─── XML Agent ────────────────────────────────────────────────────────────────

@register_node("agent.xml")
async def agent_xml(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    XML-format ReAct agent — uses XML-style tags for Thought/Action/Observation.
    Well-suited for Anthropic Claude models which work better with structured XML output.

    config:
      - model: LLM model name
      - tools: list of tool node IDs
      - input: the user question
      - system_prompt: additional system instructions
      - max_iterations: max iterations (default 8)
    """
    from core.execution_engine import NODE_HANDLERS
    from integrations.ai.handler import _call_anthropic, _call_openai, _pick_provider

    provider = _pick_provider(config)
    model = config.get("model", "")
    max_iter = min(int(config.get("max_iterations", 8)), MAX_ITERATIONS)
    question = _render(config.get("input") or config.get("prompt", ""), input_data)
    tool_ids = config.get("tools") or []

    tools_xml = "\n".join(f"  <tool><name>{t}</name><description>Call the {t} node</description></tool>"
                          for t in tool_ids if t in NODE_HANDLERS)

    system = config.get("system_prompt") or (
        "You are a helpful assistant that uses XML tags for structured reasoning.\n\n"
        "Use this format:\n"
        "<thought>Your reasoning here</thought>\n"
        "<action><tool>tool_name</tool><input>{\"key\": \"value\"}</input></action>\n"
        "<observation>Tool result</observation>\n"
        "... repeat as needed ...\n"
        "<final_answer>Your final answer</final_answer>\n\n"
        f"<available_tools>\n{tools_xml}\n</available_tools>"
    )

    context = question
    thoughts = []
    final_answer = None

    for iteration in range(max_iter):
        if provider == "anthropic":
            response = await _call_anthropic(model, system, context, 2048, 0)
        else:
            response = await _call_openai(model, system, context, 2048, 0)

        thoughts.append(response)

        # Check for final answer
        fa_match = re.search(r"<final_answer>(.*?)</final_answer>", response, re.DOTALL)
        if fa_match:
            final_answer = fa_match.group(1).strip()
            break

        # Parse action
        action_match = re.search(r"<action>\s*<tool>(.*?)</tool>\s*<input>(.*?)</input>\s*</action>",
                                 response, re.DOTALL)
        if action_match:
            tool_id = action_match.group(1).strip()
            try:
                tool_input = json.loads(action_match.group(2).strip())
            except Exception:
                tool_input = {"input": action_match.group(2).strip()}

            if tool_id in NODE_HANDLERS:
                try:
                    obs = await NODE_HANDLERS[tool_id](tool_input, tool_input, None, db)
                    obs_str = json.dumps(obs) if isinstance(obs, dict) else str(obs)
                except Exception as e:
                    obs_str = f"Error: {e}"
            else:
                obs_str = f"Unknown tool: {tool_id}"

            context = f"{context}\n{response}\n<observation>{obs_str}</observation>"
        else:
            final_answer = response
            break

    return {
        "answer": final_answer or context,
        "thoughts": thoughts,
        "iterations": len(thoughts),
        "provider": provider,
    }


# ─── Worker (multi-agent worker node) ─────────────────────────────────────────

@register_node("agent.worker")
async def agent_worker(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    A specialized worker agent designed to be called by agent.supervisor.
    Has a fixed role/persona and a set of tools to accomplish a specific category of tasks.

    config:
      - name: worker name/identifier
      - role: system-level role description
      - tools: list of tool node IDs this worker can use
      - model: LLM model to use
      - max_iterations: max ReAct iterations (default 5)
      - input: the task to perform
    """
    from core.execution_engine import NODE_HANDLERS
    from integrations.ai.handler import _call_anthropic, _call_openai, _pick_provider

    provider = _pick_provider(config)
    model = config.get("model", "")
    name = config.get("name", "Worker")
    role = config.get("role", f"You are {name}, a specialized AI assistant.")
    tool_ids = config.get("tools") or []
    max_iter = min(int(config.get("max_iterations", 5)), MAX_ITERATIONS)
    task = _render(config.get("input") or config.get("task", ""), input_data)

    if not task:
        raise ValueError("agent.worker requires 'input' or 'task'")

    tool_descriptions = "\n".join(
        f"- {t}: available tool" for t in tool_ids if t in NODE_HANDLERS
    ) or "No tools available."

    system = (
        f"{role}\n\n"
        "Use this format:\n"
        "Thought: [reasoning]\nAction: [tool_id]\nAction Input: {\"key\": \"value\"}\nObservation: [result]\n"
        "... (repeat)\nFinal Answer: [answer]\n\n"
        f"Available tools:\n{tool_descriptions}"
    )

    context = task
    answer = None

    for _ in range(max_iter):
        if provider == "anthropic":
            response = await _call_anthropic(model, system, context, 1024, 0.1)
        else:
            response = await _call_openai(model, system, context, 1024, 0.1)

        if "Final Answer:" in response:
            answer = response.split("Final Answer:")[-1].strip()
            break

        action_match = re.search(r"Action:\s*([^\n]+)", response)
        action_input_match = re.search(r"Action Input:\s*(\{.*?\})", response, re.DOTALL)

        if action_match and action_input_match:
            tool_id = action_match.group(1).strip()
            try:
                tool_input = json.loads(action_input_match.group(1))
            except Exception:
                tool_input = {"input": action_input_match.group(1)}

            if tool_id in NODE_HANDLERS:
                try:
                    obs = await NODE_HANDLERS[tool_id](tool_input, tool_input, None, db)
                    obs_str = json.dumps(obs) if isinstance(obs, dict) else str(obs)
                except Exception as e:
                    obs_str = f"Error: {e}"
            else:
                obs_str = f"Unknown tool: {tool_id}"

            context = f"{context}\n{response}\nObservation: {obs_str}"
        else:
            answer = response
            break

    return {
        "answer": answer or context,
        "worker": name,
        "task": task,
        "provider": provider,
    }


# ─── Conversational Retrieval Agent ───────────────────────────────────────────

@register_node("agent.conversational_retrieval")
async def agent_conversational_retrieval(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Combines conversation memory with vector store retrieval.
    Maintains session history, condenses follow-up questions, and retrieves context.

    config:
      - vector_store_node: node ID for retrieval (e.g. vectorstore.pgvector.search)
      - session_id: conversation identifier
      - top_k: number of docs to retrieve (default 4)
      - model: LLM model
      - system_prompt: custom system prompt
      - input: user's message
    """
    from core.execution_engine import NODE_HANDLERS
    from integrations.ai.handler import _call_anthropic, _call_openai, _pick_provider

    provider = _pick_provider(config)
    model = config.get("model", "")
    session_id = config.get("session_id") or input_data.get("session_id", "default")
    user_message = _render(config.get("input") or config.get("prompt", ""), input_data)
    top_k = int(config.get("top_k", 4))

    if not user_message:
        raise ValueError("agent.conversational_retrieval requires 'input'")

    # In-memory session store (module-level from agents imports)
    if not hasattr(agent_conversational_retrieval, "_sessions"):
        agent_conversational_retrieval._sessions = {}

    history = agent_conversational_retrieval._sessions.get(session_id, [])

    # Step 1: Condense follow-up question into standalone question
    standalone_question = user_message
    if history:
        hist_str = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
        condense_system = (
            "Given the conversation history and the follow-up question, "
            "rephrase the follow-up question to be a standalone question that includes all necessary context. "
            "Return ONLY the rephrased question, nothing else."
        )
        condense_prompt = f"Conversation:\n{hist_str}\n\nFollow-up: {user_message}\n\nStandalone question:"

        if provider == "anthropic":
            standalone_question = await _call_anthropic(model, condense_system, condense_prompt, 256, 0)
        else:
            standalone_question = await _call_openai(model, condense_system, condense_prompt, 256, 0)
        standalone_question = standalone_question.strip()

    # Step 2: Retrieve relevant documents
    context_docs = []
    retriever_node = config.get("vector_store_node", "")
    if retriever_node and retriever_node in NODE_HANDLERS:
        try:
            retrieval_result = await NODE_HANDLERS[retriever_node](
                {**config, "query": standalone_question, "top_k": top_k},
                {"query": standalone_question},
                credential_id,
                db,
            )
            context_docs = retrieval_result.get("results", retrieval_result.get("documents", []))
        except Exception as e:
            log.warning("retrieval_failed", error=str(e))

    # Step 3: Build answer
    context_str = "\n\n".join(
        d.get("text", d.get("content", str(d))) for d in context_docs
    ) if context_docs else "No relevant documents found."

    hist_str = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
    system = config.get("system_prompt") or (
        "You are a helpful assistant that answers questions based on the provided context. "
        "If the context doesn't contain enough information, say so."
    )
    qa_prompt = (
        f"Context:\n{context_str}\n\n"
        f"{'Conversation history:' + chr(10) + hist_str + chr(10) + chr(10) if hist_str else ''}"
        f"Question: {standalone_question}\n\nAnswer:"
    )

    if provider == "anthropic":
        answer = await _call_anthropic(model, system, qa_prompt, int(config.get("max_tokens", 1024)), 0.3)
    else:
        answer = await _call_openai(model, system, qa_prompt, int(config.get("max_tokens", 1024)), 0.3)

    answer = answer.strip()

    # Update session history
    history.append({"role": "human", "content": user_message})
    history.append({"role": "assistant", "content": answer})
    max_history = int(config.get("max_history", 10))
    agent_conversational_retrieval._sessions[session_id] = history[-max_history * 2:]

    return {
        "answer": answer,
        "standalone_question": standalone_question,
        "source_documents": context_docs,
        "session_id": session_id,
        "history_length": len(history),
        "provider": provider,
    }


# ─── Tool Agent (LangChain-style) ─────────────────────────────────────────────

@register_node("agent.tool_agent")
async def agent_tool_agent(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    ToolAgent: OpenAI-compatible tool-use agent that receives a list of tools
    and autonomously selects and invokes them to complete the task. Similar to
    Flowise's ToolAgent which uses function-calling under the hood.

    config:
      - model: LLM model (default: gpt-4o-mini)
      - tools: list of tool node IDs (e.g. ["tool.calculator", "tool.brave_search"])
      - system_prompt: custom system instructions
      - input/prompt: user task
      - max_iterations: max tool call rounds (default 10)
      - provider: openai (default) or anthropic
    """
    from core.execution_engine import NODE_HANDLERS
    from integrations.ai.handler import _pick_provider

    provider = _pick_provider(config)
    model = config.get("model", "gpt-4o-mini")
    task = _render(config.get("input") or config.get("prompt", ""), input_data)
    tool_ids = config.get("tools") or []
    max_iter = min(int(config.get("max_iterations", 10)), MAX_ITERATIONS)
    system_prompt = config.get("system_prompt", "You are a helpful assistant with access to tools. Use them to complete the task.")

    if not task:
        raise ValueError("agent.tool_agent requires 'input' or 'prompt'")

    # Build tool schemas for function calling
    tool_schemas = [
        {
            "type": "function",
            "function": {
                "name": tid.replace(".", "_"),
                "description": f"Execute the {tid} tool",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "kwargs": {
                            "type": "object",
                            "description": "Input parameters for the tool as key-value pairs",
                        }
                    },
                },
            },
        }
        for tid in tool_ids
        if tid in NODE_HANDLERS
    ]

    if provider == "anthropic":
        # Use Anthropic tool use
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("agent.tool_agent with anthropic provider requires ANTHROPIC_API_KEY")

        anthropic_tools = [
            {
                "name": s["function"]["name"],
                "description": s["function"]["description"],
                "input_schema": s["function"]["parameters"],
            }
            for s in tool_schemas
        ]

        messages = [{"role": "user", "content": task}]
        tool_calls_log = []
        iterations = 0
        final_text = ""

        while iterations < max_iter:
            async with httpx.AsyncClient(timeout=120) as client:
                payload = {
                    "model": model or "claude-3-5-haiku-20241022",
                    "max_tokens": int(config.get("max_tokens", 4096)),
                    "system": system_prompt,
                    "messages": messages,
                }
                if anthropic_tools:
                    payload["tools"] = anthropic_tools

                r = await client.post(
                    ANTHROPIC_API_URL,
                    json=payload,
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                )
                r.raise_for_status()
                data = r.json()

            stop_reason = data.get("stop_reason")
            content_blocks = data.get("content", [])
            messages.append({"role": "assistant", "content": content_blocks})
            iterations += 1

            if stop_reason == "end_turn":
                for block in content_blocks:
                    if block.get("type") == "text":
                        final_text = block["text"]
                break

            if stop_reason == "tool_use":
                tool_results = []
                for block in content_blocks:
                    if block.get("type") == "tool_use":
                        tool_name = block["name"]
                        tool_input = block.get("input", {})
                        tool_id = tool_name.replace("_", ".", 1)
                        tool_kwargs = tool_input.get("kwargs", tool_input)

                        if tool_id in NODE_HANDLERS:
                            try:
                                result = await NODE_HANDLERS[tool_id](tool_kwargs, tool_kwargs, credential_id, db)
                            except Exception as e:
                                result = {"error": str(e)}
                        else:
                            result = {"error": f"Unknown tool: {tool_id}"}

                        tool_calls_log.append({"tool": tool_id, "input": tool_kwargs, "result": result})
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block["id"],
                            "content": json.dumps(result),
                        })

                messages.append({"role": "user", "content": tool_results})
            else:
                for block in content_blocks:
                    if block.get("type") == "text":
                        final_text = block["text"]
                break

        return {
            "answer": final_text,
            "tool_calls": tool_calls_log,
            "iterations": iterations,
            "provider": "anthropic",
            "model": model,
        }

    else:
        # OpenAI-compatible function calling
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("agent.tool_agent requires OPENAI_API_KEY (or set provider=anthropic)")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]
        tool_calls_log = []
        iterations = 0
        final_text = ""

        async with httpx.AsyncClient(timeout=120) as client:
            while iterations < max_iter:
                payload = {
                    "model": model,
                    "messages": messages,
                }
                if tool_schemas:
                    payload["tools"] = tool_schemas
                    payload["tool_choice"] = "auto"

                r = await client.post(
                    OPENAI_API_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                r.raise_for_status()
                data = r.json()

                choice = data["choices"][0]
                msg = choice["message"]
                messages.append(msg)
                iterations += 1

                if choice["finish_reason"] in ("stop", "length"):
                    final_text = msg.get("content", "")
                    break

                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        fn_name = tc["function"]["name"]
                        fn_args = json.loads(tc["function"]["arguments"])
                        tool_id = fn_name.replace("_", ".", 1)
                        tool_kwargs = fn_args.get("kwargs", fn_args)

                        if tool_id in NODE_HANDLERS:
                            try:
                                result = await NODE_HANDLERS[tool_id](tool_kwargs, tool_kwargs, credential_id, db)
                            except Exception as e:
                                result = {"error": str(e)}
                        else:
                            result = {"error": f"Unknown tool: {tool_id}"}

                        tool_calls_log.append({"tool": tool_id, "input": tool_kwargs, "result": result})
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(result),
                        })
                else:
                    final_text = msg.get("content", "")
                    break

        return {
            "answer": final_text,
            "tool_calls": tool_calls_log,
            "iterations": iterations,
            "provider": "openai",
            "model": model,
        }


# ─── LlamaIndex-style Agents ──────────────────────────────────────────────────

@register_node("agent.llamaindex")
async def agent_llamaindex(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    LlamaIndex-compatible agent using our vector store + LLM infrastructure.
    Implements ReAct with retrieval tools, analogous to LlamaIndex's OpenAIAgent.

    config:
      - model: LLM model
      - collections: list of vector store collections to query (as tools)
      - vectorstore_type: inmemory | faiss | chroma | pinecone | qdrant | weaviate
      - top_k: documents to retrieve per query (default 4)
      - tools: additional tool node IDs
      - input/query: user query
      - max_iterations: max reasoning steps
    """
    from core.execution_engine import NODE_HANDLERS
    from integrations.ai.handler import _pick_provider, _call_openai, _call_anthropic

    provider = _pick_provider(config)
    model = config.get("model", "")
    query = _render(config.get("input") or config.get("query") or config.get("prompt", ""), input_data)
    collections = config.get("collections") or []
    vs_type = config.get("vectorstore_type", "inmemory")
    top_k = int(config.get("top_k", 4))
    tool_ids = list(config.get("tools") or [])
    max_iter = min(int(config.get("max_iterations", 8)), MAX_ITERATIONS)

    if not query:
        raise ValueError("agent.llamaindex requires 'input', 'query', or 'prompt'")

    # Build retrieval tools from collections
    async def retrieve_from_collection(coll: str, q: str) -> str:
        query_node = f"vectorstore.{vs_type}.query"
        if query_node in NODE_HANDLERS:
            try:
                result = await NODE_HANDLERS[query_node](
                    {"collection": coll, "query": q, "top_k": top_k},
                    {"query": q},
                    credential_id,
                    db,
                )
                docs = result.get("results", [])
                return "\n\n".join(d.get("content", d.get("text", str(d))) for d in docs)
            except Exception as e:
                return f"[Retrieval error from {coll}: {e}]"
        return f"[Vector store {vs_type} not available]"

    # Initial context retrieval
    context_parts = []
    for coll in collections:
        retrieved = await retrieve_from_collection(coll, query)
        if retrieved:
            context_parts.append(f"[Context from {coll}]:\n{retrieved}")

    context_str = "\n\n".join(context_parts) if context_parts else ""

    # Tool list for agent
    all_tool_ids = [f"vectorstore.{vs_type}.query:{c}" for c in collections] + list(tool_ids)
    tool_desc_lines = [f"- retrieve:{c}: Search the '{c}' knowledge base" for c in collections]
    tool_desc_lines += [f"- {t}: available tool" for t in tool_ids if t in NODE_HANDLERS]
    tools_str = "\n".join(tool_desc_lines) if tool_desc_lines else "No tools available."

    system = config.get("system_prompt") or (
        "You are a knowledgeable assistant with access to retrieval tools.\n"
        "Use the provided context and tools to answer questions accurately.\n\n"
        f"Available tools:\n{tools_str}"
    )

    initial_prompt = (
        f"{('Context:\n' + context_str + chr(10) + chr(10)) if context_str else ''}"
        f"Question: {query}\n\nLet's think step by step:"
    )

    thoughts = []
    final_answer = None
    running_context = initial_prompt

    for iteration in range(max_iter):
        if provider == "anthropic":
            response = await _call_anthropic(model, system, running_context, 2048, 0.1)
        else:
            response = await _call_openai(model, system, running_context, 2048, 0.1)

        thoughts.append(response)

        if "Final Answer:" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
            break

        # Check for retrieval action
        retrieve_match = re.search(r"Action:\s*retrieve:([^\n]+)", response)
        if retrieve_match:
            coll = retrieve_match.group(1).strip()
            q_match = re.search(r"Action Input:\s*([^\n]+)", response)
            sub_query = q_match.group(1).strip() if q_match else query
            retrieved = await retrieve_from_collection(coll, sub_query)
            running_context = f"{running_context}\n{response}\nObservation: {retrieved[:2000]}"
            continue

        # Check for tool action
        action_match = re.search(r"Action:\s*([^\n]+)", response)
        action_input_match = re.search(r"Action Input:\s*(\{.*?\})", response, re.DOTALL)
        if action_match and action_input_match:
            tool_id = action_match.group(1).strip()
            try:
                tool_input = json.loads(action_input_match.group(1))
            except Exception:
                tool_input = {"input": action_input_match.group(1)}

            if tool_id in NODE_HANDLERS:
                try:
                    obs = await NODE_HANDLERS[tool_id](tool_input, tool_input, credential_id, db)
                    obs_str = json.dumps(obs)
                except Exception as e:
                    obs_str = f"Error: {e}"
            else:
                obs_str = f"Unknown tool: {tool_id}"

            running_context = f"{running_context}\n{response}\nObservation: {obs_str}"
        else:
            final_answer = response
            break

    return {
        "answer": final_answer or running_context,
        "thoughts": thoughts,
        "iterations": len(thoughts),
        "collections_used": collections,
        "provider": provider,
        "model": model,
    }
