"""
OAuth Flow Engine.

Handles the full OAuth 2.0 dance for every provider:
  1. /oauth/connect/{provider}   → redirect user to provider
  2. /oauth/callback/{provider}  → exchange code → encrypt → store
  3. Token refresh (automatic, called by integration clients)
  4. Revoke / disconnect
"""
import base64
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from core.config import settings
from credentials.encryption import encrypt_credential, decrypt_credential
from credentials.envelope import encrypt_credential_envelope, decrypt_credential_envelope
from oauth.providers import get_provider, OAuthProvider
from storage.models import OAuthCredential, OAuthState, User


# ─── PKCE helpers ────────────────────────────────────────────────────────────

def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


# ─── Step 1: build authorization URL ─────────────────────────────────────────

async def build_authorization_url(
    provider_name: str,
    user_id: str,
    label: str,
    db: AsyncSession,
    extra_scopes: list[str] | None = None,
) -> str:
    provider = get_provider(provider_name)

    state_token = secrets.token_urlsafe(32)
    extra: dict = {}
    params: dict = {
        "client_id": provider.client_id_getter(),
        "redirect_uri": f"{settings.APP_BASE_URL}/oauth/callback/{provider_name}",
        "response_type": "code",
        "state": state_token,
    }

    scopes = list(provider.default_scopes)
    if extra_scopes:
        scopes = list(set(scopes + extra_scopes))
    if scopes:
        params["scope"] = " ".join(scopes)

    if provider.pkce:
        verifier, challenge = _pkce_pair()
        extra["pkce_verifier"] = verifier
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"

    params.update(provider.token_exchange_extra)

    # Persist state for CSRF check
    state_row = OAuthState(
        state=state_token,
        user_id=user_id,
        provider=provider_name,
        label=label,
        extra=extra,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(state_row)
    await db.commit()

    return f"{provider.authorization_url}?{urlencode(params)}"


# ─── Step 2: handle callback ──────────────────────────────────────────────────

async def handle_callback(
    provider_name: str,
    code: str,
    state_token: str,
    db: AsyncSession,
) -> OAuthCredential:
    provider = get_provider(provider_name)

    # Validate state
    result = await db.execute(
        select(OAuthState).where(
            OAuthState.state == state_token,
            OAuthState.provider == provider_name,
            OAuthState.used == False,
            OAuthState.expires_at > datetime.utcnow(),
        )
    )
    state_row = result.scalar_one_or_none()
    if not state_row:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    # Mark state used (replay protection)
    state_row.used = True
    await db.flush()

    # Exchange code for tokens
    token_data = await _exchange_code(provider, code, state_row)

    # Fetch identity
    account_id, account_name = None, None
    if provider.identity_fetcher:
        try:
            identity = await provider.identity_fetcher(token_data["access_token"])
            account_id = identity.get("id")
            account_name = identity.get("name")
        except Exception:
            pass

    # Encrypt and store
    encrypted = encrypt_credential(token_data, settings.CREDENTIAL_ENCRYPTION_KEY)

    cred = OAuthCredential(
        user_id=state_row.user_id,
        provider=provider_name,
        label=state_row.label or account_name or provider.display_name,
        scope=token_data.get("scope", ""),
        encrypted_token=encrypted,
        external_account_id=account_id,
        external_account_name=account_name,
        is_valid=True,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return cred


async def _exchange_code(provider: OAuthProvider, code: str, state_row: OAuthState) -> dict:
    redirect_uri = f"{settings.APP_BASE_URL}/oauth/callback/{provider.name}"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": provider.client_id_getter(),
        "client_secret": provider.client_secret_getter(),
    }
    if state_row.extra.get("pkce_verifier"):
        payload["code_verifier"] = state_row.extra["pkce_verifier"]

    headers = {"Accept": "application/json"}

    # Notion requires Basic auth
    if provider.name == "notion":
        creds = f"{provider.client_id_getter()}:{provider.client_secret_getter()}"
        b64 = base64.b64encode(creds.encode()).decode()
        headers["Authorization"] = f"Basic {b64}"
        payload.pop("client_id", None)
        payload.pop("client_secret", None)

    async with httpx.AsyncClient() as client:
        r = await client.post(provider.token_url, data=payload, headers=headers)
        r.raise_for_status()
        return r.json()


# ─── Token refresh ────────────────────────────────────────────────────────────

async def refresh_token(
    credential_id: str,
    db: AsyncSession,
) -> dict:
    """
    Refresh an access token using the stored refresh_token.
    Returns the updated token dict.
    Raises if the provider doesn't support refresh or token is gone.
    """
    result = await db.execute(
        select(OAuthCredential).where(OAuthCredential.id == credential_id)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    token_data = decrypt_credential(cred.encrypted_token, settings.CREDENTIAL_ENCRYPTION_KEY)
    refresh_tok = token_data.get("refresh_token")
    if not refresh_tok:
        raise HTTPException(status_code=400, detail="No refresh token available")

    provider = get_provider(cred.provider)
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_tok,
        "client_id": provider.client_id_getter(),
        "client_secret": provider.client_secret_getter(),
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(provider.token_url, data=payload,
                              headers={"Accept": "application/json"})
        r.raise_for_status()
        new_data = r.json()

    # Preserve refresh_token if provider doesn't return a new one
    if "refresh_token" not in new_data:
        new_data["refresh_token"] = refresh_tok

    cred.encrypted_token = encrypt_credential(new_data, settings.CREDENTIAL_ENCRYPTION_KEY)
    cred.is_valid = True
    cred.updated_at = datetime.utcnow()
    await db.commit()
    return new_data


# ─── Get live access token (refresh if needed) ────────────────────────────────

async def create_manual_credential(
    user_id: str,
    provider: str,
    label: str,
    data: dict,
    db: AsyncSession,
    external_account_name: Optional[str] = None,
    org_id: Optional[str] = None,
) -> OAuthCredential:
    """
    Store a non-OAuth credential (e.g. a database connection, an API key).
    `data` is any JSON-serializable dict. Uses envelope encryption
    (credentials/envelope.py) rather than the flat single-key AES-GCM used
    elsewhere in this file — manual credentials are typically raw
    passwords with no expiry/rotation of their own (unlike OAuth tokens),
    so they get the stronger per-credential-key + org-scoped-AAD treatment.
    """
    encrypted = encrypt_credential_envelope(data, org_id=org_id)
    cred = OAuthCredential(
        user_id=user_id,
        provider=provider,
        label=label,
        scope=None,
        encrypted_token=encrypted,
        external_account_id=None,
        external_account_name=external_account_name,
        is_valid=True,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return cred


async def get_credential_data(credential_id: str, db: AsyncSession) -> dict:
    """
    Decrypt and return the raw stored dict for ANY credential (OAuth token
    fields or manual fields like host/username/password). Use this instead
    of get_access_token() for non-OAuth providers (databases, raw API keys).

    Transparently handles both encryption formats: new envelope-encrypted
    rows (credentials/envelope.py) and legacy flat AES-GCM rows — see
    decrypt_credential_envelope()'s docstring.

    Every call here is an actual credential decrypt in worker memory —
    logged via core.credential_audit so "who accessed this secret and
    when" is answerable, and checked for anomalous access volume.
    """
    result = await db.execute(
        select(OAuthCredential, User.org_id)
        .join(User, User.id == OAuthCredential.user_id)
        .where(OAuthCredential.id == credential_id)
    )
    row = result.first()
    if not row or not row[0].is_valid:
        raise HTTPException(status_code=401, detail="Credential invalid or revoked")
    cred, org_id = row

    from core.credential_audit import log_credential_access
    await log_credential_access(db, credential_id=credential_id, user_id=cred.user_id, org_id=org_id, provider=cred.provider)

    return decrypt_credential_envelope(cred.encrypted_token, org_id=org_id)


async def get_access_token(credential_id: str, db: AsyncSession) -> str:
    """
    Returns a valid access_token for the credential.
    Auto-refreshes if expires_in has passed.
    """
    result = await db.execute(
        select(OAuthCredential, User.org_id)
        .join(User, User.id == OAuthCredential.user_id)
        .where(OAuthCredential.id == credential_id)
    )
    row = result.first()
    if not row or not row[0].is_valid:
        raise HTTPException(status_code=401, detail="Credential invalid or revoked")
    cred, org_id = row

    from core.credential_audit import log_credential_access
    await log_credential_access(db, credential_id=credential_id, user_id=cred.user_id, org_id=org_id, provider=cred.provider)

    token_data = decrypt_credential(cred.encrypted_token, settings.CREDENTIAL_ENCRYPTION_KEY)
    access_token = token_data.get("access_token")

    # Check expiry if we have it (Google stores expires_in + fetched_at)
    fetched_at = token_data.get("fetched_at")
    expires_in = token_data.get("expires_in")
    if fetched_at and expires_in:
        expiry = datetime.fromtimestamp(fetched_at + expires_in - 60)
        if datetime.utcnow() >= expiry:
            token_data = await refresh_token(credential_id, db)
            access_token = token_data["access_token"]

    return access_token


# ─── Revoke / disconnect ──────────────────────────────────────────────────────

async def revoke_credential(credential_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(OAuthCredential).where(OAuthCredential.id == credential_id)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        return

    token_data = decrypt_credential(cred.encrypted_token, settings.CREDENTIAL_ENCRYPTION_KEY)
    access_token = token_data.get("access_token")

    # Best-effort revoke at provider
    revoke_urls = {
        "google": f"https://oauth2.googleapis.com/revoke?token={access_token}",
        "github": None,   # GitHub has no revoke endpoint
        "slack": None,    # Slack revoke requires POST
        "discord": "https://discord.com/api/oauth2/token/revoke",
    }
    provider_name = cred.provider
    if provider_name in revoke_urls and revoke_urls[provider_name]:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(revoke_urls[provider_name], timeout=5)
        except Exception:
            pass

    await db.delete(cred)
    await db.commit()
