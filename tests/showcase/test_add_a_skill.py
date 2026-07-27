"""Showcase verification — item 251, adding a skill as data.

The tutorial's whole claim is that a skill nobody coded starts governing
the world once it exists as a ``skill_def`` object and the table is
reloaded. So the interesting assertions are the three effective-skill
numbers (trained / untrained-but-defined / undefined), and the two ways
the world reacts to them: a per-viewer ``@detail`` and a check-driven
payout.

As everywhere in this suite, the doc IS the test input: the Build-it
transcript is read from the markdown, so an edit that breaks the build
breaks this file.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from realm.core.checks import set_check_resolver
from realm.core.dice import CheckResult
from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"
DOC = "251_add_a_skill.md"
BUILD_RED_FLAGS = ("Unknown command", "Script error", "Syntax error",
                   "Traceback", "not defined")


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


def pinned(success: bool, margin: int, effective: int):
    """A resolver that forces the outcome, so the payout is deterministic."""
    return lambda obj, skill, mod: CheckResult(
        success=success, margin=margin, roll=6, effective=effective)


@pytest.fixture
def bay():
    sim = Simulator()
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
    builder.add_tag("builder")
    builder.add_tag("admin")          # owns the press that pays out
    yield sim, builder
    set_check_resolver(None)
    sim.close()


async def run_build(sim, builder):
    for line in build_lines(DOC):
        # submit_line (not do): real input path, so '''-heredoc blocks
        # accumulate; one-liners dispatch identically.
        await sim.submit_line(builder, line)
    out = "\n".join(sim.seen(builder))
    for flag in BUILD_RED_FLAGS:
        assert flag not in out, f"{DOC} build tripped {flag!r}:\n{out}"


def crew(sim, room):
    """A trained technician and an equally clever untrained deckhand."""
    vex = sim.player("Vex", location=room)
    vex.db.set("intelligence", 12)
    vex.db.set("skill_diagnostics", 14)
    doss = sim.player("Doss", location=room)
    doss.db.set("intelligence", 12)
    return vex, doss


@pytest.mark.asyncio
class TestAddASkill:

    async def test_defining_the_skill_changes_what_untrained_means(self, bay):
        """The headline claim: an undefined skill is a flat 5 for everyone,
        while a defined one answers to the character's characteristic."""
        sim, builder = bay
        await run_build(sim, builder)
        vex, doss = crew(sim, builder.location)

        from realm.core.checks import skill_level
        assert skill_level(vex, "diagnostics") == 14      # trained
        assert skill_level(doss, "diagnostics") == 8      # 12 int, -4 penalty
        assert skill_level(doss, "zzz_undefined") == 5    # the flat floor

    async def test_the_skill_def_carries_stat_and_penalty(self, bay):
        sim, builder = bay
        await run_build(sim, builder)
        skill = sim.store.find_cached(name="diagnostics")[0]
        assert skill.has_tag("skill_def")
        assert skill.db.get("stat") == "intelligence"
        assert skill.db.get("penalty") == -4

    async def test_detail_line_is_per_viewer(self, bay):
        """The passive half: the coupling shows its tell to a trained eye."""
        sim, builder = bay
        await run_build(sim, builder)
        vex, doss = crew(sim, builder.location)

        sim.seen(vex)
        await sim.submit_line(vex, "look battered coupling")
        assert "induction rings" in "\n".join(sim.seen(vex))

        sim.seen(doss)
        await sim.submit_line(doss, "look battered coupling")
        assert "induction rings" not in "\n".join(sim.seen(doss))

    async def test_press_refuses_uncertified_stock(self, bay):
        sim, builder = bay
        await run_build(sim, builder)
        vex, _ = crew(sim, builder.location)

        sim.seen(vex)
        await sim.submit_line(vex, "reclaim battered coupling")
        assert "certified stock only" in "\n".join(sim.seen(vex))
        assert sim.store.find_cached(name="battered coupling"), "part survived"

    async def test_good_reading_certifies_true_grade_and_pays(self, bay):
        sim, builder = bay
        await run_build(sim, builder)
        vex, _ = crew(sim, builder.location)

        set_check_resolver(pinned(True, 5, 14))
        sim.seen(vex)
        await sim.submit_line(vex, "diagnose battered coupling")
        assert "grade 3" in "\n".join(sim.seen(vex))

        sim.seen(vex)
        await sim.submit_line(vex, "reclaim battered coupling")
        assert "120 credits" in "\n".join(sim.seen(vex))
        assert vex.db.get("credits") == 120
        assert not sim.store.find_cached(name="battered coupling")

    async def test_bad_reading_costs_the_seller(self, bay):
        """A failed check still certifies, just at the lowest grade, so a
        poor technician loses money rather than blocking the trade."""
        sim, builder = bay
        await run_build(sim, builder)
        vex, _ = crew(sim, builder.location)

        set_check_resolver(pinned(False, -3, 14))
        sim.seen(vex)
        await sim.submit_line(vex, "diagnose battered coupling")
        assert "as scrap" in "\n".join(sim.seen(vex))

        sim.seen(vex)
        await sim.submit_line(vex, "reclaim battered coupling")
        assert "40 credits" in "\n".join(sim.seen(vex))

    async def test_scanner_declines_things_that_are_not_salvage(self, bay):
        sim, builder = bay
        await run_build(sim, builder)
        vex, _ = crew(sim, builder.location)

        sim.seen(vex)
        await sim.submit_line(vex, "diagnose hand scanner")
        assert "is not salvage" in "\n".join(sim.seen(vex))
