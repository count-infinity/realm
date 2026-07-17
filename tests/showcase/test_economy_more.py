"""
Showcase "Economy & Commerce" remainder (items 88, 90, 91, 93, 94, 95,
96, 97) — every tutorial transcript driven end-to-end through the
dispatcher, exactly as the docs have the builder type it.

Docs: docs/showcase/088_player_shops.md, 090_pawn_shop.md,
091_lottery.md, 093_housing_rent.md, 094_job_board.md,
095_durability_repair.md, 096_secure_trade.md, 097_barter_npc.md.

Each play reads its tutorial's "Build it" command lines straight out of
the markdown and types them at a live builder, so a doc edit that breaks
the build breaks this suite. If this file is green, the typed lines work.
"""

from __future__ import annotations

from pathlib import Path
import re
import time

import pytest

import realm.behaviors  # noqa: F401 — registers script_ticker etc.
from realm.core.economy import get_credits
from realm.core.events import reap_expired
from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"


def build_lines(doc_name: str) -> list[str]:
    """Every command line in the tutorial's "Build it" fenced blocks."""
    body = (DOCS / doc_name).read_text()
    match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
    assert match, f"{doc_name}: no Build it section"
    lines: list[str] = []
    for block in re.findall(r"```text\n(.*?)```", match.group(1), re.S):
        lines.extend(line for line in block.splitlines() if line.strip())
    assert lines, f"{doc_name}: empty Build it"
    return lines


# --- Harness ------------------------------------------------------------------------


class World:
    """A wizard (Vala) and two mortals (Bob, Cass). Each tutorial digs its
    own room live; the mortals wander in behind the wizard."""

    def __init__(self):
        self.sim = Simulator()
        self.landing = self.sim.room("The Landing")
        self.vala = self.sim.player("Vala", location=self.landing)
        self.vala.add_tag("admin")
        self.bob = self.sim.player("Bob", location=self.landing)
        self.cass = self.sim.player("Cass", location=self.landing)

    async def build(self, doc_name):
        """Type one tutorial's build transcript — read from the doc — as
        the wizard."""
        for line in build_lines(doc_name):
            await self.sim.do(self.vala, line)
        room = self.vala.location
        self.bob.location = room
        self.cass.location = room
        # Drain build chatter so tests assert on fresh output only.
        for p in (self.vala, self.bob, self.cass):
            self.sim.seen(p)
        return room

    def text(self, player) -> str:
        return "\n".join(self.sim.seen(player))

    def find(self, name):
        hits = self.sim.store.find_cached(name=name)
        return hits[0] if hits else None

    async def fund(self, player, amount):
        await self.sim.do(self.vala,
                          f"@eval adjust_credits(get('{player.name}'), {amount})")

    async def hand(self, item_name, player):
        """Vala @creates during builds leave items in her pack; hand one over."""
        await self.sim.do(self.vala, f"give {item_name} to {player.name}")

    def close(self):
        self.sim.close()


@pytest.fixture
async def world():
    w = World()
    try:
        yield w
    finally:
        w.close()


