"""Saleor integration — products, orders, and customers via GraphQL."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _saleor_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _graphql_url(api_url: str) -> str:
    return api_url.rstrip("/") + "/graphql/"


@register_node("saleor.list_products")
async def saleor_list_products(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List products from a Saleor store via GraphQL.

    config:
      api_url — Saleor store URL e.g. https://mystore.saleor.cloud (required)
      token   — Saleor auth token (required)
      first   — number of products to fetch (optional, default 20)
      channel — channel slug to filter by (optional)
    """
    merged = {**config, **input_data}
    api_url = merged.get("api_url", "")
    token = merged.get("token", "")
    if not api_url or not token:
        raise ValueError("api_url and token are required for saleor.list_products")

    first = merged.get("first", 20)
    channel_filter = f', channel: "{merged["channel"]}"' if merged.get("channel") else ""

    query = f"""
    query {{
      products(first: {first}{channel_filter}) {{
        edges {{
          node {{
            id
            name
            slug
            isAvailable
            pricing {{
              priceRange {{
                start {{ gross {{ amount currency }} }}
              }}
            }}
          }}
        }}
        pageInfo {{ hasNextPage endCursor }}
      }}
    }}
    """

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            _graphql_url(api_url),
            headers=_saleor_headers(token),
            json={"query": query},
        )
        r.raise_for_status()
        data = r.json()

    if data.get("errors"):
        raise RuntimeError(f"GraphQL errors: {data['errors']}")

    edges = data.get("data", {}).get("products", {}).get("edges", [])
    products = [e["node"] for e in edges]
    log.info("saleor.list_products", count=len(products))
    return {"products": products, "count": len(products)}


@register_node("saleor.get_product")
async def saleor_get_product(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Saleor product by ID.

    config:
      api_url    — Saleor store URL (required)
      token      — Saleor auth token (required)
      product_id — product global ID (required)
    """
    merged = {**config, **input_data}
    api_url = merged.get("api_url", "")
    token = merged.get("token", "")
    product_id = merged.get("product_id")
    if not api_url or not token or not product_id:
        raise ValueError("api_url, token, and product_id are required")

    query = f"""
    query {{
      product(id: "{product_id}") {{
        id name slug description isAvailable
        category {{ id name }}
        variants {{ id name sku stockQuantity }}
      }}
    }}
    """

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            _graphql_url(api_url),
            headers=_saleor_headers(token),
            json={"query": query},
        )
        r.raise_for_status()
        data = r.json()

    if data.get("errors"):
        raise RuntimeError(f"GraphQL errors: {data['errors']}")

    product = data.get("data", {}).get("product")
    log.info("saleor.get_product", product_id=product_id)
    return {"product": product, "product_id": product_id}


@register_node("saleor.list_orders")
async def saleor_list_orders(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List orders from a Saleor store.

    config:
      api_url — Saleor store URL (required)
      token   — Saleor auth token (required)
      first   — number of orders to fetch (optional, default 20)
      status  — filter by status e.g. UNFULFILLED (optional)
    """
    merged = {**config, **input_data}
    api_url = merged.get("api_url", "")
    token = merged.get("token", "")
    if not api_url or not token:
        raise ValueError("api_url and token are required")

    first = merged.get("first", 20)
    filter_arg = ""
    if merged.get("status"):
        filter_arg = f', filter: {{ status: {merged["status"]} }}'

    query = f"""
    query {{
      orders(first: {first}{filter_arg}) {{
        edges {{
          node {{
            id number status created total {{ gross {{ amount currency }} }}
            userEmail
          }}
        }}
        pageInfo {{ hasNextPage endCursor }}
      }}
    }}
    """

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            _graphql_url(api_url),
            headers=_saleor_headers(token),
            json={"query": query},
        )
        r.raise_for_status()
        data = r.json()

    if data.get("errors"):
        raise RuntimeError(f"GraphQL errors: {data['errors']}")

    edges = data.get("data", {}).get("orders", {}).get("edges", [])
    orders = [e["node"] for e in edges]
    log.info("saleor.list_orders", count=len(orders))
    return {"orders": orders, "count": len(orders)}


@register_node("saleor.get_order")
async def saleor_get_order(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a specific Saleor order by ID.

    config:
      api_url  — Saleor store URL (required)
      token    — Saleor auth token (required)
      order_id — order global ID (required)
    """
    merged = {**config, **input_data}
    api_url = merged.get("api_url", "")
    token = merged.get("token", "")
    order_id = merged.get("order_id")
    if not api_url or not token or not order_id:
        raise ValueError("api_url, token, and order_id are required")

    query = f"""
    query {{
      order(id: "{order_id}") {{
        id number status created userEmail
        total {{ gross {{ amount currency }} }}
        lines {{ id productName variantName quantity unitPrice {{ gross {{ amount currency }} }} }}
        shippingAddress {{ firstName lastName streetAddress1 city country {{ code }} }}
      }}
    }}
    """

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            _graphql_url(api_url),
            headers=_saleor_headers(token),
            json={"query": query},
        )
        r.raise_for_status()
        data = r.json()

    if data.get("errors"):
        raise RuntimeError(f"GraphQL errors: {data['errors']}")

    order = data.get("data", {}).get("order")
    log.info("saleor.get_order", order_id=order_id)
    return {"order": order, "order_id": order_id}


@register_node("saleor.list_customers")
async def saleor_list_customers(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List customers from a Saleor store.

    config:
      api_url — Saleor store URL (required)
      token   — Saleor auth token (required)
      first   — number of customers to fetch (optional, default 20)
      search  — search by email/name (optional)
    """
    merged = {**config, **input_data}
    api_url = merged.get("api_url", "")
    token = merged.get("token", "")
    if not api_url or not token:
        raise ValueError("api_url and token are required")

    first = merged.get("first", 20)
    filter_arg = ""
    if merged.get("search"):
        filter_arg = f', filter: {{ search: "{merged["search"]}" }}'

    query = f"""
    query {{
      customers(first: {first}{filter_arg}) {{
        edges {{
          node {{
            id email firstName lastName dateJoined isActive
            orders {{ totalCount }}
          }}
        }}
        pageInfo {{ hasNextPage endCursor }}
      }}
    }}
    """

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            _graphql_url(api_url),
            headers=_saleor_headers(token),
            json={"query": query},
        )
        r.raise_for_status()
        data = r.json()

    if data.get("errors"):
        raise RuntimeError(f"GraphQL errors: {data['errors']}")

    edges = data.get("data", {}).get("customers", {}).get("edges", [])
    customers = [e["node"] for e in edges]
    log.info("saleor.list_customers", count=len(customers))
    return {"customers": customers, "count": len(customers)}
