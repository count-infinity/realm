"""
Admin OLC commands for REALM.

Commands for teleportation, ownership, destruction, and other admin tasks.
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_object
from realm.commands.olc.create import _find_object_global, get_persistence


async def cmd_teleport(ctx: CommandContext) -> None:
    """
    Teleport an object to a location.

    Usage: @teleport <destination>       (teleport yourself)
           @teleport <object> = <destination>

    Examples:
        @teleport The Tavern
        @teleport #abc123
        @teleport sword = me
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("Usage: @teleport [<object> =] <destination>")
        return

    # Parse arguments
    if ctx.left_args and ctx.right_args:
        target_name = ctx.left_args.strip()
        dest_name = ctx.right_args.strip()
    else:
        target_name = "me"
        dest_name = ctx.args.strip()

    # Find target
    target = _resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    # Find destination
    if dest_name.lower() in ('me', 'self'):
        destination = ctx.player
    elif dest_name.lower() == 'here':
        destination = ctx.player.location
    else:
        destination = _find_object_global(dest_name)

    if not destination:
        await ctx.session.send(f"Destination '{dest_name}' not found.")
        return

    if target == destination:
        await ctx.session.send("Can't teleport something to itself.")
        return

    old_location = target.location

    # Move the object
    target.location = destination

    persistence = get_persistence()
    if persistence:
        await persistence.save(target)

    # Notify
    if target == ctx.player:
        await ctx.session.send(f"You teleport to {destination.name}.")

        # Show the new location
        if destination.has_tag('room'):
            await _show_room(ctx, destination)
    else:
        await ctx.session.send(f"Teleported {target.name} to {destination.name}.")


async def cmd_chown(ctx: CommandContext) -> None:
    """
    Change ownership of an object.

    Usage: @chown <object> = <new owner>
    """
    if not ctx.player:
        return

    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: @chown <object> = <new owner>")
        return

    target_name = ctx.left_args.strip()
    owner_name = ctx.right_args.strip()

    # Find target
    target = _resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    # Find new owner
    new_owner = _find_object_global(owner_name)
    if not new_owner:
        await ctx.session.send(f"Owner '{owner_name}' not found.")
        return

    old_owner = target.owner
    target.owner = new_owner

    persistence = get_persistence()
    if persistence:
        await persistence.save(target)

    old_name = old_owner.name if old_owner else "nobody"
    await ctx.session.send(
        f"Ownership of {target.name} transferred from {old_name} to {new_owner.name}."
    )


async def cmd_destroy(ctx: CommandContext) -> None:
    """
    Destroy an object permanently.

    Usage: @destroy <object>

    This cannot be undone! The object and its contents are deleted.
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("Usage: @destroy <object>")
        return

    target = _resolve_target(ctx, ctx.args.strip())
    if not target:
        await ctx.session.send(f"Object '{ctx.args}' not found.")
        return

    # Safety checks
    if target == ctx.player:
        await ctx.session.send("You can't destroy yourself!")
        return

    if target.has_tag('player'):
        await ctx.session.send("Use @nuke to destroy player objects.")
        return

    if target.has_tag('safe'):
        await ctx.session.send(f"{target.name} is protected from destruction.")
        return

    # Recursively destroy contents
    destroyed_count = await _destroy_recursive(target)

    await ctx.session.send(f"Destroyed {target.name} and {destroyed_count} contained object(s).")


async def cmd_nuke(ctx: CommandContext) -> None:
    """
    Destroy a player object (admin only).

    Usage: @nuke <player>

    This disconnects the player and destroys their character.
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("Usage: @nuke <player>")
        return

    target = _find_object_global(ctx.args.strip())
    if not target:
        await ctx.session.send(f"Player '{ctx.args}' not found.")
        return

    if not target.has_tag('player'):
        await ctx.session.send(f"{target.name} is not a player. Use @destroy instead.")
        return

    if target == ctx.player:
        await ctx.session.send("You can't nuke yourself!")
        return

    # TODO: Disconnect the player's session if connected

    # Destroy
    await _destroy_recursive(target)
    await ctx.session.send(f"Player {target.name} has been nuked.")


