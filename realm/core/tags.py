"""
Tag system for flexible object categorization.

Tags replace rigid type hierarchies with flexible labels.
Objects can have multiple tags like: room, zone:forest, indoor, npc, shopkeeper
"""

from __future__ import annotations

from collections.abc import Iterator


class TagSet:
    """
    A set of tags with support for namespaced tags (e.g., 'zone:forest').

    Tags are case-insensitive and stored lowercase.

    Examples:
        tags = TagSet(['room', 'zone:forest', 'indoor'])
        tags.add('dark')
        tags.has('room')  # True
        tags.has_prefix('zone')  # True
        tags.get_value('zone')  # 'forest'
    """

    __slots__ = ('_tags',)

    def __init__(self, tags: set[str] | list[str] | None = None):
        self._tags: set[str] = set()
        if tags:
            for tag in tags:
                self.add(tag)

    def add(self, tag: str) -> None:
        """Add a tag. Tags are normalized to lowercase."""
        self._tags.add(tag.lower().strip())

    def remove(self, tag: str) -> None:
        """Remove a tag if it exists."""
        self._tags.discard(tag.lower().strip())

    def has(self, tag: str) -> bool:
        """Check if a specific tag exists."""
        return tag.lower().strip() in self._tags




    def clear(self) -> None:
        """Remove all tags."""
        self._tags.clear()

    def copy(self) -> TagSet:
        """Return a copy of this TagSet."""
        return TagSet(self._tags.copy())

    def __contains__(self, tag: str) -> bool:
        return self.has(tag)

    def __iter__(self) -> Iterator[str]:
        return iter(self._tags)

    def __len__(self) -> int:
        return len(self._tags)

    def __repr__(self) -> str:
        return f"TagSet({sorted(self._tags)})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TagSet):
            return self._tags == other._tags
        return False

    def to_list(self) -> list[str]:
        """Return tags as a sorted list (for serialization)."""
        return sorted(self._tags)

    @classmethod
    def from_list(cls, tags: list[str]) -> TagSet:
        """Create a TagSet from a list (for deserialization)."""
        return cls(tags)
