"""
Running a live game (MUD_PLAN step 9): announce, stop, watch, hold.

``@wall`` speaks to every connection; ``@shutdown`` and ``@reboot`` count
down, save and stop the server (``@reboot`` exits with the status a
supervisor restarts on); ``@snoop`` echoes a player's output to an admin;
``@freeze`` refuses a player's input until ``@thaw``. Each is logged on
``realm.admin``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from realm.commands.base import find_object_global

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject
    from realm.core.world import World
    from realm.gateway.session import Session

admin_log = logging.getLogger("realm.admin")

FROZEN = "frozen"
#: what a frozen player may still type
THAWED_COMMANDS = frozenset({"quit"})
DEFAULT_COUNTDOWN = 60


async def cmd_wall(ctx: CommandContext) -> None:
    """
    Announce something to everyone connected, playing or not.

    Usage: @wall <message>
    """
    message = (ctx.args or "").strip()
    if not message:
        await ctx.session.send("Usage: @wall <message>")
        return
    admin_log.info(f"{ctx.player.name} walls: {message}")
    for session in ctx.session_manager.all_sessions() if ctx.session_manager else []:
        await session.send(f"*** {ctx.player.name} announces: {message} ***")


def _server(ctx: CommandContext):
    return ctx.dispatcher.server if ctx.dispatcher is not None else None


async def _stop(ctx: CommandContext, *, reboot: bool) -> None:
    what = "@reboot" if reboot else "@shutdown"
    server = _server(ctx)
    if server is None:
        await ctx.session.send("There is no server to stop here.")
        return
    if "cancel" in ctx.switches:
        if server.cancel_shutdown():
            admin_log.info(f"{ctx.player.name} cancelled the shutdown")
            await server.wall(f"*** The shutdown is cancelled by {ctx.player.name}. ***")
        else:
            await ctx.session.send("There is nothing to cancel.")
        return
    raw = (ctx.left_args or "").strip()
    if raw and not raw.isdigit():
        await ctx.session.send(f"Usage: {what} [seconds] [= reason]")
        return
    seconds = int(raw) if raw else DEFAULT_COUNTDOWN
    reason = (ctx.right_args or "").strip()
    if server.shutdown_pending:
        await ctx.session.send(f"A shutdown is already counting down ({what}/cancel first).")
        return
    admin_log.info(f"{ctx.player.name} ordered {what} in {seconds}s"
                   + (f": {reason}" if reason else ""))
    await server.schedule_shutdown(seconds, reason, reboot=reboot)


async def cmd_shutdown(ctx: CommandContext) -> None:
    """
    Stop the server after a countdown (default 60 seconds), announced to
    everyone; everything is saved first. /cancel stops the countdown.

    Usage: @shutdown [seconds] [= reason]
           @shutdown/cancel
    """
    await _stop(ctx, reboot=False)


async def cmd_reboot(ctx: CommandContext) -> None:
    """
    As @shutdown, and the server exits with the status its supervisor
    restarts it on (systemd: docs/guides/operations.md).

    Usage: @reboot [seconds] [= reason]
           @reboot/cancel
    """
    await _stop(ctx, reboot=True)


def _connected_player(ctx: CommandContext, name: str) -> tuple[GameObject | None, Session | None]:
    target = find_object_global(ctx, name)
    if target is None or not target.is_player:
        return None, None
    sessions = ctx.session_manager
    return target, sessions.get_session_by_player(target) if sessions else None


async def cmd_snoop(ctx: CommandContext) -> None:
    """
    See everything a player is sent, marked with their name; @snoop alone
    stops. Logged.

    Usage: @snoop <player>
           @snoop
    """
    name = (ctx.args or "").strip()
    sessions = ctx.session_manager
    watching = [s for s in (sessions.all_sessions() if sessions else [])
                if ctx.session in s.snoopers]
    if not name:
        if not watching:
            await ctx.session.send("You are not snooping anyone.")
            return
        for session in watching:
            session.snoopers.remove(ctx.session)
            who = session.player.name if session.player is not None else session.address
            admin_log.info(f"{ctx.player.name} stops snooping {who}")
            await ctx.session.send(f"You stop snooping {who}.")
        return
    target, session = _connected_player(ctx, name)
    if target is None:
        await ctx.session.send(f"Player '{name}' not found.")
        return
    if session is None:
        await ctx.session.send(f"{target.name} is not connected.")
        return
    if session is ctx.session:
        await ctx.session.send("You can't snoop yourself.")
        return
    if ctx.session in session.snoopers:
        await ctx.session.send(f"You are already snooping {target.name}.")
        return
    if ctx.session.reaches(session):
        await ctx.session.send(f"{target.name} already sees what you see: that would loop.")
        return
    session.snoopers.append(ctx.session)
    admin_log.info(f"{ctx.player.name} snoops {target.name}")
    await ctx.session.send(f"You are snooping {target.name}. @snoop alone stops.")


async def _set_frozen(ctx: CommandContext, frozen: bool) -> None:
    what = "@freeze" if frozen else "@thaw"
    name = (ctx.args or "").strip()
    if not name:
        await ctx.session.send(f"Usage: {what} <player>")
        return
    target = find_object_global(ctx, name)
    if target is None or not target.is_player:
        await ctx.session.send(f"Player '{name}' not found.")
        return
    if frozen and target is ctx.player:
        await ctx.session.send("You can't freeze yourself.")
        return
    if target.has_tag(FROZEN) == frozen:
        await ctx.session.send(f"{target.name} is {'already' if frozen else 'not'} frozen.")
        return
    if frozen:
        target.add_tag(FROZEN)
        target.msg("You have been frozen by an administrator.")
    else:
        target.remove_tag(FROZEN)
        target.msg("You can act again.")
    admin_log.info(f"{ctx.player.name} {'freezes' if frozen else 'thaws'} {target.name}")
    await ctx.session.send(f"{target.name} is {'frozen' if frozen else 'thawed'}.")


async def cmd_freeze(ctx: CommandContext) -> None:
    """
    Refuse everything a player types (but quit) until @thaw. Logged.

    Usage: @freeze <player>
    """
    await _set_frozen(ctx, True)


async def cmd_thaw(ctx: CommandContext) -> None:
    """
    Let a frozen player act again.

    Usage: @thaw <player>
    """
    await _set_frozen(ctx, False)


async def frozen_interceptor(world: World, session: Session, line: str) -> bool:
    """``feature.input_interceptor``: a frozen player's input is refused."""
    player = session.player
    if player is None or not player.has_tag(FROZEN):
        return False
    words = line.split(maxsplit=1)
    if words and words[0].lower() in THAWED_COMMANDS:
        return False
    await session.send("You are frozen and cannot act.")
    return True


__all__ = ["FROZEN", "cmd_wall", "cmd_shutdown", "cmd_reboot", "cmd_snoop", "cmd_freeze",
           "cmd_thaw", "frozen_interceptor"]
