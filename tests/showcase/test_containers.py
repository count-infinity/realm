"""
Showcase — Containers, Storage & Item Handling (checklist items 15,
17-24).

Verifies the standalone tutorials docs/showcase/015_locked_chest.md,
017_bag_of_holding.md, 018_refrigerator.md, 019_trash_incinerator.md,
020_bookshelf.md, 021_ammo_pouch.md, 022_coat_check.md,
023_conveyor_belt.md and 024_loot_crate.md by driving a real
in-process world — realm.testing.Simulator wires the same store/
propagation/scripting/dispatcher stack a live GameServer does — with
the tutorials' EXACT command lines (raw input in, session output out).

Every build transcript is read straight out of its markdown's "Build
it" section and driven through the real dispatcher, so a doc edit that
breaks the build breaks this suite — drift is impossible rather than
merely detectable.

Determinism:
- rand() is pinned by patching random.randint (loot crate), the same
  trick the first-builds tests use;
- skill checks (pick) use the level resolver from the heist tests —
  success iff effective skill >= 10;
- script_ticker behaviors are pumped by calling the attached
  behavior's tick() directly (peaches, belts);
- wait() runs on the Simulator's virtual clock (engine.tick_waits());
- expiry is reaped by calling reap_expired() with a synthetic "now"
  past the grace period (trash bin).
"""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest

from realm.core.checks import CheckResult, set_check_resolver, skill_level
from realm.core.events import reap_expired
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


def level_resolver(obj, skill, modifier):
    """Diceless checks: success iff effective skill >= 10 (heist idiom)."""
    effective = skill_level(obj, skill) + modifier
    return CheckResult(success=effective >= 10, margin=effective - 10,
                       roll=10, effective=effective, skill=skill)


def build_lines(doc_name: str) -> list[str]:
    """Every command line in the tutorial's "Build it" fenced blocks."""
    body = (DOCS / doc_name).read_text(encoding="utf-8")
    match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
    assert match, f"{doc_name}: no Build it section"
    lines: list[str] = []
    for block in re.findall(r"```text\n(.*?)```", match.group(1), re.S):
        lines.extend(line for line in block.splitlines() if line.strip())
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
def pinned_checks():
    """Install the diceless skill-check resolver for pick tests."""
    set_check_resolver(level_resolver)
    yield
    set_check_resolver(None)


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


def ticker(obj):
    """The object's attached script_ticker behavior."""
    return next(b for b in obj.get_behaviors()
                if b.behavior_id == "script_ticker")


# =========================================================================
# 015. Locked chest & key — docs/showcase/015_locked_chest.md
# =========================================================================

CHEST_BUILD = build_lines("015_locked_chest.md")


class TestLockedChest:

    async def _built(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, CHEST_BUILD)
        chest = find_one(sim, "sea chest")
        assert chest.has_tag("locked")
        assert chest.has_tag("closed")
        return room, bilda, chest

    async def test_keyless_hands_meet_every_refusal(self, sim, pinned_checks):
        room, _bilda, chest = await self._built(sim)
        kess = sim.player("Kess", location=room, skill_lockpicking=14)

        out = await do(sim, kess, "open sea chest")
        assert "The hasp holds fast. A silver keyhole winks at you." in out
        out = await do(sim, kess, "unlock sea chest")
        assert "You don't have the key." in out

        # Improvised picking (no tools): 14 - 2 - 5 = 7 < 10.
        out = await do(sim, kess, "pick sea chest")
        assert "The lock on sea chest resists your attempt." in out
        assert chest.has_tag("locked")

        # With lockpicks: 14 - 2 = 12 >= 10.
        sim.obj("lockpick set", location=kess, tags=["thing", "lockpicks"])
        out = await do(sim, kess, "pick sea chest")
        assert "Click. You defeat the lock on sea chest." in out
        assert not chest.has_tag("locked")

    async def test_key_cycle_and_the_audible_unlock(self, sim):
        room, bilda, chest = await self._built(sim)
        kess = sim.player("Kess", location=room)

        out = await do(sim, bilda, "unlock sea chest")
        assert "You unlock sea chest with silver key." in out
        # The ON_UNLOCK reaction is room-audible.
        assert "The lock springs with a bright click." in out
        assert "The lock springs with a bright click." in sim.seen(kess)

        out = await do(sim, bilda, "open sea chest")
        assert "You open the sea chest." in out
        out = await do(sim, bilda, "get string of pearls from sea chest")
        assert "You pick up a string of pearls." in out
        pearls = find_one(sim, "string of pearls")
        assert pearls.location is bilda

        out = await do(sim, bilda, "close sea chest")
        assert "You close the sea chest." in out
        out = await do(sim, bilda, "lock sea chest")
        assert "You lock sea chest with silver key." in out
        assert chest.has_tag("locked")

    async def test_keycard_fast_path_fires_the_unlock_event(self, sim):
        """The swipe path speaks the same language as `unlock`: it fires
        the gated ON_UNLOCK event, so reactions hear a keycard exactly
        like a turned key (the formerly-filed silent-fast-path gap)."""
        _room, bilda, chest = await self._built(sim)

        out = await do(sim, bilda, "use silver key on sea chest")
        assert "You swipe silver key: sea chest unlocks." in out
        assert not chest.has_tag("locked")
        assert any("bright click" in line for line in out)

        out = await do(sim, bilda, "use silver key on sea chest")
        assert "You swipe silver key: sea chest locks." in out
        assert chest.has_tag("locked")


