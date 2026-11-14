"""
Creation OLC commands for REALM.

Commands for creating new objects, rooms, and exits.
"""

from __future__ import annotations

from realm.commands import CommandContext
from realm.commands.base import find_object_global, run_op
from realm.core import ops
from realm.core.pairing import partner_of
from realm.core.search import match_one


async def cmd_create(ctx: CommandContext) -> None:
    """
    Create a new object.

    Usage: @create <name>
           @create <name> = <parent>

    The object is created in your inventory.

    Example:
        @create storm lantern
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

    result = await run_op(ctx, ops.create, name, location=ctx.player, parent=parent)
    if result is None:
        return
    obj = result.value
    await ctx.session.send(f"Created: {obj.name} (#{obj.id[:8]})")
    if parent:
        await ctx.session.send(f"  Parent: {parent.name}")


async def cmd_dig(ctx: CommandContext) -> None:
    """
    Create a new room with optional exits.

    Usage: @dig <room name>
           @dig <room name> = <exit there>[, <exit back>]

    Examples:
        @dig The Kitchen
        @dig The Garden = north          (return 'south' auto-created)
        @dig The Cellar = trapdoor, hatch

    The first exit leads to the new room; the second (or the compass
    opposite of a known direction) is created in the new room, leading
    back.
    """
    if not ctx.player or not ctx.player.location:
        return

    if not ctx.args:
        await ctx.session.send("Usage: @dig <room name> [= <exits>]")
        return

    # Parse room name and exits
    room_name = ctx.left_args if ctx.left_args else ctx.args
    exit_spec = ctx.right_args if ctx.right_args else ""

    # "@dig room = there" or "@dig room = there, back": the FIRST name leads
    # to the new room, the SECOND (or the compass opposite) leads back.
    names = [e.strip().lower() for e in exit_spec.split(',') if e.strip()]
    out_name = names[0] if names else None
    back_name = names[1] if len(names) > 1 else None
    result = await run_op(ctx, ops.dig, room_name, from_room=ctx.player.location,
                          out_name=out_name, back_name=back_name)
    if result is None:
        return
    new_room, exit_out, exit_back = result.value
    await ctx.session.send(f"Room created: {new_room.name} (#{new_room.id[:8]})")
    if exit_out is not None:
        await ctx.session.send(f"  Exit '{exit_out.name}' created -> {new_room.name}")
    if exit_back is not None:
        await ctx.session.send(
            f"  Exit '{exit_back.name}' created -> {ctx.player.location.name} "
            f"(paired with '{exit_out.name}')")


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

    result = await run_op(ctx, ops.open_exit, exit_name, location=ctx.player.location,
                          destination=destination)
    if result is None:
        return
    await ctx.session.send(f"Exit '{exit_name}' created -> {destination.name}")


async def cmd_link(ctx: CommandContext) -> None:
    """
    Link an existing exit to a destination.

    Usage: @link <exit> = <destination>

    Use @link <exit> = here to link to your current room.

    Example:
        @link trapdoor = The Cellar
    """
    if not ctx.player or not ctx.player.location:
        return

    if not ctx.left_args or not ctx.right_args:
        await ctx.session.send("Usage: @link <exit> = <destination>")
        return

    exit_name = ctx.left_args.strip()
    dest_spec = ctx.right_args.strip()

    # Find the exit in current room
    exits = [obj for obj in ctx.player.location.contents if obj.is_exit]
    exit_obj = match_one(exit_name, exits, allow_substring=False)

    if not exit_obj:
        await ctx.session.send(f"Exit '{exit_name}' not found here.")
        return

    # Find destination
    if dest_spec.lower() == 'here':
        destination = ctx.player.location
    else:
        destination = find_object_global(ctx, dest_spec)

    if not destination:
        await ctx.session.send(f"Destination '{dest_spec}' not found.")
        return

    # Retargeting dissolves any pairing on both sides, loudly.
    result = await run_op(ctx, ops.link, exit_obj, destination)
    if result is None:
        return
    if result.value is not None:
        await ctx.session.send(
            f"Pairing with '{result.value.name}' dissolved — re-pair with @pair "
            f"if you mean it.")
    await ctx.session.send(f"Exit '{exit_name}' now leads to {destination.name}")


async def cmd_unlink(ctx: CommandContext) -> None:
    """
    Unlink an exit (remove its destination).

    Usage: @unlink <exit>

    Example:
        @unlink trapdoor
    """
    if not ctx.player or not ctx.player.location:
        return

    if not ctx.args:
        await ctx.session.send("Usage: @unlink <exit>")
        return

    exit_name = ctx.args.strip()

    # Find the exit
    exits = [obj for obj in ctx.player.location.contents if obj.is_exit]
    exit_obj = match_one(exit_name, exits, allow_substring=False)

    if not exit_obj:
        await ctx.session.send(f"Exit '{exit_name}' not found here.")
        return

    result = await run_op(ctx, ops.unlink, exit_obj)
    if result is None:
        return
    if result.value is not None:
        await ctx.session.send(f"Pairing with '{result.value.name}' dissolved.")
    await ctx.session.send(f"Exit '{exit_name}' unlinked.")


async def cmd_pair(ctx: CommandContext) -> None:
    """
    Marry two exits as the faces of ONE door, so mirror scripts
    (ON_OPEN/ON_CLOSE/ON_LOCK/ON_UNLOCK writing the far side) know their
    sibling. @dig pairs its two-way exits automatically; @pair covers
    hand-built @open exits, double doors between the same rooms, and
    re-pairing after @link dissolved a marriage.

    Usage: @pair <exit>                    (show the current partner)
           @pair <exit> = <far exit>       (marry — far side by name in the
                                            destination room, or by #id)
           @pair <exit> =                  (divorce, both sides)

    Example:
        @pair vault door = vault door
    """

    if not ctx.player or not ctx.player.location:
        return
    spec = (ctx.left_args or "").strip()
    if not spec:
        await ctx.session.send("Usage: @pair <exit> [= <far exit>]")
        return

    exits = [o for o in ctx.player.location.contents if o.is_exit]
    exit_obj = match_one(spec, exits, allow_substring=False)
    if not exit_obj:
        await ctx.session.send(f"Exit '{spec}' not found here.")
        return
    try:
        ops.check_unpair(ctx.player, exit_obj)
    except ops.OpError as err:
        await ctx.session.send(err.reason)
        return

    # No '=' → show.
    if '=' not in (ctx.args or ""):
        partner = partner_of(exit_obj)
        if partner is not None:
            room = partner.location.name if partner.location else "nowhere"
            await ctx.session.send(
                f"'{exit_obj.name}' is paired with '{partner.name}' "
                f"(in {room}).")
        else:
            await ctx.session.send(f"'{exit_obj.name}' is not paired.")
        return

    far_spec = (ctx.right_args or "").strip()

    # '=' with nothing → divorce.
    if not far_spec:
        result = await run_op(ctx, ops.unpair, exit_obj)
        if result is None:
            return
        if result.value is not None:
            await ctx.session.send(
                f"Pairing between '{exit_obj.name}' and '{result.value.name}' "
                f"dissolved.")
        else:
            await ctx.session.send(f"'{exit_obj.name}' was not paired.")
        return

    # Resolve the far side: #id anywhere, or by name among the exits of
    # this exit's destination room.
    far = None
    if far_spec.startswith('#'):
        far = ctx.persistence.get_cached(far_spec[1:]) if ctx.persistence else None
    else:
        dest_id = exit_obj.db.get('destination')
        dest = ctx.persistence.get_cached(str(dest_id)) if (
            ctx.persistence and dest_id) else None
        if dest is None:
            await ctx.session.send(
                f"'{exit_obj.name}' has no destination — link it first, or "
                f"name the far side by #id.")
            return
        far_exits = [o for o in dest.contents if o.is_exit]
        far = match_one(far_spec, far_exits, allow_substring=False)
    if far is None:
        await ctx.session.send(f"Far exit '{far_spec}' not found.")
        return

    # A marriage replaces any prior ones, cleanly, on all involved sides.
    if await run_op(ctx, ops.pair, exit_obj, far) is None:
        return
    await ctx.session.send(f"Paired: '{exit_obj.name}' <-> '{far.name}'.")


