"""
Moving time in tests: one fake clock for every clock the engine reads.

Each module that reads the time for a game reason does it through its own
module-level ``now()`` (a cooldown, a corpse lock, a letter's date, a
combat beat, idle time ...), called through the module, so replacing
``realm.std.mail.mail.now`` moves mail. :class:`FakeClock` replaces every
one of them at once, so a game test moves the whole world's time without
knowing the list::

    def test_the_lock_lifts(clock, sim):          # the ``clock`` fixture
        ...
        clock.advance(300)

Wall clocks (dates kept in the database) and monotonic ones (durations kept
in memory) all read the same fake time; nothing compares one with the
other. ``tests/test_clocks.py`` fails when a module reads the time any
other way, or adds a ``now()`` this list does not name.
"""

from __future__ import annotations

import importlib

#: Every module with a ``now()`` clock, kernel first.
ENGINE_CLOCKS: tuple[str, ...] = (
    "realm.core.events",
    "realm.scripting.waits",
    "realm.gateway.session",
    "realm.std.abilities.abilities",
    "realm.std.accounts.account",
    "realm.std.accounts.auth",
    "realm.std.achievements.achievements",
    "realm.std.channels.channels",
    "realm.std.clans.clans",
    "realm.std.clock.clock",
    "realm.std.combat.corpses",
    "realm.std.combat.encounter",
    "realm.std.instances.instances",
    "realm.std.mail.mail",
    "realm.std.needs.needs",
    "realm.std.quests.quests",
    "realm.std.rules.progression",
    "realm.std.spawning.zone_reset",
    "realm.std.tasks.tasks",
    "realm.std.vitals.regen",
    "realm.std.wilderness.wilderness",
)

#: Where a :class:`FakeClock` starts: 2027-01-15 08:00 UTC.
EPOCH = 1_800_000_000.0


class FakeClock:
    """A clock that moves only when the test moves it: ``clock.t`` is the
    time, ``clock.advance(seconds)`` moves it on, and ``install`` makes it
    every engine clock."""

    def __init__(self, start: float = EPOCH) -> None:
        self.t = float(start)

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> float:
        """Move the time on by ``seconds``; the new time."""
        self.t += float(seconds)
        return self.t

    def install(self, monkeypatch) -> FakeClock:
        """Replace every module's ``now`` in ``ENGINE_CLOCKS`` with this
        clock, for the rest of the test (``monkeypatch`` undoes it)."""
        for name in ENGINE_CLOCKS:
            monkeypatch.setattr(importlib.import_module(name), "now", self)
        return self


__all__ = ["FakeClock", "ENGINE_CLOCKS", "EPOCH"]
