"""
Server layer for REALM.

Hosts the game loop and coordinates the subsystems. The command types live
in ``realm.commands``.
"""

from realm.server.game import GameServer

__all__ = ["GameServer"]
