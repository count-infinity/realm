"""Showcase verification — disguises (134) and voice disguise (84).

Two halves of concealment, riding two different mechanisms:

* **134** rides the ``register_name_resolver`` seam. A mask makes you READ
  as an assumed identity everywhere — the room list, ``look``, and (for
  free, since attribution is named through the same seam) speech. A
  ``check_roll`` see-through contest lets a keen watcher pierce it, after
  which THEY read the true name while others stay fooled. The native half
  is the resolver the doc shows, registered in the fixture below.

* **84** needs no seam at all. ``db.voice_as`` is a pure attribute
  convention the engine looks for when it names the ``{actor}`` of a
  *speech* action, so a modulator masks the voice while ``look`` still
  shows the real face. Nothing is registered.

The Build-it command lines are read straight from each tutorial's markdown
and driven through the real dispatcher (raw input in, session output out).
Study rolls are made deterministic by pinning ``roll`` to a fixed value.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from realm.core.perception import clear_name_resolvers, register_name_resolver
from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"
RED_FLAGS = ("Unknown command", "Script error", "Syntax error", "Traceback",
             "not defined", "refuses")


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


async def run_build(sim, builder, doc):
    for line in build_lines(doc):
        await sim.do(builder, line)
    out = "\n".join(sim.seen(builder))
    for flag in RED_FLAGS:
        assert flag not in out, f"{doc} build tripped {flag!r}:\n{out}"


def said(sim, who, needle):
    return [x for x in sim.seen(who) if needle in x]


def heard(sim, who):
    """Join everything a player has received into one drained blob."""
    return "\n".join(sim.seen(who))


# --- 134 disguises ---------------------------------------------------------


def _disguise_resolver(obj, looker, current):
    """The resolver the 134 tutorial shows, registered here so the test
    exercises the same policy the doc documents. Registered alone: to
    compose with 133, register recognition FIRST and this SECOND (the doc
    explains why order matters)."""
    disguise = obj.db.get('disguise')
    pierced = obj.db.get('pierced_by') or []
    if (disguise and looker is not None and looker is not obj
            and looker.id not in pierced):
        return disguise
    return current


@pytest.fixture
def greenroom():
    sim = Simulator()
    hall = sim.room("Hall")
    vale = sim.player("Vale", location=hall)
    vale.add_tag("admin")                # owns the wardrobe it @creates
    wynn = sim.player("Wynn", location=hall)
    clear_name_resolvers()
    register_name_resolver(_disguise_resolver)
    try:
        yield sim, vale, wynn
    finally:
        clear_name_resolvers()
        sim.close()


@pytest.mark.asyncio
class TestDisguises:
    async def test_masked_face_is_worn_and_heard(self, greenroom):
        sim, vale, wynn = greenroom
        await run_build(sim, vale, "134_disguises.md")
        room = vale.location
        wynn.location = room

        # Undisguised, Vale is Vale to Wynn.
        sim.seen(wynn)
        await sim.do(vale, "say Before.")
        assert said(sim, wynn, "Before") == ['Vale says, "Before."']

        # Vale dons a disguise.
        await sim.do(vale, "don a masked courier")

        # Wynn now HEARS the mask; the seam covered the voice for free.
        # Vale still hears her own true attribution.
        sim.seen(vale), sim.seen(wynn)
        await sim.do(vale, "say Package for you.")
        assert said(sim, wynn, "Package") == [
            'a masked courier says, "Package for you."']
        assert said(sim, vale, "Package") == ['You say, "Package for you."']

        # And Wynn SEES the mask in the room list, not Vale.
        sim.seen(wynn)
        await sim.do(wynn, "look")
        blob = heard(sim, wynn)
        assert "a masked courier" in blob
        assert "Vale" not in blob

        # Doff, and the face is Vale's again to everyone.
        await sim.do(vale, "doff")
        sim.seen(wynn)
        await sim.do(vale, "say After.")
        assert said(sim, wynn, "After") == ['Vale says, "After."']

    async def test_study_pierces_only_for_the_winner(self, greenroom, monkeypatch):
        sim, vale, wynn = greenroom
        sable = sim.player("Sable", location=vale.location)
        await run_build(sim, vale, "134_disguises.md")
        room = vale.location
        wynn.location = room
        sable.location = room

        await sim.do(vale, "don a masked courier")

        # Deterministic dice: a fixed mid roll of 10. Against the wardrobe's
        # -4 quality, a keen eye (16 -> effective 12) clears it; a dull one
        # (10 -> effective 6) does not.
        monkeypatch.setattr("realm.core.dice.roll", lambda expr: 10)
        wynn.db.set('skill_perception', 16)
        sable.db.set('skill_perception', 10)

        # Sable studies and fails: still fooled.
        sim.seen(sable)
        await sim.do(sable, "study a masked courier")
        assert said(sim, sable, "the disguise holds")

        # Wynn studies and wins: sees through it. (Drain once — said()
        # empties the queue, so read the whole reply in one go.)
        sim.seen(wynn)
        await sim.do(wynn, "study a masked courier")
        wynn_reply = heard(sim, wynn)
        assert "see through the disguise" in wynn_reply
        assert "really Vale" in wynn_reply

        # The proof is on the engine surfaces: Vale speaks, and only the
        # watcher who pierced the mask hears her true name.
        sim.seen(wynn), sim.seen(sable)
        await sim.do(vale, "say Nothing to see.")
        assert said(sim, wynn, "Nothing") == ['Vale says, "Nothing to see."']
        assert said(sim, sable, "Nothing") == [
            'a masked courier says, "Nothing to see."']

        # And in the room list: Wynn sees Vale, Sable sees the courier.
        sim.seen(wynn), sim.seen(sable)
        await sim.do(wynn, "look")
        await sim.do(sable, "look")
        assert "Vale" in heard(sim, wynn)
        sable_blob = heard(sim, sable)
        assert "a masked courier" in sable_blob
        assert "Vale" not in sable_blob


# --- 84 voice disguise -----------------------------------------------------


@pytest.fixture
def booth():
    sim = Simulator()
    studio = sim.room("Studio")
    dex = sim.player("Dex", location=studio)
    dex.add_tag("admin")                 # owns the modulator it @creates
    edda = sim.player("Edda", location=studio)
    # 84 registers NOTHING — voice_as is a pure attr. Clear the seam so no
    # stray resolver from another test can bleed in.
    clear_name_resolvers()
    try:
        yield sim, dex, edda
    finally:
        clear_name_resolvers()
        sim.close()


@pytest.mark.asyncio
class TestVoiceDisguise:
    async def test_masked_voice_unmasked_face(self, booth):
        sim, dex, edda = booth
        await run_build(sim, dex, "084_voice_disguise.md")
        room = dex.location
        edda.location = room

        # Dex modulates: only the voice changes.
        await sim.do(dex, "modulate a distorted voice")

        # Edda HEARS the alias; Dex hears his own true attribution.
        sim.seen(dex), sim.seen(edda)
        await sim.do(dex, "say Identify yourself.")
        assert said(sim, edda, "Identify") == [
            'a distorted voice says, "Identify yourself."']
        assert said(sim, dex, "Identify") == [
            'You say, "Identify yourself."']

        # The whole point: the FACE is untouched. Edda's look still shows
        # Dex by name, and never the distorted voice (that's speech only).
        sim.seen(edda)
        await sim.do(edda, "look")
        blob = heard(sim, edda)
        assert "Dex" in blob
        assert "distorted voice" not in blob

        # Clear the modulator: Dex's voice is his own again.
        await sim.do(dex, "clear")
        sim.seen(edda)
        await sim.do(dex, "say It is me.")
        assert said(sim, edda, "It is me") == ['Dex says, "It is me."']
