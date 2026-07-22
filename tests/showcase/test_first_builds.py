"""
Showcase arc "First builds" — checklist items 5, 1, 2, 14, 25.

Verifies the tutorials in docs/showcase/ (005_magic_8ball.md,
001_slot_machine.md, 002_vending_machine.md, 014_basic_container.md,
025_lockable_door.md) by driving a real in-process world — the
realm.testing.Simulator wires the same store/propagation/scripting/
dispatcher stack a live GameServer does — with the tutorials' EXACT
command lines (raw input in, session output out).

The build transcripts are READ OUT OF the docs' "Build it" sections at
collection time and executed as written — nothing is transcribed here,
so a tutorial and its proof cannot drift apart. Randomness is pinned by
patching random.randint (the one source both rand() and dice() draw
from), the same trick the infiltration tests use with the check
resolver.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from realm.core.economy import get_credits
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
    """Every command line in a section's ```text fenced blocks."""
    lines: list[str] = []
    for block in re.findall(r"```text\n(.*?)```", section, re.S):
        lines.extend(line for line in block.splitlines() if line.strip())
    return lines


def build_lines(doc_name: str) -> list[str]:
    """Every command line in the tutorial's "Build it" fenced blocks."""
    lines = lines_in(build_section(doc_name))
    assert lines, f"{doc_name}: empty Build it"
    return lines


@pytest.fixture
def sim():
    s = Simulator()
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


def workshop_and_builder(sim):
    """The standing start of every tutorial: a room and a builder in it."""
    room = sim.room("The Workshop")
    bilda = sim.player("Bilda", location=room)
    bilda.add_tag("builder")
    return room, bilda


async def build(sim, player, lines):
    """Run a Build-it transcript; fail loudly if any line misfires."""
    for line in lines:
        await sim.do(player, line)
        out = "\n".join(sim.seen(player))
        for marker in BUILD_FAILURE_MARKERS:
            assert marker not in out, f"build line {line!r} failed: {out!r}"


async def do(sim, player, line):
    """Run one command and return everything the player saw."""
    await sim.do(player, line)
    return sim.seen(player)


def find_one(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no object named {name!r} in the world"
    return matches[0]


# =========================================================================
# 005. Magic 8-ball — docs/showcase/005_magic_8ball.md
# =========================================================================

EIGHTBALL_DOC = "005_magic_8ball.md"


def eightball_parts():
    """The tutorial's base build and its "Retheme it with data" coda —
    two stages of one Build-it section, and the tests need them apart
    (the retheme rewrites cmd_shake)."""
    base, marker, retheme = build_section(EIGHTBALL_DOC).partition(
        "### Retheme it with data")
    assert marker, f"{EIGHTBALL_DOC}: no retheme subsection"
    base_lines, retheme_lines = lines_in(base), lines_in(retheme)
    assert base_lines and retheme_lines, f"{EIGHTBALL_DOC}: empty stage"
    return base_lines, retheme_lines


class TestMagic8Ball:

    async def test_shake_answers_from_the_switch_table(self, sim, pinned_rand):
        room, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=room)
        await build(sim, bilda, eightball_parts()[0])
        sim.seen(kess)  # discard build chatter

        pinned_rand["value"] = 3
        out = await do(sim, bilda, "shake")
        assert 'oracle ball says, "Ask again later."' in out
        # Bystanders hear the oracle too — the ball speaks to the room.
        assert 'oracle ball says, "Ask again later."' in sim.seen(kess)

    async def test_shake_falls_through_to_the_default_answer(
            self, sim, pinned_rand):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, eightball_parts()[0])

        pinned_rand["value"] = 8  # no case 8 in the table -> default
        out = await do(sim, bilda, "shake")
        assert 'oracle ball says, "The fluid clouds. No answer comes."' in out

    async def test_retheme_reads_the_answers_attribute(self, sim, pinned_rand):
        _room, bilda = workshop_and_builder(sim)
        base, retheme = eightball_parts()
        await build(sim, bilda, base)
        await build(sim, bilda, retheme)

        pinned_rand["value"] = 2  # index 2 of the 3-answer list
        out = await do(sim, bilda, "shake")
        assert "oracle ball trembles in Bilda's grip." in out
        assert 'oracle ball says, "The dice are still rolling."' in out

    async def test_shake_only_works_near_the_ball(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, eightball_parts()[0])
        elsewhere = sim.room("Elsewhere")
        remote = sim.player("Remy", location=elsewhere)
        out = await do(sim, remote, "shake")
        # Not in the search path (room contents/room/inventory/zone), so
        # the trigger never fires (a live server answers "Huh?").
        assert not any("oracle ball says" in line for line in out)


