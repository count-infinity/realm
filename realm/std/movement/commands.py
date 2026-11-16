"""
Movement commands for REALM.

Handles player movement through exits and the world.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.commands import CommandContext
from realm.commands.base import find_exit
from realm.core.movement import (
    fire_exit_fail,
    has_dest_resolver,
    move_through_exit,
    resolve_exit_destination,
)
from realm.core.search import AmbiguousMatchError, match_one
from realm.core.world import get_world

if TYPE_CHECKING:
    from realm.core.objects import GameObject


async def _show_room(ctx: CommandContext) -> None:
    """Show the room the walker arrived in, when the world has ``look``."""
    look = get_world().services.get("look")
    if look is not None:
        await ctx.session.send(look.render_room(ctx.player.location, ctx.player,
                                                    arrival=True))


async def walk(ctx: CommandContext, exit_obj: GameObject, direction: str) -> None:
    """Walk ``ctx.player`` through ``exit_obj`` and show the room beyond.
    ``go``, the direction commands and a typed exit name all end here."""
    dest_obj = resolve_exit_destination(exit_obj, ctx.persistence)
    if not dest_obj and not has_dest_resolver(exit_obj):
        # A dead-end exit fires ON_FAIL — an @afail hook may materialize the
        # room beyond it (an instance portal) and move us in.
        moved = await fire_exit_fail(
            ctx.player, exit_obj, 'no_destination', direction=direction)
        if moved:
            await _show_room(ctx)
        else:
            await ctx.session.send(
                exit_obj.db.get('fail_msg')
                or "That exit doesn't lead anywhere.")
        return

    moved = await move_through_exit(
        ctx.player, dest_obj, exit_obj=exit_obj, direction=direction
    )
    if not moved:
        return

    # Show the new room (resolved by the traversal for a deferred exit).
    await _show_room(ctx)


def exit_by_name(room: GameObject, name: str) -> GameObject | None:
    """An exit of ``room`` by exact name, alias, or unambiguous prefix
    (never a substring, so 'or' won't match 'north'). Ambiguous is None."""
    name_lower = name.lower()
    exits = [o for o in room.contents if o.is_exit]
    for obj in exits:
        if obj.name.lower() == name_lower:
            return obj
        if name_lower in [a.lower() for a in obj.db.get('aliases', [])]:
            return obj
    try:
        return match_one(name, exits, allow_substring=False)
    except AmbiguousMatchError:
        return None


async def walk_typed_exit(ctx: CommandContext) -> bool:
    """The ``movement`` feature's fallback: a line that is no command but
    names an exit walks through it. Multi-word exit names ("fire escape")
    arrive split into command and args, so the whole line is tried too."""
    if not ctx.player or not ctx.player.location:
        return False
    room = ctx.player.location
    exit_obj = (exit_by_name(room, ctx.command_name)
                or exit_by_name(room, ctx.raw_input.strip()))
    if exit_obj is None:
        return False
    await walk(ctx, exit_obj, exit_obj.name)
    return True


async def cmd_go(ctx: CommandContext) -> None:
    """
    Move through an exit.

    Usage: go <direction>

    Example:
        go north
        north                  (bare exit names work too)
    """
    if not ctx.args:
        await ctx.session.send("Go where?")
        return

    direction = ctx.args.strip()

    # Find the exit
    exit_obj = find_exit(ctx, direction)
    if not exit_obj:
        await ctx.session.send(f"You can't go {direction}.")
        return

    await walk(ctx, exit_obj, direction)


async def cmd_direction(ctx: CommandContext) -> None:
    """
    Move in a cardinal direction.

    This is the handler for n, s, e, w, etc.
    """
    # The command's own name IS the direction ('n' reaches it as 'north').
    direction = ctx.command_name

    exit_obj = find_exit(ctx, direction)
    if not exit_obj:
        await ctx.session.send(f"You can't go {direction}.")
        return
    await walk(ctx, exit_obj, direction)