# --- 088 tests ------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPlayerStall:

    async def _open(self, w):
        await w.build("088_player_shops.md")
        stall = w.find("stall three")
        await w.sim.do(w.vala, "@create a stimpack")
        await w.sim.do(w.vala, "@set a stimpack/value = 20")
        await w.hand("a stimpack", w.bob)
        await w.fund(w.bob, 100)
        await w.fund(w.cass, 100)
        for p in (w.vala, w.bob, w.cass):
            w.sim.seen(p)
        return stall

    async def test_rent_stock_and_reprice(self, world):
        w = world
        stall = await self._open(w)

        await w.sim.do(w.bob, "rent stall")
        assert "Stall three is yours." in w.text(w.bob)
        assert get_credits(w.bob) == 80
        assert get_credits(stall) == 20                 # first period up front
        assert stall.db.get("renter") == w.bob.id

        await w.sim.do(w.bob, "stall stock a stimpack")
        assert "goes on the shelf at 20 credits." in w.text(w.bob)
        stim = w.find("a stimpack")
        assert stim.location is stall                   # escrowed
        assert stim.db.get("stall_price") == 20

        await w.sim.do(w.bob, "stall price a stimpack = 35")
        assert stim.db.get("stall_price") == 35
        assert "chalks a new price: a stimpack at 35 credits." in w.text(w.cass)

        await w.sim.do(w.cass, "stall")
        out = w.text(w.cass)
        assert "stall three, run by Bob:" in out
        assert "a stimpack - 35 credits" in out

    async def test_only_the_renter_configures(self, world):
        w = world
        stall = await self._open(w)
        await w.sim.do(w.bob, "rent stall")
        await w.sim.do(w.bob, "stall stock a stimpack")

        await w.sim.do(w.cass, "stall price a stimpack = 1")
        assert "Only the renter sets prices here." in w.text(w.cass)
        assert w.find("a stimpack").db.get("stall_price") == 20

        await w.sim.do(w.cass, "stall collect")
        assert "this is not your stall" in w.text(w.cass)

        await w.sim.do(w.cass, "rent stall")            # already let
        assert "already let" in w.text(w.cass)
        assert stall.db.get("renter") == w.bob.id

    async def test_buy_pays_the_ledger_and_collect_pays_the_renter(self, world):
        w = world
        stall = await self._open(w)
        await w.sim.do(w.bob, "rent stall")
        await w.sim.do(w.bob, "stall stock a stimpack")
        await w.sim.do(w.bob, "stall price a stimpack = 35")

        await w.sim.do(w.cass, "stall buy a stimpack")
        assert get_credits(w.cass) == 65
        stim = w.find("a stimpack")
        assert stim.location is w.cass
        assert stim.db.get("stall_price") is None
        assert stall.db.get("earnings") == 35
        assert get_credits(stall) == 20 + 35            # rent + earnings
        assert "Your stall sells a stimpack for 35 credits." in w.text(w.bob)

        await w.sim.do(w.bob, "stall collect")
        assert "You pocket 35 credits in takings." in w.text(w.bob)
        assert get_credits(w.bob) == 80 + 35
        assert stall.db.get("earnings") == 0
        assert get_credits(stall) == 20                 # the market's rent

    async def test_rent_tick_docks_earnings(self, world):
        w = world
        stall = await self._open(w)
        await w.sim.do(w.bob, "rent stall")
        await w.sim.do(w.bob, "stall stock a stimpack")
        await w.sim.do(w.cass, "stall buy a stimpack")  # earnings 20
        assert stall.db.get("earnings") == 20

        await w.sim.do(w.vala,
                       "@eval set_attr(get('stall three'), 'paid_until', now() - 1)")
        before = stall.db.get("paid_until")
        await w.sim.do(w.vala, "@tr stall three/on_tick")
        assert stall.db.get("earnings") == 0            # 20 - 20 rent
        assert stall.db.get("paid_until") == before + 300
        assert stall.db.get("renter") == w.bob.id       # still trading
        assert "The market takes 20 credits rent" in w.text(w.bob)

    async def test_broke_stall_is_repossessed_to_an_absent_renter(self, world):
        w = world
        stall = await self._open(w)
        await w.sim.do(w.bob, "rent stall")
        await w.sim.do(w.bob, "stall stock a stimpack")
        w.bob.location = w.landing                      # renter wanders off
        await w.sim.do(w.vala,
                       "@eval set_attr(get('stall three'), 'paid_until', now() - 1)")

        await w.sim.do(w.vala, "@tr stall three/on_tick")
        stim = w.find("a stimpack")
        assert stim.location is w.bob                   # goods chased him home
        assert stim.db.get("stall_price") is None
        assert stall.db.get("renter") is None
        assert "repossessed for unpaid rent" in w.text(w.bob)
        assert "TO LET" in w.text(w.cass)

        await w.sim.do(w.cass, "rent stall")            # pitch is free again
        assert stall.db.get("renter") == w.cass.id


# --- 090 tests ------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPawnShop:

    async def _open(self, w):
        await w.build("090_pawn_shop.md")
        shop = w.find("the Pawn Counter")
        await w.sim.do(w.vala, "@create a chrono watch")
        await w.sim.do(w.vala, "@set a chrono watch/value = 40")
        await w.hand("a chrono watch", w.bob)
        for p in (w.vala, w.bob, w.cass):
            w.sim.seen(p)
        return shop

    async def test_pawn_advances_a_percentage_and_escrows(self, world):
        w = world
        shop = await self._open(w)

        await w.sim.do(w.bob, "pawn a chrono watch")
        out = w.text(w.bob)
        assert "Yaro counts out 24 credits" in out       # 40 * 60%
        assert "Redeem it for 26" in out                 # loan 24 + max(1, 24//10)=2 vig
        assert get_credits(w.bob) == 24
        watch = w.find("a chrono watch")
        assert watch.location is shop                    # escrowed
        row = shop.db.get("pledge_" + watch.id)
        assert row["owner"] == w.bob.id and row["loan"] == 24
        tag = w.find("a pawn tag (a chrono watch)")
        assert tag is not None and tag.location is shop
        assert tag.db.get("item") == watch.id
        assert tag.db.get("expires_at") is not None      # the forfeit timer

    async def test_redeem_inside_the_window_costs_the_vig(self, world):
        w = world
        shop = await self._open(w)
        await w.fund(w.bob, 10)
        await w.sim.do(w.bob, "pawn a chrono watch")     # bob: 10 + 24 = 34

        await w.sim.do(w.bob, "redeem a chrono watch")
        assert "You redeem your a chrono watch for 26 credits." in w.text(w.bob)
        watch = w.find("a chrono watch")
        assert watch.location is w.bob
        assert get_credits(w.bob) == 34 - 26
        assert shop.db.get("pledge_" + watch.id) is None
        assert w.find("a pawn tag (a chrono watch)") is None   # tag retired
        assert get_credits(shop) == 1000 - 24 + 26       # the vig stayed

    async def test_unvalued_goods_pawn_at_the_fallback(self, world):
        w = world
        await self._open(w)
        await w.sim.do(w.vala, "@create a mystery box")
        await w.hand("a mystery box", w.cass)

        await w.sim.do(w.cass, "pawn a mystery box")
        assert "Yaro counts out 3 credits" in w.text(w.cass)   # 60% of 5
        assert get_credits(w.cass) == 3

    async def test_lapsed_window_forfeits_to_the_rack(self, world):
        w = world
        shop = await self._open(w)
        await w.sim.do(w.bob, "pawn a chrono watch")
        watch = w.find("a chrono watch")

        # The reaper fires the tag's ON_EXPIRE, then retires the tag.
        reaped = await reap_expired(w.sim.store, now=time.time() + 301)
        assert reaped >= 1
        assert shop.db.get("pledge_" + watch.id) is None
        assert watch.has_tag("forfeit")
        assert watch.location is shop
        assert w.find("a pawn tag (a chrono watch)") is None
        assert "moves a chrono watch to the sale rack" in w.text(w.cass)

        await w.fund(w.bob, 100)
        await w.sim.do(w.bob, "redeem a chrono watch")
        assert "the window has closed" in w.text(w.bob)

        await w.sim.do(w.cass, "rack")
        assert "a chrono watch - 40 credits" in w.text(w.cass)
        await w.fund(w.cass, 40)
        await w.sim.do(w.cass, "rack buy a chrono watch")
        assert "Yours for 40 credits." in w.text(w.cass)
        assert watch.location is w.cass
        assert not watch.has_tag("forfeit")

    async def test_pawning_nothing_is_refused(self, world):
        w = world
        await self._open(w)
        await w.sim.do(w.cass, "pawn a golden idol")
        assert "You are not carrying that" in w.text(w.cass)


