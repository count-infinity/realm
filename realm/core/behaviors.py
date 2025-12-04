"""
Behavior system for composable object behaviors.

Behaviors are attached to GameObjects at runtime and receive events.
They can validate (veto) events and react to them.

Key features:
- Composable: Multiple behaviors can be attached to one object
- Runtime modifiable: Add/remove behaviors while game is running
- Event-driven: Behaviors react to the two-phase event system
- Tickable: Behaviors can opt into periodic updates
"""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.events import Event
    from realm.core.objects import GameObject


class Behavior(ABC):
    """
    Base class for composable behaviors.

    Subclass this to create behaviors like:
    - AggressiveBehavior: Attacks players on sight
    - WanderingBehavior: Moves randomly
    - ShopkeeperBehavior: Handles buy/sell transactions
    - ScriptBehavior: Executes user-defined scripts

    Lifecycle:
    - attach(obj): Called when behavior is added to an object
    - detach(obj): Called when behavior is removed from an object

    Event handling (two-phase):
    - validate_event(obj, event): Return False to veto the event
    - handle_event(obj, event): React to the event after validation

    Periodic updates:
    - tick(obj, delta): Called periodically if should_tick is True
    """

    # Class-level configuration
    behavior_id: str = "base"  # Unique identifier for this behavior type

    __slots__ = ('_owner', '_params')

    def __init__(self, **params: Any):
        """
        Initialize the behavior with optional parameters.

        Parameters are stored and can be used to configure behavior.
        For example: AggressiveBehavior(attack_chance=0.5)
        """
        self._owner: GameObject | None = None
        self._params: dict[str, Any] = params

    @property
    def owner(self) -> GameObject | None:
        """The object this behavior is attached to."""
        return self._owner

    @property
    def params(self) -> dict[str, Any]:
        """Configuration parameters for this behavior."""
        return self._params

    def get_param(self, name: str, default: Any = None) -> Any:
        """Get a parameter value with default."""
        return self._params.get(name, default)

    # --- Lifecycle methods ---

    def attach(self, obj: GameObject) -> None:
        """
        Called when this behavior is added to an object.

        Override to perform setup, subscribe to events, etc.
        """
        self._owner = obj

    def detach(self, obj: GameObject) -> None:
        """
        Called when this behavior is removed from an object.

        Override to perform cleanup.
        """
        self._owner = None

    # --- Event handling (two-phase) ---

    async def validate_event(self, obj: GameObject, event: Event) -> bool:
        """
        Phase 1: Validation. Return False to veto the event.

        Override to implement validation logic. For example:
        - A "frozen" behavior might veto MOVE events
        - A "muted" behavior might veto SPEECH events

        Args:
            obj: The GameObject this behavior is attached to
            event: The event being validated

        Returns:
            True to allow the event, False to cancel it
        """
        return True

    async def handle_event(self, obj: GameObject, event: Event) -> None:
        """
        Phase 2: Execution. React to the event after validation.

        Override to implement event reactions. For example:
        - An "aggressive" behavior might attack on ENTER events
        - A "greeter" behavior might say hello on ENTER events

        Args:
            obj: The GameObject this behavior is attached to
            event: The event to handle
        """
        pass

    # --- Periodic updates ---

    @property
    def should_tick(self) -> bool:
        """
        Return True if this behavior wants periodic tick() calls.

        Override to enable ticking for behaviors that need periodic updates.
        """
        return False

    @property
    def tick_interval(self) -> float:
        """
        Return the desired tick interval in seconds.

        Default is 1.0 second. Override for different intervals.
        """
        return 1.0

    async def tick(self, obj: GameObject, delta: float) -> None:
        """
        Called periodically for behaviors where should_tick is True.

        Args:
            obj: The GameObject this behavior is attached to
            delta: Time elapsed since last tick in seconds
        """
        pass

    # --- Serialization ---

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize this behavior for persistence.

        Returns a dictionary that can be used to recreate the behavior.
        """
        return {
            'behavior_id': self.behavior_id,
            'params': self._params,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Behavior:
        """
        Create a behavior from serialized data.

        Note: This base implementation just creates an instance with params.
        The behavior registry should map behavior_id to the correct class.
        """
        return cls(**data.get('params', {}))

    def __repr__(self) -> str:
        owner_name = self._owner.name if self._owner else "unattached"
        return f"<{self.__class__.__name__} on '{owner_name}'>"


class BehaviorRegistry:
    """
    Registry for behavior classes.

    Allows behaviors to be looked up by their behavior_id string,
    which is useful for serialization and dynamic behavior attachment.
    """

    _behaviors: dict[str, type[Behavior]] = {}

    @classmethod
    def register(cls, behavior_class: type[Behavior]) -> type[Behavior]:
        """
        Register a behavior class.

        Can be used as a decorator:
        @BehaviorRegistry.register
        class MyBehavior(Behavior):
            behavior_id = "my_behavior"
        """
        cls._behaviors[behavior_class.behavior_id] = behavior_class
        return behavior_class

    @classmethod
    def get(cls, behavior_id: str) -> type[Behavior] | None:
        """Get a behavior class by its ID."""
        return cls._behaviors.get(behavior_id)

    @classmethod
    def create(cls, behavior_id: str, **params: Any) -> Behavior | None:
        """Create a behavior instance by ID with parameters."""
        behavior_class = cls._behaviors.get(behavior_id)
        if behavior_class:
            return behavior_class(**params)
        return None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Behavior | None:
        """Create a behavior from serialized data."""
        behavior_id = data.get('behavior_id')
        if not behavior_id:
            return None
        behavior_class = cls._behaviors.get(behavior_id)
        if behavior_class:
            return behavior_class.from_dict(data)
        return None

    @classmethod
    def list_all(cls) -> list[str]:
        """List all registered behavior IDs."""
        return list(cls._behaviors.keys())
