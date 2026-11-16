"""The ``vitals`` feature. Its declarations are in ``feature.py``; this package
holds its parts, which import without loading the feature.

It has no public names: a game uses it by listing it in ``FEATURES``, and
other features reach it as ``world.services["vitals"]`` (a
:class:`realm.std.vitals.regen.Vitals`)."""

__all__: list[str] = []
