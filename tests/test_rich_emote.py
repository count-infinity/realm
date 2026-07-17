"""Rich emotes: `pose waves at /Bob` names Bob per viewer.

A plain pose bakes one string for everyone. A rich emote references
people with a sigil (`/`, configurable) and each reference renders
through `get_display_name(looker)` — so the referenced person reads
"you", a viewer who knows a disguised actor by their fake name reads
that, and a stranger reads an sdesc. It is the identity seam pointed at
emotes.

Non-references are left untouched (a stray slash, `3/4`), and player text
can't inject participant tokens — the body still rides the `{speech}`
token.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.core.perception import (
    clear_name_resolvers,
    register_name_resolver,
)
from realm.core.verbs import (
    DEFAULT_EMOTE_SIGIL,
    get_emote_sigil,
    parse_emote_refs,
    set_emote_sigil,
)
from realm.testing import Simulator


@pytest.fixture
def world():
    sim = Simulator()
    room = sim.room("Plaza")
    ada = sim.player("Ada", location=room)
    bob = sim.player("Bob", location=room)
    cara = sim.player("Cara", location=room)
    clear_name_resolvers()
    try:
        yield SimpleNamespace(sim=sim, room=room, ada=ada, bob=bob, cara=cara)
    finally:
        clear_name_resolvers()
        set_emote_sigil(DEFAULT_EMOTE_SIGIL)
        sim.close()


def line(sim, who, needle):
    return [x for x in sim.seen(who) if needle in x]


@pytest.mark.asyncio
class TestPerViewerReferences:
    async def test_referenced_person_reads_you(self, world):
        w = world
        w.sim.seen(w.bob), w.sim.seen(w.cara)
        await w.sim.do(w.ada, "pose slides the datapad to /Bob.")
        assert line(w.sim, w.bob, "datapad") == ["Ada slides the datapad to you."]
        assert line(w.sim, w.cara, "datapad") == ["Ada slides the datapad to Bob."]

    async def test_reference_honors_a_disguise_per_viewer(self, world):
        w = world
        register_name_resolver(
            lambda o, lk, cur: o.db.get('disguise') or cur)
        w.ada.db.set('disguise', 'a hooded figure')
        w.sim.seen(w.cara)
        await w.sim.do(w.ada, "pose beckons to /Bob.")
        # Cara sees the disguised actor AND knows Bob.
        assert line(w.sim, w.cara, "beckons") == [
            "a hooded figure beckons to Bob."]

    async def test_multiple_references(self, world):
        w = world
        w.sim.seen(w.cara)
        await w.sim.do(w.ada, "pose looks from /Bob to /Cara.")
        # Cara reads herself as "you", Bob by name.
        assert line(w.sim, w.cara, "looks") == ["Ada looks from Bob to you."]


@pytest.mark.asyncio
class TestNonReferencesAndSafety:
    async def test_unmatched_slash_is_literal(self, world):
        w = world
        w.sim.seen(w.bob)
        await w.sim.do(w.ada, "pose eats 3/4 of the pie and/or leaves.")
        assert line(w.sim, w.bob, "pie") == [
            "Ada eats 3/4 of the pie and/or leaves."]

    async def test_plain_pose_is_unchanged(self, world):
        w = world
        w.sim.seen(w.bob)
        await w.sim.do(w.ada, "pose waves hello.")
        assert line(w.sim, w.bob, "waves") == ["Ada waves hello."]

    async def test_participant_tokens_stay_literal(self, world):
        w = world
        w.sim.seen(w.bob)
        await w.sim.do(w.ada, "pose mutters {actor} then taps /Bob.")
        assert line(w.sim, w.bob, "mutters") == [
            "Ada mutters {actor} then taps you."]

    async def test_possessive_after_a_reference(self, world):
        w = world
        w.sim.seen(w.cara)
        await w.sim.do(w.ada, "pose takes /Bob's hand.")
        # "Bob" resolves, the "'s" is left literal.
        assert line(w.sim, w.cara, "takes") == ["Ada takes Bob's hand."]


class TestSigilConfig:
    def teardown_method(self):
        set_emote_sigil(DEFAULT_EMOTE_SIGIL)

    def test_default_is_slash(self):
        assert get_emote_sigil() == "/"

    def test_sigil_is_configurable(self):
        set_emote_sigil("@")
        assert get_emote_sigil() == "@"

    @pytest.mark.parametrize("bad", ["", "a", "1", " ", "x/", "/" * 17])
    def test_bad_sigils_rejected_at_config_time(self, bad):
        with pytest.raises(ValueError):
            set_emote_sigil(bad)

    def test_parse_uses_the_configured_sigil(self):
        # A tiny standalone object graph — parse_emote_refs needs only
        # .location and .contents.
        from realm.core.objects import GameObject
        room = GameObject("Room", tags=['room'])
        ada = GameObject("Ada", location=room)
        bob = GameObject("Bob", location=room)
        room.contents  # ensure membership realised

        set_emote_sigil("@")
        body, refs = parse_emote_refs(ada, "waves at @Bob")
        assert refs == [bob]
        assert "Bob" not in body            # replaced by a marker
        # The old sigil is now inert.
        body2, refs2 = parse_emote_refs(ada, "waves at /Bob")
        assert refs2 == []
        assert body2 == "waves at /Bob"
