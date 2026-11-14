"""
The ``spawning`` feature.

Spawners, restock, population control and zone resets.
"""

from __future__ import annotations

from realm.behaviors.spawner import PopulationBehavior, RestockBehavior, SpawnerBehavior
from realm.behaviors.zone_reset import ZoneResetBehavior
from realm.features import Feature

feature = Feature(
    'spawning',
    doc='Spawners, restock, population control and zone resets.',
)

for _cls in (SpawnerBehavior, RestockBehavior, PopulationBehavior, ZoneResetBehavior):
    feature.behavior(_cls)
