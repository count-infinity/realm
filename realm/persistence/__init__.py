"""
Persistence layer for REALM.

Handles saving and loading game objects to/from SQLite (or PostgreSQL).
"""

from realm.persistence.manager import PersistenceManager
from realm.persistence.repository import GameObjectRepository

__all__ = ["PersistenceManager", "GameObjectRepository"]
