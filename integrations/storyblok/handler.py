"""Storyblok integration — headless CMS (Management API token auth)."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


async def _client(credential_id: str, db):
    creds = await get_credential_data(credential_id, db)
    api_token = creds["api_token"]
    space_id = creds["space_id"]
    base_url = f"https://mapi.storyblok.com/v1/spaces/{space_id}/"
    return httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": api_token, "Content-Type": "application/json"},
        timeout=30,
    ), space_id


@register_node("storyblok.list_stories")
async def storyblok_list_stories(config: dict, input_data: dict, credential_id: str, db) -> dict:
    page = config.get("page", 1)
    per_page = config.get("per_page", 25)
    search_term = config.get("search_term") or input_data.get("search_term")
    folder_only = config.get("folder_only", False)

    params: dict = {"page": page, "per_page": per_page}
    if search_term:
        params["search_term"] = search_term
    if folder_only:
        params["folder_only"] = 1

    log.info("storyblok.list_stories", page=page, per_page=per_page)
    client, space_id = await _client(credential_id, db)
    async with client as c:
        r = await c.get("stories/", params=params)
        r.raise_for_status()
        data = r.json()

    return {"stories": data.get("stories", []), "total": data.get("total", 0), "space_id": space_id}


@register_node("storyblok.get_story")
async def storyblok_get_story(config: dict, input_data: dict, credential_id: str, db) -> dict:
    story_id = config.get("story_id") or input_data.get("story_id", "")

    log.info("storyblok.get_story", story_id=story_id)
    client, space_id = await _client(credential_id, db)
    async with client as c:
        r = await c.get(f"stories/{story_id}")
        r.raise_for_status()
        data = r.json()

    return {"story": data.get("story", data), "space_id": space_id}


@register_node("storyblok.create_story")
async def storyblok_create_story(config: dict, input_data: dict, credential_id: str, db) -> dict:
    name = config.get("name") or input_data.get("name", "")
    slug = config.get("slug") or input_data.get("slug", "")
    content = config.get("content") or input_data.get("content", {})
    parent_id = config.get("parent_id") or input_data.get("parent_id")
    is_folder = config.get("is_folder", False)

    story_payload: dict = {
        "name": name,
        "slug": slug,
        "content": content,
        "is_folder": is_folder,
    }
    if parent_id:
        story_payload["parent_id"] = parent_id

    log.info("storyblok.create_story", name=name, slug=slug)
    client, space_id = await _client(credential_id, db)
    async with client as c:
        r = await c.post("stories/", json={"story": story_payload})
        r.raise_for_status()
        data = r.json()

    story = data.get("story", data)
    return {"story_id": story.get("id"), "name": story.get("name"), "slug": story.get("slug"), "space_id": space_id}


@register_node("storyblok.publish_story")
async def storyblok_publish_story(config: dict, input_data: dict, credential_id: str, db) -> dict:
    story_id = config.get("story_id") or input_data.get("story_id", "")

    log.info("storyblok.publish_story", story_id=story_id)
    client, space_id = await _client(credential_id, db)
    async with client as c:
        r = await c.get(f"stories/{story_id}/publish")
        r.raise_for_status()
        data = r.json()

    story = data.get("story", data)
    return {
        "story_id": story.get("id", story_id),
        "published": True,
        "published_at": story.get("published_at"),
        "space_id": space_id,
    }