async def cmd_find(ctx: CommandContext) -> None:
    """
    Search for objects by name or tag.

    Usage: @find <name>
           @find/tag <tag>
           @find/owner <owner>
    """
    persistence = get_persistence()
    if not ctx.player or not persistence:
        return

    if not ctx.args:
        await ctx.session.send("Usage: @find[/tag|/owner] <search>")
        return

    search = ctx.args.strip().lower()
    results = []

    if 'tag' in ctx.switches:
        # Search by tag
        for obj in persistence._object_cache.values():
            if obj.has_tag(search):
                results.append(obj)
    elif 'owner' in ctx.switches:
        # Search by owner name
        for obj in persistence._object_cache.values():
            if obj.owner and obj.owner.name.lower() == search:
                results.append(obj)
    else:
        # Search by name
        for obj in persistence._object_cache.values():
            if search in obj.name.lower():
                results.append(obj)

    if not results:
        await ctx.session.send("No objects found.")
        return

    await ctx.session.send(f"\nFound {len(results)} object(s):")
    for obj in results[:20]:  # Limit display
        loc = obj.location.name if obj.location else "nowhere"
        tags = ", ".join(obj.tags.to_list()[:3])
        await ctx.session.send(f"  {obj.name} (#{obj.id[:8]}) - {loc} [{tags}]")

    if len(results) > 20:
        await ctx.session.send(f"  ... and {len(results) - 20} more")

    await ctx.session.send("")


