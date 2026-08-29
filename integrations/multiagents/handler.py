"""
Multi-agent orchestration nodes — Supervisor/Worker pattern.

These nodes implement multi-agent coordination where a Supervisor LLM decides
which Worker agent to invoke next, and Workers execute specialized tasks.
Equivalent to Flowise's multiagents/Supervisor and multiagents/Worker.

Nodes:
  multiagent.supervisor   — LLM supervisor that routes tasks to workers
  multiagent.worker       — Specialized worker agent with its own tools/prompt
"""
import json
import re

import httpx
import structlog

from core.execution_engine import register_node, NODE_HANDLERS
from core.config import settings

log = structlog.get_logger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MAX_SUPERVISOR_ROUNDS = 20


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


async def _call_openai(model: str, system: str, messages: list[dict], max_tokens: int = 1024) -> str:
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY required for multiagent.supervisor")
    payload = {
        "model": model or "gpt-4o",
        "max_tokens": max_tokens,
        "messages": [{"role": "system", "content": system}] + messages,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(OPENAI_API_URL, headers={"Authorization": f"Bearer {api_key}"}, json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def _call_anthropic(model: str, system: str, messages: list[dict], max_tokens: int = 1024) -> str:
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY required for multiagent.supervisor")
    payload = {
        "model": model or "claude-3-5-haiku-20241022",
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            ANTHROPIC_API_URL,
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            json=payload,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]


async def _call_llm(provider: str, model: str, system: str, messages: list[dict], max_tokens: int = 1024) -> str:
    if provider == "anthropic":
        return await _call_anthropic(model, system, messages, max_tokens)
    return await _call_openai(model, system, messages, max_tokens)


# ─── Supervisor ───────────────────────────────────────────────────────────────

@register_node("multiagent.supervisor")
async def multiagent_supervisor(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Supervisor node: orchestrates a team of worker agents. The supervisor LLM
    receives the task and decides which worker to call, passing results back
    until the task is complete. Equivalent to Flowise's
    multiagents/Supervisor/Supervisor.ts.

    config:
      - provider: openai | anthropic (default: openai)
      - model: supervisor LLM model
      - system_prompt: supervisor instructions (supports {{ }} templates)
      - workers: list of worker configs, each with:
          - name: worker name (used to route tasks)
          - node_id: registered node ID of the worker (e.g. "multiagent.worker")
          - description: what this worker can do (shown to supervisor)
          - config: config to pass to the worker node
      - task: the task description (supports {{ }} templates)
      - max_rounds: max supervisor/worker rounds (default: 10)
    """
    provider = config.get("provider", "openai")
    model = config.get("model", "")
    workers_cfg = config.get("workers") or []
    task = _render(config.get("task") or config.get("input", ""), input_data) or json.dumps(input_data)
    max_rounds = min(int(config.get("max_rounds", 10)), MAX_SUPERVISOR_ROUNDS)

    # Build worker roster description
    worker_descs = []
    for w in workers_cfg:
        worker_descs.append(f"- {w['name']}: {w.get('description', 'A specialized worker')}")

    roster = "\n".join(worker_descs) if worker_descs else "No workers available."

    system_prompt = _render(config.get("system_prompt", ""), input_data) or (
        "You are a supervisor orchestrating a team of specialized worker agents.\n"
        "Your job is to break down complex tasks, delegate to the right workers, "
        "and synthesize their outputs into a final answer.\n\n"
        f"Available workers:\n{roster}\n\n"
        "To delegate to a worker, respond with:\n"
        "DELEGATE TO: <worker_name>\n"
        "TASK: <specific task for that worker>\n\n"
        "When the task is complete, respond with:\n"
        "FINAL ANSWER: <your complete answer>"
    )

    messages: list[dict] = [{"role": "user", "content": f"Task: {task}"}]
    conversation_history: list[dict] = []
    final_answer = None

    for round_num in range(max_rounds):
        response = await _call_llm(provider, model, system_prompt, messages)
        conversation_history.append({"round": round_num + 1, "supervisor": response})
        messages.append({"role": "assistant", "content": response})

        # Check for FINAL ANSWER
        final_match = re.search(r"FINAL ANSWER:\s*(.+)", response, re.DOTALL | re.IGNORECASE)
        if final_match:
            final_answer = final_match.group(1).strip()
            break

        # Check for DELEGATE TO
        delegate_match = re.search(
            r"DELEGATE TO:\s*(\S+.*?)\nTASK:\s*(.+?)(?=\nDELEGATE TO:|FINAL ANSWER:|$)",
            response, re.DOTALL | re.IGNORECASE,
        )
        if delegate_match:
            worker_name = delegate_match.group(1).strip()
            worker_task = delegate_match.group(2).strip()

            # Find the worker config
            worker_cfg = next(
                (w for w in workers_cfg if w["name"].lower() == worker_name.lower()),
                None,
            )

            if worker_cfg:
                worker_node_id = worker_cfg.get("node_id", "multiagent.worker")
                worker_config = {
                    **worker_cfg.get("config", {}),
                    "task": worker_task,
                    "worker_name": worker_cfg["name"],
                }
                if worker_node_id in NODE_HANDLERS:
                    try:
                        worker_result = await NODE_HANDLERS[worker_node_id](
                            worker_config, {**input_data, "task": worker_task}, credential_id, db
                        )
                        observation = worker_result.get("output") or json.dumps(worker_result)
                        conversation_history[-1]["worker_name"] = worker_name
                        conversation_history[-1]["worker_result"] = worker_result
                    except Exception as e:
                        observation = f"Worker error: {e}"
                        log.warning("worker_error", worker=worker_name, error=str(e))
                else:
                    observation = f"Worker '{worker_name}' node not found."
            else:
                observation = f"No worker named '{worker_name}' found in roster."

            messages.append({"role": "user", "content": f"Worker result:\n{observation}"})
        else:
            # No delegation pattern found; treat response as final
            final_answer = response
            break

    return {
        **input_data,
        "supervisor_output": final_answer or response,
        "conversation_history": conversation_history,
        "rounds_completed": round_num + 1,
        "task": task,
    }


# ─── Worker ───────────────────────────────────────────────────────────────────

@register_node("multiagent.worker")
async def multiagent_worker(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Worker node: a specialized agent that executes a specific task within a
    multi-agent system. Receives tasks from the Supervisor and returns results.
    Equivalent to Flowise's multiagents/Worker/Worker.ts.

    config:
      - worker_name: name of this worker (informational)
      - provider: openai | anthropic (default: openai)
      - model: LLM model
      - system_prompt: worker's specialization prompt (supports {{ }} templates)
      - tools: list of tool node IDs available to this worker
      - max_tool_iterations: max tool-use loops (default: 5)
      - task: task to execute (supports {{ }} templates, or from input_data.task)
    """
    worker_name = config.get("worker_name", "Worker")
    provider = config.get("provider", "openai")
    model = config.get("model", "")
    system_prompt = _render(
        config.get("system_prompt", f"You are {worker_name}, a specialized AI assistant."),
        input_data,
    )
    tool_ids = config.get("tools") or []
    max_tool_iter = int(config.get("max_tool_iterations", 5))
    task = _render(config.get("task", ""), input_data) or input_data.get("task", json.dumps(input_data))

    # Build available tool descriptions
    tool_descriptions = []
    for tid in tool_ids:
        if tid in NODE_HANDLERS:
            tool_descriptions.append(f"  - {tid}")

    if tool_descriptions:
        system_prompt += (
            "\n\nAvailable tools (use by responding with 'Tool: <id>\\nInput: <json>'):\n"
            + "\n".join(tool_descriptions)
        )

    messages: list[dict] = [{"role": "user", "content": task}]
    tool_calls_log = []

    for _ in range(max_tool_iter):
        response = await _call_llm(provider, model, system_prompt, messages)
        messages.append({"role": "assistant", "content": response})

        # Check for tool invocation
        tool_match = re.search(r"Tool:\s*(\S+)\s*\nInput:\s*(\{.*?\})", response, re.DOTALL)
        if tool_match and tool_match.group(1) in NODE_HANDLERS:
            tool_id = tool_match.group(1)
            try:
                tool_args = json.loads(tool_match.group(2))
            except json.JSONDecodeError:
                tool_args = {}
            try:
                tool_result = await NODE_HANDLERS[tool_id](tool_args, tool_args, credential_id, db)
                observation = json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
                tool_calls_log.append({"tool": tool_id, "args": tool_args, "result": tool_result})
            except Exception as e:
                observation = f"Tool error: {e}"
            messages.append({"role": "user", "content": f"Tool result: {observation}"})
        else:
            # Final response
            break

    return {
        "output": response,
        "worker_name": worker_name,
        "tool_calls": tool_calls_log,
        "task": task,
    }
