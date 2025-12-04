"""
Core GameObject implementation.

Everything in REALM is a GameObject with behaviors attached.
No rigid type hierarchy - use tags for categorization.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from realm.core.tags import TagSet

if TYPE_CHECKING:
    from realm.core.behaviors import Behavior
    from realm.core.events import Event


class AttributeProxy:
    """
    Provides Evennia-style attribute access: obj.db.myattr = value

    Attributes are stored in a dictionary and automatically tracked
    for persistence (dirty tracking).
    """

    __slots__ = ('_attrs', '_owner', '_dirty')

    def __init__(self, attrs: dict[str, Any], owner: GameObject):
        object.__setattr__(self, '_attrs', attrs)
        object.__setattr__(self, '_owner', owner)
        object.__setattr__(self, '_dirty', set())

    def __getattr__(self, name: str) -> Any:
        attrs = object.__getattribute__(self, '_attrs')
        if name.startswith('_'):
            raise AttributeError(f"Attribute names cannot start with underscore: {name}")
        return attrs.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith('_'):
            raise AttributeError(f"Attribute names cannot start with underscore: {name}")
        attrs = object.__getattribute__(self, '_attrs')
        dirty = object.__getattribute__(self, '_dirty')
        owner = object.__getattribute__(self, '_owner')

        old_value = attrs.get(name)
        if old_value != value:
            attrs[name] = value
            dirty.add(name)
            owner._mark_dirty()

    def __delattr__(self, name: str) -> None:
        if name.startswith('_'):
            raise AttributeError(f"Attribute names cannot start with underscore: {name}")
        attrs = object.__getattribute__(self, '_attrs')
        dirty = object.__getattribute__(self, '_dirty')
        owner = object.__getattribute__(self, '_owner')

        if name in attrs:
            del attrs[name]
            dirty.add(name)
            owner._mark_dirty()

    def __contains__(self, name: str) -> bool:
        attrs = object.__getattribute__(self, '_attrs')
        return name in attrs

    def get(self, name: str, default: Any = None) -> Any:
        """Get an attribute with a default value."""
        attrs = object.__getattribute__(self, '_attrs')
        return attrs.get(name, default)

    def set(self, name: str, value: Any) -> None:
        """Set an attribute (alternative to dot notation)."""
        self.__setattr__(name, value)

    def delete(self, name: str) -> None:
        """Delete an attribute (alternative to del)."""
        self.__delattr__(name)

    def all(self) -> dict[str, Any]:
        """Return all attributes as a dictionary."""
        attrs = object.__getattribute__(self, '_attrs')
        return dict(attrs)

    def clear_dirty(self) -> set[str]:
        """Clear and return the set of dirty attribute names."""
        dirty = object.__getattribute__(self, '_dirty')
        result = dirty.copy()
        dirty.clear()
        return result


class GameObject:
    """
    Base class for all game objects.

    Everything in REALM is a GameObject with behaviors attached.
    Tags provide flexible categorization (room, player, npc, zone:forest, etc).

    Attributes:
        id: Unique identifier (UUID string)
        name: Display name
        description: Object description
        location: Container object (room, inventory, etc.)
        contents: List of contained objects
        parent: Explicit @parent for attribute inheritance
        owner: Who owns this object
        tags: Flexible categorization via TagSet
        behaviors: List of attached Behavior instances
        locks: Permission locks (to be implemented)
    """

    __slots__ = (
        'id',
        'name',
        'description',
        '_location',
        '_contents',
        'parent',
        'owner',
        'tags',
        '_behaviors',
        'locks',
        '_attrs',
        '_db',
        '_dirty',
    )

    def __init__(
        self,
        name: str,
        *,
        id: str | None = None,
        description: str = "",
        location: GameObject | None = None,
        parent: GameObject | None = None,
        owner: GameObject | None = None,
        tags: set[str] | list[str] | None = None,
    ):
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self._location: GameObject | None = None
        self._contents: list[GameObject] = []
        self.parent = parent
        self.owner = owner
        self.tags = TagSet(tags)
        self._behaviors: list[Behavior] = []
        self.locks: dict[str, Any] = {}  # Lock type -> lock expression
        self._attrs: dict[str, Any] = {}
        self._db: AttributeProxy | None = None
        self._dirty = False

        # Set location through property to maintain contents lists
        if location is not None:
            self.location = location

    @property
    def db(self) -> AttributeProxy:
        """Evennia-style attribute access."""
        if self._db is None:
            self._db = AttributeProxy(self._attrs, self)
        return self._db

    @property
    def location(self) -> GameObject | None:
        """The container this object is in."""
        return self._location

    @location.setter
    def location(self, new_location: GameObject | None) -> None:
        """Move this object to a new location."""
        old_location = self._location

        # Remove from old location's contents
        if old_location is not None and self in old_location._contents:
            old_location._contents.remove(self)

        # Add to new location's contents
        if new_location is not None and self not in new_location._contents:
            new_location._contents.append(self)

        self._location = new_location
        self._mark_dirty()

    @property
    def contents(self) -> list[GameObject]:
        """Objects contained in this object (read-only view)."""
        return list(self._contents)

    def _mark_dirty(self) -> None:
        """Mark this object as needing persistence."""
        self._dirty = True

    def is_dirty(self) -> bool:
        """Check if this object needs to be saved."""
        return self._dirty

    def clear_dirty(self) -> None:
        """Clear the dirty flag after saving."""
        self._dirty = False
        if self._db is not None:
            self._db.clear_dirty()

    # --- Tag shortcuts ---

    def has_tag(self, tag: str) -> bool:
        """Check if this object has a specific tag."""
        return self.tags.has(tag)

    def add_tag(self, tag: str) -> None:
        """Add a tag to this object."""
        self.tags.add(tag)
        self._mark_dirty()

    def remove_tag(self, tag: str) -> None:
        """Remove a tag from this object."""
        self.tags.remove(tag)
        self._mark_dirty()

    # --- Type tag shortcuts ---

    @property
    def is_room(self) -> bool:
        return self.has_tag('room')

    @property
    def is_player(self) -> bool:
        return self.has_tag('player')

    @property
    def is_exit(self) -> bool:
        return self.has_tag('exit')

    @property
    def is_thing(self) -> bool:
        return self.has_tag('thing')

    # --- Behavior management ---

    def add_behavior(self, behavior: Behavior) -> None:
        """Attach a behavior to this object."""
        if behavior not in self._behaviors:
            self._behaviors.append(behavior)
            behavior.attach(self)
            self._mark_dirty()

    def remove_behavior(self, behavior: Behavior) -> None:
        """Detach a behavior from this object."""
        if behavior in self._behaviors:
            behavior.detach(self)
            self._behaviors.remove(behavior)
            self._mark_dirty()

    def get_behaviors(self) -> list[Behavior]:
        """Get all attached behaviors."""
        return list(self._behaviors)

    def get_behavior(self, behavior_type: type) -> Behavior | None:
        """Get the first behavior of a specific type."""
        for b in self._behaviors:
            if isinstance(b, behavior_type):
                return b
        return None

    # --- Event handling (two-phase) ---

    async def on_event_validate(self, event: Event) -> bool:
        """
        Phase 1: Validation. Any behavior can veto by returning False.
        Called before the event is executed.
        """
        for behavior in self._behaviors:
            if not await behavior.validate_event(self, event):
                return False
        return True

    async def on_event_execute(self, event: Event) -> None:
        """
        Phase 2: Execution. Called after validation passes.
        All behaviors get to react to the event.
        """
        for behavior in self._behaviors:
            await behavior.handle_event(self, event)

    # --- Attribute inheritance ---

    def resolve_attr(self, name: str, default: Any = None) -> Any:
        """
        Resolve an attribute with inheritance.

        Lookup order:
        1. This object's attributes
        2. Walk @parent chain
        3. (Future: Type ancestors)
        """
        # Check this object
        if name in self._attrs:
            return self._attrs[name]

        # Walk parent chain
        current = self.parent
        visited: set[str] = {self.id}  # Prevent infinite loops

        while current is not None and current.id not in visited:
            visited.add(current.id)
            if name in current._attrs:
                return current._attrs[name]
            current = current.parent

        return default

    # --- Utility methods ---

    def msg(self, text: str) -> None:
        """
        Send a message to this object.

        For players, this sends to their session.
        For other objects, this may trigger listen behaviors.

        Note: Actual implementation depends on session management.
        This is a placeholder that subclasses/behaviors can override.
        """
        # Default implementation does nothing
        # Player objects will override to send to their session
        pass

    def __repr__(self) -> str:
        return f"<GameObject {self.id[:8]}... '{self.name}' tags={self.tags}>"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GameObject):
            return self.id == other.id
        return False

    def __hash__(self) -> int:
        return hash(self.id)
