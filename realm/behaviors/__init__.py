"""
Framework behavior kit: composable NPC and world behaviors.

Importing this package registers every behavior with the
BehaviorRegistry, so persisted worlds can rehydrate them by id.
"""

import realm.combat.behaviors  # noqa: F401 — register the combat AI behaviors
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
    StealBehavior,
    WatchfulBehavior,
)
from realm.behaviors.scripted import ScriptedBehavior
from realm.behaviors.shop import ShopkeeperBehavior
from realm.behaviors.spawner import (
    PopulationBehavior,
    RestockBehavior,
    SpawnerBehavior,
)
from realm.behaviors.ticker import ScriptTickerBehavior
from realm.behaviors.zone_reset import ZoneResetBehavior

__all__ = [
    "CasterBehavior",
    "ScriptedBehavior",
    "ScriptTickerBehavior",
    "SpawnerBehavior",
    "RestockBehavior",
    "PopulationBehavior",
    "ZoneResetBehavior",
    "ShopkeeperBehavior",
    "WatchfulBehavior",
    "PatrolBehavior",
    "ScavengerBehavior",
    "StealBehavior",
    "DecayBehavior",
    "TimedEffectBehavior",
    "ModifierEffectBehavior",
    "DispositionBoostBehavior",
    "DamageOverTimeBehavior",
    "RegenerationBehavior",
]
