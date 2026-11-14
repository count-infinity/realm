"""The ``sight`` feature. Its declarations are in ``feature.py``; this package
holds its parts, which import without loading the feature.

Its public names are in ``__all__`` (docs/reference/public-api.md);
they load on first use, so importing one part does not load the rest."""

from realm._exports import exports

__all__, __getattr__, __dir__ = exports(globals(), {
    "room_is_lit": "realm.std.sight.sight:room_is_lit",
    "can_see_room": "realm.std.sight.sight:can_see_room",
})
