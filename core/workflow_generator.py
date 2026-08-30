"""
AI Workflow Builder — generate workflow graphs from natural language prompts.

Uses an LLM (OpenAI or Anthropic) with a system prompt that includes available
node types and schema format, to produce a valid workflow JSON definition.
"""
import json
import re

import httpx
import structlog

from core.config import settings
from core.execution_engine import NODE_HANDLERS

log = structlog.get_logger(__name__)


def _get_available_node_types() -> list[str]:
    """Return all registered node type names."""
    return sorted(NODE_HANDLERS.keys())


async def generate_workflow_from_prompt(
    prompt: str,
    existing_workflow: dict | None = None,
    settings_override: dict | None = None,
) -> dict:
    """
    Use an LLM to generate a workflow JSON from a natural language description.

    Returns: {"nodes": [...], "edges": [...], "explanation": "..."}
    """
    node_types = _get_available_node_types()
    node_types_str = ", ".join(node_types[:100])  # Limit to avoid token overflow

    system_prompt = (
        "You are an expert workflow builder for AutoFlow, a workflow automation platform.\n"
        "Generate a workflow definition as a JSON object with 'nodes' and 'edges' arrays.\n\n"
        "Each node has:\n"
        '  {"id": "unique_id", "type": "node.type", "config": {...}, "required": true}\n\n'
        "Each edge has:\n"
        '  {"source": "node_id", "target": "node_id"}\n\n'
        f"Available node types: {node_types_str}\n\n"
        "Common patterns:\n"
        "- ai.chat: LLM prompt with system_prompt, prompt, provider, model\n"
        "- ai.extract: Extract structured JSON from text\n"
        "- http.request: HTTP calls with method, url, headers, body\n"
        "- core.condition: Branch on field/operator/value\n"
        "- core.transform: Reshape data with mapping dict\n"
        "- slack.send_message: Post to Slack with channel, text\n"
        "- core.delay: Wait N seconds\n\n"
        "Rules:\n"
        "1. Use ONLY node types from the available list above\n"
        "2. Every edge source/target must reference an existing node ID\n"
        "3. The graph must be a DAG (no cycles unless using agentflow.loop)\n"
        "4. Config fields should use {{field}} for referencing upstream outputs\n"
        "5. Include an 'explanation' field describing what the workflow does\n\n"
        "Respond with ONLY a valid JSON object. No markdown, no commentary."
    )

    user_prompt = f"Build a workflow for: {prompt}"
    if existing_workflow:
        user_prompt += f"\n\nExisting workflow to modify:\n{json.dumps(existing_workflow, indent=2)[:3000]}"

    # Call LLM
    if settings.ANTHROPIC_API_KEY:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 4096,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            )
            r.raise_for_status()
            raw = r.json()["content"][0]["text"]
    elif settings.OPENAI_API_KEY:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={
                    "model": "gpt-4o",
                    "max_tokens": 4096,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"]
    else:
        raise ValueError("No AI provider configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.")

    # Parse JSON from response
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return {
            "nodes": [],
            "edges": [],
            "explanation": f"Failed to parse LLM response as JSON: {e}",
            "raw_response": raw,
        }

    # Ensure required fields
    if "nodes" not in result:
        result["nodes"] = []
    if "edges" not in result:
        result["edges"] = []
    if "explanation" not in result:
        result["explanation"] = "Workflow generated from prompt."

    return result


def validate_workflow_graph(nodes: list[dict], edges: list[dict]) -> dict:
    """
    Validate a proposed workflow graph for correctness.

    Returns: {"valid": bool, "errors": [...], "warnings": [...]}
    """
    errors = []
    warnings = []

    node_ids = {n.get("id") for n in nodes if n.get("id")}

    # Check all node types are valid
    for node in nodes:
        node_type = node.get("type", "")
        if node_type not in NODE_HANDLERS:
            errors.append(f"Unknown node type '{node_type}' on node '{node.get('id')}'")
        if not node.get("id"):
            errors.append("Node missing 'id' field")

    # Check all edge references exist
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source not in node_ids:
            errors.append(f"Edge source '{source}' does not exist in nodes")
        if target not in node_ids:
            errors.append(f"Edge target '{target}' does not exist in nodes")

    # Check for cycles using topological sort
    if not errors:
        try:
            from core.execution_engine import topological_sort
            topological_sort(nodes, edges)
        except ValueError as e:
            if "cycle" in str(e).lower():
                # Check if it's an intentional loop node
                loop_nodes = {n["id"] for n in nodes if n.get("type") == "agentflow.loop"}
                if not loop_nodes:
                    errors.append(str(e))
                else:
                    warnings.append(f"Graph has cycles, but loop nodes are present: {loop_nodes}")

    # Check for orphan nodes (no edges)
    if len(nodes) > 1:
        connected = set()
        for edge in edges:
            connected.add(edge.get("source"))
            connected.add(edge.get("target"))
        orphans = node_ids - connected
        for orphan in orphans:
            warnings.append(f"Node '{orphan}' has no connections")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
