"""
Showcase "Interactive Objects & Gadgets" — checklist items 3, 4, 6, 7,
8, 9, 10, 11, 12, 13.

Verifies the standalone tutorials in docs/showcase/ (003_jukebox.md,
004_atm_terminal.md, 006_flashlight.md, 007_voice_recorder.md,
008_camera.md, 009_music_box.md, 010_typewriter.md, 011_mirror.md,
012_gift_box.md, 013_fortune_teller.md) by driving a real in-process
world — realm.testing.Simulator wires the same store/propagation/
scripting/dispatcher stack a live GameServer does — with the tutorials'
EXACT command lines (raw input in, session output out).

The build transcripts below are copied verbatim from the docs' "Build
it" sections; the sync test at the bottom keeps them from drifting.
Timers are driven deterministically: script_ticker scripts via
`@tr <obj>/on_tick`, wait() chains via engine.tick_waits() after
zeroing the tempo/delay data attribute, prompt() wizards by invoking
the session's captured input handler — the same techniques the heist
and economy arc tests use.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import realm.behaviors  # noqa: F401 — registers script_ticker
from realm.core.economy import get_credits
from realm.testing import Simulator

# Output that must never appear while running a "Build it" transcript —
# catches typos, permission problems, and validation failures in any
# tutorial line.
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
    # on a live server; give the Simulator the same wiring (exactly as the
    # heist and living-npcs suites do).
    s.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(s._sessions.values()))
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def pinned_rand(monkeypatch):
    """Pin rand(): random.randint returns holder['value'] clamped to range."""
    holder = {"value": 1}

    def fake_randint(low, high):
        return max(low, min(holder["value"], high))

    monkeypatch.setattr(
        "realm.scripting.functions.random.randint", fake_randint)
    return holder


def workshop_and_builder(sim):
    """The standing start of every tutorial: a room and a builder in it."""
    room = sim.room("The Workshop")
    bilda = sim.player("Bilda", location=room)
    bilda.add_tag("builder")
    return room, bilda


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


# =========================================================================
# 003. Jukebox — docs/showcase/003_jukebox.md
# =========================================================================

JUKEBOX_BUILD = [
    "@create jukebox",
    "drop jukebox",
    "@desc jukebox = A chrome-and-neon jukebox from a more optimistic "
    "century. [[t = V('tracks', []); n = V('spinning', None); "
    'result = f"The window card reads: '
    "{t[n]['title'] if n is not None and n < len(t) else 'SILENCE'}"
    '."]]',
    '@set jukebox/tracks = [{"title": "Stardust Rag", "lines": '
    '["the void don\'t care, but baby I do", '
    '"every orbit brings me back to you"]}, '
    '{"title": "Vacuum Blues", "lines": '
    '["got a hull full of nothing and nowhere to be"]}]',
    "@set jukebox/menu = t = V('tracks', []); result = "
    "'Pick a track: ' + ' '.join(f\"[{i + 1}] {tr['title']}\" "
    "for i, tr in enumerate(t)) + ' -- or anything else to walk away.'",
    "@set jukebox/cmd_play = $play: prompt(enactor, eval_attr(me, "
    "'menu'), 'on_pick')",
    "@set jukebox/on_pick = t = V('tracks', []); w = "
    "trim(arg0); n = int(w) if w.isdigit() else 0; ok = 1 <= n <= "
    "len(t); (set_attr(me, 'spinning', n - 1), set_attr(me, 'cursor', "
    "0), remit(here, f\"The jukebox whirs, and the arm drops on "
    "{t[n - 1]['title']}.\")) if ok else pemit(enactor, 'The jukebox "
    "clunks and returns your choice unplayed.')",
    "@behavior jukebox = script_ticker, interval:4",
    "@set jukebox/on_tick = n = V('spinning', None); t = "
    "V('tracks', []); i = V('cursor', 0); lines = "
    "t[n]['lines'] if n is not None and n < len(t) else []; "
    "(remit(here, f'~ {lines[i]} ~'), incr('cursor')) "
    "if n is not None and i < len(lines) else None; "
    "(del_attr(me, 'spinning'), remit(here, 'The record hisses into "
    "the run-out groove, and the arm lifts.')) if n is not None and "
    "i >= len(lines) else None",
]


class TestJukebox:

    async def test_menu_pick_and_ticker_lyrics(self, sim):
        room, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=room)
        await build(sim, bilda, JUKEBOX_BUILD)
        sim.seen(kess)

        # Idle: the window card reads SILENCE.
        out = await do(sim, bilda, "look jukebox")
        assert any("The window card reads: SILENCE." in line for line in out)

        # play -> the prompt() menu arrives as the player's next question.
        out = await do(sim, bilda, "play")
        joined = "\n".join(out)
        assert "Pick a track:" in joined
        assert "[1] Stardust Rag" in joined
        assert "[2] Vacuum Blues" in joined

        # Answer 1 — the whole room hears the arm drop.
        await answer(sim, bilda, "1")
        assert ("The jukebox whirs, and the arm drops on Stardust Rag."
                in sim.seen(kess))

        # Now playing shows on the window card.
        out = await do(sim, bilda, "look jukebox")
        assert any("The window card reads: Stardust Rag." in line
                   for line in out)

        # Each ticker beat is one lyric line, room-wide.
        sim.seen(bilda)
        await do(sim, bilda, "@tr jukebox/on_tick")
        assert "~ the void don't care, but baby I do ~" in sim.seen(kess)
        await do(sim, bilda, "@tr jukebox/on_tick")
        assert "~ every orbit brings me back to you ~" in sim.seen(kess)

        # The side ends: run-out groove, then silence again.
        await do(sim, bilda, "@tr jukebox/on_tick")
        assert ("The record hisses into the run-out groove, and the arm "
                "lifts." in sim.seen(kess))
        out = await do(sim, bilda, "look jukebox")
        assert any("The window card reads: SILENCE." in line for line in out)

        # A dead ticker beat plays nothing.
        sim.seen(kess)
        await do(sim, bilda, "@tr jukebox/on_tick")
        assert not any("~" in line for line in sim.seen(kess))

    async def test_bad_pick_is_returned_unplayed(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, JUKEBOX_BUILD)
        await do(sim, bilda, "play")
        out = await answer(sim, bilda, "9")
        assert "The jukebox clunks and returns your choice unplayed." in out
        jukebox = find_one(sim, "jukebox")
        assert jukebox.db.get("spinning") is None


# =========================================================================
# 004. ATM / bank terminal — docs/showcase/004_atm_terminal.md
# =========================================================================

ATM_BUILD_CORE = [
    "@create BankNet Core",
    "drop BankNet Core",
    "@set BankNet Core/net_balance = bank = get('BankNet Core'); "
    'pemit(enactor, f"BANKNET -- account balance: '
    "{get_attr(bank, 'acct_' + enactor.id, 0)} credits.\"); "
    "result = 1",
    "@set BankNet Core/net_deposit = bank = get('BankNet Core'); "
    "amt = int(arg0) if arg0.isdigit() else 0; ok = amt > 0 and "
    "transfer_credits(enactor, bank, amt); k = f'acct_{enactor.id}'; "
    "bal = get_attr(bank, k, 0) + amt; set_attr(bank, k, bal) if ok "
    "else None; pemit(enactor, f'Deposit accepted. Balance: "
    "{bal} credits.' if ok else 'The terminal buzzes: your "
    "wallet cannot cover that.'); result = 1",
    "@set BankNet Core/net_withdraw = bank = get('BankNet Core'); "
    "amt = int(arg0) if arg0.isdigit() else 0; "
    "k = f'acct_{enactor.id}'; bal = get_attr(bank, k, 0); "
    "ok = 0 < amt <= bal and "
    "transfer_credits(bank, enactor, amt); set_attr(bank, k, "
    "bal - amt) if ok else None; pemit(enactor, f'Notes whir out of "
    "the slot. Balance: {bal - amt} credits.' if ok else "
    "'The terminal buzzes: insufficient funds on account.'); result = 1",
]

ATM_BUILD_TERMINAL = [
    "@create atm terminal",
    "drop atm terminal",
    "@desc atm terminal = A steel kiosk with a scratched screen and a "
    'cash slot polished by thumbs. [[result = f"The screen glows: ACCT '
    "{get_attr(get('BankNet Core'), 'acct_' + viewer.id, 0)} CR.\"]]",
    "@set atm terminal/cmd_atm = $atm: eval_attr(get('BankNet Core'), "
    "'net_balance')",
    "@set atm terminal/cmd_deposit = $deposit *: "
    "eval_attr(get('BankNet Core'), 'net_deposit', trim(arg0))",
    "@set atm terminal/cmd_withdraw = $withdraw *: "
    "eval_attr(get('BankNet Core'), 'net_withdraw', trim(arg0))",
]

ATM_BUILD_BRANCH = [
    "@dig The Docks Concourse = gangway, plaza",
    "gangway",
    "@clone atm terminal",
    "plaza",
]


def bank_plaza_and_admin(sim):
    """The ATM tutorial's standing start: an ADMIN builder (the master
    must be admin-owned so terminals can debit depositors)."""
    room = sim.room("The Bank Plaza")
    vala = sim.player("Vala", location=room)
    vala.add_tag("admin")
    return room, vala


class TestAtmTerminal:

    async def _built(self, sim):
        plaza, vala = bank_plaza_and_admin(sim)
        await build(sim, vala, ATM_BUILD_CORE)
        await build(sim, vala, ATM_BUILD_TERMINAL)
        await build(sim, vala, ATM_BUILD_BRANCH)
        assert vala.location is plaza
        docks = find_one(sim, "The Docks Concourse")
        return plaza, docks, vala

    async def test_accounts_are_shared_across_terminals(self, sim):
        plaza, docks, vala = await self._built(sim)
        core = find_one(sim, "BankNet Core")

        # A mortal customer with pocket money.
        bob = sim.player("Bob", location=plaza)
        await build(sim, vala, ["@eval adjust_credits(get('Bob'), 100)"])

        out = await do(sim, bob, "atm")
        assert "BANKNET -- account balance: 0 credits." in out

        out = await do(sim, bob, "deposit 60")
        assert "Deposit accepted. Balance: 60 credits." in out
        assert get_credits(bob) == 40
        # The cash lives in the CORE's vault, not the kiosk.
        assert get_credits(core) == 60
        assert get_credits(find_one(sim, "atm terminal")) == 0

        # The per-viewer screen readout.
        out = await do(sim, bob, "look atm terminal")
        assert any("The screen glows: ACCT 60 CR." in line for line in out)

        # Walk to the docks: the CLONED terminal serves the same account.
        await do(sim, bob, "gangway")
        assert bob.location is docks
        out = await do(sim, bob, "atm")
        assert "BANKNET -- account balance: 60 credits." in out

        out = await do(sim, bob, "withdraw 25")
        assert "Notes whir out of the slot. Balance: 35 credits." in out
        assert get_credits(bob) == 65
        assert get_credits(core) == 35

        # Back at the plaza, the first terminal agrees.
        await do(sim, bob, "plaza")
        out = await do(sim, bob, "atm")
        assert "BANKNET -- account balance: 35 credits." in out

    async def test_overdrafts_and_bad_amounts_buzz(self, sim):
        plaza, _docks, vala = await self._built(sim)
        bob = sim.player("Bob", location=plaza)
        await build(sim, vala, ["@eval adjust_credits(get('Bob'), 10)"])

        out = await do(sim, bob, "withdraw 500")
        assert "The terminal buzzes: insufficient funds on account." in out
        out = await do(sim, bob, "deposit 999")
        assert "The terminal buzzes: your wallet cannot cover that." in out
        out = await do(sim, bob, "deposit lots")
        assert "The terminal buzzes: your wallet cannot cover that." in out
        assert get_credits(bob) == 10


# =========================================================================
# 006. Flashlight — docs/showcase/006_flashlight.md
# =========================================================================

FLASHLIGHT_BUILD = [
    "@create flashlight",
    "@set flashlight/battery = 3",
    "@set flashlight/cmd_click = $click: lit = has_tag(me, 'light'); "
    "b = V('battery', 0); (remove_tag(me, 'light'), "
    "pemit(enactor, 'Click. The beam dies.')) if lit else "
    "((add_tag(me, 'light'), pemit(enactor, 'Click. A hard white beam "
    "snaps on.')) if b > 0 else pemit(enactor, 'Click. Click. Nothing. "
    "The battery is dead.'))",
    "@behavior flashlight = script_ticker, interval:10",
    "@set flashlight/on_tick = lit = has_tag(me, 'light'); b = "
    "V('battery', 0); left = b - 1 if lit else b; "
    "decr('battery') if lit else None; remove_tag(me, "
    "'light') if lit and left <= 0 else None; msg = 'The flashlight "
    "flickers; its battery is nearly spent.' if lit and left == 1 else "
    "('The flashlight gutters and dies.' if lit and left <= 0 else "
    "''); h = loc(me); (pemit(h, msg) if has_tag(h, 'player') else "
    "remit(h, msg)) if msg and h else None",
    "@dig The Undercroft = down, up",
    "down",
    "@tag here = dark",
]


class TestFlashlight:

    async def _built(self, sim):
        workshop, bilda = workshop_and_builder(sim)
        await build(sim, bilda, FLASHLIGHT_BUILD)
        undercroft = find_one(sim, "The Undercroft")
        assert bilda.location is undercroft
        return workshop, undercroft, bilda

    async def test_darkness_wielding_and_battery_death(self, sim):
        _workshop, undercroft, bilda = await self._built(sim)

        # Dark room, light off: pitch black.
        out = await do(sim, bilda, "look")
        assert "It is pitch black here. You can't see a thing." in out

        # Click it on — but a light buried in your pack lights nothing:
        # the engine wants it HELD UP (wielded) or set down.
        out = await do(sim, bilda, "click")
        assert "Click. A hard white beam snaps on." in out
        out = await do(sim, bilda, "look")
        assert "It is pitch black here. You can't see a thing." in out

        out = await do(sim, bilda, "wield flashlight")
        assert "You ready flashlight." in out
        out = await do(sim, bilda, "look")
        assert any("The Undercroft" in line for line in out)
        assert "It is pitch black here. You can't see a thing." not in out

        # The ticker drains only while lit: 3 -> 2, then 2 -> 1 (warning),
        # then 1 -> 0 (dies, tag drops, darkness returns).
        await do(sim, bilda, "@tr flashlight/on_tick")
        out = await do(sim, bilda, "@tr flashlight/on_tick")
        assert "The flashlight flickers; its battery is nearly spent." in out
        out = await do(sim, bilda, "@tr flashlight/on_tick")
        assert "The flashlight gutters and dies." in out
        flashlight = find_one(sim, "flashlight")
        assert not flashlight.has_tag("light")
        assert flashlight.db.get("battery") == 0

        out = await do(sim, bilda, "look")
        assert "It is pitch black here. You can't see a thing." in out

        # Dead battery: clicking is just noise.
        out = await do(sim, bilda, "click")
        assert "Click. Click. Nothing. The battery is dead." in out

    async def test_a_lit_flashlight_on_the_floor_lights_the_room(self, sim):
        _workshop, undercroft, bilda = await self._built(sim)
        kess = sim.player("Kess", location=undercroft)

        # A fresh battery, clicked on and DROPPED: floor lights need no
        # wielder, and they light the room for everyone.
        await do(sim, bilda, "click")
        await do(sim, bilda, "drop flashlight")
        out = await do(sim, kess, "look")
        assert any("The Undercroft" in line for line in out)

        # Unlit ticker beats don't drain the battery.
        await do(sim, bilda, "click")
        await do(sim, bilda, "@tr flashlight/on_tick")
        assert find_one(sim, "flashlight").db.get("battery") == 3


# =========================================================================
# 007. Voice recorder — docs/showcase/007_voice_recorder.md
# =========================================================================

RECORDER_BUILD = [
    "@create voice recorder",
    "drop voice recorder",
    "@desc voice recorder = A palm-sized deck of scuffed bakelite with "
    "one spinning reel. [[n = len(V('transcript', [])); "
    "result = f'The counter reads {n} line' + ('' if n == 1 "
    "else 's') + ('; the REC lamp burns red.' if V('recording', 0) "
    "else '.')]]",
    "@set voice recorder/cmd_record = $record: (set_attr(me, "
    "'recording', 1), set_attr(me, 'transcript', []), remit(here, "
    "'The voice recorder clicks; a red REC lamp lights.'))",
    "@set voice recorder/listen_all = ^*: set_attr(me, 'transcript', "
    "(V('transcript', []) + [f'{name(enactor)}: {escape(arg0)}'])"
    "[-20:]) if V('recording', 0) else None",
    "@set voice recorder/cmd_stop = $stop: (set_attr(me, 'recording', "
    "0), remit(here, 'The REC lamp dims.'))",
    "@set voice recorder/cmd_play = $play: rows = V('transcript', []); "
    "pemit(enactor, 'The tape is blank.') if not "
    "rows else remit(here, 'The voice recorder crackles and plays:'); "
    "[remit(here, '  > ' + r) for r in rows]",
]


class TestVoiceRecorder:

    async def test_record_stop_and_playback(self, sim):
        room, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=room)
        await build(sim, bilda, RECORDER_BUILD)
        sim.seen(kess)

        out = await do(sim, bilda, "record")
        assert "The voice recorder clicks; a red REC lamp lights." in out

        await do(sim, bilda, "say The drop is at midnight.")
        await do(sim, kess, "say Bring the case and come alone.")

        out = await do(sim, bilda, "stop")
        assert "The REC lamp dims." in out

        # Off the record: said after stop.
        await do(sim, kess, "say Wait, forget all that.")

        # The living description counts the take.
        out = await do(sim, bilda, "look voice recorder")
        assert any("The counter reads 2 lines." in line for line in out)

        sim.seen(kess)
        out = await do(sim, bilda, "play")
        joined = "\n".join(out)
        assert "The voice recorder crackles and plays:" in joined
        assert "  > Bilda: The drop is at midnight." in joined
        assert "  > Kess: Bring the case and come alone." in joined
        assert "forget all that" not in joined
        # Playback is room-wide.
        assert ("  > Bilda: The drop is at midnight." in sim.seen(kess))

    async def test_pocketed_recorder_hears_nothing(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, RECORDER_BUILD)

        # In your pocket it still takes commands ($-triggers search your
        # inventory) but overhears nothing: ^listen only scans the ROOM.
        await do(sim, bilda, "get voice recorder")
        await do(sim, bilda, "record")
        await do(sim, bilda, "say This never reaches the tape.")
        out = await do(sim, bilda, "play")
        assert "The tape is blank." in out

    async def test_recorder_never_records_its_own_playback(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, RECORDER_BUILD)
        await do(sim, bilda, "record")
        await do(sim, bilda, "say Only this line.")
        await do(sim, bilda, "play")   # still recording — plays back openly
        recorder = find_one(sim, "voice recorder")
        assert recorder.db.get("transcript") == ["Bilda: Only this line."]


# =========================================================================
# 008. Camera — docs/showcase/008_camera.md
# =========================================================================

CAMERA_BUILD = [
    "@desc here = Dust hangs in the light of one caged bulb.",
    "@create box camera",
    "@set box camera/cmd_snap = $snap: room = loc(enactor); people = "
    "[name(o) for o in contents(room) if has_tag(o, 'player') or "
    "has_tag(o, 'npc')]; props = [name(o) for o in contents(room) if "
    "not (has_tag(o, 'player') or has_tag(o, 'npc') or has_tag(o, "
    "'exit'))]; rows = [['', 'A stiff glossy print, edges still warm "
    "from the developer.'], ['', f'The scene: {name(room)}.']] + "
    "([['', room.description]] if room.description else []) + "
    "([['', f\"Pictured: {', '.join(people)}.\"]] if people else []) + "
    "([['', f\"Scattered about: {', '.join(props)}.\"]] if props "
    "else []); photo = create_obj(f'a photograph of {name(room)}', "
    "tags=['thing', 'no_group'], location=enactor); set_attr(photo, "
    "'desc_extras', rows); set_attr(photo, 'taken_at', now()); "
    "remit(here, 'FLASH. The box camera whirs and spits out a "
    "photograph.')",
]


class TestCamera:

    async def test_snapshot_captures_room_and_occupants(self, sim):
        room, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=room)
        sim.obj("crated servitor", location=room, tags=["thing"])
        await build(sim, bilda, CAMERA_BUILD)
        sim.seen(kess)

        out = await do(sim, bilda, "snap")
        assert ("FLASH. The box camera whirs and spits out a photograph."
                in out)
        assert ("FLASH. The box camera whirs and spits out a photograph."
                in sim.seen(kess))

        photo = find_one(sim, "a photograph of The Workshop")
        assert photo.location is bilda

        out = await do(sim, bilda, "look photograph")
        joined = "\n".join(out)
        assert "A stiff glossy print, edges still warm from the developer." \
            in joined
        assert "The scene: The Workshop." in joined
        assert "Dust hangs in the light of one caged bulb." in joined
        assert "Pictured: Bilda, Kess." in joined
        assert "crated servitor" in joined

        # The photo is a snapshot, not a live feed: Kess leaves, the
        # print still shows her.
        kess.location = sim.room("Elsewhere")
        out = await do(sim, bilda, "look photograph")
        assert "Pictured: Bilda, Kess." in "\n".join(out)

        # A second snap makes a second, independent print.
        await do(sim, bilda, "snap")
        prints = sim.store.find_cached(name="a photograph of The Workshop")
        assert len(prints) == 2
        texts = ["\n".join(row[1] for row in p.db.get("desc_extras"))
                 for p in prints]
        assert sum("Pictured: Bilda, Kess." in t for t in texts) == 1
        assert sum("Pictured: Bilda." in t and "Kess" not in t
                   for t in texts) == 1


# =========================================================================
# 009. Music box — docs/showcase/009_music_box.md
# =========================================================================

MUSICBOX_BUILD = [
    "@create music box",
    "drop music box",
    "@set music box/tempo = 5",
    '@set music box/notes = ["a bright, glassy arpeggio", "three '
    'descending notes, like rain off a roof", "a tiny waltz figure, '
    'slightly out of tune"]',
    "@set music box/cmd_wind = $wind music box: t = V('turns', 0); "
    "(set_attr(me, 'turns', min(t + 3, 9)), pose(f'clicks "
    "softly as {name(enactor)} winds the brass key.'), "
    "(wait(V('tempo', 5), 'trigger me/play_note') if t == 0 "
    "else None))",
    "@set music box/play_note = t = V('turns', 0); notes = "
    "V('notes', []); i = V('cursor', 0); "
    "(pose(f'plays {notes[i % len(notes)]}.'), incr('cursor'), "
    "decr('turns'), "
    "(wait(V('tempo', 5), 'trigger me/play_note') if "
    "t - 1 > 0 else pose('slows... and stops with a final, drooping "
    "plink.'))) if t > 0 and notes else None",
]


class TestMusicBox:

    async def _built(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, MUSICBOX_BUILD)
        # Test-only: zero the tempo so tick_waits() can fire each link of
        # the wait() chain deterministically (the gas-bomb fuse trick).
        await build(sim, bilda, ["@set music box/tempo = 0"])
        return room, bilda

    async def test_wind_and_run_down(self, sim):
        room, bilda = await self._built(sim)
        kess = sim.player("Kess", location=room)

        out = await do(sim, bilda, "wind music box")
        assert "music box clicks softly as Bilda winds the brass key." in out
        assert find_one(sim, "music box").db.get("turns") == 3

        # Each wait() link plays one note and re-arms the next.
        sim.seen(kess)
        await sim.engine.tick_waits()
        assert "music box plays a bright, glassy arpeggio." in sim.seen(kess)
        await sim.engine.tick_waits()
        assert ("music box plays three descending notes, like rain off "
                "a roof." in sim.seen(kess))

        # The last turn: final note, then the wind-down — chain over.
        await sim.engine.tick_waits()
        out = sim.seen(kess)
        assert ("music box plays a tiny waltz figure, slightly out of "
                "tune." in out)
        assert ("music box slows... and stops with a final, drooping "
                "plink." in out)
        assert find_one(sim, "music box").db.get("turns") == 0

        # Silence after: no pending waits remain.
        await sim.engine.tick_waits()
        assert not any("music box plays" in line for line in sim.seen(kess))

    async def test_rewinding_stacks_turns_without_double_chains(self, sim):
        _room, bilda = await self._built(sim)
        box = find_one(sim, "music box")

        await do(sim, bilda, "wind music box")
        await do(sim, bilda, "wind music box")   # t != 0: no second chain
        assert box.db.get("turns") == 6

        # One tick, exactly ONE note — a second chain would double up.
        sim.seen(bilda)   # drain the wind chatter
        await sim.engine.tick_waits()
        notes = [line for line in sim.seen(bilda) if "music box plays" in line]
        assert len(notes) == 1

        # The spring caps at 9 turns.
        await do(sim, bilda, "wind music box")
        await do(sim, bilda, "wind music box")
        await do(sim, bilda, "wind music box")
        assert box.db.get("turns") == 9


# =========================================================================
# 010. Typewriter & paper — docs/showcase/010_typewriter.md
# =========================================================================

TYPEWRITER_BUILD = [
    "@create brass typewriter",
    "drop brass typewriter",
    "@set brass typewriter/cmd_type = $type *: title = trim(arg0); "
    "busy = V('sheet', ''); (pemit(enactor, 'A sheet is "
    "already in the roller; you pick up where the last typist left "
    "off.'), prompt(enactor, 'Next line (PAGE / DONE):', 'on_line')) "
    "if busy else None; pemit(enactor, 'Give the sheet a title: type "
    "<title>.') if not title and not busy else None; s = "
    "create_obj(f'a typed sheet: {title}', tags=['thing', 'document'], "
    "location=enactor) if title and not busy else None; (set_attr(s, "
    "'title', title), set_attr(s, 'pages', 1), set_attr(me, 'sheet', "
    "s.id), remit(here, f'{name(enactor)} feeds a fresh sheet into "
    "the brass typewriter.'), prompt(enactor, 'The keys wait. Type a "
    "line (PAGE starts a new page; DONE pulls the sheet):', "
    "'on_line')) if s else None",
    '@set brass typewriter/on_line = s = get(f"#{V(\'sheet\', \'\')}"); '
    "w = trim(arg0); n = get_attr(s, 'pages', 1) if s "
    "else 0; (set_attr(me, 'sheet', ''), pemit(enactor, 'The platen "
    "ratchets back and you pull the finished sheet free.')) if not s "
    "or w == 'DONE' else ((set_attr(s, 'pages', n + 1), "
    "prompt(enactor, f'A fresh page rolls in. [page {n + 1}] "
    "Next line (PAGE / DONE):', 'on_line')) if w == 'PAGE' else "
    "(set_attr(s, f'page_{n}', get_attr(s, f'page_{n}', []) "
    "+ [escape(arg0)]), prompt(enactor, f'[page {n}] Next "
    "line (PAGE / DONE):', 'on_line')))",
    "@set brass typewriter/cmd_peruse = $peruse *: s = "
    "get(trim(arg0)); ok = s is not None and has_tag(s, 'document'); "
    "pemit(enactor, 'There is no document by that name here.') if not "
    "ok else pemit(enactor, 'The type reads, page by page:'); "
    "[pemit(enactor, line) for g in [ok] if g for p in range(1, "
    "get_attr(s, 'pages', 1) + 1) for line in [f'--- page {p} ---'] "
    "+ [str(x) for x in get_attr(s, f'page_{p}', [])]]",
    "@set brass typewriter/cmd_sign = $sign *: s = get(trim(arg0)); "
    "ok = s is not None and has_tag(s, 'document') and loc(s) is "
    "enactor; already = str(get_attr(s, 'signed_by', '')) if ok else "
    "''; pemit(enactor, 'Hold the document you mean to sign.') if not "
    "ok else None; pemit(enactor, f'It already bears a signature: "
    "{already}.') if ok and already else None; "
    "k = f\"page_{get_attr(s, 'pages', 1)}\" if ok else ''; "
    "(set_attr(s, k, "
    "get_attr(s, k, []) + [f'Signed in a firm hand: "
    "{name(enactor)}']), set_attr(s, 'signed_by', name(enactor)), "
    "remit(here, f'{name(enactor)} signs {name(s)} with a "
    "flourish.')) if ok and not already else None",
]


class TestTypewriter:

    async def test_write_read_and_sign_a_two_page_document(self, sim):
        room, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=room)
        await build(sim, bilda, TYPEWRITER_BUILD)
        sim.seen(kess)

        out = await do(sim, bilda, "type Manifesto")
        assert ("Bilda feeds a fresh sheet into the brass typewriter."
                in sim.seen(kess))
        assert any("The keys wait." in line for line in out)

        await answer(sim, bilda, "All gadgets deserve softcode.")
        await answer(sim, bilda, "No exceptions.")
        out = await answer(sim, bilda, "PAGE")
        assert any("A fresh page rolls in. [page 2]" in line for line in out)
        await answer(sim, bilda, "Draft two follows.")
        out = await answer(sim, bilda, "DONE")
        assert ("The platen ratchets back and you pull the finished "
                "sheet free." in out)

        sheet = find_one(sim, "a typed sheet: Manifesto")
        assert sheet.location is bilda
        assert sheet.db.get("pages") == 2
        assert sheet.db.get("page_1") == [
            "All gadgets deserve softcode.", "No exceptions."]
        assert sheet.db.get("page_2") == ["Draft two follows."]

        out = await do(sim, bilda, "peruse typed sheet")
        joined = "\n".join(out)
        assert "The type reads, page by page:" in joined
        assert "--- page 1 ---" in joined
        assert "All gadgets deserve softcode." in joined
        assert "--- page 2 ---" in joined
        assert "Draft two follows." in joined

        # Sign it: the signature lands on the last page, once.
        sim.seen(kess)
        out = await do(sim, bilda, "sign typed sheet")
        assert ("Bilda signs a typed sheet: Manifesto with a flourish."
                in sim.seen(kess))
        out = await do(sim, bilda, "peruse typed sheet")
        assert "Signed in a firm hand: Bilda" in "\n".join(out)
        out = await do(sim, bilda, "sign typed sheet")
        assert "It already bears a signature: Bilda." in out

        # You must HOLD a document to sign it.
        await do(sim, bilda, "drop typed sheet")
        out = await do(sim, bilda, "sign typed sheet")
        assert "Hold the document you mean to sign." in out

    async def test_roller_busy_resumes_and_bad_reads_refuse(self, sim):
        room, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=room)
        await build(sim, bilda, TYPEWRITER_BUILD)

        await do(sim, bilda, "type Ransom Note")
        await answer(sim, bilda, "We have your ficus.")
        # Kess finds the wizard abandoned mid-sheet: typing resumes it.
        out = await do(sim, kess, "type Grocery List")
        assert ("A sheet is already in the roller; you pick up where "
                "the last typist left off." in out)
        await answer(sim, kess, "Wire 500 credits to the usual account.")
        await answer(sim, kess, "DONE")

        sheet = find_one(sim, "a typed sheet: Ransom Note")
        assert sheet.db.get("page_1") == [
            "We have your ficus.",
            "Wire 500 credits to the usual account."]

        out = await do(sim, bilda, "peruse the wind")
        assert "There is no document by that name here." in out


# =========================================================================
# 011. Mirror — docs/showcase/011_mirror.md
# =========================================================================

MIRROR_BUILD = [
    "@create tall mirror",
    "drop tall mirror",
    "@desc tall mirror = A tall oval of old glass in a tarnished brass "
    'frame; whatever stands before it, it returns. [[result = f"In the '
    "glass: {name(viewer)} -- {viewer.description or 'a "
    "face the silver cannot quite fix.'}\"]] [[worn = [name(o) for o in "
    "contents(viewer) if has_tag(o, 'worn')]; "
    "result = f\"Worn: {', '.join(worn)}.\" if worn else '']]",
    "@set tall mirror/on_look = oemit(enactor, "
    "f'{name(enactor)} pauses to study the tall mirror.')",
]

MIRROR_PROPS = [
    "@create woolen scarf",
    "@tag woolen scarf = wearable",
]


class TestMirror:

    async def test_each_viewer_sees_their_own_reflection(self, sim):
        room, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=room)
        await build(sim, bilda, MIRROR_BUILD)
        await build(sim, bilda, MIRROR_PROPS)

        await do(sim, bilda, "@desc me = Tall, wiry, one chipped tooth.")
        out = await do(sim, bilda, "look tall mirror")
        assert any("In the glass: Bilda -- Tall, wiry, one chipped tooth."
                   in line for line in out)

        # No @desc yet: the mirror's fallback line.
        out = await do(sim, kess, "look tall mirror")
        assert any("In the glass: Kess -- a face the silver cannot "
                   "quite fix." in line for line in out)

        # Worn gear shows; carried gear doesn't.
        await do(sim, bilda, "wear woolen scarf")
        out = await do(sim, bilda, "look tall mirror")
        assert any("Worn: woolen scarf." in line for line in out)
        out = await do(sim, kess, "look tall mirror")
        assert not any("Worn:" in line for line in out)

    async def test_on_look_narrates_to_bystanders_only(self, sim):
        room, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=room)
        await build(sim, bilda, MIRROR_BUILD)
        sim.seen(kess)

        out = await do(sim, bilda, "look tall mirror")
        assert "Bilda pauses to study the tall mirror." not in out
        assert "Bilda pauses to study the tall mirror." in sim.seen(kess)


# =========================================================================
# 012. Gift box — docs/showcase/012_gift_box.md
# =========================================================================

GIFTBOX_BUILD = [
    "@create gift box",
    "@set gift box/container = true",
    "drop gift box",
    "@desc gift box = A crisp white box under a red ribbon. "
    "[[to = V('for_name', ''); "
    'result = f"The tag reads: for {to}, from '
    "{V('from_name', 'a secret admirer')}.\" "
    "if to else 'The ribbon hangs loose; the tag is blank.']]",
    "@create silver locket",
    "put silver locket in gift box",
    "close gift box",
    "@set gift box/cmd_address = $address * to *: who = "
    "get(trim(arg1)); ok = who is not None and has_tag(who, "
    "'player'); (set_attr(me, 'for_id', who.id), set_attr(me, "
    "'for_name', name(who)), set_attr(me, 'from_name', "
    "name(enactor)), remit(here, f'{name(enactor)} ties the ribbon "
    "tight and pens a name on the tag.')) if ok else pemit(enactor, "
    "'You find no one by that name to address it to.')",
    "@set gift box/on_check = mine = atype == 'item:on_open' and "
    "target is me; to = V('for_id', ''); block(f\"The ribbon "
    "is charmed shut. The tag reads: for {V('for_name', '')} only.\") "
    "if mine and to and actor.id != to else None",
    "@set gift box/on_open = to = V('for_id', ''); inside "
    "= ', '.join(name(o) for o in contents(me)); (oemit(enactor, f'The "
    "ribbon leaps free as {name(enactor)} opens the gift "
    "box!'), pemit(enactor, f\"The ribbon leaps free! Inside: {inside} "
    "-- with love from {V('from_name', 'a secret admirer')}.\"), "
    "del_attr(me, 'for_id'), del_attr(me, "
    "'for_name'), del_attr(me, 'from_name')) if to else None",
]


class TestGiftBox:

    async def test_only_the_recipient_can_unwrap(self, sim):
        room, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=room)
        rook = sim.player("Rook", location=room)
        await build(sim, bilda, GIFTBOX_BUILD)
        sim.seen(kess)

        out = await do(sim, bilda, "address gift box to Kess")
        assert ("Bilda ties the ribbon tight and pens a name on the tag."
                in sim.seen(kess))

        out = await do(sim, bilda, "look gift box")
        assert any("The tag reads: for Kess, from Bilda." in line
                   for line in out)

        # The ward: wrong hands (even the giver's) can't open it.
        box = find_one(sim, "gift box")
        out = await do(sim, rook, "open gift box")
        assert ("The ribbon is charmed shut. The tag reads: for Kess "
                "only." in out)
        assert box.has_tag("closed")
        out = await do(sim, bilda, "open gift box")
        assert ("The ribbon is charmed shut. The tag reads: for Kess "
                "only." in out)

        # Hand it over; the recipient unwraps with fanfare.
        await do(sim, bilda, "give gift box to Kess")
        sim.seen(rook)
        out = await do(sim, kess, "open gift box")
        assert ("The ribbon leaps free! Inside: silver locket -- with "
                "love from Bilda." in out)
        assert ("The ribbon leaps free as Kess opens the gift box!"
                in sim.seen(rook))
        assert not box.has_tag("closed")

        out = await do(sim, kess, "get silver locket from gift box")
        assert "You pick up a silver locket." in out

        # Unwrapped, the tag clears and the box is an ordinary container.
        out = await do(sim, kess, "look gift box")
        assert any("The ribbon hangs loose; the tag is blank." in line
                   for line in out)
        await do(sim, kess, "close gift box")
        out = await do(sim, rook, "open gift box")
        assert "You open the gift box." in out

    async def test_addressing_a_stranger_fails_softly(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, GIFTBOX_BUILD)
        out = await do(sim, bilda, "address gift box to Zanzibar")
        assert "You find no one by that name to address it to." in out


# =========================================================================
# 013. Fortune teller booth — docs/showcase/013_fortune_teller.md
# =========================================================================

FORTUNE_BUILD = [
    "@create Zoltar",
    "drop Zoltar",
    "@desc Zoltar = A glass cabinet housing a turbaned automaton, its "
    'waxen hand hovering over a deck of cards. [[result = f"The brass '
    "counter reads {V('told', 0)} fortunes told.\"]]",
    "@set Zoltar/cost = 5",
    '@set Zoltar/fortunes = ["You will take a journey your boots '
    'already suspect.", "Beware a door that is polite to you.", '
    '"Money finds you when you stop watching for it.", "An old debt '
    'returns wearing a new face."]',
    "@set Zoltar/on_payment = cost = V('cost', 5); paid = "
    "credits(me) - V('ledger', 0); f = V('fortunes', []); "
    "ok = paid >= cost and bool(f); "
    "(transfer_credits(me, enactor, paid - cost), incr('told'), "
    "remit(here, \"Zoltar's "
    "eyes flare. Gears grind behind the glass, and a stiff card drops "
    "into the brass tray.\"), [(set_attr(c, 'desc_extras', [['', "
    "'ZOLTAR SPEAKS:'], ['', chr(34) + f[rand(0, len(f) - 1)] + "
    "chr(34)], ['', f'Lucky numbers: {rand(1, 99)} and "
    "{rand(1, 99)}.']]), pemit(enactor, 'You lift the fortune "
    "card from the tray.')) for c in [create_obj('a printed fortune "
    "card', tags=['thing', 'no_group'], location=enactor)]]) if ok "
    "else (transfer_credits(me, enactor, paid), pemit(enactor, f'A "
    "fortune costs {cost} credits. The coins clatter "
    "back.')); set_attr(me, 'ledger', credits(me))",
]


class TestFortuneTeller:

    async def test_coin_op_fortunes(self, sim, pinned_rand):
        room, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=room)
        await build(sim, bilda, FORTUNE_BUILD)
        await build(sim, bilda, ["@eval adjust_credits(me, 20); "
                                 "result = credits(me)"])
        zoltar = find_one(sim, "Zoltar")
        sim.seen(kess)

        # Underpay: refunded in full, with the price quoted.
        out = await do(sim, bilda, "pay 3 to Zoltar")
        assert "A fortune costs 5 credits. The coins clatter back." in out
        assert get_credits(bilda) == 20
        assert get_credits(zoltar) == 0

        # Pay the fee (rand pinned to 2 -> fortune index 2, luckies 2).
        pinned_rand["value"] = 2
        out = await do(sim, bilda, "pay 5 to Zoltar")
        assert "You lift the fortune card from the tray." in out
        assert ("Zoltar's eyes flare. Gears grind behind the glass, and "
                "a stiff card drops into the brass tray." in sim.seen(kess))
        assert get_credits(bilda) == 15
        assert get_credits(zoltar) == 5

        card = find_one(sim, "a printed fortune card")
        assert card.location is bilda
        out = await do(sim, bilda, "look fortune card")
        joined = "\n".join(out)
        assert "ZOLTAR SPEAKS:" in joined
        assert '"Money finds you when you stop watching for it."' in joined
        assert "Lucky numbers: 2 and 2." in joined

        # Overpay: change clatters into the tray with the card.
        pinned_rand["value"] = 1
        out = await do(sim, bilda, "pay 9 to Zoltar")
        assert "You lift the fortune card from the tray." in out
        assert get_credits(bilda) == 10   # 15 - 9 + 4 change
        assert get_credits(zoltar) == 10

        # The counter on the cabinet keeps score.
        out = await do(sim, bilda, "look Zoltar")
        assert any("The brass counter reads 2 fortunes told." in line
                   for line in out)

        # Each card is its own object with its own fortune.
        cards = sim.store.find_cached(name="a printed fortune card")
        assert len(cards) == 2


# =========================================================================
# Docs <-> tests sync — the transcripts above must match the tutorials
# =========================================================================

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

DOC_TRANSCRIPTS = {
    "003_jukebox.md": JUKEBOX_BUILD,
    "004_atm_terminal.md": ATM_BUILD_CORE + ATM_BUILD_TERMINAL
    + ATM_BUILD_BRANCH,
    "006_flashlight.md": FLASHLIGHT_BUILD,
    "007_voice_recorder.md": RECORDER_BUILD,
    "008_camera.md": CAMERA_BUILD,
    "009_music_box.md": MUSICBOX_BUILD,
    "010_typewriter.md": TYPEWRITER_BUILD,
    "011_mirror.md": MIRROR_BUILD + MIRROR_PROPS,
    "012_gift_box.md": GIFTBOX_BUILD,
    "013_fortune_teller.md": FORTUNE_BUILD,
}


def test_tutorial_docs_contain_the_exact_tested_command_lines():
    """Every Build-it line exercised above appears verbatim in its doc,
    so the tutorials can never drift from what the tests prove works."""
    for doc_name, lines in DOC_TRANSCRIPTS.items():
        text = (DOCS / doc_name).read_text(encoding="utf-8")
        for line in lines:
            assert line in text, (
                f"{doc_name} is missing a tested tutorial line:\n{line}")
