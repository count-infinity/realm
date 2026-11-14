"""
Pools: bounded numbers on objects (KERNEL_PLAN 8.1).

``realm/core/pools.py`` is kernel, so everything here runs in a bare world
(no features). A pool named ``hp`` is the attributes ``hp`` and ``max_hp``.
"""

from __future__ import annotations

import pytest

from realm.core import pools
from realm.core.objects import GameObject
from realm.core.pools import Pool


def thing(name: str = "thing", **attrs) -> GameObject:
    obj = GameObject(name=name)
    for key, value in attrs.items():
        obj.db.set(key, value)
    return obj


# --- harm and mend ------------------------------------------------------------


def test_harm_clamps_a_down_pool_at_its_floor(world):
    obj = thing(hp=5, max_hp=10)
    change = pools.harm(obj, "hp", 8)
    assert (change.old, change.new, change.requested, change.applied) == (5, 0, 8, 5)
    assert obj.db.hp == 0


def test_harm_goes_negative_without_a_floor(world):
    obj = thing(hp=5, max_hp=10, pools={"hp": {"floor": None}})
    change = pools.harm(obj, "hp", 8)
    assert change.new == -3 and change.applied == 8
    assert obj.db.hp == -3


def test_mend_caps_at_max_and_is_unbounded_without_one(world):
    capped = thing(hp=7, max_hp=10)
    assert pools.mend(capped, "hp", 5).applied == 3
    assert capped.db.hp == 10
    open_ended = thing(luck=3)
    assert pools.mend(open_ended, "luck", 50).new == 53


def test_an_up_pool_rises_under_harm_and_is_spent_at_max(world):
    obj = thing(stress=4, max_stress=6, pools={"stress": {"direction": "up"}})
    change = pools.harm(obj, "stress", 5)
    assert (change.old, change.new, change.applied) == (4, 6, 2)
    assert change.became_spent and pools.is_spent(obj, "stress")
    mended = pools.mend(obj, "stress", 9)
    assert (mended.new, mended.applied) == (0, 6)
    assert not pools.is_spent(obj, "stress")


def test_pool_percent_counts_what_is_left(world):
    obj = thing(hp=3, max_hp=12, harm=2, max_harm=6, luck=4,
                pools={"harm": {"direction": "up"}})
    assert pools.pool_percent(obj, "hp") == 25.0
    assert pools.pool_percent(obj, "hp", 6) == 50.0
    assert round(pools.pool_percent(obj, "harm"), 1) == 66.7
    assert pools.pool_percent(obj, "luck") is None       # no max
    assert pools.pool_percent(obj, "mana") is None       # no pool


def test_harm_and_mend_refuse_a_negative_amount(world):
    obj = thing(hp=5)
    with pytest.raises(ValueError, match="negative"):
        pools.harm(obj, "hp", -1)
    with pytest.raises(ValueError, match="negative"):
        pools.mend(obj, "hp", -1)


# --- overflow and soak --------------------------------------------------------


def ship(**extra) -> GameObject:
    attrs = dict(shields=4, max_shields=20, hull=30, max_hull=30, armor=2,
                 pools={"shields": {"overflow": "hull"}, "hull": {"soak_attr": "armor"}})
    attrs.update(extra)
    return thing("ship", **attrs)


def test_harm_overflows_into_the_next_pool(world):
    obj = ship()
    change = pools.harm(obj, "shields", 10)
    assert obj.db.shields == 0 and obj.db.hull == 24
    assert change.applied == 4 and change.became_spent
    assert change.spilled is not None
    assert (change.spilled.pool, change.spilled.requested, change.spilled.applied) == ("hull", 6, 6)
    assert change.total_applied == 10


def test_soak_applies_at_each_pool_it_reaches(world):
    obj = ship()
    change = pools.harm(obj, "shields", 10, soak=True)
    assert obj.db.hull == 26
    assert change.spilled.soaked == 2 and change.spilled.applied == 4
    assert change.total_applied == 8


def test_an_overflow_cycle_raises_naming_both_pools(world):
    obj = thing(a=5, b=5, pools={"a": {"overflow": "b"}, "b": {"overflow": "a"}})
    with pytest.raises(ValueError, match=r"'a'.*'b'|'b'.*'a'"):
        pools.harm(obj, "a", 20)
    with pytest.raises(ValueError, match=r"'a'.*'b'|'b'.*'a'"):
        pools.vital_pool(thing(a=5, b=5, damage_pool="a",
                               pools={"a": {"overflow": "b"}, "b": {"overflow": "a"}}))