# --- 091 tests ------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLottery:

    async def test_buy_mints_a_recorded_ticket(self, world):
        w = world
        await w.build("091_lottery.md")
        term = w.find("the lottery terminal")
        await w.fund(w.bob, 50)

        await w.sim.do(w.bob, "lotto buy")
        assert get_credits(w.bob) == 40
        assert get_credits(term) == 10                  # pot escrowed here
        assert term.db.get("pot") == 10
        assert term.db.get("sold") == 1
        assert term.db.get("draw_at") is not None
        ticket = w.find("lottery ticket 1")
        assert ticket.location is w.bob                 # minted at self, teleported
        assert term.db.get("stub_1") == "#" + ticket.id
        assert ticket.db.get("serial") == 1
        assert "buys lottery ticket 1. The pot stands at 10 credits." \
            in w.text(w.cass)

        await w.sim.do(w.bob, "lotto")
        assert "Pot: 10 credits across 1 tickets." in w.text(w.bob)

    async def test_forged_ticket_never_wins_the_ledger_does(self, world):
        w = world
        await w.build("091_lottery.md")
        term = w.find("the lottery terminal")
        await w.fund(w.bob, 10)
        await w.sim.do(w.bob, "lotto buy")              # genuine ticket 1 -> Bob

        # Cass forges a perfect lookalike, serial and all.
        await w.sim.do(w.vala, "@create lottery ticket 1")
        await w.sim.do(w.vala, "@set lottery ticket 1/serial = 1")
        await w.hand("lottery ticket 1", w.cass)
        fakes = [o for o in w.cass.contents if o.name == "lottery ticket 1"]
        assert len(fakes) == 1

        await w.sim.do(w.vala, "@tr the lottery terminal/draw")
        assert get_credits(w.bob) == 10                 # the pot came back to Bob
        assert get_credits(w.cass) == 0
        assert "ticket 1 wins! Bob collects 10 credits." in w.text(w.cass)
        # Round retired: ledger empty, genuine stub destroyed, forgery ignored.
        assert term.db.get("pot") == 0
        assert term.db.get("sold") == 0
        assert term.db.get("stub_1") is None
        assert [o for o in w.bob.contents if o.has_tag("lottery_ticket")] == []
        assert fakes[0].location is w.cass              # the fake still sits there

    async def test_tickets_are_bearer_instruments(self, world):
        w = world
        await w.build("091_lottery.md")
        await w.fund(w.bob, 10)
        await w.sim.do(w.bob, "lotto buy")
        await w.sim.do(w.bob, "give lottery ticket 1 to Cass")

        await w.sim.do(w.vala, "@tr the lottery terminal/draw")
        assert get_credits(w.cass) == 10                # the holder wins
        assert get_credits(w.bob) == 0

    async def test_unheld_winner_rolls_the_pot_over(self, world):
        w = world
        await w.build("091_lottery.md")
        term = w.find("the lottery terminal")
        await w.fund(w.bob, 20)
        await w.sim.do(w.bob, "lotto buy")
        await w.sim.do(w.bob, "drop lottery ticket 1")  # stub lies on the floor

        await w.sim.do(w.vala, "@tr the lottery terminal/draw")
        assert "The pot rolls over." in w.text(w.cass)
        assert term.db.get("pot") == 10                 # carried forward
        assert term.db.get("sold") == 0
        assert w.find("lottery ticket 1") is None       # retired anyway

        # Next round stacks onto the rolled-over pot.
        await w.sim.do(w.bob, "lotto buy")
        assert term.db.get("pot") == 20
        await w.sim.do(w.vala, "@tr the lottery terminal/draw")
        assert get_credits(w.bob) == 20                 # spent 20, won 20

    async def test_broke_buyer_is_refused(self, world):
        w = world
        await w.build("091_lottery.md")
        term = w.find("the lottery terminal")
        await w.sim.do(w.cass, "lotto buy")
        assert "insufficient credits" in w.text(w.cass)
        assert term.db.get("sold") is None

    async def test_tick_draws_only_past_the_deadline(self, world):
        w = world
        await w.build("091_lottery.md")
        term = w.find("the lottery terminal")
        await w.fund(w.bob, 10)
        await w.sim.do(w.bob, "lotto buy")

        await w.sim.do(w.vala, "@tr the lottery terminal/on_tick")
        assert term.db.get("sold") == 1                 # 120s round still open

        await w.sim.do(w.vala,
                       "@eval set_attr(get('the lottery terminal'), 'draw_at', now() - 1)")
        await w.sim.do(w.vala, "@tr the lottery terminal/on_tick")
        assert term.db.get("sold") == 0                 # due -> drawn
        assert get_credits(w.bob) == 10


