"""
Combat commands: fighting on the beat.

``attack`` opens (or joins) the room's encounter; from then on the
fight advances on the encounter's beat. ``queue`` (or the maneuver
shortcuts) sets what you'll do when the beat fires — freely changeable
until then. ``pace`` tunes your preferred beat length; the slowest
player in a fight sets its tempo.
"""

from __future__ import annotations

from realm.combat.manager import get_combat_manager, is_combat_capable
from realm.combat.maneuver import QueuedAction
from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_object
from realm.core.checks import check


def _manager(ctx: CommandContext):
    manager = get_combat_manager()
    if manager is None:
        return None
    return manager


def _bar(current: int, maximum: int, width: int = 10) -> str:
    maximum = max(1, maximum)
    filled = max(0, min(width, round(width * current / maximum)))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


async def cmd_attack(ctx: CommandContext) -> None:
    """
    Attack someone — starts combat, or switches your target in a fight.

    Usage: attack <target>
           kill <target>

    Example:
        attack thug
    """
    if ctx.player.has_tag('unconscious'):
        await ctx.session.send("You are unconscious.")
        return
    if not ctx.args:
        await ctx.session.send("Attack whom?")
        return
    manager = _manager(ctx)
    if manager is None:
        await ctx.session.send("Combat is not enabled here.")
        return

    target = find_object(ctx, ctx.args.strip(),
                         search_room=True, search_inventory=False)
    if not target:
        await ctx.session.send(f"You don't see '{ctx.args.strip()}' here.")
        return
    if target is ctx.player:
        await ctx.session.send("Attacking yourself won't help.")
        return
    if not is_combat_capable(target):
        await ctx.session.send(f"{target.name} is not something you can fight.")
        return

    encounter = manager.encounter_of(ctx.player)
    starting = encounter is None or encounter.get(target.id) is None

    encounter = await manager.initiate(ctx.player, target)
    if encounter is None:
        await ctx.session.send("You can't start a fight here.")
        return
    encounter.queue(ctx.player, QueuedAction(maneuver="attack", target_id=target.id))

    if starting:
        ctx.player.msg(f"You square off against {target.name}!")
        if ctx.player.location:
            ctx.player.location.msg_contents(
                f"{ctx.player.get_display_name(None)} squares off against {target.name}!",
                exclude=[ctx.player],
            )
    else:
        await ctx.session.send(
            f"You will attack {target.name} on the next beat "
            f"({int(encounter.seconds_to_beat)}s)."
        )


async def cmd_queue(ctx: CommandContext) -> None:
    """
    Choose your next combat action; replaceable until the beat fires.

    Usage: queue <maneuver> [target]
           e.g. queue defend | queue attack guard | queue flee north

    Example:
        queue shoot thug
        queue aim thug
        queue close
    """
    manager = _manager(ctx)
    encounter = manager.encounter_of(ctx.player) if manager else None
    if encounter is None:
        await ctx.session.send("You aren't in combat.")
        return
    if not ctx.args:
        maneuvers = ", ".join(m.key for m in encounter.combat_system.ruleset.maneuvers())
        await ctx.session.send(f"Queue what? Maneuvers: {maneuvers}")
        return

    parts = ctx.args.strip().split(None, 1)
    maneuver = encounter.combat_system.ruleset.get_maneuver(parts[0])
    if maneuver is None:
        await ctx.session.send(f"Unknown maneuver '{parts[0]}'.")
        return
    rest = parts[1].strip() if len(parts) > 1 else ""

    target_id = None
    if maneuver.needs_target:
        if rest:
            target = find_object(ctx, rest, search_room=True, search_inventory=False)
            if not target or encounter.get(target.id) is None:
                await ctx.session.send(f"'{rest}' isn't in this fight.")
                return
            target_id = target.id
            rest = ""
        # else: fall back to current target at fire time

    encounter.queue(ctx.player, QueuedAction(
        maneuver=maneuver.key, target_id=target_id, args=rest,
    ))
    await ctx.session.send(
        f"Queued: {maneuver.name}"
        f"{' (fires in ' + str(int(encounter.seconds_to_beat)) + 's)'}"
    )


