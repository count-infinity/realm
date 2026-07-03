"""
Tests for the tiered name matcher (realm.core.search) and its wiring
into the command helpers.

Tier contract: exact > word-prefix (scored, left-to-right) > substring.
Exact can never be ambushed by a partial; ambiguity is surfaced, not
guessed away; name-N picks between twins.
"""

from __future__ import annotations

import pytest

from realm.commands.base import find_exit, find_object, find_object_global
from realm.core.objects import GameObject
from realm.core.propagation import reset_engine
from realm.core.search import (
    AmbiguousMatchError,
    format_ambiguous,
    match_objects,
    match_one,
)
from realm.gateway.session import Session
from realm.server.dispatcher import CommandContext, CommandDispatcher


@pytest.fixture(autouse=True)
def fresh_propagation_engine():
    reset_engine()
    yield
    reset_engine()


def objs(*names: str) -> list[GameObject]:
    return [GameObject(name) for name in names]


# --- Matcher tiers -----------------------------------------------------------


class TestMatchTiers:

    def test_exact_beats_prefix(self):
        box, gloves = objs("box", "boxing gloves")
        result = match_objects("box", [box, gloves])
        assert result.tier == "exact"
        assert result.matches == [box]

    def test_exact_is_case_insensitive(self):
        (promenade,) = objs("Station Promenade")
        assert match_objects("station promenade", [promenade]).matches == [promenade]

    def test_alias_counts_as_exact(self):
        sword = GameObject("Ancient Blade")
        sword.db.aliases = ["sword"]
        assert match_objects("sword", [sword]).tier == "exact"

    def test_word_prefix_matches_inner_word(self):
        (promenade,) = objs("Station Promenade")
        result = match_objects("prom", [promenade])
        assert result.tier == "word_prefix"
        assert result.matches == [promenade]

    def test_multiword_query_all_words_must_match(self):
        big_sword, big_shield = objs("Big Sword", "Big Shield")
        result = match_objects("big sw", [big_sword, big_shield])
        assert result.matches == [big_sword]

    def test_word_prefix_is_order_sensitive(self):
        (big_sword,) = objs("Big Sword")
        assert match_objects("sword big", [big_sword]).matches == []

    def test_scoring_prefers_more_matched_words(self):
        big_sword, sword = objs("Big Sword", "Sword of Bigness")
        # "big sw" scores 2 on Big Sword; fails on "Sword of Bigness"
        # (consumed left-to-right: 'big' matches 'Bigness' too late).
        result = match_objects("big sw", [sword, big_sword])
        assert result.matches == [big_sword]

    def test_substring_as_last_resort(self):
        (burger,) = objs("Burgermeister")
        result = match_objects("meister", [burger])
        assert result.tier == "substring"
        assert result.matches == [burger]

    def test_substring_can_be_disabled(self):
        (burger,) = objs("Burgermeister")
        assert match_objects("meister", [burger], allow_substring=False).matches == []

    def test_no_match(self):
        assert match_objects("dragon", objs("box", "sword")).matches == []

    def test_empty_query_and_candidates(self):
        assert match_objects("", objs("box")).matches == []
        assert match_objects("box", []).matches == []

    def test_candidates_deduplicated(self):
        (box,) = objs("box")
        assert match_objects("box", [box, box]).matches == [box]


class TestMultimatchPick:

    def test_name_number_picks_nth(self):
        box1, box2 = objs("box", "box")
        result = match_objects("box-2", [box1, box2])
        assert result.matches == [box2]

    def test_name_number_out_of_range(self):
        box1, box2 = objs("box", "box")
        assert match_objects("box-3", [box1, box2]).matches == []

    def test_literal_name_with_dash_wins_over_pick(self):
        # An object literally named "box-2" is matched exactly, not
        # treated as a pick of the second "box".
        box, box_2 = objs("box", "box-2")
        result = match_objects("box-2", [box, box_2])
        assert result.matches == [box_2]

    def test_match_one_autopicks_identical_twins(self):
        # Visually identical objects: prompting is noise, take the first.
        box1, box2 = objs("box", "box")
        assert match_one("box", [box1, box2]) is box1

    def test_match_one_raises_when_matches_differ(self):
        gem, rock = objs("red gem", "red rock")
        with pytest.raises(AmbiguousMatchError) as exc:
            match_one("red", [gem, rock])
        assert exc.value.matches == [gem, rock]

    def test_format_ambiguous_lists_picks(self):
        room = GameObject("Room", tags=["room"])
        looker = GameObject("Alice", location=room, tags=["player"])
        carried = GameObject("box", location=looker)
        floor = GameObject("box", location=room)

        text = format_ambiguous(AmbiguousMatchError("box", [carried, floor]), looker)

        assert "Which 'box' do you mean?" in text
        assert "box-1 (carried)" in text
        assert "box-2 (here)" in text
        assert "box-1" in text.splitlines()[-1]  # usage hint


