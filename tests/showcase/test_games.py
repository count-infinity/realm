"""
Showcase "Games & Recreation" — checklist items 98, 99, 100, 101, 102,
103, 104, 105, 106, 107, 108.

Verifies the standalone tutorials in docs/showcase/ (098_dice_roller.md
through 108_casino_floor.md) by driving a real in-process world —
realm.testing.Simulator wires the same store/propagation/scripting/
dispatcher stack a live GameServer does — with the tutorials' EXACT
command lines (raw input in, session output out).

The BUILD_* lists below are copied verbatim from the docs' "Build it"
sections; the sync test at the bottom keeps them from drifting.
Determinism: rand() is pinned via realm.scripting.functions.random,
the dice kernel (roll/margin_under/skill_check/contest) via
realm.core.dice.random; wait() chains run on the Simulator's virtual
clock (engine.tick_waits()); prompt() wizards answer through the
session's captured input handler — the same techniques the gadget and
economy suites use.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import realm.behaviors  # noqa: F401 — registers script_ticker
from realm.core.economy import get_credits
from realm.testing import Simulator

BUILD_FAILURE_MARKERS = (
    "Unknown command",
    "Permission denied",
    "Usage:",
    "not found",
    "Script error",
    "Eval error",
    "error",
)


@pytest.fixture
def sim():
    s = Simulator()
    # prompt() finds player sessions through the engine's session manager
    # on a live server; give the Simulator the same wiring.
    s.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(s._sessions.values()))
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def pinned_rand(monkeypatch):
    """Pin rand() (scripting layer): random.randint returns
    holder['value'] clamped into range."""
    holder = {"value": 1}

    def fake_randint(low, high):
        return max(low, min(holder["value"], high))

    monkeypatch.setattr(
        "realm.scripting.functions.random.randint", fake_randint)
    return holder


@pytest.fixture
def pinned_dice(monkeypatch):
    """Pin the dice kernel (roll()/margin_under/skill_check/contest):
    every die face is holder['value'] clamped into range."""
    holder = {"value": 4}

    def fake_randint(low, high):
        return max(low, min(holder["value"], high))

    monkeypatch.setattr("realm.core.dice.random.randint", fake_randint)
    return holder


def parlor_and_staff(sim):
    """The standing start: a room, an admin builder (Vala — the dart
    board and casino cage need owner authority over players, per their
    docs), and two mortals."""
    room = sim.room("The Rec Deck")
    vala = sim.player("Vala", location=room)
    vala.add_tag("admin")
    kess = sim.player("Kess", location=room)
    bob = sim.player("Bob", location=room)
    return room, vala, kess, bob


async def build(sim, player, lines):
    """Run a Build-it transcript; fail loudly if any line misfires."""
    for line in lines:
        await sim.do(player, line)
        out = "\n".join(sim.seen(player))
        for marker in BUILD_FAILURE_MARKERS:
            assert marker not in out, f"build line {line!r} failed: {out!r}"


async def do(sim, player, line):
    """Run one command and return everything the player saw."""
    await sim.do(player, line)
    return sim.seen(player)


async def answer(sim, player, line):
    """Answer a pending prompt() wizard with the player's next line."""
    session = sim.session(player)
    handler = session.input_handler
    assert handler is not None, "no prompt() is pending for this player"
    await handler(session, line)
    return sim.seen(player)


def find_one(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no object named {name!r} in the world"
    return matches[0]


def drain_all(sim, *players):
    for p in players:
        sim.seen(p)


async def grant(sim, vala, player, amount):
    await sim.do(vala, f"@eval adjust_credits(get('{player.name}'), {amount})")
    sim.seen(vala)


# =========================================================================
# 098. Dice roller — docs/showcase/098_dice_roller.md
# =========================================================================

DICE_BUILD = [
    "@create a dice cup",
    "drop a dice cup",
    "@desc a dice cup = A leather cup, dice rattling inside. [[result = "
    "'Last throw: ' + str(get_attr(me, 'last', '--')) + '.']]",
    "@set a dice cup/cmd_roll = $roll *: expr = trim(arg0); total = "
    "roll(expr); set_attr(me, 'last', expr + ' = ' + str(total)); "
    "remit(here, name(enactor) + ' rattles the cup and throws ' + expr "
    "+ ': ' + str(total) + '.')",
    "@set a dice cup/cmd_try = $try *: s = trim(arg0).lower(); lvl = "
    "get_attr(enactor, 'skill_' + s, get_attr(enactor, 'dexterity', 10) "
    "- 5); r = margin_under(roll('3d6'), lvl, skill=s); word = "
    "'critically nails' if r.margin >= 6 else ('makes' if r.success "
    "else ('barely misses' if r.margin >= -2 else 'blows')); "
    "remit(here, name(enactor) + ' rolls ' + str(r.roll) + ' vs ' + s + "
    "' ' + str(r.effective) + ' -- ' + word + ' it (margin ' + "
    "str(r.margin) + ').')",
    "@set a dice cup/cmd_check = $check *: s = trim(arg0).lower(); ok = "
    "skill_check(enactor, s); pemit(enactor, 'The table holds its "
    "breath... ' + ('You pull it off.' if ok else 'No dice.')); "
    "oemit(enactor, name(enactor) + ' tries a ' + s + ' check and ' + "
    "('makes it.' if ok else 'fumbles.'))",
]


class TestDiceRoller:

    async def test_notation_rolls_are_public(self, sim, pinned_dice):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, DICE_BUILD)
        drain_all(sim, vala, kess, bob)

        pinned_dice["value"] = 4          # every die shows 4
        await do(sim, kess, "roll 3d6")
        assert ("Kess rattles the cup and throws 3d6: 12."
                in sim.seen(bob))         # remit: the room hears it

        await do(sim, kess, "roll 2d20kh1")
        assert ("Kess rattles the cup and throws 2d20kh1: 4."
                in sim.seen(bob))

        await do(sim, kess, "roll 3d6+2")
        assert ("Kess rattles the cup and throws 3d6+2: 14."
                in sim.seen(bob))

        # The description remembers the last throw.
        out = await do(sim, kess, "look a dice cup")
        assert any("Last throw: 3d6+2 = 14." in line for line in out)

    async def test_margin_narration_vs_skill(self, sim, pinned_dice):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, DICE_BUILD)
        drain_all(sim, vala, kess, bob)

        pinned_dice["value"] = 4          # 3d6 = 12
        # Sheet-writes are builder-gated; the admin sets the demo skill.
        await do(sim, vala, "@set Kess/skill_stealth = 13")
        sim.seen(kess)
        await do(sim, kess, "try stealth")
        assert ("Kess rolls 12 vs stealth 13 -- makes it (margin 1)."
                in sim.seen(bob))

        # Untrained: DX 10 house default -> guns 5, margin -7 -> blown.
        await do(sim, kess, "try guns")
        assert ("Kess rolls 12 vs guns 5 -- blows it (margin -7)."
                in sim.seen(bob))

    async def test_engine_check_and_rolls_echo(self, sim, pinned_dice):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, DICE_BUILD)
        drain_all(sim, vala, kess, bob)

        pinned_dice["value"] = 4          # 3d6 = 12, no crit band
        await do(sim, vala, "@set me/skill_stealth = 13")
        await do(sim, vala, "@rolls on")
        sim.seen(vala)
        out = await do(sim, vala, "check stealth")
        joined = "\n".join(out)
        assert "[roll stealth: 12 vs 13 -> success (margin +1)]" in joined
        assert "The table holds its breath... You pull it off." in joined
        assert "Vala tries a stealth check and makes it." in sim.seen(bob)


# =========================================================================
# 099. Card deck — docs/showcase/099_card_deck.md
# =========================================================================

DECK_BUILD = [
    "@create a deck of cards",
    "drop a deck of cards",
    "@desc a deck of cards = Well-worn cards in a battered tin. "
    "[[result = str(len(get_attr(me, 'deck', []))) + "
    "' cards remain in the tin.']]",
    "@set a deck of cards/fresh = result = [r + s for s in ['s', 'h', "
    "'d', 'c'] for r in ['A', '2', '3', '4', '5', '6', '7', '8', '9', "
    "'10', 'J', 'Q', 'K']]",
    "@set a deck of cards/hands = {}",
    "@attr a deck of cards/hands = secret",
    "@set a deck of cards/cmd_shuffle = $shuffle: d = eval_attr(me, "
    "'fresh'); p = [d.pop(rand(0, len(d) - 1)) for i in range(len(d))]; "
    "set_attr(me, 'deck', p); set_attr(me, 'hands', {}); set_attr(me, "
    "'table', []); remit(here, name(enactor) + ' shuffles the deck with "
    "a riffle and a bridge.')",
    "@set a deck of cards/cmd_deal = $deal * to *: n = int(trim(arg0)); "
    "who = get(trim(arg1)); d = get_attr(me, 'deck', []); h = "
    "get_attr(me, 'hands', {}); ok = who is not None and loc(who) is "
    "here and 0 < n <= len(d); (h.update({who.id: h.get(who.id, []) + "
    "d[:n]}), set_attr(me, 'hands', h), set_attr(me, 'deck', d[n:]), "
    "remit(here, name(who) + ' is dealt ' + str(n) + ' cards, face "
    "down.'), pemit(who, 'Your cards: ' + ' '.join(h[who.id]))) if ok "
    "else pemit(enactor, 'The deck cannot do that -- shuffle first, "
    "name a player here, and mind the count.')",
    "@set a deck of cards/cmd_hand = $hand: h = get_attr(me, 'hands', "
    "{}).get(enactor.id, []); pemit(enactor, 'Your hand: ' + "
    "' '.join(h) if h else 'You hold no cards.'); oemit(enactor, "
    "name(enactor) + ' fans a hand of cards close to the chest.') if h "
    "else None",
    "@set a deck of cards/cmd_play = $play *: c = trim(arg0); h = "
    "get_attr(me, 'hands', {}); mine = h.get(enactor.id, []); pick = "
    "[x for x in mine if x.lower() == c.lower()]; (mine.remove(pick[0]), "
    "h.update({enactor.id: mine}), set_attr(me, 'hands', h), "
    "set_attr(me, 'table', get_attr(me, 'table', []) + [pick[0]]), "
    "remit(here, name(enactor) + ' plays ' + pick[0] + ' onto the "
    "table.')) if pick else pemit(enactor, 'That card is not in your "
    "hand.')",
    "@set a deck of cards/cmd_table = $table: t = get_attr(me, 'table', "
    "[]); pemit(enactor, 'On the table: ' + (' '.join(t) if t else "
    "'nothing yet.'))",
]


