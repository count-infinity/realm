"""
The ``rules`` feature's commands: the character sheet and advancement.
"""

from __future__ import annotations

from realm.commands import CommandContext
from realm.core.world import get_world
from realm.std.rules.checks import skill_level


async def cmd_points(ctx: CommandContext) -> None:
    """
    Show your character sheet (score).

    The sheet speaks the active game system's language: a point-buy
    system (GURPS/D20) shows character points and skills; an XP system
    (merc) shows level, experience, combat stats, and equipment.

    Usage: score / points
    """
    system = get_world().rules
    if system is not None:
        lines = system.score_lines(ctx.player)
    else:
        cp = int(ctx.player.db.get('character_points') or 0)
        lines = [f"Character points: {cp}"]
    await ctx.session.send("\n" + "\n".join(lines) + "\n")


IMPROVE_COST = 4  # character points per +1 skill level (GURPS-ish)


async def cmd_improve(ctx: CommandContext) -> None:
    """
    Spend character points to raise a skill by one level.

    Usage: improve <skill>       e.g. improve stealth

    Example:
        improve stealth        (4 CP per level under GURPS)
    """

    skill = ctx.args.strip().lower().replace(' ', '_')
    if not skill:
        await ctx.session.send("Improve which skill? (see: points)")
        return
    if skill.startswith('skill_'):
        skill = skill[6:]

    cp = int(ctx.player.db.get('character_points') or 0)
    system = get_world().rules
    current = skill_level(ctx.player, skill)
    cost = system.improve_cost(skill, current) if system else IMPROVE_COST
    if cp < cost:
        await ctx.session.send(
            f"Improving {skill} costs {cost} points; you have {cp}."
        )
        return

    ctx.player.db.set(f"skill_{skill}", current + 1)
    ctx.player.db.character_points = cp - cost
    await ctx.session.send(
        f"You train {skill.replace('_', ' ')} to {current + 1} "
        f"({cp - cost} points remain)."
    )