# --- 093 tests ------------------------------------------------------------------------


@pytest.mark.asyncio
class TestHousingRent:

    async def _open(self, w):
        hall = await w.build("093_housing_rent.md")
        assert hall.name == "Rooming House Hall"        # Vala walked back out
        box = w.find("the rent box")
        flat = w.find("Harbor Flat")
        await w.fund(w.bob, 200)
        for p in (w.vala, w.bob, w.cass):
            w.sim.seen(p)
        return hall, flat, box

    async def test_lease_admits_the_tenant_and_bars_strangers(self, world):
        w = world
        hall, flat, box = await self._open(w)

        await w.sim.do(w.bob, "lease flat")
        assert "Harbor Flat is yours." in w.text(w.bob)
        assert box.db.get("tenant") == w.bob.id

        await w.sim.do(w.bob, "flat door")
        assert w.bob.location is flat
        await w.sim.do(w.cass, "flat door")
        assert "This flat is privately let." in w.text(w.cass)
        assert w.cass.location is hall
        await w.sim.do(w.bob, "hall door")
        assert w.bob.location is hall

    async def test_overdue_rent_freezes_the_door_until_paid(self, world):
        w = world
        hall, flat, box = await self._open(w)
        await w.sim.do(w.bob, "lease flat")
        await w.sim.do(w.vala,
                       "@eval set_attr(get('the rent box'), 'paid_until', now() - 10)")

        await w.sim.do(w.bob, "flat door")
        assert "The landlord froze the door code" in w.text(w.bob)
        assert w.bob.location is hall                   # locked out by arithmetic

        await w.sim.do(w.bob, "pay 50 to the rent box")
        assert "The box stamps a receipt: 1 period(s) paid." in w.text(w.bob)
        assert get_credits(w.bob) == 150
        assert box.db.get("paid_until") > time.time()

        await w.sim.do(w.bob, "flat door")
        assert w.bob.location is flat                   # the code works again

    async def test_underpay_and_stranger_money_bounce(self, world):
        w = world
        hall, flat, box = await self._open(w)
        await w.sim.do(w.bob, "lease flat")

        await w.sim.do(w.bob, "pay 30 to the rent box")
        assert "The box spits it back: the rent is 50 a period." in w.text(w.bob)
        assert get_credits(w.bob) == 200                # refunded in full

        await w.fund(w.cass, 60)
        await w.sim.do(w.cass, "pay 60 to the rent box")
        assert "you hold no lease here." in w.text(w.cass)
        assert get_credits(w.cass) == 60
        assert get_credits(box) == 0                    # refunds are exact

    async def test_tick_warns_once_inside_the_grace(self, world):
        w = world
        hall, flat, box = await self._open(w)
        await w.sim.do(w.bob, "lease flat")
        await w.sim.do(w.vala,
                       "@eval set_attr(get('the rent box'), 'paid_until', now() - 10)")

        await w.sim.do(w.vala, "@tr the rent box/on_tick")
        assert "A courier finds you: rent on Harbor Flat is overdue." \
            in w.text(w.bob)
        assert box.db.get("warned") == 1
        assert box.db.get("tenant") == w.bob.id         # grace: no eviction yet

        await w.sim.do(w.vala, "@tr the rent box/on_tick")
        assert "A courier finds you" not in w.text(w.bob)   # warned once

    async def test_past_grace_the_movers_clear_the_flat(self, world):
        w = world
        hall, flat, box = await self._open(w)
        await w.sim.do(w.bob, "lease flat")
        await w.sim.do(w.vala, "@create a duffel bag")
        await w.hand("a duffel bag", w.bob)
        await w.sim.do(w.bob, "flat door")
        await w.sim.do(w.bob, "drop a duffel bag")
        assert w.find("a duffel bag").location is flat

        await w.sim.do(w.vala,
                       "@eval set_attr(get('the rent box'), 'paid_until', now() - 999)")
        await w.sim.do(w.vala, "@tr the rent box/on_tick")
        assert w.bob.location is hall                   # tenant swept out too
        assert w.find("a duffel bag").location is hall
        assert box.db.get("tenant") is None
        assert "your lease is terminated" in w.text(w.bob)
        assert "Movers carry furniture out of Harbor Flat" in w.text(w.cass)
        # Exits stayed put, and the flat is open to the next tenant.
        assert any(o.has_tag("exit") for o in flat.contents)
        await w.sim.do(w.cass, "flat door")
        assert w.cass.location is flat


# --- 094 tests ------------------------------------------------------------------------


