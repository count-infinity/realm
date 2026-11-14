"""
REALM - Real-time Event-Action Layered MUD Framework

A Python MUD framework combining combat depth, builder empowerment,
and low barrier to entry.

The names in ``__all__`` are the public API a game imports
(``from realm import Feature, GameObject``); see
docs/reference/public-api.md. They load on first use, so ``import realm``
loads no feature. Rules and combat types live in their features:
``realm.std.rules`` and ``realm.std.combat``.
"""

from realm._exports import exports

__version__ = "0.1.0"

__all__, __getattr__, __dir__ = exports(globals(), {
    "Feature": "realm.features:Feature",
    "FeatureError": "realm.features:FeatureError",
    "CLASSIC": "realm.std:CLASSIC",
    "GameObject": "realm.core.objects:GameObject",
    "Action": "realm.core.propagation:Action",
    "propagate": "realm.core.propagation:propagate",
    "fire_event": "realm.core.events:fire_event",
    "ActionType": "realm.core.action_types:ActionType",
    "Behavior": "realm.core.behaviors:Behavior",
    "CommandContext": "realm.commands.dispatcher:CommandContext",
    "Pool": "realm.core.pools:Pool",
    "pools": "realm.core.pools",
    "ops": "realm.core.ops",
    "OpError": "realm.core.ops:OpError",
    "World": "realm.core.world:World",
    "get_world": "realm.core.world:get_world",
    "check_lock": "realm.permissions:check_lock",
    "controls": "realm.permissions:controls",
    "has_entitlement": "realm.permissions:has_entitlement",
    "Settings": "realm.config.loader:Settings",
    "softcode_function": "realm.scripting.registry:softcode_function",
    "dice": "realm.core.dice",
    "defs": "realm.core.defs",
    "import_objects": "realm.persistence.worldio:import_objects",
    "import_pack": "realm.packs:import_pack",
    "Store": "realm.persistence.store:Store",
})
