"""
Showcase arc "Working economy" (items 86 -> 63 -> 87 -> 89 -> 92) —
every tutorial transcript driven end-to-end through the dispatcher,
exactly as the docs have the builder type it.

Docs: docs/showcase/arc_economy.md, 086_currency.md, 063_shopkeeper.md,
087_bank_accounts.md, 089_auction_house.md, 092_commodity_market.md.

The tutorial *is* the single source of truth: each build's command lines
are read straight out of its markdown "Build it" section and typed at the
dispatcher. Nothing here mirrors them, so nothing here can drift from
them — if this file is green, the lines the docs print work.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

import realm.behaviors  # noqa: F401 — registers shopkeeper/script_ticker
from realm.core.economy import get_credits
from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

# The arc prologue (arc_economy.md, "Build order and prerequisites").
# 086 digs the square itself, as the first two lines of its own Build it;
# every other tutorial assumes it already exists.
PROLOGUE = [
    "@dig Market Square",
    "@teleport Market Square",
]


def build_lines(doc_name: str) -> list[str]:
    """Every command line in the tutorial's "Build it" fenced blocks."""
    body = (DOCS / doc_name).read_text()
    match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
    assert match, f"{doc_name}: no Build it section"
    lines: list[str] = []
    for block in re.findall(r"```(?:text)?\n(.*?)```", match.group(1), re.S):
        lines.extend(line for line in block.splitlines() if line.strip())
    assert lines, f"{doc_name}: empty Build it"
    return lines


# --- Harness -------------------------------------------------------------------


class ArcWorld:
    """A wizard (Vala) and two mortals (Bob, Cass); the arc prologue digs
    Market Square live, exactly as arc_economy.md opens."""

    def __init__(self):
        self.sim = Simulator()
        self.landing = self.sim.room("The Landing")
        self.docks = self.sim.room("The Docks")
        self.vala = self.sim.player("Vala", location=self.landing)
        self.vala.add_tag("admin")
        self.bob = self.sim.player("Bob", location=self.landing)
        self.cass = self.sim.player("Cass", location=self.landing)
        self.square = None

    async def build(self, doc_name):
        """Type one tutorial's Build-it transcript, read from its doc."""
        lines = build_lines(doc_name)
        # 086's own first lines dig the square; the rest need the prologue.
        if PROLOGUE[0] not in lines:
            for line in PROLOGUE:
                await self.sim.do(self.vala, line)
        for line in lines:
            await self.sim.do(self.vala, line)
        self.square = self.find("Market Square")
        assert self.square is not None
        assert self.vala.location is self.square
        # The mortals wander in behind the wizard.
        self.bob.location = self.square
        self.cass.location = self.square

    def text(self, player) -> str:
        return "\n".join(self.sim.seen(player))

    def find(self, name):
        hits = self.sim.store.find_cached(name=name)
        return hits[0] if hits else None

    def close(self):
        self.sim.close()


@pytest.fixture
async def world():
    w = ArcWorld()
    try:
        yield w
    finally:
        w.close()


def cash_stacks(holder):
    return [o for o in holder.contents if o.has_tag("cash")]


def face_value(holder):
    return sum(int(o.db.get("denom") or 0) * int(o.db.get("count") or 0)
               for o in cash_stacks(holder))


# --- 086 tests -------------------------------------------------------------------


