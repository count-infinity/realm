"""
The ``crime`` feature.

Wanted flags for assaulting players, the guards who act on them, and
thieves.
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.crime.behaviors import PeacekeeperBehavior, StealBehavior, WantedBehavior
from realm.std.crime.crime import crime_observer

feature = Feature(
    'crime',
    requires=['rules', 'combat', 'economy', 'effects'],
    doc='Wanted flags for assaulting players, and the guards who act on them.',
)

# Assaulting or murdering a player flags the attacker wanted (a timed tag);
# peacekeeper guards attack the wanted.
feature.observer(crime_observer)
for _cls in (WantedBehavior, PeacekeeperBehavior, StealBehavior):
    feature.behavior(_cls)
