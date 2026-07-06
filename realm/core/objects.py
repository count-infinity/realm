"""
Core GameObject implementation.

Everything in REALM is a GameObject with behaviors attached.
No rigid type hierarchy - use tags for categorization.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from realm.core.tags import TagSet

if TYPE_CHECKING:
    from realm.core.behaviors import Behavior
    from realm.core.propagation import Action


class AttributeProxy:
    """
    Provides Evennia-style attribute access: obj.db.myattr = value

    Attributes are stored in a dictionary and automatically tracked
    for persistence (dirty tracking).
    """

    __slots__ = ('_attrs', '_owner')

    def __init__(self, attrs: dict[str, Any], owner: GameObject):
        object.__setattr__(self, '_attrs', attrs)
        object.__setattr__(self, '_owner', owner)

    def __getattr__(self, name: str) -> Any:
        attrs = object.__getattribute__(self, '_attrs')
        if name.startswith('_'):
            raise AttributeError(f"Attribute names cannot start with underscore: {name}")
        return attrs.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith('_'):
            raise AttributeError(f"Attribute names cannot start with underscore: {name}")
        attrs = object.__getattribute__(self, '_attrs')
        owner = object.__getattribute__(self, '_owner')

        old_value = attrs.get(name)
        if old_value != value:
            attrs[name] = value
            owner._mark_dirty()

    def __delattr__(self, name: str) -> None:
        if name.startswith('_'):
            raise AttributeError(f"Attribute names cannot start with underscore: {name}")
        attrs = object.__getattribute__(self, '_attrs')
        owner = object.__getattribute__(self, '_owner')

        if name in attrs:
            del attrs[name]
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
        '__weakref__',
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
        '_msg_handler',
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
        self._msg_handler: Callable[[str], None] | None = None

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
            from realm.core.behaviors import register_behavior_owner
            register_behavior_owner(self)

    def remove_behavior(self, behavior: Behavior) -> None:
        """Detach a behavior from this object."""
        if behavior in self._behaviors:
            behavior.detach(self)
            self._behaviors.remove(behavior)
            self._mark_dirty()
            if not self._behaviors:
                from realm.core.behaviors import unregister_behavior_owner
                unregister_behavior_owner(self)

    def get_behaviors(self) -> list[Behavior]:
        """Get all attached behaviors."""
        return list(self._behaviors)

    def get_behavior(self, behavior_type: type) -> Behavior | None:
        """Get the first behavior of a specific type."""
        for b in self._behaviors:
            if isinstance(b, behavior_type):
                return b
        return None

    # --- Action propagation visitors ---
    #
    # The propagation engine calls these on each object in the chain.
    # The default implementations walk this object's behaviors. Subclasses
    # override to also walk child objects (a Character walks equipment,
    # a Pet walks its rider, etc.) — call super() first to run own behaviors.

    async def visit_check(self, action: Action) -> None:
        """
        Permission pass: enforce locks, then own hook, then behaviors.

        Locks run first so behaviors observe lock-blocked attempts (both
        propagation passes always complete). Imported lazily so core stays
        importable on its own.
        """
        from realm.permissions.locks import enforce_lock_on_action
        enforce_lock_on_action(self, action)
        self.at_action_check(action)
        for behavior in self._behaviors:
            await behavior.on_check(self, action)

    async def visit_react(self, action: Action) -> None:
        """Reaction pass: run own hook then own behaviors' on_react."""
        self.at_action_react(action)
        for behavior in self._behaviors:
            await behavior.on_react(self, action)

    async def visit_observe_check(self, action: Action) -> None:
        """Permission pass when this object is a bystander in the room."""
        self.at_observe_check(action)
        for behavior in self._behaviors:
            await behavior.on_check(self, action)

    async def visit_observe_react(self, action: Action) -> None:
        """Reaction pass when this object is a bystander in the room."""
        self.at_observe_react(action)
        for behavior in self._behaviors:
            await behavior.on_react(self, action)

    # --- Action hooks ---
    #
    # Sync, lightweight hooks for typeclass-style overrides. Heavy work
    # belongs in a Behavior. Override on subclasses; do not call super().

    def at_action_check(self, action: Action) -> None:
        """Called during permission pass before behaviors, when this is actor or target."""
        pass

    def at_action_react(self, action: Action) -> None:
        """Called during reaction pass before behaviors, when this is actor or target."""
        pass

    def at_observe_check(self, action: Action) -> None:
        """Called during permission pass before behaviors, when this is a bystander."""
        pass

    def at_observe_react(self, action: Action) -> None:
        """Called during reaction pass before behaviors, when this is a bystander."""
        pass

    # --- Attribute inheritance ---


    def get_display_name(self, looker: GameObject | None = None) -> str:
        """
        The name ``looker`` knows this object by.

        Perception-aware ("Someone" for an unseen actor); the override
        point for recognition/disguise systems. Lazy import keeps core
        importable on its own.
        """
        from realm.core.perception import perceived_name
        return perceived_name(self, looker)


    def msg(self, text: str) -> None:
        """
        Deliver a message to this object.

        Routes through ``_msg_handler`` if one is installed (typical for
        players linked to a session). Otherwise drops the message — non-player
        objects ignore output by default.

        Subclasses or behaviors that want listen-style reactions can override
        this method or install a handler that captures the text.
        """
        if self._msg_handler is not None:
            self._msg_handler(text)

    def set_msg_handler(self, handler: Callable[[str], None] | None) -> None:
        """
        Install a callback that receives messages sent to this object.

        Typically called by the framework when a player is linked to a session
        (handler = session.send_nowait). Pass ``None`` to clear.
        """
        self._msg_handler = handler

    def clear_msg_handler(self) -> None:
        """Clear any installed msg handler (alias for set_msg_handler(None))."""
        self._msg_handler = None

    def msg_contents(
        self,
        text: str,
        exclude: Iterable[GameObject] | None = None,
    ) -> None:
        """
        Deliver a message to every object contained in this one.

        Used for room broadcasts. ``exclude`` skips listed objects (typically
        the actor and target of an action that already received their own
        per-perspective messages).
        """
        excluded_ids: set[str] = set()
        if exclude is not None:
            for obj in exclude:
                if obj is not None:
                    excluded_ids.add(obj.id)
        for child in self._contents:
            if child.id in excluded_ids:
                continue
            child.msg(text)

    def __repr__(self) -> str:
        return f"<GameObject {self.id[:8]}... '{self.name}' tags={self.tags}>"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GameObject):
            return self.id == other.id
        return False

    def __hash__(self) -> int:
        return hash(self.id)
