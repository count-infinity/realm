"""
The ``rules`` feature.

The game system's checks and advancement in softcode and commands.
"""

from __future__ import annotations

from realm.commands.builtin.combat import cmd_improve, cmd_points
from realm.features import Feature
from realm.std.rules import softcode
from realm.std.rules.system import equipment_observer, reload_rules, resolve_game_system

feature = Feature(
    'rules',
    doc="The game system's checks and advancement in softcode and commands.",
)


@feature.on_install
def _install_game_system(world) -> None:
    """GAME_SYSTEM becomes ``world.rules``; the world's checks resolve and
    default skills through it. A bad path raises here, at boot."""
    world.rules = resolve_game_system(world.settings.game_system)
    reload_rules()

feature.command(
    'points',
    cmd_points,
    aliases=['cp', 'score'],
    category='combat',
    help_text='Show character points and skills',
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
async def skill_gate(actor, exit_obj, direction):
    """Skill-gated exits (fire escapes, ledges): ``db.check_skill`` names
    the skill, ``db.check_difficulty`` subtracts, ``db.check_fail_msg``
    replaces the failure line."""
    skill = exit_obj.db.get('check_skill')
    if not skill:
        return None
    from realm.core.checks import check
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
