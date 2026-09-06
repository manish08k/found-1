"""SkyPrep LMS integration for user, course, and progress management."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _base_url(company: str) -> str:
    return f"https://{company}.skyprep.com/api"


@register_node("skyprep.list_users")
async def skyprep_list_users(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all users in SkyPrep."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    company = merged.get("company", "")
    if not api_key:
        raise ValueError("api_key is required")
    if not company:
        raise ValueError("company is required")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{_base_url(company)}/users",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"page": merged.get("page", 1), "per_page": merged.get("per_page", 25)},
        )
        r.raise_for_status()
        result = r.json()
    log.info("skyprep.list_users")
    return result


@register_node("skyprep.list_courses")
async def skyprep_list_courses(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List all courses in SkyPrep."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    company = merged.get("company", "")
    if not api_key:
        raise ValueError("api_key is required")
    if not company:
        raise ValueError("company is required")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{_base_url(company)}/courses",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"page": merged.get("page", 1), "per_page": merged.get("per_page", 25)},
        )
        r.raise_for_status()
        result = r.json()
    log.info("skyprep.list_courses")
    return result


@register_node("skyprep.enroll_user")
async def skyprep_enroll_user(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Enroll a user in a course."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    company = merged.get("company", "")
    if not api_key:
        raise ValueError("api_key is required")
    if not company:
        raise ValueError("company is required")
    user_id = merged.get("user_id", "")
    course_id = merged.get("course_id", "")
    if not user_id:
        raise ValueError("user_id is required")
    if not course_id:
        raise ValueError("course_id is required")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_base_url(company)}/users/{user_id}/courses/{course_id}/enroll",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={},
        )
        r.raise_for_status()
        result = r.json()
    log.info("skyprep.enroll_user")
    return result


@register_node("skyprep.get_progress")
async def skyprep_get_progress(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get a user's course progress."""
    merged = {**config, **input_data}
    api_key = merged.get("api_key", "")
    company = merged.get("company", "")
    if not api_key:
        raise ValueError("api_key is required")
    if not company:
        raise ValueError("company is required")
    user_id = merged.get("user_id", "")
    if not user_id:
        raise ValueError("user_id is required")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{_base_url(company)}/users/{user_id}/progress",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"course_id": merged.get("course_id", "")},
        )
        r.raise_for_status()
        result = r.json()
    log.info("skyprep.get_progress")
    return result
