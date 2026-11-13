"""
The built-in features.

``BUILTIN`` maps each built-in feature name to its declaration module.
``CLASSIC`` is every built-in feature: the default ``FEATURES`` and what a
game gets when it lists nothing. A game subtracts what it does not want:

    FEATURES = ["basics", "talk", "movement", "look", "items", "building", "game"]
"""

BUILTIN: dict[str, str] = {
    "basics": "realm.std.basics",
    "talk": "realm.std.talk",
    "movement": "realm.std.movement",
    "look": "realm.std.look",
    "items": "realm.std.items",
    "building": "realm.std.building",
    "rules": "realm.std.rules",
    "stealth": "realm.std.stealth",
    "combat": "realm.std.combat",
    "effects": "realm.std.effects",
    "abilities": "realm.std.abilities",
    "economy": "realm.std.economy",
    "social": "realm.std.social",
    "crime": "realm.std.crime",
    "npc": "realm.std.npc",
    "spawning": "realm.std.spawning",
    "instances": "realm.std.instances",
    "wilderness": "realm.std.wilderness",
    "gurps": "realm.games.gurps",
    "d20": "realm.games.d20",
    "merc": "realm.games.merc",
}

CLASSIC: tuple[str, ...] = tuple(BUILTIN)

__all__ = ["BUILTIN", "CLASSIC"]
