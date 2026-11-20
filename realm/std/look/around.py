"""
Looking beyond the room (MUD_PLAN 11.4): ``scan``, ``exits`` and ``where``.

``scan`` lists who is one room away through each open exit, ``exits`` where
each exit leads, ``where`` the players in the same zone (``where <name>``:
who of that name is in it, ROM's). All three respect
sight: a dark room shows no one (and ``exits`` says it is too dark to
tell), a closed door hides what is behind it, and anyone the viewer cannot
see is left out. A world ``$``-command of the same word comes first, as it
does for every built-in that a build may already use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.movement import resolve_exit_destination
from realm.core.perception import can_see
from realm.core.world import get_world
from realm.core.zones import zone_tags
from realm.gateway.session import online_players
from realm.std.look.render import can_see_room, out_of_play

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject


async def _world_verb(ctx: CommandContext) -> bool:
    """A world ``$``-command of the same word takes the line first
    (showcase 193 builds a ``$scan``)."""
    engine = get_world().scripts
    return engine is not None and await engine.handle_unknown_command(ctx)


def _exits(viewer: GameObject) -> list[GameObject]:
    room = viewer.location
    if room is None:
        return []
    return [o for o in room.contents if o.is_exit and can_see(viewer, o)]


def _who_is_in(viewer: GameObject, room: GameObject) -> list[GameObject]:
    """The characters ``viewer`` can make out in ``room``."""
    if not can_see_room(viewer, room):
        return []
    return [o for o in room.contents
            if (o.is_npc or (o.is_player and not out_of_play(o)))
            and o is not viewer and can_see(viewer, o)]


async def cmd_scan(ctx: CommandContext) -> None:
    """
    See who is one room away, through each open exit.

    Usage: scan
    """
    if await _world_verb(ctx):
        return
    viewer = ctx.player
    lines = []
    for exit_obj in _exits(viewer):
        if exit_obj.has_tag('closed'):
            continue
        beyond = resolve_exit_destination(exit_obj)
        if beyond is None or beyond is viewer.location:
            continue
        there = _who_is_in(viewer, beyond)
        if there:
            names = ", ".join(o.get_display_name(viewer) for o in there)
            lines.append(f"  {exit_obj.name} ({beyond.name}): {names}")
    if not lines:
        await ctx.session.send("You see no one nearby.")
        return
    await ctx.session.send("\n".join(["Looking around you see:", *lines]))


async def cmd_exits(ctx: CommandContext) -> None:
    """
    List the exits here and where each one leads.

    Usage: exits
    """
    if await _world_verb(ctx):
        return
    viewer = ctx.player
    exits = _exits(viewer)
    if not exits:
        await ctx.session.send("Obvious exits:\n  None.")
        return
    width = max(len(e.name) for e in exits)
    lines = ["Obvious exits:"]
    for exit_obj in exits:
        if exit_obj.has_tag('closed'):
            where = "(closed)"
        else:
            beyond = resolve_exit_destination(exit_obj)
            if beyond is None:
                where = "somewhere"
            elif not can_see_room(viewer, beyond):
                where = "Too dark to tell"
            else:
                where = beyond.name
        lines.append(f"  {exit_obj.name:{width}} - {where}")
    await ctx.session.send("\n".join(lines))


def _same_zone(here: GameObject | None, there: GameObject | None) -> bool:
    """Whether two rooms are in one zone. Rooms in no zone count as one
    zone of their own, so a world without zones lists everyone."""
    if here is None or there is None:
        return False
    mine, theirs = set(zone_tags(here)), set(zone_tags(there))
    return bool(mine & theirs) if mine or theirs else True


async def cmd_where(ctx: CommandContext) -> None:
    """
    List the players in this zone and the room each is in; with a name, who
    and what of that name is in this zone, and where (ROM's ``where <name>``).

    Usage: where
           where <name>

    Example:
        where fido
    """
    if await _world_verb(ctx):
        return
    viewer = ctx.player
    wanted = (ctx.args or "").strip()
    if wanted:
        await _where_named(ctx, viewer, wanted)
        return
    near = [p for p in online_players()
            if can_see(viewer, p) and _same_zone(viewer.location, p.location)]
    if not near:
        await ctx.session.send("Players near you:\n  None.")
        return
    width = max(len(p.get_display_name(viewer)) for p in near) + 2
    lines = ["Players near you:"]
    for player in near:
        lines.append(f"  {player.get_display_name(viewer):{width}}{player.location.name}")
    await ctx.session.send("\n".join(lines))


async def _where_named(ctx: CommandContext, viewer: GameObject, wanted: str) -> None:
    """``where <name>``: the characters of that name in the viewer's zone
    whom the viewer could see (at most ``_WHERE_MAX``)."""
    from realm.core.search import match_objects
    store = get_world().store
    candidates = [o for o in (*store.find_cached(tag='npc'), *online_players())
                  if o is not viewer and o.location is not None
                  and _same_zone(viewer.location, o.location)
                  and can_see_room(viewer, o.location) and can_see(viewer, o)]
    found = match_objects(wanted, candidates, allow_substring=False).matches[:_WHERE_MAX]
    if not found:
        await ctx.session.send(f"You didn't find any {wanted}.")
        return
    width = max(len(o.get_display_name(viewer)) for o in found) + 2
    await ctx.session.send("\n".join(
        f"{o.get_display_name(viewer):{width}}{o.location.name}" for o in found))


#: The most ``where <name>`` lists.
_WHERE_MAX = 10


__all__ = ["cmd_scan", "cmd_exits", "cmd_where"]
