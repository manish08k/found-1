"""
Integration SDK — CredentialHelper.

Provides a clean async interface for decrypting and validating credentials
stored in the ``OAuthCredential`` table.  Integration handlers should use
this instead of calling ``oauth.flow.get_credential_data`` directly, since
it adds field-level validation and clearer error messages.
"""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from integrations.sdk.errors import AuthenticationError

log = structlog.get_logger(__name__)


class CredentialHelper:
    """
    Async helper for loading and validating integration credentials.

    All public methods are ``async`` and accept a SQLAlchemy async session.
    The class itself holds no state — it can be used as a singleton.

    Usage
    -----
    .. code-block:: python

        credential = await CredentialHelper.get(credential_id, db)
        CredentialHelper.validate_fields(credential, ["api_key", "base_url"])
        api_key = credential["api_key"]
    """

    @staticmethod
    async def get(credential_id: str, db: AsyncSession) -> dict[str, Any]:
        """
        Decrypt and return the credential fields for ``credential_id``.

        The decryption delegates to ``oauth.flow.get_credential_data``
        which handles both envelope-encrypted static credentials and
        OAuth access tokens (refreshing if necessary).

        Raises
        ------
        AuthenticationError
            If the credential does not exist or cannot be decrypted.
        """
        if not credential_id:
            raise AuthenticationError(
                "credential_id is required but was not provided",
                provider="",
            )

        try:
            # Import here to avoid a circular import at module level.
            from oauth.flow import get_credential_data

            data: dict[str, Any] = await get_credential_data(credential_id, db)
            if data is None:
                raise AuthenticationError(
                    f"Credential '{credential_id}' returned no data — "
                    "it may have been deleted or not yet configured.",
                    provider="",
                )
            return data
        except AuthenticationError:
            raise
        except Exception as exc:
            log.error("credential_load_failed", credential_id=credential_id, error=str(exc))
            raise AuthenticationError(
                f"Failed to load credential '{credential_id}': {exc}",
                provider="",
            ) from exc

    @staticmethod
    def validate_fields(credential: dict[str, Any], required_fields: list[str]) -> None:
        """
        Assert that every field name in ``required_fields`` is present
        in ``credential`` and has a non-empty, non-None value.

        Raises
        ------
        AuthenticationError
            With a message that lists all missing/empty fields.
        """
        missing = [
            field
            for field in required_fields
            if not credential.get(field)
        ]
        if missing:
            raise AuthenticationError(
                f"Credential is missing required field(s): {', '.join(missing)}. "
                "Please update the credential configuration.",
                provider="",
            )

    @staticmethod
    async def get_validated(
        credential_id: str,
        db: AsyncSession,
        required_fields: list[str],
    ) -> dict[str, Any]:
        """
        Convenience method: load and validate in one call.

        Equivalent to::

            cred = await CredentialHelper.get(credential_id, db)
            CredentialHelper.validate_fields(cred, required_fields)
            return cred
        """
        credential = await CredentialHelper.get(credential_id, db)
        CredentialHelper.validate_fields(credential, required_fields)
        return credential
