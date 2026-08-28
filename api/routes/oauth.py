"""OAuth routes — user-facing connect flow."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from storage.database import get_db
from storage.models import OAuthCredential
from oauth.flow import build_authorization_url, handle_callback, revoke_credential
from oauth.providers import PROVIDERS
from api.middleware.auth import get_current_user, get_current_user_flexible

router = APIRouter()


@router.get("/connect/{provider}")
async def connect_provider(
    provider: str,
    label: str = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user_flexible),
):
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    p = PROVIDERS[provider]
    if not p.client_id_getter():
        raise HTTPException(
            status_code=501,
            detail=f"{p.display_name} OAuth is not configured. Set {provider.upper()}_CLIENT_ID in environment.",
        )

    url = await build_authorization_url(
        provider_name=provider,
        user_id=user.id,
        label=label or p.display_name,
        db=db,
    )
    return RedirectResponse(url=url)


@router.get("/callback/{provider}")
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    cred = await handle_callback(provider, code, state, db)
    # Redirect to frontend success page
    from core.config import settings
    return RedirectResponse(
        url=f"{settings.frontend_url}/credentials?connected={provider}&id={cred.id}"
    )


@router.get("/callback/{provider}/error")
async def oauth_error(provider: str, error: str = Query(...), error_description: str = Query(default="")):
    from core.config import settings
    return RedirectResponse(
        url=f"{settings.frontend_url}/credentials?error={error}&provider={provider}"
    )


@router.get("/credentials")
async def list_credentials(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(OAuthCredential).where(OAuthCredential.user_id == user.id)
    )
    creds = result.scalars().all()
    return {
        "credentials": [
            {
                "id": c.id,
                "provider": c.provider,
                "label": c.label,
                "external_account_name": c.external_account_name,
                "is_valid": c.is_valid,
                "created_at": c.created_at.isoformat(),
            }
            for c in creds
        ]
    }


@router.delete("/credentials/{credential_id}")
async def delete_credential(
    credential_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(OAuthCredential).where(
            OAuthCredential.id == credential_id,
            OAuthCredential.user_id == user.id,
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    await revoke_credential(credential_id, db)
    return {"ok": True}