"""
Built worlds for tests, without pytest (``realm.testing.fixtures`` wraps
them as fixtures).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


def build_test_world(names: list[str], settings: Any = None) -> Iterator[Any]:
    """Build and install a world of the features ``names`` on a memory
    store; a generator for a fixture (``yield from build_test_world(CLASSIC)``),
    closed when it resumes."""
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


def reconfigure(world: Any, **changes: Any) -> Any:
    """Change a built world's settings as config.py would
    (``reconfigure(sim.world, keyid_sigil="$$")``). A bad value raises
    ValueError: Settings validates on construction."""
    from dataclasses import replace
    world.settings = replace(world.settings, **changes)
    return world


__all__ = ["build_test_world", "reconfigure"]
