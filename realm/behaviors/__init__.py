"""
Framework behavior kit: composable NPC and world behaviors.

Importing this package registers every behavior with the
BehaviorRegistry, so persisted worlds can rehydrate them by id.
"""

from realm.behaviors.decay import DecayBehavior
from realm.behaviors.effects import (
    DamageOverTimeBehavior,
    DispositionBoostBehavior,
    ModifierEffectBehavior,
    RegenerationBehavior,
    TimedEffectBehavior,
)
from realm.behaviors.npc import PatrolBehavior, WatchfulBehavior
from realm.behaviors.shop import ShopkeeperBehavior
from realm.behaviors.spawner import SpawnerBehavior
from realm.behaviors.ticker import ScriptTickerBehavior
from realm.behaviors.zone_reset import ZoneResetBehavior

__all__ = [
    "ScriptTickerBehavior",
    "SpawnerBehavior",
    "ZoneResetBehavior",
    "ShopkeeperBehavior",
    "WatchfulBehavior",
    "PatrolBehavior",
    "DecayBehavior",
    "TimedEffectBehavior",
    "ModifierEffectBehavior",
    "DispositionBoostBehavior",
    "DamageOverTimeBehavior",
    "RegenerationBehavior",
]