@pytest.mark.asyncio
class TestCurrency:

    async def test_cashout_makes_optimal_change_and_conserves_value(self, world):
        w = world
        await w.build("086_currency.md")
        mint = w.find("the Mint")
        assert mint is not None and mint.location is w.square

        await w.sim.do(w.vala, "@eval adjust_credits(me, 137)")
        await w.sim.do(w.vala, "credits")
        assert "You are carrying 137 credits." in w.text(w.vala)

        await w.sim.do(w.vala, "cashout 137")
        out = w.text(w.vala)
        assert "The Mint counts out 137 credits in coin." in out
        await w.sim.do(w.vala, "inventory")
        assert "a stack of 3 ten-credit chits" in w.text(w.vala)
        # Wallet emptied; the Mint's reserve backs every coin in play.
        assert get_credits(w.vala) == 0
        assert get_credits(mint) == 137
        # Greedy change: 1 bar, 3 chits, 7 chips.
        stacks = {o.name: (o.db.get("denom"), o.db.get("count"))
                  for o in cash_stacks(w.vala)}
        assert stacks == {
            "a stack of 1 hundred-credit bar": (100, 1),
            "a stack of 3 ten-credit chits": (10, 3),
            "a stack of 7 one-credit chips": (1, 7),
        }
        assert face_value(w.vala) == 137

    async def test_pocket_melts_coins_back_into_the_wallet(self, world):
        w = world
        await w.build("086_currency.md")
        mint = w.find("the Mint")
        await w.sim.do(w.vala, "@eval adjust_credits(me, 137)")
        await w.sim.do(w.vala, "cashout 137")

        await w.sim.do(w.vala, "pocket")
        assert "You pocket 137 credits." in w.text(w.vala)
        assert get_credits(w.vala) == 137
        assert get_credits(mint) == 0
        assert cash_stacks(w.vala) == []

    async def test_cashout_refused_when_wallet_short(self, world):
        w = world
        await w.build("086_currency.md")
        await w.sim.do(w.vala, "cashout 9999")
        assert "Your wallet cannot cover that." in w.text(w.vala)
        assert cash_stacks(w.vala) == []

    async def test_physical_cash_changes_hands_like_any_object(self, world):
        w = world
        await w.build("086_currency.md")
        mint = w.find("the Mint")
        await w.sim.do(w.vala, "@eval adjust_credits(me, 25)")
        await w.sim.do(w.vala, "cashout 25")

        await w.sim.do(w.vala, "give a stack of 2 ten-credit chits to Bob")
        assert face_value(w.bob) == 20

        await w.sim.do(w.bob, "pocket")
        assert get_credits(w.bob) == 20
        # Conservation: the reserve still backs exactly the coins left out.
        assert get_credits(mint) == face_value(w.vala) == 5

    async def test_exchange_remints_to_fewest_pieces(self, world):
        w = world
        await w.build("086_currency.md")
        await w.sim.do(w.vala, "@eval adjust_credits(me, 15)")
        await w.sim.do(w.vala, "cashout 5")
        await w.sim.do(w.vala, "cashout 5")
        await w.sim.do(w.vala, "cashout 5")
        assert len(cash_stacks(w.vala)) == 3          # three chip stacks

        await w.sim.do(w.vala, "exchange")
        stacks = {o.name for o in cash_stacks(w.vala)}
        assert stacks == {"a stack of 1 ten-credit chit",
                          "a stack of 5 one-credit chips"}
        assert face_value(w.vala) == 15               # value unchanged


# --- 063 tests -------------------------------------------------------------------


@pytest.mark.asyncio
class TestShopkeeper:

    async def test_native_shop_lists_and_sells(self, world):
        w = world
        await w.build("063_shopkeeper.md")
        vex = w.find("Trader Vex")
        assert vex is not None

        await w.sim.do(w.vala, "@eval adjust_credits(me, 100)")
        await w.sim.do(w.vala, "list")
        out = w.text(w.vala)
        assert "a stimpack — 26 credits" in out       # 20 * 1.3
        assert "a ration bar — 6 credits" in out      # round(5 * 1.3) = 6

        await w.sim.do(w.vala, "buy stimpack")
        assert get_credits(w.vala) == 100 - 26
        assert get_credits(vex) == 26
        assert any(o.name == "a stimpack" for o in w.vala.contents)

    async def test_restock_tick_refills_the_shelves(self, world):
        w = world
        await w.build("063_shopkeeper.md")
        vex = w.find("Trader Vex")
        await w.sim.do(w.vala, "@eval adjust_credits(me, 100)")
        await w.sim.do(w.vala, "buy stimpack")
        assert not any(o.name == "a stimpack" for o in vex.contents)

        await w.sim.do(w.vala, "@tr Trader Vex/on_tick")
        stims = [o for o in vex.contents if o.name == "a stimpack"]
        rations = [o for o in vex.contents if o.name == "a ration bar"]
        assert len(stims) == 3 and len(rations) == 5
        assert all(int(o.db.get("value")) == 20 for o in stims)

    async def test_tip_moves_disposition_and_prices(self, world):
        w = world
        await w.build("063_shopkeeper.md")
        await w.sim.do(w.vala, "@eval adjust_credits(me, 100)")

        await w.sim.do(w.vala, "pay 10 to Trader Vex")
        out = w.text(w.vala)
        assert "Much obliged, Vala." in out           # ON_PAYMENT fired

        await w.sim.do(w.vala, "list")
        assert "a stimpack — 25 credits" in w.text(w.vala)  # 20*1.3*0.95

    async def test_sell_pays_buyback_price(self, world):
        w = world
        await w.build("063_shopkeeper.md")
        vex = w.find("Trader Vex")
        await w.sim.do(w.vala, "@eval adjust_credits(me, 100)")
        await w.sim.do(w.vala, "buy stimpack")        # vex now holds 26

        await w.sim.do(w.vala, "sell stimpack")
        # 20 * 0.4 = 8 at neutral disposition.
        assert get_credits(w.vala) == 100 - 26 + 8
        assert any(o.name == "a stimpack" for o in vex.contents)


