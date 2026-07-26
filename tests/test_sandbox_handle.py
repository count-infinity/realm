"""
Wall 2 — the softcode capability handle (docs/design/sandbox-security.md).

Softcode is handed opaque handles, not live GameObjects, so every read flows
through the guarded (secret-gating) reader and every write must go through a
`controls()`-checked function. These tests pin the authority boundary: the
cross-owner write/teleport/escalation exploits die, guarded reads survive,
and `is`/`==` still hold via per-run interning.
"""

from __future__ import annotations

import pytest

from realm.core.attrflags import set_attr_flags
from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


def scene(sim):
    """Ada (attacker) and Bob (victim) in a room; a vault Bob owns."""
    room = sim.room("Room")
    ada = sim.player("Ada", location=room)
    bob = sim.player("Bob", location=room)
    vault = sim.obj("vault", location=room)
    vault.owner = bob
    gadget = sim.obj("gadget", location=room)
    gadget.owner = ada
    return room, ada, bob, vault, gadget


class TestAuthorityWritesBlocked:

    async def test_cross_owner_attr_assign_blocked(self, sim):
        _room, ada, _bob, vault, _g = scene(sim)
        before = vault.db.get("x")
        await sim.eval(ada, "get('vault').db.x = 9")
        assert vault.db.get("x") == before  # unchanged

    async def test_cross_owner_db_set_blocked(self, sim):
        _room, ada, _bob, vault, _g = scene(sim)
        await sim.eval(ada, "get('vault').db.set('y', 9)")
        assert vault.db.get("y") is None

    async def test_direct_attribute_write_blocked_even_on_own(self, sim):
        # Writes never ride attribute assignment; use set_attr. (Even on your
        # own object, so there is one visible, guarded write path.)
        _room, ada, _bob, _v, _g = scene(sim)
        _r, err = await sim.eval(ada, "me.hp = 5")
        assert err is not None
        assert ada.db.get("hp") is None

    async def test_structural_write_blocked(self, sim):
        _room, ada, bob, vault, _g = scene(sim)
        await sim.eval(ada, "get('Bob').location = get('vault')")
        assert bob.location is not vault  # not teleported

    async def test_tags_are_immutable(self, sim):
        _room, ada, _bob, _v, gadget = scene(sim)
        await sim.eval(ada, "me.tags.add('admin')")
        assert not gadget.has_tag("admin")

    async def test_object_valued_reads_do_not_leak_a_writable_object(self, sim):
        # loc(me)/me.location is itself a handle, so you cannot hop through it
        # to mutate the room you are merely standing in.
        room, ada, _bob, _v, _g = scene(sim)
        before = room.db.get("z")
        await sim.eval(ada, "me.location.db.z = 9")
        assert room.db.get("z") == before


class TestGuardedReadsSurvive:

    async def test_field_reads_work(self, sim):
        _room, ada, _bob, _v, _g = scene(sim)
        r, err = await sim.eval(ada, "result = f'{me.name}/{me.id}'")
        assert err is None
        assert r == f"{ada.name}/{ada.id}"

    async def test_db_get_still_reads(self, sim):
        _room, ada, _bob, _v, _g = scene(sim)
        ada.db.set("mood", "wry")
        r, err = await sim.eval(ada, "result = me.db.get('mood')")
        assert err is None and r == "wry"

    async def test_attribute_fallthrough_reads_db(self, sim):
        # me.mood (unknown as a field) falls through to the guarded db reader.
        _room, ada, _bob, _v, _g = scene(sim)
        ada.db.set("mood", "wry")
        r, _e = await sim.eval(ada, "result = me.mood")
        assert r == "wry"

    async def test_set_attr_on_own_object_round_trips(self, sim):
        _room, ada, _bob, _v, _g = scene(sim)
        r, err = await sim.eval(
            ada, "set_attr(me, 'hp', 7); result = me.db.get('hp')")
        assert err is None and r == 7


