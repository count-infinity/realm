"""
Password hashing for REALM accounts.

scrypt (stdlib hashlib) with per-password salt, stored as
``scrypt$<salt_hex>$<hash_hex>``. verify_password accepts legacy
plaintext (pre-hashing accounts) and reports it so the caller can
rehash in place on successful login.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_SCRYPT = {'n': 2 ** 14, 'r': 8, 'p': 1}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> tuple[bool, bool]:
    """
    Check a password. Returns (ok, needs_rehash).

    needs_rehash is True when the stored value is legacy plaintext —
    the caller should overwrite it with hash_password(password).
    """
    if stored.startswith("scrypt$"):
        try:
            _scheme, salt_hex, hash_hex = stored.split("$", 2)
            digest = hashlib.scrypt(
                password.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
            return hmac.compare_digest(digest.hex(), hash_hex), False
        except (ValueError, TypeError):
            return False, False
    # Legacy plaintext account.
    return hmac.compare_digest(password, stored), True


__all__ = ["hash_password", "verify_password"]
