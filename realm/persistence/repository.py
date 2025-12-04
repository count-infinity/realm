"""
Simple in-memory object repository.

Used for testing and development without a database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject


class GameObjectRepository:
    """
    In-memory repository for game objects.

    Provides a simple interface for storing and retrieving objects
    without database overhead. Useful for testing and demos.
    """

    def __init__(self):
        """Initialize empty repository."""
        self._objects: dict[str, GameObject] = {}

    async def save(self, obj: GameObject) -> None:
        """Save an object to the repository."""
        self._objects[obj.id] = obj

    async def load(self, obj_id: str) -> GameObject | None:
        """Load an object by ID."""
        return self._objects.get(obj_id)

    async def delete(self, obj_id: str) -> bool:
        """Delete an object by ID. Returns True if deleted."""
        if obj_id in self._objects:
            del self._objects[obj_id]
            return True
        return False

    async def exists(self, obj_id: str) -> bool:
        """Check if an object exists."""
        return obj_id in self._objects

    def all(self) -> list[GameObject]:
        """Get all objects."""
        return list(self._objects.values())

    def find_by_tag(self, tag: str) -> list[GameObject]:
        """Find all objects with a given tag."""
        return [obj for obj in self._objects.values() if obj.has_tag(tag)]

    def find_by_name(self, name: str) -> list[GameObject]:
        """Find all objects with a given name (case-insensitive)."""
        name_lower = name.lower()
        return [
            obj for obj in self._objects.values()
            if obj.name.lower() == name_lower
        ]

    def clear(self) -> None:
        """Clear all objects from the repository."""
        self._objects.clear()
