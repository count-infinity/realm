"""
Exit pairing (realm/core/pairing.py) — the two faces of one door as an
engine-owned relationship: @dig auto-pairs, @link/@unlink/@destroy
dissolve, @pair (re)marries by hand. A stored reference is stale-able,
so the engine owns every write path that can invalidate it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    s.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(s._sessions.values()))
    try:
        yield s
    finally:
        s.close()


def builder(sim, room):
    p = sim.player("Bilda", location=room)
    p.add_tag("builder")
    return p


def exits_of(room):
    return [o for o in room.contents if o.has_tag("exit")]


async def dig_vault(sim, bilda):
    await sim.do(bilda, "@dig The Vault = vault door, vault door")
    vault = sim.store.find_cached(name="The Vault")[0]
    side_a = exits_of(bilda.location)[0]
    side_b = exits_of(vault)[0]
    return vault, side_a, side_b


class TestAutoPairing:

    async def test_dig_pairs_the_two_faces(self, sim):
        room = sim.room("Workshop")
        bilda = builder(sim, room)
        _vault, side_a, side_b = await dig_vault(sim, bilda)
        assert side_a.db.get("partner") == "#" + side_b.id
        assert side_b.db.get("partner") == "#" + side_a.id
        assert any("paired" in line for line in sim.seen(bilda))

    async def test_one_way_dig_pairs_nothing(self, sim):
        room = sim.room("Workshop")
        bilda = builder(sim, room)
        await sim.do(bilda, "@dig The Attic = ladder, ")
        # a lone name with no compass opposite: no return exit, no pairing
        ladder = exits_of(room)[0]
        assert ladder.db.get("partner") is None


class TestDissolution:

    async def test_link_dissolves_both_sides(self, sim):
        room = sim.room("Workshop")
        bilda = builder(sim, room)
        _vault, side_a, side_b = await dig_vault(sim, bilda)
        sim.room("The Cellar")
        sim.seen(bilda)

        await sim.do(bilda, "@link vault door = The Cellar")
        out = sim.seen(bilda)
        assert any("dissolved" in line for line in out)
        assert side_a.db.get("partner") is None
        assert side_b.db.get("partner") is None
        assert any("now leads to The Cellar" in line for line in out)

    async def test_unlink_dissolves_both_sides(self, sim):
        room = sim.room("Workshop")
        bilda = builder(sim, room)
        _vault, side_a, side_b = await dig_vault(sim, bilda)
        await sim.do(bilda, "@unlink vault door")
        assert side_a.db.get("partner") is None
        assert side_b.db.get("partner") is None

    async def test_destroy_clears_the_survivor(self, sim):
        room = sim.room("Workshop")
        bilda = builder(sim, room)
        _vault, side_a, side_b = await dig_vault(sim, bilda)
        await sim.do(bilda, "@destroy vault door")
        assert side_b.db.get("partner") is None


class TestPairCommand:

    async def test_pair_by_name_in_destination_room(self, sim):
        room = sim.room("Workshop")
        bilda = builder(sim, room)
        _vault, side_a, side_b = await dig_vault(sim, bilda)
        await sim.do(bilda, "@link vault door = The Vault")  # dissolves
        assert side_a.db.get("partner") is None
        sim.seen(bilda)

        await sim.do(bilda, "@pair vault door = vault door")
        assert any("Paired:" in line for line in sim.seen(bilda))
        assert side_a.db.get("partner") == "#" + side_b.id
        assert side_b.db.get("partner") == "#" + side_a.id

    async def test_pair_show_and_divorce(self, sim):
        room = sim.room("Workshop")
        bilda = builder(sim, room)
        _vault, side_a, side_b = await dig_vault(sim, bilda)
        sim.seen(bilda)

        await sim.do(bilda, "@pair vault door")
        assert any("is paired with" in line for line in sim.seen(bilda))

        await sim.do(bilda, "@pair vault door =")
        assert any("dissolved" in line for line in sim.seen(bilda))
        assert side_a.db.get("partner") is None
        assert side_b.db.get("partner") is None

    async def test_remarriage_cleans_prior_pairings(self, sim):
        # Double doors: A1<->B1 exists; pairing A1 with B2 must free B1.
        room = sim.room("Workshop")
        bilda = builder(sim, room)
        vault, side_a, side_b1 = await dig_vault(sim, bilda)
        side_b2 = sim.obj("service door", location=vault, tags=["exit"])
        side_b2.db.set("destination", room.id)
        sim.seen(bilda)

        await sim.do(bilda, "@pair vault door = service door")
        assert side_a.db.get("partner") == "#" + side_b2.id
        assert side_b2.db.get("partner") == "#" + side_a.id
        assert side_b1.db.get("partner") is None  # freed, not dangling

    async def test_pair_by_id(self, sim):
        room = sim.room("Workshop")
        bilda = builder(sim, room)
        _vault, side_a, side_b = await dig_vault(sim, bilda)
        await sim.do(bilda, "@pair vault door =")
        sim.seen(bilda)
        await sim.do(bilda, f"@pair vault door = #{side_b.id}")
        assert side_a.db.get("partner") == "#" + side_b.id


class TestMirrorHearsEveryPath:
    """The lock fast-paths (use-keycard, pick) now fire the same gated
    lock/unlock events as the real commands — a mirrored door's far side
    follows a swipe and a successful pick."""

    async def _door(self, sim):
        room = sim.room("Workshop")
        bilda = builder(sim, room)
        vault, side_a, side_b = await dig_vault(sim, bilda)
        for side in (side_a, side_b):
            side.db.set("key_id", "vault_brass")
            side.db.set(
                "on_lock", "if target is me: add_tag(V('partner'), 'locked')")
            side.db.set(
                "on_unlock",
                "if target is me: remove_tag(V('partner'), 'locked')")
        return room, bilda, side_a, side_b

    async def test_keycard_swipe_mirrors(self, sim):
        _room, bilda, side_a, side_b = await self._door(sim)
        card = sim.obj("keycard", location=bilda)
        card.db.set("unlocks", "vault_brass")

        await sim.do(bilda, "use keycard on vault door")   # locks
        assert side_a.has_tag("locked")
        assert side_b.has_tag("locked"), "far side must hear the swipe"

        await sim.do(bilda, "use keycard on vault door")   # unlocks
        assert not side_a.has_tag("locked")
        assert not side_b.has_tag("locked")

    async def test_pick_mirrors_and_flags_picked(self, sim, monkeypatch):
        _room, bilda, side_a, side_b = await self._door(sim)
        side_a.add_tag("locked")
        side_b.add_tag("locked")
        # Record what the ON_UNLOCK script sees; pin the skill check to pass.
        side_a.db.set(
            "on_unlock",
            "if target is me: (remove_tag(V('partner'), 'locked'), "
            "set_attr(me, 'heard_picked', adata('picked')))")
        from realm.core import checks

        class _Pass:
            success = True
            margin = 5
        monkeypatch.setattr(
            "realm.commands.builtin.manipulation.check",
            lambda *a, **k: _Pass())

        await sim.do(bilda, "pick vault door")
        assert not side_a.has_tag("locked")
        assert not side_b.has_tag("locked"), "far side must hear the pick"
        assert side_a.db.get("heard_picked") is True
