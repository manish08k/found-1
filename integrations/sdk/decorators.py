"""
Integration SDK — Operation & Trigger decorators.

These decorators mark methods on a ``BaseIntegration`` subclass so that
``register_all()`` can auto-register them with the execution engine's
``NODE_HANDLERS`` dict.

Usage example::

    class MyIntegration(BaseIntegration):
        name = "myapp"

        @operation(
            "myapp.create_record",
            label="Create Record",
            description="Creates a new record in MyApp",
            input_schema={"title": {"type": "string", "required": True}},
            output_schema={"id": {"type": "string"}, "url": {"type": "string"}},
        )
        async def create_record(self, config, input_data, credential_id, db):
            ...

        @trigger(
            "myapp.new_record",
            label="New Record",
            description="Fires when a new record is created",
            trigger_type="webhook",
        )
        async def on_new_record(self, config, input_data, credential_id, db):
            ...
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Any, Callable, Literal


# ── Metadata containers ────────────────────────────────────────────────────────

@dataclass
class OperationMeta:
    """Metadata attached to a method decorated with ``@operation``."""
    node_type: str
    label: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    is_operation: bool = True
    is_trigger: bool = False


@dataclass
class TriggerMeta:
    """Metadata attached to a method decorated with ``@trigger``."""
    node_type: str
    label: str
    description: str = ""
    trigger_type: Literal["webhook", "poll"] = "webhook"
    is_operation: bool = False
    is_trigger: bool = True


# ── Decorator factories ────────────────────────────────────────────────────────

def operation(
    node_type: str,
    label: str,
    description: str = "",
    input_schema: dict[str, Any] | None = None,
    output_schema: dict[str, Any] | None = None,
) -> Callable:
    """
    Mark a ``BaseIntegration`` method as a registerable node operation.

    Parameters
    ----------
    node_type:
        The unique dot-namespaced node type string
        (e.g. ``"myapp.create_record"``). This is the key used in
        ``NODE_HANDLERS`` and in workflow node definitions.
    label:
        Short human-readable name shown in the UI node picker.
    description:
        Longer description shown in the node picker tooltip / docs.
    input_schema:
        JSON-Schema-like dict describing accepted input fields.
        Keys are field names; values are dicts with ``type``, ``required``,
        ``description``, ``default``, etc.
    output_schema:
        JSON-Schema-like dict describing the fields returned by this
        operation.
    """
    def decorator(fn: Callable) -> Callable:
        meta = OperationMeta(
            node_type=node_type,
            label=label,
            description=description,
            input_schema=input_schema or {},
            output_schema=output_schema or {},
        )
        fn._sdk_meta = meta  # type: ignore[attr-defined]

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await fn(*args, **kwargs)

        wrapper._sdk_meta = meta  # type: ignore[attr-defined]
        return wrapper

    return decorator


def trigger(
    node_type: str,
    label: str,
    description: str = "",
    trigger_type: Literal["webhook", "poll"] = "webhook",
) -> Callable:
    """
    Mark a ``BaseIntegration`` method as a trigger node.

    Trigger handlers receive events from external systems and emit
    ``trigger_data`` into the workflow engine.

    Parameters
    ----------
    node_type:
        The unique dot-namespaced node type string
        (e.g. ``"myapp.new_record"``).
    label:
        Short human-readable name shown in the UI trigger picker.
    description:
        Longer description.
    trigger_type:
        ``"webhook"`` — the provider pushes events to our endpoint.
        ``"poll"`` — we periodically poll the provider for new events.
    """
    def decorator(fn: Callable) -> Callable:
        meta = TriggerMeta(
            node_type=node_type,
            label=label,
            description=description,
            trigger_type=trigger_type,
        )
        fn._sdk_meta = meta  # type: ignore[attr-defined]

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await fn(*args, **kwargs)

        wrapper._sdk_meta = meta  # type: ignore[attr-defined]
        return wrapper

    return decorator
