"""
Account administration (MUD_PLAN 6.6): ``@account`` and ``@sitelock``.

Every ban, unban, password reset, boot and sitelock change is logged at
INFO on the ``realm.admin`` logger, naming who did it and to whom.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from realm.core.world import get_world
from realm.std.accounts import account as accounts_clock
from realm.std.accounts.account import (
    FOREVER,
    admin_log,
    characters_of,
    ensure_sitelock_registry,
    find_account,
    parse_duration,
    sitelock_registry,
)

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject


def _when(stamp) -> str:
    if not stamp:
        return "never"
    if stamp == FOREVER:
        return "forever"
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(float(stamp)))


async def _boot(account: GameObject, message: str) -> int:
    sessions = get_world().sessions
    booted = 0
    for session in list(sessions.all_sessions()) if sessions is not None else []:
        if session.account is account:
            await session.send(message)
            await sessions.destroy_session(session)
            booted += 1
    return booted


async def cmd_account(ctx: CommandContext) -> None:
    """
    Look after an account.

    Usage: @account <name>                       show it
           @account/password <name> = <new>      reset its password
           @account/ban <name> <duration> = <reason>
                                                 ban it (30m, 2h, 3d, 1w, forever)
           @account/unban <name>                 lift a ban
           @account/boot <name>                  disconnect its sessions
    """
    who = ctx.player.name
    switch = ctx.switches[0] if ctx.switches else ""
    left = (ctx.left_args if "=" in (ctx.args or "") else ctx.args or "").strip()
    right = ctx.right_args.strip() if "=" in (ctx.args or "") else ""
    words = left.split()
    if not words:
        await ctx.session.send("Usage: @account <name>")
        return
    account = find_account(words[0])
    if account is None:
        await ctx.session.send(f"No account called '{words[0]}'.")
        return
    store = get_world().store

    if switch == "password":
        if len(right) < 4:
            await ctx.session.send("Give a new password of at least 4 characters: "
                                   "@account/password <name> = <new>")
            return
        get_world().services["accounts"].auth.set_password(account, right)
        await store.save(account)
        admin_log.info(f"{who} reset the password of account {account.name}")
        await ctx.session.send(f"{account.name}'s password is reset.")
    elif switch == "ban":
        length = parse_duration(words[1]) if len(words) > 1 else None
        if length is None:
            await ctx.session.send("Usage: @account/ban <name> <30m|2h|3d|1w|forever> "
                                   "= <reason>")
            return
        account.db.banned_until = (FOREVER if length == FOREVER
                                   else accounts_clock.now() + float(length))
        account.db.ban_reason = right or "no reason given"
        await store.save(account)
        admin_log.info(f"{who} banned account {account.name} until "
                       f"{_when(account.db.banned_until)}: {account.db.ban_reason}")
        await _boot(account, f"You have been banned: {account.db.ban_reason}")
        await ctx.session.send(f"{account.name} is banned until "
                               f"{_when(account.db.banned_until)}.")
    elif switch == "unban":
        account.db.delete("banned_until")
        account.db.delete("ban_reason")
        await store.save(account)
        admin_log.info(f"{who} unbanned account {account.name}")
        await ctx.session.send(f"{account.name} is no longer banned.")
    elif switch == "boot":
        booted = await _boot(account, "You have been disconnected by an administrator.")
        admin_log.info(f"{who} booted account {account.name} ({booted} session(s))")
        await ctx.session.send(f"Booted {booted} session(s) of {account.name}.")
    elif switch:
        await ctx.session.send(f"Unknown switch /{switch}. See: help @account")
    else:
        names = ", ".join(c.name for c in characters_of(account)) or "none"
        lines = [f"Account {account.name}",
                 f"  characters:  {names}",
                 f"  created:     {_when(account.db.get('created'))}",
                 f"  last login:  {_when(account.db.get('last_login'))} from "
                 f"{account.db.get('last_address') or 'nowhere'}"]
        if account.db.get("email"):
            lines.append(f"  email:       {account.db.email}")
        if account.db.get("banned_until") is not None:
            lines.append(f"  banned until {_when(account.db.banned_until)}: "
                         f"{account.db.get('ban_reason')}")
        await ctx.session.send("\n".join(lines))


async def cmd_sitelock(ctx: CommandContext) -> None:
    """
    Lock out connections from an address or an address prefix.

    Usage: @sitelock <address-or-prefix> [= reason]
           @sitelock/remove <address-or-prefix>
           @sitelock/list
    """
    who = ctx.player.name
    switch = ctx.switches[0] if ctx.switches else ""
    raw = ctx.args or ""
    prefix = (ctx.left_args if "=" in raw else raw).strip()
    reason = ctx.right_args.strip() if "=" in raw else ""
    if switch == "list" or (not switch and not prefix):
        registry = sitelock_registry()
        sites = (registry.db.get("sites") if registry is not None else None) or {}
        if not sites:
            await ctx.session.send("No sites are locked out.")
            return
        lines = ["Locked-out sites:"]
        for site, entry in sorted(sites.items()):
            lines.append(f"  {site:20} {entry.get('reason')}  (by {entry.get('by')}, "
                         f"{_when(entry.get('at'))})")
        await ctx.session.send("\n".join(lines))
        return
    registry = await ensure_sitelock_registry()
    sites = dict(registry.db.get("sites") or {})
    if switch == "remove":
        if sites.pop(prefix, None) is None:
            await ctx.session.send(f"{prefix} is not locked out.")
            return
        registry.db.sites = sites
        await get_world().store.save(registry)
        admin_log.info(f"{who} removed the sitelock on {prefix}")
        await ctx.session.send(f"{prefix} may connect again.")
        return
    sites[prefix] = {"reason": reason or "this site is locked out", "by": who,
                     "at": accounts_clock.now()}
    registry.db.sites = sites
    await get_world().store.save(registry)
    admin_log.info(f"{who} sitelocked {prefix}: {sites[prefix]['reason']}")
    await ctx.session.send(f"{prefix} is locked out: {sites[prefix]['reason']}")


__all__ = ["cmd_account", "cmd_sitelock"]