# =========================================================================
# 017. Bag of holding — docs/showcase/017_bag_of_holding.md
# =========================================================================

BAG_BUILD = build_lines("017_bag_of_holding.md")


class TestBagOfHolding:

    async def test_honest_aggregation_blocks_the_smuggle(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BAG_BUILD)

        out = await do(sim, bilda, "weigh iron anvil")
        assert "The needle settles at 12 lbs." in out

        # The duffel has no override: it weighs what it holds.
        await do(sim, bilda, "put iron anvil in canvas duffel")
        out = await do(sim, bilda, "weigh canvas duffel")
        assert "The needle settles at 12 lbs." in out

        out = await do(sim, bilda, "put canvas duffel in porter's satchel")
        assert ("At 12 lbs that would overload the porter's satchel "
                "(0 of 10 lbs used)." in out)
        duffel = find_one(sim, "canvas duffel")
        assert duffel.location is bilda, "blocked put must not move the item"

    async def test_carry_weight_override_launders_the_anvil(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BAG_BUILD)
        await do(sim, bilda, "put iron anvil in canvas duffel")
        await do(sim, bilda, "put canvas duffel in porter's satchel")

        await do(sim, bilda, "get iron anvil from canvas duffel")
        out = await do(sim, bilda, "put iron anvil in bag of holding")
        assert any("You put" in line and "iron anvil" in line
                   for line in out)

        # The fold takes the override clause: shell weight only.
        out = await do(sim, bilda, "weigh bag of holding")
        assert "The needle settles at 2 lbs." in out

        # The living description still counts the hidden cargo.
        out = await do(sim, bilda, "look bag of holding")
        assert any("It holds 1 item and hangs like an empty purse "
                   "regardless." in line for line in out)

        # And the ward honors the same convention.
        out = await do(sim, bilda, "put bag of holding in porter's satchel")
        assert any("You put a bag of holding in the porter's satchel"
                   in line for line in out)
        out = await do(sim, bilda, "weigh porter's satchel")
        assert "The needle settles at 2 lbs." in out

        # Nothing lied about the anvil itself.
        anvil = find_one(sim, "iron anvil")
        assert anvil.db.get("weight") == 12


# =========================================================================
# 018. Refrigerator — docs/showcase/018_refrigerator.md
# =========================================================================

FRIDGE_BUILD = build_lines("018_refrigerator.md")


