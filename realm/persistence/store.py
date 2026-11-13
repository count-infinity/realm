"""
The store protocol: what engine code may call on a world store.

``PersistenceManager`` (SQLite) and ``MemoryStore`` (tests, tools) both
satisfy it. Engine code types a store parameter as ``Store`` and calls only
these members.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from realm.core.objects import GameObject


@runtime_checkable
class Store(Protocol):
    """The live object cache plus the write path."""

    def get_cached(self, obj_id: str) -> GameObject | None:
        """A loaded object by id, or None."""
        ...

    def all_cached(self) -> list[GameObject]:
        """Every loaded object."""
        ...

    def find_cached(self, *, tag: str | None = None,
                    name: str | None = None) -> list[GameObject]:
        """Loaded objects with ``tag`` and/or this exact name (case-insensitive)."""
        ...

    async def save(self, obj: GameObject) -> None:
        """Register ``obj`` and persist it."""
        ...

    async def delete(self, obj: GameObject) -> None:
        """Forget ``obj`` and remove it from storage."""
        ...

    def keyid_holder(self, keyid: str) -> GameObject | None:
        """The object holding this friendly keyid, or None."""
        ...

    def claim_keyid(self, obj: GameObject, keyid: str) -> tuple[bool, str]:
        """Bind ``keyid`` to ``obj``. Returns ``(ok, reason)``."""
        ...

    def release_keyid(self, obj: GameObject) -> None:
        """Free ``obj``'s keyid."""
        ...


__all__ = ["Store"]
