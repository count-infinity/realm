"""What tells and channels share: who is online, who a name is, where a
person's preferences live."""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.world import find_world

if TYPE_CHECKING:
    from realm.core.objects import GameObject


def online_players() -> list[GameObject]:
    """Every character in play, in connection order."""
    world = find_world()
    sessions = world.sessions if world is not None else None
    if sessions is None:
        return []
    return [s.player for s in sessions.all_sessions() if s.player is not None]


def is_online(player: GameObject) -> bool:
    world = find_world()
    sessions = world.sessions if world is not None else None
    return sessions is not None and sessions.get_session_by_player(player) is not None


def find_character(name: str) -> GameObject | None:
    """The character called ``name`` (any case), online or not."""
    world = find_world()
    store = world.store if world is not None else None
    found = store.find_cached(tag="player", name=name.strip()) if store is not None else []
    return found[0] if found else None


def preferences_holder(player: GameObject) -> GameObject:
    """Where a person's channel preferences live: their account when they
    have one (``db.account``), else the character."""
    world = find_world()
    account_id = player.db.get("account")
    if account_id and world is not None and world.store is not None:
        account = world.store.get_cached(str(account_id))
        if account is not None:
            return account
    return player


__all__ = ["online_players", "is_online", "find_character", "preferences_holder"]
