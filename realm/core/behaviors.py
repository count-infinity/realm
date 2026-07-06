"""
Behavior system for composable object behaviors.

Behaviors are attached to GameObjects at runtime and participate in the
two-pass action propagation engine via on_check (permission pass) and
on_react (reaction pass). They can also opt into periodic ticks.

Key features:
- Composable: Multiple behaviors can be attached to one object
- Runtime modifiable: Add/remove behaviors while game is running
- Action-driven: Behaviors react to actions via on_check / on_react
- Tickable: Behaviors can opt into periodic updates
"""

from __future__ import annotations

import weakref
from abc import ABC
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action


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

    Action handling (two-pass):
    - on_check(obj, action): Permission pass — inspect, modify, or block
    - on_react(obj, action): Reaction pass — accumulate messages, queue trailing

    Periodic updates:
    - tick(obj, delta): Called periodically if should_tick is True
    """

    # Class-level configuration
    behavior_id: str = "base"  # Unique identifier for this behavior type

    __slots__ = ('__weakref__', '_owner', '_params')

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

    # --- Action propagation (two-pass) ---

    async def on_check(self, obj: GameObject, action: Action) -> None:
        """
        Permission pass: inspect or block an action before it resolves.

        Override to:
          - Filter on action.action_type or action.tags
          - Call action.block(reason) to veto the action
          - Call action.add_modifier(value, reason) to influence resolution
          - Call action.add_data(key, value) to inject context for downstream

        The permission pass ALWAYS runs to completion — even a blocked action
        notifies all observers. Don't return early as a "veto," call block().

        Args:
            obj: The GameObject this behavior is attached to
            action: The action being propagated
        """
        pass

    async def on_react(self, obj: GameObject, action: Action) -> None:
        """
        Reaction pass: react to an action's resolution.

        Always runs after the permission pass, even if the action was blocked.
        Override to:
          - Add audience messages via action.add_message(audience, msg)
          - Queue trailing actions via action.queue_trailing(other)
          - Mutate world state in response to what happened

        Args:
            obj: The GameObject this behavior is attached to
            action: The action being propagated
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
        Desired seconds between tick() calls. The server heartbeat fires
        at TICK_INTERVAL; behaviors asking for longer intervals are
        skipped on intervening pulses. Default 0 = every pulse.
        """
        return 0.0

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


# --- Behavior-owner registry -------------------------------------------------
#
# The server's tick loop should not scan 100,000 inert objects to find the
# fifty with behaviors. Objects register here when their first behavior is
# attached (weak references — deleted objects vanish on their own).

_behavior_owners: weakref.WeakSet = weakref.WeakSet()


def register_behavior_owner(obj: GameObject) -> None:
    _behavior_owners.add(obj)


def unregister_behavior_owner(obj: GameObject) -> None:
    _behavior_owners.discard(obj)


def behavior_owners() -> list[GameObject]:
    """A snapshot of every object with at least one behavior attached."""
    return list(_behavior_owners)


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
