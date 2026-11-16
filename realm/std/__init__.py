"""
The built-in features.

A built-in feature is a package, ``realm/std/<name>/`` (a game system's is
``realm/games/<name>/``): ``feature.py`` declares it, and its other modules
(``actions.py``, ``verbs.py``, ``commands.py``, ...) are its parts. The
package ``__init__`` stays empty, so a part imports without loading the
feature. ``FEATURES`` names a built-in by its package name (``"talk"``).

``CLASSIC`` is every built-in feature: the default ``FEATURES`` and what a
game gets when it lists nothing. A game subtracts what it does not want:

    FEATURES = ["accounts", "basics", "talk", "movement", "look", "items", "building",
                "game"]
"""

CLASSIC: tuple[str, ...] = (
    "accounts", "basics", "talk", "movement", "look", "sight", "items", "building",
    "rules", "stealth", "combat", "effects", "vitals", "abilities", "economy", "social",
    "crime", "npc", "spawning", "instances", "wilderness", "tasks", "achievements",
    "gurps", "d20", "merc",
)

__all__ = ["CLASSIC"]
