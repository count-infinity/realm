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
class TestEventsAreHeardByTheWholeRoom:
    """`target` is not a nicety — it is the difference between "this
    happened to me" and "this happened near me".

    Events propagate to every object in the room. The old till idiom
    (reconstruct the amount by diffing your own balance) was *accidentally*
    immune, because a neighbour's payment moved none of your money. Reading
    `adata('amount')` is exact and clearer — but it hears everything, so
    the guard has to come with it. Getting this wrong hands out free fuel.
    """

    async def test_unguarded_hook_hears_a_neighbours_payment(self, world):
        w = world
        pump = w.sim.obj("pump", location=w.room)
        pump.db.set('ON_PAYMENT', "set_attr(me, 'heard', adata('amount', 0))")
        w.sim.obj("machine", location=w.room)
        w.alice.db.set('credits', 100)

        await w.sim.do(w.alice, "pay 25 to machine")

        # This is the FOOT-GUN, pinned so nobody "simplifies" the guard away.
        assert pump.db.get('heard') == 25

    async def test_guarded_hook_ignores_a_neighbours_payment(self, world):
        w = world
        pump = w.sim.obj("pump", location=w.room)
        pump.db.set(
            'ON_PAYMENT',
            "set_attr(me, 'heard', adata('amount', 0) if target is me else 0)")
        w.sim.obj("machine", location=w.room)
        w.alice.db.set('credits', 100)

        await w.sim.do(w.alice, "pay 25 to machine")

        assert pump.db.get('heard') == 0

    async def test_guarded_hook_still_hears_its_own_payment(self, world):
        w = world
        pump = w.sim.obj("pump", location=w.room)
        pump.db.set(
            'ON_PAYMENT',
            "set_attr(me, 'heard', adata('amount', 0) if target is me else 0)")
        w.sim.obj("machine", location=w.room)
        w.alice.db.set('credits', 100)

        await w.sim.do(w.alice, "pay 25 to pump")

        assert pump.db.get('heard') == 25


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
class TestNoActionBindsEmptyNames:
    """A `$`-command or `@tr` has no action behind it. The event names are
    still BOUND, just empty — `adata()` answers with its default.

    They must not simply vanish: `@tr obj/ON_GET` is how a builder tests a
    hook, and once tutorials started reading `adata('amount')`, an unbound
    name meant `@tr` died of NameError — with the traceback going to the
    log and a cheerful "Triggered obj/ON_GET." going to the builder. "No
    data" is the honest answer; an exception is not.
    """

    async def test_dollar_command_runs_without_an_action(self, world):
        w = world
        lever = w.sim.obj("lever", location=w.room)
        lever.db.set('cmd_pull', "$pull:set_attr(me, 'ok', 'ran')")

        await w.sim.do(w.alice, "pull")

        assert lever.db.get('ok') == "ran"

    async def test_dollar_command_adata_returns_its_default(self, world):
        w = world
        lever = w.sim.obj("lever", location=w.room)
        lever.db.set('cmd_pull', "$pull:set_attr(me, 'amt', adata('amount', 'none'))")

        await w.sim.do(w.alice, "pull")

        assert lever.db.get('amt') == "none"

    async def test_tr_on_a_payload_reading_hook_does_not_explode(self, world):
        """The regression: 31 tutorials teach `@tr` as the way to test a
        hook, and several now read the payload."""
        w = world
        builder = w.sim.player("Bilda", location=w.room)
        builder.add_tag('builder')
        builder.add_tag('admin')
        thing = w.sim.obj("thing", location=w.room)
        thing.db.set('ON_GET', "set_attr(me, 'amt', adata('amount', 'no-data')); "
                               "set_attr(me, 'tgt', name(target) if target else 'none')")

        await w.sim.do(builder, "@tr thing/ON_GET")

        assert thing.db.get('amt') == "no-data"
        assert thing.db.get('tgt') == "none"

    async def test_actor_still_equals_enactor_with_no_action(self, world):
        """In the real case actor IS the enactor; keep that true when the
        action is absent, or `actor` silently means something different
        under @tr than in flight."""
        w = world
        lever = w.sim.obj("lever", location=w.room)
        lever.db.set('cmd_pull', "$pull:set_attr(me, 'same', actor is enactor)")

        await w.sim.do(w.alice, "pull")

        assert lever.db.get('same') is True
