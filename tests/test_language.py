"""
Tests for display-time articles/plurals (realm.core.language), room
display grouping (realm.core.render), and their matcher integration.

Contract: names are bare nouns; articles and plurals are computed at
render/match time (never stored), with db.article / db.plural overrides
for English's exceptions. Grouping is presentation-only and O(n).
"""

from __future__ import annotations

import pytest

from realm.core.language import (
    article_for,
    numbered_name,
    plural_name,
    pluralize,
    singular_name,
)
from realm.core.objects import GameObject
from realm.core.propagation import reset_engine
from realm.core.render import (
    default_group_formatter,
    group_contents,
    render_room,
    set_group_formatter,
)
from realm.core.search import match_objects, match_one


@pytest.fixture(autouse=True)
def clean_state():
    reset_engine()
    yield
    reset_engine()
    set_group_formatter(None)


# --- Articles ----------------------------------------------------------------


class TestArticles:

    def test_consonant_gets_a(self):
        assert article_for("sword") == "a"

    def test_vowel_gets_an(self):
        assert article_for("apple") == "an"

    def test_proper_noun_gets_none(self):
        assert article_for("Zeke the Bartender") == ""

    def test_singular_name_applies_article(self):
        assert singular_name(GameObject("apple")) == "an apple"
        assert singular_name(GameObject("sword")) == "a sword"
        assert singular_name(GameObject("Zeke the Bartender")) == "Zeke the Bartender"

    def test_article_override(self):
        sand = GameObject("sand")
        sand.db.article = "some"
        assert singular_name(sand) == "some sand"

    def test_article_override_empty_forces_none(self):
        boots = GameObject("boots of speed")
        boots.db.article = ""
        assert singular_name(boots) == "boots of speed"

    def test_article_override_for_english_warts(self):
        hour = GameObject("hourglass")  # 'an' by vowel rule would be wrong
        hour.db.article = "an"  # builder decides; heuristic said "a"? no — h
        assert singular_name(hour) == "an hourglass"


# --- Plurals -----------------------------------------------------------------


class TestPlurals:

    def test_simple_s(self):
        assert pluralize("apple") == "apples"

    def test_es_endings(self):
        assert pluralize("box") == "boxes"
        assert pluralize("torch") == "torches"

    def test_consonant_y_to_ies(self):
        assert pluralize("berry") == "berries"

    def test_vowel_y_plain_s(self):
        assert pluralize("key") == "keys"

    def test_f_to_ves(self):
        assert pluralize("knife") == "knives"
        assert pluralize("wolf") == "wolves"

    def test_irregular(self):
        assert pluralize("staff") == "staves"
        assert pluralize("fish") == "fish"

    def test_last_word_only(self):
        assert pluralize("energy cell") == "energy cells"
        assert pluralize("quarterstaff") == "quarterstaffs"  # ff guard

    def test_plural_override(self):
        obj = GameObject("beef jerky")
        obj.db.plural = "strips of beef jerky"
        assert plural_name(obj) == "strips of beef jerky"

    def test_numbered_name(self):
        apple = GameObject("apple")
        assert numbered_name(apple, 1) == "an apple"
        assert numbered_name(apple, 3) == "3 apples"


# --- Display grouping ---------------------------------------------------------


