"""
The built-in features.

``BUILTIN`` maps each built-in feature name to its declaration module.
A built-in feature is a package, ``realm/std/<name>/``: ``feature.py``
declares it, and its other modules (``actions.py``, ``verbs.py``, ...) are
its parts. The package ``__init__`` stays empty, so a part imports without
loading the feature.

``CLASSIC`` is every built-in feature: the default ``FEATURES`` and what a
game gets when it lists nothing. A game subtracts what it does not want:

    FEATURES = ["accounts", "basics", "talk", "movement", "look", "items", "building",
                "game"]
"""

BUILTIN: dict[str, str] = {
    "accounts": "realm.std.accounts.feature",
    "basics": "realm.std.basics.feature",
    "talk": "realm.std.talk.feature",
    "movement": "realm.std.movement.feature",
    "look": "realm.std.look.feature",
    "items": "realm.std.items.feature",
    "building": "realm.std.building.feature",
    "rules": "realm.std.rules.feature",
    "stealth": "realm.std.stealth.feature",
    "combat": "realm.std.combat.feature",
    "effects": "realm.std.effects.feature",
    "abilities": "realm.std.abilities.feature",
    "economy": "realm.std.economy.feature",
    "social": "realm.std.social.feature",
    "crime": "realm.std.crime.feature",
    "npc": "realm.std.npc.feature",
    "spawning": "realm.std.spawning.feature",
    "instances": "realm.std.instances.feature",
    "wilderness": "realm.std.wilderness.feature",
    "gurps": "realm.games.gurps.feature",
    "d20": "realm.games.d20.feature",
    "merc": "realm.games.merc.feature",
}

CLASSIC: tuple[str, ...] = tuple(BUILTIN)

__all__ = ["BUILTIN", "CLASSIC"]
