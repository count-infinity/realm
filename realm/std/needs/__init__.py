"""The ``needs`` feature. Its declarations are in ``feature.py``; this
package holds its parts, which import without loading the feature.

It has no public names: a game uses it by listing it in ``FEATURES`` (and
giving characters ``food``, ``water`` or ``fatigue`` pools, as Merc does),
and other features reach it as ``world.services["needs"]``."""

__all__: list[str] = []
