"""Showcase verification — Identity & Speech (items 133, 134, 84, 79, 139, 85).

These tutorials sit on the two per-viewer seams shipped 2026-07-17:
`register_name_resolver` (who someone appears to be) and
`register_speech_renderer` (how their words arrive). Most carry a small
NATIVE half — a resolver/renderer a game registers at deploy time — plus
in-game softcode that drives it. The Build-it command lines are read
straight from each tutorial's markdown and driven through the dispatcher;
the native halves are registered in each test's fixture, mirroring the
Python the tutorial shows.

Item 85 (rich emotes) needs no native half at all — `pose /name` is a
builtin — so its tutorial is pure in-game and its test just drives it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from realm.core.perception import (
    clear_name_resolvers,
    register_name_resolver,
)
from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"
RED_FLAGS = ("Unknown command", "Script error", "Syntax error", "Traceback",
             "not defined", "refuses")


def build_lines(doc_name: str) -> list[str]:
    """Every command line in the tutorial's "Build it" fenced blocks."""
    body = (DOCS / doc_name).read_text()
    match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
    assert match, f"{doc_name}: no Build it section"
    lines: list[str] = []
    for block in re.findall(r"```text\n(.*?)```", match.group(1), re.S):
        lines.extend(line for line in block.splitlines() if line.strip())
    assert lines, f"{doc_name}: empty Build it"
    return lines


async def run_build(sim, builder, doc):
    for line in build_lines(doc):
        await sim.do(builder, line)
    out = "\n".join(sim.seen(builder))
    for flag in RED_FLAGS:
        assert flag not in out, f"{doc} build tripped {flag!r}:\n{out}"


def said(sim, who, needle):
    return [x for x in sim.seen(who) if needle in x]


# --- 133 short-descs & introductions ---------------------------------------


def _recognition_resolver(obj, looker, current):
    """The resolver the 133 tutorial shows, registered here so the test
    exercises the same policy the doc documents."""
    sdesc = obj.db.get('sdesc')
    if (sdesc and looker is not None and looker is not obj
            and looker.id not in (obj.db.get('recognized_by') or [])):
        return sdesc
    return current


@pytest.fixture
def masq():
    sim = Simulator()
    hall = sim.room("Hall")
    ada = sim.player("Ada", location=hall)
    ada.add_tag("admin")                 # owns the steward it @creates
    bran = sim.player("Bran", location=hall)
    clear_name_resolvers()
    register_name_resolver(_recognition_resolver)
    try:
        yield sim, ada, bran
    finally:
        clear_name_resolvers()
        sim.close()


@pytest.mark.asyncio
class TestShortDescs:
    async def test_stranger_then_introduced(self, masq):
        sim, ada, bran = masq
        await run_build(sim, ada, "133_short_descs.md")
        # Move both into the steward's room, give sdescs.
        room = ada.location
        bran.location = room
        await sim.do(ada, "@set Ada/sdesc = a tall woman in a domino mask")
        await sim.do(ada, "@set Bran/sdesc = a stout man in a feathered hat")

        # Bran doesn't know Ada yet: her speech reads as the sdesc.
        sim.seen(bran)
        await sim.do(ada, "say Care to dance?")
        assert said(sim, bran, "dance") == [
            'a tall woman in a domino mask says, "Care to dance?"']

        # Ada introduces herself to Bran.
        sim.seen(bran)
        await sim.do(ada, "introduce Bran")
        assert said(sim, bran, "introduces")

        # Now Bran hears her by name; the seam covered her voice too.
        sim.seen(bran)
        await sim.do(ada, "say Shall we?")
        assert said(sim, bran, "Shall") == ['Ada says, "Shall we?"']

    async def test_a_third_party_still_sees_the_mask(self, masq):
        sim, ada, bran = masq
        cass = sim.player("Cass", location=ada.location)
        await run_build(sim, ada, "133_short_descs.md")
        room = ada.location
        bran.location = room
        cass.location = room
        await sim.do(ada, "@set Ada/sdesc = a tall woman in a domino mask")

        await sim.do(ada, "introduce Bran")           # only Bran learns her
        sim.seen(bran), sim.seen(cass)
        await sim.do(ada, "say Two of you now.")
        assert said(sim, bran, "Two") == ['Ada says, "Two of you now."']
        assert said(sim, cass, "Two") == [
            'a tall woman in a domino mask says, "Two of you now."']
