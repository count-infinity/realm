"""
Showcase "Games & Recreation" — checklist items 98, 99, 100, 101, 102,
103, 104, 105, 106, 107, 108.

Verifies the standalone tutorials in docs/showcase/ (098_dice_roller.md
through 108_casino_floor.md) by driving a real in-process world —
realm.testing.Simulator wires the same store/propagation/scripting/
dispatcher stack a live GameServer does — with the tutorials' EXACT
command lines (raw input in, session output out).

Every command line in each tutorial's "Build it" section is read
straight out of its markdown and driven through the real dispatcher, so
the tests execute what the docs actually say: a doc edit that breaks a
build breaks this suite, and there is nothing left to drift.
Determinism: rand() is pinned via realm.scripting.functions.random,
the dice kernel (roll/margin_under/skill_check/contest) via
realm.core.dice.random; wait() chains run on the Simulator's virtual
clock (engine.tick_waits()); prompt() wizards answer through the
session's captured input handler — the same techniques the gadget and
economy suites use.
"""

from __future__ import annotations

from pathlib import Path
import re
from types import SimpleNamespace

import pytest

import realm.behaviors  # noqa: F401 — registers script_ticker
from realm.core.economy import get_credits
from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

BUILD_FAILURE_MARKERS = (
    "Unknown command",
    "Permission denied",
    "Usage:",
    "not found",
    "Script error",
    "Eval error",
    "error",
)


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

DICE_BUILD = build_lines("098_dice_roller.md")


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

DECK_BUILD = build_lines("099_card_deck.md")


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

POKER_BUILD = build_lines("100_poker_table.md")


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

    async def test_a_neighbours_payment_never_reaches_the_pot(self, sim):
        """ON_PAYMENT is a witnessed event: it fires on every object in
        the room, not just the one paid. The table's hook must check
        `target == me` or adata('amount') hands it the bartender's
        money -- and a seated player buying a drink stakes it by
        accident. Drop the guard from the doc and this test fails."""
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, POKER_BUILD)
        # A second payable, standing in the same room as the table.
        await build(sim, vala, [
            "@create the bartender",
            "drop the bartender",
        ])
        await self._seated_and_dealt(sim, vala, kess, bob)
        table = find_one(sim, "the poker table")
        drain_all(sim, vala, kess, bob)

        # Kess is seated and betting -- the exact player the unguarded
        # hook would misread. She buys a drink instead.
        await do(sim, kess, "pay 7 to the bartender")
        assert table.db.get("pot") in (None, 0)       # nothing staked
        assert table.db.get("bets")[kess.id] == 0
        saw = "\n".join(sim.seen(bob))
        assert "into the pot" not in saw
        assert "returns your credits" not in saw     # nor a spurious refund
        assert get_credits(kess) == 93               # 100 - the drink, only

        # ...and the table still takes a real bet.
        await do(sim, kess, "pay 10 to the poker table")
        assert table.db.get("pot") == 10

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

CHESS_BUILD = build_lines("101_chess_board.md")


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

TRIVIA_BUILD = build_lines("102_trivia_host.md")


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

RPS_BUILD = build_lines("103_rock_paper_scissors.md")


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

    async def test_a_neighbours_payment_is_not_a_stake(self, sim):
        """The stone must check `target == me`: unguarded, adata('amount')
        would hand it a payment made to the tip jar beside it, and a
        duelist's unrelated 10-credit purchase would silently pay their
        stake. Drop the guard from the doc and this test fails."""
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, RPS_BUILD)
        await build(sim, vala, ["@create a tip jar", "drop a tip jar"])
        await grant(sim, vala, kess, 30)
        await grant(sim, vala, bob, 30)
        await do(sim, kess, "challenge Bob for 10")
        stone = find_one(sim, "the dueling stone")
        drain_all(sim, vala, kess, bob)

        # Exactly the wager, from a listed duelist -- but to the jar.
        await do(sim, kess, "pay 10 to a tip jar")
        assert stone.db.get("bout")["paid"] == []       # no stake banked
        saw = "\n".join(sim.seen(kess))
        assert "accepts your stake" not in saw
        assert "spits your credits back" not in saw     # nor a bogus refund
        assert get_credits(kess) == 20                  # the jar has it

        # The real stake still banks.
        await do(sim, kess, "pay 10 to the dueling stone")
        assert stone.db.get("bout")["paid"] == [kess.id]

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

