"""
A tag -> object-id index for a store's live cache.

``find_cached(tag=...)`` reads it instead of scanning every object. The
store adds and removes objects as they enter and leave its cache, and
registers itself with ``realm.core.objects`` so an in-memory ``add_tag`` /
``remove_tag`` keeps the index current before any save.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject


class TagIndex:
    """``tag -> {object id}`` for the objects one store holds."""

    __slots__ = ('_ids',)

    def __init__(self) -> None:
        # dicts used as insertion-ordered sets: stable, repeatable results.
        self._ids: dict[str, dict[str, None]] = {}

    def add(self, obj: GameObject) -> None:
        for tag in obj.tags:
            self._ids.setdefault(tag, {})[obj.id] = None

    def remove(self, obj: GameObject) -> None:
        for tag in obj.tags:
            ids = self._ids.get(tag)
            if ids is not None:
                ids.pop(obj.id, None)

    def retag(self, obj: GameObject, tag: str, added: bool) -> None:
        tag = tag.lower().strip()
        if added:
            self._ids.setdefault(tag, {})[obj.id] = None
        else:
            ids = self._ids.get(tag)
            if ids is not None:
                ids.pop(obj.id, None)

    def ids(self, tag: str) -> list[str]:
        return list(self._ids.get(tag.lower().strip(), ()))

    def clear(self) -> None:
        self._ids.clear()


__all__ = ["TagIndex"]
