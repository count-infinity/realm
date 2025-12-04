"""
Server layer for REALM.

Handles command dispatching, game logic, and coordination.
"""

from realm.server.dispatcher import CommandDispatcher
from realm.server.game import GameServer

__all__ = ["CommandDispatcher", "GameServer"]
