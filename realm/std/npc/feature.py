"""
The ``npc`` feature.

NPC behaviors: watchful, patrol, scavenger, wandering, guard, decay.
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.npc.behaviors import (
    GuardBehavior,
    PatrolBehavior,
    ScavengerBehavior,
    WanderingBehavior,
)
from realm.std.npc.decay import DecayBehavior

feature = Feature(
    'npc',
    doc='NPC behaviors: patrol, scavenger, wandering, guard, decay.',
)

for _cls in (PatrolBehavior, ScavengerBehavior, WanderingBehavior, GuardBehavior,
             DecayBehavior):
    feature.behavior(_cls)