class TestCardDeck:

    async def test_shuffle_is_a_full_permutation(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, DECK_BUILD)
        drain_all(sim, vala, kess, bob)

        await do(sim, kess, "shuffle")
        assert ("Kess shuffles the deck with a riffle and a bridge."
                in sim.seen(bob))
        deck = find_one(sim, "a deck of cards")
        cards = deck.db.get("deck")
        assert len(cards) == 52 and len(set(cards)) == 52
        assert "As" in cards and "10h" in cards and "Kd" in cards

    async def test_deal_is_private_to_the_recipient(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, DECK_BUILD)
        await do(sim, vala, "shuffle")
        drain_all(sim, vala, kess, bob)

        await do(sim, vala, "deal 5 to Kess")
        # The room sees the deal; only Kess sees the faces.
        bob_saw = "\n".join(sim.seen(bob))
        assert "Kess is dealt 5 cards, face down." in bob_saw
        assert "Your cards:" not in bob_saw
        kess_saw = "\n".join(sim.seen(kess))
        assert "Your cards:" in kess_saw

        deck = find_one(sim, "a deck of cards")
        assert len(deck.db.get("deck")) == 47
        hand = deck.db.get("hands")[kess.id]
        assert len(hand) == 5

        # look shows the shrinking tin.
        out = await do(sim, kess, "look a deck of cards")
        assert any("47 cards remain in the tin." in line for line in out)

        # hand re-whispers it; the room only sees the fan.
        out = await do(sim, kess, "hand")
        assert any("Your hand: " + " ".join(hand) in line for line in out)
        assert ("Kess fans a hand of cards close to the chest."
                in sim.seen(bob))

    async def test_bad_deals_bounce(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, DECK_BUILD)
        drain_all(sim, vala, kess, bob)
        out = await do(sim, vala, "deal 5 to Kess")   # never shuffled
        assert any("The deck cannot do that" in line for line in out)

    async def test_play_moves_a_card_to_the_table(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, DECK_BUILD)
        await do(sim, vala, "shuffle")
        await do(sim, vala, "deal 5 to Kess")
        drain_all(sim, vala, kess, bob)

        deck = find_one(sim, "a deck of cards")
        card = deck.db.get("hands")[kess.id][0]
        await do(sim, kess, "play " + card.lower())   # case-insensitive
        assert f"Kess plays {card} onto the table." in sim.seen(bob)
        assert len(deck.db.get("hands")[kess.id]) == 4
        assert deck.db.get("table") == [card]
        out = await do(sim, kess, "table")
        assert any("On the table: " + card in line for line in out)

        out = await do(sim, kess, "play Zz")
        assert any("That card is not in your hand." in line for line in out)

    async def test_hands_are_engine_private(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, DECK_BUILD)
        await do(sim, vala, "shuffle")
        await do(sim, vala, "deal 5 to Kess")

        deck = find_one(sim, "a deck of cards")
        # A stranger reads None through the secret flag...
        result, err = await sim.eval(
            bob, "result = get_attr(get('a deck of cards'), 'hands')")
        assert err is None and result is None
        # ...the owner still reads the dict.
        result, err = await sim.eval(
            vala, "result = get_attr(get('a deck of cards'), 'hands')")
        assert err is None and kess.id in result


# =========================================================================
# 100. Poker table — docs/showcase/100_poker_table.md
# =========================================================================

POKER_BUILD = [
    "@create the poker table",
    "drop the poker table",
    "@desc the poker table = Green felt, chip rails, a shaded lamp. "
    "[[result = 'The pot holds ' + str(get_attr(me, 'pot', 0)) + "
    "' credits.']]",
    "@set the poker table/hands = {}",
    "@attr the poker table/hands = secret",
    "@set the poker table/cmd_sit = $sit: p = get_attr(me, 'players', "
    "[]); n = get_attr(me, 'names', {}); ok = get_attr(me, 'phase', "
    "'lobby') == 'lobby' and enactor.id not in p; [(set_attr(me, "
    "'players', p + [enactor.id]), n.update({enactor.id: "
    "name(enactor)}), set_attr(me, 'names', n), remit(here, "
    "name(enactor) + ' takes a seat at the poker table.')) for g in "
    "[ok] if g]; pemit(enactor, 'You are in. Someone type: deal cards.' "
    "if ok else 'No seat for you -- a hand is in play, or you are "
    "already seated.')",
    "@set the poker table/cmd_deal = $deal cards: p = get_attr(me, "
    "'players', []); ok = get_attr(me, 'phase', 'lobby') == 'lobby' and "
    "enactor.id in p and len(p) >= 2; d = [r + s for s in ['s', 'h', "
    "'d', 'c'] for r in ['A', '2', '3', '4', '5', '6', '7', '8', '9', "
    "'10', 'J', 'Q', 'K']]; sh = [d.pop(rand(0, len(d) - 1)) for i in "
    "range(len(d))]; [(set_attr(me, 'hands', {pid: sh[i * 5:i * 5 + 5] "
    "for i, pid in enumerate(p)}), set_attr(me, 'bets', {pid: 0 for pid "
    "in p}), set_attr(me, 'folded', []), set_attr(me, 'phase', "
    "'betting'), remit(here, 'Five cards apiece, face down. Betting is "
    "open: pay the table to bet, fold to quit, showdown when stakes "
    "match.'), [pemit(get('#' + pid), 'Your hand: ' + ' '.join(sh[i * "
    "5:i * 5 + 5])) for i, pid in enumerate(p)]) for g in [ok] if g]; "
    "pemit(enactor, 'Take a seat first, find an opponent, or finish the "
    "current hand.') if not ok else None",
    "@set the poker table/on_payment = paid = credits(me) - "
    "get_attr(me, 'ledger', 0); b = get_attr(me, 'bets', {}); live = "
    "get_attr(me, 'phase', 'lobby') == 'betting' and enactor.id in b "
    "and enactor.id not in get_attr(me, 'folded', []); [(b.update("
    "{enactor.id: b[enactor.id] + paid}), set_attr(me, 'bets', b), "
    "set_attr(me, 'pot', get_attr(me, 'pot', 0) + paid), remit(here, "
    "name(enactor) + ' pushes ' + str(paid) + ' into the pot -- staked "
    "' + str(b[enactor.id]) + ' this hand.')) for g in [live] if g]; "
    "(transfer_credits(me, enactor, paid), pemit(enactor, 'The table "
    "returns your credits: no hand in play for you.')) if not live and "
    "paid > 0 else None; set_attr(me, 'ledger', credits(me))",
    "@set the poker table/cmd_fold = $fold: f = get_attr(me, 'folded', "
    "[]); p = get_attr(me, 'players', []); ok = get_attr(me, 'phase') "
    "== 'betting' and enactor.id in p and enactor.id not in f; f2 = f + "
    "[enactor.id]; live = [pid for pid in p if pid not in f2]; "
    "[(set_attr(me, 'folded', f2), remit(here, name(enactor) + ' "
    "folds.')) for g in [ok] if g]; eval_attr(me, 'settle', "
    "' '.join(live)) if ok and len(live) == 1 else None",
    "@set the poker table/score = cs = arg0.split(); vs = "
    "sorted([member(c[:-1], '2 3 4 5 6 7 8 9 10 J Q K A') for c in "
    "cs], reverse=True); n = {v: vs.count(v) for v in vs}; shape = "
    "sorted(n.values(), reverse=True); cat = 7 if shape[0] == 4 else "
    "(6 if shape == [3, 2] else (3 if shape[0] == 3 else (2 if "
    "shape[:2] == [2, 2] else (1 if shape[0] == 2 else 0)))); result = "
    "[cat] + [pr[1] for pr in sorted([[n[v], v] for v in vs], "
    "reverse=True)]",
    "@set the poker table/catname = result = switch(int(arg0), 7, "
    "'four of a kind', 6, 'a full house', 3, 'three of a kind', 2, "
    "'two pair', 1, 'a pair', 'high card')",
    "@set the poker table/cmd_showdown = $showdown: p = get_attr(me, "
    "'players', []); f = get_attr(me, 'folded', []); b = get_attr(me, "
    "'bets', {}); live = [pid for pid in p if pid not in f]; h = "
    "get_attr(me, 'hands', {}); n = get_attr(me, 'names', {}); ok = "
    "get_attr(me, 'phase') == 'betting' and enactor.id in live and "
    "len(set([b[pid] for pid in live])) == 1 and b[live[0]] > 0; sc = "
    "{pid: eval_attr(me, 'score', ' '.join(h[pid])) for pid in live} if "
    "ok else {}; best = max(sc.values()) if ok else None; w = [pid for "
    "pid in live if sc[pid] == best] if ok else []; [remit(here, "
    "n.get(pid, '?') + ' shows ' + ' '.join(h[pid]) + ' -- ' + "
    "eval_attr(me, 'catname', str(sc[pid][0])) + '.') for g in [ok] if "
    "g for pid in live]; eval_attr(me, 'settle', ' '.join(w)) if ok "
    "else pemit(enactor, 'Not yet -- betting still open (all live "
    "stakes must match and be above zero).')",
    "@set the poker table/settle = w = arg0.split(); pot = get_attr(me, "
    "'pot', 0); share = pot // len(w); n = get_attr(me, 'names', {}); "
    "[transfer_credits(me, get('#' + pid), share) for pid in w]; "
    "remit(here, 'The pot -- ' + str(pot) + ' credits -- goes to ' + "
    "', '.join([n.get(pid, '?') for pid in w]) + '.'); set_attr(me, "
    "'pot', pot - share * len(w)); set_attr(me, 'phase', 'lobby'); "
    "set_attr(me, 'players', []); set_attr(me, 'hands', {}); "
    "set_attr(me, 'ledger', credits(me)); result = 1",
]