def test_damage_and_vital_pools(world):
    obj = ship(damage_pool="shields")
    assert pools.damage_pool(obj) == "shields"
    assert pools.vital_pool(obj) == "hull"
    person = thing(hp=10, max_hp=10)
    assert pools.damage_pool(person) == "hp" == pools.vital_pool(person)
    assert pools.damage_pool(thing("rock")) is None
    assert pools.vital_pool(thing("rock")) is None


def test_the_damage_pool_setting(world):
    from realm.testing import reconfigure
    reconfigure(world, damage_pool="harm")
    assert pools.damage_pool(thing(harm=0, max_harm=6)) == "harm"
    assert pools.damage_pool(thing(hp=10)) is None


# --- definitions --------------------------------------------------------------


def test_definition_lookup_order(world):
    from realm.features import Feature, FeatureSet
    feature = Feature("ships")
    feature.pool(Pool("hull", soak_attr="plating"))
    feature.pool(Pool("shields", overflow="hull"))
    features = FeatureSet([feature])
    features.install_runtime(world)

    # 4. implicit: any number is a pool with default settings.
    assert pools.pool_def(thing(mana=3), "mana") == Pool("mana")
    assert pools.pool_def(thing(mana="lots"), "mana") is None

    # 3. a world default.
    assert pools.pool_def(thing(hull=3), "hull").soak_attr == "plating"

    # 2. the parent's ``pools`` attribute beats the world default...
    template = thing("template", pools={"hull": {"soak_attr": "armor"}})
    child = thing("child", hull=3)
    child.parent = template
    assert pools.pool_def(child, "hull").soak_attr == "armor"
    # ...without hiding the world default for a pool it does not name.
    assert pools.pool_def(child, "shields").overflow == "hull"

    # 1. the object's own ``pools`` attribute beats the parent's.
    child.db.pools = {"hull": {"floor": None}}
    own = pools.pool_def(child, "hull")
    assert own.floor is None and own.soak_attr is None   # first match wins, no merge


def test_a_rules_system_supplies_world_defaults():
    from realm.std.rules.system import GameSystem
    from realm.testing import Simulator

    class ShipRules(GameSystem):
        def pools(self):
            return [Pool("hull", soak_attr="plating")]

    with Simulator(features=["rules"], game_system=ShipRules):
        assert pools.pool_def(thing(hull=3), "hull").soak_attr == "plating"


def test_declared_pools_lists_what_the_object_has(world):
    pools.add_default(world, Pool("hp"))
    pools.add_default(world, Pool("mana"))
    ship = thing(hp=3, shields=5, strength=12, pools={"shields": {"overflow": "hp"}})
    assert pools.declared_pools(ship) == ["hp", "shields"]   # no mana; strength is implicit
    assert pools.declared_pools(thing(strength=12)) == []


def test_conflicting_world_defaults_fail_loudly(world):
    from realm.features import Feature, FeatureError, FeatureSet
    one, two = Feature("one"), Feature("two")
    one.pool(Pool("hull"))
    two.pool(Pool("hull", floor=None))
    with pytest.raises(FeatureError, match="hull"):
        FeatureSet([one, two])


def test_a_bad_pool_spec_fails_loudly(world):
    with pytest.raises(ValueError, match="overfow"):
        pools.pool_def(thing(hp=3, pools={"hp": {"overfow": "x"}}), "hp")
    with pytest.raises(ValueError, match="direction"):
        pools.pool_def(thing(hp=3, pools={"hp": {"direction": "sideways"}}), "hp")


def test_storage_names(world):
    obj = thing(pools={"heat": {"attr": "core_temp", "max_attr": "core_limit",
                                "direction": "up"}}, core_temp=3, core_limit=5)
    assert pools.pool_get(obj, "heat") == 3 and pools.pool_max(obj, "heat") == 5
    pools.set_pool(obj, "heat", 1, max=9)
    assert obj.db.core_temp == 1 and obj.db.core_limit == 9
    assert not obj.db.get("heat") and not obj.db.get("max_heat")


# --- spend, set_pool, and objects without the pool ----------------------------


def test_spend_is_all_or_nothing(world):
    obj = thing(mana=5, max_mana=10)
    assert pools.spend(obj, "mana", 6) is None
    assert obj.db.mana == 5
    assert pools.spend(obj, "mana", 5).new == 0


def test_spend_on_an_up_pool_raises_it_and_blocks_at_max(world):
    obj = thing(heat=4, max_heat=6, pools={"heat": {"direction": "up"}})
    assert pools.spend(obj, "heat", 2).new == 6
    assert pools.spend(obj, "heat", 1) is None
    assert obj.db.heat == 6