def _make_shortcut(maneuver_key: str):
    async def shortcut(ctx: CommandContext) -> None:
        ctx.args = f"{maneuver_key} {ctx.args}".strip()
        await cmd_queue(ctx)
    return shortcut


async def cmd_flee(ctx: CommandContext) -> None:
    """
    Try to escape combat through an exit (resolves on the beat).

    Usage: flee [direction]

    Example:
        flee north
    """
    manager = _manager(ctx)
    encounter = manager.encounter_of(ctx.player) if manager else None
    if encounter is None:
        await ctx.session.send("You aren't fighting anyone.")
        return
    encounter.queue(ctx.player, QueuedAction(maneuver="flee", args=ctx.args.strip()))
    await ctx.session.send(
        f"You look for an escape route... (fires in "
        f"{int(encounter.seconds_to_beat)}s)"
    )


async def cmd_combat_status(ctx: CommandContext) -> None:
    """
    Show the fight: who's in it, their condition, your queued action.

    Usage: combat
    """
    manager = _manager(ctx)
    encounter = manager.encounter_of(ctx.player) if manager else None
    if encounter is None:
        await ctx.session.send("You aren't in combat.")
        return

    lines = [f"\nRound {encounter.round_number + 1} — next beat in "
             f"{int(encounter.seconds_to_beat)}s (beat: {int(encounter.beat_seconds)}s)"]
    me = encounter.get(ctx.player.id)
    for participant in sorted(encounter.participants.values(),
                              key=lambda p: p.initiative, reverse=True):
        combatant = participant.combatant
        target = encounter.participants.get(participant.target_id or "")
        target_note = f" -> {target.obj.name}" if target else ""
        marker = "*" if participant.obj is ctx.player else " "
        lines.append(
            f" {marker}{participant.obj.name:20} "
            f"{_bar(combatant.hp, combatant.max_hp)} "
            f"{combatant.hp}/{combatant.max_hp}{target_note}"
        )
    if me is not None and me.queued is not None:
        maneuver = encounter.combat_system.ruleset.get_maneuver(me.queued.maneuver)
        target = encounter.participants.get(me.queued.target_id or "")
        target_name = target.obj.name if target else None
        lines.append(f"\nQueued: {me.queued.describe(maneuver, target_name)}")
    else:
        policy = ctx.player.db.get('combat_default') or 'repeat'
        lines.append(f"\nQueued: nothing (default policy: {policy})")
    lines.append("")
    await ctx.session.send("\n".join(lines))


async def cmd_pace(ctx: CommandContext) -> None:
    """
    Set your preferred combat beat in seconds. The slowest player in a
    fight sets its tempo.

    Usage: pace <seconds>

    Example:
        pace 15                (seconds per combat beat)
    """
    manager = _manager(ctx)
    if manager is None:
        await ctx.session.send("Combat is not enabled here.")
        return
    if not ctx.args:
        current = ctx.player.db.get('combat_beat') or manager.beat_default
        await ctx.session.send(f"Your combat pace is {int(float(current))}s per beat.")
        return
    try:
        seconds = float(ctx.args.strip())
    except ValueError:
        await ctx.session.send("Usage: pace <seconds>")
        return
    seconds = max(manager.beat_min, min(manager.beat_max, seconds))
    ctx.player.db.combat_beat = seconds
    encounter = manager.encounter_of(ctx.player)
    if encounter is not None:
        encounter._recompute_beat()
    await ctx.session.send(f"Combat pace set to {int(seconds)}s per beat.")


async def cmd_combat_default(ctx: CommandContext) -> None:
    """
    What you do when a beat fires with nothing queued.

    Usage: combatdefault <attack|defend|repeat|nothing>

    Example:
        combatdefault defend
    """
    choice = ctx.args.strip().lower()
    if choice not in ('attack', 'defend', 'repeat', 'nothing'):
        current = ctx.player.db.get('combat_default') or 'repeat'
        await ctx.session.send(
            f"Your combat default is '{current}'. "
            "Usage: combatdefault <attack|defend|repeat|nothing>"
        )
        return
    ctx.player.db.combat_default = choice
    await ctx.session.send(f"Combat default set to '{choice}'.")


