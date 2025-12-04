"""
Movement commands for REALM.

Handles player movement through exits and the world.
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_exit
from realm.core.events import Event, EventType


async def cmd_go(ctx: CommandContext) -> None:
    """
    Move through an exit.

    Usage: go <direction>
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("Go where?")
        return

    direction = ctx.args.strip()

    # Find the exit
    exit_obj = find_exit(ctx, direction)
    if not exit_obj:
        await ctx.session.send(f"You can't go {direction}.")
        return

    # Get destination
    destination = exit_obj.db.get('destination')
    if not destination:
        await ctx.session.send("That exit doesn't lead anywhere.")
        return

    # Get the destination object from cache/persistence
    # For now, we need to have a reference to the actual GameObject
    # This would normally come from the persistence layer
    dest_obj = exit_obj.db.get('destination_obj')
    if not dest_obj:
        await ctx.session.send("That exit doesn't lead anywhere.")
        return

    old_location = ctx.player.location

    # Emit leave event (can be cancelled)
    if old_location:
        leave_event = Event(
            type=EventType.LEAVE,
            source=ctx.player,
            location=old_location,
            data={'exit': exit_obj, 'destination': dest_obj},
            source_msg=f"You leave {direction}.",
            others_msg=f"{ctx.player.name} leaves {direction}.",
        )

        # TODO: Emit through event bus
        # For now, just send messages
        await ctx.session.send(leave_event.source_msg)

        # Notify others in old room
        for obj in old_location.contents:
            if obj != ctx.player and obj.has_tag('player'):
                obj.msg(leave_event.others_msg)

    # Move the player
    ctx.player.location = dest_obj

    # Emit enter event
    enter_event = Event(
        type=EventType.ENTER,
        source=ctx.player,
        location=dest_obj,
        data={'from': old_location, 'exit': exit_obj},
        others_msg=f"{ctx.player.name} arrives.",
    )

    # Notify others in new room
    for obj in dest_obj.contents:
        if obj != ctx.player and obj.has_tag('player'):
            obj.msg(enter_event.others_msg)

    # Show the new room
    await _show_room(ctx, dest_obj)


async def cmd_direction(ctx: CommandContext) -> None:
    """
    Move in a cardinal direction.

    This is the handler for n, s, e, w, etc.
    """
    if not ctx.player:
        return

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


async def _show_room(ctx: CommandContext, room) -> None:
    """Show a room to the player."""
    await ctx.session.send(f"\n{room.name}")
    await ctx.session.send("-" * len(room.name))

    if room.description:
        await ctx.session.send(room.description)

    # Show contents (excluding self and exits)
    others = [
        obj for obj in room.contents
        if obj != ctx.player and not obj.has_tag('exit')
    ]
    if others:
        await ctx.session.send("\nYou see:")
        for obj in others:
            if obj.has_tag('player'):
                await ctx.session.send(f"  {obj.name} is here.")
            else:
                await ctx.session.send(f"  {obj.name}")

    # Show exits
    exits = [obj for obj in room.contents if obj.has_tag('exit')]
    if exits:
        exit_names = ", ".join(e.name for e in exits)
        await ctx.session.send(f"\nExits: {exit_names}")

    await ctx.session.send("")


def register_movement_commands(dispatcher: CommandDispatcher) -> None:
    """Register movement commands with the dispatcher."""

    dispatcher.register(
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
    dispatcher.register("in", cmd_direction, help_text="Go in")
    dispatcher.register("out", cmd_direction, help_text="Go out")
