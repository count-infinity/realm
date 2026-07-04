"""
Framework behavior kit: composable NPC and world behaviors.

Importing this package registers every behavior with the
BehaviorRegistry, so persisted worlds can rehydrate them by id.
"""

from realm.behaviors.decay import DecayBehavior
from realm.behaviors.effects import (
    DamageOverTimeBehavior,
    RegenerationBehavior,
    TimedEffectBehavior,
)
from realm.behaviors.npc import PatrolBehavior, WatchfulBehavior

__all__ = [
    "WatchfulBehavior",
    "PatrolBehavior",
    "DecayBehavior",
    "TimedEffectBehavior",
    "DamageOverTimeBehavior",
    "RegenerationBehavior",
]