@pytest.mark.asyncio
class TestJobBoard:

    async def _open(self, w):
        await w.build("094_job_board.md")
        return w.find("the job board"), w.find("Foreman Dray")

    async def test_the_foreman_posts_up_to_two_jobs(self, world):
        w = world
        board, dray = await self._open(w)

        await w.sim.do(w.vala, "@tr Foreman Dray/on_tick")
        assert board.db.get("job_1") is not None
        assert "Work posted:" in w.text(w.cass)         # remit reaches the room

        await w.sim.do(w.vala, "@tr Foreman Dray/on_tick")
        assert board.db.get("job_2") is not None
        await w.sim.do(w.vala, "@tr Foreman Dray/on_tick")
        assert board.db.get("next_job") == 3            # capped at two open

        await w.sim.do(w.bob, "jobs")
        out = w.text(w.bob)
        assert "The job board:" in out and "OPEN" in out

    async def test_accept_claims_a_job_exclusively(self, world):
        w = world
        board, dray = await self._open(w)
        await w.sim.do(w.vala, "@tr Foreman Dray/on_tick")

        await w.sim.do(w.bob, "accept job 1")
        assert "You sign for job #1:" in w.text(w.bob)
        assert board.db.get("job_1")["taken"] == w.bob.id

        await w.sim.do(w.cass, "accept job 1")
        assert "already taken" in w.text(w.cass)
        await w.sim.do(w.cass, "accept job 9")
        assert "No such job" in w.text(w.cass)

    async def test_hand_in_verifies_and_pays_automatically(self, world):
        w = world
        board, dray = await self._open(w)
        await w.sim.do(w.vala, "@tr Foreman Dray/on_tick")
        job = board.db.get("job_1")
        await w.sim.do(w.bob, "accept job 1")
        await w.sim.do(w.vala, f"@create {job['want']}")
        await w.hand(job["want"], w.bob)
        dray_purse = get_credits(dray)

        await w.sim.do(w.bob, f"give {job['want']} to Foreman Dray")
        assert f"Good work, Bob. {job['reward']} credits, as posted." \
            in w.text(w.cass)
        assert get_credits(w.bob) == job["reward"]      # wages landed
        assert get_credits(dray) == dray_purse - job["reward"]
        assert board.db.get("job_1") is None            # posting closed
        assert w.find(job["want"]) is None              # goods consumed

    async def test_dray_ignores_handovers_he_is_not_the_recipient_of(self, world):
        """event:on_receive is witnessed room-wide, not delivered only to
        the recipient — so the hook's `target is me` guard is what keeps
        Dray from grading every handover in his own hall."""
        w = world
        board, dray = await self._open(w)
        await w.sim.do(w.vala, "@tr Foreman Dray/on_tick")
        job = board.db.get("job_1")
        await w.sim.do(w.bob, "accept job 1")
        await w.sim.do(w.vala, f"@create {job['want']}")

        # Vala hands Bob the goods, standing in Dray's hall.
        await w.sim.do(w.vala, f"give {job['want']} to Bob")
        assert w.find(job["want"]).location is w.bob    # not consumed
        assert get_credits(w.bob) == 0                  # not paid
        assert board.db.get("job_1") is not None        # posting still open

        # Handing them to Dray himself still works.
        await w.sim.do(w.bob, f"give {job['want']} to Foreman Dray")
        assert get_credits(w.bob) == job["reward"]
        assert board.db.get("job_1") is None

    async def test_wrong_or_unclaimed_deliveries_bounce(self, world):
        w = world
        board, dray = await self._open(w)
        await w.sim.do(w.vala, "@tr Foreman Dray/on_tick")
        job = board.db.get("job_1")
        await w.sim.do(w.bob, "accept job 1")

        await w.sim.do(w.vala, "@create a soggy boot")
        await w.hand("a soggy boot", w.bob)
        await w.sim.do(w.bob, "give a soggy boot to Foreman Dray")
        assert "That is not what any job of yours calls for." in w.text(w.bob)
        assert w.find("a soggy boot").location is w.bob     # pushed back

        # The right goods from someone who never signed also bounce.
        await w.sim.do(w.vala, f"@create {job['want']}")
        await w.hand(job["want"], w.cass)
        await w.sim.do(w.cass, f"give {job['want']} to Foreman Dray")
        assert w.find(job["want"]).location is w.cass
        assert get_credits(w.cass) == 0


# --- 095 tests ------------------------------------------------------------------------


@pytest.fixture
def combat():
    """A deterministic combat manager wired into the Simulator's world:
    3d6 always rolls 10 (skill 12 hits, dodge 0 fails), damage is flat 1."""
    from realm.combat.manager import CombatManager, set_combat_manager
    from realm.combat.rulesets.gurps import GURPSRuleset
    from realm.combat.system import CombatSystem

    class FixedRuleset(GURPSRuleset):
        def roll_3d6(self):
            return 10, [3, 3, 4]

        def roll_damage(self, attacker, defender, attack_result, weapon=None):
            from realm.combat.ruleset import DamageResult, DamageType
            return DamageResult(total=1,
                                damage_by_type={DamageType.PHYSICAL: 1})

    mgr = CombatManager(CombatSystem(ruleset=FixedRuleset()),
                        beat_min=4.0, beat_max=120.0, beat_default=60.0)
    set_combat_manager(mgr)
    try:
        yield mgr
    finally:
        mgr.stop_all()
        set_combat_manager(None)


