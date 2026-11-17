"""
Softcode functions: account data (MUD_PLAN 6.4). The ``accounts`` feature
declares each, in the "Accounts" group; the first parameter is the run's
frame.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from realm.core.attrflags import PROTECTED_ATTRS, has_attr_flag
from realm.std.accounts.account import ACCOUNT_RECORDS, account_of, characters_of

if TYPE_CHECKING:
    from realm.core.objects import GameObject


def _writable_account(frame, obj) -> tuple[GameObject | None, GameObject | None]:
    character = frame.resolve(obj)
    if character is None or not frame.may_mutate(character):
        return character, None
    return character, account_of(character)


def account_attr(frame, obj: GameObject | str | None, name: str, default: Any = None) -> Any:
    """
    An attribute on the character's account: shared by every character
    the same person plays. None for a character with no account.

    Example: account_attr(enactor, 'banked_gold', 0)
    """
    character = frame.resolve(obj)
    account = account_of(character)
    if account is None:
        return None
    name = str(name)
    if name in PROTECTED_ATTRS or has_attr_flag(account, name, "secret"):
        return None
    value = account.db.get(name)
    return default if value is None else value


def _check_name(account: GameObject, name: str) -> bool:
    return (name not in PROTECTED_ATTRS and name not in ACCOUNT_RECORDS
            and not has_attr_flag(account, name, "system"))


def set_account_attr(frame, obj: GameObject | str | None, name: str, value: Any) -> bool:
    """
    Set an attribute on the character's account, for every character of
    that person to read. The executor must control the character;
    protected and ``system`` attributes are refused, and so are the
    records the engine keeps (``characters``, ``bonus_characters``,
    ``achievements``, the ban and login dates).

    Example: set_account_attr(enactor, 'banked_gold', 50)
    """
    _character, account = _writable_account(frame, obj)
    if account is None or not _check_name(account, str(name)):
        return False
    account.db.set(str(name), value)
    frame.touch(account)
    return True


def incr_account_attr(frame, obj: GameObject | str | None, name: str, by: int = 1) -> Any:
    """
    Add ``by`` to a number on the character's account and return the new
    value (None when refused). The same rules as ``set_account_attr``.

    Example: incr_account_attr(enactor, 'kills')
    """
    _character, account = _writable_account(frame, obj)
    if account is None or not _check_name(account, str(name)):
        return None
    value = int(account.db.get(str(name)) or 0) + int(by)
    account.db.set(str(name), value)
    frame.touch(account)
    return value


def account_characters(frame, obj: GameObject | str | None) -> list[str]:
    """
    The names of every character on the character's account (empty for a
    character with none).

    Example: account_characters(enactor)
    """
    return [c.name for c in characters_of(account_of(frame.resolve(obj)))]


def character_limit(frame, obj: GameObject | str | None) -> int | None:
    """
    How many characters the character's account may hold:
    ``MAX_CHARACTERS``, plus the account's ``bonus_characters`` (set by an
    administrator), plus what its achievements grant. None for a character
    with no account.

    Example: character_limit(enactor) - len(account_characters(enactor))
    """
    from realm.core.world import get_world
    account = account_of(frame.resolve(obj))
    if account is None:
        return None
    return get_world().services["accounts"].character_limit(account)


__all__ = ["account_attr", "set_account_attr", "incr_account_attr", "account_characters",
           "character_limit"]
