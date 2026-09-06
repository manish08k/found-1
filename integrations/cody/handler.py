"""Sourcegraph Cody AI coding assistant integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

SOURCEGRAPH_GRAPHQL = "https://sourcegraph.com/.api/graphql"
SOURCEGRAPH_COMPLETIONS = "https://sourcegraph.com/.api/completions/stream"


@register_node("cody.complete")
async def cody_complete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate a code completion using Sourcegraph Cody.

    config/input_data:
      access_token — Sourcegraph access token
      prompt       — code context / prompt for completion
      model        — optional model name (default: anthropic/claude-3-5-sonnet-20241022)
      max_tokens   — optional max tokens to generate (default 256)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    if not access_token:
        raise ValueError("access_token is required")
    prompt = merged.get("prompt", "")
    if not prompt:
        raise ValueError("prompt is required")

    payload = {
        "model": merged.get("model", "anthropic/claude-3-5-sonnet-20241022"),
        "messages": [{"speaker": "human", "text": prompt}],
        "maxTokensToSample": merged.get("max_tokens", 256),
        "temperature": merged.get("temperature", 0.2),
        "topK": merged.get("top_k", -1),
        "topP": merged.get("top_p", -1),
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            SOURCEGRAPH_COMPLETIONS,
            headers={
                "Authorization": f"token {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("cody.complete")
    return result


@register_node("cody.chat")
async def cody_chat(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Send a chat message to Sourcegraph Cody.

    config/input_data:
      access_token — Sourcegraph access token
      message      — user chat message
      context_files — optional list of file paths to include as context
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    if not access_token:
        raise ValueError("access_token is required")
    message = merged.get("message", "")
    if not message:
        raise ValueError("message is required")

    # Use Cody chat completions via the completions API
    payload = {
        "model": merged.get("model", "anthropic/claude-3-5-sonnet-20241022"),
        "messages": [
            {"speaker": "human", "text": message},
        ],
        "maxTokensToSample": merged.get("max_tokens", 1000),
        "temperature": merged.get("temperature", 0.2),
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            SOURCEGRAPH_COMPLETIONS,
            headers={
                "Authorization": f"token {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
        )
        r.raise_for_status()
        result = r.json()

    log.info("cody.chat")
    return result


@register_node("cody.search_code")
async def cody_search_code(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Search code across Sourcegraph repositories.

    config/input_data:
      access_token — Sourcegraph access token
      query        — Sourcegraph search query (supports regex and filters)
      count        — optional max results (default 10)
    """
    merged = {**config, **input_data}
    access_token = merged.get("access_token", "")
    if not access_token:
        raise ValueError("access_token is required")
    query = merged.get("query", "")
    if not query:
        raise ValueError("query is required")

    count = merged.get("count", 10)

    graphql_query = """
    query SearchCode($query: String!, $count: Int!) {
      search(query: $query, version: V2, patternType: standard) {
        results {
          resultCount
          approximateResultCount
          results {
            ... on FileMatch {
              __typename
              repository {
                name
              }
              file {
                path
                url
              }
              lineMatches {
                lineNumber
                preview
              }
            }
          }
        }
      }
    }
    """

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            SOURCEGRAPH_GRAPHQL,
            headers={
                "Authorization": f"token {access_token}",
                "Content-Type": "application/json",
            },
            json={"query": graphql_query, "variables": {"query": query, "count": count}},
        )
        r.raise_for_status()
        result = r.json()

    log.info("cody.search_code", query=query)
    return result