# =========================================================================
# 001. Slot machine — docs/showcase/001_slot_machine.md
# =========================================================================

SLOT_DOC = "001_slot_machine.md"

# The payout table as documented: weight -> prize on a 10-credit stake.
SLOT_TABLE = {250: 1, 50: 4, 20: 10, 10: 20, 0: 65}


class TestSlotMachine:

    async def test_documented_house_edge_is_a_real_house_edge(self):
        """Expected return must stay under the 10-credit stake."""
        total_weight = sum(SLOT_TABLE.values())
        assert total_weight == 100
        expected = sum(p * w for p, w in SLOT_TABLE.items()) / total_weight
        assert expected == 8.5  # 85% return — the documented 15% edge
        assert expected < 10

    async def test_full_session_stake_jackpot_refund_and_bust(
            self, sim, pinned_rand):
        room, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=room)
        await build(sim, bilda, build_lines(SLOT_DOC))
        machine = find_one(sim, "slot machine")
        assert get_credits(machine) == 500  # the float

        # Pocket money for the player (tutorial line).
        await build(sim, bilda, ["@eval adjust_credits(me, 120); "
                                 "result = credits(me)"])
        out = await do(sim, bilda, "credits")
        assert "You are carrying 120 credits." in out

        # Pull without staking: refused, nothing moves.
        out = await do(sim, bilda, "pull")
        assert ("The lever will not budge. Stake a pull first: "
                "pay 10 to slot machine." in out)
        assert get_credits(bilda) == 120

        # Stake and hit the jackpot (roll pinned to 1).
        out = await do(sim, bilda, "pay 10 to slot machine")
        assert "Clunk. The lever unlocks: type pull." in out
        assert get_credits(bilda) == 110
        assert get_credits(machine) == 510

        sim.seen(kess)
        pinned_rand["value"] = 1
        out = await do(sim, bilda, "pull")
        assert "[ NOVA : NOVA : NOVA ]" in out
        assert "Payout! 250 credits rattle into the tray." in out
        assert get_credits(bilda) == 360
        assert get_credits(machine) == 260
        # The room watches you play (oemit excludes the actor).
        kess_saw = sim.seen(kess)
        assert "Bilda pulls the lever. The reels clatter." in kess_saw

        # Underpaying is refunded in full.
        out = await do(sim, bilda, "pay 3 to slot machine")
        assert "A pull costs 10 credits. Coins returned." in out
        assert get_credits(bilda) == 360
        assert get_credits(machine) == 260

        # Stake again and bust (roll pinned to 100).
        await do(sim, bilda, "pay 10 to slot machine")
        pinned_rand["value"] = 100
        out = await do(sim, bilda, "pull")
        assert "[ ---- : ---- : ---- ]" in out
        assert "The reels settle on nothing. The house smiles." in out
        assert get_credits(bilda) == 350
        assert get_credits(machine) == 270

        # The living description reads the hopper.
        out = await do(sim, bilda, "look slot machine")
        assert any("The hopper holds 270 credits." in line for line in out)

    async def test_stake_is_consumed_one_pull_per_payment(
            self, sim, pinned_rand):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, build_lines(SLOT_DOC))
        await build(sim, bilda, ["@eval adjust_credits(me, 120); "
                                 "result = credits(me)"])
        await do(sim, bilda, "pay 10 to slot machine")
        pinned_rand["value"] = 100
        await do(sim, bilda, "pull")
        out = await do(sim, bilda, "pull")   # second pull: stake is spent
        assert ("The lever will not budge. Stake a pull first: "
                "pay 10 to slot machine." in out)


# =========================================================================
# 002. Vending machine — docs/showcase/002_vending_machine.md
# =========================================================================

VENDING_DOC = "002_vending_machine.md"


