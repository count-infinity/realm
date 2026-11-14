"""
Suite-wide fixtures.

The world fixtures (``world``, ``classic_world``, ``configure``, the
``features`` marker) come from the ``realm.testing.fixtures`` plugin, the
same one a game's tests use. Every test starts and ends with no world
installed, so a Simulator or server a test forgot to close cannot leak
into the next.

A test that hand-wires a service (a fake check resolver, a combat
manager) takes ``world`` (no features) or ``classic_world`` (every
built-in), or builds a ``Simulator``, and sets the field on that world:

    def test_rigged(world):
        world.services["checks"].resolver = always_succeed
"""

from __future__ import annotations

import pytest

from realm.std.rules import checks as checks_module

pytest_plugins = ["realm.testing.fixtures"]


@pytest.fixture(autouse=True)
def _shared_checks_untouched():
    yield
    # The no-world Checks is shared by every test; a test that changes it
    # leaks into the next. Change the world's own Checks instead.
    assert checks_module._NO_WORLD == checks_module.Checks(), (
        "a test changed the no-world Checks; take the `world` fixture and "
        "set world.services['checks'] instead")
