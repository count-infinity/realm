"""
Creation OLC commands for REALM.

Commands for creating new objects, rooms, and exits.
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_object_global, require_control, save_object
from realm.core.objects import GameObject
from realm.core.search import match_one


async def cmd_create(ctx: CommandContext) -> None:
    """
    Create a new object.

    Usage: @create <name>
           @create <name> = <parent>

    The object is created in your inventory.
    """
    if not ctx.args:
        await ctx.session.send("Usage: @create <name> [= <parent>]")
        return

    # Parse name and optional parent
    name = ctx.left_args if ctx.left_args else ctx.args
    parent_name = ctx.right_args if ctx.right_args else None

    # Find parent if specified
    parent = None
    if parent_name:
        parent = find_object_global(ctx, parent_name)
        if not parent:
            await ctx.session.send(f"Parent object '{parent_name}' not found.")
            return

    # Create the object
    obj = GameObject(
        name=name.strip(),
        location=ctx.player,  # Created in inventory
        owner=ctx.player,
        parent=parent,
        tags=['thing'],
    )

    await save_object(ctx, obj)

    await ctx.session.send(f"Created: {obj.name} (#{obj.id[:8]})")

    if parent:
        await ctx.session.send(f"  Parent: {parent.name}")


async def cmd_dig(ctx: CommandContext) -> None:
    """
    Create a new room with optional exits.

    Usage: @dig <room name>
           @dig <room name> = <exit1>, <exit2>

    Examples:
        @dig The Kitchen
        @dig The Garden = north, south
        @dig Basement = down, up

    Exit pairs are created linking the new room to your current location.
    """
    if not ctx.player or not ctx.player.location:
        return

    if not ctx.args:
        await ctx.session.send("Usage: @dig <room name> [= <exits>]")
        return

    # Parse room name and exits
    room_name = ctx.left_args if ctx.left_args else ctx.args
    exit_spec = ctx.right_args if ctx.right_args else ""

    # Create the room
    new_room = GameObject(
        name=room_name.strip(),
        owner=ctx.player,
        tags=['room'],
    )

    await save_object(ctx, new_room)

    await ctx.session.send(f"Room created: {new_room.name} (#{new_room.id[:8]})")

    # Create exits if specified
    if exit_spec:
        exits = [e.strip() for e in exit_spec.split(',')]

        # Map common exit pairs
        exit_pairs = {
            'north': 'south', 'south': 'north',
            'east': 'west', 'west': 'east',
            'up': 'down', 'down': 'up',
            'in': 'out', 'out': 'in',
            'northeast': 'southwest', 'southwest': 'northeast',
            'northwest': 'southeast', 'southeast': 'northwest',
        }

        current_room = ctx.player.location

        for exit_name in exits:
            exit_name = exit_name.lower()

            # Create exit from current room to new room
            exit_out = GameObject(
                name=exit_name,
                location=current_room,
                owner=ctx.player,
                tags=['exit'],
            )
            exit_out.db.destination = new_room.id

            await save_object(ctx, exit_out)

            await ctx.session.send(f"  Exit '{exit_name}' created -> {new_room.name}")

            # Create return exit if there's a known pair
            if exit_name in exit_pairs:
                return_name = exit_pairs[exit_name]
                exit_back = GameObject(
                    name=return_name,
                    location=new_room,
                    owner=ctx.player,
                    tags=['exit'],
                )
                exit_back.db.destination = current_room.id

                await save_object(ctx, exit_back)

                await ctx.session.send(f"  Exit '{return_name}' created -> {current_room.name}")


async def cmd_open(ctx: CommandContext) -> None:
    """
    Create an exit to an existing room.

    Usage: @open <exit name> = <destination>

    Examples:
        @open north = #abc123
        @open door = The Kitchen
    """
    if not ctx.player or not ctx.player.location:
        return

    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: @open <exit name> = <destination>")
        return

    exit_name = ctx.left_args.strip()
    dest_spec = ctx.right_args.strip()

    # Find the destination
    destination = find_object_global(ctx, dest_spec)
    if not destination:
        await ctx.session.send(f"Destination '{dest_spec}' not found.")
        return

    if not destination.has_tag('room'):
        await ctx.session.send(f"'{destination.name}' is not a room.")
        return

    # Create the exit
    exit_obj = GameObject(
        name=exit_name,
        location=ctx.player.location,
        owner=ctx.player,
        tags=['exit'],
    )
    exit_obj.db.destination = destination.id

    await save_object(ctx, exit_obj)

    await ctx.session.send(f"Exit '{exit_name}' created -> {destination.name}")


async def cmd_link(ctx: CommandContext) -> None:
    """
    Link an existing exit to a destination.

    Usage: @link <exit> = <destination>

    Use @link <exit> = here to link to your current room.
    """
    if not ctx.player or not ctx.player.location:
        return

    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: @link <exit> = <destination>")
        return

    exit_name = ctx.left_args.strip()
    dest_spec = ctx.right_args.strip()

    # Find the exit in current room
    exits = [obj for obj in ctx.player.location.contents if obj.has_tag('exit')]
    exit_obj = match_one(exit_name, exits, allow_substring=False)

    if not exit_obj:
        await ctx.session.send(f"Exit '{exit_name}' not found here.")
        return

    if not await require_control(ctx, exit_obj):
        return

    # Find destination
    if dest_spec.lower() == 'here':
        destination = ctx.player.location
    else:
        destination = find_object_global(ctx, dest_spec)

    if not destination:
        await ctx.session.send(f"Destination '{dest_spec}' not found.")
        return

    # Update the exit
    exit_obj.db.destination = destination.id

    await save_object(ctx, exit_obj)

    await ctx.session.send(f"Exit '{exit_name}' now leads to {destination.name}")


async def cmd_unlink(ctx: CommandContext) -> None:
    """
    Unlink an exit (remove its destination).

    Usage: @unlink <exit>
    """
    if not ctx.player or not ctx.player.location:
        return

    if not ctx.args:
        await ctx.session.send("Usage: @unlink <exit>")
        return

    exit_name = ctx.args.strip()

    # Find the exit
    exits = [obj for obj in ctx.player.location.contents if obj.has_tag('exit')]
    exit_obj = match_one(exit_name, exits, allow_substring=False)

    if not exit_obj:
        await ctx.session.send(f"Exit '{exit_name}' not found here.")
        return

    if not await require_control(ctx, exit_obj):
        return

    # Remove destination
    exit_obj.db.delete('destination')
    exit_obj.db.delete('destination_obj')

    await save_object(ctx, exit_obj)

    await ctx.session.send(f"Exit '{exit_name}' unlinked.")


def register_create_commands(dispatcher: CommandDispatcher) -> None:
    """Register creation OLC commands with the dispatcher."""

    dispatcher.register(
        "@create",
        cmd_create,
        help_text="Create a new object",
        usage="@create <name> [= <parent>]",
        permission="builder",
        parse_equals=True,
    )

    dispatcher.register(
        "@dig",
        cmd_dig,
        help_text="Create a new room with exits",
        usage="@dig <room name> [= <exit1>, <exit2>]",
        permission="builder",
        parse_equals=True,
    )

    dispatcher.register(
        "@open",
        cmd_open,
        help_text="Create an exit to a room",
        usage="@open <exit name> = <destination>",
        permission="builder",
        parse_equals=True,
    )

    dispatcher.register(
        "@link",
        cmd_link,
        help_text="Link an exit to a destination",
        usage="@link <exit> = <destination>",
        permission="builder",
        parse_equals=True,
    )

    dispatcher.register(
        "@unlink",
        cmd_unlink,
        help_text="Unlink an exit",
        usage="@unlink <exit>",
        permission="builder",
    )
