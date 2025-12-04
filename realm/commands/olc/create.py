"""
Creation OLC commands for REALM.

Commands for creating new objects, rooms, and exits.
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher
from realm.core.objects import GameObject


# Reference to persistence manager (set by GameServer)
_persistence = None


def set_persistence(manager) -> None:
    """Set the persistence manager for OLC commands."""
    global _persistence
    _persistence = manager


def get_persistence():
    """Get the persistence manager for OLC commands."""
    return _persistence


async def cmd_create(ctx: CommandContext) -> None:
    """
    Create a new object.

    Usage: @create <name>
           @create <name> = <parent>

    The object is created in your inventory.
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("Usage: @create <name> [= <parent>]")
        return

    # Parse name and optional parent
    name = ctx.left_args if ctx.left_args else ctx.args
    parent_name = ctx.right_args if ctx.right_args else None

    # Find parent if specified
    parent = None
    if parent_name:
        parent = _find_object_global(parent_name)
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

    # Save to persistence
    if _persistence:
        await _persistence.save(obj)

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

    if _persistence:
        await _persistence.save(new_room)

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
            exit_out.db.destination_obj = new_room

            if _persistence:
                await _persistence.save(exit_out)

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
                exit_back.db.destination_obj = current_room

                if _persistence:
                    await _persistence.save(exit_back)

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
    destination = _find_object_global(dest_spec)
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
    exit_obj.db.destination_obj = destination

    if _persistence:
        await _persistence.save(exit_obj)

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
    exit_obj = None
    for obj in ctx.player.location.contents:
        if obj.has_tag('exit') and obj.name.lower() == exit_name.lower():
            exit_obj = obj
            break

    if not exit_obj:
        await ctx.session.send(f"Exit '{exit_name}' not found here.")
        return

    # Find destination
    if dest_spec.lower() == 'here':
        destination = ctx.player.location
    else:
        destination = _find_object_global(dest_spec)

    if not destination:
        await ctx.session.send(f"Destination '{dest_spec}' not found.")
        return

    # Update the exit
    exit_obj.db.destination = destination.id
    exit_obj.db.destination_obj = destination

    if _persistence:
        await _persistence.save(exit_obj)

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
    exit_obj = None
    for obj in ctx.player.location.contents:
        if obj.has_tag('exit') and obj.name.lower() == exit_name.lower():
            exit_obj = obj
            break

    if not exit_obj:
        await ctx.session.send(f"Exit '{exit_name}' not found here.")
        return

    # Remove destination
    exit_obj.db.delete('destination')
    exit_obj.db.delete('destination_obj')

    if _persistence:
        await _persistence.save(exit_obj)

    await ctx.session.send(f"Exit '{exit_name}' unlinked.")


def _find_object_global(spec: str) -> GameObject | None:
    """
    Find an object by ID or name.

    Checks:
    1. By ID (if starts with # or looks like UUID)
    2. By name in persistence cache
    """
    if not _persistence:
        return None

    spec = spec.strip()

    # Check if it's an ID reference
    if spec.startswith('#'):
        obj_id = spec[1:]
        return _persistence._object_cache.get(obj_id)

    # Check if it looks like a UUID
    if '-' in spec and len(spec) > 30:
        return _persistence._object_cache.get(spec)

    # Search by name in cache
    spec_lower = spec.lower()
    for obj in _persistence._object_cache.values():
        if obj.name.lower() == spec_lower:
            return obj

    return None


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
