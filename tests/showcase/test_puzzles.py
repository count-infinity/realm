"""
Showcase verification — Puzzles & Mechanisms (checklist items 209-218).

Verifies the standalone tutorials in docs/showcase/ (209_lever_combination.md
through 218_puzzle_reset.md) by driving a real in-process world —
realm.testing.Simulator wires the same store / propagation / scripting /
dispatcher stack a live GameServer does — with each tutorial's EXACT
command lines (raw input in, session output out). Every command line in a
tutorial's "Build it" section is exercised here, and the sync test at the
bottom keeps the transcripts from drifting from the docs.

Determinism:
- Checks (the `search` command in 216/217) run through a pluggable resolver
  that succeeds iff effective skill >= 10, margin = effective - 10 — the
  same convention as tests/test_heist.py / test_traps_devices.py. So a
  searcher at Observation 13 clears conceal_difficulty <= 3 and no more.
- `wait()` chains (the Simon flashes, the escape-room countdown) run on the
  Simulator's virtual clock: the builds set the beat/interval to 0 so a
  pumped `tick_waits()` fires the due waits immediately.
- `on_tick` (the shifting maze) is driven by `run_object_script(warden,
  'on_tick')` — exactly what the `script_ticker` behavior calls, run as the
  warden, deterministically.
- `prompt()` wizards (keypad, riddle-via-prompt, Simon, escape keypad)
  answer through the session's captured input handler.
- `ON_RESET` (218) is fired with `fire_event`, the event the `zone_reset`
  behavior raises when a zone is due and empty.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import realm.behaviors  # noqa: F401 — registers script_ticker / zone_reset
from realm.core.checks import CheckResult, set_check_resolver, skill_level
from realm.core.events import fire_event
from realm.testing import Simulator


def level_resolver(obj, skill, modifier):
    effective = skill_level(obj, skill) + modifier
    return CheckResult(
        success=effective >= 10,
        margin=effective - 10,
        roll=10,
        effective=effective,
        skill=skill,
    )


BUILD_RED_FLAGS = (
    "Unknown command", "Usage:", "not found", "Script error",
    "can't", "don't", "No permission",
)


@pytest.fixture
def sim():
    simulator = Simulator()
    set_check_resolver(level_resolver)
    # GameServer wires the session manager at startup; the Simulator leaves
    # it to the test (prompt() needs it to find player sessions).
    simulator.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(simulator._sessions.values()))
    yield simulator
    set_check_resolver(None)
    simulator.close()


# --- Harness -------------------------------------------------------------------


async def run_lines(sim, player, lines):
    """Drive raw command lines through the dispatcher, re-pinning the
    deterministic resolver after each (a build's @reload would re-install
    the game's dice resolver — none of these builds do, but it's cheap
    insurance and matches the sibling suites)."""
    for line in lines:
        await sim.do(player, line)
        set_check_resolver(level_resolver)


async def build(sim, lines, **builder_attrs):
    """Run one tutorial's Build-it transcript as a builder from Limbo."""
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo, **builder_attrs)
    builder.add_tag("builder")
    await run_lines(sim, builder, lines)
    out = "\n".join(sim.seen(builder))
    for flag in BUILD_RED_FLAGS:
        assert flag not in out, f"build tripped {flag!r}:\n{out}"
    return builder


def room(sim, name):
    matches = [o for o in sim.store.find_cached(name=name) if o.has_tag("room")]
    assert matches, f"no room named {name!r}"
    return matches[0]


