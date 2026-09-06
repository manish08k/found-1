"""Amazon Secrets Manager integration for managing secrets."""
import json
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def _get_client(creds: dict):
    if not HAS_BOTO3:
        raise ImportError("boto3 is required. Install with: pip install boto3")
    return boto3.client(
        "secretsmanager",
        aws_access_key_id=creds.get("aws_access_key_id"),
        aws_secret_access_key=creds.get("aws_secret_access_key"),
        region_name=creds.get("region_name", "us-east-1"),
    )


@register_node("amazon_secrets_manager.get_secret")
async def get_secret(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Retrieve a secret value from Secrets Manager."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    secret_id = merged.get("secret_id") or merged.get("secret_name")
    if not secret_id:
        raise ValueError("amazon_secrets_manager.get_secret requires 'secret_id'")
    version_id = merged.get("version_id")
    version_stage = merged.get("version_stage")

    def _get():
        client = _get_client(creds)
        kwargs = {"SecretId": secret_id}
        if version_id:
            kwargs["VersionId"] = version_id
        if version_stage:
            kwargs["VersionStage"] = version_stage
        response = client.get_secret_value(**kwargs)
        secret = response.get("SecretString") or base64.b64decode(response.get("SecretBinary", b"")).decode()
        try:
            secret = json.loads(secret)
        except (json.JSONDecodeError, TypeError):
            pass
        return {
            "secret_id": secret_id,
            "secret_value": secret,
            "arn": response.get("ARN"),
            "version_id": response.get("VersionId"),
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get)


@register_node("amazon_secrets_manager.create_secret")
async def create_secret(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Create a new secret in Secrets Manager."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    name = merged.get("name")
    secret_value = merged.get("secret_value") or merged.get("secret_string")
    if not name or not secret_value:
        raise ValueError("create_secret requires 'name' and 'secret_value'")

    def _create():
        client = _get_client(creds)
        if isinstance(secret_value, dict):
            sv = json.dumps(secret_value)
        else:
            sv = str(secret_value)
        kwargs = {"Name": name, "SecretString": sv}
        desc = merged.get("description")
        if desc:
            kwargs["Description"] = desc
        response = client.create_secret(**kwargs)
        return {"arn": response.get("ARN"), "name": response.get("Name"), "version_id": response.get("VersionId")}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _create)


@register_node("amazon_secrets_manager.update_secret")
async def update_secret(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Update an existing secret's value."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    secret_id = merged.get("secret_id")
    secret_value = merged.get("secret_value") or merged.get("secret_string")
    if not secret_id or not secret_value:
        raise ValueError("update_secret requires 'secret_id' and 'secret_value'")

    def _update():
        client = _get_client(creds)
        if isinstance(secret_value, dict):
            sv = json.dumps(secret_value)
        else:
            sv = str(secret_value)
        response = client.update_secret(SecretId=secret_id, SecretString=sv)
        return {"arn": response.get("ARN"), "name": response.get("Name"), "version_id": response.get("VersionId")}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _update)


@register_node("amazon_secrets_manager.delete_secret")
async def delete_secret(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Delete a secret, optionally with a recovery window."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    secret_id = merged.get("secret_id")
    if not secret_id:
        raise ValueError("delete_secret requires 'secret_id'")
    recovery_window = merged.get("recovery_window_in_days", 30)
    force = merged.get("force_delete_without_recovery", False)

    def _delete():
        client = _get_client(creds)
        kwargs = {"SecretId": secret_id}
        if force:
            kwargs["ForceDeleteWithoutRecovery"] = True
        else:
            kwargs["RecoveryWindowInDays"] = int(recovery_window)
        response = client.delete_secret(**kwargs)
        return {
            "arn": response.get("ARN"),
            "name": response.get("Name"),
            "deletion_date": str(response.get("DeletionDate", "")),
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _delete)


@register_node("amazon_secrets_manager.list_secrets")
async def list_secrets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """List secrets in Secrets Manager."""
    import asyncio
    merged = {**config, **input_data}
    creds = await get_credential_data(credential_id, db) if credential_id else merged
    max_results = int(merged.get("max_results", 100))

    def _list():
        client = _get_client(creds)
        response = client.list_secrets(MaxResults=max_results)
        secrets = response.get("SecretList", [])
        return {"secrets": secrets, "count": len(secrets), "next_token": response.get("NextToken")}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _list)
