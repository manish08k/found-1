"""DigitalOcean integration — droplets, domains, and databases."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

DO_BASE = "https://api.digitalocean.com/v2"


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


@register_node("digital_ocean.list_droplets")
async def do_list_droplets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List DigitalOcean droplets.

    config:
      api_key  — DigitalOcean API key (required)
      per_page — Number of droplets per page (default 25)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for digital_ocean.list_droplets")
    per_page = int(config.get("per_page", 25))

    async with httpx.AsyncClient(base_url=DO_BASE, timeout=30) as client:
        r = await client.get("/droplets", headers=_headers(api_key), params={"per_page": per_page})
        r.raise_for_status()
        data = r.json()

    droplets = data.get("droplets", [])
    log.info("digital_ocean.list_droplets", count=len(droplets))
    return {"droplets": droplets, "count": len(droplets), "meta": data.get("meta", {})}


@register_node("digital_ocean.create_droplet")
async def do_create_droplet(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new DigitalOcean droplet.

    config/input_data:
      api_key — DigitalOcean API key (required)
      name    — Droplet name (required)
      region  — Region slug e.g. "nyc3" (required)
      size    — Size slug e.g. "s-1vcpu-1gb" (required)
      image   — Image slug or ID e.g. "ubuntu-22-04-x64" (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    name = config.get("name") or input_data.get("name")
    region = config.get("region") or input_data.get("region")
    size = config.get("size") or input_data.get("size")
    image = config.get("image") or input_data.get("image")

    if not api_key:
        raise ValueError("api_key is required for digital_ocean.create_droplet")
    if not name:
        raise ValueError("name is required for digital_ocean.create_droplet")
    if not region:
        raise ValueError("region is required for digital_ocean.create_droplet")
    if not size:
        raise ValueError("size is required for digital_ocean.create_droplet")
    if not image:
        raise ValueError("image is required for digital_ocean.create_droplet")

    payload = {"name": name, "region": region, "size": size, "image": image}

    async with httpx.AsyncClient(base_url=DO_BASE, timeout=30) as client:
        r = await client.post("/droplets", headers=_headers(api_key), json=payload)
        r.raise_for_status()
        data = r.json()

    droplet = data.get("droplet", {})
    log.info("digital_ocean.create_droplet", droplet_id=droplet.get("id"), name=name, status=droplet.get("status"))
    return {"droplet": droplet, "id": droplet.get("id"), "name": name, "status": droplet.get("status")}


@register_node("digital_ocean.get_droplet")
async def do_get_droplet(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a DigitalOcean droplet by ID.

    config/input_data:
      api_key — DigitalOcean API key (required)
      id      — Droplet ID (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    droplet_id = config.get("id") or input_data.get("id")

    if not api_key:
        raise ValueError("api_key is required for digital_ocean.get_droplet")
    if not droplet_id:
        raise ValueError("id is required for digital_ocean.get_droplet")

    async with httpx.AsyncClient(base_url=DO_BASE, timeout=30) as client:
        r = await client.get(f"/droplets/{droplet_id}", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    droplet = data.get("droplet", {})
    log.info("digital_ocean.get_droplet", droplet_id=droplet_id, status=droplet.get("status"))
    return {"droplet": droplet, "id": droplet_id, "status": droplet.get("status"), "name": droplet.get("name")}


@register_node("digital_ocean.list_domains")
async def do_list_domains(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List DigitalOcean domains.

    config:
      api_key — DigitalOcean API key (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for digital_ocean.list_domains")

    async with httpx.AsyncClient(base_url=DO_BASE, timeout=30) as client:
        r = await client.get("/domains", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    domains = data.get("domains", [])
    log.info("digital_ocean.list_domains", count=len(domains))
    return {"domains": domains, "count": len(domains)}


@register_node("digital_ocean.list_databases")
async def do_list_databases(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List DigitalOcean managed database clusters.

    config:
      api_key — DigitalOcean API key (required)
    """
    api_key = config.get("api_key") or input_data.get("api_key")
    if not api_key:
        raise ValueError("api_key is required for digital_ocean.list_databases")

    async with httpx.AsyncClient(base_url=DO_BASE, timeout=30) as client:
        r = await client.get("/databases", headers=_headers(api_key))
        r.raise_for_status()
        data = r.json()

    databases = data.get("databases", [])
    log.info("digital_ocean.list_databases", count=len(databases))
    return {"databases": databases, "count": len(databases)}
