"""
Social commands: greet, persuade, fasttalk.

The disposition layer made playable — first impressions (memoized
reaction rolls), honest persuasion (permanent +1), and fast talk
(a bigger boost that WEARS OFF, with a price for getting caught).
"""

from __future__ import annotations

from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_object
from realm.core.checks import contest
from realm.core.disposition import (
    adjust_disposition,
    disposition_band,
    get_disposition,
    reaction_roll,
)

BAND_DESCRIPTIONS = {
    "hostile": "{name} regards you with open hostility.",
    "unfriendly": "{name} eyes you with suspicion.",
    "neutral": "{name} regards you neutrally.",
    "friendly": "{name} seems well-disposed toward you.",
    "devoted": "{name} clearly holds you in the highest regard.",
}


def _find_npc(ctx: CommandContext, spec: str):
    target = find_object(ctx, spec, search_room=True, search_inventory=False)
    if target is None or not (target.has_tag('npc') or target.has_tag('player')):
        return None
    return target


async def cmd_greet(ctx: CommandContext) -> None:
    """
    Size up an NPC — rolls the first-impression reaction if you've
    never interacted, then shows their attitude.

    Usage: consider <npc>       (alias: con)
    """
    if not ctx.player or not ctx.args:
        await ctx.session.send("Consider whom?")
        return
    target = _find_npc(ctx, ctx.args.strip())
    if target is None:
        await ctx.session.send(f"You don't see '{ctx.args.strip()}' here.")
        return

    value = reaction_roll(target, ctx.player)
    band = disposition_band(value)
    await ctx.session.send(
        BAND_DESCRIPTIONS[band].format(name=target.name.capitalize()))


async def cmd_persuade(ctx: CommandContext) -> None:
    """
    Honestly win someone over: persuasion vs will. Success sticks
    (+1 disposition, permanent); failure hardens them slightly. One
    attempt per person per cooldown.

    Usage: persuade <npc>
    """
    if not ctx.player or not ctx.args:
        await ctx.session.send("Persuade whom?")
        return
    target = _find_npc(ctx, ctx.args.strip())
    if target is None:
        await ctx.session.send(f"You don't see '{ctx.args.strip()}' here.")
        return
    if target is ctx.player:
        await ctx.session.send("You are already convinced.")
        return

    cooldowns = target.db.get('persuade_cooldowns') or {}
    if cooldowns.get(ctx.player.id):
        await ctx.session.send(
            f"{target.name.capitalize()} has heard you out already. "
            "Give it a rest.")
        return

    reaction_roll(target, ctx.player)  # first impression baseline
    won = contest(ctx.player, 'persuasion', target, 'will')
    cooldowns = dict(cooldowns)
    cooldowns[ctx.player.id] = True
    target.db.persuade_cooldowns = cooldowns

    if won:
        value = adjust_disposition(target, ctx.player, 1)
        await ctx.session.send(
            f"{target.name.capitalize()} nods along — you've won some "
            f"goodwill. ({disposition_band(value)})")
        target.location and target.location.msg_contents(
            f"{ctx.player.name} makes a persuasive case to {target.name}.",
            exclude=[ctx.player])
    else:
        value = adjust_disposition(target, ctx.player, 0)
        await ctx.session.send(
            f"{target.name.capitalize()} remains unmoved. "
            f"({disposition_band(value)})")