# --- 087 tests -------------------------------------------------------------------


@pytest.mark.asyncio
class TestBank:

    async def test_deposit_withdraw_and_audit_log(self, world):
        w = world
        await w.build("087_bank_accounts.md")
        bank = w.find("First Orbital Bank")
        await w.sim.do(w.vala, "@eval adjust_credits(me, 400)")

        await w.sim.do(w.vala, "deposit 300")
        assert "Deposited 300 credits. Balance: 300." in w.text(w.vala)
        assert get_credits(w.vala) == 100
        assert get_credits(bank) == 300               # the vault holds it
        assert bank.db.get("acct_" + w.vala.id) == 300

        await w.sim.do(w.vala, "withdraw 50")
        assert "Withdrew 50 credits. Balance: 250." in w.text(w.vala)
        assert get_credits(w.vala) == 150
        assert bank.db.get("acct_" + w.vala.id) == 250

        await w.sim.do(w.vala, "bank")
        out = w.text(w.vala)
        assert "Account balance: 250 credits." in out
        assert "deposit 300 -> balance 300" in out
        assert "withdraw 50 -> balance 250" in out

    async def test_withdraw_beyond_balance_refused(self, world):
        w = world
        await w.build("087_bank_accounts.md")
        await w.sim.do(w.vala, "@eval adjust_credits(me, 100)")
        await w.sim.do(w.vala, "deposit 100")
        await w.sim.do(w.vala, "withdraw 500")
        assert "Insufficient funds on account." in w.text(w.vala)
        assert get_credits(w.vala) == 0

    async def test_transfer_reaches_a_player_in_another_room(self, world):
        w = world
        await w.build("087_bank_accounts.md")
        bank = w.find("First Orbital Bank")
        await w.sim.do(w.vala, "@eval move_to(get('Bob'), 'The Docks', force=True)")
        assert w.bob.location is w.docks

        await w.sim.do(w.vala, "@eval adjust_credits(me, 400)")
        await w.sim.do(w.vala, "deposit 300")
        await w.sim.do(w.vala, "xfer 100 to Bob")
        assert "Wired 100 credits." in w.text(w.vala)

        assert bank.db.get("acct_" + w.vala.id) == 200
        assert bank.db.get("acct_" + w.bob.id) == 100
        # Ledger money moved without the recipient present — and he heard.
        assert "Vala wires you 100 credits at First Orbital Bank." in w.text(w.bob)
        # Reserve unchanged by an internal transfer.
        assert get_credits(bank) == 300

    async def test_interest_tick_pays_every_member(self, world):
        w = world
        await w.build("087_bank_accounts.md")
        bank = w.find("First Orbital Bank")
        await w.sim.do(w.vala, "@eval adjust_credits(me, 400)")
        await w.sim.do(w.vala, "deposit 300")
        await w.sim.do(w.vala, "withdraw 50")
        await w.sim.do(w.vala, "xfer 100 to Bob")

        await w.sim.do(w.vala, "@tr First Orbital Bank/on_tick")
        assert bank.db.get("acct_" + w.vala.id) == 157   # 150 + 5%
        assert bank.db.get("acct_" + w.bob.id) == 105    # 100 + 5%
        # The faucet is explicit: the bank minted reserve to back interest.
        assert get_credits(bank) == 250 + 7 + 5

        await w.sim.do(w.vala, "bank")
        assert "interest 7 -> balance 157" in w.text(w.vala)


