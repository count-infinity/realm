"""Showcase verification — item 252, inventing an action with act().

Three claims carry this tutorial and each gets a test: a custom event
carries a structured payload its subscribers can read, a participant's
``on_check`` can rewrite that payload before any subscriber sees it, and
``block()`` stops the reaction pass outright.

The doc IS the test input: the Build-it transcript is read from the
markdown, so an edit that breaks the build breaks this file.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"
DOC = "252_custom_action.md"
BUILD_RED_FLAGS = ("Unknown command", "Script error", "Syntax error",
                   "Traceback", "not defined")


def build_lines(doc_name: str) -> list[str]:
    body = (DOCS / doc_name).read_text()
    match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
    assert match, f"{doc_name}: no Build it section"
    lines: list[str] = []
    for block in re.findall(r"```text\n(.*?)```", match.group(1), re.S):
        lines.extend(line for line in block.splitlines() if line.strip())
    assert lines, f"{doc_name}: empty Build it"
    return lines


@pytest.fixture
def reactor():
    sim = Simulator()
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
    builder.add_tag("builder")
    builder.add_tag("admin")
    yield sim, builder
    sim.close()


async def run_build(sim, builder):
    for line in build_lines(DOC):
        # submit_line (not do): real input path, so '''-heredoc blocks
        # accumulate; one-liners dispatch identically.
        await sim.submit_line(builder, line)
    out = "\n".join(sim.seen(builder))
    for flag in BUILD_RED_FLAGS:
        assert flag not in out, f"{DOC} build tripped {flag!r}:\n{out}"


async def purge(sim, who):
    """Fire the event and let the queued propagation drain."""
    sim.seen(who)
    await sim.submit_line(who, "purge")
    await asyncio.sleep(0.05)
    return "\n".join(sim.seen(who))


def find(sim, name):
    return sim.store.find_cached(name=name)[0]


@pytest.mark.asyncio
class TestCustomAction:

    async def test_subscribers_read_the_payload(self, reactor):
        """severity and section ride the event, not the emitter's attrs."""
        sim, bob = reactor
        await run_build(sim, bob)
        await sim.submit_line(bob, "@set carbon filter/online = 0")

        out = await purge(sim, bob)
        assert "trauma team standing by for section C" in out

    async def test_tag_subscriber_answers_without_reading_severity(self, reactor):
        sim, bob = reactor
        await run_build(sim, bob)
        out = await purge(sim, bob)
        assert "blast door slams" in out
        assert find(sim, "blast door").db.get("sealed") == 1

    async def test_message_key_is_always_present(self, reactor):
        sim, bob = reactor
        await run_build(sim, bob)
        await purge(sim, bob)
        entries = find(sim, "logbook").db.get("entries")
        assert entries and "coolant klaxon" in entries[0]

    async def test_attached_filter_rewrites_the_payload(self, reactor):
        """The headline: a bystander carrying the hazard_filter behavior_def
        edits the event in flight, and the subscriber downstream reads the
        edited value."""
        sim, bob = reactor
        await run_build(sim, bob)

        out = await purge(sim, bob)                    # filter online
        assert "minor exposure" in out
        assert "trauma team" not in out

        await sim.submit_line(bob, "@set carbon filter/online = 0")
        out = await purge(sim, bob)                    # same event, intact
        assert "trauma team" in out

    async def test_editing_the_def_retunes_the_filter_live(self, reactor):
        sim, bob = reactor
        await run_build(sim, bob)

        await sim.submit_line(
            bob,
            "@set hazard_filter/on_check = "
            "if has_atag('hazard'): set_adata('severity', 9)")
        out = await purge(sim, bob)
        assert "trauma team" in out    # the def now raises instead of cuts

    async def test_block_stops_every_subscriber(self, reactor):
        sim, bob = reactor
        await run_build(sim, bob)
        await sim.submit_line(
            bob, "@set here/on_check = if has_atag('hazard'): block('containment holds')")
        find(sim, "blast door").db.set("sealed", None)

        out = await purge(sim, bob)
        assert "MEDBAY" not in out
        assert "blast door slams" not in out
        assert find(sim, "blast door").db.get("sealed") is None

    async def test_bystander_on_check_attribute_is_not_consulted(self, reactor):
        """Participants decide, bystanders react: a raw on_check ATTRIBUTE
        on a floor object never runs. Attaching a behavior is the opt-in,
        which is why the filter carries hazard_filter instead."""
        sim, bob = reactor
        await run_build(sim, bob)
        await sim.submit_line(bob, "@set carbon filter/online = 0")
        await sim.submit_line(bob, "@create loose rock")
        await sim.submit_line(bob, "drop loose rock")
        await sim.submit_line(
            bob, "@set loose rock/on_check = if has_atag('hazard'): set_adata('severity', 0)")

        out = await purge(sim, bob)
        assert "trauma team" in out, "a bystander attribute must not intercept"
