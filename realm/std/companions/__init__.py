"""The ``companions`` feature. Its declarations are in ``feature.py``; this
package holds its parts, which import without loading the feature.

Public: ``master_of(obj)``, ``companions_of(character)``,
``set_master(npc, character | None)`` and ``ACCOMPANIED``, the action tag
of a move whose company comes along; other features reach the rest as
``world.services["companions"]``."""

from realm._exports import exports

__all__, __getattr__, __dir__ = exports(globals(), {
    "ACCOMPANIED": "realm.std.companions.companions:ACCOMPANIED",
    "master_of": "realm.std.companions.companions:master_of",
    "companions_of": "realm.std.companions.companions:companions_of",
    "set_master": "realm.std.companions.companions:set_master",
})
