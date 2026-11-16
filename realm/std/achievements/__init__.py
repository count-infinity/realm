"""The ``achievements`` feature. Its declarations are in ``feature.py``; this
package holds its parts, which import without loading the feature.

It has no public names: a game uses it by listing it in ``FEATURES`` and
calling the softcode functions ``grant_achievement`` and
``has_achievement``."""

__all__: list[str] = []
