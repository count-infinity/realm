"""
Showcase arc "Working economy" (items 86 -> 63 -> 87 -> 89 -> 92) —
every tutorial transcript driven end-to-end through the dispatcher,
exactly as the docs have the builder type it.

Docs: docs/showcase/arc_economy.md, 086_currency.md, 063_shopkeeper.md,
087_bank_accounts.md, 089_auction_house.md, 092_commodity_market.md.

The transcripts below are the single source of truth: the BUILD_* lists
are verbatim the "Build it" command lines of each tutorial. If this file
is green, the typed lines work.
"""

from __future__ import annotations

import pytest

import realm.behaviors  # noqa: F401 — registers shopkeeper/script_ticker
from realm.core.economy import get_credits
from realm.testing import Simulator

# --- Arc prologue (arc_economy.md / 086 "Build it") ----------------------------

PROLOGUE = [
    "@dig Market Square",
    "@teleport Market Square",
]

# --- 086. Multi-denomination currency -----------------------------------------

BUILD_MINT = [
    "@create the Mint",
    "drop the Mint",
    "@set the Mint/change = b, r = divmod(int(arg0), 100); c, u = divmod(r, 10); result = [[b, 100, 'hundred-credit bar'], [c, 10, 'ten-credit chit'], [u, 1, 'one-credit chip']]",
    "@set the Mint/cmd_cashout = $cashout *:amt = int(arg0); ok = amt > 0 and transfer_credits(enactor, me, amt); pemit(enactor, f'The Mint counts out {amt} credits in coin.' if ok else 'Your wallet cannot cover that.'); [(set_attr(c, 'denom', d), set_attr(c, 'count', n)) for g, a in [[ok, amt]] if g for n, d, nm in eval_attr(me, 'change', a) if n for c in [create_obj(f\"a stack of {n} {nm}{'s' if n > 1 else ''}\", tags=['thing', 'cash'], location=enactor)]]",
    "@set the Mint/cmd_pocket = $pocket:total = sum(get_attr(o, 'denom', 0) * get_attr(o, 'count', 0) for o in contents(enactor) if has_tag(o, 'cash')); ok = transfer_credits(me, enactor, total); [destroy_obj(o) for g in [ok] if g for o in contents(enactor) if has_tag(o, 'cash')]; pemit(enactor, f'You pocket {total} credits.' if ok else 'You are not carrying any coin.')",
    "@set the Mint/cmd_exchange = $exchange:total = sum(get_attr(o, 'denom', 0) * get_attr(o, 'count', 0) for o in contents(enactor) if has_tag(o, 'cash')); [destroy_obj(o) for t in [total] if t for o in contents(enactor) if has_tag(o, 'cash')]; [(set_attr(c, 'denom', d), set_attr(c, 'count', n)) for t in [total] if t for n, d, nm in eval_attr(me, 'change', t) if n for c in [create_obj(f\"a stack of {n} {nm}{'s' if n > 1 else ''}\", tags=['thing', 'cash'], location=enactor)]]; pemit(enactor, 'The Mint remints your coin: same value, fewest pieces.' if total else 'You have no coin to exchange.')",
]

# --- 063. Shopkeeper -----------------------------------------------------------

BUILD_SHOP = [
    "@create Trader Vex",
    "@tag Trader Vex = npc",
    "drop Trader Vex",
    "@behavior Trader Vex = shopkeeper, markup:1.3, buyback:0.4",
    "@create a stimpack",
    "@set a stimpack/value = 20",
    "give a stimpack to Trader Vex",
    "@create a ration bar",
    "@set a ration bar/value = 5",
    "give a ration bar to Trader Vex",
    '@set Trader Vex/stocklist = [["a stimpack", 3, 20], ["a ration bar", 5, 5]]',
    "@set Trader Vex/restock = [set_attr(create_obj(nm, location=me), 'value', v) for nm, k, v in V('stocklist', []) for j in range(k - len([o for o in contents(me) if name(o) == nm]))]; result = 1",
    "@behavior Trader Vex = script_ticker, interval:8",
    "@set Trader Vex/on_tick = eval_attr(me, 'restock')",
    "@set Trader Vex/ON_PAYMENT = say(f'Much obliged, {name(enactor)}.'); adjust_disposition(me, enactor, 1)",
]

# --- 087. Bank accounts --------------------------------------------------------