async def cmd_examine_full(ctx: CommandContext) -> None:
    """
    Show detailed technical information about an object.

    Usage: @examine <object>
           @ex <object>
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("Usage: @examine <object>")
        return

    target = _resolve_target(ctx, ctx.args.strip())
    if not target:
        await ctx.session.send(f"Object '{ctx.args}' not found.")
        return

    await ctx.session.send(f"\n{'=' * 50}")
    await ctx.session.send(f"Name: {target.name}")
    await ctx.session.send(f"ID: {target.id}")
    await ctx.session.send(f"{'=' * 50}")

    # Description
    if target.description:
        await ctx.session.send(f"\nDescription:\n{target.description}")

    # Location info
    await ctx.session.send(f"\nLocation: {target.location.name if target.location else 'None'}")
    await ctx.session.send(f"Owner: {target.owner.name if target.owner else 'None'}")
    await ctx.session.send(f"Parent: {target.parent.name if target.parent else 'None'}")

    # Tags
    if target.tags:
        await ctx.session.send(f"\nTags: {', '.join(sorted(target.tags.to_list()))}")

    # Locks
    if target.locks:
        await ctx.session.send("\nLocks:")
        for lock_type, expr in target.locks.items():
            await ctx.session.send(f"  {lock_type}: {expr}")

    # Attributes
    attrs = target.db.all()
    if attrs:
        await ctx.session.send("\nAttributes:")
        for key, value in sorted(attrs.items()):
            await ctx.session.send(f"  {key}: {value!r}")

    # Behaviors
    behaviors = target.get_behaviors()
    if behaviors:
        await ctx.session.send("\nBehaviors:")
        for b in behaviors:
            await ctx.session.send(f"  {b.behavior_id}: {b.params}")

    # Contents
    if target.contents:
        await ctx.session.send(f"\nContents ({len(target.contents)}):")
        for obj in target.contents[:10]:
            await ctx.session.send(f"  {obj.name} (#{obj.id[:8]})")
        if len(target.contents) > 10:
            await ctx.session.send(f"  ... and {len(target.contents) - 10} more")

    await ctx.session.send("")


async def cmd_force(ctx: CommandContext) -> None:
    """
    Force an object to execute a command.

    Usage: @force <object> = <command>
    """
    if not ctx.player:
        return

    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: @force <object> = <command>")
        return

    target = _resolve_target(ctx, ctx.left_args.strip())
    if not target:
        await ctx.session.send(f"Object '{ctx.left_args}' not found.")
        return

    command = ctx.right_args

    # TODO: Execute command as target
    # This requires creating a fake session/context for the target
    await ctx.session.send(f"@force not fully implemented. Would force {target.name} to: {command}")


async def cmd_boot(ctx: CommandContext) -> None:
    """
    Disconnect a player.

    Usage: @boot <player>
    """
    if not ctx.player:
        return

    if not ctx.args:
        await ctx.session.send("Usage: @boot <player>")
        return

    # TODO: Find player's session and disconnect
    await ctx.session.send(f"@boot not fully implemented.")


async def _show_room(ctx: CommandContext, room) -> None:
    """Show a room to the player."""
    await ctx.session.send(f"\n{room.name}")
    await ctx.session.send("-" * len(room.name))

    if room.description:
        await ctx.session.send(room.description)

    # Show contents
    others = [obj for obj in room.contents if obj != ctx.player and not obj.has_tag('exit')]
    if others:
        await ctx.session.send("\nYou see:")
        for obj in others:
            await ctx.session.send(f"  {obj.name}")

    # Show exits
    exits = [obj for obj in room.contents if obj.has_tag('exit')]
    if exits:
        exit_names = ", ".join(e.name for e in exits)
        await ctx.session.send(f"\nExits: {exit_names}")

    await ctx.session.send("")


async def _destroy_recursive(obj) -> int:
    """Destroy an object and all its contents. Returns count of destroyed objects."""
    count = 0

    # First destroy contents
    for child in list(obj.contents):
        count += await _destroy_recursive(child)
        count += 1

    # Remove from location
    if obj.location:
        obj.location = None

    # Delete from persistence
    persistence = get_persistence()
    if persistence:
        await persistence.delete(obj)

    return count


def _resolve_target(ctx: CommandContext, name: str):
    """Resolve a target by name, with special handling for 'me' and 'here'."""
    name_lower = name.lower()

    if name_lower in ('me', 'self'):
        return ctx.player
    if name_lower == 'here':
        return ctx.player.location if ctx.player else None

    # Try local first
    target = find_object(ctx, name, search_exits=True)
    if target:
        return target

    # Try global lookup
    return _find_object_global(name)


def register_admin_commands(dispatcher: CommandDispatcher) -> None:
    """Register admin OLC commands with the dispatcher."""

    dispatcher.register(
        "@teleport",
        cmd_teleport,
        aliases=["@tel"],
        help_text="Teleport to a location",
        usage="@teleport [<object> =] <destination>",
        permission="builder",
        parse_equals=True,
    )

    dispatcher.register(
        "@chown",
        cmd_chown,
        help_text="Change ownership of an object",
        usage="@chown <object> = <new owner>",
        permission="admin",
        parse_equals=True,
    )

    dispatcher.register(
        "@destroy",
        cmd_destroy,
        aliases=["@recycle"],
        help_text="Destroy an object",
        usage="@destroy <object>",
        permission="builder",
    )

    dispatcher.register(
        "@nuke",
        cmd_nuke,
        help_text="Destroy a player object",
        usage="@nuke <player>",
        permission="admin",
    )

    dispatcher.register(
        "@find",
        cmd_find,
        aliases=["@search"],
        help_text="Search for objects",
        usage="@find[/tag|/owner] <search>",
        permission="builder",
    )

    dispatcher.register(
        "@examine",
        cmd_examine_full,
        aliases=["@ex"],
        help_text="Show detailed object information",
        usage="@examine <object>",
        permission="builder",
    )

    dispatcher.register(
        "@force",
        cmd_force,
        help_text="Force an object to execute a command",
        usage="@force <object> = <command>",
        permission="admin",
        parse_equals=True,
    )

    dispatcher.register(
        "@boot",
        cmd_boot,
        help_text="Disconnect a player",
        usage="@boot <player>",
        permission="admin",
    )