class TestRefrigerator:

    async def test_cold_slows_the_clock(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, FRIDGE_BUILD)
        counter = find_one(sim, "ripe peach")
        chilled = find_one(sim, "twin peach")
        icebox = find_one(sim, "icebox")
        assert counter.location is room
        assert chilled.location is icebox

        out = await do(sim, bilda, "look ripe peach")
        assert any("Bursting with juice." in line for line in out)

        # Four heartbeats: counter peach at 2, description turns.
        for _ in range(4):
            await ticker(counter).tick(counter, 4.0)
            await ticker(chilled).tick(chilled, 4.0)
        assert counter.db.get("freshness") == 2
        out = await do(sim, bilda, "look ripe peach")
        assert any("Going soft and winey." in line for line in out)

        # Two more: the counter peach dies where it lies...
        for _ in range(2):
            await ticker(counter).tick(counter, 4.0)
            await ticker(chilled).tick(chilled, 4.0)
        assert sim.store.get_cached(counter.id) is None
        assert ("The ripe peach collapses into a slick of brown mush."
                in sim.seen(bilda))
        mush = find_one(sim, "a slick of brown mush")
        assert mush.location is room

        # ...while the icebox twin spent the same six ticks at 1/4 rate.
        assert chilled.db.get("freshness") == 4.5
        await do(sim, bilda, "get twin peach from icebox")
        out = await do(sim, bilda, "look twin peach")
        assert any("Bursting with juice." in line for line in out)

    async def test_rate_follows_the_holder(self, sim):
        """Carried fruit rots at full speed: loc(me) is the player, who
        publishes no decay_rate — default 1."""
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, FRIDGE_BUILD)
        chilled = find_one(sim, "twin peach")
        await do(sim, bilda, "get twin peach from icebox")
        await ticker(chilled).tick(chilled, 4.0)
        assert chilled.db.get("freshness") == 5
        await do(sim, bilda, "put twin peach in icebox")
        await ticker(chilled).tick(chilled, 4.0)
        assert chilled.db.get("freshness") == 4.75


# =========================================================================
# 019. Trash bin / incinerator — docs/showcase/019_trash_incinerator.md
# =========================================================================

BIN_BUILD = build_lines("019_trash_incinerator.md")


class TestTrashIncinerator:

    async def test_grace_lease_rescue_and_purge(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BIN_BUILD)
        peel = find_one(sim, "banana peel")
        hourglass = find_one(sim, "broken hourglass")
        bin_ = find_one(sim, "rubbish bin")

        out = await do(sim, bilda, "put banana peel in rubbish bin")
        assert ("It lands with a clang. You have 60 seconds to change "
                "your mind: rummage <item>." in out)
        # The sweep is deferred one beat; the lease lands on the pump.
        assert peel.db.get("expires_at") is None
        await sim.engine.tick_waits()
        assert peel.db.get("expires_at") is not None

        # The pardon: timestamp gone, item back in hand.
        out = await do(sim, bilda, "rummage banana")
        assert "You fish the banana peel back out. Reprieved." in out
        assert peel.location is bilda
        assert peel.db.get("expires_at") is None
        out = await do(sim, bilda, "rummage banana")
        assert "You paw through the muck and come up empty." in out

        # Commit both. Within the grace period nothing burns.
        await do(sim, bilda, "put banana peel in rubbish bin")
        await do(sim, bilda, "put broken hourglass in rubbish bin")
        await sim.engine.tick_waits()
        assert await reap_expired(sim.store, now=time.time()) == 0
        assert peel.location is bin_

        # Past the grace period: both reaped, and the bin narrates each.
        sim.seen(bilda)
        reaped = await reap_expired(sim.store, now=time.time() + 61)
        assert reaped == 2
        assert sim.store.get_cached(peel.id) is None
        assert sim.store.get_cached(hourglass.id) is None
        flames = [line for line in sim.seen(bilda)
                  if "The bin belches a gout of flame." in line]
        assert len(flames) == 2
        assert len(bin_.contents) == 0

    async def test_rethrow_restarts_the_sentence(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BIN_BUILD)
        peel = find_one(sim, "banana peel")

        await do(sim, bilda, "put banana peel in rubbish bin")
        await sim.engine.tick_waits()
        first = peel.db.get("expires_at")
        await do(sim, bilda, "rummage banana peel")
        await do(sim, bilda, "put banana peel in rubbish bin")
        await sim.engine.tick_waits()
        assert peel.db.get("expires_at") >= first  # a fresh 60s lease


# =========================================================================
# 020. Bookshelf — docs/showcase/020_bookshelf.md
# =========================================================================

SHELF_BUILD = build_lines("020_bookshelf.md")


class TestBookshelf:

    async def test_browse_lists_titles_sorted_and_ignores_the_mitten(
            self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, SHELF_BUILD)

        out = await do(sim, bilda, "browse")
        joined = "\n".join(out)
        assert "Spines on the shelf:" in joined
        assert "1. An Atlas of Drowned Coasts" in joined
        assert "2. Ninety Soups" in joined
        assert "3. The Gullwater Wreck" in joined
        assert "mitten" not in joined

        # The description runs the same book-only filter.
        out = await do(sim, bilda, "look walnut bookshelf")
        assert any("3 volumes stand in a ragged row." in line
                   for line in out)

    async def test_index_renumbers_when_a_book_leaves(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, SHELF_BUILD)
        await do(sim, bilda, "get thick cookbook from walnut bookshelf")

        out = await do(sim, bilda, "browse")
        joined = "\n".join(out)
        assert "1. An Atlas of Drowned Coasts" in joined
        assert "2. The Gullwater Wreck" in joined
        assert "Ninety Soups" not in joined