# --- 089 tests -------------------------------------------------------------------


@pytest.mark.asyncio
class TestAuction:

    async def _open(self, w):
        await w.build("089_auction_house.md")
        await w.sim.do(w.vala, "@eval adjust_credits(get('Bob'), 200)")
        await w.sim.do(w.vala, "@eval adjust_credits(get('Cass'), 200)")
        return w.find("the Auction Kiosk")

    async def test_listing_escrows_the_item(self, world):
        w = world
        kiosk = await self._open(w)
        await w.sim.do(w.vala, "@create plasma torch")
        await w.sim.do(w.vala, "auction plasma torch for 50")
        assert "Listed." in w.text(w.vala)

        torch = w.find("plasma torch")
        assert torch.location is kiosk                # seller can't touch it
        lot = kiosk.db.get("lot_1")
        assert lot["item_name"] == "plasma torch" and lot["min"] == 50
        assert "lists plasma torch as lot #1 (min 50)." in w.text(w.bob)

        await w.sim.do(w.bob, "auctions")
        out = w.text(w.bob)
        assert "#1 plasma torch — min 50, bid none" in out

    async def test_bids_escrow_and_outbids_refund(self, world):
        w = world
        kiosk = await self._open(w)
        await w.sim.do(w.vala, "@create plasma torch")
        await w.sim.do(w.vala, "auction plasma torch for 50")

        await w.sim.do(w.bob, "bid 1 60")
        assert "Bid placed." in w.text(w.bob)
        assert get_credits(w.bob) == 140              # escrowed instantly

        await w.sim.do(w.cass, "bid 1 75")
        assert get_credits(w.cass) == 125
        assert get_credits(w.bob) == 200              # refunded on the spot
        assert "You are outbid on lot #1; 60 credits refunded." in w.text(w.bob)

        await w.sim.do(w.bob, "bid 1 70")             # below 76 floor
        assert "bid below 76" in w.text(w.bob)
        assert get_credits(w.bob) == 200
        assert kiosk.db.get("lot_1")["bidder_name"] == "Cass"

    async def test_snipe_bid_extends_the_deadline(self, world):
        w = world
        kiosk = await self._open(w)
        await w.sim.do(w.vala, "@set the Auction Kiosk/duration = 10")
        await w.sim.do(w.vala, "@create old boot")
        await w.sim.do(w.vala, "auction old boot for 5")
        ends_before = kiosk.db.get("lot_1")["ends"]

        await w.sim.do(w.bob, "bid 1 5")              # inside the 30s window
        ends_after = kiosk.db.get("lot_1")["ends"]
        assert ends_after > ends_before               # deadline pushed out

    async def test_settlement_pays_seller_and_delivers_item(self, world):
        w = world
        kiosk = await self._open(w)
        await w.sim.do(w.vala, "@set the Auction Kiosk/duration = 0")
        await w.sim.do(w.vala, "@set the Auction Kiosk/snipe = 0")
        await w.sim.do(w.vala, "@create crystal skull")
        await w.sim.do(w.vala, "auction crystal skull for 10")
        await w.sim.do(w.cass, "bid 1 20")
        vala_before = get_credits(w.vala)

        await w.sim.do(w.vala, "@tr the Auction Kiosk/on_tick")
        skull = w.find("crystal skull")
        assert skull.location is w.cass
        assert get_credits(w.vala) == vala_before + 20
        assert kiosk.db.get("lot_1") is None
        assert kiosk.db.get("history") == ["crystal skull -> Cass at 20"]
        assert "The gavel falls: crystal skull goes to Cass for 20 credits." \
            in w.text(w.bob)

    async def test_unsold_lot_returns_to_seller(self, world):
        w = world
        kiosk = await self._open(w)
        await w.sim.do(w.vala, "@set the Auction Kiosk/duration = 0")
        await w.sim.do(w.vala, "@create broken fork")
        await w.sim.do(w.vala, "auction broken fork for 5")

        await w.sim.do(w.vala, "@tr the Auction Kiosk/on_tick")
        fork = w.find("broken fork")
        assert fork.location is w.vala
        assert "finds no buyer" in w.text(w.bob)
        assert kiosk.db.get("history") == ["broken fork -> unsold at 0"]

    async def test_cancel_before_bids_only(self, world):
        w = world
        kiosk = await self._open(w)
        await w.sim.do(w.vala, "@create silver ring")
        await w.sim.do(w.vala, "auction silver ring for 5")

        await w.sim.do(w.bob, "cancel 1")             # not his lot
        assert "Not your lot" in w.text(w.bob)

        await w.sim.do(w.vala, "cancel 1")
        assert "Listing withdrawn." in w.text(w.vala)
        ring = w.find("silver ring")
        assert ring.location is w.vala
        assert kiosk.db.get("lot_1") is None


