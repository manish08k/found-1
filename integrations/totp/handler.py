"""
TOTP two-factor authentication code generator integration.

Generates and verifies time-based one-time passwords (RFC 6238).
Uses pyotp if available, falls back to a manual HMAC-SHA1 implementation.

Credential fields:
  - secret : Base32-encoded TOTP secret
"""
import structlog
import httpx  # noqa: F401 — kept for consistency with platform pattern

from core.execution_engine import register_node
from oauth.flow import get_credential_data

try:
    import pyotp
    _PYOTP_AVAILABLE = True
except ImportError:
    pyotp = None  # type: ignore[assignment]
    _PYOTP_AVAILABLE = False

# RFC 6238 manual fallback imports
import hmac
import hashlib
import time
import struct
import base64

log = structlog.get_logger(__name__)

_DEFAULT_PERIOD = 30
_DEFAULT_DIGITS = 6


def _manual_totp(secret_b32: str, timestamp: float | None = None, period: int = _DEFAULT_PERIOD, digits: int = _DEFAULT_DIGITS) -> str:
    """RFC 6238 manual TOTP implementation using HMAC-SHA1."""
    # Decode the base32 secret (pad if needed)
    secret_b32 = secret_b32.upper().strip()
    padding = (8 - len(secret_b32) % 8) % 8
    secret_bytes = base64.b32decode(secret_b32 + "=" * padding)

    t = int((timestamp if timestamp is not None else time.time()) / period)
    msg = struct.pack(">Q", t)
    h = hmac.new(secret_bytes, msg, hashlib.sha1).digest()

    offset = h[-1] & 0x0F
    code_int = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    code = code_int % (10 ** digits)
    return str(code).zfill(digits)


async def _get_secret(credential_id: str, db) -> str:
    creds = await get_credential_data(credential_id, db)
    secret = creds.get("secret")
    if not secret:
        raise ValueError("TOTP credential missing 'secret'")
    return secret.strip()


@register_node("totp.generate_code")
async def totp_generate_code(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Generate the current TOTP code."""
    period = int(config.get("period") or input_data.get("period", _DEFAULT_PERIOD))
    digits = int(config.get("digits") or input_data.get("digits", _DEFAULT_DIGITS))

    secret = await _get_secret(credential_id, db)
    now = time.time()

    if _PYOTP_AVAILABLE:
        totp = pyotp.TOTP(secret, digits=digits, interval=period)
        code = totp.now()
        remaining_seconds = period - int(now) % period
    else:
        code = _manual_totp(secret, timestamp=now, period=period, digits=digits)
        remaining_seconds = period - int(now) % period

    log.info("totp.generate_code", digits=digits, period=period, remaining=remaining_seconds)
    return {
        "code": code,
        "period": period,
        "digits": digits,
        "remaining_seconds": remaining_seconds,
        "backend": "pyotp" if _PYOTP_AVAILABLE else "manual_rfc6238",
    }


@register_node("totp.verify_code")
async def totp_verify_code(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Verify a TOTP code allowing for clock drift."""
    code = str(config.get("code") or input_data.get("code", "")).strip()
    period = int(config.get("period") or input_data.get("period", _DEFAULT_PERIOD))
    digits = int(config.get("digits") or input_data.get("digits", _DEFAULT_DIGITS))
    # valid_window: number of periods before/after to check (default 1 = ±1 period)
    valid_window = int(config.get("valid_window") or input_data.get("valid_window", 1))

    if not code:
        raise ValueError("totp.verify_code requires 'code'")

    secret = await _get_secret(credential_id, db)
    now = time.time()

    if _PYOTP_AVAILABLE:
        totp = pyotp.TOTP(secret, digits=digits, interval=period)
        valid = totp.verify(code, valid_window=valid_window)
    else:
        valid = False
        for delta in range(-valid_window, valid_window + 1):
            candidate_time = now + delta * period
            expected = _manual_totp(secret, timestamp=candidate_time, period=period, digits=digits)
            if hmac.compare_digest(expected, code):
                valid = True
                break

    log.info("totp.verify_code", valid=valid, backend="pyotp" if _PYOTP_AVAILABLE else "manual_rfc6238")
    return {
        "valid": valid,
        "code": code,
        "backend": "pyotp" if _PYOTP_AVAILABLE else "manual_rfc6238",
    }