class TestPokerTable:

    async def _seated_and_dealt(self, sim, vala, kess, bob):
        await grant(sim, vala, kess, 100)
        await grant(sim, vala, bob, 100)
        await do(sim, kess, "sit")
        await do(sim, bob, "sit")
        return await do(sim, kess, "deal cards")   # kess's private hand line

    async def test_deal_requires_a_table_of_two(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, POKER_BUILD)
        drain_all(sim, vala, kess, bob)
        out = await do(sim, kess, "deal cards")
        assert any("Take a seat first" in line for line in out)
        out = await do(sim, kess, "sit")
        assert any("You are in." in line for line in out)
        out = await do(sim, kess, "sit")
        assert any("already seated" in line for line in out)

    async def test_bets_pot_and_fold_to_the_last_player(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, POKER_BUILD)
        deal_out = await self._seated_and_dealt(sim, vala, kess, bob)
        assert any("Your hand:" in line for line in deal_out)
        drain_all(sim, vala, kess, bob)

        await do(sim, kess, "pay 10 to the poker table")
        assert ("Kess pushes 10 into the pot -- staked 10 this hand."
                in sim.seen(bob))
        await do(sim, bob, "pay 10 to the poker table")
        sim.seen(kess)

        table = find_one(sim, "the poker table")
        assert table.db.get("pot") == 20

        # A bystander's payment bounces straight back.
        await grant(sim, vala, vala, 50)
        out = await do(sim, vala, "pay 5 to the poker table")
        assert any("The table returns your credits" in line for line in out)
        assert get_credits(vala) == 50

        drain_all(sim, vala, kess, bob)
        await do(sim, bob, "fold")
        kess_saw = "\n".join(sim.seen(kess))
        assert "Bob folds." in kess_saw
        assert "The pot -- 20 credits -- goes to Kess." in kess_saw
        assert get_credits(kess) == 110          # 100 - 10 + 20
        assert get_credits(bob) == 90
        assert table.db.get("phase") == "lobby"

    async def test_showdown_reveals_and_best_shape_wins(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, POKER_BUILD)
        await self._seated_and_dealt(sim, vala, kess, bob)
        await do(sim, kess, "pay 10 to the poker table")

        # Stakes differ -> showdown refused.
        out = await do(sim, kess, "showdown")
        assert any("Not yet -- betting still open" in line for line in out)

        await do(sim, bob, "pay 10 to the poker table")
        # Pin the showdown: the table's owner deals known hands.
        await do(sim, vala,
                 "@eval set_attr(get('the poker table'), 'hands', "
                 f"{{'{kess.id}': ['Ah', 'As', '2c', '5d', '9h'], "
                 f"'{bob.id}': ['Kh', 'Qs', '9c', '5s', '2d']}}); "
                 "result = 1")
        drain_all(sim, vala, kess, bob)

        await do(sim, kess, "showdown")
        saw = "\n".join(sim.seen(bob))
        assert "Kess shows Ah As 2c 5d 9h -- a pair." in saw
        assert "Bob shows Kh Qs 9c 5s 2d -- high card." in saw
        assert "The pot -- 20 credits -- goes to Kess." in saw
        assert get_credits(kess) == 110
        assert get_credits(bob) == 90

    async def test_hole_cards_are_engine_private(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, POKER_BUILD)
        await self._seated_and_dealt(sim, vala, kess, bob)
        result, err = await sim.eval(
            bob, "result = get_attr(get('the poker table'), 'hands')")
        assert err is None and result is None


# =========================================================================
# 101. Chess board — docs/showcase/101_chess_board.md
# =========================================================================

CHESS_BUILD = [
    "@create a chessboard",
    "drop a chessboard",
    "@desc a chessboard = Scarred maple, ranks and files burned in. "
    "[[result = ('White' if get_attr(me, 'turn', 'w') == 'w' else "
    "'Black') + ' to move.']]",
    "@set a chessboard/fresh = result = [list('rnbqkbnr'), "
    "list('pppppppp'), list('........'), list('........'), "
    "list('........'), list('........'), list('PPPPPPPP'), "
    "list('RNBQKBNR')]",
    "@set a chessboard/cmd_reset = $chess reset: set_attr(me, 'state', "
    "eval_attr(me, 'fresh')); set_attr(me, 'turn', 'w'); set_attr(me, "
    "'white', ''); set_attr(me, 'black', ''); remit(here, 'The "
    "chessboard resets to the opening position. Claim sides: white / "
    "black.')",
    "@set a chessboard/cmd_white = $white: taken = get_attr(me, "
    "'white', ''); (set_attr(me, 'white', enactor.id), remit(here, "
    "name(enactor) + ' takes white.')) if not taken else "
    "pemit(enactor, 'White is taken.')",
    "@set a chessboard/cmd_black = $black: taken = get_attr(me, "
    "'black', ''); (set_attr(me, 'black', enactor.id), remit(here, "
    "name(enactor) + ' takes black.')) if not taken else "
    "pemit(enactor, 'Black is taken.')",
    "@set a chessboard/cmd_board = $board: b = get_attr(me, 'state', "
    "[]); pemit(enactor, '  +' + repeat('-', 17) + '+'); "
    "[pemit(enactor, str(8 - i) + ' | ' + ' '.join(b[i]) + ' |') for i "
    "in range(8)]; pemit(enactor, '  +' + repeat('-', 17) + '+'); "
    "pemit(enactor, '    a b c d e f g h')",
    "@set a chessboard/sq = f = member(arg0[0], 'a b c d e f g h'); r = "
    "int(arg0[1]) if arg0[1].isdigit() else 0; result = [8 - r, f - 1] "
    "if f and 1 <= r <= 8 else None",
    "@set a chessboard/legal = b = get_attr(me, 'state', []); p = arg0; "
    "fr = int(arg1); fc = int(arg2); tr = int(arg3); tc = int(arg4); "
    "dr = tr - fr; dc = tc - fc; k = p.lower(); fwd = -1 if p.isupper() "
    "else 1; start = 6 if p.isupper() else 1; tgt = b[tr][tc]; steps = "
    "max(abs(dr), abs(dc)); sr = (dr > 0) - (dr < 0); sc = (dc > 0) - "
    "(dc < 0); clear = all([b[fr + sr * i][fc + sc * i] == '.' for i in "
    "range(1, steps)]); result = (dc == 0 and tgt == '.' and (dr == fwd "
    "or (fr == start and dr == 2 * fwd and clear)) or (abs(dc) == 1 and "
    "dr == fwd and tgt != '.')) if k == 'p' else ((dr == 0 or dc == 0) "
    "and clear if k == 'r' else (abs(dr) == abs(dc) and clear if k == "
    "'b' else ((dr == 0 or dc == 0 or abs(dr) == abs(dc)) and clear if "
    "k == 'q' else (steps == 1 if k == 'k' else sorted([abs(dr), "
    "abs(dc)]) == [1, 2]))))",
    "@set a chessboard/cmd_move = $move * *: b = get_attr(me, 'state', "
    "[]); a = eval_attr(me, 'sq', trim(arg0)); z = eval_attr(me, 'sq', "
    "trim(arg1)); t = get_attr(me, 'turn', 'w'); seat = get_attr(me, "
    "'white' if t == 'w' else 'black', ''); ok = bool(b) and a is not "
    "None and z is not None and enactor.id == seat; p = b[a[0]][a[1]] "
    "if ok else '.'; mine = p != '.' and (p.isupper() if t == 'w' else "
    "p.islower()); tgt = b[z[0]][z[1]] if ok else '.'; onmine = tgt != "
    "'.' and (tgt.isupper() if t == 'w' else tgt.islower()); ok2 = ok "
    "and mine and not onmine and eval_attr(me, 'legal', p, a[0], a[1], "
    "z[0], z[1]); [(set_attr(me, 'state', [[p if [i, j] == z else ('.' "
    "if [i, j] == a else b[i][j]) for j in range(8)] for i in "
    "range(8)]), set_attr(me, 'turn', 'b' if t == 'w' else 'w'), "
    "remit(here, ('White' if t == 'w' else 'Black') + ' plays ' + "
    "trim(arg0) + '-' + trim(arg1) + (', taking ' + tgt + '.' if tgt != "
    "'.' else '.'))) for g in [ok2] if g]; pemit(enactor, 'The pieces "
    "refuse: not your seat, not your turn, or not a legal move.') if "
    "not ok2 else None",
]


