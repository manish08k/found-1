"""
OAuth Provider Registry.

Each provider is defined once here with:
  - authorization_url
  - token_url
  - default scopes
  - how to fetch the connected account identity

The OAuth router reads this registry — adding a new provider = adding one entry.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional
import httpx

from core.config import settings


@dataclass
class OAuthProvider:
    name: str                          # internal key, e.g. "google"
    display_name: str                  # "Google"
    authorization_url: str
    token_url: str
    default_scopes: list[str]
    client_id_getter: Callable[[], str]
    client_secret_getter: Callable[[], str]
    # After token exchange, fetch user/workspace identity
    identity_fetcher: Optional[Callable] = None
    # Some providers (Slack, Discord) use non-standard token exchange
    token_exchange_extra: dict = field(default_factory=dict)
    # PKCE required?
    pkce: bool = False
    icon: str = ""


async def _google_identity(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()
        data = r.json()
        return {"id": data.get("sub"), "name": data.get("email")}


async def _slack_identity(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()
        data = r.json()
        return {"id": data.get("team_id"), "name": data.get("team")}


async def _github_identity(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}",
                     "Accept": "application/vnd.github+json"},
        )
        r.raise_for_status()
        data = r.json()
        return {"id": str(data.get("id")), "name": data.get("login")}


async def _notion_identity(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://api.notion.com/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}",
                     "Notion-Version": "2022-06-28"},
        )
        r.raise_for_status()
        data = r.json()
        return {"id": data.get("id"), "name": data.get("name")}


async def _discord_identity(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()
        data = r.json()
        return {"id": data.get("id"), "name": data.get("username")}


async def _hubspot_identity(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://api.hubapi.com/oauth/v1/access-tokens/" + access_token,
        )
        r.raise_for_status()
        data = r.json()
        return {"id": str(data.get("hub_id")), "name": data.get("hub_domain")}


async def _airtable_identity(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://api.airtable.com/v0/meta/whoami",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()
        data = r.json()
        return {"id": data.get("id"), "name": data.get("email")}


PROVIDERS: dict[str, OAuthProvider] = {
    "google": OAuthProvider(
        name="google",
        display_name="Google",
        authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        default_scopes=[
            "openid", "email", "profile",
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/calendar",
        ],
        client_id_getter=lambda: settings.GOOGLE_CLIENT_ID,
        client_secret_getter=lambda: settings.GOOGLE_CLIENT_SECRET,
        identity_fetcher=_google_identity,
        token_exchange_extra={"access_type": "offline", "prompt": "consent"},
        pkce=True,
        icon="google",
    ),
    "slack": OAuthProvider(
        name="slack",
        display_name="Slack",
        authorization_url="https://slack.com/oauth/v2/authorize",
        token_url="https://slack.com/api/oauth.v2.access",
        default_scopes=[
            "channels:read", "channels:history", "channels:write",
            "chat:write", "files:write", "reactions:write",
            "users:read", "users:read.email",
            "im:read", "im:write", "im:history",
            "groups:read", "groups:write",
        ],
        client_id_getter=lambda: settings.SLACK_CLIENT_ID,
        client_secret_getter=lambda: settings.SLACK_CLIENT_SECRET,
        identity_fetcher=_slack_identity,
        icon="slack",
    ),
    "github": OAuthProvider(
        name="github",
        display_name="GitHub",
        authorization_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        default_scopes=["repo", "read:user", "user:email", "workflow"],
        client_id_getter=lambda: settings.GITHUB_CLIENT_ID,
        client_secret_getter=lambda: settings.GITHUB_CLIENT_SECRET,
        identity_fetcher=_github_identity,
        icon="github",
    ),
    "notion": OAuthProvider(
        name="notion",
        display_name="Notion",
        authorization_url="https://api.notion.com/v1/oauth/authorize",
        token_url="https://api.notion.com/v1/oauth/token",
        default_scopes=[],   # Notion uses capability-based auth, not scopes
        client_id_getter=lambda: settings.NOTION_CLIENT_ID,
        client_secret_getter=lambda: settings.NOTION_CLIENT_SECRET,
        identity_fetcher=_notion_identity,
        icon="notion",
    ),
    "discord": OAuthProvider(
        name="discord",
        display_name="Discord",
        authorization_url="https://discord.com/oauth2/authorize",
        token_url="https://discord.com/api/oauth2/token",
        default_scopes=["identify", "guilds", "bot", "messages.read"],
        client_id_getter=lambda: settings.DISCORD_CLIENT_ID,
        client_secret_getter=lambda: settings.DISCORD_CLIENT_SECRET,
        identity_fetcher=_discord_identity,
        icon="discord",
    ),
    "hubspot": OAuthProvider(
        name="hubspot",
        display_name="HubSpot",
        authorization_url="https://app.hubspot.com/oauth/authorize",
        token_url="https://api.hubapi.com/oauth/v1/token",
        default_scopes=["contacts", "crm.objects.contacts.read",
                        "crm.objects.contacts.write", "timeline"],
        client_id_getter=lambda: settings.HUBSPOT_CLIENT_ID,
        client_secret_getter=lambda: settings.HUBSPOT_CLIENT_SECRET,
        identity_fetcher=_hubspot_identity,
        icon="hubspot",
    ),
    "airtable": OAuthProvider(
        name="airtable",
        display_name="Airtable",
        authorization_url="https://airtable.com/oauth2/v1/authorize",
        token_url="https://airtable.com/oauth2/v1/token",
        default_scopes=[
            "data.records:read", "data.records:write",
            "schema.bases:read", "schema.bases:write",
            "webhook:manage",
        ],
        client_id_getter=lambda: settings.AIRTABLE_CLIENT_ID,
        client_secret_getter=lambda: settings.AIRTABLE_CLIENT_SECRET,
        identity_fetcher=_airtable_identity,
        pkce=True,
        icon="airtable",
    ),
}


def get_provider(name: str) -> OAuthProvider:
    if name not in PROVIDERS:
        raise ValueError(f"Unknown OAuth provider: {name}")
    return PROVIDERS[name]
