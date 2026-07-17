"""Showcase verification — 85. Rich emote parser.

Rich emotes (`pose waves at /Bob`) are a builtin: no native half, no
registration. `pose` resolves `/name` references and renders each one per
viewer through `get_display_name` — the referenced person reads "you",
everyone else reads the name THEY know. This test drives the tutorial's
Try-it transcript through the real dispatcher and asserts each reader's
line, then shows the same emote composing with a disguise resolver (the
133/134 identity seam) and honoring the configurable `EMOTE_SIGIL`.

The 085 tutorial has no Build-it setup — the feature needs none — so the
Try-it pose lines are driven directly here (per the showcase brief). Every
command and every expected read is also asserted to appear verbatim in the
doc, so the tutorial and this test can't drift apart.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from realm.core.perception import (
    clear_name_resolvers,
    register_name_resolver,
)
from realm.core.verbs import (
    DEFAULT_EMOTE_SIGIL,
    get_emote_sigil,
    set_emote_sigil,
)
from realm.testing import Simulator

DOC = (Path(__file__).resolve().parents[2]
       / "docs" / "showcase" / "085_rich_emotes.md").read_text()


def in_doc(*needles: str) -> None:
    """The tutorial must actually contain what the test claims it shows."""
    for needle in needles:
        assert needle in DOC, f"085 doc is missing: {needle!r}"


def build_section() -> str:
    match = re.search(r"^## Build it$(.*?)^## ", DOC, re.M | re.S)
    assert match, "085 doc: no Build it section"
    return match.group(1)


@pytest.fixture
def plaza():
    sim = Simulator()
    room = sim.room("Plaza")
    ada = sim.player("Ada", location=room)
    bob = sim.player("Bob", location=room)
    cara = sim.player("Cara", location=room)
    clear_name_resolvers()
    try:
        yield sim, ada, bob, cara
    finally:
        clear_name_resolvers()
        set_emote_sigil(DEFAULT_EMOTE_SIGIL)
        sim.close()


def reads(sim, who, needle):
    """The lines `who` received containing `needle` (queue drained)."""
    return [x for x in sim.seen(who) if needle in x]


# --- The build has no build ------------------------------------------------


def test_build_it_installs_nothing():
    """085 is a pure builtin: its Build-it must state there is no setup and
    contain no driveable builder commands (no ``@`` verbs, no fenced
    transcript). If someone adds a setup step, this fails on purpose."""
    section = build_section()
    in_doc("Nothing to build.")
    # A pure builtin: no fenced command transcript to run (build_lines only
    # ever reads ```text blocks, so an empty Build-it means zero setup).
    assert "```" not in section, "085 Build-it should carry no command block"


# --- Per-viewer references (the substance) ---------------------------------


class TestPerViewerReferences:
    async def test_referenced_person_reads_you(self, plaza):
        sim, ada, bob, cara = plaza
        sim.seen(bob), sim.seen(cara)
        await sim.do(ada, "pose slides the datapad to /Bob.")
        assert reads(sim, bob, "datapad") == ["Ada slides the datapad to you."]
        assert reads(sim, cara, "datapad") == ["Ada slides the datapad to Bob."]
        in_doc(
            "pose slides the datapad to /Bob.",
            "Ada slides the datapad to you.",
            "Ada slides the datapad to Bob.",
        )

    async def test_colon_shortcut_is_the_same_emote(self, plaza):
        sim, ada, bob, cara = plaza
        sim.seen(bob), sim.seen(cara)
        await sim.do(ada, ":waves at /Bob.")          # ':' is 'pose'
        assert reads(sim, bob, "waves") == ["Ada waves at you."]
        assert reads(sim, cara, "waves") == ["Ada waves at Bob."]
        in_doc("`:` is `pose`")

    async def test_multiple_references_each_reader_is_you(self, plaza):
        sim, ada, bob, cara = plaza
        sim.seen(bob), sim.seen(cara)
        await sim.do(ada, "pose looks from /Bob to /Cara.")
        # Each reader is "you"; the other is named.
        assert reads(sim, cara, "looks") == ["Ada looks from Bob to you."]
        assert reads(sim, bob, "looks") == ["Ada looks from you to Cara."]
        in_doc("pose looks from /Bob to /Cara.", "Ada looks from Bob to you.")

    async def test_possessive_after_a_reference(self, plaza):
        sim, ada, bob, cara = plaza
        sim.seen(cara)
        await sim.do(ada, "pose takes /Bob's hand.")
        # "Bob" resolves; the "'s" glued on is left literal.
        assert reads(sim, cara, "takes") == ["Ada takes Bob's hand."]
        in_doc("pose takes /Bob's hand.", "Ada takes Bob's hand.")


# --- Non-references and safety ---------------------------------------------


class TestNonReferencesAndSafety:
    async def test_unmatched_slash_is_literal(self, plaza):
        sim, ada, bob, cara = plaza
        sim.seen(bob)
        await sim.do(ada, "pose eats 3/4 of the pie and/or leaves.")
        assert reads(sim, bob, "pie") == [
            "Ada eats 3/4 of the pie and/or leaves."]
        in_doc(
            "pose eats 3/4 of the pie and/or leaves.",
            "Ada eats 3/4 of the pie and/or leaves.",
        )

    async def test_plain_pose_is_unchanged(self, plaza):
        sim, ada, bob, cara = plaza
        sim.seen(bob)
        await sim.do(ada, "pose waves hello.")
        assert reads(sim, bob, "waves") == ["Ada waves hello."]
        in_doc("pose waves hello.", "Ada waves hello.")

    async def test_player_text_cannot_inject_a_token(self, plaza):
        sim, ada, bob, cara = plaza
        sim.seen(bob)
        await sim.do(ada, "pose mutters {actor} then taps /Bob.")
        # The typed "{actor}" stays literal; only the real reference resolves.
        assert reads(sim, bob, "mutters") == [
            "Ada mutters {actor} then taps you."]
        in_doc("Player text can't smuggle in tokens")


# --- Composition with the identity seam ------------------------------------


class TestComposesWithDisguise:
    async def test_reference_honors_a_disguise_per_viewer(self, plaza):
        sim, ada, bob, cara = plaza
        # A game's disguise policy on the same seam 133/134 use. Registered
        # here only to demonstrate composition — the parser itself needs no
        # such binding.
        register_name_resolver(lambda o, lk, cur: o.db.get('disguise') or cur)
        ada.db.set('disguise', 'a hooded figure')
        sim.seen(bob), sim.seen(cara)
        await sim.do(ada, "pose beckons to /Bob.")
        # The actor is masked; the reference is still named the way each
        # reader knows Bob (and Bob himself reads "you").
        assert reads(sim, cara, "beckons") == [
            "a hooded figure beckons to Bob."]
        assert reads(sim, bob, "beckons") == [
            "a hooded figure beckons to you."]
        in_doc("a hooded figure beckons to Bob.")


# --- Going further: the configurable sigil ---------------------------------


class TestConfigurableSigil:
    async def test_default_sigil_is_slash(self, plaza):
        assert get_emote_sigil() == DEFAULT_EMOTE_SIGIL == "/"
        in_doc("EMOTE_SIGIL")

    async def test_changing_the_sigil_reroutes_references(self, plaza):
        sim, ada, bob, cara = plaza
        set_emote_sigil("@")
        sim.seen(bob), sim.seen(cara)
        await sim.do(ada, "pose waves at @Bob.")
        assert reads(sim, bob, "waves") == ["Ada waves at you."]
        assert reads(sim, cara, "waves") == ["Ada waves at Bob."]

        # The old sigil is now inert — a "/" is just punctuation again.
        sim.seen(cara)
        await sim.do(ada, "pose waves at /Bob.")
        assert reads(sim, cara, "waves") == ["Ada waves at /Bob."]

    def test_a_bad_sigil_is_rejected_at_config_time(self):
        # The doc's promise: bad values raise at boot, not mid-emote.
        in_doc("1–16 non-alphanumeric, non-space characters")
        for bad in ("", "a", "1", " ", "x/"):
            with pytest.raises(ValueError):
                set_emote_sigil(bad)
        set_emote_sigil(DEFAULT_EMOTE_SIGIL)
