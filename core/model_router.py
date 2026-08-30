"""
Model Router — intelligent model selection based on cost, latency, and capability.

Provides:
  - route_model: pick best model given budget and requirements
  - get_fallback_model: cheaper alternative for a given model
"""
from core.cost_tracker import MODEL_PRICING, calculate_cost


# Capability tiers (higher = more capable)
MODEL_CAPABILITY: dict[str, int] = {
    "gpt-4o": 90,
    "gpt-4-turbo": 85,
    "gpt-4": 85,
    "claude-opus-4-6": 95,
    "claude-sonnet-4-6": 88,
    "claude-3-5-sonnet-20241022": 88,
    "claude-3-opus-20240229": 92,
    "o1": 95,
    "o1-mini": 80,
    "o3-mini": 82,
    "gemini-1.5-pro": 85,
    "gpt-4o-mini": 75,
    "gpt-3.5-turbo": 65,
    "claude-3-5-haiku-20241022": 70,
    "claude-3-haiku-20240307": 60,
    "gemini-1.5-flash": 70,
    "gemini-2.0-flash": 72,
    "mistral-large-latest": 80,
    "mistral-small-latest": 65,
    "llama-3.1-70b-versatile": 75,
    "llama-3.1-8b-instant": 55,
}

# Fallback chain: model -> cheaper alternative
FALLBACK_CHAIN: dict[str, str] = {
    "gpt-4o": "gpt-4o-mini",
    "gpt-4-turbo": "gpt-4o-mini",
    "gpt-4": "gpt-4o-mini",
    "claude-opus-4-6": "claude-sonnet-4-6",
    "claude-sonnet-4-6": "claude-3-5-haiku-20241022",
    "claude-3-5-sonnet-20241022": "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229": "claude-3-5-haiku-20241022",
    "o1": "o3-mini",
    "o1-mini": "gpt-4o-mini",
    "gemini-1.5-pro": "gemini-1.5-flash",
    "mistral-large-latest": "mistral-small-latest",
    "llama-3.1-70b-versatile": "llama-3.1-8b-instant",
}


def get_fallback_model(model: str) -> str:
    """Return a cheaper fallback for the given model."""
    return FALLBACK_CHAIN.get(model, model)


def route_model(
    preferred_model: str,
    budget_usd: float | None = None,
    requirements: dict | None = None,
    available_models: list[str] | None = None,
) -> dict:
    """
    Pick the best model given constraints.

    Args:
        preferred_model: User's preferred model
        budget_usd: Max budget in USD for this call (estimated based on ~1K tokens)
        requirements: Optional dict with keys:
            - min_capability: minimum capability tier (0-100)
            - prefer: "cost" | "latency" | "capability"
        available_models: List of models to choose from (default: all known)

    Returns:
        {"model": str, "reason": str, "estimated_cost_1k": float}
    """
    reqs = requirements or {}
    min_capability = reqs.get("min_capability", 0)
    prefer = reqs.get("prefer", "capability")

    candidates = available_models or list(MODEL_PRICING.keys())
    # Filter out embedding models
    candidates = [m for m in candidates if not m.startswith("text-embedding")]

    # Score each candidate
    scored = []
    for model in candidates:
        capability = MODEL_CAPABILITY.get(model, 50)
        if capability < min_capability:
            continue

        pricing = MODEL_PRICING.get(model)
        if not pricing:
            continue

        # Estimate cost for ~1K input + 500 output tokens
        est_cost = calculate_cost(model, 1000, 500)

        if budget_usd is not None and est_cost > budget_usd:
            continue

        # Composite score based on preference
        if prefer == "cost":
            # Lower cost = higher score
            score = 1.0 / (est_cost + 0.0001)
        elif prefer == "latency":
            # Smaller/cheaper models tend to be faster
            score = (1.0 / (est_cost + 0.0001)) * 0.7 + capability * 0.3
        else:
            # Default: maximize capability within budget
            score = capability * 0.8 + (1.0 / (est_cost + 0.0001)) * 0.2

        scored.append((model, score, est_cost, capability))

    if not scored:
        # No model fits constraints, return preferred with warning
        est = calculate_cost(preferred_model, 1000, 500)
        return {
            "model": preferred_model,
            "reason": "No model matched constraints; using preferred model",
            "estimated_cost_1k": round(est, 6),
        }

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    best = scored[0]

    # If preferred model is among candidates and scores within 10% of best, prefer it
    for entry in scored:
        if entry[0] == preferred_model and entry[1] >= best[1] * 0.9:
            return {
                "model": preferred_model,
                "reason": "Preferred model meets all constraints",
                "estimated_cost_1k": round(entry[2], 6),
            }

    return {
        "model": best[0],
        "reason": f"Selected based on {prefer} optimization (capability={best[3]}, cost=${best[2]:.4f}/1k)",
        "estimated_cost_1k": round(best[2], 6),
    }
