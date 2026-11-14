"""
The ``rules`` feature.

The game system's checks and advancement in softcode and commands.
"""

from __future__ import annotations

from realm.commands.builtin.combat import cmd_improve, cmd_points
from realm.features import Feature
from realm.systems import equipment_observer

feature = Feature(
    'rules',
    doc="The game system's checks and advancement in softcode and commands.",
)

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
