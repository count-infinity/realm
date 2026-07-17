"""Showcase verification — Speech transforms (items 79 languages, 139 intoxication).

Both tutorials sit on the per-listener speech-renderer seam shipped
2026-07-17 (`register_speech_renderer`): the spoken body is resolved once
per recipient, so a native transform can garble it for a listener who
lacks the tongue (79) or slur it for a drunk speaker (139). Each item's
native half — the renderer a game registers at deploy time — is defined
here exactly as its tutorial documents it and registered in the fixture;
the in-game Build-it command lines are read straight from the markdown and
driven through the dispatcher.

The two renderers compose: registered in order, each sees the previous
one's output, so a drunk speaker of a foreign tongue both garbles and
slurs (the final class here drives that).
"""

from __future__ import annotations

import re
import types
from pathlib import Path

import pytest

from realm.core.propagation import (
    clear_speech_renderers,
    register_speech_renderer,
)
from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"
RED_FLAGS = ("Unknown command", "Script error", "Syntax error", "Traceback",
             "not defined", "refuses", "will not run")


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


def only(lines, needle):
    """Filter an already-drained batch (``sim.seen`` empties the queue, so
    capture once and filter with this when a listener is checked twice)."""
    return [x for x in lines if needle in x]


# --- the native halves, verbatim from the tutorials -------------------------


def garble_unknown_tongue(body, action, looker):
    """The 79 renderer the tutorial shows, registered so the test exercises
    the same policy the doc documents."""
    if action.action_type != "event:speech":
        return body                      # only spoken words garble
    tongue = action.actor.db.get("speaking")
    if not tongue or looker is None or looker is action.actor:
        return body                      # plain speech, or the speaker's own ear
    if tongue in (looker.db.get("languages") or []):
        return body                      # this listener shares the tongue
    return f"<something in {tongue.title()}>"


def slur_when_drunk(body, action, looker):
    """The 139 renderer the tutorial shows: deterministic, no randomness."""
    if action.action_type != "event:speech" or not action.actor.has_tag("drunk"):
        return body
    stretch = 1 + int(action.actor.db.get("drunks") or 1)
    swap = {"s": "sh", "S": "Sh"}
    return "".join(
        swap.get(c, c * stretch if c.lower() in "aeiou" else c) for c in body)


def _seat(sim, room, *players):
    """Drop players into the room the build teleported the builder into."""
    for p in players:
        p.location = room


# --- 79 languages -----------------------------------------------------------


@pytest.fixture
def moot():
    sim = Simulator()
    start = sim.room("Start")
    ada = sim.player("Ada", location=start)
    ada.add_tag("admin")                 # owns the lectern it @creates
    vex = sim.player("Vex", location=start)
    mara = sim.player("Mara", location=start)
    bran = sim.player("Bran", location=start)
    clear_speech_renderers()
    register_speech_renderer(garble_unknown_tongue)
    try:
        yield sim, ada, vex, mara, bran
    finally:
        clear_speech_renderers()
        sim.close()


@pytest.mark.asyncio
class TestLanguages:
    async def test_two_listeners_hear_one_say_differently(self, moot):
        sim, ada, vex, mara, bran = moot
        await run_build(sim, ada, "079_languages.md")
        room = ada.location
        _seat(sim, room, vex, mara, bran)

        await sim.do(ada, '@set Vex/languages = ["trade"]')
        await sim.do(ada, '@set Mara/languages = ["trade"]')
        await sim.do(ada, '@set Bran/languages = []')

        # The admin-owned lectern writes Vex's own sheet (Vex is not admin).
        await sim.do(vex, "speak trade")
        assert vex.db.get("speaking") == "trade"

        sim.seen(vex), sim.seen(mara), sim.seen(bran)
        await sim.do(vex, "say the cargo lands at dawn")
        vex_lines, mara_lines, bran_lines = (
            sim.seen(vex), sim.seen(mara), sim.seen(bran))

        # One say, two different bodies — attribution identical.
        assert only(mara_lines, "cargo") == [
            'Vex says, "the cargo lands at dawn"']
        assert only(bran_lines, "Trade") == [
            'Vex says, "<something in Trade>"']
        assert only(bran_lines, "Vex says,")          # name untouched
        # The speaker reads her own words plain.
        assert only(vex_lines, "cargo") == [
            'You say, "the cargo lands at dawn"']

    async def test_common_is_universal(self, moot):
        sim, ada, vex, mara, bran = moot
        await run_build(sim, ada, "079_languages.md")
        room = ada.location
        _seat(sim, room, vex, mara, bran)
        await sim.do(ada, '@set Vex/languages = ["trade"]')
        await sim.do(ada, '@set Bran/languages = []')

        # Speaking Trade, then dropping back to common, unblocks Bran.
        await sim.do(vex, "speak trade")
        await sim.do(vex, "speak common")
        assert vex.db.get("speaking") is None
        sim.seen(bran)
        await sim.do(vex, "say and the manifest is clean")
        assert said(sim, bran, "manifest") == [
            'Vex says, "and the manifest is clean"']


# --- 139 intoxication -------------------------------------------------------


