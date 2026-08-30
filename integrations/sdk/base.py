"""
Integration SDK — BaseIntegration.

All integration classes should subclass ``BaseIntegration`` and:

1. Define class-level metadata (``name``, ``display_name``, etc.)
2. Override ``get_headers()`` and/or ``base_url`` for auth / routing
3. Define ``credential_fields`` so the UI can render the credential form
4. Decorate handler methods with ``@operation`` or ``@trigger``
5. Call ``MyIntegration().register_all()`` from ``handler.py``

Minimal example::

    from integrations.sdk.base import BaseIntegration, CredentialField
    from integrations.sdk.decorators import operation
    from integrations.sdk.auth import BearerAuth

    class AcmeIntegration(BaseIntegration):
        name = "acme"
        display_name = "Acme Corp"
        description = "Automate Acme Corp tasks"
        icon = "acme-logo.svg"
        category = "CRM"
        base_url = "https://api.acme.com/v1"

        credential_fields = [
            CredentialField("api_key", "API Key", required=True,
                            help_text="Found in Acme → Settings → API"),
        ]

        def get_headers(self, credential: dict) -> dict:
            return {"Authorization": f"Bearer {credential['api_key']}"}

        async def test_credential(self, credential: dict) -> bool:
            async with self.build_client(credential) as client:
                data = await client.get("/me")
                return bool(data.get("id"))

        @operation("acme.list_contacts", label="List Contacts",
                   output_schema={"contacts": {"type": "array"}})
        async def list_contacts(self, config, input_data, credential_id, db):
            credential = await self._load_credential(credential_id, db)
            async with self.build_client(credential) as client:
                return await client.get("/contacts")
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx
import structlog

from integrations.sdk.errors import IntegrationError
from integrations.sdk.http import ResilientHTTPClient

log = structlog.get_logger(__name__)


# ── CredentialField ─────────────────────────────────────────────────────────

@dataclass
class CredentialField:
    """
    Describes a single field in an integration's credential form.

    Parameters
    ----------
    name:
        Internal key used to store and retrieve the value.
    label:
        Human-readable label displayed in the UI.
    type:
        HTML input type: ``"text"``, ``"password"``, ``"url"``,
        ``"email"``, ``"select"``, etc. Default ``"text"``.
    required:
        Whether the field must be non-empty. Default ``True``.
    help_text:
        Optional hint text shown below the input in the UI.
    placeholder:
        Optional placeholder value shown inside the input.
    options:
        For ``type="select"`` fields: list of ``{"value": ..., "label": ...}``
        dicts.
    """
    name: str
    label: str
    type: str = "text"
    required: bool = True
    help_text: str = ""
    placeholder: str = ""
    options: list[dict[str, str]] = field(default_factory=list)


# ── BaseIntegration ─────────────────────────────────────────────────────────

class BaseIntegration:
    """
    Base class for all integrations.

    Subclasses define class-level metadata, credential fields, auth headers,
    and handler methods (decorated with ``@operation`` / ``@trigger``).

    Class attributes
    ----------------
    name : str
        Unique machine-readable identifier (e.g. ``"stripe"``).
    display_name : str
        Human-readable name shown in the UI.
    description : str
        Short description shown in the integration catalogue.
    icon : str
        Icon URL or icon identifier for the UI.
    category : str
        Category label for grouping in the UI (e.g. ``"Payments"``).
    credential_fields : list[CredentialField]
        Fields the user must fill in to configure a credential.
    base_url : str
        Base URL used by ``build_client()``. Override in subclass or set
        the ``base_url`` class attribute.
    """

    # Subclasses MUST override these
    name: str = ""
    display_name: str = ""
    description: str = ""
    icon: str = ""
    category: str = ""

    # Subclasses should define their credential fields
    credential_fields: list[CredentialField] = []

    # Subclasses should set this or override the property
    _base_url: str = ""

    @property
    def base_url(self) -> str:
        return self._base_url

    @base_url.setter
    def base_url(self, value: str) -> None:
        self._base_url = value

    # ── Auth / client factories ────────────────────────────────────────────

    def get_headers(self, credential: dict) -> dict:
        """
        Return default HTTP headers for the given credential.

        Override this to inject auth headers (``Authorization``,
        ``X-API-Key``, etc.). The default implementation returns an empty
        dict (no auth header).

        Parameters
        ----------
        credential:
            Decrypted credential fields as returned by
            ``CredentialHelper.get()``.
        """
        return {}

    def build_client(
        self,
        credential: dict,
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        extra_headers: dict[str, str] | None = None,
    ) -> ResilientHTTPClient:
        """
        Create a ``ResilientHTTPClient`` pre-configured with the
        integration's ``base_url``, ``get_headers()`` result, and sane
        retry/timeout defaults.

        Returns a ``ResilientHTTPClient`` that should be used as an async
        context manager::

            async with self.build_client(credential) as client:
                data = await client.get("/endpoint")

        Parameters
        ----------
        credential:
            Decrypted credential dict.
        timeout:
            Per-request timeout in seconds. Default 30.
        max_retries:
            Maximum retry attempts for retriable errors. Default 3.
        extra_headers:
            Additional headers merged on top of ``get_headers()``.
        """
        headers = {**self.get_headers(credential), **(extra_headers or {})}
        return ResilientHTTPClient(
            provider=self.name,
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
            max_retries=max_retries,
        )

    # ── Credential helpers ─────────────────────────────────────────────────

    async def _load_credential(self, credential_id: str, db: Any) -> dict:
        """
        Load and decrypt a credential. Delegates to ``CredentialHelper``.

        This is a convenience method so handler code stays concise:
            credential = await self._load_credential(credential_id, db)
        """
        from integrations.sdk.credential_helper import CredentialHelper

        return await CredentialHelper.get(credential_id, db)

    async def _load_validated_credential(
        self, credential_id: str, db: Any, required_fields: list[str]
    ) -> dict:
        """Load, decrypt, and validate required fields in one call."""
        from integrations.sdk.credential_helper import CredentialHelper

        return await CredentialHelper.get_validated(credential_id, db, required_fields)

    # ── Credential testing ─────────────────────────────────────────────────

    async def test_credential(self, credential: dict) -> bool:
        """
        Verify that a credential actually works against the live API.

        Override this to make a cheap read-only API call (e.g. ``GET /me``).
        Returns ``True`` if the credential is valid, ``False`` otherwise.
        The default raises ``NotImplementedError``.

        The UI calls this when the user saves a new credential to give
        immediate feedback.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement test_credential()"
        )

    # ── Auto-registration ──────────────────────────────────────────────────

    def register_all(self) -> None:
        """
        Auto-register all ``@operation`` / ``@trigger`` decorated methods
        with the execution engine's ``NODE_HANDLERS`` dict.

        Call this from the integration's ``handler.py`` at module level::

            integration = AcmeIntegration()
            integration.register_all()

        Each decorated method is wrapped in a closure that binds ``self``
        so the registered handler conforms to the engine's signature::

            async def handler(config, input_data, credential_id, db) -> dict
        """
        from core.execution_engine import NODE_HANDLERS

        registered: list[str] = []
        for attr_name in dir(self.__class__):
            if attr_name.startswith("_"):
                continue
            attr = getattr(self.__class__, attr_name, None)
            meta = getattr(attr, "_sdk_meta", None)
            if meta is None:
                continue

            node_type = meta.node_type
            bound_method = getattr(self, attr_name)
            handler = _make_handler(bound_method, node_type, self.name)

            NODE_HANDLERS[node_type] = handler
            registered.append(node_type)

        log.info(
            "integration_registered_handlers",
            integration=self.name,
            count=len(registered),
            node_types=registered,
        )

    def get_node_definitions(self) -> list[dict[str, Any]]:
        """
        Return a list of node definition dicts for all operations/triggers
        defined on this integration. Useful for generating documentation
        or populating the UI node picker.
        """
        definitions = []
        for attr_name in dir(self.__class__):
            if attr_name.startswith("_"):
                continue
            attr = getattr(self.__class__, attr_name, None)
            meta = getattr(attr, "_sdk_meta", None)
            if meta is None:
                continue

            definitions.append({
                "node_type": meta.node_type,
                "label": getattr(meta, "label", ""),
                "description": getattr(meta, "description", ""),
                "input_schema": getattr(meta, "input_schema", {}),
                "output_schema": getattr(meta, "output_schema", {}),
                "is_trigger": getattr(meta, "is_trigger", False),
                "trigger_type": getattr(meta, "trigger_type", None),
                "integration": self.name,
            })
        return sorted(definitions, key=lambda d: d["node_type"])

    # ── Repr ───────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"


# ── Handler factory ────────────────────────────────────────────────────────────

def _make_handler(
    bound_method: Callable,
    node_type: str,
    provider_name: str,
) -> Callable:
    """
    Wrap a bound integration method in the standard handler signature
    expected by the execution engine.

    The engine calls:  ``handler(config, input_data, credential_id, db)``

    Integration methods are bound and called as:
        ``method(config, input_data, credential_id, db)``

    We also normalise the return value: if the method returns ``None``,
    we return ``{}`` to avoid downstream ``NoneType`` errors in the engine.
    """
    async def handler(
        config: dict,
        input_data: dict,
        credential_id: str,
        db: Any,
    ) -> dict:
        try:
            result = await bound_method(config, input_data, credential_id, db)
            if result is None:
                return {}
            if not isinstance(result, dict):
                return {"result": result}
            return result
        except IntegrationError:
            raise
        except Exception as exc:
            log.error(
                "integration_handler_error",
                node_type=node_type,
                provider=provider_name,
                error=str(exc),
                exc_info=True,
            )
            raise IntegrationError(
                str(exc),
                provider=provider_name,
                retryable=False,
            ) from exc

    handler.__name__ = node_type
    handler.__qualname__ = f"handler[{node_type}]"
    return handler
