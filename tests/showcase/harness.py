"""
The shared showcase test harness — ONE canonical copy of the doc-driven
build helpers that were historically pasted into every suite.

The contract: a tutorial's ``## Build it`` fenced blocks are read straight
out of its markdown and driven through the REAL client input path
(``Simulator.submit_line`` -> ``Session.submit_input`` -> dispatcher), so
multi-line ``'''`` heredoc blocks accumulate exactly as a player typing
them would, and a doc edit that breaks the build breaks the suite.

Suites import from here instead of keeping local copies:

    from tests.showcase.harness import (
        BUILD_FAILURE_MARKERS, DOCS, answer, build, build_lines,
        build_section, do, find_one, lines_in, make_sim,
        workshop_and_builder,
    )

The ``sim`` and ``pinned_rand`` fixtures live in ``conftest.py`` (built on
``make_sim``), so most suites need no fixture of their own; a suite with
special wiring (the heist's observers, a custom resolver) composes
``make_sim()`` inside its local fixture instead.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import re

from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

# Output that must never appear while running a "Build it" transcript —
# catches typos, permission problems, and validation failures in any
# tutorial line.
BUILD_FAILURE_MARKERS = (
    "Unknown command",
    "Permission denied",
    "Usage:",
    "not found",
    "Script error",
    "Eval error",
    "error",
)


def build_section(doc_name: str) -> str:
    """The raw text of a tutorial's "Build it" section."""
    body = (DOCS / doc_name).read_text(encoding="utf-8")
    match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
    assert match, f"{doc_name}: no Build it section"
    return match.group(1)


def lines_in(section: str) -> list[str]:
    """Every command line in a section's ```text fenced blocks.

    Blank lines INSIDE a block are kept (a heredoc body may breathe —
    the session preserves them into the stored script); blank padding at
    a block's edges is layout and is trimmed. Outside a heredoc a blank
    line is a no-op at the session anyway.
    """
    lines: list[str] = []
    for block in re.findall(r"```text\n(.*?)```", section, re.S):
        block_lines = block.splitlines()
        while block_lines and not block_lines[0].strip():
            block_lines.pop(0)
        while block_lines and not block_lines[-1].strip():
            block_lines.pop()
        lines.extend(block_lines)
    return lines


def build_lines(doc_name: str) -> list[str]:
    """Every command line in the tutorial's "Build it" fenced blocks."""
    lines = lines_in(build_section(doc_name))
    assert lines, f"{doc_name}: empty Build it"
    return lines


def make_sim(**kwargs) -> Simulator:
    """A Simulator wired the way a live GameServer is — including the
    session-manager plumbing prompt() wizards resolve through."""
    s = Simulator(**kwargs)
    if s.engine is not None:
        s.engine.session_manager = SimpleNamespace(
            all_sessions=lambda: list(s._sessions.values()))
    return s


def workshop_and_builder(sim):
    """The standing start of every tutorial: a room and a builder in it."""
    room = sim.room("The Workshop")
    bilda = sim.player("Bilda", location=room)
    bilda.add_tag("builder")
    return room, bilda


async def build(sim, player, lines, markers=BUILD_FAILURE_MARKERS):
    """Run a Build-it transcript; fail loudly if any line misfires.

    Routes each line through the REAL client input path (``submit_line``)
    so multi-line ``'''`` heredoc blocks accumulate exactly as a player
    typing them would; one-liners run identically.
    """
    for line in lines:
        await sim.submit_line(player, line)
        out = "\n".join(sim.seen(player))
        for marker in markers:
            assert marker not in out, f"build line {line!r} failed: {out!r}"


async def do(sim, player, line):
    """Run one command and return everything the player saw."""
    await sim.do(player, line)
    return sim.seen(player)


async def answer(sim, player, line):
    """Answer a pending prompt() wizard with the player's next line."""
    session = sim.session(player)
    handler = session.input_handler
    assert handler is not None, "no prompt() is pending for this player"
    await handler(session, line)
    return sim.seen(player)


def find_one(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no object named {name!r} in the world"
    return matches[0]


__all__ = [
    "BUILD_FAILURE_MARKERS", "DOCS", "answer", "build", "build_lines",
    "build_section", "do", "find_one", "lines_in", "make_sim",
    "workshop_and_builder",
]
