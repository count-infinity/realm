"""
Economy kit: credits, shopkeepers (disposition-priced), pay + the
ON_PAYMENT softcode hook (the B2 bribed ogre).
"""

from __future__ import annotations

import pytest

from realm.behaviors.shop import ShopkeeperBehavior, find_shopkeeper
from realm.core.disposition import set_disposition
from realm.core.economy import adjust_credits, get_credits, transfer_credits
from realm.core.objects import GameObject
from realm.core.propagation import get_engine, reset_engine
from realm.gateway.session import Session
from tests.test_olc import MockPersistence, make_context, use_persistence


@pytest.fixture(autouse=True)
def fresh_engine():
    reset_engine()
    yield
    reset_engine()


class TestEconomyCore:

    def test_balances_never_negative(self):
        bob = GameObject("Bob")
        assert get_credits(bob) == 0
        assert adjust_credits(bob, 50) is True
        assert adjust_credits(bob, -60) is False
        assert get_credits(bob) == 50

    def test_transfer(self):
        bob = GameObject("Bob")
        merchant = GameObject("merchant")
        adjust_credits(bob, 30)
        assert transfer_credits(bob, merchant, 20) is True
        assert get_credits(bob) == 10 and get_credits(merchant) == 20
        assert transfer_credits(bob, merchant, 999) is False
        assert transfer_credits(bob, merchant, -5) is False


class TestShopPricing:

    def _shop(self):
        room = GameObject("Bazaar", tags=["room"])
        keeper = GameObject("merchant", tags=["npc"], location=room)
        behavior = ShopkeeperBehavior(markup=1.2, buyback=0.5)
        keeper.add_behavior(behavior)
        sword = GameObject("sword", tags=["thing"], location=keeper)
        sword.db.value = 100
        bob = GameObject("Bob", tags=["player"], location=room)
        return room, keeper, behavior, sword, bob

    def test_neutral_prices(self):
        _room, keeper, behavior, sword, bob = self._shop()
        assert behavior.price_to_buy(keeper, sword, bob) == 120
        assert behavior.price_to_sell(keeper, sword, bob) == 50

    def test_disposition_moves_prices(self):
        _room, keeper, behavior, sword, bob = self._shop()
        set_disposition(keeper, bob, 3)   # devoted: -15% buying, +15% selling
        assert behavior.price_to_buy(keeper, sword, bob) == 102
        assert behavior.price_to_sell(keeper, sword, bob) == 57
        set_disposition(keeper, bob, -3)  # hostile pricing
        assert behavior.price_to_buy(keeper, sword, bob) == 138

    def test_find_shopkeeper(self):
        room, keeper, _b, _s, _bob = self._shop()
        found = find_shopkeeper(room)
        assert found is not None and found[0] is keeper
        assert find_shopkeeper(GameObject("Empty", tags=["room"])) is None

    def test_wares_hide_wielded_and_no_sell(self):
        _room, keeper, behavior, sword, _bob = self._shop()
        heirloom = GameObject("heirloom", tags=["thing", "no_sell"],
                              location=keeper)
        assert heirloom not in behavior.wares(keeper)
        assert sword in behavior.wares(keeper)