BUILD_BANK = [
    "@create First Orbital Bank",
    "drop First Orbital Bank",
    "@set First Orbital Bank/rate = 5",
    "@set First Orbital Bank/log_row = k = 'log_' + arg0; set_attr(me, k, (V(k, []) + [f'{arg1} {arg2} -> balance {arg3}'])[-10:]); result = 1",
    "@set First Orbital Bank/cmd_bank = $bank:pemit(enactor, f\"Account balance: {V('acct_' + enactor.id, 0)} credits.\"); [pemit(enactor, '  ' + row) for row in V('log_' + enactor.id, [])]",
    "@set First Orbital Bank/cmd_deposit = $deposit *:amt = int(arg0); ok = amt > 0 and transfer_credits(enactor, me, amt); bal = V('acct_' + enactor.id, 0) + amt; [(incr('acct_' + enactor.id, a), set_attr(me, 'members', sorted(set(V('members', []) + [enactor.id]))), eval_attr(me, 'log_row', enactor.id, 'deposit', a, b)) for g, a, b in [[ok, amt, bal]] if g]; pemit(enactor, f'Deposited {amt} credits. Balance: {bal}.' if ok else 'Your wallet cannot cover that.')",
    "@set First Orbital Bank/cmd_withdraw = $withdraw *:amt = int(arg0); bal = V('acct_' + enactor.id, 0); ok = 0 < amt <= bal and transfer_credits(me, enactor, amt); [(decr('acct_' + enactor.id, a), eval_attr(me, 'log_row', enactor.id, 'withdraw', a, b - a)) for g, a, b in [[ok, amt, bal]] if g]; pemit(enactor, f'Withdrew {amt} credits. Balance: {bal - amt}.' if ok else 'Insufficient funds on account.')",
    "@set First Orbital Bank/cmd_xfer = $xfer * to *:amt = int(arg0); who = get(arg1); bal = V('acct_' + enactor.id, 0); ok = who is not None and has_tag(who, 'player') and 0 < amt <= bal; [(decr('acct_' + enactor.id, a), incr('acct_' + w.id, a), set_attr(me, 'members', sorted(set(V('members', []) + [w.id]))), eval_attr(me, 'log_row', enactor.id, 'transfer to ' + name(w), a, b - a), eval_attr(me, 'log_row', w.id, 'transfer from ' + name(enactor), a, V('acct_' + w.id, 0)), pemit(w, f'{name(enactor)} wires you {a} credits at First Orbital Bank.')) for g, a, b, w in [[ok, amt, bal, who]] if g]; pemit(enactor, f'Wired {amt} credits.' if ok else 'No such account holder, or insufficient funds.')",
    "@behavior First Orbital Bank = script_ticker, interval:150",
    "@set First Orbital Bank/on_tick = [(adjust_credits(me, gain), incr('acct_' + pid, gain), eval_attr(me, 'log_row', pid, 'interest', gain, bal + gain)) for pid in V('members', []) for bal in [V('acct_' + pid, 0)] for gain in [bal * V('rate', 0) // 100] if gain > 0]",
]

# --- 089. Auction house --------------------------------------------------------

