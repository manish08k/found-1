"""GraphQL integration — send queries and mutations to any GraphQL endpoint."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _build_headers(config: dict, credential_id: str | None, db) -> dict:
    """Build request headers, optionally adding Bearer auth from credential."""
    headers: dict = {"Content-Type": "application/json", "Accept": "application/json"}

    # Merge any user-supplied headers first
    extra_headers = config.get("headers") or {}
    headers.update(extra_headers)

    # Add Bearer token from credential if provided
    if credential_id:
        try:
            creds = await get_credential_data(credential_id, db)
            token = (
                creds.get("access_token")
                or creds.get("token")
                or creds.get("api_key")
                or creds.get("bearer_token")
            )
            if token:
                headers["Authorization"] = f"Bearer {token}"
        except Exception as exc:
            log.warning("graphql.credential_fetch_failed", error=str(exc))

    return headers


@register_node("graphql.query")
async def graphql_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Execute a GraphQL query against any endpoint.

    config/input_data:
      endpoint   — full GraphQL endpoint URL (required)
      query      — GraphQL query string (required)
      variables  — dict of query variables (optional)
      operation  — operation name (optional)
      headers    — additional HTTP headers dict (optional)
      timeout    — request timeout in seconds (default 30)

    If a credential is provided, its access_token/api_key is sent as Bearer auth.
    """
    endpoint = config.get("endpoint") or input_data.get("endpoint")
    if not endpoint:
        raise ValueError("endpoint is required for graphql.query")

    query_str = config.get("query") or input_data.get("query")
    if not query_str:
        raise ValueError("query is required for graphql.query")

    variables = config.get("variables") or input_data.get("variables") or {}
    operation = config.get("operation") or input_data.get("operation")
    timeout = float(config.get("timeout", 30))

    headers = await _build_headers(config, credential_id, db)

    payload: dict = {"query": query_str, "variables": variables}
    if operation:
        payload["operationName"] = operation

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(endpoint, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()

    errors = data.get("errors")
    result_data = data.get("data", {})

    if errors:
        log.warning("graphql.query_errors", endpoint=endpoint, errors=errors)

    log.info("graphql.query", endpoint=endpoint, operation=operation, has_errors=bool(errors))
    return {
        "data": result_data,
        "errors": errors,
        "status_code": r.status_code,
        "endpoint": endpoint,
    }


@register_node("graphql.mutation")
async def graphql_mutation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Execute a GraphQL mutation against any endpoint.

    config/input_data:
      endpoint   — full GraphQL endpoint URL (required)
      mutation   — GraphQL mutation string (required); can also be key 'query'
      variables  — dict of mutation variables (optional)
      operation  — operation name (optional)
      headers    — additional HTTP headers dict (optional)
      timeout    — request timeout in seconds (default 30)

    If a credential is provided, its access_token/api_key is sent as Bearer auth.
    """
    endpoint = config.get("endpoint") or input_data.get("endpoint")
    if not endpoint:
        raise ValueError("endpoint is required for graphql.mutation")

    # Accept both 'mutation' and 'query' keys — GraphQL protocol uses 'query' for both
    mutation_str = (
        config.get("mutation")
        or input_data.get("mutation")
        or config.get("query")
        or input_data.get("query")
    )
    if not mutation_str:
        raise ValueError("mutation (or query) is required for graphql.mutation")

    variables = config.get("variables") or input_data.get("variables") or {}
    operation = config.get("operation") or input_data.get("operation")
    timeout = float(config.get("timeout", 30))

    headers = await _build_headers(config, credential_id, db)

    payload: dict = {"query": mutation_str, "variables": variables}
    if operation:
        payload["operationName"] = operation

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(endpoint, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()

    errors = data.get("errors")
    result_data = data.get("data", {})

    if errors:
        log.warning("graphql.mutation_errors", endpoint=endpoint, errors=errors)

    log.info("graphql.mutation", endpoint=endpoint, operation=operation, has_errors=bool(errors))
    return {
        "data": result_data,
        "errors": errors,
        "status_code": r.status_code,
        "endpoint": endpoint,
        "success": not bool(errors),
    }
