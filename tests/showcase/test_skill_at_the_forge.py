"""Showcase verification — item 253, a skill learned at the forge.

Two skills improve two different ways in one game: ``smithing`` by use (the
forge's ``check_roll``) and ``metallurgy`` by idle study. The doc IS the
test input: the Build-it transcript is read from the markdown.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from realm.core.dice import CheckResult
from realm.std.rules.checks import checks, skill_level
from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"
DOC = "253_skill_at_the_forge.md"
BUILD_RED_FLAGS = ("Unknown command", "Script error", "Syntax error",
                   "Traceback", "not defined", "Usage:")


def build_lines() -> list[str]:
    body = (DOCS / DOC).read_text()
    match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
    assert match, "no Build it section"
    lines: list[str] = []
    for block in re.findall(r"```text\n(.*?)```", match.group(1), re.S):
        lines.extend(line for line in block.splitlines() if line.strip())
    return lines


@pytest.fixture
def clocks(monkeypatch):
    now = [2_000_000.0]
    monkeypatch.setattr("realm.std.tasks.tasks.now", lambda: now[0])
    monkeypatch.setattr("realm.std.rules.progression.now", lambda: now[0])
    return now


@pytest.fixture
async def smithy(clocks):
    sim = Simulator()
    limbo = sim.room("Limbo")
    bob = sim.player("Bob", location=limbo, dexterity=10, intelligence=12, wisdom=11)
    bob.add_tag("builder")
    for line in build_lines():
        await sim.submit_line(bob, line)
    out = "\n".join(sim.seen(bob))
    for flag in BUILD_RED_FLAGS:
        assert flag not in out, f"{DOC} build tripped {flag!r}:\n{out}"
    try:
        yield sim, bob, clocks
    finally:
        sim.close()


def _always(success: bool):
    checks().resolver = lambda obj, skill, mod: CheckResult(
        success=success, margin=1 if success else -1, roll=8, effective=10, skill=skill)


async def _forge_a_nail(sim, bob, clock):
    from realm.std.tasks.tasks import task_sweep
    await sim.do(bob, "forge nail")
    clock[0] += 6
    await task_sweep(sim.store)
    return "\n".join(sim.seen(bob))


async def test_forging_raises_smithing_by_use(smithy):
    sim, bob, clock = smithy
    assert bob.location.name == "Smithy"
    start = skill_level(bob, "smithing")             # dexterity 10 - 5
    assert start == 5
    _always(True)
    seen = ""
    for _ in range(10):
        seen += await _forge_a_nail(sim, bob, clock)
        if bob.db.get("skill_smithing"):
            break
    assert bob.db.skill_smithing == start + 1
    assert "hammers out an iron nail" in seen
    assert "You have become better at smithing!" in seen
    assert sim.store.find_cached(name="an iron nail")


async def test_metallurgy_is_studied_over_real_time(smithy):
    sim, bob, clock = smithy
    await sim.do(bob, "study metallurgy")
    assert "You begin studying metallurgy." in sim.seen(bob)
    before = skill_level(bob, "metallurgy")
    clock[0] += 8 * 3600
    await sim.do(bob, "skills")
    out = "\n".join(sim.seen(bob))
    assert bob.db.skill_metallurgy > before
    assert "You have finished training metallurgy" in out
    assert "Training metallurgy" in out


async def test_smithing_cannot_be_studied_and_metallurgy_does_not_learn_by_use(smithy):
    sim, bob, clock = smithy
    await sim.do(bob, "study smithing")
    assert "improves by use" in "\n".join(sim.seen(bob))
    from realm.std.rules.checks import check
    _always(True)
    for _ in range(20):
        check(bob, "metallurgy")
    assert bob.db.get("skill_metallurgy") is None


async def test_walking_off_lets_the_iron_cool(smithy):
    sim, bob, clock = smithy
    from realm.std.tasks.tasks import task_sweep
    await sim.do(bob, "forge nail")
    await sim.do(bob, "out")
    assert "You let the iron cool, unworked." in "\n".join(sim.seen(bob))
    clock[0] += 60
    await task_sweep(sim.store)
    assert not sim.store.find_cached(name="an iron nail")
