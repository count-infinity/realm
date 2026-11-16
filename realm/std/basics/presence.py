"""
Who is on (MUD_PLAN step 9, capability audit G4).

The characters in play are the session manager's (``online_players``,
``is_online`` in realm.gateway.session; a link-dead character is not in
play: it has no connection). ``who`` lists them
with their idle time and the link-dead characters waiting in their rooms,
leaving out anyone the viewer cannot see. Beside each name it shows what
the ``who`` service's ``fields`` say: callables ``(viewer, player) -> str
| None``, so a feature adds a mark (``channels``: afk); the game system's
``who_title`` puts a title after the name (Merc: ``the Swordpupil (1
warrior)``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from realm.core.perception import can_see
from realm.core.world import find_world
from realm.gateway import session as session_clock
from realm.gateway.session import online_players

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject

WhoField = Callable[["GameObject | None", "GameObject"], "str | None"]


class WhoService:
    """``world.services["who"]``: what ``who`` shows beside a name."""

    def __init__(self) -> None:
        self.fields: list[WhoField] = []

    def marks(self, viewer: GameObject | None, player: GameObject) -> list[str]:
        out = []
        for field in self.fields:
            text = field(viewer, player)
            if text:
                out.append(str(text))
        return out


def _sessions():
    world = find_world()
    return world.sessions if world is not None else None


def idle_seconds_of(player: GameObject) -> float | None:
    """Seconds since ``player`` last typed, or since its link dropped;
    None when it is not on."""
    sessions = _sessions()
    if sessions is None:
        return None
    session = sessions.get_session_by_player(player)
    if session is not None:
        return session.idle_time
    for waiting, since in sessions.linkdead():
        if waiting is player:
            return session_clock.clock() - since
    return None


def format_idle(seconds: float) -> str:
    idle = int(seconds)
    if idle < 60:
        return f"{idle}s"
    if idle < 3600:
        return f"{idle // 60}m"
    return f"{idle // 3600}h"


def linkdead_marker(obj: GameObject, looker: GameObject | None) -> str | None:
    """``feature.marker``: ``Ann (linkdead)`` in a room."""
    return "linkdead" if obj.has_tag("linkdead") else None


def who_rows(viewer: GameObject | None) -> list[tuple[GameObject, float, list[str]]]:
    """(player, idle seconds, marks) for everyone ``viewer`` sees on."""
    sessions = _sessions()
    if sessions is None:
        return []
    world = find_world()
    service = world.services.get("who") if world is not None else None
    rows = []
    for session in sessions.playing_sessions():
        player = session.player
        if player is not None and can_see(viewer, player):
            rows.append((player, session.idle_time, []))
    now = session_clock.clock()
    for player, since in sessions.linkdead():
        if can_see(viewer, player):
            rows.append((player, now - since, ["linkdead"]))
    if service is not None:
        for player, _idle, marks in rows:
            marks.extend(service.marks(viewer, player))
    return rows


async def cmd_who(ctx: CommandContext) -> None:
    """
    Show who is online: each player's idle time, their marks (afk,
    linkdead, and whatever the game adds) and where they are.

    Usage: who
    """
    rows = who_rows(ctx.player)
    lines = [f"\n{'=' * 40}", f"  {len(rows)} player(s) online", f"{'=' * 40}"]
    if rows:
        lines.append("")
    world = find_world()
    rules = world.rules if world is not None else None
    for player, idle, marks in rows:
        title = rules.who_title(player) if rules is not None else None
        named = f"{player.name} {title}" if title else player.name
        shown = f" [{', '.join(marks)}]" if marks else ""
        where = f" in {player.location.name}" if player.location is not None else ""
        lines.append(f"  {named}{shown} (idle {format_idle(idle)}){where}")
    lines.append("")
    ctx.session.send_paged("\n".join(lines))


# --- softcode -------------------------------------------------------------------------------


def online_players_fn(frame) -> list[GameObject]:
    """
    The characters in play now that the running object can see.

    Example: [name(p) for p in online_players()]
    """
    return [p for p in online_players() if can_see(frame.executor, p)]


def idle_seconds(frame, obj: GameObject | str | None) -> int | None:
    """
    Seconds since a player last typed (or since its link dropped); None
    when it is not on.

    Example: idle_seconds(enactor) > 600
    """
    target = frame.resolve(obj)
    if target is None:
        return None
    idle = idle_seconds_of(target)
    return None if idle is None else int(idle)


__all__ = ["WhoService", "idle_seconds_of", "format_idle",
           "linkdead_marker", "who_rows", "cmd_who", "online_players_fn", "idle_seconds"]
