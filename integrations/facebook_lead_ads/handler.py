"""
Facebook Lead Ads integration.

Provides access to Lead Ad forms, lead submissions, and form details
via the Facebook Graph API v17.0.

Credential fields:
  - access_token : Facebook Page access token (with leads_retrieval permission)
  - page_id      : (optional default) Facebook Page ID

Auth: Bearer token via Authorization header.
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

FB_BASE = "https://graph.facebook.com/v17.0"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    access_token = creds.get("access_token")
    if not access_token:
        raise ValueError("Facebook Lead Ads credential missing 'access_token'")
    return httpx.AsyncClient(
        base_url=FB_BASE,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise RuntimeError(
            f"Facebook API error {r.status_code}: {detail}"
        )


@register_node("facebook_lead_ads.list_forms")
async def list_forms(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """List all Lead Ad forms for a given Facebook Page."""
    page_id = (
        config.get("page_id")
        or input_data.get("page_id")
    )
    if not page_id:
        raise ValueError("'page_id' is required in config or input_data")

    fields = config.get("fields", "id,name,status,created_time,leads_count")
    limit = int(config.get("limit", 25))

    log.info("facebook_lead_ads.list_forms", page_id=page_id, limit=limit)

    forms = []
    params = {"fields": fields, "limit": limit}
    async with await _client(credential_id, db) as client:
        url = f"/{page_id}/leadgen_forms"
        while True:
            r = await client.get(url, params=params)
            _raise_for_status(r)
            data = r.json()
            forms.extend(data.get("data", []))
            paging = data.get("paging", {})
            next_url = paging.get("next")
            if not next_url or len(forms) >= limit:
                break
            # Facebook returns absolute next URLs; strip base
            url = next_url.replace(FB_BASE, "")
            params = {}  # next URL includes params

    log.info("facebook_lead_ads.list_forms.done", count=len(forms))
    return {"forms": forms, "count": len(forms)}


@register_node("facebook_lead_ads.get_leads")
async def get_leads(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve lead submissions for a specific Lead Ad form."""
    form_id = (
        config.get("form_id")
        or input_data.get("form_id")
    )
    if not form_id:
        raise ValueError("'form_id' is required in config or input_data")

    fields = config.get(
        "fields",
        "id,created_time,field_data,ad_id,ad_name,adset_id,adset_name,campaign_id,campaign_name",
    )
    limit = int(config.get("limit", 100))
    filter_since = config.get("since") or input_data.get("since")
    filter_until = config.get("until") or input_data.get("until")

    params: dict = {"fields": fields, "limit": min(limit, 100)}
    if filter_since:
        params["filtering"] = (
            f'[{{"field":"time_created","operator":"GREATER_THAN","value":{filter_since}}}]'
        )

    log.info("facebook_lead_ads.get_leads", form_id=form_id, limit=limit)

    leads = []
    async with await _client(credential_id, db) as client:
        url = f"/{form_id}/leads"
        while True:
            r = await client.get(url, params=params)
            _raise_for_status(r)
            data = r.json()
            batch = data.get("data", [])
            leads.extend(batch)
            paging = data.get("paging", {})
            cursors = paging.get("cursors", {})
            next_cursor = cursors.get("after")
            if not next_cursor or len(leads) >= limit:
                break
            params = {"fields": fields, "limit": min(limit - len(leads), 100), "after": next_cursor}

    log.info("facebook_lead_ads.get_leads.done", form_id=form_id, count=len(leads))
    return {"leads": leads, "count": len(leads), "form_id": form_id}


@register_node("facebook_lead_ads.get_form_details")
async def get_form_details(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Retrieve detailed metadata for a specific Lead Ad form."""
    form_id = (
        config.get("form_id")
        or input_data.get("form_id")
    )
    if not form_id:
        raise ValueError("'form_id' is required in config or input_data")

    fields = config.get(
        "fields",
        "id,name,status,created_time,leads_count,questions,privacy_policy_url,follow_up_action_url",
    )

    log.info("facebook_lead_ads.get_form_details", form_id=form_id)

    async with await _client(credential_id, db) as client:
        r = await client.get(f"/{form_id}", params={"fields": fields})
        _raise_for_status(r)
        form = r.json()

    log.info("facebook_lead_ads.get_form_details.done", form_id=form_id)
    return {"form": form}
