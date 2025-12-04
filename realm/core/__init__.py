"""
Core module containing the fundamental building blocks of REALM.

- GameObject: Base class for all game objects
- Event/EventBus: Two-phase event system
- Behavior: Composable behavior system
- Tags: Flexible categorization
"""

from realm.core.objects import GameObject, AttributeProxy
from realm.core.events import Event, EventBus
from realm.core.behaviors import Behavior
from realm.core.tags import TagSet

__all__ = [
    "GameObject",
    "AttributeProxy",
    "Event",
    "EventBus",
    "Behavior",
    "TagSet",
]
