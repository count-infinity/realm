"""
An in-memory world store (no database).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.persistence.keyid import KeyidIndex

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

    async def save(self, obj: GameObject) -> None:
        self._cache[obj.id] = obj
        self._keyids.index(obj)

    async def delete(self, obj: GameObject) -> None:
        self._keyids.release(obj)
        self._cache.pop(obj.id, None)

    def add(self, obj: GameObject) -> None:
        self._cache[obj.id] = obj
        self._keyids.index(obj)

    def unregister(self, obj: GameObject) -> None:
        self._keyids.release(obj)
        self._cache.pop(obj.id, None)

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
        out = []
        for obj in self._cache.values():
            if tag is not None and not obj.has_tag(tag):
                continue
            if needle is not None and obj.name.lower() != needle:
                continue
            out.append(obj)
        return out


__all__ = ["MemoryStore"]
