"""The ``combat`` feature. Its declarations are in ``feature.py``; this package
holds its parts, which import without loading the feature: the abstract
``Ruleset`` (``ruleset.py``; the built-in rulesets live with their games in
``realm/games/<name>/ruleset.py``), the ``CombatSystem`` and ruleset registry
(``system.py``), encounters and their ``CombatManager``, combatants,
maneuvers, strategies, damage and the combat AI behaviors."""
