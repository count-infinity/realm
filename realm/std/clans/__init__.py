"""The ``clans`` feature. Its declarations are in ``feature.py``; this
package holds its parts, which import without loading the feature.

Public: ``clan_of(obj, category="")``, ``clans_of(obj)``,
``find_clan(name)`` and ``has_power(clan, obj, power)``; other features
reach them as ``world.services["clans"]``."""

from realm._exports import exports

__all__, __getattr__, __dir__ = exports(globals(), {
    "clan_of": "realm.std.clans.clans:clan_of",
    "clans_of": "realm.std.clans.clans:clans_of",
    "find_clan": "realm.std.clans.clans:find_clan",
    "has_power": "realm.std.clans.clans:has_power",
})