class TestVendingMachine:

    async def test_browse_lists_prices_and_stock(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, build_lines(VENDING_DOC))
        out = await do(sim, bilda, "browse")
        joined = "\n".join(out)
        assert "Selections (pay first, then vend <selection>):" in joined
        assert "coffee - 25 cr - bulb of cold coffee (5 left)" in joined
        assert "ration - 40 cr - vacuum-sealed ration (2 left)" in joined

    async def test_pay_then_vend_dispenses_a_spawned_item(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, build_lines(VENDING_DOC))
        await build(sim, bilda, ["@eval adjust_credits(me, 200); "
                                 "result = credits(me)"])

        # No credit yet: told exactly what to feed it.
        out = await do(sim, bilda, "vend coffee")
        assert ("CREDIT 0 of 25. Feed it: pay 25 to vending machine."
                in out)

        out = await do(sim, bilda, "pay 25 to vending machine")
        assert "The display blinks. CREDIT: 25. Type vend <selection>." in out

        # The living description shows YOUR credit.
        out = await do(sim, bilda, "look vending machine")
        assert any("The display reads CREDIT: 25." in line for line in out)

        out = await do(sim, bilda, "vend coffee")
        assert ("The vending machine whirs and drops a bulb of cold "
                "coffee into the tray." in out)

        # The product is a real object in the room, with the weight attr
        # the container tutorial (014) will weigh.
        bulb = find_one(sim, "bulb of cold coffee")
        assert bulb.location is room
        assert bulb.db.get("weight") == 1

        out = await do(sim, bilda, "get bulb of cold coffee")
        assert "You pick up a bulb of cold coffee." in out
        assert bulb.location is bilda

        # Stock decremented; credit spent.
        out = await do(sim, bilda, "browse")
        assert any("coffee - 25 cr" in line and "(4 left)" in line
                   for line in out)

    async def test_unknown_selection_and_sell_out(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, build_lines(VENDING_DOC))
        await build(sim, bilda, ["@eval adjust_credits(me, 200); "
                                 "result = credits(me)"])

        out = await do(sim, bilda, "vend gruel")
        assert "The panel blinks: NO SUCH SELECTION. Try browse." in out

        await do(sim, bilda, "pay 80 to vending machine")
        await do(sim, bilda, "vend ration")
        out = await do(sim, bilda, "vend ration")
        assert ("The vending machine whirs and drops a vacuum-sealed "
                "ration into the tray." in out)
        out = await do(sim, bilda, "vend ration")
        assert "The ration coil is empty. SOLD OUT." in out

        machine = find_one(sim, "vending machine")
        assert get_credits(machine) == 80
        assert get_credits(bilda) == 120


# =========================================================================
# 014. Basic container — docs/showcase/014_basic_container.md
# =========================================================================

SACK_DOC = "014_basic_container.md"


class TestBasicContainer:

    async def _built(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, build_lines(SACK_DOC))
        sack = find_one(sim, "canvas sack")
        return room, bilda, sack

    async def test_weight_ward_blocks_the_overload(self, sim):
        _room, bilda, sack = await self._built(sim)

        out = await do(sim, bilda, "put pebble in canvas sack")
        assert "You put a pebble in the canvas sack." in out
        assert "The canvas sack now holds 1 of 3 items." in out

        out = await do(sim, bilda, "put brick in canvas sack")
        assert "The canvas sack now holds 2 of 3 items." in out

        # 5 lbs in, 8 more would burst the 10 lb limit: block(), with math.
        out = await do(sim, bilda, "put lead ingot in canvas sack")
        assert ("At 8 lbs that would overload the canvas sack "
                "(5 of 10 lbs used)." in out)
        ingot = find_one(sim, "lead ingot")
        assert ingot.location is bilda, "blocked put must not move the item"
        assert len(sack.contents) == 2

    async def test_count_ward_blocks_the_fourth_item(self, sim):
        _room, bilda, sack = await self._built(sim)
        await do(sim, bilda, "put pebble in canvas sack")
        await do(sim, bilda, "put brick in canvas sack")
        await do(sim, bilda, "put bottle cap in canvas sack")

        out = await do(sim, bilda, "put rusty spoon in canvas sack")
        assert "The canvas sack is stuffed full - 3 items is its limit." in out
        assert len(sack.contents) == 3

        # The living description counts the load.
        out = await do(sim, bilda, "look canvas sack")
        assert any("It bulges around 3 items." in line for line in out)

    async def test_closed_sack_refuses_both_directions(self, sim):
        _room, bilda, sack = await self._built(sim)
        await do(sim, bilda, "put pebble in canvas sack")

        out = await do(sim, bilda, "close canvas sack")
        assert "You close the canvas sack." in out

        out = await do(sim, bilda, "put brick in canvas sack")
        assert "canvas sack is closed." in "\n".join(out)
        out = await do(sim, bilda, "get pebble from canvas sack")
        assert "canvas sack is closed." in "\n".join(out)

        out = await do(sim, bilda, "open canvas sack")
        assert "You open the canvas sack." in out
        out = await do(sim, bilda, "get pebble from canvas sack")
        assert "You pick up a pebble." in out
        assert len(sack.contents) == 0


