"""User auth routes — register, login, token refresh, Google sign-in."""
import base64
import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.config import settings
from credentials.encryption import encrypt_credential
from oauth.providers import PROVIDERS
from storage.database import get_db
from storage.models import User, GoogleLoginState, OAuthCredential
from api.middleware.auth import (
    hash_password, verify_password, create_access_token, get_current_user,
    get_current_user_full_or_mfa_setup,
    check_login_rate_limit, reset_login_rate_limit,
    check_account_lockout, record_failed_login, reset_account_lockout,
    revoke_access_token,
)
from api.middleware.refresh_tokens import (
    create_refresh_token, rotate_refresh_token, revoke_refresh_token, revoke_all_refresh_tokens,
)
from api.middleware.mfa import (
    generate_mfa_secret, encrypt_mfa_secret, decrypt_mfa_secret,
    provisioning_uri, verify_totp_code, mfa_required_for,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    mfa_code: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class MfaVerifyRequest(BaseModel):
    code: str


async def _issue_full_session(user: User, db: AsyncSession, request: Request) -> dict:
    access_token = create_access_token(user.id, user.email)
    refresh = await create_refresh_token(db, user.id, request)
    await db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user_id": user.id,
        "expires_in_minutes": 15,
    }


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.flush()
    return await _issue_full_session(user, db, request)


