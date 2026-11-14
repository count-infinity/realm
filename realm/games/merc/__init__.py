"""The ``merc`` game: ``system.py`` (the GameSystem), ``ruleset.py`` (its combat
ruleset) and ``feature.py`` (the feature that declares the ruleset).

Its public names are in ``__all__`` (docs/reference/public-api.md);
they load on first use."""

from realm._exports import exports

__all__, __getattr__, __dir__ = exports(globals(), {
    "MercSystem": "realm.games.merc.system:MercSystem",
    "MERC_CLASSES": "realm.games.merc.system:MERC_CLASSES",
    "MercRuleset": "realm.games.merc.ruleset:MercRuleset",
})
