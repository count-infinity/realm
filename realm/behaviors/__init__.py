"""
Framework behavior kit: composable NPC and world behaviors.

Importing this package registers every behavior with the
BehaviorRegistry, so persisted worlds can rehydrate them by id.
"""

from realm.behaviors.caster import CasterBehavior
from realm.behaviors.decay import DecayBehavior
from realm.behaviors.effects import (
    DamageOverTimeBehavior,
    DispositionBoostBehavior,
    ModifierEffectBehavior,
    RegenerationBehavior,
    TimedEffectBehavior,
)
from realm.behaviors.npc import (
    PatrolBehavior,
    ScavengerBehavior,
    WatchfulBehavior,
)
from realm.behaviors.scripted import ScriptedBehavior
from realm.behaviors.shop import ShopkeeperBehavior
from realm.behaviors.spawner import RestockBehavior, SpawnerBehavior
from realm.behaviors.ticker import ScriptTickerBehavior
from realm.behaviors.zone_reset import ZoneResetBehavior

__all__ = [
    "CasterBehavior",
    "ScriptedBehavior",
    "ScriptTickerBehavior",
    "SpawnerBehavior",
    "RestockBehavior",
    "ZoneResetBehavior",
    "ShopkeeperBehavior",
    "WatchfulBehavior",
    "PatrolBehavior",
    "ScavengerBehavior",
    "DecayBehavior",
    "TimedEffectBehavior",
    "ModifierEffectBehavior",
    "DispositionBoostBehavior",
    "DamageOverTimeBehavior",
    "RegenerationBehavior",
]
