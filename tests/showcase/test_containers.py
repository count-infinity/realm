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

The build transcripts below are copied verbatim from the docs' "Build
it" sections; a sync test at the bottom keeps them from drifting.

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

import time
from pathlib import Path

import pytest

from realm.core.checks import CheckResult, set_check_resolver, skill_level
from realm.core.events import reap_expired
from realm.testing import Simulator

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

CHEST_BUILD = [
    "@create sea chest",
    "@set sea chest/container = true",
    "drop sea chest",
    "@create string of pearls",
    "put string of pearls in sea chest",
    "close sea chest",
    "@set sea chest/key_id = chest_silver",
    "@set sea chest/locked_msg = The hasp holds fast. A silver keyhole "
    "winks at you.",
    "@set sea chest/lock_skill = lockpicking",
    "@set sea chest/lock_difficulty = 2",
    "@set sea chest/on_unlock = remit(loc(me), 'The lock springs with a "
    "bright click.')",
    "@create silver key",
    "@set silver key/unlocks = chest_silver",
    "lock sea chest",
]


class TestLockedChest:

    async def _built(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, CHEST_BUILD)
        chest = find_one(sim, "sea chest")
        assert chest.db.get("locked") is True
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
        assert chest.db.get("locked") is True

        # With lockpicks: 14 - 2 = 12 >= 10.
        sim.obj("lockpick set", location=kess, tags=["thing", "lockpicks"])
        out = await do(sim, kess, "pick sea chest")
        assert "Click. You defeat the lock on sea chest." in out
        assert chest.db.get("locked") is False

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
        assert chest.db.get("locked") is True

    async def test_keycard_fast_path_toggles_but_stays_silent(self, sim):
        """The filed gap: `use key on chest` toggles locked by direct
        write, so ON_UNLOCK reactions never fire on the swipe path."""
        _room, bilda, chest = await self._built(sim)

        out = await do(sim, bilda, "use silver key on sea chest")
        assert "You swipe silver key: sea chest unlocks." in out
        assert chest.db.get("locked") is False
        assert not any("bright click" in line for line in out)

        out = await do(sim, bilda, "use silver key on sea chest")
        assert "You swipe silver key: sea chest locks." in out
        assert chest.db.get("locked") is True


# =========================================================================
# 017. Bag of holding — docs/showcase/017_bag_of_holding.md
# =========================================================================

BAG_BUILD = [
    "@create cargo scale",
    "drop cargo scale",
    "@desc cargo scale = A freight scale with a brass needle the size of "
    "a sword blade.",
    "@set cargo scale/cmd_weigh = $weigh *: w = lambda w, o: "
    "get_attr(o, 'carry_weight') if has_attr(o, 'carry_weight') else "
    "get_attr(o, 'weight', 0) + sum([w(w, c) for c in contents(o)]); "
    "it = get(trim(arg0)); pemit(enactor, f'The needle settles at "
    "{w(w, it)} lbs.') if it else pemit(enactor, 'Nothing by "
    "that name to weigh.')",
    "@create porter's satchel",
    "@set porter's satchel/container = true",
    "drop porter's satchel",
    "@set porter's satchel/weight_limit = 10",
    "@set porter's satchel/on_check = mine = atype == 'item:on_put' and "
    "target is me; w = lambda w, o: get_attr(o, 'carry_weight') if "
    "has_attr(o, 'carry_weight') else get_attr(o, 'weight', 0) + "
    "sum([w(w, c) for c in contents(o)]); adding = w(w, adata('item')) "
    "if mine else 0; load = w(w, me) if mine else 0; "
    "limit = V('weight_limit', 10); block(f'At {adding} "
    "lbs that would overload the {name(me)} ({load} "
    "of {limit} lbs used).') if mine and load + adding > "
    "limit else None",
    "@create iron anvil",
    "@set iron anvil/weight = 12",
    "@create canvas duffel",
    "@set canvas duffel/container = true",
    "@create bag of holding",
    "@set bag of holding/container = true",
    "@set bag of holding/carry_weight = 2",
    "@desc bag of holding = Plain oiled leather, far too light in the "
    "hand. [[n = len(contents(me)); result = 'It holds ' + str(n) + "
    "' item' + ('' if n == 1 else 's') + ' and hangs like an empty "
    "purse regardless.']]",
]


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

PEACH_TICK = (
    "f = V('freshness', 6) - get_attr(loc(me), 'decay_rate', 1); "
    "set_attr(me, 'freshness', f); (remit(here, f'The {name(me)} "
    "collapses into a slick of brown mush.'), create_obj('a slick of "
    "brown mush', [], loc(me)), destroy_obj(me)) if f <= 0 else None"
)