@pytest.mark.asyncio
class TestDurability:

    async def _open(self, w):
        yard = await w.build("095_durability_repair.md")
        blade = w.find("a mono blade")
        welder = w.find("an arc welder")
        await w.hand("a mono blade", w.bob)
        await w.hand("an arc welder", w.bob)
        await w.hand("a flak vest", w.bob)
        for stat, val in (("hp", 30), ("max_hp", 30), ("skill_melee", 12),
                          ("dodge", 6), ("strength", 10), ("dexterity", 12)):
            w.bob.db.set(stat, val)
        # The dummy stands there and takes it: no skill, so it never
        # lands a blow of its own.
        dummy = w.sim.obj("training dummy", location=yard, tags=["npc"],
                          hp=50, max_hp=50, dodge=0, strength=10, dexterity=10)
        return blade, welder, dummy

    async def test_every_swing_wears_the_wielded_weapon(self, world, combat):
        w = world
        blade, welder, dummy = await self._open(w)
        await w.sim.do(w.bob, "wield a mono blade")
        assert blade.has_tag("wielded")

        await w.sim.do(w.bob, "attack training dummy")
        enc = combat.encounter_of(w.bob)
        assert enc is not None
        await enc.resolve_round()
        assert blade.db.get("condition") == 95          # one swing, minus 5
        await enc.resolve_round()
        assert blade.db.get("condition") == 90

    async def test_thresholds_announce_and_zero_blocks_rewield(self, world, combat):
        w = world
        blade, welder, dummy = await self._open(w)
        await w.sim.do(w.bob, "wield a mono blade")
        await w.sim.do(w.bob, "attack training dummy")
        enc = combat.encounter_of(w.bob)

        blade.db.set("condition", 30)
        await enc.resolve_round()
        assert blade.db.get("condition") == 25
        assert "a mono blade is looking battered." in w.text(w.cass)

        blade.db.set("condition", 5)
        await enc.resolve_round()
        assert blade.db.get("condition") == 0
        assert "a mono blade gives out with a crack!" in w.text(w.cass)

        await w.sim.do(w.bob, "unwield")
        assert not blade.has_tag("wielded")
        await w.sim.do(w.bob, "wield a mono blade")
        assert "ruin of snapped segments" in w.text(w.bob)   # ward refuses
        assert not blade.has_tag("wielded")

    async def test_armour_wears_by_the_damage_it_stops(self, world, combat):
        w = world
        blade, welder, dummy = await self._open(w)
        vest = w.find("a flak vest")
        await w.sim.do(w.bob, "wear a flak vest")
        assert vest.has_tag("worn")

        # A partner who actually swings back: ON_DAMAGE only fires on a
        # blow that lands, and it names Bob as the target.
        w.sim.obj("a sparring partner", location=w.bob.location, tags=["npc"],
                  hp=50, max_hp=50, skill_melee=12, dodge=0,
                  strength=10, dexterity=10)
        await w.sim.do(w.bob, "attack a sparring partner")
        enc = combat.encounter_of(w.bob)

        await enc.resolve_round()
        assert vest.db.get("condition") == 99      # one blow of 1 damage
        await enc.resolve_round()
        assert vest.db.get("condition") == 98

        # The thresholds announce, exactly as the weapon's do.
        vest.db.set("condition", 26)
        await enc.resolve_round()
        assert vest.db.get("condition") == 25
        assert "a flak vest is scarred and dented." in w.text(w.cass)

        vest.db.set("condition", 1)
        await enc.resolve_round()
        assert vest.db.get("condition") == 0
        assert "a flak vest comes apart at the seams!" in w.text(w.cass)

        # Ruined armour refuses to go back on — the item's own ward.
        await w.sim.do(w.bob, "remove a flak vest")
        assert not vest.has_tag("worn")
        await w.sim.do(w.bob, "wear a flak vest")
        assert "split webbing and loose plate" in w.text(w.bob)
        assert not vest.has_tag("worn")

        # ...until the bench trues it.
        await w.fund(w.bob, 100)
        await w.sim.do(w.bob, "repair a flak vest")
        assert vest.db.get("condition") == 100
        await w.sim.do(w.bob, "wear a flak vest")
        assert vest.has_tag("worn")

    async def test_a_dominated_fight_spares_the_armour(self, world, combat):
        """The asymmetry the tutorial promises: ON_ATTACK wears the
        weapon on every swing thrown, ON_DAMAGE wears armour only on
        blows that land. The dummy never lands one."""
        w = world
        blade, welder, dummy = await self._open(w)
        vest = w.find("a flak vest")
        await w.sim.do(w.bob, "wear a flak vest")
        await w.sim.do(w.bob, "wield a mono blade")
        await w.sim.do(w.bob, "attack training dummy")
        enc = combat.encounter_of(w.bob)

        await enc.resolve_round()
        await enc.resolve_round()
        assert blade.db.get("condition") == 90     # two swings, minus 5 each
        assert vest.db.get("condition") == 100     # never took a blow

    async def test_repair_restores_and_burns_the_fee(self, world, combat):
        w = world
        blade, welder, dummy = await self._open(w)
        bench = w.find("the repair bench")
        blade.db.set("condition", 0)
        await w.fund(w.bob, 100)

        await w.sim.do(w.bob, "repair a mono blade")
        assert "good as new for 50 credits." in w.text(w.bob)
        assert blade.db.get("condition") == 100
        assert get_credits(w.bob) == 50
        assert get_credits(bench) == 0                  # the fee was burned

        await w.sim.do(w.bob, "wield a mono blade")
        assert blade.has_tag("wielded")                 # good as new indeed

        await w.sim.do(w.bob, "repair a mono blade")    # nothing to fix now
        assert "Nothing to repair" in w.text(w.bob)

    async def test_tools_wear_themselves_on_use(self, world):
        w = world
        blade, welder, dummy = await self._open(w)

        await w.sim.do(w.bob, "use an arc welder")
        assert welder.db.get("condition") == 10
        assert "(condition 10)" in w.text(w.bob)
        await w.sim.do(w.bob, "use an arc welder")
        assert welder.db.get("condition") == 0

        await w.sim.do(w.bob, "use an arc welder")      # its own ward now blocks
        assert "The welder is burnt out." in w.text(w.bob)
        assert welder.db.get("condition") == 0

        await w.fund(w.bob, 100)
        await w.sim.do(w.bob, "repair an arc welder")
        assert welder.db.get("condition") == 100
        assert get_credits(w.bob) == 50


