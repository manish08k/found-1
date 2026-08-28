"""
TOTP-based MFA (Google Authenticator / Authy / 1Password compatible).

Mandatory for admin/owner roles once MFA_ENFORCE_FOR_ELEVATED_ROLES is
true (default) — those are exactly the roles that can now add raw
database credentials and save write-capable workflow nodes
(api/middleware/rbac.py), so they're the highest-value account takeover
target. Optional (but available) for everyone else.

The TOTP secret itself is stored encrypted (reuses
credentials/encryption.py — same treatment as any other secret at rest,
not a special case).
"""
import pyotp
import structlog

from core.config import settings
from credentials.encryption import encrypt_credential, decrypt_credential
from storage.models import User

log = structlog.get_logger(__name__)

MFA_ENFORCE_FOR_ELEVATED_ROLES = True
_ELEVATED_ROLES = {"admin", "owner"}


def generate_mfa_secret() -> str:
    return pyotp.random_base32()


def encrypt_mfa_secret(secret: str) -> str:
    return encrypt_credential({"secret": secret}, settings.APP_SECRET_KEY)


def decrypt_mfa_secret(blob: str) -> str:
    return decrypt_credential(blob, settings.APP_SECRET_KEY)["secret"]


def provisioning_uri(secret: str, email: str) -> str:
    """otpauth:// URI for a QR code — feed this to any TOTP authenticator app."""
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="AutoFlow")


def verify_totp_code(secret: str, code: str) -> bool:
    totp = pyotp.totp.TOTP(secret)
    # valid_window=1 tolerates normal clock drift (accepts the previous/
    # next 30s window too) without materially weakening the 6-digit code.
    return totp.verify(code, valid_window=1)


def mfa_required_for(user: User) -> bool:
    """
    Whether this user's role means they must have MFA enabled to log in
    at all — not just "may enable it". Solo/no-org users are never forced
    (nothing to protect a teammate from), matching the same philosophy as
    api/middleware/rbac.py's personal-workspace carve-out.
    """
    if not MFA_ENFORCE_FOR_ELEVATED_ROLES:
        return False
    if not user.org_id or not user.role:
        return False
    return user.role.value in _ELEVATED_ROLES