@router.post("/login")
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await check_login_rate_limit(request)
    await check_account_lockout(body.email)

    result = await db.execute(select(User).where(User.email == body.email, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        await record_failed_login(body.email)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # MFA required for this role but never enrolled: don't issue a usable
    # session — hand back a narrow-scope token good only for completing
    # enrollment (api/middleware/auth.py's mfa_setup scope).
    if mfa_required_for(user) and not user.mfa_enabled:
        setup_token = create_access_token(user.id, user.email, scope="mfa_setup", expire_minutes=10)
        await reset_login_rate_limit(request)
        await reset_account_lockout(body.email)
        return {"mfa_enrollment_required": True, "setup_token": setup_token}

    if user.mfa_enabled:
        if not body.mfa_code:
            return {"mfa_code_required": True}
        secret = decrypt_mfa_secret(user.mfa_secret)
        if not verify_totp_code(secret, body.mfa_code):
            await record_failed_login(body.email)
            raise HTTPException(status_code=401, detail="Invalid MFA code")

    await reset_login_rate_limit(request)
    await reset_account_lockout(body.email)
    return await _issue_full_session(user, db, request)


@router.post("/refresh")
async def refresh(body: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user_id, new_refresh = await rotate_refresh_token(db, body.refresh_token, request)
    except ValueError as e:
        await db.commit()  # persist any reuse-detected mass-revocation before responding
        raise HTTPException(status_code=401, detail=str(e))

    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        await db.commit()
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_access_token(user.id, user.email)
    await db.commit()
    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "user_id": user.id,
        "expires_in_minutes": 15,
    }


@router.post("/logout", status_code=204)
async def logout(
    body: LogoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Revokes the current access token immediately and, if provided, the refresh token — this device only."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        await revoke_access_token(auth_header[7:])
    if body.refresh_token:
        await revoke_refresh_token(db, body.refresh_token)
    await db.commit()


@router.post("/logout-everywhere", status_code=204)
async def logout_everywhere(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Revokes every refresh token for this account — use after a suspected compromise."""
    await revoke_all_refresh_tokens(db, user.id)
    await db.commit()


# ─── MFA enrollment (TOTP) ─────────────────────────────────────────────────────

@router.post("/mfa/setup")
async def mfa_setup(user: User = Depends(get_current_user_full_or_mfa_setup), db: AsyncSession = Depends(get_db)):
    """Generates a new TOTP secret + QR provisioning URI. Not yet enabled — call /mfa/verify with a code to confirm."""
    secret = generate_mfa_secret()
    user.mfa_secret = encrypt_mfa_secret(secret)
    await db.commit()
    return {"secret": secret, "provisioning_uri": provisioning_uri(secret, user.email)}


@router.post("/mfa/verify")
async def mfa_verify(
    body: MfaVerifyRequest,
    request: Request,
    user: User = Depends(get_current_user_full_or_mfa_setup),
    db: AsyncSession = Depends(get_db),
):
    """Confirms enrollment with one TOTP code, then enables MFA. If this was a forced first-time enrollment (mfa_setup-scope token), also issues the real session."""
    if not user.mfa_secret:
        raise HTTPException(status_code=400, detail="Call /mfa/setup first")
    secret = decrypt_mfa_secret(user.mfa_secret)
    if not verify_totp_code(secret, body.code):
        raise HTTPException(status_code=401, detail="Invalid code")

    user.mfa_enabled = True
    await db.flush()
    return await _issue_full_session(user, db, request)


@router.post("/mfa/disable")
async def mfa_disable(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user.mfa_enabled = False
    user.mfa_secret = None
    await db.commit()
    return {"mfa_enabled": False}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat(),
    }


# ─── Sign in with Google ──────────────────────────────────────────────────
#
# Flow:
#   1. GET /api/auth/google/login    -> redirect to Google's consent screen
#   2. GET /api/auth/google/callback -> exchange code, upsert user, save an
#                                        OAuthCredential, redirect to the
#                                        frontend with ?google_token=...
#
# This sign-in flow now requests the SAME scopes as /oauth/connect/google
# (Gmail, Sheets, Drive, Calendar) so that signing in with Google also
# connects the integration credential in one step — no separate "Connect"
# click needed on the Credentials page.

def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


@router.get("/google/login")
async def google_login(db: AsyncSession = Depends(get_db)):
    provider = PROVIDERS["google"]
    if not provider.client_id_getter():
        raise HTTPException(
            status_code=501,
            detail="Google sign-in is not configured. Set GOOGLE_CLIENT_ID in environment.",
        )

    state_token = secrets.token_urlsafe(32)
    verifier, challenge = _pkce_pair()
    db.add(GoogleLoginState(
        state=state_token,
        extra={"pkce_verifier": verifier},
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    ))
    await db.commit()

    params = {
        "client_id": provider.client_id_getter(),
        "redirect_uri": f"{settings.APP_BASE_URL}/api/auth/google/callback",
        "response_type": "code",
        "scope": " ".join(provider.default_scopes),
        "state": state_token,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        # Request a refresh token so the connected credential keeps working
        # after the access token expires.
        "access_type": "offline",
        "prompt": "consent",
    }
    return RedirectResponse(url=f"{provider.authorization_url}?{urlencode(params)}")


@router.get("/google/callback")
async def google_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    def _fail(reason: str) -> RedirectResponse:
        return RedirectResponse(url=f"{settings.frontend_url}/login?error={reason}")

    if error or not code or not state:
        return _fail("google_auth_failed")

    # Validate + consume state (CSRF / replay protection)
    result = await db.execute(
        select(GoogleLoginState).where(
            GoogleLoginState.state == state,
            GoogleLoginState.used == False,
            GoogleLoginState.expires_at > datetime.utcnow(),
        )
    )
    state_row = result.scalar_one_or_none()
    if not state_row:
        return _fail("invalid_state")
    state_row.used = True
    await db.flush()

    provider = PROVIDERS["google"]
    redirect_uri = f"{settings.APP_BASE_URL}/api/auth/google/callback"

    try:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                provider.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": provider.client_id_getter(),
                    "client_secret": provider.client_secret_getter(),
                    "code_verifier": state_row.extra.get("pkce_verifier", ""),
                },
                headers={"Accept": "application/json"},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
            access_token = token_data["access_token"]

            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_resp.raise_for_status()
            info = userinfo_resp.json()
    except (httpx.HTTPError, KeyError):
        await db.commit()
        return _fail("google_auth_failed")

    email = info.get("email")
    google_id = info.get("sub")
    if not email or not google_id:
        await db.commit()
        return _fail("google_auth_failed")
    if not info.get("email_verified", False):
        await db.commit()
        return _fail("google_email_unverified")

    # Find existing user by Google ID first, then by email (account linking)
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if user:
        if not user.is_active:
            await db.commit()
            return _fail("account_disabled")
        if user.google_id != google_id:
            user.google_id = google_id  # link Google identity to existing account
    else:
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            # Random password — this account can only sign in via Google
            # unless the user later sets a password explicitly.
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            google_id=google_id,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)

    # ── Save/refresh the Google integration credential ──────────────────
    # Same record type used by /oauth/connect/google, so it shows up
    # immediately under Credentials -> Connected, ready for workflows.
    token_data["fetched_at"] = datetime.utcnow().timestamp()
    encrypted = encrypt_credential(token_data, settings.CREDENTIAL_ENCRYPTION_KEY)

    result = await db.execute(
        select(OAuthCredential).where(
            OAuthCredential.user_id == user.id,
            OAuthCredential.provider == "google",
        )
    )
    cred = result.scalar_one_or_none()

    if "refresh_token" not in token_data and cred:
        from credentials.encryption import decrypt_credential
        old_data = decrypt_credential(cred.encrypted_token, settings.CREDENTIAL_ENCRYPTION_KEY)
        if old_data.get("refresh_token"):
            token_data["refresh_token"] = old_data["refresh_token"]
            encrypted = encrypt_credential(token_data, settings.CREDENTIAL_ENCRYPTION_KEY)

    if cred:
        cred.encrypted_token = encrypted
        cred.scope = token_data.get("scope", "")
        cred.is_valid = True
        cred.external_account_id = google_id
        cred.external_account_name = email
        cred.updated_at = datetime.utcnow()
    else:
        db.add(OAuthCredential(
            user_id=user.id,
            provider="google",
            label=provider.display_name,
            scope=token_data.get("scope", ""),
            encrypted_token=encrypted,
            external_account_id=google_id,
            external_account_name=email,
            is_valid=True,
        ))
    await db.commit()

    token = create_access_token(user.id, user.email)
    redirect = RedirectResponse(url=f"{settings.frontend_url}/")
    redirect.set_cookie(
        key="oauth_token",
        value=token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=300,  # 5 minutes — SPA should exchange it immediately
        path="/",
    )
    return redirect