# --- 096 tests ------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSecureTrade:

    async def _open(self, w):
        await w.build("096_secure_trade.md")
        broker = w.find("Broker Unit 7")
        await w.sim.do(w.vala, "@create plasma torch")
        await w.hand("plasma torch", w.bob)
        await w.sim.do(w.vala, "@create crystal skull")
        await w.hand("crystal skull", w.cass)
        for p in (w.vala, w.bob, w.cass):
            w.sim.seen(p)
        return broker

    async def test_stage_confirm_and_atomic_swap(self, world):
        w = world
        broker = await self._open(w)

        await w.sim.do(w.bob, "trade with Cass")
        assert "opens a brokered trade with Cass" in w.text(w.cass)
        assert broker.db.get("party_a") == w.bob.id
        assert broker.db.get("party_b") == w.cass.id

        await w.sim.do(w.bob, "give plasma torch to Broker Unit 7")
        torch = w.find("plasma torch")
        assert torch.location is broker                 # escrowed
        assert torch.db.get("staged_by") == w.bob.id
        assert "Bob stages plasma torch. All confirmations reset." \
            in w.text(w.cass)

        await w.sim.do(w.cass, "give crystal skull to Broker Unit 7")
        skull = w.find("crystal skull")
        assert skull.location is broker

        await w.sim.do(w.bob, "trade confirm")
        assert "You confirm. Waiting on the other side." in w.text(w.bob)
        assert broker.db.get("confirm_a") == 1

        await w.sim.do(w.cass, "trade confirm")         # the one-script commit
        assert "The trade executes." in w.text(w.cass)
        assert "trade complete between Bob and Cass" in w.text(w.bob)
        assert torch.location is w.cass
        assert skull.location is w.bob
        assert torch.db.get("staged_by") is None
        assert broker.db.get("party_a") is None         # session cleared

    async def test_any_change_resets_confirmations(self, world):
        w = world
        broker = await self._open(w)
        await w.sim.do(w.vala, "@create old boot")
        await w.hand("old boot", w.cass)
        await w.sim.do(w.bob, "trade with Cass")
        await w.sim.do(w.bob, "give plasma torch to Broker Unit 7")
        await w.sim.do(w.cass, "give crystal skull to Broker Unit 7")
        await w.sim.do(w.bob, "trade confirm")
        assert broker.db.get("confirm_a") == 1

        await w.sim.do(w.cass, "give old boot to Broker Unit 7")
        assert broker.db.get("confirm_a") == 0          # Bob's confirm wiped
        assert "All confirmations reset." in w.text(w.bob)

        await w.sim.do(w.bob, "trade confirm")
        await w.sim.do(w.cass, "trade confirm")
        # Bob gets both of Cass's staged items; Cass gets the torch.
        assert w.find("old boot").location is w.bob
        assert w.find("crystal skull").location is w.bob
        assert w.find("plasma torch").location is w.cass

    async def test_bystanders_and_strays_are_refused(self, world):
        w = world
        broker = await self._open(w)
        # No trade open: staging bounces with instructions.
        await w.sim.do(w.bob, "give plasma torch to Broker Unit 7")
        assert "open a trade first" in w.text(w.bob)
        assert w.find("plasma torch").location is w.bob

        await w.sim.do(w.bob, "trade with Cass")
        await w.sim.do(w.vala, "@create sturdy boots")
        await w.sim.do(w.vala, "give sturdy boots to Broker Unit 7")
        assert w.find("sturdy boots").location is w.vala    # not a party
        await w.sim.do(w.vala, "trade confirm")
        assert "You are not part of this trade." in w.text(w.vala)

    async def test_a_handover_between_bystanders_is_not_a_staging(self, world):
        """on_receive is witnessed room-wide: without the `target is me`
        guard the broker would stage goods that were never handed to it,
        and reset live confirmations doing it."""
        w = world
        broker = await self._open(w)
        await w.sim.do(w.bob, "trade with Cass")
        await w.sim.do(w.bob, "give plasma torch to Broker Unit 7")
        await w.sim.do(w.cass, "give crystal skull to Broker Unit 7")
        await w.sim.do(w.bob, "trade confirm")
        assert broker.db.get("confirm_a") == 1

        # Vala hands Cass a bag, in the annex — nothing to do with the trade.
        await w.sim.do(w.vala, "@create a paper bag")
        await w.sim.do(w.vala, "give a paper bag to Cass")
        bag = w.find("a paper bag")
        assert bag.location is w.cass                   # never escrowed
        assert bag.db.get("staged_by") is None
        assert broker.db.get("confirm_a") == 1          # confirmation survived

    async def test_walking_out_voids_the_deal(self, world):
        w = world
        broker = await self._open(w)
        await w.sim.do(w.bob, "trade with Cass")
        await w.sim.do(w.bob, "give plasma torch to Broker Unit 7")
        await w.sim.do(w.cass, "give crystal skull to Broker Unit 7")

        await w.sim.do(w.bob, "out")                    # ON_LEAVE tripwire
        assert w.bob.location is w.find("The Concourse")
        assert "The broker voids the trade as Bob walks away" in w.text(w.cass)
        assert w.find("plasma torch").location is w.bob      # chased him out
        assert w.find("crystal skull").location is w.cass
        assert broker.db.get("party_a") is None

    async def test_cancel_returns_everything(self, world):
        w = world
        broker = await self._open(w)
        await w.sim.do(w.bob, "trade with Cass")
        await w.sim.do(w.bob, "give plasma torch to Broker Unit 7")

        await w.sim.do(w.cass, "trade cancel")
        assert "backs out; the broker returns all staged goods." in w.text(w.bob)
        assert w.find("plasma torch").location is w.bob
        assert broker.db.get("party_a") is None


