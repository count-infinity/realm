"""
REALM testing utilities.

The Simulator drives the *real* engine (propagation, softcode, commands,
game system) in-process, so a test — or a game author checking their own
content — can run softcode or player commands and observe exactly what a
connected player would see. No sockets, no database file.

The pytest fixtures (``world``, ``classic_world``, the ``features``
marker) are a plugin: put ``pytest_plugins = ["realm.testing.fixtures"]``
in your ``conftest.py``. ``build_test_world`` and ``reconfigure`` are the
same worlds without pytest.
"""

from realm.testing.simulator import Simulator
from realm.testing.worlds import build_test_world, reconfigure

__all__ = ["Simulator", "build_test_world", "reconfigure"]
