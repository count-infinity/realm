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