BUILD_AUCTION = [
    "@create the Auction Kiosk",
    "drop the Auction Kiosk",
    "@set the Auction Kiosk/duration = 120",
    "@set the Auction Kiosk/snipe = 30",
    "@set the Auction Kiosk/cmd_auction = $auction * for *:item = [o for o in contents(enactor) if name(o).lower() == arg0.strip().lower()]; ok = bool(item) and int(arg1) > 0; [(move_to(o, me), set_attr(me, 'lot_' + str(n), {'seller': enactor.id, 'seller_name': name(enactor), 'item': o.id, 'item_name': name(o), 'min': int(arg1), 'bid': 0, 'bidder': '', 'bidder_name': '', 'ends': now() + V('duration', 120)}), set_attr(me, 'next_lot', n + 1), remit(here, f'{name(enactor)} lists {name(o)} as lot #{n} (min {int(arg1)}).')) for g, lst in [[ok, item]] if g for o in [lst[0]] for n in [V('next_lot', 1)]]; pemit(enactor, 'Listed.' if ok else 'You are not carrying that, or the minimum is bad.')",
    "@set the Auction Kiosk/cmd_auctions = $auctions:pemit(enactor, 'Open lots:'); [pemit(enactor, f\"  #{i} {lot['item_name']} — min {lot['min']}, bid {str(lot['bid']) + ' by ' + lot['bidder_name'] if lot['bidder'] else 'none'}, {max(0, int(lot['ends'] - now()))}s left\") for i in range(1, V('next_lot', 1)) for lot in [V('lot_' + str(i))] if lot]",
    "@set the Auction Kiosk/cmd_bid = $bid * *:lot = V('lot_' + arg0.strip()); amt = int(arg1); low = (lot['bid'] + 1 if lot['bidder'] else lot['min']) if lot else 0; ok = bool(lot) and lot['seller'] != enactor.id and amt >= low and transfer_credits(enactor, me, amt); [(transfer_credits(me, get('#' + l['bidder']), l['bid']) if l['bidder'] else None, pemit(get('#' + l['bidder']), f\"You are outbid on lot #{arg0.strip()}; {l['bid']} credits refunded.\") if l['bidder'] else None, set_attr(me, 'lot_' + arg0.strip(), dict(l, bid=a, bidder=enactor.id, bidder_name=name(enactor), ends=(now() + V('snipe', 30) if l['ends'] - now() < V('snipe', 30) else l['ends']))), remit(here, f'{name(enactor)} bids {a} on lot #{arg0.strip()}.')) for g, l, a in [[ok, lot, amt]] if g]; pemit(enactor, 'Bid placed.' if ok else f'No such lot, your own lot, or bid below {low}.')",
    "@set the Auction Kiosk/settle = lot = V('lot_' + arg0); w = get('#' + lot['bidder']) if lot['bidder'] else None; s = get('#' + lot['seller']); it = get('#' + lot['item']); r = (move_to(it, w), transfer_credits(me, s, lot['bid']), remit(here, f\"The gavel falls: {lot['item_name']} goes to {lot['bidder_name']} for {lot['bid']} credits.\")) if w else (move_to(it, s) if it and s else None, remit(here, f\"{lot['item_name']} finds no buyer and returns to {lot['seller_name']}.\")); set_attr(me, 'history', (V('history', []) + [f\"{lot['item_name']} -> {lot['bidder_name'] or 'unsold'} at {lot['bid']}\"])[-20:]); del_attr(me, 'lot_' + arg0); result = 1",
    "@set the Auction Kiosk/cmd_cancel = $cancel *:lot = V('lot_' + arg0.strip()); ok = bool(lot) and lot['seller'] == enactor.id and not lot['bidder']; [(move_to(get('#' + l['item']), enactor), del_attr(me, 'lot_' + arg0.strip()), remit(here, f'{name(enactor)} withdraws lot #{arg0.strip()}.')) for g, l in [[ok, lot]] if g]; pemit(enactor, 'Listing withdrawn.' if ok else 'Not your lot, already bid on, or no such lot.')",
    "@behavior the Auction Kiosk = script_ticker, interval:4",
    "@set the Auction Kiosk/on_tick = [eval_attr(me, 'settle', i) for i in range(1, V('next_lot', 1)) for lot in [V('lot_' + str(i))] if lot and now() >= lot['ends']]",
]

# --- 092. Commodity market -----------------------------------------------------

