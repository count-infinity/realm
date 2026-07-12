"""
REALM testing utilities.

The Simulator drives the *real* engine (propagation, softcode, commands,
game system) in-process, so a test — or a game author checking their own
content — can run softcode or player commands and observe exactly what a
connected player would see. No sockets, no database file.
"""

from realm.testing.simulator import Simulator

__all__ = ["Simulator"]
