"""
Accounts (MUD_PLAN 6.1): the thing a person logs in to.

An account is a ``GameObject`` tagged ``account``, with no location. It
holds ``password`` (the scrypt hash; a protected attribute softcode never
reads), ``characters`` (character ids, in creation order), ``created``,
``last_login``, ``last_address``, ``email``, ``banned_until`` and
``ban_reason``, and anything a game adds (account data, achievements). A
character holds ``account``, its account's id.

Account names are unique among accounts and character names among
characters; the two are separate namespaces.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from realm.core.world import find_world

if TYPE_CHECKING:
    from realm.core.objects import GameObject

ACCOUNT_TAG = "account"
SITELOCK_TAG = "sitelock_registry"
#: ``banned_until`` for a ban with no end.
FOREVER = "forever"

#: Who banned, unbanned, reset or sitelocked whom (MUD_PLAN 6.6).
admin_log = logging.getLogger("realm.admin")


def now() -> float:
    """The wall clock bans expire on (tests replace it)."""
    return time.time()


def _store() -> Any:
    world = find_world()
    return world.store if world is not None else None


def find_account(name: str) -> GameObject | None:
    """The account called ``name`` (any case), or None."""
    store = _store()
    found = store.find_cached(tag=ACCOUNT_TAG, name=str(name)) if store is not None else []
    return found[0] if found else None


def account_of(character: GameObject | None) -> GameObject | None:
    """The account a character belongs to, or None (an NPC, a character
    from before accounts, a test's bare player)."""
    if character is None:
        return None
    account_id = character.db.get("account")
    store = _store()
    if not account_id or store is None:
        return None
    account = store.get_cached(str(account_id))
    return account if account is not None and account.has_tag(ACCOUNT_TAG) else None


def characters_of(account: GameObject | None) -> list[GameObject]:
    """The account's characters, in creation order (missing ones skipped)."""
    store = _store()
    if account is None or store is None:
        return []
    out = []
    for char_id in account.db.get("characters") or []:
        char = store.get_cached(str(char_id))
        if char is not None:
            out.append(char)
    return out


def link_character(account: GameObject, character: GameObject) -> None:
    """Make ``character`` one of ``account``'s."""
    ids = list(account.db.get("characters") or [])
    if character.id not in ids:
        ids.append(character.id)
        account.db.characters = ids
    character.db.account = account.id


def unlink_character(account: GameObject, character: GameObject) -> None:
    account.db.characters = [i for i in (account.db.get("characters") or [])
                             if i != character.id]
    character.db.delete("account")


def new_account(name: str, password_hash: str) -> GameObject:
    """An account object (the caller saves it)."""
    from realm.core.objects import GameObject
    account = GameObject(name=name, tags=[ACCOUNT_TAG], location=None)
    account.db.password = password_hash
    account.db.characters = []
    account.db.created = now()
    return account


# --- bans -----------------------------------------------------------------------


def parse_duration(text: str) -> float | str | None:
    """"30m", "2h", "3d", "1w" -> seconds; "forever"/"perm" -> FOREVER;
    None when it is neither."""
    text = text.strip().lower()
    if text in ("forever", "perm", "permanent", "never"):
        return FOREVER
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    if len(text) >= 2 and text[-1] in units and text[:-1].isdigit():
        return int(text[:-1]) * units[text[-1]]
    return None


def ban_message(account: GameObject) -> str | None:
    """Why ``account`` may not connect now, or None when it may (an
    expired ban is cleared on the way)."""
    until = account.db.get("banned_until")
    if until is None:
        return None
    reason = account.db.get("ban_reason") or "no reason given"
    if until == FOREVER:
        return f"This account is banned permanently: {reason}"
    if now() >= float(until):
        account.db.delete("banned_until")
        account.db.delete("ban_reason")
        return None
    when = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(float(until)))
    return f"This account is banned until {when}: {reason}"


# --- sitelocks -------------------------------------------------------------------


def sitelock_registry() -> GameObject | None:
    """The one object that holds the sitelocks (``sites``: prefix ->
    {"reason", "by", "at"}), or None before the first sitelock."""
    store = _store()
    found = store.find_cached(tag=SITELOCK_TAG) if store is not None else []
    return found[0] if found else None


async def ensure_sitelock_registry() -> GameObject:
    """The sitelock registry, made and saved if the world has none yet."""
    registry = sitelock_registry()
    if registry is not None:
        return registry
    from realm.core.objects import GameObject
    registry = GameObject(name="sitelock registry", tags=[SITELOCK_TAG], location=None)
    registry.db.sites = {}
    await _store().save(registry)
    return registry


def sitelocked(address: str) -> str | None:
    """The reason ``address`` is locked out, or None."""
    registry = sitelock_registry()
    sites = registry.db.get("sites") if registry is not None else None
    for prefix, entry in (sites or {}).items():
        if str(address).startswith(prefix):
            return str((entry or {}).get("reason") or "this site is locked out")
    return None


__all__ = ["ACCOUNT_TAG", "SITELOCK_TAG", "FOREVER", "admin_log", "now", "find_account",
           "account_of", "characters_of", "link_character", "unlink_character",
           "new_account", "parse_duration", "ban_message", "sitelock_registry",
           "ensure_sitelock_registry", "sitelocked"]
