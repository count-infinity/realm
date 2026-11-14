"""The ``combat`` feature. Its declarations are in ``feature.py``; this package
holds its parts, which import without loading the feature: the abstract
``Ruleset`` (``ruleset.py``; the built-in rulesets live with their games in
``realm/games/<name>/ruleset.py``), the ``CombatSystem`` and ruleset registry
(``system.py``), encounters and their ``CombatManager``, combatants,
maneuvers, strategies, damage and the combat AI behaviors.

Its public names are in ``__all__`` (docs/reference/public-api.md);
they load on first use, so importing one part does not load the rest."""

from realm._exports import exports

__all__, __getattr__, __dir__ = exports(globals(), {
    "Ruleset": "realm.std.combat.ruleset:Ruleset",
    "AttackResult": "realm.std.combat.ruleset:AttackResult",
    "DamageResult": "realm.std.combat.ruleset:DamageResult",
    "RollResult": "realm.std.combat.ruleset:RollResult",
    "DamageType": "realm.std.combat.ruleset:DamageType",
    "Combatant": "realm.std.combat.combatant:Combatant",
    "deal_damage": "realm.std.combat.damage:deal_damage",
    "CombatView": "realm.std.combat.strategy:CombatView",
    "CombatAction": "realm.std.combat.actions:CombatAction",
})