# =========================================================================
# 021. Ammo pouch — docs/showcase/021_ammo_pouch.md
# =========================================================================

POUCH_BUILD = build_lines("021_ammo_pouch.md")


class TestAmmoPouch:

    async def test_ammo_slots_in_and_lunch_stays_out(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, POUCH_BUILD)
        pouch = find_one(sim, "ammo pouch")

        out = await do(sim, bilda, "put charge cell in ammo pouch")
        assert "Slotted. The ammo pouch now carries 1 rounds." in out
        out = await do(sim, bilda, "put spare charge cell in ammo pouch")
        assert "Slotted. The ammo pouch now carries 2 rounds." in out

        out = await do(sim, bilda, "put dried fig in ammo pouch")
        assert ("The loops inside the ammo pouch fit ammunition and "
                "nothing else - the dried fig stays out." in out)
        fig = find_one(sim, "dried fig")
        assert fig.location is bilda, "blocked put must not move the item"
        assert len(pouch.contents) == 2

        # Getting back out is not gated.
        out = await do(sim, bilda, "get charge cell from ammo pouch")
        assert "You pick up a charge cell." in out
        assert len(pouch.contents) == 1


# =========================================================================
# 022. Coat check — docs/showcase/022_coat_check.md
# =========================================================================

COAT_BUILD = build_lines("022_coat_check.md")


class TestCoatCheck:

    async def test_deposit_mints_a_paired_ticket(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, COAT_BUILD)
        golem = find_one(sim, "Coat-Check Golem")
        coat = find_one(sim, "wool greatcoat")

        out = await do(sim, bilda, "give wool greatcoat to Coat-Check Golem")
        assert ("The golem stows your wool greatcoat on hook 1 and "
                "punches ticket 1." in out)
        assert coat.location is golem
        assert coat.db.get("checked") == 1
        ticket = find_one(sim, "claim ticket 1")
        assert ticket.location is bilda
        assert ticket.db.get("claim_no") == 1
        # The other half of the pair: the ledger on the master.
        assert golem.db.get("held_1") == "#" + coat.id

    async def test_claim_needs_both_halves(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, COAT_BUILD)
        golem = find_one(sim, "Coat-Check Golem")
        coat = find_one(sim, "wool greatcoat")
        await do(sim, bilda, "give wool greatcoat to Coat-Check Golem")

        # A number with no ticket behind it: brass palms.
        out = await do(sim, bilda, "claim 4")
        assert ("The golem shows you two empty brass palms: no matching "
                "ticket in your hand." in out)
        assert coat.location is golem

        # The real thing: coat back, token destroyed, ledger cleared.
        ticket = find_one(sim, "claim ticket 1")
        out = await do(sim, bilda, "claim 1")
        assert ("The golem lifts your wool greatcoat off hook 1 and "
                "retires the ticket." in out)
        assert coat.location is bilda
        assert coat.db.get("checked") is None
        assert sim.store.get_cached(ticket.id) is None
        assert golem.db.get("held_1") is None

    async def test_numbers_never_recycle_and_strays_bounce(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, COAT_BUILD)
        kess = sim.player("Kess", location=room)
        scarf = sim.obj("knit scarf", location=kess)

        await do(sim, bilda, "give wool greatcoat to Coat-Check Golem")
        await do(sim, bilda, "claim 1")

        # Hook 1 is history; Kess gets hook 2.
        out = await do(sim, kess, "give knit scarf to Coat-Check Golem")
        assert ("The golem stows your knit scarf on hook 2 and punches "
                "ticket 2." in out)

        # Absent-mindedly handing the ticket over just bounces it back.
        ticket = find_one(sim, "claim ticket 2")
        out = await do(sim, kess, "give claim ticket 2 to Coat-Check Golem")
        assert ("The golem taps the ticket and hands it back: just say "
                "claim 2." in out)
        assert ticket.location is kess

        out = await do(sim, kess, "claim 2")
        assert ("The golem lifts your knit scarf off hook 2 and retires "
                "the ticket." in out)
        assert scarf.location is kess


