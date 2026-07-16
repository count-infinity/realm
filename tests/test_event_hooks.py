"""
Event-hooks package — new ON_<EVENT> lifecycle hooks (the tbaMUD DG-Scripts
gaps), all firing through ``realm.core.events.fire_event``:

  REMOVE (gated) · RECEIVE · LOAD · EXPIRE · CAST · HITPRCNT

REALM's event stream is open, so each is a fire site, not a language change.
Gated hooks let a witnessing ``on_check`` ward veto (a cursed ring refusing
removal); informational hooks just fire the trigger.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from realm.core.events import reap_expired
from realm.testing import Simulator


@pytest.fixture
def world():
    sim = Simulator()
    room = sim.room("Hall")
    alice = sim.player("Alice", location=room)
    bob = sim.player("Bob", location=room)
    try:
        yield SimpleNamespace(sim=sim, room=room, alice=alice, bob=bob,
                              store=sim.store)
    finally:
        sim.close()


@pytest.mark.asyncio
class TestRemoveGated:

    async def test_cursed_item_refuses_removal(self, world):
        w = world
        ring = w.sim.obj("cursed ring", location=w.alice, tags=["worn"])
        ring.db.set("on_check",
                    "block('It won\\'t budge.') if atype == 'item:on_remove' "
                    "else None")

        await w.sim.do(w.alice, "remove cursed ring")

        assert ring.has_tag("worn")               # veto held
        assert any("budge" in m for m in w.sim.seen(w.alice))

    async def test_normal_item_comes_off(self, world):
        w = world
        hat = w.sim.obj("hat", location=w.alice, tags=["worn"])
        await w.sim.do(w.alice, "remove hat")
        assert not hat.has_tag("worn")

    async def test_cursed_weapon_veto_reason_reaches_the_player(self, world):
        w = world
        sword = w.sim.obj("black blade", location=w.alice, tags=["wielded"])
        sword.db.set("on_check",
                     "block('It clings to your hand!') "
                     "if atype == 'item:on_unwield' else None")

        await w.sim.do(w.alice, "unwield")

        assert sword.has_tag("wielded")           # veto held
        assert any("clings" in m for m in w.sim.seen(w.alice))  # reason shown


@pytest.mark.asyncio
class TestReceive:

    async def test_recipient_on_receive_fires(self, world):
        w = world
        gift = w.sim.obj("gift", location=w.alice)
        # Bob reacts to being handed something (enactor = the giver).
        w.bob.db.set("on_receive", "pemit(enactor, 'Bob nods thanks.')")

        await w.sim.do(w.alice, "give gift to Bob")

        assert gift.location is w.bob
        assert any("nods thanks" in m for m in w.sim.seen(w.alice))


@pytest.mark.asyncio
class TestExpire:

    async def test_expired_object_fires_and_is_destroyed(self, world):
        w = world
        smoke = w.sim.obj("a wisp of smoke", location=w.room)
        smoke.db.set("expires_at", time.time() - 1)     # already due
        smoke.db.set("on_expire",
                     f"pemit('#{w.alice.id}', 'The smoke dissipates.')")

        reaped = await reap_expired(w.store, now=time.time())

        assert reaped == 1
        assert w.store.get_cached(smoke.id) is None
        assert any("dissipates" in m for m in w.sim.seen(w.alice))

    async def test_on_expire_can_renew_the_lease(self, world):
        w = world
        ward = w.sim.obj("a glowing ward", location=w.room)
        ward.db.set("expires_at", time.time() - 1)
        ward.db.set("on_expire", "expire(me, 999)")     # renew, don't die

        reaped = await reap_expired(w.store, now=time.time())

        assert reaped == 0
        assert w.store.get_cached(ward.id) is ward
        assert float(ward.db.get("expires_at")) > time.time()

    async def test_not_yet_due_is_left_alone(self, world):
        w = world
        obj = w.sim.obj("a candle", location=w.room)
        obj.db.set("expires_at", time.time() + 10_000)
        assert await reap_expired(w.store, now=time.time()) == 0
        assert w.store.get_cached(obj.id) is obj


@pytest.mark.asyncio
class TestCast:

    async def test_on_cast_fires_at_target(self, world):
        w = world
        # A wolf that flinches when a power is aimed at it (enactor = caster).
        w.bob.db.set("on_cast", "pemit(enactor, name(me) + ' recoils.')")

        await w.sim.eval(w.alice, f"cast('#{w.bob.id}', 'fear')",
                         enactor=w.alice)

        assert any("recoils" in m for m in w.sim.seen(w.alice))

    async def test_remote_cast_needs_reach(self, world):
        from realm.permissions.locks import LockType
        w = world
        # Bob is in a sealed vault (REACH-locked); Alice casts from the hall.
        vault = w.sim.room("Vault")
        vault.locks[LockType.REACH.value] = "False"
        w.bob.location = vault
        w.bob.db.set("on_cast", "pemit(enactor, 'recoils')")

        await w.sim.eval(w.alice, f"cast('#{w.bob.id}', 'fear', tags=['magic'])",
                         enactor=w.alice)

        assert not any("recoils" in m for m in w.sim.seen(w.alice))  # reach denied

    async def test_magic_ward_resists_the_cast(self, world):
        w = world
        # A magic-resist charm: its on_check blocks anything magic-tagged,
        # so the cast is vetoed and ON_CAST never reacts.
        w.bob.db.set("on_check",
                     "block('warded') if has_atag('magic') else None")
        w.bob.db.set("on_cast", "pemit(enactor, 'recoils')")

        # The spell tags itself 'magic' — the kernel doesn't assume it.
        await w.sim.eval(w.alice, f"cast('#{w.bob.id}', 'fear', tags=['magic'])",
                         enactor=w.alice)

        assert not any("recoils" in m for m in w.sim.seen(w.alice))


@pytest.mark.asyncio
class TestLoad:

    async def test_spawned_object_fires_on_load(self, world):
        w = world
        from realm.core.behaviors import BehaviorRegistry
        spawner = BehaviorRegistry.create(
            "spawner",
            prototype={"name": "a wolf", "tags": ["npc"],
                       "attrs": {"on_load": "set_attr(me, 'awoke', 1)"}},
            count=1)
        w.room.add_behavior(spawner)

        await spawner.tick(w.room, 4.0)     # first spawn is immediate

        wolf = next(o for o in w.room.contents if o.name == "a wolf")
        assert wolf.db.get("awoke") == 1    # ON_LOAD ran on the fresh spawn


@pytest.mark.asyncio
async def test_hitprcnt_fires_once_on_threshold_cross():
    """HP falling through db.hitprcnt fires event:on_hitprcnt exactly once —
    the low-HP AI seam. Driven through the real combat system; the event is
    captured with a propagation observer (no softcode engine here)."""
    from realm.combat.combatant import clear_combatant_cache
    from realm.combat.rulesets.d20 import D20Ruleset
    from realm.combat.system import CombatSystem
    from realm.core.objects import GameObject
    from realm.core.propagation import get_engine, reset_engine

    reset_engine()
    clear_combatant_cache()
    fired = []

    async def observer(action):
        if action.action_type == "event:on_hitprcnt":
            fired.append(action)

    get_engine().add_observer(observer)
    try:
        attacker = GameObject("Fighter")
        attacker.db.set("strength", 20)
        attacker.db.set("proficiency_bonus", 10)   # reliable hits

        goblin = GameObject("Goblin")
        goblin.db.set("armor_class", 1)            # almost always hit
        goblin.db.set("hp", 100)
        goblin.db.set("max_hp", 100)
        goblin.db.set("hitprcnt", 90)              # react at 90%

        combat = CombatSystem(ruleset=D20Ruleset())
        for _ in range(20):
            await combat.attack(attacker, goblin)
            if fired:
                break

        assert len(fired) == 1                     # once, on the crossing
        # Fires as HP crosses to at-or-below the threshold — damage can land
        # HP exactly on 90% (10 of 100), so the reported percent is <= 90.
        assert fired[0].extra["percent"] <= 90
        assert fired[0].target is goblin
    finally:
        reset_engine()
        clear_combatant_cache()
