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
    (merc) shows level, experience, pools, combat stats, and equipment; a
    system that says nothing shows the character's pools.

    Usage: score / points
    """
    from realm.std.rules.progression import accrue_training
    accrue_training(ctx.player)
    lines = get_world().rules.score_lines(ctx.player)
    await ctx.session.send("\n" + "\n".join(lines) + "\n")


def skill_groups() -> dict[str, str]:
    """skill name -> its ``skill_def``'s ``group``, for those that have one."""
    from realm.std.rules.definitions import SKILL_DEF_TAG
    store = get_world().store
    out: dict[str, str] = {}
    for sdef in (store.find_cached(tag=SKILL_DEF_TAG) if store is not None else ()):
        group = sdef.db.get("group")
        if group:
            out[sdef.name.strip().lower().replace(" ", "_")] = str(group)
    return out


async def cmd_skills(ctx: CommandContext) -> None:
    """
    List the skills you have trained, and how good you are at each.

    Usage: skills
    """
    from realm.std.rules.progression import accrue_training, next_level_in, progression_of
    rules = get_world().rules
    accrue_training(ctx.player)
    trained = sorted((key[6:], value) for key, value in ctx.player.db.all().items()
                     if key.startswith('skill_') and not key.startswith('skill_xp_'))
    if not trained:
        await ctx.session.send("You have no trained skills.")
        return
    groups = skill_groups()
    by_group: dict[str, list[tuple[str, int]]] = {}
    for name, level in trained:
        by_group.setdefault(groups.get(name, ""), []).append((name, level))
    lines = ["Your skills:"]
    for group in sorted(by_group):                 # "" (ungrouped) first
        indent = "  "
        if group:
            lines.append(f"  {group}:")
            indent = "    "
        for name, level in by_group[group]:
            shown = rules.format_skill(name, int(level))
            how = progression_of(ctx.player, name)
            note = ""
            if how == "use":
                xp = int(ctx.player.db.get(f"skill_xp_{name}") or 0)
                note = f"   (use: {xp}/{rules.use_xp_needed(int(level))})"
            elif how == "idle" and ctx.player.db.get("training") == name:
                note = "   (training)"
            lines.append(f"{indent}{name.replace('_', ' '):20} {shown}{note}")
    training = ctx.player.db.get("training")
    if training:
        seconds = next_level_in(ctx.player) or 0
        lines.append(f"Training {training.replace('_', ' ')}: the next level in "
                     f"{int(seconds // 60) + 1} minute(s).")
    ctx.session.send_paged("\n".join(lines))


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

    current = skill_level(ctx.player, skill)
    cost = get_world().rules.improve_cost(skill, current)
    if cost is None:
        await ctx.session.send("This game has no skill purchase.")
        return
    cp = int(ctx.player.db.get('character_points') or 0)
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
