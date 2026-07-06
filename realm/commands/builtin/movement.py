"""
Movement commands for REALM.

Handles player movement through exits and the world.
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_exit
from realm.core.movement import move_through_exit, resolve_exit_destination
from realm.core.render import render_room


async def cmd_go(ctx: CommandContext) -> None:
    """
    Move through an exit.

    Usage: go <direction>
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

    dest_obj = resolve_exit_destination(exit_obj, ctx.persistence)
    if not dest_obj:
        await ctx.session.send("That exit doesn't lead anywhere.")
        return

    moved = await move_through_exit(
        ctx.player, dest_obj, exit_obj=exit_obj, direction=direction
    )
    if not moved:
        return

    # Show the new room
    await ctx.session.send(render_room(dest_obj, ctx.player))


async def cmd_direction(ctx: CommandContext) -> None:
    """
    Move in a cardinal direction.

    This is the handler for n, s, e, w, etc.
    """
    # The command name IS the direction (after alias expansion)
    direction = ctx.command_name

    # Find the exit
    exit_obj = find_exit(ctx, direction)
    if not exit_obj:
        await ctx.session.send(f"You can't go {direction}.")
        return

    # Reuse the go command logic with the direction as args
    ctx.args = direction
    await cmd_go(ctx)


def register_movement_commands(dispatcher: CommandDispatcher) -> None:
    """Register movement commands with the dispatcher."""
    from functools import partial
    register = partial(dispatcher.register, category="movement")

    register(
        "go",
        cmd_go,
        help_text="Move in a direction",
        usage="go <direction>",
    )

    # Cardinal directions
    for direction in ['north', 'south', 'east', 'west', 'up', 'down']:
        dispatcher.register(
            direction,
            cmd_direction,
            help_text=f"Go {direction}",
        )

    # Diagonal directions
    for direction in ['northeast', 'northwest', 'southeast', 'southwest']:
        dispatcher.register(
            direction,
            cmd_direction,
            help_text=f"Go {direction}",
        )

    # In/out
    register("in", cmd_direction, help_text="Go in")
    register("out", cmd_direction, help_text="Go out")