async def cmd_fasttalk(ctx: CommandContext) -> None:
    """
    Bend the truth: fast_talk vs detect_lies. Success buys +2
    disposition that WEARS OFF (~2 min); getting caught costs you -1,
    permanently.

    Usage: fasttalk <npc>
    """
    if not ctx.player or not ctx.args:
        await ctx.session.send("Fast-talk whom?")
        return
    target = _find_npc(ctx, ctx.args.strip())
    if target is None:
        await ctx.session.send(f"You don't see '{ctx.args.strip()}' here.")
        return
    if target is ctx.player:
        await ctx.session.send("You talk yourself in circles.")
        return

    already = any(b.behavior_id == 'disposition_boost'
                  and b.get_param('target_id') == ctx.player.id
                  for b in target.get_behaviors())
    if already:
        await ctx.session.send(
            f"{target.name.capitalize()} is already eating out of your hand.")
        return

    reaction_roll(target, ctx.player)
    won = contest(ctx.player, 'fast_talk', target, 'detect_lies')

    if won:
        from realm.behaviors.effects import DispositionBoostBehavior
        target.add_behavior(DispositionBoostBehavior(
            target_id=ctx.player.id, delta=2, duration=30))
        value = get_disposition(target, ctx.player)
        await ctx.session.send(
            f"{target.name.capitalize()} buys every word — for now. "
            f"({disposition_band(value)})")
    else:
        value = adjust_disposition(target, ctx.player, -1)
        await ctx.session.send(
            f"{target.name.capitalize()} sees right through you. "
            f"({disposition_band(value)})")
        target.location and target.location.msg_contents(
            f"{target.name.capitalize()} scowls at {ctx.player.name}.",
            exclude=[ctx.player])


async def cmd_follow(ctx: CommandContext) -> None:
    """
    Fall in behind someone — you'll walk exits after them.

    Usage: follow <target>
           follow          (stop following)
    """
    from realm.core.party import leader_id, set_following

    spec = (ctx.args or "").strip()
    if not spec or spec.lower() in ('me', 'self', 'none', 'stop'):
        if leader_id(ctx.player):
            set_following(ctx.player, None)
            await ctx.session.send("You stop following.")
        else:
            await ctx.session.send("Follow whom?")
        return

    target = find_object(ctx, spec, search_room=True, search_inventory=False)
    if target is None or target is ctx.player:
        await ctx.session.send(f"You don't see '{spec}' here.")
        return

    set_following(ctx.player, target)
    await ctx.session.send(f"You fall in behind {target.name}.")
    target.msg(f"{ctx.player.name} starts following you.")


async def cmd_unfollow(ctx: CommandContext) -> None:
    """Stop following. Usage: unfollow"""
    from realm.core.party import leader_id, set_following

    if leader_id(ctx.player):
        set_following(ctx.player, None)
        await ctx.session.send("You stop following.")
    else:
        await ctx.session.send("You aren't following anyone.")


async def cmd_party(ctx: CommandContext) -> None:
    """
    Who's traveling with you (the follow chains in this room).

    Usage: party (alias: group)
    """
    from realm.core.party import leader_id, party_members

    members = party_members(ctx.player)
    if len(members) == 1:
        await ctx.session.send("You're on your own.")
        return
    lines = ["Your party:"]
    for member in members:
        lid = leader_id(member)
        suffix = ""
        if member is ctx.player:
            suffix = " (you)"
        if lid:
            leader = next((m for m in members if m.id == lid), None)
            if leader is not None:
                suffix += f" — following {leader.name}"
        lines.append(f"  {member.name}{suffix}")
    await ctx.session.send("\n".join(lines))


def register_social_commands(dispatcher: CommandDispatcher) -> None:
    # NOT "greet" — that's a classic softcode $-command name and
    # builtins shadow the softcode fallback.
    dispatcher.register(
        "consider", cmd_greet, aliases=["con"],
        help_text="Size up an NPC's attitude toward you",
        usage="consider <npc>")
    dispatcher.register(
        "persuade", cmd_persuade,
        help_text="Win someone over honestly (persuasion vs will)",
        usage="persuade <npc>")
    dispatcher.register(
        "fasttalk", cmd_fasttalk, aliases=["fast-talk"],
        help_text="Bend the truth for temporary goodwill (fast_talk vs detect_lies)",
        usage="fasttalk <npc>")
    dispatcher.register(
        "follow", cmd_follow,
        help_text="Walk exits after someone (follow with no target stops)",
        usage="follow [<target>]")
    dispatcher.register(
        "unfollow", cmd_unfollow,
        help_text="Stop following",
        usage="unfollow")
    dispatcher.register(
        "party", cmd_party, aliases=["group"],
        help_text="Show who's traveling with you",
        usage="party")
