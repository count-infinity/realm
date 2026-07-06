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



class AuthService:
    """
    Account identity: lookup, verification, creation, and login rate
    limiting. GameServer delegates _do_connect/_do_create identity work
    here; session linkage and the chargen flow stay in the composition
    root.

    Rate limiting is per character name, in memory: more than
    ``max_attempts`` failures inside ``window_seconds`` locks the name
    until the window drains (protects against online guessing; scrypt
    already makes offline guessing expensive).
    """

    def __init__(self, persistence, *, max_attempts: int = 5,
                 window_seconds: float = 60.0, clock=None):
        import time
        self._persistence = persistence
        self._max_attempts = max_attempts
        self._window = window_seconds
        self._clock = clock or time.monotonic
        self._failures: dict[str, list[float]] = {}

    # --- Rate limiting ---

    def _prune(self, key: str) -> list[float]:
        now = self._clock()
        stamps = [t for t in self._failures.get(key, [])
                  if now - t < self._window]
        self._failures[key] = stamps
        return stamps

    def is_locked(self, name: str) -> bool:
        return len(self._prune(name.lower())) >= self._max_attempts

    def record_failure(self, name: str) -> None:
        self._failures.setdefault(name.lower(), []).append(self._clock())

    # --- Identity ---

    async def authenticate(self, name: str, password: str):
        """
        Returns (player, "") on success, (None, user_message) on failure.
        Upgrades legacy plaintext passwords in place on success.
        """
        if self.is_locked(name):
            return None, ("Too many failed attempts. "
                          "Wait a minute and try again.")

        matches = self._persistence.find_cached(tag='player', name=name)
        player = matches[0] if matches else None
        if player is None:
            return None, (f"Character '{name}' not found. "
                          "Use 'create' to make one.")

        stored = str(player.db.get('password') or '')
        ok, needs_rehash = verify_password(password, stored)
        if not ok:
            self.record_failure(name)
            return None, "Invalid password."

        if needs_rehash:
            player.db.password = hash_password(password)
            await self._persistence.save(player)
        return player, ""

    async def create_account(self, name: str, password: str, *, system=None):
        """
        Create a fresh character (hashed password, system baseline).
        Returns (player, "") or (None, user_message). The caller places
        them in the world / starts chargen.
        """
        from realm.core.objects import GameObject

        if self._persistence.find_cached(tag='player', name=name):
            return None, f"Character '{name}' already exists."

        player = GameObject(
            name=name,
            description=f"This is {name}.",
            location=None,
            tags=['player'],
        )
        player.db.password = hash_password(password)
        if system is not None:
            system.apply_baseline(player)
        return player, ""


__all__ = ["hash_password", "verify_password", "AuthService"]
