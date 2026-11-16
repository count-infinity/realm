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
from realm.std.rules.progression import login_observer, training_sweep
from realm.std.rules.system import (
    RulesService,
    equipment_observer,
    reload_rules,
    resolve_game_system,
)
from realm.std.rules.training import TrainerBehavior, cmd_practice, cmd_study, cmd_train

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
    system, with every feature's ``check_modifier`` folded in; and
    ``services["rules"]``, the award filters other features append to. A
    bad path raises here, at boot."""
    checks = Checks()
    checks.modifier_providers.extend(world.check_modifiers)
    world.services["checks"] = checks
    world.services["rules"] = RulesService()
    world.rules = resolve_game_system(world.settings.game_system)
    for pool in world.rules.pools():
        add_default(world, replace(pool, owner=f"rules ({world.rules.system_id})"))
    reload_rules()

feature.command(
    'points',
    cmd_points,
    # `sc` stays the score now `scan` shares its first letters (ROM's order).
    aliases=['cp', 'score', 'sc'],
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

feature.command(
    'practice',
    cmd_practice,
    aliases=['prac'],
    category='combat',
    help_text='Practice a skill with a trainer',
    usage='practice [skill]',
)
feature.command(
    'train',
    cmd_train,
    category='combat',
    help_text='Raise a characteristic at a trainer',
    usage='train <stat>',
)
feature.command(
    'study',
    cmd_study,
    category='combat',
    help_text='Study a skill over real time',
    usage='study <skill> | study stop',
)
feature.behavior(TrainerBehavior)
feature.setting(
    "FOOD_FULL", 500,
    "The food a stomach holds (`GameSystem.stomach`), for a character of "
    "`NEEDS_BASE_WEIGHT`; CoffeeMud's.")
feature.setting(
    "WATER_FULL", 1000,
    "The water a stomach holds (`GameSystem.stomach`), for a character of "
    "`NEEDS_BASE_WEIGHT`; CoffeeMud's.")
feature.setting(
    "NEEDS_BASE_WEIGHT", 150,
    "The weight a stomach of `FOOD_FULL` and `WATER_FULL` belongs to: a "
    "character with a `weight` scales both (and its hunger and thirst) by "
    "`weight / NEEDS_BASE_WEIGHT`.")
feature.setting(
    "IDLE_TRAINING_MAX_HOURS", 0,
    "How many hours of time away an idle (`study`) skill banks at once. 0: unlimited.")
# Idle training catches up while a character plays (the reaper) and when it
# logs in (the observer, which also gives a character made before its game
# system declared food and water a full stomach).
feature.reaper(training_sweep)
feature.observer(login_observer)

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
