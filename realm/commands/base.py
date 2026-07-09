"""
Base utilities for command implementation.

Provides helper functions for common command patterns. All name
resolution goes through realm.core.search — one matcher, so "prom"
finds "Station Promenade" everywhere a player can name something.
Helpers return None for no match and raise AmbiguousMatchError when several
objects match equally well (the dispatcher renders the choice list).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.search import match_objects, match_one

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject


def exit_named(room: GameObject, name: str) -> GameObject | None:
    """An existing exit in a room by exact (case-insensitive) name."""
    lower = name.strip().lower()
    for obj in room.contents:
        if obj.has_tag('exit') and obj.name.lower() == lower:
            return obj
    return None


async def require_control(ctx: CommandContext, target: GameObject) -> bool:
    """
    Gate for mutating builder commands: caller must control the target
    (see permissions.locks.controls). Sends the refusal itself; callers
    just ``if not await require_control(ctx, target): return``.
    """
    from realm.permissions.locks import controls

    if controls(ctx.player, target):
        return True
    await ctx.session.send(f"You don't control {target.name}.")
    return False


async def save_object(ctx: CommandContext, obj: GameObject) -> None:
    """Persist a modified object, if the server has persistence wired."""
    if ctx.persistence:
        await ctx.persistence.save(obj)


def find_object_global(ctx: CommandContext, spec: str) -> GameObject | None:
    """
    Find an object anywhere in the world by ID or name.

    Accepts ``#id``, a bare UUID, or a (partial) name. Requires
    persistence; returns None when the server runs without it. Raises
    AmbiguousMatchError when a name matches several objects equally well.
    """
    persistence = ctx.persistence
    if not persistence:
        return None

    spec = spec.strip()

    # ID reference (#abc123 or bare UUID)
    if spec.startswith('#'):
        return persistence.get_cached(spec[1:])
    if '-' in spec and len(spec) > 30:
        return persistence.get_cached(spec)

    return match_one(spec, persistence.all_cached())


def resolve_target(ctx: CommandContext, name: str) -> GameObject | None:
    """
    Resolve a builder-command target: 'me'/'self', 'here', then local
    objects (including exits), then a global ID/name lookup.
    """
    name_lower = name.lower()

    if name_lower in ('me', 'self'):
        return ctx.player
    if name_lower == 'here':
        return ctx.player.location if ctx.player else None

    target = find_object(ctx, name, search_exits=True)
    if target:
        return target

    return find_object_global(ctx, name)


def local_candidates(
    ctx: CommandContext,
    *,
    search_room: bool = True,
    search_inventory: bool = True,
    search_exits: bool = False,
) -> list[GameObject]:
    """
    Objects a player can plausibly mean by name: inventory first, then
    room contents (excluding self, and exits unless requested).

    Perception applies: things the player can't see (invisible, or in an
    unlit dark room) can't be targeted. Exits are exempt — a secret door
    stays traversable by name for those who know it's there.
    """
    from realm.core.perception import can_see

    if not ctx.player:
        return []

    candidates: list[GameObject] = []
    if search_inventory:
        candidates.extend(ctx.player.contents)
    if search_room and ctx.player.location:
        for obj in ctx.player.location.contents:
            if obj == ctx.player:
                continue
            if obj.has_tag('exit'):
                if search_exits:
                    candidates.append(obj)
                continue
            if can_see(ctx.player, obj):
                candidates.append(obj)
    return candidates


def find_object(
    ctx: CommandContext,
    name: str,
    *,
    search_room: bool = True,
    search_inventory: bool = True,
    search_exits: bool = False,
) -> GameObject | None:
    """
    Find one object by (partial) name from the player's perspective.

    Candidates: inventory, then room contents, then exits if requested.
    Returns None for no match; raises AmbiguousMatchError when several match
    equally well (pick with ``name-2`` style suffixes).
    """
    return match_one(
        name,
        local_candidates(
            ctx,
            search_room=search_room,
            search_inventory=search_inventory,
            search_exits=search_exits,
        ),
    )


def find_objects(
    ctx: CommandContext,
    name: str,
    *,
    search_room: bool = True,
    search_inventory: bool = True,
) -> list[GameObject]:
    """
    Find all objects matching a (partial) name — the best-matching tier.
    """
    return match_objects(
        name,
        local_candidates(
            ctx,
            search_room=search_room,
            search_inventory=search_inventory,
        ),
    ).matches


def find_player(ctx: CommandContext, name: str) -> GameObject | None:
    """
    Find a player by (partial) name in the current room — a player you
    can see (whisper can't target someone hiding invisible).
    """
    from realm.core.perception import can_see

    if not ctx.player or not ctx.player.location:
        return None

    players = [
        obj for obj in ctx.player.location.contents
        if obj.has_tag('player') and can_see(ctx.player, obj)
    ]
    return match_one(name, players)


def find_exit(ctx: CommandContext, direction: str) -> GameObject | None:
    """
    Find an exit by name, alias, or unambiguous prefix.

    No substring tier — 'or' should not match 'north'.
    """
    if not ctx.player or not ctx.player.location:
        return None

    exits = [
        obj for obj in ctx.player.location.contents if obj.has_tag('exit')
    ]
    return match_one(direction, exits, allow_substring=False)


def format_list(items: list[str], conjunction: str = "and") -> str:
    """
    Format a list of items for display.

    Examples:
        [] -> ""
        ["apple"] -> "apple"
        ["apple", "banana"] -> "apple and banana"
        ["apple", "banana", "cherry"] -> "apple, banana, and cherry"
    """
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conjunction} {items[1]}"
    return f"{', '.join(items[:-1])}, {conjunction} {items[-1]}"
