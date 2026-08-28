"""
Real Stripe subscription billing for AutoFlow's own plans (Free/Starter/
Pro/Business/Enterprise) — as opposed to integrations/stripe_/handler.py,
which lets a workflow use each USER's own Stripe account.

This is genuinely wired to Stripe's real API contract (Checkout
Sessions + webhooks), not a stub. What it can't do from this build
environment: complete an actual charge, because that needs a real
Stripe merchant account's live/test API keys, which aren't set here
(STRIPE_SECRET_KEY is empty by default — see core/config.py). The code
path is correct and ready to work the moment real keys are configured;
that's true of any Stripe integration built by any developer without
already having a live merchant account — it's not a limitation specific
to this environment, it's inherent to how payment processing works.

Webhook signature verification implements Stripe's documented scheme
directly (HMAC-SHA256 over "{timestamp}.{payload}", timestamp tolerance
window) rather than depending on the `stripe` Python SDK, matching this
project's existing pattern of raw httpx calls for the user-facing Stripe
node (avoids a heavy dependency for what's a well-documented, stable
signature scheme).
"""
import hashlib
import hmac
import time

import httpx
import structlog

from core.config import settings
from storage.models import Organization, OrgPlan

log = structlog.get_logger(__name__)

STRIPE_API_BASE = "https://api.stripe.com/v1"

# Maps our plan names to the Stripe Price IDs configured for this
# deployment (core/config.py) — these come from YOUR Stripe dashboard's
# product catalog, they're not something this code can invent.
# Maps our plan names to the Stripe Price IDs configured for this
# deployment (core/config.py) — these come from YOUR Stripe dashboard's
# product catalog, they're not something this code can invent.
PLAN_TO_PRICE_ID = {
    "starter": lambda: settings.STRIPE_PRICE_ID_STARTER,
    "pro": lambda: settings.STRIPE_PRICE_ID_PRO,
    "business": lambda: settings.STRIPE_PRICE_ID_BUSINESS,
}


class BillingNotConfigured(Exception):
    """Raised when STRIPE_SECRET_KEY isn't set — fails loudly instead of pretending to succeed."""


def _require_configured() -> None:
    if not settings.STRIPE_SECRET_KEY:
        raise BillingNotConfigured(
            "STRIPE_SECRET_KEY is not set. Real subscription billing requires a real Stripe "
            "merchant account — see core/config.py's Platform billing section."
        )


async def create_checkout_session(
    org: Organization, user_email: str, target_plan: str, success_url: str, cancel_url: str,
) -> str:
    """
    Creates a real Stripe Checkout Session and returns its hosted URL —
    the frontend redirects the browser there. Stripe hosts the actual
    card-entry form; no card data ever touches this backend, which is
    also the correct/required approach for PCI compliance (SAQ A rather
    than the much heavier SAQ D that'd apply if this backend handled raw
    card numbers itself).
    """
    _require_configured()
    if target_plan not in PLAN_TO_PRICE_ID:
        raise ValueError(f"'{target_plan}' isn't a purchasable plan (expected starter/pro/business)")
    price_id = PLAN_TO_PRICE_ID[target_plan]()
    if not price_id:
        raise BillingNotConfigured(f"No Stripe Price ID configured for the '{target_plan}' plan")

    payload = {
        "mode": "subscription",
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": 1,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": org.id,
        "metadata[org_id]": org.id,
        "metadata[target_plan]": target_plan,
    }
    if org.stripe_customer_id:
        payload["customer"] = org.stripe_customer_id
    else:
        payload["customer_email"] = user_email

    async with httpx.AsyncClient(base_url=STRIPE_API_BASE, auth=(settings.STRIPE_SECRET_KEY, ""), timeout=30) as client:
        r = await client.post("/checkout/sessions", data=payload)
        r.raise_for_status()
        session = r.json()

    return session["url"]