HUNT_BUILD = build_lines("104_scavenger_hunt.md")


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

RACES_BUILD = build_lines("105_npc_races.md")


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

    async def test_a_neighbours_payment_arms_no_stake(self, sim):
        """Barnum must check `target == me`, or paying the hot-dog cart
        beside him arms a free bet. Drop the guard and this fails."""
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, RACES_BUILD)
        await build(sim, vala, ["@create a hot-dog cart", "drop a hot-dog cart"])
        await grant(sim, vala, bob, 50)
        barnum = find_one(sim, "Bookie Barnum")
        drain_all(sim, vala, kess, bob)

        await do(sim, bob, "pay 10 to a hot-dog cart")
        assert barnum.db.get("stake_" + bob.id) is None    # nothing armed
        assert "palms your" not in "\n".join(sim.seen(bob))
        out = await do(sim, bob, "back comet")
        assert any("Pay your stake first" in line for line in out)

        # A real stake still arms.
        await do(sim, bob, "pay 10 to Bookie Barnum")
        assert barnum.db.get("stake_" + bob.id) == 10

    async def test_backing_without_a_stake_is_refused(self, sim):
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, RACES_BUILD)
        drain_all(sim, vala, kess, bob)
        out = await do(sim, bob, "back comet")
        assert any("Pay your stake first" in line for line in out)


# =========================================================================
# 106. Arm wrestling — docs/showcase/106_arm_wrestling.md
# =========================================================================

WRESTLE_BUILD = build_lines("106_arm_wrestling.md")


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

    async def test_a_neighbours_payment_starts_no_bout(self, sim):
        """The wrestling table must check `target == me`: unguarded, both
        duelists paying the bar next to it would start the bout for free.
        Drop the guard from the doc and this test fails."""
        room, vala, kess, bob = parlor_and_staff(sim)
        await build(sim, vala, WRESTLE_BUILD)
        await build(sim, vala, ["@create a beer tap", "drop a beer tap"])
        await grant(sim, vala, kess, 20)
        await grant(sim, vala, bob, 20)
        await do(sim, kess, "wrestle Bob for 10")
        table = find_one(sim, "the wrestling table")
        drain_all(sim, vala, kess, bob)

        await do(sim, kess, "pay 10 to a beer tap")
        await do(sim, bob, "pay 10 to a beer tap")
        assert table.db.get("bout")["paid"] == []       # no stakes banked
        assert "lock hands" not in "\n".join(sim.seen(vala))   # no bout
        assert get_credits(table) == 0                  # and no escrow

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

DARTS_BUILD = build_lines("107_dart_board.md")


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

CASINO_BUILD = build_lines("108_casino_floor.md")


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

    async def test_a_payment_to_a_neighbour_mints_no_chips(self, sim):
        """The floor deliberately puts several payment-takers in one
        room, and ON_PAYMENT fires on all of them. Unguarded, paying the
        slot machine would have the cage mint chips backed by nothing --
        breaking reserve == chips-outstanding, the invariant this whole
        tutorial is about. Remove `if target == me` and this fails."""
        room, vala, kess, bob = parlor_and_staff(sim)
        floor = await self._floor(sim, vala, kess, bob)
        cage = find_one(sim, "the cashier cage")
        await build(sim, vala, [
            "@create a slot machine",
            "drop a slot machine",
        ])
        await grant(sim, vala, bob, 200)
        before = get_credits(cage)
        assert before == chips_outstanding(sim)
        drain_all(sim, vala, kess, bob)

        await do(sim, bob, "pay 25 to a slot machine")
        assert not [o for o in bob.contents if o.has_tag("chip")]
        assert get_credits(cage) == before == chips_outstanding(sim)
        assert get_credits(bob) == 175

        # The cage itself still works.
        await do(sim, bob, "pay 100 to the cashier cage")
        stacks = [o for o in bob.contents if o.has_tag("chip")]
        assert len(stacks) == 1 and stacks[0].db.get("chips") == 100
        assert get_credits(cage) == before + 100 == chips_outstanding(sim)

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
