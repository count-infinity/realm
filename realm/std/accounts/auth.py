"""
Password hashing and account identity for REALM.

scrypt (stdlib hashlib) with per-password salt, stored as
``scrypt$<salt_hex>$<hash_hex>``. Any other stored value never matches:
a database from before hashing (2026-07-04) must be recreated.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from realm.core.options import ACCOUNT_TAG
from realm.std.accounts.account import link_character, new_account

_SCRYPT = {'n': 2 ** 14, 'r': 8, 'p': 1}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Check a password against a stored ``scrypt$`` value. Anything else
    (including plaintext) fails closed."""
    if not stored.startswith("scrypt$"):
        return False
    try:
        _scheme, salt_hex, hash_hex = stored.split("$", 2)
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)


class AuthService:
    """
    Account identity: lookup, verification, creation, and login rate
    limiting. The login flow (``login.py``) delegates its identity work
    here; session linkage and the character menu stay in the flow.

    Rate limiting is per account name, in memory: more than
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

    def _account(self, name: str):
        found = self._persistence.find_cached(tag=ACCOUNT_TAG, name=name)
        return found[0] if found else None

    async def authenticate(self, name: str, password: str):
        """
        Returns (account, "") on success, (None, user_message) on failure.
        """
        if self.is_locked(name):
            return None, ("Too many failed attempts. "
                          "Wait a minute and try again.")
        account = self._account(name)
        if account is None:
            return None, (f"Account '{name}' not found. "
                          "Use 'create' to make one.")
        if not verify_password(password, str(account.db.get('password') or '')):
            self.record_failure(name)
            return None, "Invalid password."
        return account, ""

    def check_password(self, account, password: str) -> bool:
        return verify_password(password, str(account.db.get('password') or ''))

    def set_password(self, account, password: str) -> None:
        account.db.password = hash_password(password)

    async def create_account(self, name: str, password: str):
        """
        Create an account. Returns (account, "") or (None, user_message).
        The first account on a fresh database is the operator's: its first
        character will be the superuser.
        """
        if not name.isidentifier() or len(name) > 30:
            return None, "An account name is one word of letters, digits and _."
        if len(password) < 4:
            return None, "Choose a password of at least 4 characters."
        if self._account(name):
            return None, f"Account '{name}' already exists."
        first = (not self._persistence.find_cached(tag=ACCOUNT_TAG)
                 and not self._persistence.find_cached(tag='player'))
        account = new_account(name, hash_password(password))
        if first:
            account.db.founder = True
        await self._persistence.save(account)
        return account, ""

    async def create_character(self, account, name: str, *, system=None):
        """
        Create a character on ``account`` (the system's baseline applied).
        Returns (player, "") or (None, user_message). The caller places
        them in the world / starts chargen. The founding account's first
        character gets the ``god`` tag.
        """
        from realm.core.objects import GameObject

        if not name.isidentifier() or len(name) > 30:
            return None, "A character name is one word of letters, digits and _."
        if self._persistence.find_cached(tag='player', name=name):
            return None, f"A character called '{name}' already exists."
        player = GameObject(
            name=name,
            description=f"This is {name}.",
            location=None,
            tags=['player'],
        )
        if account.db.get('founder') and not account.db.get('characters'):
            player.add_tag('god')
            account.db.delete('founder')
        if system is not None:
            system.apply_baseline(player)
            player.db.game_system = system.system_id
        link_character(account, player)
        await self._persistence.save(player)
        await self._persistence.save(account)
        return player, ""


__all__ = ["hash_password", "verify_password", "AuthService"]