# --- 097 tests ------------------------------------------------------------------------


@pytest.mark.asyncio
class TestBarterNPC:

    async def _open(self, w):
        await w.build("097_barter_npc.md")
        rook = w.find("Rook the Tinker")
        await w.hand("a bent hull plate", w.bob)
        for p in (w.vala, w.bob, w.cass):
            w.sim.seen(p)
        return rook

    async def test_wants_lists_the_menu(self, world):
        w = world
        await self._open(w)
        await w.sim.do(w.bob, "wants")
        out = w.text(w.bob)
        assert "Rook trades goods for goods. No coin." in out
        assert "anything scrap_metal -> a patched thermal cloak" in out
        assert "anything power_cell -> a tinkered lantern" in out

    async def test_matching_gift_swaps_item_for_item(self, world):
        w = world
        rook = await self._open(w)
        assert get_credits(w.bob) == 0 and get_credits(rook) == 0

        await w.sim.do(w.bob, "give a bent hull plate to Rook the Tinker")
        assert "A fair swap: a patched thermal cloak for your a bent hull plate." \
            in w.text(w.bob)
        cloak = w.find("a patched thermal cloak")
        assert cloak.location is w.bob                  # counter-gift delivered
        plate = w.find("a bent hull plate")
        assert plate.location is rook and plate.db.get("kept") == 1

        # Wallets untouched on both sides — the whole point.
        assert get_credits(w.bob) == 0
        assert get_credits(rook) == 0

    async def test_rook_ignores_handovers_between_other_people(self, world):
        """The yard's other traffic is not Rook's business: on_receive is
        witnessed room-wide, so only `target is me` stops him paying out a
        cloak for scrap that was never handed to him."""
        w = world
        rook = await self._open(w)
        await w.sim.do(w.vala, "@create a spare hull plate")
        await w.sim.do(w.vala, "@tag a spare hull plate = scrap_metal")

        # Vala hands Cass a scrap_metal item, standing in Rook's yard.
        await w.sim.do(w.vala, "give a spare hull plate to Cass")
        assert w.find("a spare hull plate").location is w.cass
        assert w.find("a spare hull plate").db.get("kept") is None
        assert w.find("a patched thermal cloak") is None    # no counter-gift
        assert "A fair swap" not in w.text(w.cass)

    async def test_off_list_goods_bounce_back(self, world):
        w = world
        rook = await self._open(w)
        await w.sim.do(w.vala, "@create a ration bar")
        await w.hand("a ration bar", w.cass)

        await w.sim.do(w.cass, "give a ration bar to Rook the Tinker")
        assert "No use to me. Ask me what I want." in w.text(w.cass)
        assert w.find("a ration bar").location is w.cass
        assert w.find("a patched thermal cloak") is None

    async def test_the_tag_is_the_currency_not_the_name(self, world):
        w = world
        rook = await self._open(w)
        await w.sim.do(w.vala, "@create a snapped strut")
        await w.sim.do(w.vala, "@tag a snapped strut = scrap_metal")
        await w.hand("a snapped strut", w.cass)

        await w.sim.do(w.cass, "give a snapped strut to Rook the Tinker")
        assert "A fair swap: a patched thermal cloak for your a snapped strut." \
            in w.text(w.cass)
        cloaks = w.sim.store.find_cached(name="a patched thermal cloak")
        assert len(cloaks) == 1 and cloaks[0].location is w.cass
