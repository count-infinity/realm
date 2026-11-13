"""
Admin OLC commands for REALM.

Commands for teleportation, ownership, destruction, and other admin tasks.
"""

from __future__ import annotations

from realm.commands import CommandContext
from realm.commands.base import (
    find_object_global,
    resolve_target,
    run_op,
)
from realm.core import ops
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

    # Moving something other than yourself needs relocation authority (you
    # control it, or own the room it stands in). The move is forced: it
    # skips on_check wards but honors the destination's ENTER/TELEPORT locks
    # (admins bypass locks as always) and fires the informational on_enter.
    result = await run_op(ctx, ops.relocate, target, destination, force=True)
    if result is None:
        return
    if not result.value:
        await ctx.session.send(
            f"Teleport failed — {destination.name} won't admit "
            f"{'you' if target is ctx.player else target.name}."
        )
        return

    if target == ctx.player:
        await ctx.session.send(f"You teleport to {destination.name}.")
        if destination.is_room:
            await ctx.session.send(render_room(destination, ctx.player))
    else:
        await ctx.session.send(f"Teleported {target.name} to {destination.name}.")


async def cmd_chown(ctx: CommandContext) -> None:
    """
    Change ownership of an object.

    Usage: @chown <object> = <new owner>

    Example:
        @chown music box = Ada
        (scripted objects are HALTED on transfer; review, then @untag <obj> = halt)
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

    result = await run_op(ctx, ops.chown, target, new_owner)
    if result is None:
        return
    old_name = result.value.name if result.value else "nobody"
    await ctx.session.send(
        f"Ownership of {target.name} transferred from {old_name} to {new_owner.name}."
    )


async def cmd_destroy(ctx: CommandContext) -> None:
    """
    Destroy an object permanently.

    Usage: @destroy <object>

    This cannot be undone! Players inside are sent home (else to the start
    room), player-owned items go to their owner's home, and everything else
    inside is destroyed with it. Players and `safe` objects are refused.

    Example:
        @destroy rusty key
    """
    if not ctx.args:
        await ctx.session.send("Usage: @destroy <object>")
        return

    target = resolve_target(ctx, ctx.args.strip())
    if not target:
        await ctx.session.send(f"Object '{ctx.args}' not found.")
        return

    try:
        destroyed_count = await ops.destroy(ctx.player, target, ctx.persistence)
    except ops.OpError as refused:
        await ctx.session.send(refused.reason)
        return

    await ctx.session.send(f"Destroyed {target.name} and {destroyed_count} contained object(s).")


async def cmd_nuke(ctx: CommandContext) -> None:
    """
    Destroy a player object (admin only).

    Usage: @nuke <player>

    This disconnects the player and destroys their character.

    Example:
        @nuke Vandal
    """
    if not ctx.args:
        await ctx.session.send("Usage: @nuke <player>")
        return

    target = find_object_global(ctx, ctx.args.strip())
    if not target:
        await ctx.session.send(f"Player '{ctx.args}' not found.")
        return

    if not target.is_player:
        await ctx.session.send(f"{target.name} is not a player. Use @destroy instead.")
        return

    if target == ctx.player:
        await ctx.session.send("You can't nuke yourself!")
        return

    try:
        ops.check_destroy(ctx.player, target, allow_player=True)
    except ops.OpError as refused:
        await ctx.session.send(refused.reason)
        return

    # Hang up the player's live session first, if connected, so their client
    # isn't left driving a destroyed character.
    sm = ctx.session_manager
    session = sm.get_session_by_player(target) if sm else None
    if session is not None:
        await session.send("Your character has been removed from the world.")
        await sm.destroy_session(session)

    await ops.destroy(ctx.player, target, ctx.persistence, allow_player=True,
                      contents="destroy")
    await ctx.session.send(f"Player {target.name} has been nuked.")


async def cmd_find(ctx: CommandContext) -> None:
    """
    Search for objects by name or tag.

    Usage: @find <name>
           @find/tag <tag>
           @find/attr <attribute>[=<value>]
           @find/owner <owner>

    Example:
        @find lighthouse
        @find/tag zone:castle
        @find/attr value=50
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
    elif 'attr' in ctx.switches:
        from realm.core.query import _UNSET, find_objects
        attr, _, raw = ctx.args.strip().partition('=')
        wanted = _UNSET
        if raw:
            from realm.commands.olc.modify import _parse_value
            wanted = _parse_value(raw.strip())
        results = find_objects(attr=attr.strip(), value=wanted, limit=100)
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

    Example:
        @examine merchant
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

    # Attributes — own first, then anything inherited through @parent
    # (invisible inheritance is a debugging nightmare; show it, marked).
    attrs = target.db.all()
    if attrs:
        await ctx.session.send("\nAttributes:")
        for key, value in sorted(attrs.items()):
            await ctx.session.send(f"  {key}: {value!r}")
    if target.parent is not None:
        inherited = {k: v for k, v in target.db.merged().items()
                     if k not in attrs}
        if inherited:
            await ctx.session.send(
                f"\nInherited (from {target.parent.name}):")
            for key, value in sorted(inherited.items()):
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


async def cmd_boot(ctx: CommandContext) -> None:
    """
    Disconnect a player's session (they keep their character).

    Usage: @boot <player>

    Example:
        @boot Vandal
    """
    if not ctx.args:
        await ctx.session.send("Usage: @boot <player>")
        return

    target = find_object_global(ctx, ctx.args.strip())
    if not target or not target.is_player:
        await ctx.session.send(f"Player '{ctx.args.strip()}' not found.")
        return
    if await run_op(ctx, ops.boot, target, ctx.session_manager) is None:
        return
    await ctx.session.send(f"Booted {target.name}.")