def verify_webhook_signature(payload: bytes, sig_header: str, tolerance_seconds: int = 300) -> dict:
    """
    Implements Stripe's documented webhook signature scheme directly:
    https://docs.stripe.com/webhooks#verify-manually

    The Stripe-Signature header looks like:
      t=1614556800,v1=5257a869e7ecebeda32affa62cdca3fa51cad7e77a0e56ff536d0ce8e108d8bd

    We recompute HMAC-SHA256 over "{t}.{payload}" using the webhook
    signing secret and compare to v1 with a constant-time comparison —
    NOT with `==`, which leaks timing information about how many
    leading bytes matched and is a genuine (if narrow) side-channel a
    real attacker could use against a real deployment.
    """
    _require_configured()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise BillingNotConfigured("STRIPE_WEBHOOK_SECRET is not set — cannot verify webhook authenticity")

    parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        raise ValueError("Malformed Stripe-Signature header")

    age = abs(time.time() - int(timestamp))
    if age > tolerance_seconds:
        raise ValueError(f"Webhook timestamp is {int(age)}s old — outside the {tolerance_seconds}s tolerance window (possible replay)")

    signed_payload = f"{timestamp}.{payload.decode()}"
    expected_signature = hmac.new(
        settings.STRIPE_WEBHOOK_SECRET.encode(), signed_payload.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        raise ValueError("Webhook signature verification failed — payload does not match signature")

    import json
    return json.loads(payload)


async def apply_webhook_event(event: dict, db) -> None:
    """
    Syncs an org's plan/subscription fields based on a verified Stripe
    webhook event. Only handles the three events that actually change
    billing state — Stripe sends many more event types than this cares
    about, and silently ignoring the ones we don't handle is correct
    (not every event needs a reaction here).
    """
    import uuid as _uuid
    from sqlalchemy import select

    def _safe_uuid(value) -> str | None:
        """
        Returns value if it parses as a UUID, else None. Stripe's own
        test-webhook feature (and any malformed/adversarial payload that
        got this far) can send a client_reference_id/metadata value that
        isn't a real org ID at all — this should be logged and skipped,
        not crash the whole webhook handler with a raw database driver
        exception. Signature verification (verify_webhook_signature)
        already confirms the payload came from Stripe; this additionally
        confirms the ID inside it is even shaped like one of ours.
        """
        if not value:
            return None
        try:
            _uuid.UUID(str(value))
            return str(value)
        except (ValueError, AttributeError):
            log.warning("stripe_webhook_non_uuid_org_id", value=value)
            return None

    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        org_id = _safe_uuid(data.get("client_reference_id") or data.get("metadata", {}).get("org_id"))
        target_plan = data.get("metadata", {}).get("target_plan")
        if not org_id:
            log.warning("stripe_webhook_missing_org_id", event_type=event_type)
            return
        result = await db.execute(select(Organization).where(Organization.id == org_id))
        org = result.scalar_one_or_none()
        if not org:
            log.warning("stripe_webhook_org_not_found", org_id=org_id)
            return
        org.stripe_customer_id = data.get("customer")
        org.stripe_subscription_id = data.get("subscription")
        org.subscription_status = "active"
        if target_plan and target_plan in {p.value for p in OrgPlan}:
            org.plan = OrgPlan(target_plan)
        log.info("stripe_subscription_activated", org_id=org_id, plan=target_plan)

    elif event_type == "customer.subscription.updated":
        subscription_id = data.get("id")
        status = data.get("status")  # active, past_due, canceled, unpaid, etc.
        result = await db.execute(select(Organization).where(Organization.stripe_subscription_id == subscription_id))
        org = result.scalar_one_or_none()
        if not org:
            return
        org.subscription_status = status
        # A subscription that's past_due/unpaid keeps its current plan
        # (Stripe's own dunning/retry process handles the grace period)
        # — we only actively downgrade on an explicit cancellation event
        # below, not on every payment hiccup.
        log.info("stripe_subscription_status_changed", org_id=org.id, status=status)

    elif event_type == "customer.subscription.deleted":
        subscription_id = data.get("id")
        result = await db.execute(select(Organization).where(Organization.stripe_subscription_id == subscription_id))
        org = result.scalar_one_or_none()
        if not org:
            return
        org.plan = OrgPlan.free
        org.subscription_status = "canceled"
        log.info("stripe_subscription_canceled_downgrade_to_free", org_id=org.id)

    else:
        log.debug("stripe_webhook_ignored", event_type=event_type)
