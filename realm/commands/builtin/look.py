"""
Look and examine commands for REALM.

Handles viewing rooms, objects, and players.
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_object, find_exit
from realm.core.events import Event, EventType


async def cmd_look(ctx: CommandContext) -> None:
    """
    Look at the room or an object.

    Usage: look [target]
           l [target]
    """
    if not ctx.player:
        return

    if not ctx.args:
        # Look at the room
        await _show_room(ctx)
        return

    target_name = ctx.args.strip()

    # Try to find an object
    target = find_object(ctx, target_name, search_exits=True)

    if target:
        await _show_object(ctx, target)
        return

    # Try as an exit
    exit_obj = find_exit(ctx, target_name)
    if exit_obj:
        await _show_exit(ctx, exit_obj)
        return

    # Check for special targets
    if target_name.lower() in ('me', 'self'):
        await _show_object(ctx, ctx.player)
        return

    if target_name.lower() == 'here' and ctx.player.location:
        await _show_room(ctx)
        return

    await ctx.session.send(f"You don't see '{target_name}' here.")


async def cmd_examine(ctx: CommandContext) -> None:
    """
    Examine an object in detail.

    Shows more information than look, including attributes.

    Usage: examine <target>
           ex <target>
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("Examine what?")
        return

    target_name = ctx.args.strip()

    # Special cases
    if target_name.lower() in ('me', 'self'):
        target = ctx.player
    elif target_name.lower() == 'here':
        target = ctx.player.location
    else:
        target = find_object(ctx, target_name, search_exits=True)

    if not target:
        await ctx.session.send(f"You don't see '{target_name}' here.")
        return

    # Show detailed information
    await ctx.session.send(f"\n{target.name}")
    await ctx.session.send("=" * len(target.name))

    if target.description:
        await ctx.session.send(target.description)

    await ctx.session.send("")

    # Show tags
    if target.tags:
        tags_str = ", ".join(sorted(target.tags.to_list()))
        await ctx.session.send(f"Tags: {tags_str}")

    # Show ID (for builders)
    # TODO: Check if player has builder permission
    await ctx.session.send(f"ID: {target.id}")

    # Show owner
    if target.owner:
        await ctx.session.send(f"Owner: {target.owner.name}")

    # Show parent
    if target.parent:
        await ctx.session.send(f"Parent: {target.parent.name}")

    # Show location
    if target.location:
        await ctx.session.send(f"Location: {target.location.name}")

    # Show contents count
    if target.contents:
        await ctx.session.send(f"Contents: {len(target.contents)} object(s)")

    # Show behaviors
    behaviors = target.get_behaviors()
    if behaviors:
        behavior_names = [b.behavior_id for b in behaviors]
        await ctx.session.send(f"Behaviors: {', '.join(behavior_names)}")

    # Show custom attributes
    attrs = target.db.all()
    if attrs:
        await ctx.session.send("\nAttributes:")
        for key, value in sorted(attrs.items()):
            # Skip internal attributes
            if not key.startswith('_'):
                await ctx.session.send(f"  {key}: {value}")

    await ctx.session.send("")


async def _show_room(ctx: CommandContext) -> None:
    """Display the current room to the player."""
    if not ctx.player:
        return

    room = ctx.player.location
    if not room:
        await ctx.session.send("You are nowhere.")
        return

    # Emit look event
    event = Event(
        type=EventType.LOOK,
        source=ctx.player,
        target=room,
        location=room,
    )
    # TODO: Emit through event bus

    # Room name
    await ctx.session.send(f"\n{room.name}")
    await ctx.session.send("-" * len(room.name))

    # Room description
    if room.description:
        await ctx.session.send(room.description)

    # Contents (excluding self and exits)
    things = []
    players = []
    for obj in room.contents:
        if obj == ctx.player:
            continue
        if obj.has_tag('exit'):
            continue
        if obj.has_tag('player'):
            players.append(obj)
        else:
            things.append(obj)

    if things:
        await ctx.session.send("\nYou see:")
        for obj in things:
            await ctx.session.send(f"  {obj.name}")

    if players:
        await ctx.session.send("\nPlayers here:")
        for obj in players:
            status = ""
            if obj.db.get('idle', 0) > 300:  # 5 minutes
                status = " (idle)"
            await ctx.session.send(f"  {obj.name}{status}")

    # Exits
    exits = [obj for obj in room.contents if obj.has_tag('exit')]
    if exits:
        exit_names = ", ".join(e.name for e in exits)
        await ctx.session.send(f"\nExits: {exit_names}")
    else:
        await ctx.session.send("\nExits: None")

    await ctx.session.send("")


async def _show_object(ctx: CommandContext, target) -> None:
    """Display an object to the player."""
    # Emit look event
    event = Event(
        type=EventType.LOOK,
        source=ctx.player,
        target=target,
        location=ctx.player.location if ctx.player else None,
    )
    # TODO: Emit through event bus

    await ctx.session.send(f"\n{target.name}")

    if target.description:
        await ctx.session.send(target.description)
    else:
        await ctx.session.send("You see nothing special.")

    # If it's a container with visible contents
    if target.contents and not target.has_tag('player'):
        visible = [obj for obj in target.contents if not obj.has_tag('exit')]
        if visible:
            await ctx.session.send("\nContains:")
            for obj in visible:
                await ctx.session.send(f"  {obj.name}")

    await ctx.session.send("")


async def _show_exit(ctx: CommandContext, exit_obj) -> None:
    """Display an exit to the player."""
    await ctx.session.send(f"\n{exit_obj.name}")

    if exit_obj.description:
        await ctx.session.send(exit_obj.description)

    dest = exit_obj.db.get('destination_obj')
    if dest:
        await ctx.session.send(f"Leads to: {dest.name}")

    await ctx.session.send("")


def register_look_commands(dispatcher: CommandDispatcher) -> None:
    """Register look commands with the dispatcher."""

    dispatcher.register(
        "look",
        cmd_look,
        aliases=["l"],
        help_text="Look at your surroundings or an object",
        usage="look [target]",
    )

    dispatcher.register(
        "examine",
        cmd_examine,
        aliases=["ex", "exam"],
        help_text="Examine an object in detail",
        usage="examine <target>",
    )
