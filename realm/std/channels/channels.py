"""
Channels (MUD_PLAN 7.2).

A channel is a ``channel_def`` object: its name (and optional ``alias``)
is a command, its ``speak`` and ``listen`` locks decide who may talk and
hear (``immtalk`` is staff-only by data), ``format`` is how a line reads
(``[{channel}] {name}: {message}``), and the last ``history_size`` lines
are kept in ``history``.

A message is one ``comm:on_channel`` action (hook ``CHANNEL``, payload
``channel`` and ``message``) with the channel definition as its target, so
softcode on the definition hears every line. It reaches every online
player who passes the listen lock and has the channel on, except one the
world's deaf rules silence (a sleeper). Preferences (``channels_off``) are
kept on the account when there is one, else on the character.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from realm.core.propagation import Action, propagate
from realm.core.world import find_world
from realm.permissions.locks import check_lock
from realm.std.channels.common import online_players, preferences_holder

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject

DEFAULT_FORMAT = "[{channel}] {name}: {message}"
DEFAULT_HISTORY = 20


def channels() -> list[GameObject]:
    from realm.core.defs import def_objects
    return sorted(def_objects("channel").values(), key=lambda o: o.name)


def find_channel(word: str) -> GameObject | None:
    """The channel whose name or alias is ``word``."""
    want = word.strip().lower()
    for channel in channels():
        if want in (channel.name.lower(), str(channel.db.get("alias") or "").lower()):
            return channel
    return None


def may_speak(player: GameObject, channel: GameObject) -> bool:
    return check_lock(channel, "speak", player)


def may_listen(player: GameObject, channel: GameObject) -> bool:
    return check_lock(channel, "listen", player)


def is_on(player: GameObject, channel: GameObject) -> bool:
    off = preferences_holder(player).db.get("channels_off") or []
    return channel.name not in off


def set_on(player: GameObject, channel: GameObject, on: bool) -> None:
    holder = preferences_holder(player)
    off = [c for c in (holder.db.get("channels_off") or []) if c != channel.name]
    if not on:
        off.append(channel.name)
    holder.db.channels_off = off


def members(channel: GameObject) -> list[GameObject]:
    """The online players who hear ``channel`` now."""
    return [p for p in online_players() if may_listen(p, channel) and is_on(p, channel)]


def _deaf(player: GameObject, action: Action) -> bool:
    world = find_world()
    return any(rule(player, action) for rule in (world.deaf_rules if world else ()))


def _remember(channel: GameObject, line: str) -> None:
    size = int(channel.db.get("history_size") or DEFAULT_HISTORY)
    history = [*(channel.db.get("history") or []), [time.time(), line]][-size:]
    channel.db.history = history


async def broadcast(channel: GameObject, line: str, *, speaker: GameObject | None,
                    message: str) -> Action:
    """Announce ``line`` on ``channel`` and deliver it to its members."""
    action = Action(actor=speaker, target=channel, action_type="comm:on_channel",
                    extra={"channel": channel.name, "message": message})
    await propagate(action, deliver=False)
    if action.blocked:
        if speaker is not None:
            speaker.msg(action.block_reason or "Your words do not carry.")
        return action
    _remember(channel, line)
    for player in members(channel):
        if player is not speaker and _deaf(player, action):
            continue
        player.msg(line)
    return action


def format_line(channel: GameObject, name: str, message: str) -> str:
    template = str(channel.db.get("format") or DEFAULT_FORMAT)
    # Player text goes in last, so it cannot name a {field}.
    return (template.replace("{channel}", channel.name).replace("{name}", name)
            .replace("{message}", message))


async def channel_fallback(ctx: CommandContext) -> bool:
    """``feature.fallback``: a channel's name or alias speaks on it. A
    world ``$``-command of the same word comes first."""
    player = ctx.player
    channel = find_channel(ctx.command_name) if player is not None else None
    if channel is None:
        return False
    world = find_world()
    if world is not None and world.scripts is not None \
            and await world.scripts.handle_unknown_command(ctx):
        return True
    message = (ctx.args or "").strip()
    if not may_speak(player, channel):
        await ctx.session.send(f"You may not speak on {channel.name}.")
        return True
    if not is_on(player, channel):
        await ctx.session.send(f"You have {channel.name} turned off "
                               f"('channel {channel.name} on').")
        return True
    if not message:
        await ctx.session.send(f"Say what on {channel.name}?")
        return True
    await broadcast(channel, format_line(channel, player.name, message),
                    speaker=player, message=message)
    return True


async def cmd_channels(ctx: CommandContext) -> None:
    """
    List the channels you can hear, and whether each is on.

    Usage: channels
    """
    player = ctx.player
    rows = [c for c in channels() if may_listen(player, c)]
    if not rows:
        await ctx.session.send("There are no channels.")
        return
    lines = ["Channels:"]
    for channel in rows:
        alias = channel.db.get("alias")
        shown = f"{channel.name} ({alias})" if alias else channel.name
        state = "on" if is_on(player, channel) else "off"
        lines.append(f"  {shown:20} {state:4} {channel.db.get('description') or ''}")
    lines.append("Talk on one by typing its name: gossip hello. "
                 "channel <name> on|off|history")
    await ctx.session.send("\n".join(lines))


async def cmd_channel(ctx: CommandContext) -> None:
    """
    Turn a channel on or off, or show its recent lines.

    Usage: channel <name> on|off|history
    """
    words = (ctx.args or "").split()
    if len(words) != 2:
        await ctx.session.send("Usage: channel <name> on|off|history")
        return
    channel = find_channel(words[0])
    player = ctx.player
    if channel is None or not may_listen(player, channel):
        await ctx.session.send(f"There is no channel called '{words[0]}'.")
        return
    what = words[1].lower()
    if what in ("on", "off"):
        set_on(player, channel, what == "on")
        await ctx.session.send(f"{channel.name} is {what}.")
    elif what == "history":
        history = channel.db.get("history") or []
        if not history:
            await ctx.session.send(f"Nothing has been said on {channel.name}.")
            return
        lines = [f"Recent {channel.name}:"]
        for stamp, line in history:
            lines.append(f"  {time.strftime('%H:%M', time.gmtime(float(stamp)))} {line}")
        await ctx.session.send("\n".join(lines))
    else:
        await ctx.session.send("Usage: channel <name> on|off|history")


__all__ = ["DEFAULT_FORMAT", "channels", "find_channel", "may_speak", "may_listen", "is_on",
           "set_on", "members", "broadcast", "format_line", "channel_fallback",
           "cmd_channels", "cmd_channel"]