class TestChessBoard:

    async def _fresh_game(self, sim, vala, kess, bob):
        await build(sim, vala, CHESS_BUILD)
        await do(sim, vala, "chess reset")
        await do(sim, kess, "white")
        await do(sim, bob, "black")
        drain_all(sim, vala, kess, bob)

    async def test_board_renders_the_opening(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await self._fresh_game(sim, vala, kess, bob)
        out = await do(sim, kess, "board")
        joined = "\n".join(out)
        assert "8 | r n b q k b n r |" in joined
        assert "2 | P P P P P P P P |" in joined
        assert "    a b c d e f g h" in joined

    async def test_seats_turns_and_pawn_moves(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await self._fresh_game(sim, vala, kess, bob)

        out = await do(sim, vala, "white")
        assert any("White is taken." in line for line in out)

        await do(sim, kess, "move e2 e4")
        assert "White plays e2-e4." in sim.seen(bob)

        # White cannot move twice.
        out = await do(sim, kess, "move d2 d4")
        assert any("The pieces refuse" in line for line in out)

        await do(sim, bob, "move e7 e5")
        assert "Black plays e7-e5." in sim.seen(kess)

        # Double-step only from home: the e-pawn cannot leap again.
        out = await do(sim, kess, "move e4 e6")
        assert any("The pieces refuse" in line for line in out)

    async def test_blocked_rook_open_queen_and_capture(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await self._fresh_game(sim, vala, kess, bob)
        await do(sim, kess, "move e2 e4")
        await do(sim, bob, "move e7 e5")
        drain_all(sim, vala, kess, bob)

        # The rook cannot ghost through its own pawn.
        out = await do(sim, kess, "move a1 a4")
        assert any("The pieces refuse" in line for line in out)

        # The queen's diagonal is open after e4.
        await do(sim, kess, "move d1 h5")
        assert "White plays d1-h5." in sim.seen(bob)
        await do(sim, bob, "move a7 a6")
        sim.seen(kess)
        await do(sim, kess, "move h5 e5")
        assert "White plays h5-e5, taking p." in sim.seen(bob)

        board = find_one(sim, "a chessboard")
        state = board.db.get("state")
        assert state[3][4] == "Q"        # queen sits on e5
        assert state[7][3] == "."        # d1 vacated

        # Knights jump: b1-c3 from a crowded rank.
        await do(sim, bob, "move b8 c6")
        sim.seen(kess)
        await do(sim, kess, "move b1 c3")
        assert "White plays b1-c3." in sim.seen(bob)


# =========================================================================
# 102. Trivia host — docs/showcase/102_trivia_host.md
# =========================================================================

TRIVIA_BUILD = [
    "@create Quizmaster Quill",
    "@tag Quizmaster Quill = npc",
    "drop Quizmaster Quill",
    "@desc Quizmaster Quill = A waistcoated fussbudget with index cards "
    "and a brass bell.",
    '@set Quizmaster Quill/questions = [{"q": "Which planet wears the '
    'Great Red Spot?", "a": "jupiter"}, {"q": "How many faces has a '
    'd20?", "a": "20"}, {"q": "What do you pay a ferryman?", "a": '
    '"coin"}]',
    "@set Quizmaster Quill/window = 20",
    "@set Quizmaster Quill/tempo = 4",
    "@set Quizmaster Quill/cmd_start = $trivia: ok = not get_attr(me, "
    "'running', 0); [(set_attr(me, 'running', 1), set_attr(me, 'idx', "
    "0), set_attr(me, 'scores', {}), remit(here, 'Quill rings his "
    "bell: Trivia! Shout your answers. ' + str(len(get_attr(me, "
    "'questions', []))) + ' questions.'), eval_attr(me, 'ask')) for g "
    "in [ok] if g]; pemit(enactor, 'A game is already running.') if "
    "not ok else None",
    "@set Quizmaster Quill/ask = qs = get_attr(me, 'questions', []); i "
    "= get_attr(me, 'idx', 0); sc = get_attr(me, 'scores', {}); top = "
    "max(sc.values()) if sc else 0; champs = ', '.join(sorted([nm for "
    "nm, pts in sc.items() if pts == top])) if sc else 'nobody'; "
    "(set_attr(me, 'open', 1), set_attr(me, 'deadline', now() + "
    "get_attr(me, 'window', 20)), remit(here, 'Question ' + str(i + 1) "
    "+ ': ' + qs[i]['q']), wait(get_attr(me, 'window', 20), 'trigger "
    "me/times_up')) if i < len(qs) else (set_attr(me, 'running', 0), "
    "remit(here, 'That is the game! Top score: ' + champs + ' with ' + "
    "str(top) + '.')); result = 1",
    "@set Quizmaster Quill/next_q = eval_attr(me, 'ask')",
    "@set Quizmaster Quill/times_up = qs = get_attr(me, 'questions', "
    "[]); i = get_attr(me, 'idx', 0); (set_attr(me, 'open', 0), "
    "set_attr(me, 'idx', i + 1), remit(here, 'Time! The answer was: ' "
    "+ qs[i]['a'] + '.'), wait(get_attr(me, 'tempo', 4), 'trigger "
    "me/next_q')) if get_attr(me, 'open', 0) and now() >= get_attr(me, "
    "'deadline', 0) else None",
    "@set Quizmaster Quill/listen_guess = ^*: qs = get_attr(me, "
    "'questions', []); i = get_attr(me, 'idx', 0); live = get_attr(me, "
    "'running', 0) and get_attr(me, 'open', 0) and has_tag(enactor, "
    "'player') and i < len(qs); hit = live and qs[i]['a'] in "
    "trim(arg0).lower(); sc = get_attr(me, 'scores', {}); "
    "[(set_attr(me, 'open', 0), set_attr(me, 'idx', i + 1), "
    "sc.update({name(enactor): sc.get(name(enactor), 0) + 1}), "
    "set_attr(me, 'scores', sc), remit(here, name(enactor) + ' has "
    "it: ' + qs[i]['a'] + '! Score: ' + str(sc[name(enactor)]) + '.'), "
    "wait(get_attr(me, 'tempo', 4), 'trigger me/next_q')) for g in "
    "[hit] if g]",
    "@set Quizmaster Quill/cmd_scores = $standings: sc = get_attr(me, "
    "'scores', {}); pemit(enactor, 'Trivia standings:'); "
    "[pemit(enactor, '  ' + nm + ' -- ' + str(pts)) for nm, pts in "
    "sorted(sc.items(), key=lambda kv: -kv[1])]; pemit(enactor, '  (no "
    "scores yet)') if not sc else None",
]


class TestTriviaHost:

    async def test_a_full_timed_round(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, TRIVIA_BUILD)
        # Test-only pacing: zero the window and tempo so tick_waits()
        # can drive the clock deterministically.
        await do(sim, vala, "@set Quizmaster Quill/window = 0")
        await do(sim, vala, "@set Quizmaster Quill/tempo = 0")
        drain_all(sim, vala, kess, bob)

        await do(sim, vala, "trivia")
        saw = "\n".join(sim.seen(kess))
        assert "Quill rings his bell" in saw
        assert "Question 1: Which planet wears the Great Red Spot?" in saw

        # Wrong shouts cost nothing.
        await do(sim, kess, "say mars")
        assert not any("has it" in line for line in sim.seen(bob))

        # First correct shout scores and closes the window.
        await do(sim, kess, "say jupiter, surely")
        assert "Kess has it: jupiter! Score: 1." in sim.seen(bob)

        # The beat timer asks the next question.
        await sim.engine.tick_waits()
        assert any("Question 2: How many faces has a d20?" in line
                   for line in sim.seen(bob))

        # Nobody answers -> the window closes with the answer.
        await sim.engine.tick_waits()
        assert any("Time! The answer was: 20." in line
                   for line in sim.seen(bob))
        await sim.engine.tick_waits()
        assert any("Question 3: What do you pay a ferryman?" in line
                   for line in sim.seen(kess))

        await do(sim, bob, "say coin")
        assert "Bob has it: coin! Score: 1." in sim.seen(kess)

        out = await do(sim, kess, "standings")
        joined = "\n".join(out)
        assert "Kess -- 1" in joined and "Bob -- 1" in joined

        await sim.engine.tick_waits()
        assert any("That is the game! Top score: Bob, Kess with 1."
                   in line for line in sim.seen(kess))

        # The game over, a second start is allowed; a mid-game start is
        # refused.
        await do(sim, vala, "trivia")
        assert any("Question 1:" in line for line in sim.seen(bob))
        out = await do(sim, vala, "trivia")
        assert any("A game is already running." in line for line in out)


# =========================================================================
# 103. Rock-paper-scissors — docs/showcase/103_rock_paper_scissors.md
# =========================================================================

RPS_BUILD = [
    "@create the dueling stone",
    "drop the dueling stone",
    "@desc the dueling stone = A waist-high basalt block, split by a "
    "coin slot. [[bt = get_attr(me, 'bout', None); result = 'A bout is "
    "in progress.' if bt else 'The stone waits for a challenge.']]",
    "@set the dueling stone/choices = {}",
    "@attr the dueling stone/choices = secret",
    "@set the dueling stone/cmd_challenge = $challenge * for *: opp = "
    "get(trim(arg0)); w = int(trim(arg1)); ok = not get_attr(me, "
    "'bout', None) and opp is not None and has_tag(opp, 'player') and "
    "loc(opp) is here and opp is not enactor and w > 0; [(set_attr(me, "
    "'bout', {'a': enactor.id, 'b': opp.id, 'wager': w, 'paid': []}), "
    "set_attr(me, 'choices', {}), remit(here, name(enactor) + ' "
    "challenges ' + name(opp) + ' at the dueling stone: "
    "rock-paper-scissors for ' + str(w) + ' credits. Both must pay ' + "
    "str(w) + ' to the dueling stone.')) for g in [ok] if g]; "
    "pemit(enactor, 'The stone is busy, or that is no valid opponent "
    "or wager.') if not ok else None",
    "@set the dueling stone/on_payment = paid = credits(me) - "
    "get_attr(me, 'ledger', 0); bt = get_attr(me, 'bout', None); ok = "
    "bt is not None and enactor.id in [bt['a'], bt['b']] and "
    "enactor.id not in bt['paid'] and paid == bt['wager']; "
    "[(bt['paid'].append(enactor.id), set_attr(me, 'bout', bt), "
    "pemit(enactor, 'The stone accepts your stake.')) for g in [ok] if "
    "g]; [(remit(here, 'Both stakes are in. The stone addresses the "
    "duelists.'), prompt(get('#' + bt['a']), 'The stone hums: rock, "
    "paper, or scissors?', 'on_throw'), prompt(get('#' + bt['b']), "
    "'The stone hums: rock, paper, or scissors?', 'on_throw')) for g "
    "in [ok and len(bt['paid']) == 2] if g]; (transfer_credits(me, "
    "enactor, paid), pemit(enactor, 'The stone spits your credits "
    "back: wrong amount, or no bout of yours.')) if not ok and paid > "
    "0 else None; set_attr(me, 'ledger', credits(me))",
    "@set the dueling stone/on_throw = c = trim(arg0).lower(); bt = "
    "get_attr(me, 'bout', None); valid = c in ['rock', 'paper', "
    "'scissors'] and bt is not None and enactor.id in [bt['a'], "
    "bt['b']]; ch = get_attr(me, 'choices', {}); [(ch.update("
    "{enactor.id: c}), set_attr(me, 'choices', ch), pemit(enactor, "
    "'The stone sears your choice in silence: ' + c + '.')) for g in "
    "[valid] if g]; prompt(enactor, 'Rock, paper, or scissors -- "
    "nothing else:', 'on_throw') if bt is not None and not valid else "
    "None; eval_attr(me, 'resolve') if valid and len(ch) == 2 else "
    "None",
    "@set the dueling stone/resolve = bt = get_attr(me, 'bout', {}); "
    "ch = get_attr(me, 'choices', {}); a = bt['a']; b = bt['b']; an = "
    "name(get('#' + a)); bn = name(get('#' + b)); ca = ch[a]; cb = "
    "ch[b]; beats = {'rock': 'scissors', 'paper': 'rock', 'scissors': "
    "'paper'}; w = a if beats[ca] == cb else (b if beats[cb] == ca "
    "else ''); remit(here, 'The stone flares: ' + an + ' throws ' + ca "
    "+ '; ' + bn + ' throws ' + cb + '.'); (transfer_credits(me, "
    "get('#' + a), bt['wager']), transfer_credits(me, get('#' + b), "
    "bt['wager']), remit(here, 'A tie. The stakes slide back out of "
    "the slot.')) if not w else (transfer_credits(me, get('#' + w), "
    "bt['wager'] * 2), remit(here, name(get('#' + w)) + ' takes the "
    "pot: ' + str(bt['wager'] * 2) + ' credits.')); del_attr(me, "
    "'bout'); set_attr(me, 'choices', {}); set_attr(me, 'ledger', "
    "credits(me)); result = 1",
]


class TestRockPaperScissors:

    async def _bout_to_prompts(self, sim, vala, kess, bob, wager=10):
        await do(sim, kess, f"challenge Bob for {wager}")
        await do(sim, kess, f"pay {wager} to the dueling stone")
        await do(sim, bob, f"pay {wager} to the dueling stone")

    async def test_escrow_secret_commit_and_reveal(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, RPS_BUILD)
        await grant(sim, vala, kess, 30)
        await grant(sim, vala, bob, 30)
        drain_all(sim, vala, kess, bob)

        await do(sim, kess, "challenge Bob for 10")
        assert any("rock-paper-scissors for 10 credits" in line
                   for line in sim.seen(bob))
        out = await do(sim, kess, "pay 10 to the dueling stone")
        assert any("The stone accepts your stake." in line for line in out)
        await do(sim, bob, "pay 10 to the dueling stone")
        assert any("The stone hums: rock, paper, or scissors?" in line
                   for line in sim.seen(kess))

        # Kess commits first — her choice is sealed.
        await answer(sim, kess, "rock")
        result, err = await sim.eval(
            bob, "result = get_attr(get('the dueling stone'), 'choices')")
        assert err is None and result is None

        # A junk answer re-prompts instead of forfeiting.
        out = await answer(sim, bob, "banana")
        assert any("nothing else" in line for line in out)
        drain_all(sim, vala, kess, bob)
        await answer(sim, bob, "scissors")
        saw = "\n".join(sim.seen(vala))
        assert "The stone flares: Kess throws rock; Bob throws scissors." \
            in saw
        assert "Kess takes the pot: 20 credits." in saw
        assert get_credits(kess) == 40 and get_credits(bob) == 20

    async def test_ties_refund_both_stakes(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, RPS_BUILD)
        await grant(sim, vala, kess, 30)
        await grant(sim, vala, bob, 30)
        await self._bout_to_prompts(sim, vala, kess, bob)
        drain_all(sim, vala, kess, bob)
        await answer(sim, kess, "rock")
        await answer(sim, bob, "rock")
        assert any("A tie. The stakes slide back out of the slot." in line
                   for line in sim.seen(vala))
        assert get_credits(kess) == 30 and get_credits(bob) == 30

    async def test_stray_payments_bounce(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, RPS_BUILD)
        await grant(sim, vala, kess, 30)
        drain_all(sim, vala, kess, bob)
        out = await do(sim, kess, "pay 5 to the dueling stone")
        assert any("The stone spits your credits back" in line
                   for line in out)
        assert get_credits(kess) == 30


# =========================================================================
# 104. Scavenger hunt — docs/showcase/104_scavenger_hunt.md
# =========================================================================

HUNT_BUILD = [
    "@create the Hunt Board",
    "drop the Hunt Board",
    "@desc the Hunt Board = A corkboard headed THE GREAT HUNT, three "
    "photographs pinned beneath. [[lb = get_attr(me, 'leaderboard', "
    "{}); result = str(len(lb)) + ' hunters on the board.']]",
    '@set the Hunt Board/finds = ["a shard of driftglass", "a brass '
    'gear", "a violet feather"]',
    "@create a shard of driftglass",
    "@tag a shard of driftglass = hunt",
    "drop a shard of driftglass",
    "@create a brass gear",
    "@tag a brass gear = hunt",
    "drop a brass gear",
    "@create a violet feather",
    "@tag a violet feather = hunt",
    "drop a violet feather",
    "@set the Hunt Board/cmd_claim = $claim: want = get_attr(me, "
    "'finds', []); carried = [name(o) for o in contents(enactor) if "
    "has_tag(o, 'hunt')]; got = [nm for nm in want if nm in carried]; "
    "lb = get_attr(me, 'leaderboard', {}); best = lb.get(name(enactor), "
    "0); [(lb.update({name(enactor): len(got)}), set_attr(me, "
    "'leaderboard', lb)) for g in [len(got) > best] if g]; "
    "pemit(enactor, 'The board stamps your card: ' + str(len(got)) + ' "
    "of ' + str(len(want)) + ' finds.'); [(set_attr(me, 'champions', "
    "get_attr(me, 'champions', []) + [name(enactor)]), remit(here, "
    "name(enactor) + ' has found everything on the hunt!')) for g in "
    "[len(got) == len(want) and name(enactor) not in get_attr(me, "
    "'champions', [])] if g]",
    "@set the Hunt Board/cmd_hunters = $hunters: lb = get_attr(me, "
    "'leaderboard', {}); ch = get_attr(me, 'champions', []); "
    "pemit(enactor, 'THE GREAT HUNT -- standings:'); [pemit(enactor, "
    "'  ' + nm + ' -- ' + str(k) + ' finds' + (' [CHAMPION #' + "
    "str(ch.index(nm) + 1) + ']' if nm in ch else '')) for nm, k in "
    "sorted(lb.items(), key=lambda kv: -kv[1])]; pemit(enactor, '  "
    "(nobody yet)') if not lb else None",
]


class TestScavengerHunt:

    async def test_partial_full_and_forged_claims(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, HUNT_BUILD)
        drain_all(sim, vala, kess, bob)

        await do(sim, kess, "get a shard of driftglass")
        await do(sim, kess, "get a brass gear")
        out = await do(sim, kess, "claim")
        assert any("The board stamps your card: 2 of 3 finds." in line
                   for line in out)
        out = await do(sim, kess, "hunters")
        assert any("Kess -- 2 finds" in line for line in out)

        # A forged look-alike carries no tag and counts for nothing.
        await do(sim, vala, "@create a brass gear")
        await do(sim, vala, "give a brass gear to Bob")
        out = await do(sim, bob, "claim")
        assert any("The board stamps your card: 0 of 3 finds." in line
                   for line in out)

        drain_all(sim, vala, kess, bob)
        await do(sim, kess, "get a violet feather")
        out = await do(sim, kess, "claim")
        assert any("3 of 3 finds." in line for line in out)
        assert ("Kess has found everything on the hunt!"
                in sim.seen(bob))

        # Champion once, high-water mark holds.
        await do(sim, kess, "drop a violet feather")
        await do(sim, kess, "claim")
        out = await do(sim, kess, "hunters")
        joined = "\n".join(out)
        assert "Kess -- 3 finds [CHAMPION #1]" in joined
        board = find_one(sim, "the Hunt Board")
        assert board.db.get("champions") == ["Kess"]


# =========================================================================
# 105. NPC races & betting — docs/showcase/105_npc_races.md
# =========================================================================

RACES_BUILD = [
    "@create Bookie Barnum",
    "@tag Bookie Barnum = npc",
    "drop Bookie Barnum",
    "@desc Bookie Barnum = Loud coat, louder voice, a chalkboard of "
    "odds and a pocket that eats credits.",
    "@eval m = get('Bookie Barnum'); adjust_credits(m, 1000); "
    "set_attr(m, 'ledger', credits(m)); result = credits(m)",
    '@set Bookie Barnum/field = {"Comet": 2, "Old Thunder": 3, '
    '"Rustbucket": 5}',
    "@set Bookie Barnum/distance = 30",
    "@set Bookie Barnum/cmd_odds = $odds: f = get_attr(me, 'field', "
    "{}); pemit(enactor, 'The chalkboard:'); [pemit(enactor, '  ' + nm "
    "+ ' -- ' + str(od) + '-to-1') for nm, od in sorted(f.items())]; "
    "pemit(enactor, 'Pay me your stake, then: back <runner>.')",
    "@set Bookie Barnum/on_payment = paid = credits(me) - get_attr(me, "
    "'ledger', 0); ok = not get_attr(me, 'running', 0) and paid > 0; k "
    "= 'stake_' + enactor.id; (set_attr(me, k, get_attr(me, k, 0) + "
    "paid), pemit(enactor, 'Barnum palms your ' + str(paid) + ' "
    "credits: now back a runner.')) if ok else (transfer_credits(me, "
    "enactor, paid), pemit(enactor, 'No bets while they run. Your "
    "credits, returned.')) if paid > 0 else None; set_attr(me, "
    "'ledger', credits(me))",
    "@set Bookie Barnum/cmd_back = $back *: f = get_attr(me, 'field', "
    "{}); pickl = [nm for nm in f if nm.lower() == trim(arg0).lower()]; "
    "k = 'stake_' + enactor.id; st = get_attr(me, k, 0); ok = "
    "bool(pickl) and st > 0 and not get_attr(me, 'running', 0); bk = "
    "get_attr(me, 'book', {}); [(bk.update({enactor.id: {'runner': "
    "pickl[0], 'stake': st, 'name': name(enactor)}}), set_attr(me, "
    "'book', bk), del_attr(me, k), set_attr(me, 'post', get_attr(me, "
    "'post', 3)), remit(here, name(enactor) + ' backs ' + pickl[0] + ' "
    "for ' + str(st) + ' at ' + str(f[pickl[0]]) + '-to-1.')) for g in "
    "[ok] if g]; pemit(enactor, 'Pay your stake first, name a runner "
    "on the card, and bet before the off.') if not ok else None",
    "@behavior Bookie Barnum = script_ticker, interval:6",
    "@set Bookie Barnum/on_tick = eval_attr(me, 'stride') if "
    "get_attr(me, 'running', 0) else (eval_attr(me, 'countdown') if "
    "get_attr(me, 'book', {}) else None)",
    "@set Bookie Barnum/countdown = c = get_attr(me, 'post', 3) - 1; "
    "set_attr(me, 'post', c); (set_attr(me, 'running', 1), "
    "set_attr(me, 'positions', {nm: 0 for nm in get_attr(me, 'field', "
    "{})}), remit(here, 'A bell! They are off!')) if c <= 0 else "
    "remit(here, 'Barnum bawls: post time in ' + str(c) + '!'); "
    "result = 1",
    "@set Bookie Barnum/stride = f = get_attr(me, 'field', {}); pos = "
    "get_attr(me, 'positions', {}); upd = {nm: pos[nm] + rand(1, 9 - "
    "min(f[nm], 7)) for nm in pos}; set_attr(me, 'positions', upd); "
    "lead = max(upd, key=upd.get); dist = "
    "get_attr(me, 'distance', 30); (remit(here, lead + ' takes the "
    "wire! ' + lead + ' wins!'), eval_attr(me, 'payout', lead)) if "
    "upd[lead] >= dist else remit(here, lead + ' leads at the ' + "
    "str(upd[lead]) + ' mark.'); result = 1",
    "@set Bookie Barnum/payout = f = get_attr(me, 'field', {}); bk = "
    "get_attr(me, 'book', {}); [(transfer_credits(me, get('#' + pid), "
    "b['stake'] * (f[arg0] + 1)), pemit(get('#' + pid), 'Barnum counts "
    "out ' + str(b['stake'] * (f[arg0] + 1)) + ' credits. Pleasure "
    "doing business.')) for pid, b in bk.items() if b['runner'] == "
    "arg0]; set_attr(me, 'running', 0); set_attr(me, 'book', {}); "
    "del_attr(me, 'positions'); del_attr(me, 'post'); set_attr(me, "
    "'ledger', credits(me)); result = 1",
]


class TestNpcRaces:

    async def test_book_race_call_and_payout(self, sim, pinned_rand):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, RACES_BUILD)
        await grant(sim, vala, bob, 50)
        drain_all(sim, vala, kess, bob)

        out = await do(sim, bob, "odds")
        joined = "\n".join(out)
        assert "Comet -- 2-to-1" in joined
        assert "Rustbucket -- 5-to-1" in joined

        out = await do(sim, bob, "pay 10 to Bookie Barnum")
        assert any("Barnum palms your 10 credits" in line for line in out)
        await do(sim, bob, "back comet")
        assert ("Bob backs Comet for 10 at 2-to-1." in sim.seen(kess))

        # The countdown, tick by tick.
        await do(sim, vala, "@tr Bookie Barnum/on_tick")
        assert any("post time in 2!" in line for line in sim.seen(kess))
        await do(sim, vala, "@tr Bookie Barnum/on_tick")
        assert any("post time in 1!" in line for line in sim.seen(kess))
        await do(sim, vala, "@tr Bookie Barnum/on_tick")
        assert any("A bell! They are off!" in line for line in sim.seen(kess))

        # Pinned strides: Comet 7, Old Thunder 6, Rustbucket 4 per tick.
        pinned_rand["value"] = 10
        await do(sim, vala, "@tr Bookie Barnum/on_tick")
        assert any("Comet leads at the 7 mark." in line
                   for line in sim.seen(kess))

        # Past-posting bounces while they run.
        out = await do(sim, bob, "pay 5 to Bookie Barnum")
        assert any("No bets while they run. Your credits, returned."
                   in line for line in out)

        for _ in range(3):
            await do(sim, vala, "@tr Bookie Barnum/on_tick")
        sim.seen(kess)
        await do(sim, vala, "@tr Bookie Barnum/on_tick")   # 35 >= 30
        assert any("Comet takes the wire! Comet wins!" in line
                   for line in sim.seen(kess))
        assert any("Barnum counts out 30 credits" in line
                   for line in sim.seen(bob))
        assert get_credits(bob) == 70          # 50 - 10 + 30
        barnum = find_one(sim, "Bookie Barnum")
        assert get_credits(barnum) == 980      # 1000 + 10 - 30
        assert barnum.db.get("book") == {}
        assert not barnum.db.get("running")

    async def test_backing_without_a_stake_is_refused(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, RACES_BUILD)
        drain_all(sim, vala, kess, bob)
        out = await do(sim, bob, "back comet")
        assert any("Pay your stake first" in line for line in out)


# =========================================================================
# 106. Arm wrestling — docs/showcase/106_arm_wrestling.md
# =========================================================================

WRESTLE_BUILD = [
    "@create brawn",
    "@tag brawn = skill_def",
    "@set brawn/stat = strength",
    "@set brawn/penalty = 0",
    "@reload",
    "@create the wrestling table",
    "drop the wrestling table",
    "@desc the wrestling table = Elbow-polished oak, ringed by chalk "
    "lines and old beer. [[bt = get_attr(me, 'bout', None); result = "
    "'A grudge match is forming.' if bt else 'The chair opposite is "
    "empty.']]",
    "@set the wrestling table/cmd_wrestle = $wrestle * for *: opp = "
    "get(trim(arg0)); w = int(trim(arg1)); ok = not get_attr(me, "
    "'bout', None) and opp is not None and has_tag(opp, 'player') and "
    "loc(opp) is here and opp is not enactor and w > 0; [(set_attr(me, "
    "'bout', {'a': enactor.id, 'b': opp.id, 'wager': w, 'paid': []}), "
    "remit(here, name(enactor) + ' slaps ' + str(w) + ' credits on the "
    "table and calls out ' + name(opp) + '. Both: pay ' + str(w) + ' "
    "to the wrestling table.')) for g in [ok] if g]; pemit(enactor, "
    "'The table is busy, or that is no valid opponent or wager.') if "
    "not ok else None",
    "@set the wrestling table/on_payment = paid = credits(me) - "
    "get_attr(me, 'ledger', 0); bt = get_attr(me, 'bout', None); ok = "
    "bt is not None and enactor.id in [bt['a'], bt['b']] and "
    "enactor.id not in bt['paid'] and paid == bt['wager']; "
    "[(bt['paid'].append(enactor.id), set_attr(me, 'bout', bt), "
    "pemit(enactor, 'Your stake hits the wood.')) for g in [ok] if g]; "
    "(transfer_credits(me, enactor, paid), pemit(enactor, 'The table "
    "shrugs your credits back: wrong amount, or no bout of yours.')) "
    "if not ok and paid > 0 else None; set_attr(me, 'ledger', "
    "credits(me)); eval_attr(me, 'bout_go') if ok and len(bt['paid']) "
    "== 2 else None",
    "@set the wrestling table/bout_go = bt = get_attr(me, 'bout', {}); "
    "a = get('#' + bt['a']); b = get('#' + bt['b']); remit(here, "
    "name(a) + ' and ' + name(b) + ' lock hands over the scarred "
    "tabletop. The crowd leans in.'); win = a if contest(a, 'brawn', "
    "b, 'brawn') else b; lose = b if win is a else a; remit(here, "
    "'Knuckles whiten, the table groans... ' + name(win) + \" slams \" "
    "+ name(lose) + \"'s arm down! The crowd roars.\"); "
    "transfer_credits(me, win, bt['wager'] * 2); remit(here, name(win) "
    "+ ' scoops the pot: ' + str(bt['wager'] * 2) + ' credits.'); "
    "del_attr(me, 'bout'); set_attr(me, 'ledger', credits(me)); "
    "result = 1",
]


class TestArmWrestling:

    async def test_skill_def_bridges_strength_into_contests(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, WRESTLE_BUILD)
        from realm.core.checks import SKILL_DEFAULTS
        assert SKILL_DEFAULTS.get("brawn") == ("strength", 0)

    async def test_wagered_bout_with_crowd_call(self, sim, pinned_dice):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, WRESTLE_BUILD)
        await grant(sim, vala, kess, 20)
        await grant(sim, vala, bob, 20)
        # Pinned 3d6 = 12: ST 14 succeeds by 2, ST 8 fails — Kess wins.
        pinned_dice["value"] = 4
        # Sheet-writes are builder-gated; the admin sets the demo stats.
        await do(sim, vala, "@set Kess/strength = 14")
        await do(sim, vala, "@set Bob/strength = 8")
        drain_all(sim, vala, kess, bob)

        await do(sim, kess, "wrestle Bob for 10")
        assert any("calls out Bob. Both: pay 10 to the wrestling table."
                   in line for line in sim.seen(bob))
        out = await do(sim, kess, "pay 10 to the wrestling table")
        assert any("Your stake hits the wood." in line for line in out)
        drain_all(sim, vala, kess, bob)
        await do(sim, bob, "pay 10 to the wrestling table")
        saw = "\n".join(sim.seen(vala))
        assert ("Kess and Bob lock hands over the scarred tabletop. "
                "The crowd leans in.") in saw
        assert ("Knuckles whiten, the table groans... Kess slams Bob's "
                "arm down! The crowd roars.") in saw
        assert "Kess scoops the pot: 20 credits." in saw
        assert get_credits(kess) == 30 and get_credits(bob) == 10

        table = find_one(sim, "the wrestling table")
        assert table.db.get("bout") is None
        assert get_credits(table) == 0

    async def test_stray_payment_shrugged_back(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, WRESTLE_BUILD)
        await grant(sim, vala, bob, 20)
        drain_all(sim, vala, kess, bob)
        out = await do(sim, bob, "pay 7 to the wrestling table")
        assert any("The table shrugs your credits back" in line
                   for line in out)
        assert get_credits(bob) == 20


# =========================================================================
# 107. Dart board — docs/showcase/107_dart_board.md
# =========================================================================

DARTS_BUILD = [
    "@create a dart board",
    "drop a dart board",
    "@desc a dart board = Cork and sisal, more hole than board. "
    "[[result = 'Chalked below: house record ' + str(get_attr(me, "
    "'record', 0)) + '.']]",
    "@set a dart board/cmd_throw = $throw: lvl = get_attr(enactor, "
    "'skill_darts', get_attr(enactor, 'dexterity', 10) - 4); r = "
    "margin_under(roll('3d6'), lvl, skill='darts'); m = r.margin; pts "
    "= 50 if r.success and m >= 6 else (25 if r.success and m >= 3 "
    "else (15 if r.success and m >= 1 else (5 if r.success else 0))); "
    "spot = switch(pts, 50, 'BULLSEYE', 25, 'the inner ring', 15, 'a "
    "fat single', 5, 'the rim', 'the wall with a sad thunk'); "
    "remit(here, name(enactor) + ' throws -- ' + spot + '! (' + "
    "str(pts) + ' points)'); t = 'total_' + enactor.id; total = "
    "get_attr(me, t, 0) + pts; set_attr(me, t, total); set_attr(me, "
    "'record', max(get_attr(me, 'record', 0), total)); k = 'practice_' "
    "+ enactor.id; n = get_attr(me, k, 0) + 1; set_attr(me, k, n); "
    "(pemit(enactor, 'Your arm is learning: darts rises to ' + str(lvl "
    "+ 1) + '.') if set_attr(enactor, 'skill_darts', lvl + 1) else "
    "None) if n % 10 == 0 else None",
    "@set a dart board/cmd_chalk = $chalk: pemit(enactor, 'Your chalk "
    "line: ' + str(get_attr(me, 'total_' + enactor.id, 0)) + ' points "
    "over ' + str(get_attr(me, 'practice_' + enactor.id, 0)) + ' "
    "darts.')",
]


class TestDartBoard:

    async def test_margins_pick_rings_and_practice_trains(
            self, sim, pinned_dice):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, DARTS_BUILD)
        drain_all(sim, vala, kess, bob)

        pinned_dice["value"] = 4          # every 3d6 rolls 12
        # Untrained: DX 10 -> darts 6; 12 vs 6 misses -> the wall.
        await do(sim, kess, "throw")
        assert ("Kess throws -- the wall with a sad thunk! (0 points)"
                in sim.seen(bob))

        # Trained: 12 vs 14 -> margin 2 -> a fat single. (Sheet-writes are
        # builder-gated; the admin trains the demo skill.)
        await do(sim, vala, "@set Kess/skill_darts = 14")
        sim.seen(kess)
        await do(sim, kess, "throw")
        assert ("Kess throws -- a fat single! (15 points)"
                in sim.seen(bob))
        out = await do(sim, kess, "chalk")
        assert any("Your chalk line: 15 points over 2 darts." in line
                   for line in out)

        # Eight more darts: the tenth throw earns the practice award —
        # the admin-owned board writes the player's sheet.
        for _ in range(7):
            await do(sim, kess, "throw")
        out = await do(sim, kess, "throw")                # dart #10
        assert any("Your arm is learning: darts rises to 15." in line
                   for line in out)
        assert kess.db.get("skill_darts") == 15
        board = find_one(sim, "a dart board")
        assert board.db.get("practice_" + kess.id) == 10
        assert board.db.get("total_" + kess.id) == 135    # 0 + 9 * 15
        assert board.db.get("record") == 135

        # The sharper arm shows: 12 vs 15 -> margin 3 -> inner ring.
        drain_all(sim, vala, kess, bob)
        await do(sim, kess, "throw")
        assert ("Kess throws -- the inner ring! (25 points)"
                in sim.seen(bob))
        out = await do(sim, kess, "look a dart board")
        assert any("house record 160." in line for line in out)


