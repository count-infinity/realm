"""
Suite-wide fixtures.

Every test starts and ends with no world installed (``realm.core.world``),
so a Simulator or server a test forgot to close cannot leak into the next.

A test that hand-wires a service (a fake check resolver, a combat
manager) takes ``world`` (no features) or ``classic_world`` (every
built-in), or builds a ``Simulator``, and sets the field on that world:

    def test_rigged(world):
        world.services["checks"].resolver = always_succeed
"""

from __future__ import annotations

import pytest

from realm.core.world import set_world
from realm.std.rules import checks as checks_module


@pytest.fixture(autouse=True)
def _no_world_between_tests():
    set_world(None)
    yield
    set_world(None)
    # The no-world Checks is shared by every test; a test that changes it
    # leaks into the next. Change the world's own Checks instead.
    assert checks_module._NO_WORLD == checks_module.Checks(), (
        "a test changed the no-world Checks; take the `world` fixture and "
        "set world.services['checks'] instead")


def build_test_world(names: list[str], settings=None):
    """Build and install a world of ``names`` (a generator for a fixture:
    ``yield from build_test_world(CLASSIC)``); closed on teardown."""
    from realm.features import load
    from realm.persistence.memory import MemoryStore
    from realm.server.world import build_world

    features = load(names)
    features.install_registries()
    world = build_world(MemoryStore(), settings, features=features)
    try:
        yield world
    finally:
        world.close()


@pytest.fixture
def _bare_world():
    yield from build_test_world([])


@pytest.fixture
def world(_bare_world):
    """A built, installed world with no features (the bare kernel)."""
    return _bare_world


@pytest.fixture
def classic_world():
    """A built, installed world with every built-in feature."""
    from realm.std import CLASSIC
    yield from build_test_world(list(CLASSIC))


def reconfigure(world, **changes):
    """Change a built world's settings as config.py would
    (``reconfigure(sim.world, keyid_sigil="$$")``). A bad value raises
    ValueError: Settings validates on construction."""
    from dataclasses import replace
    world.settings = replace(world.settings, **changes)
    return world


@pytest.fixture
def configure(_bare_world):
    """``configure(emote_sigil="@")``: reconfigure the bare world."""
    return lambda **changes: reconfigure(_bare_world, **changes)


@pytest.fixture
def classic_world_unscripted():
    """Every built-in feature with scripting off: the test wires its own
    ScriptEngine (``world.scripts = engine``; ``world.observe(...)``)."""
    from realm.config.loader import Settings
    from realm.std import CLASSIC
    yield from build_test_world(list(CLASSIC), Settings(enable_scripting=False))
