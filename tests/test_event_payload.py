"""
ON_<EVENT> / ^listen scripts can read the action's payload.

Before this, a witness saw only *who* acted — never *what happened*. The
engine already put the useful data in ``Action.extra`` (``amount`` on
payments, ``damage`` on hits, ``item`` on gets, ``pose`` on emotes); it
simply never reached softcode, so builders reconstructed it by diffing
their own balance (the "ledger"/"till" idiom taught across a dozen
showcase tutorials).

These tests drive the real commands through the dispatcher and assert the
payload arrives. The apply pass stays read-only: no block/mod/set_adata.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.testing import Simulator


@pytest.fixture
def world():
    sim = Simulator()
    room = sim.room("Hall")
    alice = sim.player("Alice", location=room)
    bob = sim.player("Bob", location=room)
    try:
        yield SimpleNamespace(sim=sim, room=room, alice=alice, bob=bob)
    finally:
        sim.close()


@pytest.mark.asyncio
class TestPaymentAmount:
    """The headline case: ON_PAYMENT could not read the amount paid."""

    async def test_on_payment_reads_the_amount(self, world):
        w = world
        ogre = w.sim.obj("ogre", location=w.room)
        ogre.db.set('ON_PAYMENT', "set_attr(me, 'took', adata('amount'))")
        w.alice.db.set('credits', 100)

        await w.sim.do(w.alice, "pay 25 to ogre")

        assert ogre.db.get('took') == 25

    async def test_on_payment_sees_who_was_paid(self, world):
        """`target` distinguishes 'I was paid' from 'someone was paid'."""
        w = world
        ogre = w.sim.obj("ogre", location=w.room)
        troll = w.sim.obj("troll", location=w.room)
        script = "set_attr(me, 'paid_me', target.id == me.id)"
        ogre.db.set('ON_PAYMENT', script)
        troll.db.set('ON_PAYMENT', script)
        w.alice.db.set('credits', 100)

        await w.sim.do(w.alice, "pay 5 to ogre")

        assert ogre.db.get('paid_me') is True
        assert troll.db.get('paid_me') is False   # witnessed, not addressed


@pytest.mark.asyncio
class TestItemAndPose:
    async def test_on_get_names_the_item_via_target(self, world):
        """018/019/200 wanted "which item was picked up".

        For `get gem` the item IS the action's target (do_get passes no
        extra), so `target` is the answer — which only became readable
        with the event namespace.
        """
        w = world
        watcher = w.sim.obj("watcher", location=w.room)
        watcher.db.set('ON_GET', "set_attr(me, 'saw', name(target))")
        w.sim.obj("gem", location=w.room)

        await w.sim.do(w.alice, "get gem")

        assert watcher.db.get('saw') == "gem"

    async def test_on_receive_reads_item_and_giver_from_adata(self, world):
        """Where the target is a *person*, the item rides in extra —
        so this is a true adata() case."""
        w = world
        w.bob.db.set(
            'ON_RECEIVE',
            "set_attr(me, 'got', name(adata('item'))); "
            "set_attr(me, 'from', name(adata('giver')))",
        )
        gem = w.sim.obj("gem", location=w.alice)
        gem.location = w.alice

        await w.sim.do(w.alice, "give gem to Bob")

        assert w.bob.db.get('got') == "gem"
        assert w.bob.db.get('from') == "Alice"

    async def test_atype_and_has_atag_are_bound(self, world):
        w = world
        watcher = w.sim.obj("watcher", location=w.room)
        watcher.db.set(
            'ON_GET',
            "set_attr(me, 'ty', atype); set_attr(me, 'hostile', has_atag('hostile'))",
        )
        w.sim.obj("gem", location=w.room)

        await w.sim.do(w.alice, "get gem")

        assert watcher.db.get('ty') == "item:on_get"
        assert watcher.db.get('hostile') is False


@pytest.mark.asyncio
class TestListenGetsThePayload:
    async def test_listen_can_read_the_message(self, world):
        w = world
        parrot = w.sim.obj("parrot", location=w.room)
        parrot.db.set('listen_all', "^*:set_attr(me, 'heard', adata('message'))")

        await w.sim.do(w.alice, "say hello there")

        assert parrot.db.get('heard') == "hello there"


@pytest.mark.asyncio
class TestApplyPassStaysReadOnly:
    """The decision has already been made; a witness must not rewrite it."""

    async def test_no_block_in_event_namespace(self, world):
        w = world
        watcher = w.sim.obj("watcher", location=w.room)
        # block() must be unbound here -> NameError -> script fails, but the
        # world op still happened (the veto pass is over).
        watcher.db.set('ON_GET', "block('nope')")
        w.sim.obj("gem", location=w.room)

        await w.sim.do(w.alice, "get gem")

        gem = next(o for o in w.alice.contents if o.name == "gem")
        assert gem is not None          # the get was NOT vetoed

    async def test_no_set_adata_in_event_namespace(self, world):
        w = world
        watcher = w.sim.obj("watcher", location=w.room)
        watcher.db.set('ON_GET', "set_adata('item', None)")
        w.sim.obj("gem", location=w.room)

        await w.sim.do(w.alice, "get gem")

        assert any(o.name == "gem" for o in w.alice.contents)


@pytest.mark.asyncio
class TestCheckPassUnchanged:
    """_check_namespace now layers on _event_namespace — the ward verbs
    must still work exactly as before."""

    async def test_ward_can_still_block_using_the_shared_names(self, world):
        """The ward lives on the TARGET (softcode wards are
        participant-only — a room is a bystander for item:on_get). It
        reads `atype` from the shared _event_namespace and vetoes with
        `block`, which only the check pass gets.
        """
        w = world
        anvil = w.sim.obj("anvil", location=w.room)
        anvil.db.set(
            'on_check',
            "block('too heavy') if atype == 'item:on_get' else None",
        )

        await w.sim.do(w.alice, "get anvil")

        assert not any(o.name == "anvil" for o in w.alice.contents)
        assert any("too heavy" in line for line in w.sim.seen(w.alice))


@pytest.mark.asyncio
class TestNoActionNoNames:
    """A $-command has no action behind it; the event names stay unbound."""

    async def test_dollar_command_has_no_adata(self, world):
        w = world
        lever = w.sim.obj("lever", location=w.room)
        lever.db.set('cmd_pull', "$pull:set_attr(me, 'ok', 'ran')")

        await w.sim.do(w.alice, "pull")

        assert lever.db.get('ok') == "ran"   # runs fine without event names
