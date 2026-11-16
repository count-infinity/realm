"""Equipment-derived stats ride the event bus, not the wear command.

``cmd_wear``/``cmd_unwear`` fire ``item:on_wear``/``item:on_remove``;
``equipment_observer`` (registered at boot like the stealth and hostile
observers) forwards an applied gear change to the active GameSystem's
``on_equipment_change``. MercSystem re-derives Diku AC there; the ABC
default is a no-op, so systems with nothing equipment-derived are inert.
The command itself never touches the rules package.
"""

from __future__ import annotations

import pytest

from realm.commands.dispatcher import CommandContext, CommandDispatcher
from realm.core.objects import GameObject
from realm.core.propagation import Action
from realm.core.world import get_world
from realm.games.gurps.system import GurpsSystem
from realm.games.merc.system import MercSystem
from realm.gateway.session import Session
from realm.std.items.equipment import cmd_unwear, cmd_wear
from realm.std.rules.system import equipment_observer


def _player(name, location):
    player = GameObject(name=name, location=location)
    player.add_tag("player")
    sess = Session(protocol="test", address="127.0.0.1")
    sess.link_player(player)
    return player, sess


def _ctx(sess, args):
    return CommandContext(session=sess, player=sess.player, raw_input=args,
                          command_name="test", args=args,
                          dispatcher=CommandDispatcher())


@pytest.fixture
def bus(world):
    """The boot wiring in miniature: the observer on a bare world."""
    world.observe(equipment_observer)
    return world


@pytest.mark.asyncio
class TestMercWornArmor:

    async def test_wear_lowers_ac_remove_restores(self, bus):
        get_world().rules = MercSystem()
        room = GameObject("Arena", tags=["room"])
        hero, sess = _player("Conan", room)
        hero.db.dexterity = 13                      # base AC 10
        plate = GameObject("plate mail", location=hero,
                           tags=["thing", "wearable"])
        plate.db.slot = "body"
        plate.db.ac_apply = 8

        await cmd_wear(_ctx(sess, "plate"))
        assert plate.has_tag("worn")
        assert hero.db.get("armor_class") == 2      # 10 - 8

        await cmd_unwear(_ctx(sess, "plate"))
        assert not plate.has_tag("worn")
        assert hero.db.get("armor_class") == 10

    async def test_pieces_stack(self, bus):
        get_world().rules = MercSystem()
        room = GameObject("Arena", tags=["room"])
        hero, sess = _player("Conan", room)
        hero.db.dexterity = 13
        for name, slot, apply_ in (("plate mail", "body", 8),
                                   ("iron helm", "head", 3)):
            item = GameObject(name, location=hero, tags=["thing", "wearable"])
            item.db.slot = slot
            item.db.ac_apply = apply_
        await cmd_wear(_ctx(sess, "plate"))
        await cmd_wear(_ctx(sess, "helm"))
        assert hero.db.get("armor_class") == -1     # 10 - 8 - 3


@pytest.mark.asyncio
class TestSeamStaysNeutral:

    async def test_default_system_is_a_noop(self, bus):
        # GURPS caches nothing from gear (no armor-DR pipeline yet): wearing
        # goggles must neither crash nor invent an armor_class.
        get_world().rules = GurpsSystem()
        room = GameObject("Room", tags=["room"])
        raven, sess = _player("Raven", room)
        goggles = GameObject("goggles", location=raven,
                             tags=["thing", "wearable"])
        await cmd_wear(_ctx(sess, "goggles"))
        assert goggles.has_tag("worn")
        assert raven.db.get("armor_class") is None

    async def test_no_active_system_is_safe(self, bus):
        # A bare engine (tests, tools) has no game system installed.
        bus.rules = None
        room = GameObject("Room", tags=["room"])
        raven, sess = _player("Raven", room)
        cloak = GameObject("cloak", location=raven,
                           tags=["thing", "wearable"])
        await cmd_wear(_ctx(sess, "cloak"))
        assert cloak.has_tag("worn")

    async def test_observer_ignores_unapplied_and_unrelated(self, bus):
        # A vetoed wear (applied=False) and a non-equipment action must not
        # trigger a recompute.
        calls = []

        class Spy(MercSystem):
            def on_equipment_change(self, player):
                calls.append(player.name)

        get_world().rules = Spy()
        hero = GameObject("Conan")
        vetoed = Action(actor=hero, target=None, action_type="item:on_wear")
        vetoed.applied = False
        await equipment_observer(vetoed)
        unrelated = Action(actor=hero, target=None, action_type="item:on_get")
        unrelated.applied = True
        await equipment_observer(unrelated)
        assert calls == []
        worn = Action(actor=hero, target=None, action_type="item:on_wear")
        worn.applied = True
        await equipment_observer(worn)
        assert calls == ["Conan"]