async def cmd_wimpy(ctx: CommandContext) -> None:
    """
    Auto-flee reflex: below the given HP%, you flee — even over a
    queued action. (Sugar for a '!' strategy rule.)

    Usage: wimpy <percent> | wimpy off

    Example:
        wimpy 30               (auto-flee below 30% HP)
    """
    arg = ctx.args.strip().lower()
    rules = list(ctx.player.db.get('combat_strategy') or [])
    rules = [r for r in rules if not (str(r[0]).startswith('!me.hp_percent <'))]
    if arg == 'off':
        ctx.player.db.combat_strategy = rules
        await ctx.session.send("Wimpy off — you'll fight to the end.")
        return
    try:
        pct = int(arg)
        if not 1 <= pct <= 99:
            raise ValueError
    except ValueError:
        await ctx.session.send("Usage: wimpy <1-99> | wimpy off")
        return
    rules.insert(0, [f"!me.hp_percent < {pct}", "flee"])
    ctx.player.db.combat_strategy = rules
    await ctx.session.send(f"Wimpy set: you'll flee below {pct}% HP.")


async def cmd_firstaid(ctx: CommandContext) -> None:
    """
    Tend wounds with the First Aid skill (out of combat only). Can
    revive the unconscious.

    Usage: firstaid [target|me]

    Example:
        firstaid Alice
    """
    if ctx.player.has_tag('in_combat'):
        await ctx.session.send("Not while you're fighting!")
        return
    name = ctx.args.strip() or "me"
    if name.lower() in ('me', 'self'):
        target = ctx.player
    else:
        target = find_object(ctx, name, search_room=True, search_inventory=False)
    if not target:
        await ctx.session.send(f"You don't see '{name}' here.")
        return

    hp = int(target.db.get('hp') or 0)
    max_hp = int(target.db.get('max_hp') or 0)
    if max_hp <= 0:
        await ctx.session.send(f"{target.name} doesn't need first aid.")
        return
    if hp >= max_hp:
        await ctx.session.send(f"{target.name} is unhurt.")
        return

    result = check(ctx.player, 'first_aid')
    if not result.success:
        await ctx.session.send("You fumble with the dressings to no effect.")
        return
    healed = max(1, result.margin // 2 + 1)
    target.db.hp = min(max_hp, hp + healed)
    who = "your" if target is ctx.player else f"{target.name}'s"
    ctx.player.msg(f"You dress {who} wounds ({healed} HP).")
    if target is not ctx.player:
        target.msg(f"{ctx.player.name} dresses your wounds ({healed} HP).")
    if target.has_tag('unconscious') and int(target.db.get('hp') or 0) > 0:
        target.remove_tag('unconscious')
        target.msg("You come to, aching all over.")
        if target.location:
            target.location.msg_contents(
                f"{target.name} regains consciousness.", exclude=[target],
            )


async def cmd_wield(ctx: CommandContext) -> None:
    """
    Ready a carried weapon (one at a time).

    Usage: wield <weapon>

    Example:
        wield laser pistol
    """
    from realm.commands.base import find_object

    if not ctx.player or not ctx.args:
        await ctx.session.send("Wield what?")
        return
    weapon = find_object(ctx, ctx.args.strip(),
                         search_room=False, search_inventory=True)
    if weapon is None:
        await ctx.session.send(f"You aren't carrying '{ctx.args.strip()}'.")
        return

    from realm.core.events import fire_event
    wielding = await fire_event(ctx.player, weapon, "item:on_wield", gated=True)
    if wielding.blocked:
        ctx.player.msg(wielding.block_reason or f"You can't ready {weapon.name}.")
        return
    for item in ctx.player.contents:
        if item.has_tag('wielded') and item is not weapon:
            item.remove_tag('wielded')
            ctx.player.msg(f"You lower {item.name}.")
    weapon.add_tag('wielded')
    ctx.player.msg(f"You ready {weapon.name}.")
    if ctx.player.location:
        ctx.player.location.msg_contents(
            f"{ctx.player.name} readies {weapon.name}.", exclude=[ctx.player])


async def cmd_unwield(ctx: CommandContext) -> None:
    """
    Lower your readied weapon.

    Usage: unwield
    """
    from realm.core.events import fire_event
    for item in ctx.player.contents:
        if item.has_tag('wielded'):
            lowering = await fire_event(ctx.player, item, "item:on_unwield",
                                        gated=True)
            if lowering.blocked:
                ctx.player.msg(
                    lowering.block_reason or f"You can't lower {item.name}.")
                return
            item.remove_tag('wielded')
            await ctx.session.send(f"You lower {item.name}.")
            return
    await ctx.session.send("You have nothing readied.")


def register_combat_commands(dispatcher: CommandDispatcher) -> None:
    """Register combat commands with the dispatcher."""
    from functools import partial
    register = partial(dispatcher.register, category="combat")
    register("attack", cmd_attack, aliases=["kill", "att"],
                        help_text="Attack someone (starts combat)",
                        usage="attack <target>")
    register("queue", cmd_queue, aliases=["q"],
                        help_text="Choose your next combat action",
                        usage="queue <maneuver> [target]")
    register("defend", _make_shortcut("defend"),
                        help_text="Fight defensively next beat")
    register("flee", cmd_flee,
                        help_text="Try to escape combat",
                        usage="flee [direction]")
    register("combat", cmd_combat_status, aliases=["cstat"],
                        help_text="Show the current fight")
    register("pace", cmd_pace,
                        help_text="Set your combat beat (seconds)",
                        usage="pace <seconds>")
    register("combatdefault", cmd_combat_default,
                        help_text="Default action when a beat fires unqueued",
                        usage="combatdefault <attack|defend|repeat|nothing>")
    register("wimpy", cmd_wimpy,
                        help_text="Auto-flee below an HP percentage",
                        usage="wimpy <percent>|off")
    register("firstaid", cmd_firstaid, aliases=["aid"],
                        help_text="Tend wounds (First Aid skill)",
                        usage="firstaid [target]")
    register("points", cmd_points, aliases=["cp", "score"],
                        help_text="Show character points and skills")
    register("wield", cmd_wield, aliases=["ready", "draw"],
                        help_text="Ready a carried weapon",
                        usage="wield <weapon>")
    register("unwield", cmd_unwield, aliases=["lower", "sheathe"],
                        help_text="Lower your readied weapon",
                        usage="unwield")
    register("improve", cmd_improve,
                        help_text="Spend points to raise a skill",
                        usage="improve <skill>")


async def cmd_points(ctx: CommandContext) -> None:
    """
    Show your character points and trained skills.

    Usage: points
    """
    cp = int(ctx.player.db.get('character_points') or 0)
    lines = [f"\nCharacter points: {cp}"]
    skills = sorted(
        (key[6:], value) for key, value in ctx.player.db.all().items()
        if key.startswith('skill_')
    )
    if skills:
        lines.append("Skills:")
        lines.extend(f"  {name:20} {level}" for name, level in skills)
    lines.append(f"\nSpend with: improve <skill>  ({IMPROVE_COST} points per level)")
    lines.append("")
    await ctx.session.send("\n".join(lines))


IMPROVE_COST = 4  # character points per +1 skill level (GURPS-ish)


async def cmd_improve(ctx: CommandContext) -> None:
    """
    Spend character points to raise a skill by one level.

    Usage: improve <skill>       e.g. improve stealth

    Example:
        improve stealth        (4 CP per level under GURPS)
    """
    from realm.core.checks import skill_level

    skill = ctx.args.strip().lower().replace(' ', '_')
    if not skill:
        await ctx.session.send("Improve which skill? (see: points)")
        return
    if skill.startswith('skill_'):
        skill = skill[6:]

    cp = int(ctx.player.db.get('character_points') or 0)
    from realm.systems import get_game_system
    system = get_game_system()
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