# =========================================================================
# 108. Casino floor — docs/showcase/108_casino_floor.md
# =========================================================================

CASINO_BUILD = [
    "@dig The Casino Floor",
    "@teleport The Casino Floor",
    "@create the cashier cage",
    "drop the cashier cage",
    "@desc the cashier cage = Brass bars over a marble sill. [[result "
    "= 'The reserve holds ' + str(credits(me)) + ' credits.']]",
    "@set the cashier cage/on_payment = paid = credits(me) - "
    "get_attr(me, 'ledger', 0); c = create_obj('casino chips', "
    "tags=['thing', 'chip'], location=enactor) if paid > 0 else None; "
    "(set_attr(c, 'chips', paid), pemit(enactor, 'The teller slides ' "
    "+ str(paid) + ' in chips under the bars.')) if c is not None else "
    "None; set_attr(me, 'ledger', credits(me))",
    "@set the cashier cage/cmd_cashin = $cashin: stacks = [o for o in "
    "contents(enactor) if has_tag(o, 'chip')]; total = sum(get_attr(o, "
    "'chips', 0) for o in stacks); ok = total > 0 and "
    "transfer_credits(me, enactor, total); [destroy_obj(o) for g in "
    "[ok] if g for o in stacks]; pemit(enactor, 'The teller counts ' + "
    "str(total) + ' in chips back into credits.' if ok else 'You have "
    "no chips, or the cage cannot cover them.'); set_attr(me, "
    "'ledger', credits(me))",
    "@create Croupier Hazel",
    "@tag Croupier Hazel = npc",
    "drop Croupier Hazel",
    "@desc Croupier Hazel = Green visor, quick hands, a wheel of "
    "numbered brass. Hand her chips to play double-or-nothing.",
    "@set Croupier Hazel/on_receive = stakes = [o for o in "
    "contents(me) if has_tag(o, 'chip') and not get_attr(o, 'house', "
    "0)]; w = sum(get_attr(o, 'chips', 0) for o in stakes); rack = [o "
    "for o in contents(me) if has_tag(o, 'chip') and get_attr(o, "
    "'house', 0)]; f = rack[0] if rack else None; ok = w > 0 and f is "
    "not None; short = ok and get_attr(f, 'chips', 0) < w; "
    "[(move_to(o, enactor), pemit(enactor, 'Hazel pushes your chips "
    "back: the rack cannot cover that.')) for g in [short] if g for o "
    "in stakes]; play = ok and not short; [(set_attr(f, 'chips', "
    "get_attr(f, 'chips', 0) + w), [destroy_obj(o) for o in stakes], "
    "set_attr(me, 'spin', rand(1, 100))) for g in [play] if g]; win = "
    "play and get_attr(me, 'spin', 100) <= 45; [(set_attr(f, 'chips', "
    "get_attr(f, 'chips', 0) - 2 * w), set_attr(create_obj('casino "
    "chips', tags=['thing', 'chip'], location=enactor), 'chips', 2 * "
    "w), remit(here, 'Hazel spins the wheel... ' + name(enactor) + ' "
    "doubles up! ' + str(2 * w) + ' in chips slide back.')) for g in "
    "[win] if g]; remit(here, 'Hazel spins the wheel... the house "
    "rakes ' + str(w) + ' in chips.') if play and not win else None",
    "@eval adjust_credits(me, 500); result = credits(me)",
    "pay 500 to the cashier cage",
    "@set casino chips/house = 1",
    "give casino chips to Croupier Hazel",
]


