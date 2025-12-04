"""
Gateway layer for REALM.

Handles network protocols (telnet, websocket) and session management.
"""

from realm.gateway.session import Session, SessionManager
from realm.gateway.telnet import TelnetServer

__all__ = ["Session", "SessionManager", "TelnetServer"]
