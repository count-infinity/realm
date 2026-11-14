"""
The ``spawning`` feature.

Spawners, restock, population control and zone resets.
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.spawning.spawner import PopulationBehavior, RestockBehavior, SpawnerBehavior
from realm.std.spawning.zone_reset import ZoneResetBehavior

feature = Feature(
    'spawning',
    doc='Spawners, restock, population control and zone resets.',
)

for _cls in (SpawnerBehavior, RestockBehavior, PopulationBehavior, ZoneResetBehavior):
    feature.behavior(_cls)
