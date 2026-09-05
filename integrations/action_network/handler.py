"""
ActionNetwork advocacy CRM integration.

Provides people management, tagging, and petition signature creation
via the ActionNetwork OSDI-compliant API v2.

Credential fields:
  - api_key : ActionNetwork API key (found in Developer settings)

Auth: OSDI-API-Token header.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://actionnetwork.org/api/v2"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("ActionNetwork credential missing 'api_key'")
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "OSDI-API-Token": api_key,
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"ActionNetwork API error {r.status_code}: {detail}")


@register_node("action_network.get_people")
async def an_get_people(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve a paginated list of people in ActionNetwork."""
    page = int(config.get("page") or input_data.get("page", 1))
    filter_expr = config.get("filter") or input_data.get("filter")

    params: dict = {"page": page}
    if filter_expr:
        params["filter"] = filter_expr

    async with await _client(credential_id, db) as client:
        r = await client.get("/people", params=params)
        _raise_for_status(r)
        data = r.json()

    embedded = data.get("_embedded", {})
    people = embedded.get("osdi:people", [])
    return {
        "people": people,
        "total_pages": data.get("total_pages", 1),
        "total_records": data.get("total_records", len(people)),
        "page": page,
    }


@register_node("action_network.create_person")
async def an_create_person(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Create or upsert a person record by email address."""
    email = config.get("email") or input_data.get("email")
    if not email:
        raise ValueError("action_network.create_person requires 'email'")

    given_name = config.get("given_name") or input_data.get("given_name", "")
    family_name = config.get("family_name") or input_data.get("family_name", "")
    phone = config.get("phone") or input_data.get("phone")
    postal_code = config.get("postal_code") or input_data.get("postal_code")

    payload: dict = {
        "email_addresses": [{"address": email}],
    }
    if given_name:
        payload["given_name"] = given_name
    if family_name:
        payload["family_name"] = family_name
    if phone:
        payload["phone_numbers"] = [{"number": phone}]
    if postal_code:
        payload["postal_addresses"] = [{"postal_code": postal_code}]

    async with await _client(credential_id, db) as client:
        r = await client.post("/people", json=payload)
        _raise_for_status(r)
        person = r.json()

    person_id = person.get("identifiers", [None])[0]
    log.info("action_network.create_person", person_id=person_id, email=email)
    return {"person": person, "person_id": person_id}


@register_node("action_network.add_tag")
async def an_add_tag(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Apply a named tag to a person identified by their ActionNetwork person ID."""
    person_id = config.get("person_id") or input_data.get("person_id")
    tag_name = config.get("tag_name") or input_data.get("tag_name")

    if not person_id or not tag_name:
        raise ValueError("action_network.add_tag requires 'person_id' and 'tag_name'")

    # Extract the UUID portion if a full identifier string was passed
    if "action_network:" in str(person_id):
        person_uuid = str(person_id).split("action_network:")[-1]
    else:
        person_uuid = str(person_id)

    async with await _client(credential_id, db) as client:
        # Retrieve or create tag
        tags_r = await client.get("/tags", params={"filter": f"name eq '{tag_name}'"})
        _raise_for_status(tags_r)
        tags_data = tags_r.json()
        embedded = tags_data.get("_embedded", {})
        existing = embedded.get("osdi:tags", [])

        if existing:
            tag_href = existing[0].get("_links", {}).get("self", {}).get("href", "")
        else:
            create_r = await client.post("/tags", json={"name": tag_name})
            _raise_for_status(create_r)
            tag_href = create_r.json().get("_links", {}).get("self", {}).get("href", "")

        # Apply the tag to the person via a tagging endpoint
        # ActionNetwork uses /<tag_id>/taggings pattern
        tag_id = tag_href.rstrip("/").split("/")[-1] if tag_href else None
        if not tag_id:
            raise ValueError("Could not resolve tag ID")

        tagging_payload = {
            "_links": {
                "osdi:person": {
                    "href": f"{_BASE_URL}/people/{person_uuid}"
                }
            }
        }
        tag_r = await client.post(f"/tags/{tag_id}/taggings", json=tagging_payload)
        _raise_for_status(tag_r)
        tagging = tag_r.json()

    log.info("action_network.add_tag", person_uuid=person_uuid, tag_name=tag_name)
    return {"tagging": tagging, "tag_id": tag_id, "tag_name": tag_name}


@register_node("action_network.create_petition_signature")
async def an_create_petition_signature(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Record a petition signature for a person."""
    petition_id = config.get("petition_id") or input_data.get("petition_id")
    email = config.get("email") or input_data.get("email")

    if not petition_id or not email:
        raise ValueError(
            "action_network.create_petition_signature requires 'petition_id' and 'email'"
        )

    given_name = config.get("given_name") or input_data.get("given_name", "")
    family_name = config.get("family_name") or input_data.get("family_name", "")
    comment = config.get("comment") or input_data.get("comment", "")

    payload: dict = {
        "_links": {
            "osdi:person": {
                "href": f"{_BASE_URL}/people"
            }
        },
        "person": {
            "email_addresses": [{"address": email}],
        },
    }
    if given_name:
        payload["person"]["given_name"] = given_name
    if family_name:
        payload["person"]["family_name"] = family_name
    if comment:
        payload["comments"] = comment

    async with await _client(credential_id, db) as client:
        r = await client.post(f"/petitions/{petition_id}/signatures", json=payload)
        _raise_for_status(r)
        signature = r.json()

    log.info("action_network.create_petition_signature", petition_id=petition_id, email=email)
    return {"signature": signature}


@register_node("action_network.list_tags")
async def an_list_tags(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all tags defined in the ActionNetwork account."""
    page = int(config.get("page") or input_data.get("page", 1))

    async with await _client(credential_id, db) as client:
        r = await client.get("/tags", params={"page": page})
        _raise_for_status(r)
        data = r.json()

    embedded = data.get("_embedded", {})
    tags = embedded.get("osdi:tags", [])
    return {
        "tags": tags,
        "total_pages": data.get("total_pages", 1),
        "total_records": data.get("total_records", len(tags)),
    }