# --- Command helper integration ----------------------------------------------


def make_ctx(player: GameObject, persistence=None) -> CommandContext:
    sess = Session(protocol="test", address="127.0.0.1")
    sess.link_player(player)
    dispatcher = CommandDispatcher()
    dispatcher.persistence = persistence
    return CommandContext(
        session=sess,
        player=player,
        raw_input="",
        command_name="test",
        args="",
        dispatcher=dispatcher,
    )


class MockPersistence:
    def __init__(self, *objects):
        self._cache = {o.id: o for o in objects}

    def get_cached(self, obj_id):
        return self._cache.get(obj_id)

    def all_cached(self):
        return list(self._cache.values())


class TestHelperIntegration:

    def test_find_object_partial_in_room(self):
        room = GameObject("Room", tags=["room"])
        relic = GameObject("ancient relic", location=room, tags=["thing"])
        alice = GameObject("Alice", location=room, tags=["player"])

        assert find_object(make_ctx(alice), "rel") is relic

    def test_find_object_ambiguous_raises(self):
        room = GameObject("Room", tags=["room"])
        GameObject("red gem", location=room, tags=["thing"])
        GameObject("red rock", location=room, tags=["thing"])
        alice = GameObject("Alice", location=room, tags=["player"])

        with pytest.raises(AmbiguousMatchError):
            find_object(make_ctx(alice), "red")

    def test_find_exit_prefix_but_no_substring(self):
        room = GameObject("Room", tags=["room"])
        north = GameObject("north", location=room, tags=["exit"])
        alice = GameObject("Alice", location=room, tags=["player"])
        ctx = make_ctx(alice)

        assert find_exit(ctx, "nor") is north
        assert find_exit(ctx, "ort") is None  # substring disabled for exits

    def test_find_object_global_partial(self):
        promenade = GameObject("Station Promenade", tags=["room"])
        cantina = GameObject("The Void's Edge Cantina", tags=["room"])
        alice = GameObject("Alice", tags=["player"])
        ctx = make_ctx(alice, persistence=MockPersistence(promenade, cantina, alice))

        assert find_object_global(ctx, "Promenade") is promenade
        assert find_object_global(ctx, "cantina") is cantina

    @pytest.mark.asyncio
    async def test_dispatcher_renders_ambiguity(self):
        room = GameObject("Room", tags=["room"])
        GameObject("red gem", location=room, tags=["thing"])
        GameObject("red rock", location=room, tags=["thing"])
        alice = GameObject("Alice", location=room, tags=["player"])

        sess = Session(protocol="test", address="127.0.0.1")
        sess.link_player(alice)
        dispatcher = CommandDispatcher()

        from realm.commands.builtin.look import cmd_look
        dispatcher.register("look", cmd_look)

        await dispatcher.dispatch(sess, "look red")

        out = []
        while not sess._output_queue.empty():
            out.append(sess._output_queue.get_nowait())
        text = "\n".join(out)
        assert "Which 'red' do you mean?" in text
        assert "red gem-1" in text
        assert "red rock-2" in text

    @pytest.mark.asyncio
    async def test_pick_syntax_resolves_ambiguity(self):
        from realm.commands.builtin.inventory import cmd_get

        room = GameObject("Room", tags=["room"])
        gem1 = GameObject("gem", location=room, tags=["thing"])
        gem2 = GameObject("gem", location=room, tags=["thing"])
        alice = GameObject("Alice", location=room, tags=["player"])
        ctx = make_ctx(alice)
        ctx.args = "gem-2"

        await cmd_get(ctx)

        assert gem2.location is alice
        assert gem1.location is room
