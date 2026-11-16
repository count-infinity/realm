"""
An in-memory world store (no database).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.defs import touched
from realm.core.objects import add_tag_listener
from realm.persistence.keyid import KeyidIndex
from realm.persistence.tagindex import TagIndex

if TYPE_CHECKING:
    from realm.core.objects import GameObject


class MemoryStore:
    """A world store that keeps everything in memory and saves nothing.

    Satisfies :class:`realm.persistence.store.Store`. The Simulator uses it;
    so can tools and tests that need a world without a database.
    """

    def __init__(self) -> None:
        self._cache: dict[str, GameObject] = {}
        self._keyids = KeyidIndex(self.get_cached)
        self._tags = TagIndex()
        add_tag_listener(self)

    def on_tag(self, obj: GameObject, tag: str, added: bool) -> None:
        """An object changed a tag in memory; keep the index current."""
        if obj.id in self._cache:
            self._tags.retag(obj, tag, added)

    def _enter(self, obj: GameObject) -> None:
        old = self._cache.get(obj.id)
        if old is not None:
            self._tags.remove(old)
        self._cache[obj.id] = obj
        self._tags.add(obj)
        touched(obj)

    def _leave(self, obj: GameObject) -> None:
        if self._cache.pop(obj.id, None) is not None:
            self._tags.remove(obj)
            touched(obj)

    async def save(self, obj: GameObject) -> None:
        self._enter(obj)
        self._keyids.index(obj)

    async def delete(self, obj: GameObject) -> None:
        self._keyids.release(obj)
        self._leave(obj)

    def add(self, obj: GameObject) -> None:
        self._enter(obj)
        self._keyids.index(obj)

    def register(self, obj: GameObject) -> None:
        """Put a new object in the store from sync code: the same name as
        ``PersistenceManager.register``, so either store takes it."""
        self.add(obj)

    def unregister(self, obj: GameObject) -> None:
        self._keyids.release(obj)
        self._leave(obj)

    def keyid_holder(self, keyid: str) -> GameObject | None:
        return self._keyids.holder(keyid)

    def claim_keyid(self, obj: GameObject, keyid: str) -> tuple[bool, str]:
        return self._keyids.claim(obj, keyid)

    def release_keyid(self, obj: GameObject) -> None:
        self._keyids.release(obj)

    def get_cached(self, obj_id: str) -> GameObject | None:
        return self._cache.get(obj_id)

    def all_cached(self) -> list[GameObject]:
        return list(self._cache.values())

    def find_cached(self, *, tag: str | None = None,
                    name: str | None = None) -> list[GameObject]:
        needle = name.lower() if name is not None else None
        if tag is not None:
            candidates = [self._cache[i] for i in self._tags.ids(tag) if i in self._cache]
        else:
            candidates = list(self._cache.values())
        return [obj for obj in candidates
                if (tag is None or obj.has_tag(tag))
                and (needle is None or obj.name.lower() == needle)]


__all__ = ["MemoryStore"]
