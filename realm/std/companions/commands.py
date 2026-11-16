"""
Companion commands: ``companions``, ``order``, ``dismiss``, ``mount``,
``dismount`` (MUD_PLAN 13.1, 13.3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.commands.base import find_object
from realm.core.pools import pool_get, pool_max, vital_pool
from realm.core.search import match_one
from realm.core.world import get_world
from realm.std.companions import riding
from realm.std.companions.companions import (
    companion_limit,
    companions_of,
    follower_count,
    master_of,
    set_master,
    the,
)

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject

#: Never ordered, whatever ``ORDER_REFUSED`` says.
ALWAYS_REFUSED = frozenset({"order", "quit"})


def _condition(obj: GameObject) -> str:
    pool = vital_pool(obj)
    value = pool_get(obj, pool) if pool is not None else None
    maximum = pool_max(obj, pool) if pool is not None else None
    if value is None:
        return ""
    return f"{value}/{maximum} {pool}" if maximum is not None else f"{value} {pool}"


def _whereabouts(obj: GameObject, master: GameObject) -> str:
    if obj.location is None:
        return "waiting"
    if obj.location is master.location:
        return "here"
    return f"in {obj.location.name}"


async def cmd_companions(ctx: CommandContext) -> None:
    """
    List your companions (pets, charmed creatures, mounts): their
    condition, where they are, and how many more you may keep.

    Usage: companions
    """
    player = ctx.player
    lines = []
    keeping = companions_of(player)
    if keeping:
        lines.append("Your followers:")
        for obj in keeping:
            notes = [n for n in (_condition(obj), _whereabouts(obj, player)) if n]
            marks = [m for m, on in (("mount", obj.has_tag(riding.MOUNT_TAG)),
                                     ("charmed", obj.has_tag("charmed")),
                                     ("ridden", riding.rider_of(obj) is player)) if on]
            label = obj.name + (f" ({', '.join(marks)})" if marks else "")
            lines.append(f"  {label:<32} {'  '.join(notes)}")
    else:
        lines.append("You have no companions.")
    lines.append(f"You have {follower_count(player)} of {companion_limit(player)} followers.")
    await ctx.session.send("\n".join(lines))


def _refused_command(ctx: CommandContext, line: str) -> str | None:
    """Why ``line`` may not be ordered: a command above ``player``,
    ``order``, ``quit``, or one the game lists in ``ORDER_REFUSED``."""
    dispatcher = ctx.dispatcher
    command = dispatcher.resolve(line)
    if command is None:
        return None
    refused = set(ALWAYS_REFUSED)
    for name in get_world().setting("ORDER_REFUSED") or ():
        listed = dispatcher.get_command(str(name))
        refused.add(listed.name if listed is not None else str(name).lower())
    if command.permission != "player" or command.name in refused:
        return f"You can't order anyone to '{line}'."
    return None


async def cmd_order(ctx: CommandContext) -> None:
    """
    Order a companion (or all of them here) to do something: the command
    runs as the companion, with its own permissions. Admin commands,
    `order` and `quit` are never obeyed.

    Usage: order <name|all> <command>

    Example:
        order kitten kill fido
        order all follow me
    """
    from realm.server.puppet import force_command
    player = ctx.player
    who, _, line = (ctx.args or "").strip().partition(" ")
    line = line.strip()
    if not who or not line:
        await ctx.session.send("Order whom to do what?")
        return
    if master_of(player) is not None:
        await ctx.session.send("You feel like taking, not giving, orders.")
        return
    refusal = _refused_command(ctx, line)
    if refusal:
        await ctx.session.send(refusal)
        return
    here = [obj for obj in companions_of(player)
            if obj.location is player.location and player.location is not None]
    if who.lower() == "all":
        chosen = here
        if not chosen:
            await ctx.session.send("You have no followers here.")
            return
    else:
        target = find_object(ctx, who, search_inventory=False)
        if target is None:
            await ctx.session.send("They aren't here.")
            return
        if target not in here:
            await ctx.session.send("Do it yourself!")
            return
        chosen = [target]
    for obj in chosen:
        name = the(obj, capital=False)
        if obj.has_tag("unconscious"):
            await ctx.session.send(f"{the(obj)} is in no state to obey.")
            continue
        await ctx.session.send(f"You order {name} to '{line}'.")
        player.location.msg_contents(f"{player.name} orders {name} to '{line}'.",
                                     exclude=[player])
        await force_command(ctx.dispatcher, obj, line, watcher=ctx.session)


async def cmd_dismiss(ctx: CommandContext) -> None:
    """
    Release a companion: it stops following and obeying you, and stays
    where it is.

    Usage: dismiss <name>
    """
    player = ctx.player
    spec = (ctx.args or "").strip()
    if not spec:
        await ctx.session.send("Dismiss whom?")
        return
    target = match_one(spec, companions_of(player))
    if target is None:
        await ctx.session.send(f"You have no companion called '{spec}'.")
        return
    name = the(target, capital=False)
    await ctx.session.send(f"You dismiss {name}.")
    if player.location is not None and target.location is player.location:
        player.location.msg_contents(f"{player.name} dismisses {name}.", exclude=[player])
    await set_master(target, None, reason="dismissed")


async def cmd_mount(ctx: CommandContext) -> None:
    """
    Climb onto one of your mounts. While you ride, it carries you (and, in
    a game that charges movement, pays for each step).

    Usage: mount <name>   (or: ride <name>)
    """
    player = ctx.player
    spec = (ctx.args or "").strip()
    if not spec:
        await ctx.session.send("Mount what?")
        return
    target = find_object(ctx, spec, search_inventory=False)
    if target is None:
        await ctx.session.send("You can't find that here.")
        return
    refusal = riding.mount_refusal(player, target)
    if refusal:
        await ctx.session.send(refusal)
        return
    riding.mount(player, target)
    name = the(target, capital=False)
    await ctx.session.send(f"You mount {name}.")
    player.location.msg_contents(f"{player.name} mounts {name}.", exclude=[player])
    store = get_world().store
    if store is not None:
        await store.save(player)
        await store.save(target)


async def cmd_dismount(ctx: CommandContext) -> None:
    """
    Get down from your mount.

    Usage: dismount
    """
    if not await riding.dismount(ctx.player, how="dismount"):
        await ctx.session.send("You're not mounted.")


__all__ = ["cmd_companions", "cmd_dismiss", "cmd_dismount", "cmd_mount", "cmd_order"]
