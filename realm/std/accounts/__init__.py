"""The ``accounts`` feature. Its declarations are in ``feature.py``; this package
holds its parts, which import without loading the feature.

Public: ``account_of(character)`` and ``characters_of(account)``."""

from realm._exports import exports

__all__, __getattr__, __dir__ = exports(globals(), {
    "account_of": "realm.std.accounts.account:account_of",
    "characters_of": "realm.std.accounts.account:characters_of",
})
