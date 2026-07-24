"""
Shared fixtures for the showcase suites — the canonical ``sim`` and
``pinned_rand`` most files need. A suite with special wiring (extra
observers, a custom check resolver) shadows ``sim`` with its own module
fixture, composing ``harness.make_sim()``.
"""

from __future__ import annotations

import pytest

from tests.showcase.harness import make_sim


@pytest.fixture
def sim():
    s = make_sim()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def pinned_rand(monkeypatch):
    """Pin rand(): random.randint returns holder['value'] clamped to range."""
    holder = {"value": 1}

    def fake_randint(low, high):
        return max(low, min(holder["value"], high))

    monkeypatch.setattr(
        "realm.scripting.functions.random.randint", fake_randint)
    return holder
