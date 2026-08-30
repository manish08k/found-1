"""
AI Cost Tracker — records and analyzes LLM API usage costs.

Maintains a pricing table for popular models and provides:
  - Per-call cost calculation
  - Per-execution cost recording
  - Aggregate analytics over time
"""
from datetime import datetime, timedelta
from typing import Optional

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import ExecutionCost

log = structlog.get_logger(__name__)

# ─── Pricing Table (per million tokens, in USD) ──────────────────────────────
# Updated periodically. Prices stored as (input_price_per_M, output_price_per_M).

MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o3-mini": (1.10, 4.40),
    # Anthropic
    "claude-opus-4-6": (15.00, 75.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "claude-3-opus-20240229": (15.00, 75.00),
    "claude-3-haiku-20240307": (0.25, 1.25),
    # Google
    "gemini-1.5-pro": (3.50, 10.50),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
    # Mistral
    "mistral-large-latest": (2.00, 6.00),
    "mistral-small-latest": (0.20, 0.60),
    # Groq (hosted)
    "llama-3.1-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant": (0.05, 0.08),
    # Embeddings (per million tokens, output is 0)
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
    "text-embedding-ada-002": (0.10, 0.0),
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate estimated cost in USD for a given model and token usage.
    Returns cost in USD (floating point).
    """
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        # Try prefix matching (e.g. "gpt-4o-2024-08-06" -> "gpt-4o")
        for known_model, prices in MODEL_PRICING.items():
            if model.startswith(known_model):
                pricing = prices
                break

    if not pricing:
        # Unknown model — estimate based on a mid-range default
        pricing = (1.00, 3.00)
        log.debug("unknown_model_pricing", model=model, using_default=True)

    input_cost = (input_tokens / 1_000_000) * pricing[0]
    output_cost = (output_tokens / 1_000_000) * pricing[1]
    return input_cost + output_cost


async def record_cost(
    execution_id: str | None,
    node_id: str | None,
    node_type: str | None,
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    db: AsyncSession,
) -> ExecutionCost:
    """Record a single LLM call's cost to the database."""
    total_tokens = input_tokens + output_tokens
    cost_usd = calculate_cost(model, input_tokens, output_tokens)
    # Store as microdollars for integer precision
    cost_microdollars = int(cost_usd * 1_000_000)

    cost_record = ExecutionCost(
        execution_id=execution_id,
        node_id=node_id,
        node_type=node_type,
        model=model,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=cost_microdollars,
        latency_ms=latency_ms,
    )
    db.add(cost_record)
    return cost_record


async def get_execution_cost_summary(execution_id: str, db: AsyncSession) -> dict:
    """Get total cost breakdown for a single execution."""
    result = await db.execute(
        select(ExecutionCost).where(ExecutionCost.execution_id == execution_id)
    )
    costs = result.scalars().all()

    if not costs:
        return {
            "execution_id": execution_id,
            "total_cost_usd": 0.0,
            "total_tokens": 0,
            "node_costs": [],
        }

    total_microdollars = sum(c.estimated_cost_usd or 0 for c in costs)
    total_tokens = sum(c.total_tokens or 0 for c in costs)

    node_costs = [
        {
            "node_id": c.node_id,
            "node_type": c.node_type,
            "model": c.model,
            "provider": c.provider,
            "input_tokens": c.input_tokens,
            "output_tokens": c.output_tokens,
            "total_tokens": c.total_tokens,
            "cost_usd": round((c.estimated_cost_usd or 0) / 1_000_000, 6),
            "latency_ms": c.latency_ms,
        }
        for c in costs
    ]

    return {
        "execution_id": execution_id,
        "total_cost_usd": round(total_microdollars / 1_000_000, 6),
        "total_tokens": total_tokens,
        "node_costs": node_costs,
    }


async def get_workflow_cost_analytics(
    workflow_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = None,
) -> dict:
    """Aggregate cost analytics for a workflow over a time period."""
    from storage.models import Execution

    # Get execution IDs for this workflow
    stmt = select(Execution.id).where(Execution.workflow_id == workflow_id)
    if start_date:
        stmt = stmt.where(Execution.created_at >= start_date)
    if end_date:
        stmt = stmt.where(Execution.created_at <= end_date)

    exec_result = await db.execute(stmt)
    execution_ids = [r[0] for r in exec_result.all()]

    if not execution_ids:
        return {
            "workflow_id": workflow_id,
            "total_cost_usd": 0.0,
            "total_tokens": 0,
            "execution_count": 0,
            "by_model": {},
        }

    # Aggregate costs
    cost_result = await db.execute(
        select(
            ExecutionCost.model,
            ExecutionCost.provider,
            func.sum(ExecutionCost.input_tokens).label("total_input"),
            func.sum(ExecutionCost.output_tokens).label("total_output"),
            func.sum(ExecutionCost.total_tokens).label("total_tokens"),
            func.sum(ExecutionCost.estimated_cost_usd).label("total_cost"),
            func.count(ExecutionCost.id).label("call_count"),
        )
        .where(ExecutionCost.execution_id.in_(execution_ids))
        .group_by(ExecutionCost.model, ExecutionCost.provider)
    )
    rows = cost_result.all()

    by_model = {}
    total_cost = 0
    total_tokens = 0

    for row in rows:
        model_key = f"{row.provider}/{row.model}" if row.provider else row.model
        cost = row.total_cost or 0
        tokens = row.total_tokens or 0
        by_model[model_key] = {
            "input_tokens": row.total_input or 0,
            "output_tokens": row.total_output or 0,
            "total_tokens": tokens,
            "cost_usd": round(cost / 1_000_000, 6),
            "call_count": row.call_count,
        }
        total_cost += cost
        total_tokens += tokens

    return {
        "workflow_id": workflow_id,
        "total_cost_usd": round(total_cost / 1_000_000, 6),
        "total_tokens": total_tokens,
        "execution_count": len(execution_ids),
        "by_model": by_model,
    }
