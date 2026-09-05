"""
JWT — create and verify JSON Web Tokens.

Uses `python-jose` (preferred) or `PyJWT` when available.  Falls back to
a minimal stdlib-only base64 decoder for decode-only operations (no
signature verification in fallback mode — clearly indicated in output).

Credential fields:
  - secret    : shared secret (for HS256) or PEM private key (for RS256)
  - algorithm : 'HS256' (default) or 'RS256'

Nodes:
  - jwt.create_token  : sign and return a JWT string
  - jwt.decode_token  : decode a JWT without mandatory verification
  - jwt.verify_token  : verify signature and return claims
"""
import json
import base64
import structlog

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Optional library detection
# ---------------------------------------------------------------------------
_JOSE_AVAILABLE = False
_PYJWT_AVAILABLE = False

try:
    from jose import jwt as _jose_jwt, JWTError as _JoseJWTError  # type: ignore
    _JOSE_AVAILABLE = True
except ImportError:
    pass

if not _JOSE_AVAILABLE:
    try:
        import jwt as _pyjwt  # type: ignore
        _PYJWT_AVAILABLE = True
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _b64url_decode(s: str) -> bytes:
    """URL-safe base64 decode with padding."""
    padded = s + "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(padded)


def _stdlib_decode(token: str) -> dict:
    """Decode JWT payload without signature verification (stdlib fallback)."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT: expected 3 dot-separated parts")
    header_json = _b64url_decode(parts[0])
    payload_json = _b64url_decode(parts[1])
    header = json.loads(header_json)
    payload = json.loads(payload_json)
    return {"header": header, "payload": payload, "verified": False}


async def _get_creds(credential_id: str, db) -> tuple[str, str]:
    creds = await get_credential_data(credential_id, db)
    secret = creds.get("secret")
    algorithm = creds.get("algorithm", "HS256").upper()
    if not secret:
        raise ValueError("jwt credential missing 'secret'")
    return secret, algorithm


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("jwt.create_token")
async def jwt_create_token(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Sign and return a JWT string.

    Config / input_data fields:
      - claims (required) : dict of payload claims, e.g. {"sub": "user123", "exp": 1234567890}
      - headers           : dict of additional header fields (optional)

    Credential fields:
      - secret    : HMAC secret or RSA private key PEM
      - algorithm : 'HS256' (default) or 'RS256'
    """
    claims = config.get("claims") or input_data.get("claims")
    if not claims or not isinstance(claims, dict):
        raise ValueError("jwt.create_token requires 'claims' as a dict")

    headers = config.get("headers") or input_data.get("headers", {})
    secret, algorithm = await _get_creds(credential_id, db)

    if _JOSE_AVAILABLE:
        token = _jose_jwt.encode(claims, secret, algorithm=algorithm, headers=headers or None)
    elif _PYJWT_AVAILABLE:
        token = _pyjwt.encode(claims, secret, algorithm=algorithm, headers=headers or None)
        # PyJWT 2.x returns str; 1.x returns bytes
        if isinstance(token, bytes):
            token = token.decode("utf-8")
    else:
        raise RuntimeError(
            "jwt.create_token requires 'python-jose' or 'PyJWT'. "
            "Install one: pip install python-jose[cryptography]"
        )

    log.info("jwt.create_token", algorithm=algorithm, claims_keys=list(claims.keys()))
    return {"token": token, "algorithm": algorithm}


@register_node("jwt.decode_token")
async def jwt_decode_token(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Decode a JWT without mandatory signature verification.

    Config / input_data fields:
      - token (required) : the JWT string to decode

    Returns header, payload, and a 'verified' flag (False when using
    the stdlib fallback — no library present).
    """
    token = config.get("token") or input_data.get("token")
    if not token:
        raise ValueError("jwt.decode_token requires 'token'")

    if _JOSE_AVAILABLE:
        header = _jose_jwt.get_unverified_header(token)
        payload = _jose_jwt.get_unverified_claims(token)
        result = {"header": header, "payload": payload, "verified": False}
    elif _PYJWT_AVAILABLE:
        header = _pyjwt.get_unverified_header(token)
        payload = _pyjwt.decode(token, options={"verify_signature": False})
        result = {"header": header, "payload": payload, "verified": False}
    else:
        result = _stdlib_decode(token)

    log.info("jwt.decode_token", subject=result["payload"].get("sub"))
    return result


@register_node("jwt.verify_token")
async def jwt_verify_token(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Verify a JWT signature and return its claims.

    Config / input_data fields:
      - token    (required) : the JWT string to verify
      - audience            : expected audience claim (optional)
      - issuer              : expected issuer claim (optional)

    Credential fields:
      - secret    : HMAC secret or RSA public key PEM for verification
      - algorithm : 'HS256' (default) or 'RS256'

    Raises ValueError if signature is invalid or claims are not satisfied.
    """
    token = config.get("token") or input_data.get("token")
    if not token:
        raise ValueError("jwt.verify_token requires 'token'")

    audience = config.get("audience") or input_data.get("audience")
    issuer = config.get("issuer") or input_data.get("issuer")
    secret, algorithm = await _get_creds(credential_id, db)

    options: dict = {}
    if audience:
        options["audience"] = audience
    if issuer:
        options["issuer"] = issuer

    if _JOSE_AVAILABLE:
        try:
            payload = _jose_jwt.decode(token, secret, algorithms=[algorithm], **options)
            verified = True
        except _JoseJWTError as exc:
            raise ValueError(f"JWT verification failed: {exc}") from exc
    elif _PYJWT_AVAILABLE:
        try:
            decode_kwargs: dict = {"algorithms": [algorithm]}
            if audience:
                decode_kwargs["audience"] = audience
            if issuer:
                decode_kwargs["issuer"] = issuer
            payload = _pyjwt.decode(token, secret, **decode_kwargs)
            verified = True
        except Exception as exc:
            raise ValueError(f"JWT verification failed: {exc}") from exc
    else:
        raise RuntimeError(
            "jwt.verify_token requires 'python-jose' or 'PyJWT'. "
            "Install one: pip install python-jose[cryptography]"
        )

    log.info("jwt.verify_token", verified=verified, subject=payload.get("sub"))
    return {"payload": payload, "verified": verified, "algorithm": algorithm}