FRIDGE_BUILD = [
    "@create icebox",
    "@set icebox/container = true",
    "drop icebox",
    "@set icebox/decay_rate = 0.25",
    "@desc icebox = An enameled chest humming to itself. Frost feathers "
    "the seams.",
    "@create ripe peach",
    "@set ripe peach/freshness = 6",
    "@desc ripe peach = [[f = V('freshness', 6); result = "
    "'Bursting with juice.' if f > 4 else ('Going soft and winey.' "
    "if f > 0 else 'Compost.')]]",
    "@set ripe peach/on_tick = " + PEACH_TICK,
    "@behavior ripe peach = script_ticker, interval:1",
    "@create twin peach",
    "@set twin peach/freshness = 6",
    "@desc twin peach = [[f = V('freshness', 6); result = "
    "'Bursting with juice.' if f > 4 else ('Going soft and winey.' "
    "if f > 0 else 'Compost.')]]",
    "@set twin peach/on_tick = " + PEACH_TICK,
    "@behavior twin peach = script_ticker, interval:1",
    "drop ripe peach",
    "put twin peach in icebox",
]


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

BIN_BUILD = [
    "@create rubbish bin",
    "@set rubbish bin/container = true",
    "drop rubbish bin",
    "@desc rubbish bin = A dented municipal bin. Stenciled on the lid: "
    "CONTENTS INCINERATED WITHOUT NOTICE.",
    "@set rubbish bin/grace = 60",
    '@set rubbish bin/on_put = pemit(enactor, f"It lands with a clang. '
    "You have {V('grace', 60)} seconds to change "
    "your mind: rummage <item>.\"); wait(0, 'trigger me/do_sweep')",
    "@set rubbish bin/do_sweep = [expire(o, V('grace', 60)) "
    "for o in contents(me) if not has_attr(o, 'expires_at')]",
    "@set rubbish bin/cmd_rummage = $rummage *: found = [o for o in "
    "contents(me) if trim(arg0).lower() in name(o).lower()]; it = "
    "found[0] if found else None; (del_attr(it, 'expires_at'), "
    "teleport_obj(it, enactor), pemit(enactor, f'You fish the "
    "{name(it)} back out. Reprieved.')) if it else pemit(enactor, "
    "'You paw through the muck and come up empty.')",
    "@set rubbish bin/on_expire = remit(loc(me), 'The bin belches a "
    "gout of flame. Something is gone for good.')",
    "@create banana peel",
    "@create broken hourglass",
]


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

SHELF_BUILD = [
    "@create walnut bookshelf",
    "@set walnut bookshelf/container = true",
    "drop walnut bookshelf",
    "@desc walnut bookshelf = A tall walnut case, shelves bowed under "
    "years of paper. [[n = len([o for o in contents(me) if has_tag(o, "
    "'book')]); result = f'{n} volume' + ('' if n == 1 else 's') + "
    "' stand in a ragged row. A card taped to the shelf reads: "
    "BROWSE.']]",
    "@set walnut bookshelf/cmd_browse = $browse: books = sorted([o for "
    "o in contents(me) if has_tag(o, 'book')], key=lambda o: "
    "str(get_attr(o, 'title', name(o))).lower()); pemit(enactor, "
    "'Spines on the shelf:' if books else 'The shelf holds nothing "
    "readable.'); [pemit(enactor, f\"  {i + 1}. "
    "{get_attr(o, 'title', name(o))}\") for i, o in enumerate(books)]",
    "@create dog-eared novel",
    "@tag dog-eared novel = book",
    "@set dog-eared novel/title = The Gullwater Wreck",
    "put dog-eared novel in walnut bookshelf",
    "@create thick cookbook",
    "@tag thick cookbook = book",
    "@set thick cookbook/title = Ninety Soups",
    "put thick cookbook in walnut bookshelf",
    "@create ships atlas",
    "@tag ships atlas = book",
    "@set ships atlas/title = An Atlas of Drowned Coasts",
    "put ships atlas in walnut bookshelf",
    "@create lost mitten",
    "put lost mitten in walnut bookshelf",
]


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

POUCH_BUILD = [
    "@create ammo pouch",
    "@set ammo pouch/container = true",
    "drop ammo pouch",
    "@desc ammo pouch = Stiff leather, the loops and slots inside sized "
    "exactly for charge cells.",
    "@set ammo pouch/on_check = mine = atype == 'item:on_put' and "
    "target is me; item = adata('item'); block(f'The loops inside the "
    "{name(me)} fit ammunition and nothing else - the "
    "{name(item)} stays out.') if mine and not has_tag(item, 'ammo') "
    "else None",
    "@set ammo pouch/on_put = pemit(enactor, f'Slotted. The {name(me)} "
    "now carries {len(contents(me)) + 1} rounds.')",
    "@create charge cell",
    "@tag charge cell = ammo",
    "@create spare charge cell",
    "@tag spare charge cell = ammo",
    "@create dried fig",
]


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