def obj(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no object named {name!r}"
    return matches[0]


def objs(sim, name):
    return sim.store.find_cached(name=name)


def text(sim, player):
    return "\n".join(sim.seen(player))


async def answer(sim, player, line):
    """Answer a pending prompt() wizard with the player's next line."""
    session = sim.session(player)
    handler = session.input_handler
    assert handler is not None, "no prompt() is pending for this player"
    await handler(session, line)
    return text(sim, player)


async def drain_waits(sim, times=10):
    """Pump the virtual clock: fire every wait already due (beat/interval
    are zeroed in the tests that use this, so due == immediately)."""
    for _ in range(times):
        await sim.engine.tick_waits()


# --- Build transcripts (verbatim from the docs' "Build it" sections) -----------

# docs/showcase/209_lever_combination.md
BUILD_209 = [
    '@dig Reliquary Hall = hall, out',
    'hall',
    '@dig Inner Vault = vault gate, hall',
    '@desc Inner Vault = A bare stone cell. Whatever the reliquary was guarding sits on a plinth in the centre.',
    '@tag vault gate = closed',
    '@set vault gate/locked = true',
    '@set vault gate/locked_msg = The vault gate has no handle -- only the levers move it.',
    '@create crimson lever',
    'drop crimson lever',
    '@tag crimson lever = lever',
    '@create azure lever',
    'drop azure lever',
    '@tag azure lever = lever',
    '@create emerald lever',
    'drop emerald lever',
    '@tag emerald lever = lever',
    '@create amber lever',
    'drop amber lever',
    '@tag amber lever = lever',
    '@create lock mechanism',
    'drop lock mechanism',
    '@desc lock mechanism = A brass reader plate wired to the levers. Engraved above it: PULL THE LEVERS IN THE ORDER OF THE DAWN.',
    '@set lock mechanism/code = crimson azure emerald',
    '@attr lock mechanism/code = secret',
    "@set lock mechanism/cmd_pull = $pull *: lev = get(trim(arg0)); (pemit(enactor, 'There is no such lever to pull here.') if not (lev and has_tag(lev, 'lever') and loc(lev) == loc(me)) else (color := replace(name(lev), ' lever', ''), seq := (V('entered') or []) + [color], code := str(V('code')).split(), full := len(seq) >= len(code), (set_attr(me, 'entered', []), (remit(loc(me), 'Tumblers slam home deep in the wall -- the vault gate grinds open!'), remove_tag(get('vault gate'), 'closed')) if seq == code else remit(loc(me), 'A brazen buzzer blares. Every lever springs back to neutral.')) if full else (set_attr(me, 'entered', seq), remit(loc(me), 'The ' + color + ' lever thunks down. Something heavy shifts behind the wall.')))[-1])",
]

# docs/showcase/210_keypad_code.md
BUILD_210 = [
    '@dig Fabrication Lab = lab, out',
    'lab',
    '@dig The Cleanroom = clean gate, lab',
    '@desc The Cleanroom = A white cell under harsh light. The prototype hums on its cradle.',
    '@tag clean gate = closed',
    '@set clean gate/locked = true',
    '@set clean gate/locked_msg = A keypad blinks beside the clean gate. ENTER CODE to proceed.',
    '@create keypad',
    'drop keypad',
    '@desc keypad = A backlit numeric keypad, twelve keys worn shiny. A label reads: AUTHORIZED PERSONNEL. ENTER CODE.',
    '@set keypad/code = 4815',
    '@attr keypad/code = secret',
    "@set keypad/cmd_enter = $enter code: prompt(enactor, 'Enter access code:', 'check_code')",
    "@set keypad/check_code = (remove_tag(get('clean gate'), 'closed'), remit(loc(me), 'The keypad chirps green. The clean gate slides open.')) if trim(arg0) == str(V('code')) else pemit(enactor, 'The keypad buzzes red. ACCESS DENIED.')",
    'out',
    '@dig Maintenance Corridor = corridor, lab',
    'corridor',
    '@create maintenance log',
    'drop maintenance log',
    '@desc maintenance log = A greasy clipboard. Halfway down: "Cleanroom access reset to 4815 -- update your badges."',
]

# docs/showcase/211_riddle_door.md
BUILD_211 = [
    '@dig The Sphinx Landing = landing, out',
    'landing',
    '@dig The Hidden Shrine = sphinx arch, landing',
    '@desc The Hidden Shrine = A moss-soft chamber. Water drips somewhere, echoing.',
    '@tag sphinx arch = closed',
    '@set sphinx arch/locked = true',
    '@set sphinx arch/locked_msg = The arch is solid rock. The sphinx must be answered, not forced.',
    '@create stone sphinx',
    'drop stone sphinx',
    '@desc stone sphinx = A basalt sphinx blocks the arch. It murmurs: "I speak without a mouth and hear without an ear. I have no body, but I come alive with the wind. What am I?" (ANSWER <your reply>.)',
    '@set stone sphinx/answers = echo|voice',
    '@set stone sphinx/cmd_answer = $answer *: raw = \' \'.join(trim(arg0).lower().split()); clean = \'\'.join([c for c in raw if c.isalnum() or c == \' \']); norm = \' \'.join([w for w in clean.split() if w not in (\'a\', \'an\', \'the\')]); (remove_tag(get(\'sphinx arch\'), \'closed\'), remit(loc(me), \'The sphinx inclines its head. The arch grinds open.\')) if norm in str(V(\'answers\')).split(\'|\') else pemit(enactor, \'The sphinx is unmoved. "That is not the word."\')',
]

# docs/showcase/212_weight_plate.md
BUILD_212 = [
    '@dig The Trial Chamber = chamber, out',
    'chamber',
    '@dig The Prize Room = prize gate, chamber',
    '@desc The Prize Room = A small vault. A single reliquary waits on a pedestal.',
    '@tag prize gate = closed',
    '@set prize gate/locked = true',
    '@set prize gate/locked_msg = The prize gate is seamless stone. The plates in the floor must be satisfied.',
    '@create pressure plate',
    'drop pressure plate',
    '@set pressure plate/container = true',
    '@set pressure plate/wants = heavy',
    '@desc pressure plate = A broad iron plate, sprung to sink under real weight.',
    '@create feather plate',
    'drop feather plate',
    '@set feather plate/container = true',
    '@set feather plate/wants = light',
    '@desc feather plate = A gossamer plate that trembles at a breath -- too much weight would jam it.',
    '@create balance mechanism',
    'drop balance mechanism',
    '@desc balance mechanism = A counterweight rig linked to the floor plates. LOAD <thing> ONTO <plate> / UNLOAD <thing> FROM <plate>.',
    "@set balance mechanism/recheck = ok = all([get_attr(pl, 'load') and has_tag(get(str(get_attr(pl, 'load'))), get_attr(pl, 'wants')) for pl in [get('pressure plate'), get('feather plate')]]); g = get('prize gate'); (remove_tag(g, 'closed'), remit(loc(me), 'Counterweights settle with a boom. The prize gate swings open.')) if ok and has_tag(g, 'closed') else ((add_tag(g, 'closed'), remit(loc(me), 'The balance lurches. The prize gate slams shut.')) if not ok and not has_tag(g, 'closed') else None)",
    "@set balance mechanism/cmd_load = $load * onto *: it = get(trim(arg0)); pl = get(trim(arg1)); (pemit(enactor, 'You are not holding that.') if not (it and loc(it) == enactor) else (pemit(enactor, 'There is no such plate here.') if not (pl and get_attr(pl, 'wants') and loc(pl) == loc(me)) else (set_attr(pl, 'load', '#' + it.id), move_to(it, pl), remit(loc(me), name(enactor) + ' sets ' + name(it) + ' on ' + name(pl) + '.'), eval_attr(me, 'recheck'))))",
    "@set balance mechanism/cmd_unload = $unload * from *: pl = get(trim(arg1)); it = get(trim(arg0)); (pemit(enactor, 'That is not on that plate.') if not (it and pl and loc(it) == pl) else (del_attr(pl, 'load'), move_to(it, enactor), remit(loc(me), name(enactor) + ' lifts ' + name(it) + ' off ' + name(pl) + '.'), eval_attr(me, 'recheck')))",
    '@create iron ingot',
    '@tag iron ingot = heavy',
    'drop iron ingot',
    '@create dried feather',
    '@tag dried feather = light',
    'drop dried feather',
    '@create clay shard',
    'drop clay shard',
]

# docs/showcase/213_power_routing.md
BUILD_213 = [
    '@dig Reactor Control = reactor, out',
    'reactor',
    '@dig The Core Bay = blast shield, reactor',
    '@desc The Core Bay = The reactor core throbs behind shielded glass. The prize: an intact power cell.',
    '@tag blast shield = closed',
    '@set blast shield/locked = true',
    '@set blast shield/locked_msg = The blast shield is sealed. Route the grid to full power first.',
    '@create wall schematic',
    'drop wall schematic',
    '@desc wall schematic = A grease-penciled diagram. Junction 2\'s main line is slashed out and marked FAULT. Scrawled beside it: "Send 1 and 3 to BACKUP, keep 2 on MAIN, and she\'ll light."',
    '@create power console',
    'drop power console',
    '@desc power console = A panel of three relay switches feeding the main and backup buses. ROUTE <1-3> TO <MAIN|BACKUP>, or GRID for status.',
    '@set power console/j1 = a',
    '@set power console/j2 = a',
    '@set power console/j3 = a',
    '@set power console/solution = b a b',
    "@set power console/check = result = (V('j1') + ' ' + V('j2') + ' ' + V('j3') == str(V('solution')))",
    "@set power console/sync = live = eval_attr(me, 'check'); g = get('blast shield'); (remove_tag(g, 'closed'), remit(loc(me), 'The grid hums up to full power -- the blast shield retracts.')) if live and has_tag(g, 'closed') else ((add_tag(g, 'closed'), remit(loc(me), 'Power gutters out. The blast shield drops.')) if not live and not has_tag(g, 'closed') else None)",
    "@set power console/cmd_route = $route * to *: n = trim(arg0); v = switch(trim(arg1).lower(), 'main', 'a', 'backup', 'b', ''); (pemit(enactor, 'Try ROUTE <1-3> TO <MAIN or BACKUP>.') if n not in ('1', '2', '3') or not v else (set_attr(me, 'j' + n, v), remit(loc(me), 'Relay ' + n + ' swings to the ' + trim(arg1).lower() + ' bus.'), eval_attr(me, 'sync')))",
    "@set power console/cmd_grid = $grid: [pemit(enactor, f'Junction {n}: ' + switch(V('j' + str(n)), 'a', 'MAIN bus', 'b', 'BACKUP bus')) for n in (1, 2, 3)]; pemit(enactor, 'GRID STATUS: ' + ('ONLINE' if eval_attr(me, 'check') else 'FAULT'))",
]

# docs/showcase/214_simon.md
BUILD_214 = [
    '@dig The Signal Chamber = signal room, out',
    'signal room',
    '@dig The Sealed Cache = vault hatch, chamber',
    '@desc The Sealed Cache = A dry vault. On a shelf: a data core worth the trouble.',
    '@tag vault hatch = closed',
    '@set vault hatch/locked = true',
    '@set vault hatch/locked_msg = The vault hatch is smooth steel. The panel must be satisfied.',
    '@create simon panel',
    'drop simon panel',
    '@desc simon panel = A grid of four coloured pads -- red, green, blue, amber -- over a single START key. PLAY SIMON to begin.',
    '@set simon panel/pattern = red green blue amber',
    '@set simon panel/beat = 2',
    "@set simon panel/cmd_play = $play simon: (pemit(enactor, 'The panel is busy with someone else.') if V('busy') else (set_attr(me, 'busy', 1), set_attr(me, 'level', 1), set_attr(me, 'player', '#' + enactor.id), set_attr(me, 'flash_i', 0), remit(loc(me), name(enactor) + ' presses START -- the panel powers up. Watch the lights!'), set_attr(me, 'pending', wait(V('beat', 1), 'trigger me/signal'))))",
    "@set simon panel/signal = seq = str(V('pattern')).split()[0:V('level', 1)]; i = V('flash_i', 0); (prompt(get(V('player')), 'Repeat the sequence (e.g. RED GREEN):', 'judge') if i >= len(seq) else (remit(loc(me), 'The panel flashes ' + seq[i].upper() + '.'), incr('flash_i'), set_attr(me, 'pending', wait(V('beat', 1), 'trigger me/signal'))))",
    "@set simon panel/judge = want = ' '.join(str(V('pattern')).split()[0:V('level', 1)]); got = ' '.join(trim(arg0).lower().split()); full = len(str(V('pattern')).split()); (set_attr(me, 'busy', 0), remit(loc(me), 'BUZZ -- the pattern was wrong. The panel goes dark.')) if got != want else ((set_attr(me, 'busy', 0), remove_tag(get('vault hatch'), 'closed'), remit(loc(me), 'A rising chime -- the full sequence! The vault hatch clicks open.')) if V('level', 1) >= full else (set_attr(me, 'level', V('level', 1) + 1), set_attr(me, 'flash_i', 0), remit(loc(me), 'Correct! The sequence grows longer. Watch again.'), set_attr(me, 'pending', wait(V('beat', 1), 'trigger me/signal'))))",
]

# docs/showcase/215_shifting_maze.md
BUILD_215 = [
    '@dig Maze Entrance = enter maze, out',
    'enter maze',
    '@dig Chamber of Echoes',
    '@dig Chamber of Dust',
    '@dig The Way Out',
    '@teleport me = Chamber of Echoes',
    '@open back = Maze Entrance',
    '@teleport me = Chamber of Dust',
    '@open back = Maze Entrance',
    '@teleport me = The Way Out',
    '@desc The Way Out = Blessed daylight -- the maze spits you out at last.',
    '@open leave = Limbo',
    '@teleport me = Maze Entrance',
    '@create maze warden',
    'drop maze warden',
    '@desc maze warden = A slab of clockwork gears set into the wall, forever turning.',
    "@eval e = get('Chamber of Echoes'); d = get('Chamber of Dust'); w = get('The Way Out'); set_attr(get('maze warden'), 'pool', ['#' + e.id, '#' + d.id, '#' + w.id]); result = 'pool wired'",
    '@create shifting arch',
    '@tag shifting arch = exit',
    'drop shifting arch',
    '@desc shifting arch = A stone archway whose far side shimmers like heat-haze; you can never quite tell where it opens.',
    "@eval set_attr(get('shifting arch'), 'destination', get_attr(get('maze warden'), 'pool')[0][1:]); result = 'arch aimed'",
    "@set maze warden/on_tick = pool = V('pool'); arch = get('shifting arch'); cur = '#' + str(get_attr(arch, 'destination')); nxt = pool[(pool.index(cur) + 1) % len(pool)] if cur in pool else pool[0]; set_attr(arch, 'destination', nxt[1:]); remit(loc(arch), 'The walls grind and the shifting arch swings toward a new chamber.')",
    '@behavior maze warden = script_ticker, interval:15',
]

# docs/showcase/216_escape_room.md
BUILD_216 = [
    '@dig Escape Lobby = lobby, out',
    'lobby',
    '@dig Holding Cell',
    '@teleport me = Holding Cell',
    '@zone here = cell',
    '@tag here = instance_template',
    '@tag here = instance_entry',
    '@desc here = A bare cell, one bench, a heavy hatch. A countdown clock ticks on the wall.',
    '@set here/limit = 3',
    '@set here/beat = 60',
    "@set here/on_enter = (set_attr(me, 'started', 1), set_attr(me, 'count', V('limit', 3)), remit(me, 'A klaxon wails: ' + str(V('limit', 3)) + ' minutes until the cell floods. Find the way out!'), set_attr(me, 'pending', wait(V('beat', 60), 'trigger me/tick'))) if has_tag(enactor, 'player') and enactor != owner(me) and not V('started') else None",
    "@set here/tick = n = V('count', 0) - 1; (remit(me, 'TIME UP. Water roars in through the vents.') if n <= 0 else (set_attr(me, 'count', n), remit(me, str(n) + ' minutes remain...'), set_attr(me, 'pending', wait(V('beat', 60), 'trigger me/tick'))))",
    '@create scratched plate',
    'drop scratched plate',
    '@set scratched plate/conceal_difficulty = 2',
    '@set scratched plate/reveal_msg = Scratched under the bench, tiny numbers: 7291.',
    '@tag scratched plate = invisible',
    '@create cell keypad',
    'drop cell keypad',
    '@desc cell keypad = A keypad wired to the hatch bolts. PUNCH to enter a code.',
    '@set cell keypad/code = 7291',
    '@attr cell keypad/code = secret',
    "@set cell keypad/cmd_punch = $punch: prompt(enactor, 'Enter the code you found:', 'check')",
    "@set cell keypad/check = hs = [o for o in contents(loc(me)) if has_tag(o, 'exit') and name(o) == 'escape hatch']; (remove_tag(hs[0], 'closed'), remit(loc(me), 'The keypad flashes green -- the escape hatch unbolts!')) if hs and trim(arg0) == str(V('code')) else pemit(enactor, 'The keypad flashes red. Nothing happens.')",
    '@open escape hatch = Escape Lobby',
    '@tag escape hatch = closed',
    '@set escape hatch/locked = true',
    '@set escape hatch/locked_msg = The escape hatch is bolted from a keypad beside it.',
    '@teleport me = Escape Lobby',
    '@create cell door',
    '@tag cell door = exit',
    'drop cell door',
    '@set cell door/dest_resolver = instance',
    '@set cell door/instance_template = cell',
    '@set cell door/instance_mode = solo',
    '@set cell door/instance_ttl = 600',
]

# docs/showcase/217_hidden_object_search.md
BUILD_217 = [
    '@dig The Study = study, out',
    'study',
    "@desc The Study = A scholar's study gone to dust: a great desk, sagging shelves, a cracked oil painting.",
    '@create brass key',
    'drop brass key',
    '@desc brass key = A small brass key, filmed with dust.',
    '@set brass key/conceal_difficulty = 1',
    '@set brass key/reveal_msg = Something glints behind the desk leg -- a brass key in the dust!',
    '@tag brass key = invisible',
    '@create leather ledger',
    'drop leather ledger',
    '@desc leather ledger = A slim ledger of cramped figures.',
    '@set leather ledger/conceal_difficulty = 3',
    '@set leather ledger/reveal_msg = One book spine is false -- a leather ledger slides out from behind it.',
    '@tag leather ledger = invisible',
    '@create wall cache',
    'drop wall cache',
    '@desc wall cache = A palm-sized cavity behind the painting, lined with felt.',
    '@set wall cache/conceal_difficulty = 5',
    '@set wall cache/reveal_msg = Your fingertips catch a seam in the plaster -- a wall cache springs open!',
    '@tag wall cache = invisible',
]

# docs/showcase/218_puzzle_reset.md
BUILD_218 = [
    '@dig The Trial Room = trial, out',
    'trial',
    '@zone here = trialzone',
    '@dig The Reward Vault = trial gate, trial',
    '@desc The Reward Vault = A modest vault. The reward for turning the crank sits on a shelf.',
    '@tag trial gate = closed',
    '@set trial gate/locked = true',
    '@set trial gate/locked_msg = The trial gate is sealed. Turn the crank.',
    '@create puzzle console',
    'drop puzzle console',
    '@desc puzzle console = A brass control console. TURN CRANK to work the gate; RESET PUZZLE to restore it.',
    '@zone/master puzzle console = trialzone',
    "@set puzzle console/restore = g = get('trial gate'); (add_tag(g, 'closed') if not has_tag(g, 'closed') else None); del_attr(me, 'progress'); (create_obj('brass crank', ['thing', 'crank'], location=loc(me)) if not [o for o in contents(loc(me)) if has_tag(o, 'crank')] else None); remit(loc(me), 'Gears clunk. The trial gate re-seals and the brass crank is back in its bracket.')",
    "@set puzzle console/cmd_crank = $crank: (pemit(enactor, 'There is no crank here to turn.') if not [o for o in contents(loc(me)) if has_tag(o, 'crank')] else (remove_tag(get('trial gate'), 'closed'), set_attr(me, 'progress', 'solved'), remit(loc(me), name(enactor) + ' turns the crank -- the trial gate grinds open.')))",
    "@set puzzle console/cmd_reset = $reset puzzle: eval_attr(me, 'restore')",
    "@set puzzle console/on_reset = eval_attr(me, 'restore')",
    '@behavior puzzle console = zone_reset',
    '@set puzzle console/reset_interval = 300',
    '@create brass crank',
    '@tag brass crank = crank',
    'drop brass crank',
]



# --- 209. Lever combination ----------------------------------------------------


class TestLeverCombination:

    async def test_wrong_order_resets_right_order_opens(self, sim):
        await build(sim, BUILD_209)
        assert obj(sim, "vault gate").has_tag("closed")
        zeke = sim.player("Zeke", location=room(sim, "Reliquary Hall"))

        # The gate resists the obvious approach.
        await sim.do(zeke, "open vault gate")
        assert "no handle" in text(sim, zeke)

        # Wrong order buzzes and clears all progress.
        await sim.do(zeke, "pull crimson lever")
        await sim.do(zeke, "pull emerald lever")
        sim.seen(zeke)
        await sim.do(zeke, "pull azure lever")
        assert "buzzer blares" in text(sim, zeke)
        assert obj(sim, "vault gate").has_tag("closed")

        # crimson, azure, emerald opens it.
        await sim.do(zeke, "pull crimson lever")
        await sim.do(zeke, "pull azure lever")
        sim.seen(zeke)
        await sim.do(zeke, "pull emerald lever")
        assert "grinds open" in text(sim, zeke)
        assert not obj(sim, "vault gate").has_tag("closed")
        await sim.do(zeke, "vault gate")
        assert zeke.location is room(sim, "Inner Vault")

    async def test_decoy_and_unknown_levers(self, sim):
        await build(sim, BUILD_209)
        zeke = sim.player("Zeke", location=room(sim, "Reliquary Hall"))

        await sim.do(zeke, "pull ghost lever")
        assert "no such lever" in text(sim, zeke)

        # The amber decoy is never in a valid sequence.
        await sim.do(zeke, "pull crimson lever")
        await sim.do(zeke, "pull azure lever")
        sim.seen(zeke)
        await sim.do(zeke, "pull amber lever")
        assert "buzzer blares" in text(sim, zeke)
        assert obj(sim, "vault gate").has_tag("closed")


# --- 210. Keypad code ----------------------------------------------------------


class TestKeypadCode:

    async def test_code_gates_the_door(self, sim):
        await build(sim, BUILD_210)
        zeke = sim.player("Zeke", location=room(sim, "Fabrication Lab"))

        await sim.do(zeke, "open clean gate")
        assert "ENTER CODE" in text(sim, zeke)

        await sim.do(zeke, "enter code")
        assert "Enter access code:" in text(sim, zeke)
        out = await answer(sim, zeke, "0000")
        assert "ACCESS DENIED" in out
        assert obj(sim, "clean gate").has_tag("closed")

        await sim.do(zeke, "enter code")
        out = await answer(sim, zeke, "4815")
        assert "slides open" in out
        assert not obj(sim, "clean gate").has_tag("closed")
        await sim.do(zeke, "clean gate")
        assert zeke.location is room(sim, "The Cleanroom")

    async def test_code_is_secret_to_strangers(self, sim):
        await build(sim, BUILD_210)
        zeke = sim.player("Zeke", location=room(sim, "Fabrication Lab"))
        stolen, _err = await sim.eval(
            zeke, "result = get_attr(get('keypad'), 'code')")
        assert stolen is None


# --- 211. Riddle door ----------------------------------------------------------


class TestRiddleDoor:

    async def test_wrong_answer_stays_shut_fuzzy_answer_opens(self, sim):
        await build(sim, BUILD_211)
        zeke = sim.player("Zeke", location=room(sim, "The Sphinx Landing"))

        await sim.do(zeke, "answer a mountain")
        assert "unmoved" in text(sim, zeke)
        assert obj(sim, "sphinx arch").has_tag("closed")

        await sim.do(zeke, "answer An Echo!")
        assert "grinds open" in text(sim, zeke)
        assert not obj(sim, "sphinx arch").has_tag("closed")
        await sim.do(zeke, "sphinx arch")
        assert zeke.location is room(sim, "The Hidden Shrine")

    @pytest.mark.parametrize("phrasing", ["the echo", "ECHO", "voice"])
    async def test_phrasing_variants_all_pass(self, sim, phrasing):
        await build(sim, BUILD_211)
        zeke = sim.player("Zeke", location=room(sim, "The Sphinx Landing"))
        await sim.do(zeke, f"answer {phrasing}")
        assert "grinds open" in text(sim, zeke)
        assert not obj(sim, "sphinx arch").has_tag("closed")


# --- 212. Weight-plate puzzle --------------------------------------------------


class TestWeightPlate:

    async def test_both_plates_open_and_unload_recloses(self, sim):
        await build(sim, BUILD_212)
        chamber = room(sim, "The Trial Chamber")
        zeke = sim.player("Zeke", location=chamber)
        await sim.do(zeke, "get iron ingot")
        await sim.do(zeke, "get dried feather")

        await sim.do(zeke, "load iron ingot onto pressure plate")
        sim.seen(zeke)
        assert obj(sim, "prize gate").has_tag("closed")   # one plate isn't enough

        await sim.do(zeke, "load dried feather onto feather plate")
        assert "swings open" in text(sim, zeke)
        assert not obj(sim, "prize gate").has_tag("closed")
        await sim.do(zeke, "prize gate")
        assert zeke.location is room(sim, "The Prize Room")

        await sim.do(zeke, "chamber")
        sim.seen(zeke)
        await sim.do(zeke, "unload iron ingot from pressure plate")
        assert "slams shut" in text(sim, zeke)
        assert obj(sim, "prize gate").has_tag("closed")

    async def test_decoy_object_does_not_satisfy(self, sim):
        await build(sim, BUILD_212)
        chamber = room(sim, "The Trial Chamber")
        zeke = sim.player("Zeke", location=chamber)
        await sim.do(zeke, "get clay shard")
        await sim.do(zeke, "get dried feather")

        await sim.do(zeke, "load clay shard onto pressure plate")
        await sim.do(zeke, "load dried feather onto feather plate")
        sim.seen(zeke)
        assert obj(sim, "prize gate").has_tag("closed")   # shard is not heavy

        await sim.do(zeke, "get iron ingot")
        await sim.do(zeke, "load iron ingot onto pressure plate")
        assert "swings open" in text(sim, zeke)


# --- 213. Power routing puzzle -------------------------------------------------


class TestPowerRouting:

    async def test_route_to_solution_opens_and_break_reseals(self, sim):
        await build(sim, BUILD_213)
        reactor = room(sim, "Reactor Control")
        zeke = sim.player("Zeke", location=reactor)

        await sim.do(zeke, "grid")
        assert "FAULT" in text(sim, zeke)

        await sim.do(zeke, "route 1 to backup")
        await sim.do(zeke, "route 3 to backup")
        assert "blast shield retracts" in text(sim, zeke)
        assert not obj(sim, "blast shield").has_tag("closed")
        await sim.do(zeke, "blast shield")
        assert zeke.location is room(sim, "The Core Bay")

        await sim.do(zeke, "reactor")
        sim.seen(zeke)
        await sim.do(zeke, "route 2 to backup")
        assert "blast shield drops" in text(sim, zeke)
        assert obj(sim, "blast shield").has_tag("closed")

    async def test_grid_readout_reflects_state(self, sim):
        await build(sim, BUILD_213)
        zeke = sim.player("Zeke", location=room(sim, "Reactor Control"))
        await sim.do(zeke, "route 1 to backup")
        sim.seen(zeke)
        await sim.do(zeke, "grid")
        out = text(sim, zeke)
        assert "Junction 1: BACKUP bus" in out
        assert "Junction 2: MAIN bus" in out
        assert "GRID STATUS: FAULT" in out


# --- 214. Simon sequence -------------------------------------------------------


class TestSimon:

    async def test_full_sequence_opens_hatch(self, sim):
        builder = await build(sim, BUILD_214)
        await run_lines(sim, builder, ["@set simon panel/beat = 0"])
        zeke = sim.player("Zeke", location=room(sim, "The Signal Chamber"))

        await sim.do(zeke, "play simon")
        await drain_waits(sim)
        assert "The panel flashes RED." in text(sim, zeke)

        await answer(sim, zeke, "red")
        await drain_waits(sim)
        await answer(sim, zeke, "red green")
        await drain_waits(sim)
        await answer(sim, zeke, "red green blue")
        await drain_waits(sim)
        out = await answer(sim, zeke, "red green blue amber")
        assert "vault hatch clicks open" in out
        assert not obj(sim, "vault hatch").has_tag("closed")
        await sim.do(zeke, "vault hatch")
        assert zeke.location is room(sim, "The Sealed Cache")

    async def test_wrong_echo_ends_the_run(self, sim):
        builder = await build(sim, BUILD_214)
        await run_lines(sim, builder, ["@set simon panel/beat = 0"])
        zeke = sim.player("Zeke", location=room(sim, "The Signal Chamber"))

        await sim.do(zeke, "play simon")
        await drain_waits(sim)
        out = await answer(sim, zeke, "green")
        assert "goes dark" in out
        assert obj(sim, "vault hatch").has_tag("closed")
        assert not obj(sim, "simon panel").db.get("busy")


# --- 215. Shifting maze --------------------------------------------------------


class TestShiftingMaze:

    async def test_arch_cycles_through_the_pool(self, sim):
        await build(sim, BUILD_215)
        warden = obj(sim, "maze warden")
        arch = obj(sim, "shifting arch")
        echoes = room(sim, "Chamber of Echoes")
        dust = room(sim, "Chamber of Dust")
        wayout = room(sim, "The Way Out")

        assert arch.db.get("destination") == echoes.id
        await sim.engine.run_object_script(warden, "on_tick")
        assert arch.db.get("destination") == dust.id
        await sim.engine.run_object_script(warden, "on_tick")
        assert arch.db.get("destination") == wayout.id    # the goal is in the pool
        await sim.engine.run_object_script(warden, "on_tick")
        assert arch.db.get("destination") == echoes.id    # and it wraps

    async def test_traversal_back_exits_and_escape(self, sim):
        await build(sim, BUILD_215)
        entrance = room(sim, "Maze Entrance")
        warden = obj(sim, "maze warden")
        zeke = sim.player("Zeke", location=entrance)

        await sim.do(zeke, "shifting arch")
        assert zeke.location is room(sim, "Chamber of Echoes")
        await sim.do(zeke, "back")
        assert zeke.location is entrance         # no dead ends

        # Aim the arch at the exit and walk out — always reachable.
        await sim.engine.run_object_script(warden, "on_tick")   # -> Dust
        await sim.engine.run_object_script(warden, "on_tick")   # -> The Way Out
        await sim.do(zeke, "shifting arch")
        assert zeke.location is room(sim, "The Way Out")
        await sim.do(zeke, "leave")
        assert zeke.location is room(sim, "Limbo")


# --- 216. Escape room ----------------------------------------------------------


ZERO_THE_CLOCK = [
    "@teleport me = Holding Cell",
    "@set here/beat = 0",
    "@teleport me = Escape Lobby",
]


class TestEscapeRoom:

    async def test_search_then_code_then_escape(self, sim):
        builder = await build(sim, BUILD_216)
        await run_lines(sim, builder, ZERO_THE_CLOCK)
        lobby = room(sim, "Escape Lobby")
        alice = sim.player("Alice", location=lobby, skill_observation=14)

        await sim.do(alice, "cell door")
        assert alice.location.has_tag("instance_entry")
        assert "klaxon wails" in text(sim, alice)

        await sim.do(alice, "search")
        assert "7291" in text(sim, alice)

        await sim.do(alice, "punch")
        out = await answer(sim, alice, "0000")
        assert "flashes red" in out

        await sim.do(alice, "punch")
        out = await answer(sim, alice, "7291")
        assert "escape hatch unbolts" in out
        await sim.do(alice, "escape hatch")
        assert alice.location is lobby

    async def test_private_copies_and_the_flood(self, sim):
        builder = await build(sim, BUILD_216)
        await run_lines(sim, builder, ZERO_THE_CLOCK)
        lobby = room(sim, "Escape Lobby")
        alice = sim.player("Alice", location=lobby, skill_observation=14)
        cass = sim.player("Cass", location=lobby, skill_observation=14)

        await sim.do(alice, "cell door")
        await sim.do(cass, "cell door")
        # Each party gets a private copy — reset by construction.
        assert alice.location is not cass.location
        assert alice.location.has_tag(f"instance:cell:{alice.id}")
        assert cass.location.has_tag(f"instance:cell:{cass.id}")

        # The countdown floods the cell on its own timer.
        sim.seen(cass)
        await drain_waits(sim)
        assert "TIME UP" in text(sim, cass)


# --- 217. Hidden object search -------------------------------------------------


class TestHiddenObjectSearch:

    async def test_layered_finds_by_skill(self, sim):
        await build(sim, BUILD_217)
        study = room(sim, "The Study")
        scout = sim.player("Scout", location=study, skill_observation=13)

        await sim.do(scout, "search")
        out = text(sim, scout)
        assert "brass key" in out
        assert "leather ledger" in out
        assert not obj(sim, "brass key").has_tag("invisible")
        assert not obj(sim, "leather ledger").has_tag("invisible")
        # The master-concealed cache is beyond Observation 13.
        assert obj(sim, "wall cache").has_tag("invisible")

    async def test_expert_clears_the_room_and_finds_are_real(self, sim):
        await build(sim, BUILD_217)
        study = room(sim, "The Study")
        expert = sim.player("Ada", location=study, skill_observation=16)

        await sim.do(expert, "search")
        assert not obj(sim, "wall cache").has_tag("invisible")
        await sim.do(expert, "get wall cache")
        assert obj(sim, "wall cache").location is expert


# --- 218. Puzzle reset engineering ---------------------------------------------


class TestPuzzleReset:

    async def test_solve_manual_reset_and_stuck_recovery(self, sim):
        await build(sim, BUILD_218)
        trial = room(sim, "The Trial Room")
        zeke = sim.player("Zeke", location=trial)

        await sim.do(zeke, "crank")
        assert "grinds open" in text(sim, zeke)
        assert not obj(sim, "trial gate").has_tag("closed")

        await sim.do(zeke, "reset puzzle")
        assert "re-seals" in text(sim, zeke)
        assert obj(sim, "trial gate").has_tag("closed")
        assert obj(sim, "puzzle console").db.get("progress") is None

        # Stuck state: someone walks off with the crank.
        await sim.do(zeke, "get brass crank")
        cass = sim.player("Cass", location=trial)
        await sim.do(cass, "crank")
        assert "no crank here" in text(sim, cass)

        # Reset re-creates the missing prop — the puzzle can't be bricked.
        await sim.do(cass, "reset puzzle")
        cranks = [o for o in trial.contents if o.has_tag("crank")]
        assert len(cranks) == 1
        await sim.do(cass, "crank")
        assert "grinds open" in text(sim, cass)

    async def test_on_reset_restores_the_puzzle(self, sim):
        await build(sim, BUILD_218)
        trial = room(sim, "The Trial Room")
        console = obj(sim, "puzzle console")
        zeke = sim.player("Zeke", location=trial)

        await sim.do(zeke, "crank")
        assert not obj(sim, "trial gate").has_tag("closed")

        # zone_reset fires this ON_RESET when the zone is due and empty.
        await fire_event(None, console, "event:on_reset")
        assert obj(sim, "trial gate").has_tag("closed")
        assert console.db.get("progress") is None


# =========================================================================
# Docs <-> tests sync — the transcripts above must match the tutorials
# =========================================================================

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

DOC_TRANSCRIPTS = {
    "209_lever_combination.md": BUILD_209,
    "210_keypad_code.md": BUILD_210,
    "211_riddle_door.md": BUILD_211,
    "212_weight_plate.md": BUILD_212,
    "213_power_routing.md": BUILD_213,
    "214_simon.md": BUILD_214,
    "215_shifting_maze.md": BUILD_215,
    "216_escape_room.md": BUILD_216,
    "217_hidden_object_search.md": BUILD_217,
    "218_puzzle_reset.md": BUILD_218,
}


def test_tutorial_docs_contain_the_exact_tested_command_lines():
    """Every Build-it line exercised above appears verbatim in its doc,
    so the tutorials can never drift from what the tests prove works."""
    for doc_name, lines in DOC_TRANSCRIPTS.items():
        doc_text = (DOCS / doc_name).read_text(encoding="utf-8")
        for line in lines:
            assert line in doc_text, (
                f"{doc_name} is missing a tested tutorial line:\n{line}")
