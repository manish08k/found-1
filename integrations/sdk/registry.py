"""
Integration SDK — IntegrationRegistry.

A global registry that maps integration names to their class objects.
The registry is the single source of truth for:

- Which integrations are available
- What node types they expose
- Metadata for the UI (display_name, description, icon, category)

Usage::

    from integrations.sdk.registry import INTEGRATION_REGISTRY, IntegrationRegistry

    # Register an integration
    IntegrationRegistry.register(MyIntegration)

    # Query
    all_integrations = IntegrationRegistry.get_all()
    all_node_types   = IntegrationRegistry.get_node_types()
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Type

import structlog

if TYPE_CHECKING:
    from integrations.sdk.base import BaseIntegration

log = structlog.get_logger(__name__)

# Global dict: integration name → integration class
INTEGRATION_REGISTRY: dict[str, Type["BaseIntegration"]] = {}


class IntegrationRegistry:
    """
    Static-method namespace for managing registered integrations.

    All state lives in the module-level ``INTEGRATION_REGISTRY`` dict so
    that imports from different paths all share the same registry.
    """

    @staticmethod
    def register(integration_class: Type["BaseIntegration"]) -> Type["BaseIntegration"]:
        """
        Register an integration class.

        This does *not* call ``register_all()`` — node handlers are
        registered with the execution engine separately (typically in the
        integration's ``handler.py`` module-level code, or by calling
        ``integration_class().register_all()`` explicitly).

        Returns the class unchanged so it can be used as a class decorator::

            @IntegrationRegistry.register
            class MyIntegration(BaseIntegration):
                name = "myapp"
                ...
        """
        name = getattr(integration_class, "name", None)
        if not name:
            raise ValueError(
                f"{integration_class.__name__} must define a non-empty class attribute 'name'"
            )

        if name in INTEGRATION_REGISTRY:
            log.warning(
                "integration_registry_overwrite",
                name=name,
                previous=INTEGRATION_REGISTRY[name].__name__,
                new=integration_class.__name__,
            )

        INTEGRATION_REGISTRY[name] = integration_class
        log.debug("integration_registered", name=name, class_name=integration_class.__name__)
        return integration_class

    @staticmethod
    def get(name: str) -> Type["BaseIntegration"] | None:
        """Return the integration class registered under ``name``, or ``None``."""
        return INTEGRATION_REGISTRY.get(name)

    @staticmethod
    def get_all() -> dict[str, Type["BaseIntegration"]]:
        """Return a shallow copy of the full registry dict."""
        return dict(INTEGRATION_REGISTRY)

    @staticmethod
    def get_node_types() -> list[str]:
        """
        Return every node type exported by every registered integration.

        Collects ``_sdk_meta.node_type`` from all methods that have the
        ``_sdk_meta`` attribute (set by the ``@operation`` / ``@trigger``
        decorators).
        """
        node_types: list[str] = []
        for integration_class in INTEGRATION_REGISTRY.values():
            for attr_name in dir(integration_class):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(integration_class, attr_name, None)
                meta = getattr(attr, "_sdk_meta", None)
                if meta and hasattr(meta, "node_type"):
                    node_types.append(meta.node_type)
        return sorted(set(node_types))

    @staticmethod
    def get_metadata() -> list[dict[str, Any]]:
        """
        Return a list of metadata dicts for all registered integrations.

        Suitable for serialising to JSON for the UI's integration catalogue.
        Each dict contains ``name``, ``display_name``, ``description``,
        ``icon``, ``category``, and ``node_types``.
        """
        result = []
        for name, cls in INTEGRATION_REGISTRY.items():
            node_types = []
            for attr_name in dir(cls):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(cls, attr_name, None)
                meta = getattr(attr, "_sdk_meta", None)
                if meta and hasattr(meta, "node_type"):
                    node_types.append({
                        "node_type": meta.node_type,
                        "label": getattr(meta, "label", ""),
                        "description": getattr(meta, "description", ""),
                        "is_trigger": getattr(meta, "is_trigger", False),
                    })

            result.append({
                "name": name,
                "display_name": getattr(cls, "display_name", name),
                "description": getattr(cls, "description", ""),
                "icon": getattr(cls, "icon", ""),
                "category": getattr(cls, "category", ""),
                "node_types": sorted(node_types, key=lambda x: x["node_type"]),
            })
        return sorted(result, key=lambda x: x["name"])
