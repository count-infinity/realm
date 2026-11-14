"""
REALM's pytest fixtures, as a plugin. A game's ``tests/conftest.py`` gets
them with one line:

    pytest_plugins = ["realm.testing.fixtures"]

Fixtures:

- ``world``: a built, installed world with no features (the bare kernel),
  or the features a ``@pytest.mark.features("look", "items")`` marker names;
- ``classic_world``: every built-in feature (``realm.std.CLASSIC``);
- ``classic_world_unscripted``: the same with scripting off, for a test
  that wires its own ``ScriptEngine``;
- ``configure``: ``configure(emote_sigil="@")`` reconfigures ``world``.

Every test starts and ends with no world installed.
"""

from __future__ import annotations

import pytest

from realm.testing.worlds import build_test_world, reconfigure


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "features(*names): the `world` fixture builds a world of these "
        "features instead of a bare one")


@pytest.fixture(autouse=True)
def _no_world_between_tests():
    from realm.core.world import set_world
    set_world(None)
    yield
    set_world(None)


@pytest.fixture
def _bare_world(request):
    marker = request.node.get_closest_marker("features")
    yield from build_test_world(list(marker.args) if marker else [])


@pytest.fixture
def world(_bare_world):
    """A built, installed world with no features (the bare kernel), or the
    features a ``@pytest.mark.features("look", ...)`` marker names."""
    return _bare_world


@pytest.fixture
def classic_world():
    """A built, installed world with every built-in feature."""
    from realm.std import CLASSIC
    yield from build_test_world(list(CLASSIC))


@pytest.fixture
def classic_world_unscripted():
    """Every built-in feature with scripting off: the test wires its own
    ScriptEngine (``world.scripts = engine``; ``world.observe(...)``)."""
    from realm.config.loader import Settings
    from realm.std import CLASSIC
    yield from build_test_world(list(CLASSIC), Settings(enable_scripting=False))


@pytest.fixture
def configure(_bare_world):
    """``configure(emote_sigil="@")``: reconfigure the bare world."""
    return lambda **changes: reconfigure(_bare_world, **changes)