def test_set_pool_initializes_and_resizes(world):
    obj = thing()
    pools.set_pool(obj, "hp", 12, max=12)
    assert (obj.db.hp, obj.db.max_hp) == (12, 12)
    pools.set_pool(obj, "hp", 15, max=15)
    assert pools.pool_get(obj, "hp") == 15 and pools.pool_max(obj, "hp") == 15


def test_an_object_without_the_pool(world):
    rock = thing("rock")
    assert pools.pool_get(rock, "hp") is None
    assert pools.pool_max(rock, "hp") is None
    assert not pools.has_pool(rock, "hp")
    assert not pools.is_spent(rock, "hp")
    change = pools.harm(rock, "hp", 5)
    assert change.applied == 0 and not change.became_spent
    assert pools.mend(rock, "hp", 5).applied == 0
    assert pools.spend(rock, "hp", 1) is None
    assert rock.db.get("hp") is None


def test_a_pool_value_inherits_through_parent(world):
    template = thing("template", hp=10, max_hp=10)
    child = thing("child")
    child.parent = template
    assert pools.pool_get(child, "hp") == 10
    pools.harm(child, "hp", 3)
    assert child.db.hp == 7 and template.db.hp == 10


# --- settle -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_settle_fires_on_pool_then_on_spent_once_each():
    from realm.testing import Simulator

    with Simulator(features=[]) as sim:
        room = sim.room("Bay")
        target = sim.obj("drone", location=room, hp=3, max_hp=3)
        log = "set_attr(me, 'log', (get_attr(me, 'log', '') + '{0}'))"
        target.db.on_pool = log.replace("{0}", "P")
        target.db.on_spent = log.replace("{0}", "S")

        await pools.settle(pools.harm(target, "hp", 1))
        assert target.db.log == "P"
        await pools.settle(pools.harm(target, "hp", 5))
        assert target.db.log == "PPS"
        await pools.settle(pools.harm(target, "hp", 5))     # nothing moved
        assert target.db.log == "PPS"


@pytest.mark.asyncio
async def test_settle_payload_and_spilled_links():
    from realm.core.propagation import Action
    from realm.testing import Simulator

    seen: list[Action] = []

    async def watch(action):
        if action.action_type.startswith("pool:"):
            seen.append(action)

    with Simulator(features=[]) as sim:
        sim.world.observe(watch)
        gunner = sim.obj("gunner")
        obj = sim.add(ship())
        await pools.settle(pools.harm(obj, "shields", 10), source=gunner)

    assert [(a.action_type, a.extra["pool"]) for a in seen] == [
        ("pool:on_change", "shields"), ("pool:on_spent", "shields"),
        ("pool:on_change", "hull")]
    first = seen[0]
    assert first.actor is gunner and first.target is obj
    assert {k: first.extra[k] for k in ("old", "new", "applied")} == {
        "old": 4, "new": 0, "applied": 4}
    assert first.extra["source"] is gunner


# --- softcode -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_softcode_pool_functions():
    from realm.testing import Simulator

    with Simulator(features=[]) as sim:
        room = sim.room("Bay")
        target = sim.obj("drone", location=room, hp=5, max_hp=8, heat=0, max_heat=3,
                         pools={"heat": {"direction": "up"}})
        target.db.on_spent = "set_attr(me, 'down', 1)"
        trap = sim.obj("trap", location=room)

        result, error = await sim.eval(
            trap, "result = [pool('drone', 'hp'), pool_max('drone', 'hp'),"
                  " has_pool('drone', 'mana'), spent('drone', 'hp')]")
        assert error is None and result == [5, 8, False, False]

        result, error = await sim.eval(trap, "result = harm_pool('drone', 'hp', 9)")
        assert error is None and result == 5
        assert target.db.hp == 0 and target.db.down == 1     # settled after the run

        result, error = await sim.eval(trap, "result = mend_pool('drone', 'hp', 2)")
        assert error is None and result == 2

        result, error = await sim.eval(
            target, "result = [spend_pool('heat', 2), spend_pool('heat', 2)]")
        assert error is None and result == [True, False]
        assert target.db.heat == 2


def test_harm_pool_is_harm_gated():
    from realm.scripting.registry import registered
    assert registered()["harm_pool"].harm
    assert not registered()["mend_pool"].harm
    assert all(registered()[n].readonly for n in ("pool", "pool_max", "has_pool", "spent"))


def test_a_feature_and_the_rules_system_must_agree(world):
    from realm.features import FeatureError
    pools.add_default(world, Pool("hp", owner="ships"))
    pools.add_default(world, Pool("hp", owner="rules (base)"))      # same definition
    with pytest.raises(FeatureError, match="'hp'.*ships.*rules"):
        pools.add_default(world, Pool("hp", floor=None, owner="rules (base)"))
