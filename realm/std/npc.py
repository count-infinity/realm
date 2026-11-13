"""
The ``npc`` feature.

NPC behaviors: watchful, patrol, scavenger, wandering, guard, decay.
"""

from __future__ import annotations

from realm.behaviors.decay import DecayBehavior
from realm.behaviors.npc import PatrolBehavior, ScavengerBehavior, WatchfulBehavior
from realm.combat.behaviors import GuardBehavior, WanderingBehavior
from realm.features import Feature

feature = Feature(
    'npc',
    doc='NPC behaviors: watchful, patrol, scavenger, wandering, guard, decay.',
)

for _cls in (WatchfulBehavior, PatrolBehavior, ScavengerBehavior, WanderingBehavior,
             GuardBehavior, DecayBehavior):
    feature.behavior(_cls)
