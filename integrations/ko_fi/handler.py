"""Ko-fi — creator platform integration (webhook passthrough + verification)."""
import structlog
import httpx

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

# Ko-fi does not provide a full REST API; data is delivered via webhooks.
# The CDN endpoint below exposes a minimal public profile JSON.
KOFI_CDN_BASE = "https://storage.ko-fi.com/cdn/githubapi"


@register_node("ko_fi.list_transactions")
async def ko_fi_list_transactions(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Retrieve Ko-fi public profile/transaction data via the CDN token endpoint.

    Ko-fi's API is primarily webhook-based. This node fetches the publicly
    accessible JSON associated with a Ko-fi token. For real-time donation
    data, configure Ko-fi webhook delivery and use ko_fi.verify_webhook.

    config:
      token — Ko-fi token (found in Ko-fi settings, used in webhook URLs)
    """
    token = config.get("token", "")
    if not token:
        raise ValueError("token is required for ko_fi.list_transactions")

    async with httpx.AsyncClient(base_url=KOFI_CDN_BASE, timeout=30) as client:
        r = await client.get("/ko-fi.json", params={"kofitoken": token})
        r.raise_for_status()
        data = r.json()

    transactions = data if isinstance(data, list) else data.get("transactions", [data])
    log.info("ko_fi.list_transactions", token_prefix=token[:6])
    return {"transactions": transactions, "raw": data}


@register_node("ko_fi.verify_webhook")
async def ko_fi_verify_webhook(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Verify an incoming Ko-fi webhook payload.

    Checks that the verification_token in the webhook payload matches the
    configured token, confirming the webhook originated from Ko-fi.

    config:
      token — Ko-fi verification token (from Ko-fi Webhooks settings)

    input_data:
      verification_token — token from the webhook payload (required)
      type               — event type, e.g. "Donation", "Subscription"
      message_id         — unique message ID from Ko-fi
      amount             — transaction amount
      currency           — transaction currency code
      email              — supporter email (may be empty)
      kofi_transaction_id — Ko-fi internal transaction ID
      (any additional webhook fields are passed through)
    """
    expected_token = config.get("token", "")
    received_token = input_data.get("verification_token", "")

    if not expected_token:
        raise ValueError("token must be set in config for ko_fi.verify_webhook")

    is_valid = expected_token == received_token

    log.info(
        "ko_fi.verify_webhook",
        valid=is_valid,
        event_type=input_data.get("type"),
        message_id=input_data.get("message_id"),
    )

    if not is_valid:
        return {
            "valid": False,
            "error": "Verification token mismatch — webhook may not be from Ko-fi",
            "payload": input_data,
        }

    return {
        "valid": True,
        "type": input_data.get("type"),
        "message_id": input_data.get("message_id"),
        "amount": input_data.get("amount"),
        "currency": input_data.get("currency"),
        "email": input_data.get("email"),
        "kofi_transaction_id": input_data.get("kofi_transaction_id"),
        "payload": input_data,
    }
