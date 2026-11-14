"""
The ``npc`` feature.

NPC behaviors: watchful, patrol, scavenger, wandering, guard, decay.
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.combat.behaviors import GuardBehavior, WanderingBehavior
from realm.std.npc.behaviors import PatrolBehavior, ScavengerBehavior, WatchfulBehavior
from realm.std.npc.decay import DecayBehavior

feature = Feature(
    'npc',
    doc='NPC behaviors: watchful, patrol, scavenger, wandering, guard, decay.',
)

for _cls in (WatchfulBehavior, PatrolBehavior, ScavengerBehavior, WanderingBehavior,
             GuardBehavior, DecayBehavior):
    feature.behavior(_cls)