class TestGrouping:

    def test_identical_things_group(self):
        apples = [GameObject("apple") for _ in range(3)]
        sword = GameObject("rusty sword")
        groups = group_contents(apples + [sword])
        assert [(rep.name, n) for rep, n in groups] == [("apple", 3), ("rusty sword", 1)]

    def test_first_seen_order_preserved(self):
        a1, b, a2 = GameObject("apple"), GameObject("box"), GameObject("apple")
        groups = group_contents([a1, b, a2])
        assert [(rep.name, n) for rep, n in groups] == [("apple", 2), ("box", 1)]

    def test_no_group_tag_stands_alone(self):
        a1, a2 = GameObject("apple"), GameObject("apple")
        a2.add_tag("no_group")
        groups = group_contents([a1, a2])
        assert [(rep.name, n) for rep, n in groups] == [("apple", 1), ("apple", 1)]

    def test_render_room_shows_grouped_line(self):
        room = GameObject("Orchard", tags=["room"])
        for _ in range(3):
            GameObject("apple", location=room, tags=["thing"])
        GameObject("rusty sword", location=room, tags=["thing"])
        viewer = GameObject("Alice", location=room, tags=["player"])

        text = render_room(room, viewer)

        assert "  3 apples" in text
        assert "  a rusty sword" in text
        assert text.count("apple") == 1  # one grouped line, not three

    def test_render_room_players_not_grouped_or_articled(self):
        room = GameObject("Plaza", tags=["room"])
        viewer = GameObject("Alice", location=room, tags=["player"])
        GameObject("Bob", location=room, tags=["player"])

        text = render_room(room, viewer)

        assert "  Bob" in text
        assert "a Bob" not in text

    def test_group_formatter_hook(self):
        room = GameObject("Orchard", tags=["room"])
        for _ in range(3):
            GameObject("apple", location=room, tags=["thing"])
        viewer = GameObject("Alice", location=room, tags=["player"])

        set_group_formatter(lambda obj, n: f"{obj.name} (x{n})" if n > 1 else obj.name)
        try:
            assert "  apple (x3)" in render_room(room, viewer)
        finally:
            set_group_formatter(None)
        assert "  3 apples" in render_room(room, viewer)

    def test_default_formatter_uses_articles(self):
        assert default_group_formatter(GameObject("apple"), 1) == "an apple"
        assert default_group_formatter(GameObject("apple"), 4) == "4 apples"


# --- Matcher integration -------------------------------------------------------


class TestMatcherLanguage:

    def test_plural_query_targets_singular_object(self):
        apple = GameObject("apple")
        result = match_objects("apples", [apple])
        assert result.matches == [apple]

    def test_article_in_query_is_forgiven(self):
        apple = GameObject("apple")
        assert match_one("an apple", [apple]) is apple
        assert match_one("the apple", [apple]) is apple

    def test_article_strip_never_beats_real_name(self):
        # An object actually named "the end" must match exactly first.
        the_end = GameObject("The End")
        end = GameObject("end table")
        assert match_one("the end", [the_end, end]) is the_end

    def test_plural_override_is_targetable(self):
        staff = GameObject("staff")
        assert match_one("staves", [staff]) is staff


# --- Message tokens ------------------------------------------------------------


class TestMessageTokens:
    """format_message article tokens: {x}, {x:a}, {x:the}."""

    def _action(self, actor=None, target=None, tool=None):
        from realm.core.propagation import Action
        return Action(actor=actor, target=target, tool=tool, action_type="test:token")

    def test_bare_indefinite_and_definite(self):
        apple = GameObject("apple")
        action = self._action(actor=GameObject("Alice"), target=apple)
        assert action.format_message("{target}") == "apple"
        assert action.format_message("You pick up {target:a}.") == "You pick up an apple."
        assert action.format_message("You eye {target:the}.") == "You eye the apple."

    def test_proper_noun_skips_articles(self):
        zeke = GameObject("Zeke the Bartender")
        action = self._action(actor=GameObject("Alice"), target=zeke)
        assert action.format_message("{target:a}") == "Zeke the Bartender"
        assert action.format_message("{target:the}") == "Zeke the Bartender"

    def test_article_override_flows_through(self):
        sand = GameObject("sand")
        sand.db.article = "some"
        action = self._action(actor=GameObject("Alice"), target=sand)
        assert action.format_message("You scoop up {target:a}.") == "You scoop up some sand."

    def test_tool_tokens(self):
        coin = GameObject("coin")
        bob = GameObject("Bob")
        action = self._action(actor=GameObject("Alice"), target=bob, tool=coin)
        assert (
            action.format_message("{actor} gives {tool:a} to {target}.")
            == "Alice gives a coin to Bob."
        )

    def test_missing_participants(self):
        action = self._action()
        assert action.format_message("{actor} pokes {target:a}.") == "Someone pokes something."
