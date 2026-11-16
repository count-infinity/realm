"""
Where a player's display options are kept (MUD_PLAN 10.4).

``color``, ``pagelength``, ``prompt``, ``screenreader``, ``palette`` and any
option a game adds are attributes on the character's **account** when it has
one (the character's ``account`` attribute names it), so every character of
one person shares them; otherwise on the character itself. The ``basics``
feature's ``config`` command lists and sets them; the protocol edge, the
pager and the prompt read them through here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from realm.core.world import find_world

if TYPE_CHECKING:
    from realm.core.objects import GameObject

#: The tag an account carries (the ``accounts`` feature makes them).
ACCOUNT_TAG = "account"


def options_holder(player: GameObject) -> GameObject:
    """The object ``player``'s options live on: its account, else itself."""
    account_id = player.db.get("account")
    world = find_world()
    if account_id and world is not None:
        account = world.store.get_cached(str(account_id))
        if account is not None and account.has_tag(ACCOUNT_TAG):
            return account
    return player


def get_option(player: GameObject, name: str, default: Any = None) -> Any:
    """``player``'s option ``name``, or ``default`` when it has not set it."""
    value = options_holder(player).db.get(name)
    return default if value is None else value


def set_option(player: GameObject, name: str, value: Any) -> GameObject:
    """Set ``player``'s option; returns the object that now holds it (to save)."""
    holder = options_holder(player)
    holder.db.set(name, value)
    return holder


def clear_option(player: GameObject, name: str) -> GameObject:
    """Unset ``player``'s option (back to the game's default); returns the holder."""
    holder = options_holder(player)
    if name in holder.db:
        holder.db.delete(name)
    return holder


@dataclass(frozen=True)
class Display:
    """How one reader wants text drawn, from their ``color``,
    ``screenreader`` and ``palette`` options. Every protocol edge applies
    it the same way: ``undecorate`` the text, then either strip its color
    (``plain``) or swap colors through ``palette``."""

    undecorate: bool = False
    plain: bool = False
    palette: dict[str, str] | None = None


def display_for(player: GameObject | None) -> Display:
    """``player``'s :class:`Display`; before login (no player) the default."""
    if player is None:
        return Display()
    reader = get_option(player, "screenreader") is True
    palette = get_option(player, "palette")
    return Display(undecorate=reader,
                   plain=reader or get_option(player, "color") is False,
                   palette=palette if isinstance(palette, dict) and palette else None)


__all__ = ["ACCOUNT_TAG", "options_holder", "get_option", "set_option", "clear_option",
           "Display", "display_for"]