@pytest.fixture
def flagon():
    sim = Simulator()
    start = sim.room("Start")
    ada = sim.player("Ada", location=start)
    ada.add_tag("admin")                 # owns the bottle it @creates
    bex = sim.player("Bex", location=start)
    cass = sim.player("Cass", location=start)
    doran = sim.player("Doran", location=start)
    clear_speech_renderers()
    register_speech_renderer(slur_when_drunk)
    try:
        yield sim, ada, bex, cass, doran
    finally:
        clear_speech_renderers()
        sim.close()


@pytest.mark.asyncio
class TestIntoxication:
    async def test_sober_clean_then_progressively_slurred(self, flagon):
        sim, ada, bex, cass, doran = flagon
        await run_build(sim, ada, "139_intoxication.md")
        room = ada.location
        _seat(sim, room, bex, cass, doran)

        # Sober: clean to every listener.
        sim.seen(cass), sim.seen(doran)
        await sim.do(bex, "say Cheers, friends!")
        assert said(sim, cass, "Cheers") == ['Bex says, "Cheers, friends!"']
        assert said(sim, doran, "Cheers") == ['Bex says, "Cheers, friends!"']

        # One pull: tagged drunk, penalty on the sheet.
        await sim.do(bex, "drink")
        assert bex.has_tag("drunk")
        assert bex.db.get("drunks") == 1
        assert bex.db.get("check_mods") == {"drunk": {"all": -2}}

        sim.seen(cass)
        await sim.do(bex, "say Cheers, friends!")
        assert said(sim, cass, "says") == [
            'Bex says, "Cheeeersh, friieendsh!"']

        # Second pull: deeper penalty, worse slur, same for everyone.
        await sim.do(bex, "drink")
        assert bex.db.get("drunks") == 2
        assert bex.db.get("check_mods") == {"drunk": {"all": -4}}

        sim.seen(cass), sim.seen(doran)
        await sim.do(bex, "say Cheers, friends!")
        worse = 'Bex says, "Cheeeeeersh, friiieeendsh!"'
        assert said(sim, cass, "says") == [worse]
        assert said(sim, doran, "says") == [worse]   # every ear, same slur

    async def test_penalty_is_a_real_check_mod(self, flagon):
        sim, ada, bex, cass, doran = flagon
        await run_build(sim, ada, "139_intoxication.md")
        room = ada.location
        _seat(sim, room, bex, cass, doran)

        assert bex.db.get("check_mods") is None      # sober: nothing folded in
        await sim.do(bex, "drink")
        # The debuff lives in db.check_mods exactly as long as the effect,
        # keyed by the effect's kind — every check() folds it in.
        assert bex.db.get("check_mods") == {"drunk": {"all": -2}}


# --- composition: renderers stack in registration order ---------------------


@pytest.fixture
def bar_of_babel():
    sim = Simulator()
    start = sim.room("Start")
    ada = sim.player("Ada", location=start)
    ada.add_tag("admin")
    bex = sim.player("Bex", location=start)
    mara = sim.player("Mara", location=start)
    bran = sim.player("Bran", location=start)
    clear_speech_renderers()
    register_speech_renderer(garble_unknown_tongue)   # first: garble
    register_speech_renderer(slur_when_drunk)          # second: slur the result
    try:
        yield sim, ada, bex, mara, bran
    finally:
        clear_speech_renderers()
        sim.close()


@pytest.mark.asyncio
class TestCompose:
    async def test_drunk_foreign_speaker_garbles_and_slurs(self, bar_of_babel):
        sim, ada, bex, mara, bran = bar_of_babel
        # The bottle (139 build) puts Bex in a drunk state; the tongue is
        # set directly here — the compose story is about the two renderers.
        await run_build(sim, ada, "139_intoxication.md")
        room = ada.location
        _seat(sim, room, bex, mara, bran)
        await sim.do(ada, '@set Bex/speaking = trade')
        await sim.do(ada, '@set Mara/languages = ["trade"]')
        await sim.do(ada, '@set Bran/languages = []')

        await sim.do(bex, "drink")
        assert bex.has_tag("drunk")

        sim.seen(mara), sim.seen(bran)
        await sim.do(bex, "say the cargo lands at dawn")

        # Compute the expected bodies by composing the two renderers in the
        # order they were registered — proving the dispatcher did the same.
        stub = types.SimpleNamespace(action_type="event:speech", actor=bex)

        def pipeline(body, looker):
            return slur_when_drunk(
                garble_unknown_tongue(body, stub, looker), stub, looker)

        mara_body = pipeline("the cargo lands at dawn", mara)   # slur only
        bran_body = pipeline("the cargo lands at dawn", bran)   # garble + slur

        assert said(sim, mara, "says") == [f'Bex says, "{mara_body}"']
        assert said(sim, bran, "says") == [f'Bex says, "{bran_body}"']
        # Mara shares Trade, so the garble is skipped and she reads the real
        # (slurred) words; Bran does not, so his line still hides them behind
        # the garble placeholder — which is itself then slurred.
        assert "<" not in mara_body                  # real words, just slurred
        assert "<" in bran_body and ">" in bran_body  # garble placeholder, slurred
        assert mara_body != bran_body
