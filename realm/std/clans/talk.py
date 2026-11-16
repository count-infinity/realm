"""
Clan talk (MUD_PLAN 14.7): ``clantalk <message>`` (``ct``), for members
whose position has the ``channel`` power.

One propagated action (``clan:on_talk``, hook ``CLANTALK``, the clan as
target) delivered to the online members with the power, through the
``channels`` feature's delivery path (its service), with the last lines
kept on the clan's ``history``. Without ``channels``, clan talk is
unavailable.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from realm.core.propagation import Action
from realm.core.world import find_world
from realm.gateway.session import online_players
from realm.std.clans.clans import clans_of, has_power, is_member

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject


def _channels():
    world = find_world()
    return world.services.get("channels") if world is not None else None


def remember(clan: GameObject, line: str) -> None:
    """Keep a line in the clan's talk history (with ``channels``)."""
    service = _channels()
    if service is not None:
        service.remember(clan, line)


def listeners(clan: GameObject) -> list[GameObject]:
    """The online members who hear clan talk."""
    return [p for p in online_players()
            if is_member(clan, p) and has_power(clan, p, "channel")]


def _named(player: GameObject, text: str) -> tuple[GameObject | None, str]:
    """``(clan, message)`` when ``text`` starts with the name of one of
    ``player``'s clans (the longest that fits), else ``(None, text)``."""
    lowered = text.lower()
    best = None
    for clan in clans_of(player):
        name = clan.name.lower()
        if (lowered == name or lowered.startswith(name + " ")) and (
                best is None or len(name) > len(best.name)):
            best = clan
    if best is None:
        return None, text
    return best, text[len(best.name):].strip()


async def cmd_clantalk(ctx: CommandContext) -> None:
    """
    Talk to your clan, wherever its members are. A member of clans in two
    categories names the clan first. With nothing to say, shows the
    clan's recent lines.

    Usage: clantalk [<clan>] <message>

    Examples:
        ct Meet at the hall at dusk.
        ct Smiths The forge is lit.
    """
    player = ctx.player
    text = (ctx.args or "").strip()
    service = _channels()
    if service is None:
        await ctx.session.send("Clan talk is unavailable here.")
        return
    mine = [c for c in clans_of(player) if is_member(c, player)]
    if not mine:
        await ctx.session.send("You are not in a clan.")
        return
    clan, message = _named(player, text)
    if clan is None:
        if len(mine) > 1:
            names = " or ".join(c.name for c in mine)
            await ctx.session.send(f"Which clan? ct <clan> <message> ({names}).")
            return
        clan, message = mine[0], text
    if not has_power(clan, player, "channel"):
        await ctx.session.send(f"Your position in {clan.name} does not speak on clan talk.")
        return
    if not message:
        history = clan.db.get("history") or []
        if not history:
            await ctx.session.send(f"Nothing has been said in {clan.name}.")
            return
        lines = [f"Recent {clan.name} talk:"]
        for stamp, line in history:
            lines.append(f"  {time.strftime('%H:%M', time.gmtime(float(stamp)))} {line}")
        ctx.session.send_paged("\n".join(lines))
        return
    action = Action(actor=player, target=clan, action_type="clan:on_talk",
                    extra={"clan": clan.name, "message": message})
    await service.deliver(action, f"[{clan.name}] {player.name}: {message}",
                          listeners(clan), history=clan)


__all__ = ["remember", "listeners", "cmd_clantalk"]
