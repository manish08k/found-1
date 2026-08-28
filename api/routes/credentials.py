"""Credentials management routes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from storage.database import get_db
from storage.models import OAuthCredential
from api.middleware.auth import get_current_user
from api.middleware.rbac import require_permission_or_personal
from oauth.flow import get_access_token, create_manual_credential, get_credential_data

router = APIRouter()

# Providers that don't go through the OAuth dance — the user supplies raw
# connection fields or a static key instead, which we encrypt and store
# the same way (envelope encryption, credentials/envelope.py).
MANUAL_PROVIDERS = {"postgres", "mysql", "sqlite"}
API_KEY_PROVIDERS = {"stripe", "sendgrid", "twilio", "jira", "trello", "pagerduty", "asana", "aws_s3", "mcp"}


class CredentialRename(BaseModel):
    label: str


class DatabaseCredentialCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)
    db_type: str = Field(..., description="postgres | mysql | sqlite")
    host: Optional[str] = None
    port: Optional[int] = None
    database: str
    username: Optional[str] = None
    password: Optional[str] = None
    ssl: bool = False

    def to_dict(self) -> dict:
        return {
            "db_type": self.db_type,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "password": self.password,
            "ssl": self.ssl,
        }


@router.post("/manual")
async def create_database_credential(
    body: DatabaseCredentialCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission_or_personal("credential:database:manage")),
):
    """
    Add a SQL database connection as a credential (no OAuth flow).
    The password is encrypted at rest (credentials/encryption.py, AES-256-GCM)
    and is never sent back to the client after this call — only /test and
    workflow nodes can decrypt it, server-side, for the duration of one call.
    """
    if body.db_type not in MANUAL_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported db_type: {body.db_type}")
    if body.db_type != "sqlite" and not body.host:
        raise HTTPException(status_code=400, detail="'host' is required for this database type")

    cred = await create_manual_credential(
        user_id=user.id,
        provider=body.db_type,
        label=body.label,
        data=body.to_dict(),
        db=db,
        external_account_name=body.database,
        org_id=user.org_id,
    )
    return _serialize(cred)


class ApiKeyCredentialCreate(BaseModel):
    provider: str = Field(..., description="stripe | sendgrid | twilio | jira | trello | pagerduty | asana | aws_s3")
    label: str = Field(..., min_length=1, max_length=255)
    fields: dict = Field(..., description="Provider-specific key/value pairs, e.g. {'api_key': '...'} for Stripe")


@router.post("/api-key")
async def create_api_key_credential(
    body: ApiKeyCredentialCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission_or_personal("credential:database:manage")),
):
    """
    Generic API-key/token credential (as opposed to OAuth or the raw
    database-connection fields DatabaseCredentialCreate handles) — for
    services like Stripe/SendGrid/Twilio/Jira that authenticate with a
    static key rather than a token exchange flow. Reuses the same
    envelope encryption and role gating as database credentials, since
    it's the same risk profile: a static secret, decrypted server-side
    only for the duration of one node execution.
    """
    if body.provider not in API_KEY_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {body.provider}")
    cred = await create_manual_credential(
        user_id=user.id,
        provider=body.provider,
        label=body.label,
        data=body.fields,
        db=db,
        org_id=user.org_id,
    )
    return _serialize(cred)


@router.get("")
async def list_credentials(
    provider: str = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    q = select(OAuthCredential).where(OAuthCredential.user_id == user.id)
    if provider:
        q = q.where(OAuthCredential.provider == provider)
    result = await db.execute(q.order_by(OAuthCredential.created_at.desc()))
    creds = result.scalars().all()
    return {"credentials": [_serialize(c) for c in creds]}


@router.get("/{credential_id}")
async def get_credential(
    credential_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    cred = await _get_owned(credential_id, user.id, db)
    return _serialize(cred)


@router.patch("/{credential_id}")
async def rename_credential(
    credential_id: str,
    body: CredentialRename,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    cred = await _get_owned(credential_id, user.id, db)
    cred.label = body.label
    await db.commit()
    return _serialize(cred)


@router.post("/{credential_id}/test")
async def test_credential(
    credential_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    cred = await _get_owned(credential_id, user.id, db)
    try:
        if cred.provider in MANUAL_PROVIDERS:
            from integrations.database.handler import test_connection
            creds = await get_credential_data(credential_id, db)
            await test_connection(creds)
        elif cred.provider in API_KEY_PROVIDERS:
            creds = await get_credential_data(credential_id, db)
            test_fn = {
                "stripe": _test_stripe,
                "sendgrid": _test_sendgrid,
                "twilio": _test_twilio,
                "jira": _test_jira,
                "trello": _test_trello,
                "pagerduty": _test_pagerduty,
                "asana": _test_asana,
                "aws_s3": _test_aws_s3,
                "mcp": _test_mcp,
            }[cred.provider]
            await test_fn(creds)
        else:
            await get_access_token(credential_id, db)
        cred.is_valid = True
        await db.commit()
        return {"valid": True, "provider": cred.provider}
    except Exception as e:
        cred.is_valid = False
        await db.commit()
        return {"valid": False, "error": str(e)}


async def _test_stripe(creds: dict) -> None:
    from integrations.stripe_.handler import test_connection
    await test_connection(creds)


async def _test_sendgrid(creds: dict) -> None:
    from integrations.email_.handler import test_connection
    await test_connection(creds)


async def _test_twilio(creds: dict) -> None:
    from integrations.twilio_.handler import test_connection
    await test_connection(creds)


async def _test_jira(creds: dict) -> None:
    from integrations.jira_.handler import test_connection
    await test_connection(creds)


async def _test_trello(creds: dict) -> None:
    from integrations.trello_.handler import test_connection
    await test_connection(creds)


async def _test_pagerduty(creds: dict) -> None:
    from integrations.pagerduty_.handler import test_connection
    await test_connection(creds)


async def _test_asana(creds: dict) -> None:
    from integrations.asana_.handler import test_connection
    await test_connection(creds)


async def _test_aws_s3(creds: dict) -> None:
    from integrations.aws_s3_.handler import test_connection
    await test_connection(creds)


async def _test_mcp(creds: dict) -> None:
    from integrations.mcp_.handler import test_connection
    await test_connection(creds)


async def _get_owned(credential_id: str, user_id: str, db: AsyncSession) -> OAuthCredential:
    result = await db.execute(
        select(OAuthCredential).where(
            OAuthCredential.id == credential_id,
            OAuthCredential.user_id == user_id,
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    return cred


def _serialize(c: OAuthCredential) -> dict:
    return {
        "id": c.id,
        "provider": c.provider,
        "label": c.label,
        "scope": c.scope,
        "external_account_id": c.external_account_id,
        "external_account_name": c.external_account_name,
        "is_valid": c.is_valid,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }
