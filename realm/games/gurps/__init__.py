"""The ``gurps`` game: ``system.py`` (the GameSystem), ``ruleset.py`` (its combat
ruleset) and ``feature.py`` (the feature that declares the ruleset).

Its public names are in ``__all__`` (docs/reference/public-api.md);
they load on first use."""

from realm._exports import exports

__all__, __getattr__, __dir__ = exports(globals(), {
    "GurpsSystem": "realm.games.gurps.system:GurpsSystem",
    "TEMPLATES": "realm.games.gurps.system:TEMPLATES",
    "GURPSRuleset": "realm.games.gurps.ruleset:GURPSRuleset",
})
