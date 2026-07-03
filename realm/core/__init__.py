"""
Core module containing the fundamental building blocks of REALM.

- GameObject: Base class for all game objects
- Action / PropagationEngine: Two-pass action propagation
- Behavior: Composable behavior system attached to GameObjects
- Tags: Flexible categorization
"""

from realm.core.behaviors import Behavior, BehaviorRegistry
from realm.core.objects import AttributeProxy, GameObject
from realm.core.propagation import (
    ROOM_TARGET_CHAIN,
    Action,
    ActorStep,
    PropagationEngine,
    RoomContentsStep,
    RoomStep,
    Step,
    TargetStep,
    deliver_messages,
    get_engine,
    propagate,
    reset_engine,
)
from realm.core.tags import TagSet

__all__ = [
    "GameObject",
    "AttributeProxy",
    "Behavior",
    "BehaviorRegistry",
    "TagSet",
    "Action",
    "Step",
    "ActorStep",
    "RoomStep",
    "RoomContentsStep",
    "TargetStep",
    "ROOM_TARGET_CHAIN",
    "PropagationEngine",
    "get_engine",
    "reset_engine",
    "propagate",
    "deliver_messages",
]
