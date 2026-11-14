"""The ``rules`` feature. Its declarations are in ``feature.py``; this package
holds its parts, which import without loading the feature.

Its public names are in ``__all__`` (docs/reference/public-api.md);
they load on first use, so importing one part does not load the rest."""

from realm._exports import exports

__all__, __getattr__, __dir__ = exports(globals(), {
    "GameSystem": "realm.std.rules.system:GameSystem",
    "PointBuyMixin": "realm.std.rules.system:PointBuyMixin",
    "ChargenStep": "realm.std.rules.system:ChargenStep",
    "ChoiceStep": "realm.std.rules.system:ChoiceStep",
    "check": "realm.std.rules.checks:check",
    "CheckResult": "realm.std.rules.checks:CheckResult",
    "default_resolver": "realm.std.rules.checks:default_resolver",
    "define_skill": "realm.std.rules.definitions:define_skill",
    "define_class": "realm.std.rules.definitions:define_class",
})