class TestSecretAndProtected:

    async def test_secret_attr_gated_from_non_controller(self, sim):
        _room, ada, bob, _v, _g = scene(sim)
        bob.db.set("diary", "it was me")
        set_attr_flags(bob, "diary", ["secret"])
        r, _e = await sim.eval(ada, "result = get('Bob').db.get('diary')")
        assert r is None  # Ada does not control Bob

    async def test_secret_attr_readable_by_controller(self, sim):
        _room, _ada, bob, _v, _g = scene(sim)
        bob.db.set("diary", "it was me")
        set_attr_flags(bob, "diary", ["secret"])
        r, _e = await sim.eval(bob, "result = me.db.get('diary')")
        assert r == "it was me"

    async def test_protected_attr_hidden(self, sim):
        _room, ada, _bob, _v, _g = scene(sim)
        ada.db.set("keyid", "should-not-read")  # simulate presence
        r, _e = await sim.eval(ada, "result = me.db.get('keyid')")
        assert r is None  # PROTECTED_ATTRS never read through the handle


class TestIdentityInterning:

    async def test_same_object_interns_to_same_handle(self, sim):
        _room, ada, _bob, _v, _g = scene(sim)
        r, err = await sim.eval(ada, "result = (get('vault') is get('vault'))")
        assert err is None and r is True

    async def test_me_is_me(self, sim):
        _room, ada, _bob, _v, _g = scene(sim)
        r, _e = await sim.eval(ada, "result = (me is me)")
        assert r is True

    async def test_handles_compare_equal_by_object(self, sim):
        _room, ada, _bob, _v, _g = scene(sim)
        r, _e = await sim.eval(ada, "result = (get('vault') == get('vault'))")
        assert r is True


class TestExpressionPaths:
    """Lock / @detail / strategy conditions use eval_expression, not the
    script sandbox. guard_namespace wraps their raw objects so a hostile
    expression cannot mutate via `x.db.set(...)` when someone else triggers
    it (a look, an interaction)."""

    def test_guard_namespace_blocks_db_write(self, sim):
        from realm.core.safe_eval import eval_bool
        from realm.scripting.handle import guard_namespace
        _room, _ada, bob, _v, _g = scene(sim)
        ns = guard_namespace({'caller': bob}, principal=bob)
        # A malicious lock/detail expression: side-effect then pass.
        eval_bool("caller.db.set('robbed', 1) or True", ns)
        assert bob.db.get("robbed") is None  # write blocked

    def test_guard_namespace_blocks_attr_assign_is_not_expressible(self, sim):
        # (assignment is a statement, not an expression, so eval can't; the
        # reachable write vector is .db.set / method mutators, covered above.)
        from realm.core.safe_eval import eval_bool
        from realm.scripting.handle import guard_namespace
        _room, _ada, bob, _v, _g = scene(sim)
        ns = guard_namespace({'caller': bob}, principal=bob)
        eval_bool("caller.tags.add('admin') if True else False", ns)
        assert not bob.has_tag("admin")

    def test_guard_namespace_keeps_lock_predicates_working(self, sim):
        from realm.core.safe_eval import eval_bool
        from realm.scripting.handle import guard_namespace
        _room, _ada, bob, _v, _g = scene(sim)
        bob.add_tag("keyholder")
        bob.db.set("rank", 7)
        ns = guard_namespace({'caller': bob}, principal=bob)
        assert eval_bool("caller.has_tag('keyholder')", ns) is True
        assert eval_bool("caller.has_tag('nope')", ns) is False
        assert eval_bool("caller.db.get('rank') >= 5", ns) is True

    def test_guard_namespace_secret_gated_from_non_principal(self, sim):
        from realm.core.safe_eval import eval_bool
        from realm.scripting.handle import guard_namespace
        _room, ada, bob, _v, _g = scene(sim)
        bob.db.set("diary", "secret")
        set_attr_flags(bob, "diary", ["secret"])
        # An expression evaluated with ADA as principal cannot read Bob's secret.
        ns = guard_namespace({'target': bob}, principal=ada)
        assert eval_bool("target.db.get('diary') == 'secret'", ns) is False

    async def test_detail_condition_cannot_mutate_viewer(self, sim):
        # End-to-end: a hostile @detail row must not mutate whoever looks.
        room, ada, bob, _v, _g = scene(sim)
        trap = sim.obj("trap2", location=room)
        trap.owner = ada
        trap.db.set("desc_extras",
                    [["viewer.db.set('marked', 1) or False", "x"]])
        await sim.do(bob, "look trap2")
        assert bob.db.get("marked") is None
