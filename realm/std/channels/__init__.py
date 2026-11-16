"""The ``channels`` feature. Its declarations are in ``feature.py``; this
package holds its parts, which import without loading the feature.

It has no public names: a game uses it by listing it in ``FEATURES`` and
defining channels as ``channel_def`` objects (the ``channels`` pack ships
gossip, newbie and immtalk)."""

__all__: list[str] = []
