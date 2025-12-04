"""
Two-phase event system inspired by CoffeeMud's CMMsg.

Events flow through two phases:
1. Validation (on_validate): Any listener can veto
2. Execution (on_execute): Event is applied

Events have three-perspective messages:
- source_msg: What the actor sees
- target_msg: What the target sees
- others_msg: What everyone else sees
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject


class EventType(Enum):
    """Core event types in REALM."""

    # Movement
    ENTER = auto()      # Something enters a location
    LEAVE = auto()      # Something leaves a location
    ARRIVE = auto()     # This object arrives somewhere
    DEPART = auto()     # This object departs from somewhere

    # Combat
    ATTACK = auto()     # Attack initiated
    DAMAGE = auto()     # Damage dealt
    DEATH = auto()      # Something dies
    KILL = auto()       # Something kills another
    FLEE = auto()       # Attempt to flee combat

    # Communication
    SPEECH = auto()     # Speaking (say)
    WHISPER = auto()    # Private message
    CHANNEL = auto()    # Channel communication
    EMOTE = auto()      # Pose/emote

    # Items
    GET = auto()        # Pick up item
    DROP = auto()       # Drop item
    GIVE = auto()       # Give item to someone
    PUT = auto()        # Put item in container
    WEAR = auto()       # Wear/wield item
    REMOVE = auto()     # Remove worn item
    CONSUME = auto()    # Eat/drink item

    # Interaction
    LOOK = auto()       # Look at something
    EXAMINE = auto()    # Detailed examination
    USE = auto()        # Use an object
    OPEN = auto()       # Open door/container
    CLOSE = auto()      # Close door/container
    LOCK = auto()       # Lock door/container
    UNLOCK = auto()     # Unlock door/container

    # Commerce
    BUY = auto()        # Buy from shop
    SELL = auto()       # Sell to shop
    BRIBE = auto()      # Give money

    # Session
    CONNECT = auto()    # Player connects
    DISCONNECT = auto() # Player disconnects
    IDLE = auto()       # Player goes idle

    # Time
    TICK = auto()       # Periodic timer
    HOUR = auto()       # Game hour change
    DAY = auto()        # Game day change

    # Magic
    CAST = auto()       # Cast spell/ability
    AFFECT = auto()     # Effect applied
    RESIST = auto()     # Effect resisted

    # Custom (for scripting)
    CUSTOM = auto()     # User-defined event


@dataclass(slots=True)
class Event:
    """
    Represents a game event that flows through the two-phase system.

    Attributes:
        type: The event type (EventType enum or string for custom)
        source: The object initiating the event (actor)
        target: The primary target of the event
        location: Where the event occurs
        data: Event-specific data dictionary
        cancelled: Set to True during validation to cancel the event
        source_msg: Message shown to the source
        target_msg: Message shown to the target
        others_msg: Message shown to others in the location
    """

    type: EventType | str
    source: GameObject | None = None
    target: GameObject | None = None
    location: GameObject | None = None
    data: dict[str, Any] = field(default_factory=dict)
    cancelled: bool = False
    source_msg: str = ""
    target_msg: str = ""
    others_msg: str = ""

    def cancel(self, reason: str | None = None) -> None:
        """Cancel this event during validation phase."""
        self.cancelled = True
        if reason:
            self.data['cancel_reason'] = reason

    @property
    def cancel_reason(self) -> str | None:
        """Get the reason this event was cancelled."""
        return self.data.get('cancel_reason')

    def __repr__(self) -> str:
        type_name = self.type.name if isinstance(self.type, EventType) else self.type
        source_name = self.source.name if self.source else "None"
        target_name = self.target.name if self.target else "None"
        return f"<Event {type_name} source={source_name} target={target_name}>"


class EventBus:
    """
    Two-phase event dispatcher.

    Phase 1 (Validation): All listeners get on_event_validate() called.
                         Any can return False to cancel the event.
    Phase 2 (Execution): If not cancelled, all listeners get on_event_execute().

    Listeners are collected from:
    - The event source
    - The event target
    - Contents of the event location
    - The location itself
    """

    __slots__ = ('_global_handlers',)

    def __init__(self) -> None:
        # Global handlers that receive all events (for logging, scripting, etc.)
        self._global_handlers: list[Any] = []

    def add_global_handler(self, handler: Any) -> None:
        """Add a handler that receives all events."""
        if handler not in self._global_handlers:
            self._global_handlers.append(handler)

    def remove_global_handler(self, handler: Any) -> None:
        """Remove a global handler."""
        if handler in self._global_handlers:
            self._global_handlers.remove(handler)

    async def emit(self, event: Event) -> bool:
        """
        Emit an event through the two-phase system.

        Returns True if the event was executed, False if cancelled.
        """
        # Collect all listeners
        listeners = self._collect_listeners(event)

        # Phase 1: Validation
        for obj in listeners:
            try:
                if not await obj.on_event_validate(event):
                    event.cancelled = True
                    break
            except Exception:
                # Log but don't crash on handler errors
                # TODO: Proper logging
                pass

        # Check global handlers for validation
        for handler in self._global_handlers:
            if hasattr(handler, 'on_event_validate'):
                try:
                    if not await handler.on_event_validate(event):
                        event.cancelled = True
                        break
                except Exception:
                    pass

        if event.cancelled:
            return False

        # Phase 2: Execution
        for obj in listeners:
            try:
                await obj.on_event_execute(event)
            except Exception:
                # Log but don't crash on handler errors
                # TODO: Proper logging
                pass

        # Global handlers execution
        for handler in self._global_handlers:
            if hasattr(handler, 'on_event_execute'):
                try:
                    await handler.on_event_execute(event)
                except Exception:
                    pass

        # Deliver messages
        self._deliver_messages(event)

        return True

    def _collect_listeners(self, event: Event) -> list[GameObject]:
        """Collect all objects that should receive this event."""
        listeners: list[GameObject] = []
        seen: set[str] = set()

        def add_listener(obj: GameObject | None) -> None:
            if obj is not None and obj.id not in seen:
                seen.add(obj.id)
                listeners.append(obj)

        # Source always listens
        add_listener(event.source)

        # Target listens
        add_listener(event.target)

        # Location and its contents listen
        if event.location is not None:
            add_listener(event.location)
            for obj in event.location.contents:
                add_listener(obj)

        return listeners

    def _deliver_messages(self, event: Event) -> None:
        """Send appropriate messages to source, target, and others."""
        if event.source and event.source_msg:
            event.source.msg(event.source_msg)

        if event.target and event.target_msg and event.target != event.source:
            event.target.msg(event.target_msg)

        if event.location and event.others_msg:
            for obj in event.location.contents:
                if obj != event.source and obj != event.target:
                    obj.msg(event.others_msg)


# Convenience function
async def emit(event: Event, bus: EventBus | None = None) -> bool:
    """
    Emit an event. If no bus is provided, uses a simple local dispatch.

    For most uses, you'll want to use the game's global EventBus instance.
    """
    if bus is not None:
        return await bus.emit(event)

    # Simple fallback without a bus - just call handlers directly
    listeners: list[GameObject] = []
    if event.source:
        listeners.append(event.source)
    if event.target and event.target != event.source:
        listeners.append(event.target)

    for obj in listeners:
        if not await obj.on_event_validate(event):
            event.cancelled = True
            return False

    if not event.cancelled:
        for obj in listeners:
            await obj.on_event_execute(event)

    return not event.cancelled
