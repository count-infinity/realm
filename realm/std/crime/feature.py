"""
The ``crime`` feature.

Wanted flags for assaulting players, and the guards who act on them.
"""

from __future__ import annotations

from realm.behaviors.effects import WantedBehavior
from realm.behaviors.npc import StealBehavior
from realm.combat.behaviors import PeacekeeperBehavior
from realm.features import Feature
from realm.systems.crime import crime_observer

feature = Feature(
    'crime',
    requires=['combat', 'economy'],
    doc='Wanted flags for assaulting players, and the guards who act on them.',
)

# Assaulting or murdering a player flags the attacker wanted (a timed tag);
# peacekeeper guards attack the wanted.
feature.observer(crime_observer)
for _cls in (WantedBehavior, PeacekeeperBehavior, StealBehavior):
    feature.behavior(_cls)
