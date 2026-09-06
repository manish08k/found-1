"""HashiCorp Vault integration — read, write, delete, and list secrets."""
import httpx
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _vault_headers(vault_token: str) -> dict:
    return {"X-Vault-Token": vault_token, "Content-Type": "application/json"}


def _vault_base(vault_addr: str) -> str:
    return vault_addr.rstrip("/") + "/v1"


@register_node("hashi_corp_vault.read_secret")
async def hashi_corp_vault_read_secret(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Read a secret from HashiCorp Vault (KV v2).

    config:
      vault_addr  — Vault server address e.g. https://vault.example.com (required)
      vault_token — Vault token with read permission (required)
      mount_path  — KV secrets engine mount path, default "secret" (optional)
      secret_path — path to the secret (required)
      version     — version of the secret to read (optional)
    """
    merged = {**config, **input_data}
    vault_addr = merged.get("vault_addr", "")
    vault_token = merged.get("vault_token", "")
    mount_path = merged.get("mount_path", "secret")
    secret_path = merged.get("secret_path")

    if not vault_addr or not secret_path:
        raise ValueError("vault_addr and secret_path are required for hashi_corp_vault.read_secret")

    params: dict = {}
    if merged.get("version"):
        params["version"] = merged["version"]

    async with httpx.AsyncClient(base_url=_vault_base(vault_addr), timeout=30) as client:
        r = await client.get(
            f"/{mount_path}/data/{secret_path}",
            headers=_vault_headers(vault_token),
            params=params,
        )
        r.raise_for_status()
        data = r.json()

    secret_data = data.get("data", {}).get("data", {})
    metadata = data.get("data", {}).get("metadata", {})
    log.info("hashi_corp_vault.read_secret", secret_path=secret_path, version=metadata.get("version"))
    return {"data": secret_data, "metadata": metadata, "secret_path": secret_path}


@register_node("hashi_corp_vault.write_secret")
async def hashi_corp_vault_write_secret(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Write or update a secret in HashiCorp Vault (KV v2).

    config:
      vault_addr  — Vault server address (required)
      vault_token — Vault token with write permission (required)
      mount_path  — KV secrets engine mount path, default "secret" (optional)
      secret_path — path to the secret (required)
      data        — dict of key-value pairs to store (required)
      cas         — check-and-set version for optimistic locking (optional)
    """
    merged = {**config, **input_data}
    vault_addr = merged.get("vault_addr", "")
    vault_token = merged.get("vault_token", "")
    mount_path = merged.get("mount_path", "secret")
    secret_path = merged.get("secret_path")
    secret_data = merged.get("data", {})

    if not vault_addr or not secret_path:
        raise ValueError("vault_addr and secret_path are required for hashi_corp_vault.write_secret")
    if not secret_data:
        raise ValueError("data dict is required for hashi_corp_vault.write_secret")

    payload: dict = {"data": secret_data}
    if merged.get("cas") is not None:
        payload["options"] = {"cas": merged["cas"]}

    async with httpx.AsyncClient(base_url=_vault_base(vault_addr), timeout=30) as client:
        r = await client.post(
            f"/{mount_path}/data/{secret_path}",
            headers=_vault_headers(vault_token),
            json=payload,
        )
        r.raise_for_status()
        response = r.json()

    version = response.get("data", {}).get("version")
    log.info("hashi_corp_vault.write_secret", secret_path=secret_path, version=version)
    return {"success": True, "secret_path": secret_path, "version": version}


@register_node("hashi_corp_vault.delete_secret")
async def hashi_corp_vault_delete_secret(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Delete a secret (or specific versions) from HashiCorp Vault (KV v2).

    config:
      vault_addr  — Vault server address (required)
      vault_token — Vault token with delete permission (required)
      mount_path  — KV secrets engine mount path, default "secret" (optional)
      secret_path — path to the secret (required)
      versions    — list of version numbers to delete; omit to delete latest (optional)
    """
    merged = {**config, **input_data}
    vault_addr = merged.get("vault_addr", "")
    vault_token = merged.get("vault_token", "")
    mount_path = merged.get("mount_path", "secret")
    secret_path = merged.get("secret_path")

    if not vault_addr or not secret_path:
        raise ValueError(
            "vault_addr and secret_path are required for hashi_corp_vault.delete_secret"
        )

    async with httpx.AsyncClient(base_url=_vault_base(vault_addr), timeout=30) as client:
        if merged.get("versions"):
            # Delete specific versions
            r = await client.post(
                f"/{mount_path}/delete/{secret_path}",
                headers=_vault_headers(vault_token),
                json={"versions": merged["versions"]},
            )
        else:
            # Delete the latest version
            r = await client.delete(
                f"/{mount_path}/data/{secret_path}",
                headers=_vault_headers(vault_token),
            )
        r.raise_for_status()

    log.info("hashi_corp_vault.delete_secret", secret_path=secret_path)
    return {"success": True, "secret_path": secret_path}


@register_node("hashi_corp_vault.list_secrets")
async def hashi_corp_vault_list_secrets(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """List secret keys at a given path in HashiCorp Vault (KV v2).

    config:
      vault_addr  — Vault server address (required)
      vault_token — Vault token with list permission (required)
      mount_path  — KV secrets engine mount path, default "secret" (optional)
      secret_path — path prefix to list (optional, default "")
    """
    merged = {**config, **input_data}
    vault_addr = merged.get("vault_addr", "")
    vault_token = merged.get("vault_token", "")
    mount_path = merged.get("mount_path", "secret")
    secret_path = merged.get("secret_path", "")

    if not vault_addr:
        raise ValueError("vault_addr is required for hashi_corp_vault.list_secrets")

    path = f"/{mount_path}/metadata/{secret_path}".rstrip("/")

    async with httpx.AsyncClient(base_url=_vault_base(vault_addr), timeout=30) as client:
        r = await client.request(
            "LIST", path, headers=_vault_headers(vault_token)
        )
        r.raise_for_status()
        data = r.json()

    keys = data.get("data", {}).get("keys", [])
    log.info("hashi_corp_vault.list_secrets", secret_path=secret_path, count=len(keys))
    return {"keys": keys, "count": len(keys), "secret_path": secret_path}


@register_node("hashi_corp_vault.renew_token")
async def hashi_corp_vault_renew_token(
    config: dict, input_data: dict, credential_id: str | None, db
) -> dict:
    """Renew the current Vault token to extend its TTL.

    config:
      vault_addr  — Vault server address (required)
      vault_token — Vault token to renew (required)
      increment   — requested TTL increment e.g. "1h" (optional)
    """
    merged = {**config, **input_data}
    vault_addr = merged.get("vault_addr", "")
    vault_token = merged.get("vault_token", "")

    if not vault_addr or not vault_token:
        raise ValueError("vault_addr and vault_token are required for hashi_corp_vault.renew_token")

    payload: dict = {}
    if merged.get("increment"):
        payload["increment"] = merged["increment"]

    async with httpx.AsyncClient(base_url=_vault_base(vault_addr), timeout=30) as client:
        r = await client.post(
            "/auth/token/renew-self",
            headers=_vault_headers(vault_token),
            json=payload,
        )
        r.raise_for_status()
        data = r.json()

    auth = data.get("auth", {})
    log.info("hashi_corp_vault.renew_token", lease_duration=auth.get("lease_duration"))
    return {"auth": auth, "lease_duration": auth.get("lease_duration")}
