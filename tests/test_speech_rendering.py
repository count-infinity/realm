"""How speech reaches each listener — pinned, then made transformable.

The whole speech family (say/pose/emit/whisper/shout/ooc) is rendered
**per recipient** already: `deliver_messages` calls
`action.format_message(msg, looker=recipient)` for every listener
individually, so perception rules apply per viewer.

What was missing is any way to touch the *spoken body* per listener —
because the body was f-string-baked into the template at construction:

    action.add_message("room", f'{{actor}} says, "{message}"')

That blocked languages (garble per listener), overheard whispers
(fragments per bystander) and intoxication (slur). It also meant player
text sat inside a token-substituted string, so `say meet {actor}` came
out as "meet Alice" — a small injection.

The body is now a `{speech}` token resolved LAST, after the participant
tokens, which fixes the injection by construction and gives per-listener
transforms a place to stand.

The first class here is characterization: it pins the exact strings
players see, so the refactor is provably output-identical.

WHAT THIS DOES NOT FINISH — item 80, overheard whispers. A renderer can
tell the addressee from a bystander, but a whisper's ROOM line carries no
body to redact:

    add_message("room", "{actor} whispers something to {target}.")

Giving it a `{speech}` token would make every whisper public by default —
audible to the whole room unless a redacting renderer happened to be
registered. That is a fiction-and-privacy decision (does the engine ship a
default redactor, or does the game?), not something to slip in silently
behind a refactor. Filed rather than guessed at.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.testing import Simulator


@pytest.fixture
def world():
    sim = Simulator()
    room = sim.room("Hall")
    alice = sim.player("Alice", location=room)
    bob = sim.player("Bob", location=room)
    try:
        yield SimpleNamespace(sim=sim, room=room, alice=alice, bob=bob)
    finally:
        sim.close()


def heard(sim, who, needle: str) -> list[str]:
    return [line for line in sim.seen(who) if needle in line]


@pytest.mark.asyncio
class TestRenderingIsUnchanged:
    """Characterization. These strings are what players read today and
    must read identically after the body became a token."""

    async def test_say(self, world):
        w = world
        w.sim.seen(w.alice), w.sim.seen(w.bob)
        await w.sim.do(w.alice, "say Meet me at the jetty.")
        assert heard(w.sim, w.alice, "say") == ['You say, "Meet me at the jetty."']
        assert heard(w.sim, w.bob, "says") == ['Alice says, "Meet me at the jetty."']

    async def test_pose(self, world):
        w = world
        w.sim.seen(w.bob)
        await w.sim.do(w.alice, "pose waves hello.")
        assert heard(w.sim, w.bob, "waves") == ["Alice waves hello."]

    async def test_whisper_actor_target_and_bystander(self, world):
        w = world
        cara = w.sim.player("Cara", location=w.room)
        w.sim.seen(w.alice), w.sim.seen(w.bob), w.sim.seen(cara)
        await w.sim.do(w.alice, "whisper Bob = the vault is open")
        assert heard(w.sim, w.alice, "whisper") == [
            'You whisper to Bob, "the vault is open"']
        assert heard(w.sim, w.bob, "whispers") == [
            'Alice whispers, "the vault is open"']
        # The bystander gets the generic line — no body at all. This is
        # what item 80 (overheard whispers) wants to make leaky.
        assert heard(w.sim, cara, "whispers") == [
            "Alice whispers something to Bob."]

    async def test_shout(self, world):
        w = world
        w.sim.seen(w.bob)
        await w.sim.do(w.alice, "shout fire in the hold")
        assert heard(w.sim, w.bob, "shouts") == ['Alice shouts, "fire in the hold"']


@pytest.mark.asyncio
class TestPlayerTextIsNotSubstituted:
    """The injection the old shape allowed: the body was baked INTO the
    template, so a player typing a token got it substituted. Resolving
    `{speech}` last makes player text inert by construction."""

    async def test_tokens_in_speech_stay_literal(self, world):
        w = world
        w.sim.seen(w.bob)
        await w.sim.do(w.alice, "say meet {target} at {actor} o'clock")
        assert heard(w.sim, w.bob, "says") == [
            'Alice says, "meet {target} at {actor} o\'clock"']

    async def test_tokens_in_a_pose_stay_literal(self, world):
        w = world
        w.sim.seen(w.bob)
        await w.sim.do(w.alice, "pose points at {target}.")
        assert heard(w.sim, w.bob, "points") == ["Alice points at {target}."]

    async def test_braces_do_not_break_rendering(self, world):
        """A body full of braces must survive — substitution is
        replace-based, not str.format."""
        w = world
        w.sim.seen(w.bob)
        await w.sim.do(w.alice, "say use {'a': 1} for the dict")
        assert heard(w.sim, w.bob, "says") == [
            'Alice says, "use {\'a\': 1} for the dict"']

    async def test_ooc_and_semipose_are_inert_too(self, world):
        w = world
        w.sim.seen(w.bob)
        await w.sim.do(w.alice, "ooc brb, {actor} calling")
        await w.sim.do(w.alice, ";'s hat is {target}-shaped")
        # seen() DRAINS the queue — capture once, then filter.
        lines = w.sim.seen(w.bob)
        assert [x for x in lines if "OOC" in x] == [
            "[OOC] Alice: brb, {actor} calling"]
        assert [x for x in lines if "hat" in x] == [
            "Alice's hat is {target}-shaped"]


@pytest.fixture
def renderers():
    """Registered speech transforms, cleared after each test."""
    from realm.core.propagation import clear_speech_renderers
    clear_speech_renderers()
    yield
    clear_speech_renderers()


@pytest.mark.asyncio
class TestPerListenerTransforms:
    """The point of the exercise: the same sentence can now reach two
    listeners differently. These are the three blocked checklist items,
    each shown to be expressible in a handful of lines."""

    async def test_languages_garble_per_listener(self, world, renderers):
        """Item 79. Bob speaks Trade; Cara doesn't."""
        from realm.core.propagation import register_speech_renderer

        w = world
        cara = w.sim.player("Cara", location=w.room)
        w.alice.db.set('speaking', 'trade')
        w.bob.db.set('languages', ['trade'])
        cara.db.set('languages', [])

        def garble(body, action, looker):
            if action.action_type != "event:speech":
                return body
            tongue = (action.actor.db.get('speaking')
                      if action.actor is not None else None)
            if not tongue or looker is None:
                return body
            if tongue in (looker.db.get('languages') or []):
                return body
            return "<something in Trade>"

        register_speech_renderer(garble)
        w.sim.seen(w.bob), w.sim.seen(cara)
        await w.sim.do(w.alice, "say the vault is open")

        assert heard(w.sim, w.bob, "says") == ['Alice says, "the vault is open"']
        assert heard(w.sim, cara, "says") == ['Alice says, "<something in Trade>"']

    async def test_a_renderer_can_tell_addressee_from_bystander(self, world,
                                                                renderers):
        """Groundwork for item 80 — but NOT item 80 itself.

        A renderer can distinguish the addressee from a bystander (via
        `looker is action.target`) and rewrite the body accordingly. What
        it CANNOT yet do is leak fragments to the room, because the
        whisper's room line carries no body at all:

            add_message("room", "{actor} whispers something to {target}.")

        There is no `{speech}` there to redact, so overheard-whisper
        fragments need a further decision — see the module docstring.
        This pins the half that works: the addressee's copy is
        transformable and bystanders are identifiable.
        """
        from realm.core.propagation import register_speech_renderer

        w = world
        cara = w.sim.player("Cara", location=w.room)
        seen_lookers = []

        def note(body, action, looker):
            if action.action_type == "event:whisper":
                seen_lookers.append(
                    "addressee" if looker is action.target else "other")
                if looker is action.target:
                    return body.upper()
            return body

        register_speech_renderer(note)
        w.sim.seen(w.bob), w.sim.seen(cara)
        await w.sim.do(w.alice, "whisper Bob = the vault is open")

        # The addressee's body went through the renderer...
        assert heard(w.sim, w.bob, "whispers") == [
            'Alice whispers, "THE VAULT IS OPEN"']
        # ...and Cara still gets the bodyless room line, untouched.
        assert heard(w.sim, cara, "whispers") == [
            "Alice whispers something to Bob."]
        assert "addressee" in seen_lookers

    async def test_drink_slurs_for_everyone(self, world, renderers):
        """Item 139. Not per-listener — the same seam still serves."""
        from realm.core.propagation import register_speech_renderer

        w = world
        w.alice.db.set('drunk', 1)

        def slur(body, action, looker):
            if action.actor is not None and action.actor.db.get('drunk'):
                return body.replace("s", "sh")
            return body

        register_speech_renderer(slur)
        w.sim.seen(w.bob)
        await w.sim.do(w.alice, "say this is fine")

        # Note what is NOT slurred: the narration. A renderer touches the
        # spoken words only, never the frame around them — the room still
        # reads "Alice says," in the game's own voice. That falls out of
        # the body being a token rather than the whole line.
        assert heard(w.sim, w.bob, "says") == ['Alice says, "thish ish fine"']

    async def test_renderers_compose_in_order(self, world, renderers):
        """A drunk speaker of a foreign tongue slurs AND garbles: each
        renderer sees the previous one's output."""
        from realm.core.propagation import register_speech_renderer

        w = world
        register_speech_renderer(lambda b, a, lk: b.upper())
        register_speech_renderer(lambda b, a, lk: b + "!")
        w.sim.seen(w.bob)
        await w.sim.do(w.alice, "say hello")

        assert heard(w.sim, w.bob, "says") == ['Alice says, "HELLO!"']

    async def test_a_broken_renderer_does_not_eat_the_line(self, world, renderers):
        """Fail OPEN, loudly — the opposite of an on_check ward, and for a
        reason: a ward's job is to DENY, so "it errored" must not read as
        "it allowed". A renderer only rephrases; swallowing the sentence
        would be the worse failure."""
        from realm.core.propagation import register_speech_renderer

        w = world

        def boom(body, action, looker):
            raise RuntimeError("renderer is broken")

        register_speech_renderer(boom)
        register_speech_renderer(lambda b, a, lk: b + " (ok)")
        w.sim.seen(w.bob)
        await w.sim.do(w.alice, "say still here")

        # The broken one is skipped; the good one still runs.
        assert heard(w.sim, w.bob, "says") == ['Alice says, "still here (ok)"']