@pytest.mark.asyncio
class TestShopCommands:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    def _shop(self):
        room = GameObject("Bazaar", tags=["room"])
        keeper = GameObject("merchant", tags=["npc"], location=room)
        keeper.add_behavior(ShopkeeperBehavior())
        medkit = GameObject("medkit", tags=["thing"], location=keeper)
        medkit.db.value = 50
        bob = GameObject("Bob", tags=["player"], location=room)
        return room, keeper, medkit, bob

    async def test_list_shows_wares_and_prices(self):
        from realm.commands.builtin.economy import cmd_list
        _room, _keeper, _medkit, bob = self._shop()
        ctx = make_context(bob)
        await cmd_list(ctx)
        assert any("medkit — 60 credits" in m for m in ctx.session.messages)

    async def test_buy_moves_item_and_money(self):
        from realm.commands.builtin.economy import cmd_buy
        _room, keeper, medkit, bob = self._shop()
        adjust_credits(bob, 100)

        ctx = make_context(bob, args="medkit")
        await cmd_buy(ctx)

        assert medkit.location is bob
        assert get_credits(bob) == 40 and get_credits(keeper) == 60

    async def test_buy_refused_when_broke(self):
        from realm.commands.builtin.economy import cmd_buy
        _room, _keeper, medkit, bob = self._shop()
        ctx = make_context(bob, args="medkit")
        await cmd_buy(ctx)
        assert medkit.location is not bob
        assert any("can't afford" in m for m in ctx.session.messages)

    async def test_sell_pays_out(self):
        from realm.commands.builtin.economy import cmd_sell
        _room, keeper, _medkit, bob = self._shop()
        adjust_credits(keeper, 100)
        loot = GameObject("scrap", tags=["thing"], location=bob)
        loot.db.value = 20

        ctx = make_context(bob, args="scrap")
        await cmd_sell(ctx)

        assert loot.location is keeper
        assert get_credits(bob) == 10  # 20 * 0.5 buyback


@pytest.mark.asyncio
class TestPayAndBribes:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    async def test_pay_transfers_and_messages(self):
        from realm.commands.builtin.economy import cmd_pay
        room = GameObject("Bridge", tags=["room"])
        bob = GameObject("Bob", tags=["player"], location=room)
        troll = GameObject("troll", tags=["npc"], location=room)
        adjust_credits(bob, 30)

        ctx = make_context(bob, args="25 to troll")
        await cmd_pay(ctx)

        assert get_credits(troll) == 25 and get_credits(bob) == 5

    async def test_bribed_ogre_softcode_reacts(self):
        """The B2 classic: ON_PAYMENT softcode judges the bribe."""
        from realm.commands.builtin.economy import cmd_pay
        from realm.scripting.engine import ScriptEngine

        room = GameObject("Cave", tags=["room"])
        bob = GameObject("Bob", tags=["player"], location=room)
        sess = Session(protocol="test", address="1.1.1.1")
        sess.link_player(bob)
        ogre = GameObject("ogre", tags=["npc", "hostile"], location=room)
        ogre.db.on_payment = (
            "if get_attr(me, 'credits', 0) >= 20:\n"
            "    remove_tag(me, 'hostile')\n"
            "    say('Hurr. You pass, little one.')\n"
            "else:\n"
            "    say('Not enough shinies!')"
        )
        adjust_credits(bob, 50)

        engine = ScriptEngine()
        get_engine().add_observer(engine.handle_action)

        ctx = make_context(bob, args="25 to ogre")
        ctx.session.link_player(bob)
        await cmd_pay(ctx)

        assert get_credits(ogre) == 25
        assert not ogre.has_tag('hostile')

    async def test_insufficient_bribe(self):
        from realm.commands.builtin.economy import cmd_pay
        room = GameObject("Cave", tags=["room"])
        bob = GameObject("Bob", tags=["player"], location=room)
        troll = GameObject("troll", location=room, tags=["npc"])
        ctx = make_context(bob, args="25 to troll")
        await cmd_pay(ctx)
        assert get_credits(troll) == 0
        assert any("don't have" in m for m in ctx.session.messages)


@pytest.mark.asyncio
class TestMoneySoftcode:

    async def test_credits_and_authority(self):
        from realm.scripting.functions import ScriptFunctions

        room = GameObject("Vault", tags=["room"])
        npc = GameObject("banker", location=room)
        alice = GameObject("Alice", tags=["player"], location=room)
        adjust_credits(alice, 40)

        funcs = ScriptFunctions(executor=npc)
        assert funcs.credits(alice) == 40
        # The banker can't script money OUT of a player...
        assert funcs.transfer_credits(alice, npc, 10) is False
        # ...but pays out of its own pocket freely.
        adjust_credits(npc, 100)
        assert funcs.transfer_credits(npc, alice, 60) is True
        assert funcs.credits(alice) == 100
        # Minting requires controlling the target.
        assert funcs.adjust_credits(alice, 999) is False
        assert funcs.adjust_credits(npc, 999) is True