def chips_outstanding(sim):
    """Face value of every chip stack in the world."""
    return sum(int(o.db.get("chips") or 0)
               for o in sim.store.all_cached() if o.has_tag("chip"))


class TestCasinoFloor:

    async def _floor(self, sim, vala, kess, bob):
        # The mortals follow the pit boss onto the new floor.
        await build(sim, vala, CASINO_BUILD)
        floor = find_one(sim, "The Casino Floor")
        kess.location = floor
        bob.location = floor
        return floor

    async def test_cage_mints_melts_and_conserves(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await self._floor(sim, vala, kess, bob)
        cage = find_one(sim, "the cashier cage")
        # Post-seeding: 500 in reserve backs Hazel's 500 float.
        assert get_credits(cage) == 500 == chips_outstanding(sim)

        await grant(sim, vala, bob, 200)
        drain_all(sim, vala, kess, bob)
        out = await do(sim, bob, "pay 100 to the cashier cage")
        assert any("The teller slides 100 in chips under the bars."
                   in line for line in out)
        stacks = [o for o in bob.contents if o.has_tag("chip")]
        assert len(stacks) == 1 and stacks[0].db.get("chips") == 100
        assert get_credits(cage) == 600 == chips_outstanding(sim)

        out = await do(sim, bob, "cashin")
        assert any("The teller counts 100 in chips back into credits."
                   in line for line in out)
        assert get_credits(bob) == 200
        assert get_credits(cage) == 500 == chips_outstanding(sim)

        out = await do(sim, bob, "cashin")
        assert any("You have no chips" in line for line in out)

    async def test_wheel_win_pays_from_the_float(self, sim, pinned_rand):
        room, vala, kess, bob = parlor_and_staff(sim)
        await self._floor(sim, vala, kess, bob)
        cage = find_one(sim, "the cashier cage")
        await grant(sim, vala, bob, 200)
        await do(sim, bob, "pay 100 to the cashier cage")
        drain_all(sim, vala, kess, bob)

        pinned_rand["value"] = 45          # 45 <= 45: a win
        await do(sim, bob, "give casino chips to Croupier Hazel")
        assert any("Bob doubles up! 200 in chips slide back." in line
                   for line in sim.seen(kess))
        stacks = [o for o in bob.contents if o.has_tag("chip")]
        assert len(stacks) == 1 and stacks[0].db.get("chips") == 200
        hazel = find_one(sim, "Croupier Hazel")
        rack = [o for o in hazel.contents if o.db.get("house")]
        assert rack[0].db.get("chips") == 400
        assert get_credits(cage) == 600 == chips_outstanding(sim)

        await do(sim, bob, "cashin")
        assert get_credits(bob) == 300     # 200 - 100 + 200
        assert get_credits(cage) == 400 == chips_outstanding(sim)

    async def test_wheel_loss_rakes_into_the_float(self, sim, pinned_rand):
        room, vala, kess, bob = parlor_and_staff(sim)
        await self._floor(sim, vala, kess, bob)
        cage = find_one(sim, "the cashier cage")
        await grant(sim, vala, bob, 200)
        await do(sim, bob, "pay 50 to the cashier cage")
        drain_all(sim, vala, kess, bob)

        pinned_rand["value"] = 99          # a loss
        await do(sim, bob, "give casino chips to Croupier Hazel")
        assert any("the house rakes 50 in chips." in line
                   for line in sim.seen(kess))
        assert not [o for o in bob.contents if o.has_tag("chip")]
        hazel = find_one(sim, "Croupier Hazel")
        rack = [o for o in hazel.contents if o.db.get("house")]
        assert rack[0].db.get("chips") == 550
        assert get_credits(cage) == 550 == chips_outstanding(sim)

    async def test_uncoverable_stakes_are_pushed_back(
            self, sim, pinned_rand):
        room, vala, kess, bob = parlor_and_staff(sim)
        await self._floor(sim, vala, kess, bob)
        cage = find_one(sim, "the cashier cage")
        await grant(sim, vala, bob, 600)
        await do(sim, bob, "pay 600 to the cashier cage")
        drain_all(sim, vala, kess, bob)

        # Stake 600 against a 500 float: Hazel refuses and returns it.
        out = await do(sim, bob, "give casino chips to Croupier Hazel")
        assert any("Hazel pushes your chips back: the rack cannot "
                   "cover that." in line for line in out)
        stacks = [o for o in bob.contents if o.has_tag("chip")]
        assert len(stacks) == 1 and stacks[0].db.get("chips") == 600
        assert get_credits(cage) == 1100 == chips_outstanding(sim)


# =========================================================================
# Docs <-> tests sync — the transcripts above must match the tutorials
# =========================================================================

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

DOC_TRANSCRIPTS = {
    "098_dice_roller.md": DICE_BUILD,
    "099_card_deck.md": DECK_BUILD,
    "100_poker_table.md": POKER_BUILD,
    "101_chess_board.md": CHESS_BUILD,
    "102_trivia_host.md": TRIVIA_BUILD,
    "103_rock_paper_scissors.md": RPS_BUILD,
    "104_scavenger_hunt.md": HUNT_BUILD,
    "105_npc_races.md": RACES_BUILD,
    "106_arm_wrestling.md": WRESTLE_BUILD,
    "107_dart_board.md": DARTS_BUILD,
    "108_casino_floor.md": CASINO_BUILD,
}


def test_tutorial_docs_contain_the_exact_tested_command_lines():
    """Every Build-it line exercised above appears verbatim in its doc,
    so the tutorials can never drift from what the tests prove works."""
    for doc_name, lines in DOC_TRANSCRIPTS.items():
        text = (DOCS / doc_name).read_text(encoding="utf-8")
        for line in lines:
            assert line in text, (
                f"{doc_name} is missing a tested tutorial line:\n{line}")