# =========================================================================
# 023. Conveyor belt — docs/showcase/023_conveyor_belt.md
# =========================================================================

BELT_BUILD = build_lines("023_conveyor_belt.md")


class TestConveyorBelt:

    async def test_cargo_rides_the_chain_one_hop_per_tick(self, sim):
        workshop, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BELT_BUILD)
        assert bilda.location is workshop
        kess = sim.player("Kess", location=workshop)

        alpha = find_one(sim, "belt alpha")
        beta = find_one(sim, "belt beta")
        dock = find_one(sim, "Loading Dock")
        assert alpha.db.get("next_stop") == "#" + beta.id
        assert beta.db.get("next_stop") == "#" + dock.id

        await do(sim, bilda, "@create crate of gears")
        await do(sim, bilda, "put crate of gears in belt alpha")
        crate = find_one(sim, "crate of gears")
        assert crate.location is alpha

        # Hop one: workshop hears the clatter, crate lands on beta.
        sim.seen(kess)
        await ticker(alpha).tick(alpha, 4.0)
        assert crate.location is beta
        assert ("The belt clatters; the cargo slides out of sight."
                in sim.seen(kess))

        # Hop two: the last segment dumps onto the dock floor.
        await ticker(beta).tick(beta, 4.0)
        assert crate.location is dock

        # Idle belts stay quiet — no cargo, no clatter.
        sim.seen(kess)
        await ticker(alpha).tick(alpha, 4.0)
        assert not any("clatters" in line for line in sim.seen(kess))

    async def test_two_crates_ride_in_order(self, sim):
        workshop, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BELT_BUILD)
        alpha = find_one(sim, "belt alpha")
        beta = find_one(sim, "belt beta")
        dock = find_one(sim, "Loading Dock")

        await do(sim, bilda, "@create crate of gears")
        await do(sim, bilda, "put crate of gears in belt alpha")
        crate1 = find_one(sim, "crate of gears")
        await ticker(alpha).tick(alpha, 4.0)

        await do(sim, bilda, "@create drum of oil")
        await do(sim, bilda, "put drum of oil in belt alpha")
        crate2 = find_one(sim, "drum of oil")

        # Pump downstream-first, like the server's single heartbeat:
        # each beat, every belt hands its cargo one hop onward.
        await ticker(beta).tick(beta, 4.0)
        await ticker(alpha).tick(alpha, 4.0)
        assert crate1.location is dock
        assert crate2.location is beta
        await ticker(beta).tick(beta, 4.0)
        assert crate2.location is dock


# =========================================================================
# 024. Loot crate — docs/showcase/024_loot_crate.md
# =========================================================================

CRATE_BUILD = build_lines("024_loot_crate.md")

# The documented odds: name -> weight, summing to 100.
CRATE_TABLE = {"a rusty gear": 60, "a sealed med kit": 30,
               "a plasma core": 10}


class TestLootCrate:

    async def test_documented_weights_sum_to_a_full_wheel(self):
        assert sum(CRATE_TABLE.values()) == 100

    async def test_first_open_seeds_from_the_table_tail(
            self, sim, pinned_rand):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, CRATE_BUILD)
        crate = find_one(sim, "supply crate")

        # 100 walks past 60 and 30 into the 10-weight tail entry.
        pinned_rand["value"] = 100
        out = await do(sim, bilda, "open supply crate")
        assert ("Something rattles and settles inside the crate as the "
                "seal breaks." in out)
        assert "You open the supply crate." in out
        assert [o.name for o in crate.contents] == [
            "a plasma core", "a plasma core"]
        assert crate.db.get("seeded") == 1

    async def test_middle_weights_and_the_one_shot_flag(
            self, sim, pinned_rand):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, CRATE_BUILD)
        crate = find_one(sim, "supply crate")

        # 61 skips the 60-weight gear and lands in the med kit band.
        pinned_rand["value"] = 61
        await do(sim, bilda, "open supply crate")
        assert [o.name for o in crate.contents] == [
            "a sealed med kit", "a sealed med kit"]

        # Loot, close, reopen: the depot only packs a crate once.
        await do(sim, bilda, "get sealed med kit from supply crate")
        await do(sim, bilda, "close supply crate")
        pinned_rand["value"] = 1
        out = await do(sim, bilda, "open supply crate")
        assert not any("rattles and settles" in line for line in out)
        assert [o.name for o in crate.contents] == ["a sealed med kit"]