BUILD_MARKET = [
    "@create the Commodity Board",
    "drop the Commodity Board",
    "@eval adjust_credits(get('the Commodity Board'), 10000)",
    '@set the Commodity Board/goods = {"water_ice": {"name": "Water Ice", "base_price": 12, "base_supply": 200, "price": 12, "supply": 200}, "helium3": {"name": "Helium-3", "base_price": 60, "base_supply": 100, "price": 60, "supply": 100}}',
    "@set the Commodity Board/cmd_market = $market:pemit(enactor, 'Commodity        buy  sell  supply'); [pemit(enactor, f\"{left(g['name'] + repeat(' ', 16), 16)} {ceil(g['price'])}  {floor(g['price'] * 0.9)}  {g['supply']}\") for cid in sorted(V('goods', {})) for g in [V('goods', {})[cid]]]",
    "@set the Commodity Board/cmd_buy = $market buy * *:g = V('goods', {}); units = int(arg0); cid = arg1.strip().lower(); cost = ceil(g[cid]['price']) * units if cid in g else 0; ok = cid in g and 0 < units <= g[cid]['supply'] and transfer_credits(enactor, me, cost); upd = g[cid].update({'supply': g[cid]['supply'] - units}) if ok else None; save = set_attr(me, 'goods', g) if ok else None; lot = create_obj(f\"a sealed cargo lot ({g[cid]['name']})\", tags=['thing', 'cargo'], location=enactor) if ok else None; mark = (set_attr(lot, 'commodity', cid), set_attr(lot, 'units', units)) if ok else None; pemit(enactor, f\"You buy {units} units of {g[cid]['name']} for {cost} credits.\" if ok else 'No such commodity, not enough supply, or not enough credits.')",
    "@set the Commodity Board/cmd_sell = $market sell *:g = V('goods', {}); cid = arg0.strip().lower(); lots = [o for o in contents(enactor) if has_tag(o, 'cargo') and get_attr(o, 'commodity') == arg0.strip().lower()]; ok = bool(lots) and cid in g; units = get_attr(lots[0], 'units', 0) if ok else 0; pay = floor(g[cid]['price'] * 0.9) * units if ok else 0; paid = ok and transfer_credits(me, enactor, pay); upd = g[cid].update({'supply': g[cid]['supply'] + units}) if paid else None; save = set_attr(me, 'goods', g) if paid else None; junk = destroy_obj(lots[0]) if paid else None; pemit(enactor, f\"The exchange pays {pay} credits for {units} units of {g[cid]['name']}.\" if paid else 'You carry no such cargo lot, or the exchange cannot cover it.')",
    "@set the Commodity Board/drift = [(g.update({'supply': g['supply'] + (int((g['base_supply'] - g['supply']) * 0.05) or (1 if g['base_supply'] > g['supply'] else -1))}) if g['supply'] != g['base_supply'] else None, g.update({'price': round(min(max((g['price'] + (g['base_price'] * g['base_supply'] / max(g['supply'], 1) - g['price']) * 0.25) * rand(97, 103) / 100.0, g['base_price'] * 0.2), g['base_price'] * 5), 2)})) for cid, g in V('goods', {}).items()]; set_attr(me, 'goods', V('goods', {})); result = 1",
    "@set the Commodity Board/news = g = V('goods', {}); cid = sorted(g)[rand(0, len(g) - 1)]; raid = rand(0, 1) == 1; g[cid]['supply'] = max(1, int(g[cid]['supply'] * (0.5 if raid else 1.5))); set_attr(me, 'goods', g); remit(here, '[Market] ' + (f\"Pirate raids choke off {g[cid]['name']} shipments!\" if raid else f\"A glut freighter floods the docks with {g[cid]['name']}!\")); result = 1",
    "@behavior the Commodity Board = script_ticker, interval:8",
    "@set the Commodity Board/on_tick = eval_attr(me, 'news') if rand(1, 10) == 1 else None; eval_attr(me, 'drift')",
]


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

    async def build(self, lines):
        if self.square is None:
            for line in PROLOGUE:
                await self.sim.do(self.vala, line)
            self.square = self.find("Market Square")
            assert self.square is not None
            assert self.vala.location is self.square
            # The mortals wander in behind the wizard.
            self.bob.location = self.square
            self.cass.location = self.square
        for line in lines:
            await self.sim.do(self.vala, line)

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
        await w.build(BUILD_MINT)
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
        await w.build(BUILD_MINT)
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
        await w.build(BUILD_MINT)
        await w.sim.do(w.vala, "cashout 9999")
        assert "Your wallet cannot cover that." in w.text(w.vala)
        assert cash_stacks(w.vala) == []

    async def test_physical_cash_changes_hands_like_any_object(self, world):
        w = world
        await w.build(BUILD_MINT)
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
        await w.build(BUILD_MINT)
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
        await w.build(BUILD_SHOP)
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
        await w.build(BUILD_SHOP)
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
        await w.build(BUILD_SHOP)
        await w.sim.do(w.vala, "@eval adjust_credits(me, 100)")

        await w.sim.do(w.vala, "pay 10 to Trader Vex")
        out = w.text(w.vala)
        assert "Much obliged, Vala." in out           # ON_PAYMENT fired

        await w.sim.do(w.vala, "list")
        assert "a stimpack — 25 credits" in w.text(w.vala)  # 20*1.3*0.95

    async def test_sell_pays_buyback_price(self, world):
        w = world
        await w.build(BUILD_SHOP)
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
        await w.build(BUILD_BANK)
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
        await w.build(BUILD_BANK)
        await w.sim.do(w.vala, "@eval adjust_credits(me, 100)")
        await w.sim.do(w.vala, "deposit 100")
        await w.sim.do(w.vala, "withdraw 500")
        assert "Insufficient funds on account." in w.text(w.vala)
        assert get_credits(w.vala) == 0

    async def test_transfer_reaches_a_player_in_another_room(self, world):
        w = world
        await w.build(BUILD_BANK)
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
        await w.build(BUILD_BANK)
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
        await w.build(BUILD_AUCTION)
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
        await w.build(BUILD_MARKET)
        await w.sim.do(w.vala, "market")
        out = w.text(w.vala)
        assert "Commodity        buy  sell  supply" in out
        assert "Water Ice        12  10  200" in out
        assert "Helium-3         60  54  100" in out

    async def test_buying_mints_cargo_and_dents_supply(self, world):
        w = world
        await w.build(BUILD_MARKET)
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
        await w.build(BUILD_MARKET)
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
        await w.build(BUILD_MARKET)
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
        await w.build(BUILD_MARKET)
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
