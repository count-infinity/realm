"""Recognition and disguise: the name a looker sees is overridable.

`get_display_name(looker)` -> `perceived_name` is the documented seam for
"who does this person appear to be?" It now runs a registry of resolvers
(`register_name_resolver`), so recognition (a stranger reads as "a tall
woman" until introduced) and disguise (an assumed identity) are a few
lines of game code instead of a GameObject subclass.

The load-bearing property is *consistency*: a disguise must cover every
place a player sees the name in play — speech, the room's "Players here"
list, and looking straight at them — but NOT introspection (`@examine`,
owner readouts, logs), which must show the truth or a disguise becomes a
grief tool. These tests pin both halves.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.core.perception import (
    clear_name_resolvers,
    register_name_resolver,
)
from realm.testing import Simulator


@pytest.fixture
def world():
    sim = Simulator()
    room = sim.room("Plaza")
    alice = sim.player("Alice", location=room)
    bob = sim.player("Bob", location=room)
    clear_name_resolvers()
    try:
        yield SimpleNamespace(sim=sim, room=room, alice=alice, bob=bob)
    finally:
        clear_name_resolvers()
        sim.close()


def heard(sim, who, needle):
    return [line for line in sim.seen(who) if needle in line]


# --- recognition: sdesc until introduced -----------------------------------

def recognition_resolver(obj, looker, current):
    """Strangers read by their `sdesc`; once `looker` has been introduced
    (`recognizes` holds their id) the real name returns."""
    if looker is None or looker is obj:
        return current
    sdesc = obj.db.get('sdesc')
    if not sdesc:
        return current
    if looker.id in (obj.db.get('recognized_by') or []):
        return current
    return sdesc


@pytest.mark.asyncio
class TestRecognition:
    async def test_stranger_reads_as_sdesc_in_speech(self, world):
        w = world
        w.alice.db.set('sdesc', 'a tall woman')
        register_name_resolver(recognition_resolver)
        w.sim.seen(w.bob)

        await w.sim.do(w.alice, "say well met")

        assert heard(w.sim, w.bob, "well met") == [
            'a tall woman says, "well met"']

    async def test_stranger_reads_as_sdesc_in_the_room_listing(self, world):
        w = world
        w.alice.db.set('sdesc', 'a tall woman')
        register_name_resolver(recognition_resolver)

        await w.sim.do(w.bob, "look")
        out = "\n".join(w.sim.seen(w.bob))

        assert "a tall woman" in out
        assert "Alice" not in out          # the real name is not leaked

    async def test_stranger_reads_as_sdesc_when_looked_at(self, world):
        w = world
        w.alice.db.set('sdesc', 'a tall woman')
        register_name_resolver(recognition_resolver)

        await w.sim.do(w.bob, "look Alice")
        out = "\n".join(w.sim.seen(w.bob))

        assert "a tall woman" in out

    async def test_introduction_reveals_the_real_name(self, world):
        w = world
        w.alice.db.set('sdesc', 'a tall woman')
        register_name_resolver(recognition_resolver)

        # Bob is introduced to Alice.
        w.alice.db.set('recognized_by', [w.bob.id])
        w.sim.seen(w.bob)
        await w.sim.do(w.alice, "say now you know me")

        assert heard(w.sim, w.bob, "know me") == [
            'Alice says, "now you know me"']

    async def test_you_always_know_yourself(self, world):
        w = world
        w.alice.db.set('sdesc', 'a tall woman')
        register_name_resolver(recognition_resolver)
        w.sim.seen(w.alice)

        await w.sim.do(w.alice, "say testing")

        # Alice's own actor-line names her, not her sdesc.
        assert heard(w.sim, w.alice, "testing") == ['You say, "testing"']


# --- disguise, and the voice that comes with it ----------------------------

def disguise_resolver(obj, looker, current):
    """A disguised object reads by its assumed name to everyone but
    itself (a real game would roll a see-through contest here)."""
    if looker is obj:
        return current
    return obj.db.get('disguise') or current


@pytest.mark.asyncio
class TestDisguise:
    async def test_disguise_covers_the_room_listing(self, world):
        w = world
        w.alice.db.set('disguise', 'a hooded figure')
        register_name_resolver(disguise_resolver)

        await w.sim.do(w.bob, "look")
        out = "\n".join(w.sim.seen(w.bob))

        assert "a hooded figure" in out
        assert "Alice" not in out

    async def test_disguise_covers_the_voice_for_free(self, world):
        """Item 84: speech attribution flows through the same seam, so a
        disguise silences the real name without any speech-specific code."""
        w = world
        w.alice.db.set('disguise', 'a hooded figure')
        register_name_resolver(disguise_resolver)
        w.sim.seen(w.bob)

        await w.sim.do(w.alice, "say you don't know me")

        assert heard(w.sim, w.bob, "know me") == [
            'a hooded figure says, "you don\'t know me"']


# --- the boundary: introspection shows the truth ---------------------------

@pytest.mark.asyncio
class TestExamineShowsTruth:
    async def test_examine_ignores_the_disguise(self, world):
        w = world
        w.bob.add_tag('builder')
        w.alice.db.set('disguise', 'a hooded figure')
        register_name_resolver(disguise_resolver)

        await w.sim.do(w.bob, "examine Alice")
        out = "\n".join(w.sim.seen(w.bob))

        # A builder examining sees the real object, disguise or not.
        assert "Alice" in out


# --- mechanics: composition, no-op default, fail-open ----------------------

@pytest.mark.asyncio
class TestResolverMechanics:
    async def test_no_resolvers_is_identity(self, world):
        w = world
        w.sim.seen(w.bob)
        await w.sim.do(w.alice, "say plain")
        assert heard(w.sim, w.bob, "plain") == ['Alice says, "plain"']

    async def test_resolvers_compose_in_order(self, world):
        w = world
        register_name_resolver(lambda o, lk, cur: cur.upper() if lk else cur)
        register_name_resolver(lambda o, lk, cur: f"[{cur}]" if lk else cur)
        w.sim.seen(w.bob)

        await w.sim.do(w.alice, "say hi")

        assert heard(w.sim, w.bob, "hi") == ['[ALICE] says, "hi"']

    async def test_a_broken_resolver_does_not_blank_the_name(self, world):
        w = world

        def boom(obj, looker, current):
            raise RuntimeError("resolver broke")

        register_name_resolver(boom)
        register_name_resolver(lambda o, lk, cur: cur + "?" if lk else cur)
        w.sim.seen(w.bob)

        await w.sim.do(w.alice, "say still named")

        # The broken one is skipped; the good one still runs.
        assert heard(w.sim, w.bob, "still named") == [
            'Alice? says, "still named"']

    async def test_unseen_actor_is_someone_regardless_of_resolvers(self, world):
        """Perception wins first: you can't be recognised or disguised as
        anything if the looker can't see you at all."""
        w = world
        w.alice.db.set('sdesc', 'a tall woman')
        w.alice.add_tag('hidden')          # can_see -> False
        register_name_resolver(recognition_resolver)
        w.sim.seen(w.bob)

        await w.sim.do(w.alice, "say from the shadows")

        assert heard(w.sim, w.bob, "shadows") == [
            'Someone says, "from the shadows"']
