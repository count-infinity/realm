"""
The ``rules`` feature.

The game system's checks and advancement in softcode and commands.
"""

from __future__ import annotations

from dataclasses import replace

from realm.core.pools import add_default
from realm.features import Feature
from realm.std.rules import softcode
from realm.std.rules.checks import Checks
from realm.std.rules.commands import cmd_improve, cmd_points, cmd_skills
from realm.std.rules.definitions import parse_class_def, parse_skill_def
from realm.std.rules.system import equipment_observer, reload_rules, resolve_game_system

feature = Feature(
    'rules',
    doc="The game system's checks and advancement in softcode and commands.",
)


@feature.on_reload
def _reload(world) -> None:
    """``@reload`` and imports pick up edited skill_def objects."""
    reload_rules()


# The rules data every game system reads: skill_def and class_def objects.
feature.def_kind("skill", "skill_def", parse=parse_skill_def)
feature.def_kind("class", "class_def", parse=parse_class_def)


@feature.on_install
def _install_game_system(world) -> None:
    """GAME_SYSTEM becomes ``world.rules``, and the world gets its checks
    (``services["checks"]``): resolved and defaulted through the game
    system, with every feature's ``check_modifier`` folded in. A bad path
    raises here, at boot."""
    checks = Checks()
    checks.modifier_providers.extend(world.check_modifiers)
    world.services["checks"] = checks
    world.rules = resolve_game_system(world.settings.game_system)
    for pool in world.rules.pools():
        add_default(world, replace(pool, owner=f"rules ({world.rules.system_id})"))
    reload_rules()

feature.command(
    'points',
    cmd_points,
    aliases=['cp', 'score'],
    category='combat',
    help_text='Show your character sheet',
)
feature.command(
    'skills',
    cmd_skills,
    aliases=['sk'],
    category='combat',
    help_text='List the skills you have trained',
)
feature.command(
    'improve',
    cmd_improve,
    category='combat',
    help_text='Spend points to raise a skill',
    usage='improve <skill>',
)

# Gear changes reach the rules package as events: on_wear/on_remove ->
# GameSystem.on_equipment_change (Merc AC).
feature.observer(equipment_observer)


@feature.traversal_gate(reason="skill",
                        attrs=["check_skill", "check_difficulty", "check_fail_msg"])
async def skill_gate(actor, exit_obj, direction, *, fleeing):
    """Skill-gated exits (fire escapes, ledges): ``db.check_skill`` names
    the skill, ``db.check_difficulty`` subtracts, ``db.check_fail_msg``
    replaces the failure line."""
    skill = exit_obj.db.get('check_skill') if exit_obj is not None else None
    if not skill:
        return None
    from realm.std.rules.checks import check
    difficulty = int(exit_obj.db.get('check_difficulty') or 0)
    if check(actor, str(skill), -difficulty).success:
        return None
    return (exit_obj.db.get('check_fail_msg')
            or f"You fail to make it {direction} ({skill} check).")


# --- softcode ------------------------------------------------------------------

feature.softfn(softcode.skill_check, group='Dice & skill checks', readonly=True)
feature.softfn(softcode.check_roll, group='Dice & skill checks', readonly=True)
feature.softfn(softcode.contest, group='Dice & skill checks', readonly=True)
feature.softfn(softcode.skill, group='Dice & skill checks', readonly=True, subject=True)
feature.softfn(softcode.check, group='Dice & skill checks', readonly=True, subject=True)
