"""
Admin OLC commands for REALM.

Commands for teleportation, ownership, destruction, and other admin tasks.
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_object_global, require_control, resolve_target, save_object
from realm.core.render import render_room


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
    target = resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    # Find destination
    if dest_name.lower() in ('me', 'self'):
        destination = ctx.player
    elif dest_name.lower() == 'here':
        destination = ctx.player.location
    else:
        destination = find_object_global(ctx, dest_name)

    if not destination:
        await ctx.session.send(f"Destination '{dest_name}' not found.")
        return

    if target == destination:
        await ctx.session.send("Can't teleport something to itself.")
        return

    # Moving something other than yourself is control-level power.
    if target is not ctx.player and not await require_control(ctx, target):
        return

    # Move the object
    target.location = destination

    await save_object(ctx, target)

    # Notify
    if target == ctx.player:
        await ctx.session.send(f"You teleport to {destination.name}.")

        # Show the new location
        if destination.has_tag('room'):
            await ctx.session.send(render_room(destination, ctx.player))
    else:
        await ctx.session.send(f"Teleported {target.name} to {destination.name}.")


async def cmd_chown(ctx: CommandContext) -> None:
    """
    Change ownership of an object.

    Usage: @chown <object> = <new owner>
    """
    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: @chown <object> = <new owner>")
        return

    target_name = ctx.left_args.strip()
    owner_name = ctx.right_args.strip()

    # Find target
    target = resolve_target(ctx, target_name)
    if not target:
        await ctx.session.send(f"Object '{target_name}' not found.")
        return

    # Find new owner
    new_owner = find_object_global(ctx, owner_name)
    if not new_owner:
        await ctx.session.send(f"Owner '{owner_name}' not found.")
        return

    old_owner = target.owner
    target.owner = new_owner

    await save_object(ctx, target)

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
    if not ctx.args:
        await ctx.session.send("Usage: @destroy <object>")
        return

    target = resolve_target(ctx, ctx.args.strip())
    if not target:
        await ctx.session.send(f"Object '{ctx.args}' not found.")
        return

    if not await require_control(ctx, target):
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
    destroyed_count = await _destroy_recursive(ctx, target)

    await ctx.session.send(f"Destroyed {target.name} and {destroyed_count} contained object(s).")


async def cmd_nuke(ctx: CommandContext) -> None:
    """
    Destroy a player object (admin only).

    Usage: @nuke <player>

    This disconnects the player and destroys their character.
    """
    if not ctx.args:
        await ctx.session.send("Usage: @nuke <player>")
        return

    target = find_object_global(ctx, ctx.args.strip())
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
    await _destroy_recursive(ctx, target)
    await ctx.session.send(f"Player {target.name} has been nuked.")


async def cmd_find(ctx: CommandContext) -> None:
    """
    Search for objects by name or tag.

    Usage: @find <name>
           @find/tag <tag>
           @find/owner <owner>
    """
    if not ctx.player or not ctx.persistence:
        return

    if not ctx.args:
        await ctx.session.send("Usage: @find[/tag|/owner] <search>")
        return

    search = ctx.args.strip().lower()
    results = []

    if 'tag' in ctx.switches:
        # Search by tag
        results = ctx.persistence.find_cached(tag=search)
    elif 'owner' in ctx.switches:
        # Search by owner name
        for obj in ctx.persistence.all_cached():
            if obj.owner and obj.owner.name.lower() == search:
                results.append(obj)
    else:
        # Substring search by name
        for obj in ctx.persistence.all_cached():
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
    if not ctx.args:
        await ctx.session.send("Usage: @examine <object>")
        return

    target = resolve_target(ctx, ctx.args.strip())
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
    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: @force <object> = <command>")
        return

    target = resolve_target(ctx, ctx.left_args.strip())
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
    if not ctx.args:
        await ctx.session.send("Usage: @boot <player>")
        return

    # TODO: Find player's session and disconnect
    await ctx.session.send("@boot not fully implemented.")


async def _destroy_recursive(ctx: CommandContext, obj) -> int:
    """Destroy an object and all its contents. Returns count of destroyed objects."""
    count = 0

    # First destroy contents
    for child in list(obj.contents):
        count += await _destroy_recursive(ctx, child)
        count += 1

    # Remove from location
    if obj.location:
        obj.location = None

    # Delete from persistence
    if ctx.persistence:
        await ctx.persistence.delete(obj)

    return count


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