# --- 092 tests -------------------------------------------------------------------


@pytest.mark.asyncio
class TestCommodityMarket:

    async def test_board_renders_prices_and_supply(self, world):
        w = world
        await w.build("092_commodity_market.md")
        await w.sim.do(w.vala, "market")
        out = w.text(w.vala)
        assert "Commodity        buy  sell  supply" in out
        assert "Water Ice        12  10  200" in out
        assert "Helium-3         60  54  100" in out

    async def test_buying_mints_cargo_and_dents_supply(self, world):
        w = world
        await w.build("092_commodity_market.md")
        board = w.find("the Commodity Board")
        await w.sim.do(w.vala, "@eval adjust_credits(me, 1000)")

        await w.sim.do(w.vala, "market buy 50 water_ice")
        assert "You buy 50 units of Water Ice for 600 credits." in w.text(w.vala)
        assert get_credits(w.vala) == 400
        assert get_credits(board) == 10600
        assert board.db.get("goods")["water_ice"]["supply"] == 150
        lots = [o for o in w.vala.contents if o.has_tag("cargo")]
        assert len(lots) == 1
        assert lots[0].db.get("commodity") == "water_ice"
        assert lots[0].db.get("units") == 50

    async def test_drift_moves_price_toward_scarcity(self, world):
        w = world
        await w.build("092_commodity_market.md")
        board = w.find("the Commodity Board")
        await w.sim.do(w.vala, "@eval adjust_credits(me, 1000)")
        await w.sim.do(w.vala, "market buy 50 water_ice")

        await w.sim.do(w.vala, "@tr the Commodity Board/drift")
        goods = board.db.get("goods")
        assert goods["water_ice"]["supply"] == 152    # 5% relaxation
        # fair = 12*200/152 ≈ 15.8; one 25% step + ≤3% noise.
        assert 12.4 <= goods["water_ice"]["price"] <= 13.5
        assert goods["water_ice"]["price"] > 12

    async def test_selling_melts_cargo_back_into_supply(self, world):
        w = world
        await w.build("092_commodity_market.md")
        board = w.find("the Commodity Board")
        await w.sim.do(w.vala, "@eval adjust_credits(me, 1000)")
        await w.sim.do(w.vala, "market buy 50 water_ice")
        wallet = get_credits(w.vala)
        price = board.db.get("goods")["water_ice"]["price"]
        expected = int(price * 0.9) * 50

        await w.sim.do(w.vala, "market sell water_ice")
        assert f"The exchange pays {expected} credits" in w.text(w.vala)
        assert get_credits(w.vala) == wallet + expected
        assert board.db.get("goods")["water_ice"]["supply"] == 200
        assert not any(o.has_tag("cargo") for o in w.vala.contents)

    async def test_news_event_shocks_supply_and_announces(self, world):
        w = world
        await w.build("092_commodity_market.md")
        board = w.find("the Commodity Board")
        before = {cid: g["supply"]
                  for cid, g in board.db.get("goods").items()}

        await w.sim.do(w.vala, "@tr the Commodity Board/news")
        goods = board.db.get("goods")
        changed = [cid for cid in goods
                   if goods[cid]["supply"] != before[cid]]
        assert len(changed) == 1
        cid = changed[0]
        assert goods[cid]["supply"] in (int(before[cid] * 0.5),
                                        int(before[cid] * 1.5))
        assert "[Market]" in w.text(w.bob)