COAT_BUILD = [
    "@create Coat-Check Golem",
    "@tag Coat-Check Golem = npc",
    "drop Coat-Check Golem",
    "@desc Coat-Check Golem = Brass and patience. A rack of numbered "
    "hooks glitters behind it.",
    "@set Coat-Check Golem/on_receive = tk = [o for o in contents(me) "
    "if has_tag(o, 'claim_ticket')]; new = [o for o in contents(me) if "
    "not has_tag(o, 'claim_ticket') and not has_attr(o, 'checked')]; "
    "it = new[0] if new else None; n = V('counter', 0) + 1 "
    "if it else 0; t = create_obj(f'claim ticket {n}', "
    "['claim_ticket'], me) if it else None; (teleport_obj(tk[0], "
    'enactor), pemit(enactor, f"The golem taps the ticket and hands it '
    "back: just say claim {get_attr(tk[0], 'claim_no')}.\")) "
    "if tk else None; (set_attr(me, 'counter', n), set_attr(it, "
    "'checked', n), set_attr(me, f'held_{n}', '#' + it.id), "
    "set_attr(t, 'claim_no', n), teleport_obj(t, enactor), "
    "pemit(enactor, f'The golem stows your {name(it)} on hook "
    "{n} and punches ticket {n}.')) if it else None",
    "@set Coat-Check Golem/cmd_claim = $claim *: tick = [o for o in "
    "contents(enactor) if has_tag(o, 'claim_ticket') and "
    "str(get_attr(o, 'claim_no')) == trim(arg0)]; "
    "held = V('held_' + trim(arg0)); it = get(held) if held else None; "
    "(teleport_obj(it, enactor), del_attr(it, 'checked'), del_attr(me, "
    "'held_' + trim(arg0)), destroy_obj(tick[0]), pemit(enactor, f'The "
    "golem lifts your {name(it)} off hook {trim(arg0)} and "
    "retires the ticket.')) if tick and it else pemit(enactor, 'The "
    "golem shows you two empty brass palms: no matching ticket in your "
    "hand.' if not tick else f'The golem stares at hook {trim(arg0)}"
    ", which is bare. Curious.')",
    "@create wool greatcoat",
]


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

BELT_TICK = (
    "n = len(contents(me)); [teleport_obj(o, V('next_stop')) "
    "for o in contents(me)]; remit(loc(me), 'The belt clatters; the "
    "cargo slides out of sight.') if n else None"
)

BELT_BUILD = [
    "@create belt alpha",
    "@set belt alpha/container = true",
    "drop belt alpha",
    "@set belt alpha/on_tick = " + BELT_TICK,
    "@behavior belt alpha = script_ticker, interval:1",
    "@dig Packing Floor = downline, upline",
    "downline",
    "@create belt beta",
    "@set belt beta/container = true",
    "drop belt beta",
    "@set belt beta/on_tick = " + BELT_TICK,
    "@behavior belt beta = script_ticker, interval:1",
    "@dig Loading Dock = downline, upline",
    "@eval a = get('belt alpha'); b = get('belt beta'); set_attr(a, "
    "'next_stop', '#' + b.id); set_attr(b, 'next_stop', '#' + "
    "get('Loading Dock').id); result = 'belt line wired'",
    "upline",
]


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

CRATE_BUILD = [
    "@create supply crate",
    "@set supply crate/container = true",
    "drop supply crate",
    "@desc supply crate = A scuffed drop-crate. Stenciled across the "
    "lid: CONTENTS RANDOMIZED AT DEPOT.",
    "close supply crate",
    '@set supply crate/loot = [["a rusty gear", 60], '
    '["a sealed med kit", 30], ["a plasma core", 10]]',
    "@set supply crate/on_open = draw = lambda draw, t, r: t[0][0] if "
    "r <= t[0][1] or len(t) == 1 else draw(draw, t[1:], r - t[0][1]); "
    "(set_attr(me, 'seeded', 1), create_obj(draw(draw, V('loot'), "
    "rand(1, 100)), [], me), create_obj(draw(draw, "
    "V('loot'), rand(1, 100)), [], me), remit(loc(me), "
    "'Something rattles and settles inside the crate as the seal "
    "breaks.')) if not V('seeded', 0) else None",
]

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


# =========================================================================
# Docs <-> tests sync — the transcripts above must match the tutorials
# =========================================================================

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

DOC_TRANSCRIPTS = {
    "015_locked_chest.md": CHEST_BUILD,
    "017_bag_of_holding.md": BAG_BUILD,
    "018_refrigerator.md": FRIDGE_BUILD,
    "019_trash_incinerator.md": BIN_BUILD,
    "020_bookshelf.md": SHELF_BUILD,
    "021_ammo_pouch.md": POUCH_BUILD,
    "022_coat_check.md": COAT_BUILD,
    "023_conveyor_belt.md": BELT_BUILD,
    "024_loot_crate.md": CRATE_BUILD,
}


def test_tutorial_docs_contain_the_exact_tested_command_lines():
    """Every Build-it line exercised above appears verbatim in its doc,
    so the tutorials can never drift from what the tests prove works."""
    for doc_name, lines in DOC_TRANSCRIPTS.items():
        text = (DOCS / doc_name).read_text(encoding="utf-8")
        for line in lines:
            assert line in text, (
                f"{doc_name} is missing a tested tutorial line:\n{line}")
