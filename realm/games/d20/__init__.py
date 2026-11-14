"""The ``d20`` game: ``system.py`` (the GameSystem), ``ruleset.py`` (its combat
ruleset) and ``feature.py`` (the feature that declares the ruleset).

Its public names are in ``__all__`` (docs/reference/public-api.md);
they load on first use."""

from realm._exports import exports

__all__, __getattr__, __dir__ = exports(globals(), {
    "D20System": "realm.games.d20.system:D20System",
    "CLASSES": "realm.games.d20.system:CLASSES",
    "D20Ruleset": "realm.games.d20.ruleset:D20Ruleset",
})