# =========================================================================
# 025. Lockable door — docs/showcase/025_lockable_door.md
# =========================================================================

DOOR_DOC = "025_lockable_door.md"


def door_wiring_lines():
    """The build up to and including the @eval that pairs the two faces —
    everything the wiring test needs, and no more."""
    lines = build_lines(DOOR_DOC)
    cut = next(i for i, l in enumerate(lines) if l.startswith("@eval"))
    return lines[:cut + 1]


def door_sides(sim, workshop):
    vault = find_one(sim, "The Vault")
    side_a = next(o for o in workshop.contents if o.has_tag("exit"))
    side_b = next(o for o in vault.contents if o.has_tag("exit"))
    return vault, side_a, side_b


def door_state(exit_obj):
    return (exit_obj.has_tag("closed"), exit_obj.has_tag("locked"))


class TestLockableDoor:

    async def _built(self, sim):
        """Run the tutorial's whole transcript. It wires side A, walks
        into the vault, configures side B with the same six lines, and
        walks back — so the builder ends in the workshop, key in hand."""
        workshop, bilda = workshop_and_builder(sim)
        await build(sim, bilda, build_lines(DOOR_DOC))
        assert bilda.location is workshop
        vault, side_a, side_b = door_sides(sim, workshop)
        return workshop, vault, bilda, side_a, side_b

    async def test_wiring_reports_both_sides(self, sim):
        workshop, bilda = workshop_and_builder(sim)
        wiring = door_wiring_lines()
        await sim.do(bilda, wiring[0])
        out = sim.seen(bilda)
        assert any("Room created: The Vault" in line for line in out)
        for line in wiring[1:]:
            await sim.do(bilda, line)
        out = sim.seen(bilda)
        assert any("both sides wired" in line for line in out)
        _vault, side_a, side_b = door_sides(sim, workshop)
        assert side_a.db.get("partner") == "#" + side_b.id
        assert side_b.db.get("partner") == "#" + side_a.id

    async def test_close_and_lock_mirror_to_the_far_side(self, sim):
        workshop, vault, bilda, side_a, side_b = await self._built(sim)

        out = await do(sim, bilda, "close vault door")
        assert "You close the vault door." in out
        assert door_state(side_a) == (True, False)
        assert door_state(side_b) == (True, False), "far side must agree"

        out = await do(sim, bilda, "lock vault door")
        assert "You lock vault door with brass key." in out
        assert door_state(side_a) == (True, True)
        assert door_state(side_b) == (True, True), "far side must agree"

        # Walking is refused by the closed door; opening by the lock.
        out = await do(sim, bilda, "vault door")
        assert "The vault door is closed." in out
        assert bilda.location is workshop
        out = await do(sim, bilda, "open vault door")
        assert "The wheel spins uselessly. Locked tight." in out

        # The key opens the way — and the far side follows every step.
        out = await do(sim, bilda, "unlock vault door")
        assert "You unlock vault door with brass key." in out
        assert door_state(side_a) == (True, False)
        assert door_state(side_b) == (True, False)

        out = await do(sim, bilda, "open vault door")
        assert "You open the vault door." in out
        assert door_state(side_a) == (False, False)
        assert door_state(side_b) == (False, False)

        await do(sim, bilda, "vault door")
        assert bilda.location is vault

    async def test_locking_from_inside_locks_the_workshop_side(self, sim):
        workshop, vault, bilda, side_a, side_b = await self._built(sim)
        kess = sim.player("Kess", location=workshop)

        # The builder walks in and locks up behind them.
        await do(sim, bilda, "vault door")
        assert bilda.location is vault
        await do(sim, bilda, "close vault door")
        await do(sim, bilda, "lock vault door")
        assert door_state(side_a) == (True, True)
        assert door_state(side_b) == (True, True)

        # A keyless visitor on the OTHER side is properly shut out.
        out = await do(sim, kess, "vault door")
        assert "The vault door is closed." in out
        assert kess.location is workshop
        out = await do(sim, kess, "open vault door")
        assert "The wheel spins uselessly. Locked tight." in out
        out = await do(sim, kess, "unlock vault door")
        assert "You don't have the key." in out
