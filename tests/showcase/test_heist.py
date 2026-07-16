"""
Showcase verification — the Heist arc (docs/showcase/arc_heist.md).

Items: 27 secret door, 16 combination safe, 49 landmine, 54 security
camera & monitor, 48 gas bomb, 160 sneaking.

Every command line in each tutorial's "Build it" section is driven
through the real dispatcher (raw input in -> session output out) by a
builder player, exactly as typed in the docs; the plays then exercise
the tutorials' "Try it" flows and assert outcomes.

Dice are removed via the pluggable check resolver (same convention as
tests/test_infiltration.py): a check succeeds iff effective skill >= 10,
margin = effective - 10, so contests go to the higher skill. The @reload
line inside the gas-bomb build re-installs the GURPS resolver, so the
line runner re-pins the deterministic resolver after every command.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from realm.core.checks import CheckResult, set_check_resolver, skill_level
from realm.core.events import reap_expired
from realm.core.perception import stealth_observer
from realm.core.propagation import get_engine as get_propagation_engine
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


# --- Build transcripts (the tutorials' exact "Build it" lines) -----------------

# docs/showcase/027_secret_door.md
BUILD_27 = [
    "@dig The Security Office",
    "@teleport me = The Security Office",
    "@dig Maintenance Corridor = east, west",
    "east",
    "@dig Vault Antechamber",
    "@open loose grate = Vault Antechamber",
    "@desc loose grate = A dented ventilation grate low on the wall, screwed into its frame.",
    "@set loose grate/conceal_difficulty = 2",
    "@set loose grate/reveal_msg = One grate sits loose in its frame -- a crawlway yawns behind it!",
    "@tag loose grate = invisible",
    "@set here/on_enter = g = get('loose grate'); (remove_tag(g, 'invisible'), pemit(enactor, get_attr(g, 'reveal_msg'))) if g and has_tag(g, 'invisible') and has_tag(enactor, 'player') and skill_check(enactor, 'observation', -4) else None",
    "@teleport me = Vault Antechamber",
    "@open duct = Maintenance Corridor",
    "@desc duct = The crawlway back up into the maintenance corridor.",
]

# docs/showcase/016_combination_safe.md
BUILD_16 = [
    "@dig Nexagen Vault = vault door, antechamber",
    "@tag vault door = closed",
    "open vault door",
    "vault door",
    "@create wall safe",
    "@set wall safe/container = true",
    "drop wall safe",
    "@create prototype schematics",
    "put prototype schematics in wall safe",
    "close wall safe",
    "@set wall safe/locked = true",
    "@set wall safe/locked_msg = The safe door doesn't budge. Engraved under the dial: DIAL <NUMBER>.",
    "@set wall safe/lock_skill = lockpicking",
    "@set wall safe/lock_difficulty = 4",
    "@set wall safe/code = 17 4 33",
    "@attr wall safe/code = secret",
    "@set wall safe/cmd_dial = $dial *: seq = (get_attr(me, 'entered') or []) + [trim(arg0)]; code = str(get_attr(me, 'code')).split(); done = len(seq) >= len(code); set_attr(me, 'entered', [] if done else seq); (set_attr(me, 'locked', False), pemit(enactor, 'CLUNK. The last tumbler drops -- the wall safe unlocks.')) if done and seq == code else pemit(enactor, 'Clunk. The dial spins back to zero.' if done else 'Click.')",
    "@set wall safe/cmd_setcode = $setcode: pemit(enactor, 'Only the owner may reset the dial.') if enactor != owner(me) else (pemit(enactor, 'Open the safe first -- the reset switch is inside the door.') if has_tag(me, 'closed') else prompt(enactor, 'New combination (numbers separated by spaces):', 'on_new_code'))",
    "@set wall safe/on_new_code = (set_attr(me, 'code', trim(arg0)), pemit(enactor, 'The tumblers reseat. New combination: ' + trim(arg0))) if trim(arg0) and trim(arg0).replace(' ', '').isdigit() else pemit(enactor, 'Numbers separated by spaces, nothing else. The dial is unchanged.')",
    "@teleport me = The Security Office",
    "@create crumpled note",
    "drop crumpled note",
    "@desc crumpled note = Hurried handwriting: '17 - 4 - 33. Do NOT write this down.'",
]

# docs/showcase/049_landmine.md
BUILD_49 = [
    "@teleport me = Vault Antechamber",
    "@create anti-personnel mine",
    "drop anti-personnel mine",
    "@set anti-personnel mine/armed = 1",
    "@set anti-personnel mine/skill_concealment = 13",
    "@set anti-personnel mine/conceal_difficulty = 3",
    "@set anti-personnel mine/reveal_msg = Dust brushed aside -- a pressure plate, wired and live!",
    "@set anti-personnel mine/on_check = block('It is wedged into the floor -- and armed.') if atype == 'item:on_get' and target == me else None",
    "@set anti-personnel mine/on_enter = x = enactor; (None if not (get_attr(me, 'armed', 0) and (has_tag(x, 'player') or has_tag(x, 'npc')) and x != owner(me)) else (pemit(x, 'You step around the exposed mine.') if not has_tag(me, 'invisible') else ((remove_tag(me, 'invisible'), pemit(x, 'You freeze mid-step -- a pressure plate, right under your boot!')) if contest(x, 'observation', me, 'concealment') else eval_attr(me, 'boom'))))",
    "@set anti-personnel mine/boom = remove_tag(me, 'invisible'); set_attr(me, 'armed', 0); pemit(enactor, 'KA-WHUMP! The floor erupts under you.'); oemit(enactor, name(enactor) + ' sets off a buried mine!'); damage(enactor, roll('2d6'))",
    "@tag anti-personnel mine = invisible",
]

# docs/showcase/054_security_camera.md
BUILD_54 = [
    "@teleport me = The Security Office",
    "@create security monitor",
    "drop security monitor",
    "@desc security monitor = A bank of grainy feeds. WATCH to put an eye on the vault approach; UNWATCH to look away.",
    "@set security monitor/cmd_watch = $watch: ws = get_attr(me, 'watchers') or []; set_attr(me, 'watchers', ws if enactor.id in ws else ws + [enactor.id]); pemit(enactor, 'You settle in at the console. The antechamber feed flickers to life.')",
    "@set security monitor/cmd_unwatch = $unwatch: set_attr(me, 'watchers', [i for i in (get_attr(me, 'watchers') or []) if i != enactor.id]); pemit(enactor, 'You look away from the monitor.')",
    "@teleport me = Vault Antechamber",
    "@create security camera",
    "drop security camera",
    "@desc security camera = A glass eye on a ceiling mount, cable disappearing into the wall.",
    "@set security camera/powered = 1",
    "@set security camera/feed = security monitor",
    "@set security camera/relay = m = get(get_attr(me, 'feed', '')); ws = (get_attr(m, 'watchers') or []) if (m and get_attr(me, 'powered', 1)) else []; live = [w for w in [get('#' + str(i)) for i in ws] if w and loc(w) == loc(m)]; [pemit(w, '[' + name(me) + '] ' + str(arg0)) for w in live]; set_attr(m, 'watchers', [w.id for w in live]) if m and len(live) != len(ws) else None",
    "@set security camera/listen_feed = ^*: eval_attr(me, 'relay', name(enactor) + ' says, \"' + arg0 + '\"') if enactor else None",
    "@set security camera/on_enter = eval_attr(me, 'relay', name(enactor) + ' arrives.') if enactor else None",
    "@set security camera/on_leave = eval_attr(me, 'relay', name(enactor) + ' leaves.') if enactor else None",
    "@set security camera/cmd_cut = $cut *: (set_attr(me, 'powered', 0), remit(loc(me), name(enactor) + ' snips a cable -- the camera light dies.')) if skill_check(enactor, 'electronics', -2) else pemit(enactor, 'Sparks jump; the housing is trickier than it looks.')",
]

# docs/showcase/048_gas_bomb.md
BUILD_48 = [
    "@teleport me = Maintenance Corridor",
    "@create fortitude",
    "@tag fortitude = skill_def",
    "@set fortitude/stat = health",
    "@set fortitude/penalty = 0",
    "@reload",
    "@create gas cloud prototype",
    "@set gas cloud prototype/cloud_tick = [(pemit(o, 'The gas sears your lungs!'), damage(o, roll('1d6'))) if not skill_check(o, 'fortitude', -1) else pemit(o, 'Eyes streaming, you keep your sleeve pressed over your face.') for o in contents(loc(me)) if has_tag(o, 'player') or has_tag(o, 'npc')]",
    "@set gas cloud prototype/cloud_enter = pemit(enactor, 'Stinging yellow gas fills this room!') if has_tag(enactor, 'player') or has_tag(enactor, 'npc') else None",
    "@create gas bomb",
    "@set gas bomb/fuse = 10",
    "@set gas bomb/cmd_arm = $arm bomb: pemit(enactor, 'Set it down first -- arm it in your hands and you wear it.') if not (loc(me) and has_tag(loc(me), 'room')) else (pemit(enactor, 'It is already hissing.') if get_attr(me, 'armed', 0) else (set_attr(me, 'armed', 1), remit(loc(me), name(enactor) + ' twists the fuse cap. A thin hiss starts.'), wait(get_attr(me, 'fuse', 10), 'trigger me/detonate')))",
    "@set gas bomb/detonate = proto = get('gas cloud prototype'); dests = [get('#' + str(get_attr(e, 'destination', ''))) for e in exits(loc(me)) if not has_tag(e, 'closed')]; clouds = [c for c in [create_obj('a cloud of stinging gas', location=r) for r in [loc(me)] + [d for d in dests if d]] if c]; [set_attr(c, 'on_tick', get_attr(proto, 'cloud_tick')) for c in clouds]; [set_attr(c, 'on_enter', get_attr(proto, 'cloud_enter')) for c in clouds]; [attach_behavior(c, 'script_ticker', interval=2) for c in clouds]; [expire(c, 60) for c in clouds]; [remit(loc(c), 'A thick bank of stinging gas billows in!') for c in clouds]; destroy_obj(me)",
    "drop gas bomb",
]

# docs/showcase/160_sneaking.md
BUILD_160 = [
    "@teleport me = Nexagen Vault",
    "@create Vault Sentry",
    "@tag Vault Sentry = npc",
    "drop Vault Sentry",
    "@set Vault Sentry/hp = 13",
    "@set Vault Sentry/max_hp = 13",
    "@set Vault Sentry/health = 10",
    "@set Vault Sentry/skill_observation = 12",
    "@behavior Vault Sentry = watchful, challenge:This wing is off limits., spot_msg:Intruder! Show yourself!",
    "@set Vault Sentry/listen_creak = ^*creak*: set_attr(me, 'alert_level', get_attr(me, 'alert_level', 0) + 1); say('Who goes there?')",
    "@create loose floorboard",
    "drop loose floorboard",
    "@desc loose floorboard = One plank sits a hair prouder than its brothers.",
    "@set loose floorboard/on_enter = (None if not (has_tag(enactor, 'hidden') and has_tag(enactor, 'player')) else (pemit(enactor, 'You cross the boards without a sound.') if skill_check(enactor, 'stealth', -3) else cmd('emit A floorboard creaks sharply!')))",
]

STAGES = {
    27: BUILD_27,
    16: BUILD_16,
    49: BUILD_49,
    54: BUILD_54,
    48: BUILD_48,
    160: BUILD_160,
}
ARC_ORDER = [27, 16, 49, 54, 48, 160]

BUILD_RED_FLAGS = (
    "Unknown command", "Usage:", "not found", "Script error",
    "can't", "don't", "No permission",
)


# --- Harness -------------------------------------------------------------------


@pytest.fixture
def sim():
    simulator = Simulator()
    set_check_resolver(level_resolver)
    # GameServer registers these at startup; the Simulator leaves wiring
    # to the test (same seams, same objects).
    get_propagation_engine().add_observer(stealth_observer)
    simulator.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(simulator._sessions.values()))
    yield simulator
    set_check_resolver(None)
    simulator.close()


async def run_lines(sim, player, lines):
    """Drive raw command lines through the dispatcher, keeping the
    deterministic resolver pinned (the build's @reload re-installs the
    GURPS dice resolver)."""
    for line in lines:
        await sim.do(player, line)
        set_check_resolver(level_resolver)


async def build_heist(sim, upto=160):
    """Run the arc's build transcripts, in tutorial order, as a builder."""
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
    builder.add_tag("builder")
    for item in ARC_ORDER:
        await run_lines(sim, builder, STAGES[item])
        out = "\n".join(sim.seen(builder))
        for flag in BUILD_RED_FLAGS:
            assert flag not in out, (
                f"build stage {item} tripped {flag!r}:\n{out}")
        if item == upto:
            break
    return builder


def room(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no room named {name!r}"
    return matches[0]


def obj(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no object named {name!r}"
    return matches[0]


def text(sim, player):
    return "\n".join(sim.seen(player))


async def sweep_mine(sim, builder):
    """Play convenience: the crew swept the antechamber mine earlier."""
    await run_lines(sim, builder, ["@set anti-personnel mine/armed = 0"])
    sim.seen(builder)


# --- 27. Secret door -------------------------------------------------------------


class TestSecretDoor:

    async def test_search_reveals_and_grate_is_walkable(self, sim):
        builder = await build_heist(sim, upto=27)
        office = room(sim, "The Security Office")
        raven = sim.player("Raven", location=office,
                           skill_observation=13, skill_stealth=12,
                           hp=13, max_hp=13, health=12)

        await sim.do(raven, "east")
        out = text(sim, raven)
        # Passive glance is at -4: obs 13 -> 9, no reveal on entry.
        assert "crawlway yawns" not in out
        assert "loose grate" not in out          # hidden from the room display

        await sim.do(raven, "search")
        out = text(sim, raven)
        # Deliberate search rolls at -conceal_difficulty (-2): 11 >= 10.
        assert "One grate sits loose in its frame" in out
        assert not obj(sim, "loose grate").has_tag("invisible")

        # Revealed, the grate shows up in the exits line...
        await sim.do(raven, "look")
        assert "loose grate" in text(sim, raven)

        # ...and walks like any exit.
        await sim.do(raven, "loose grate")
        assert raven.location is room(sim, "Vault Antechamber")
        await sim.do(raven, "duct")
        assert raven.location is room(sim, "Maintenance Corridor")

    async def test_sharp_eyes_spot_it_passively_on_entry(self, sim):
        builder = await build_heist(sim, upto=27)
        office = room(sim, "The Security Office")
        hawk = sim.player("Hawk", location=office, skill_observation=14)

        await sim.do(hawk, "east")
        # The corridor's on_enter check: obs 14 - 4 = 10 -> revealed.
        assert "One grate sits loose in its frame" in text(sim, hawk)
        assert not obj(sim, "loose grate").has_tag("invisible")

    async def test_hidden_exit_traversable_by_name_for_those_in_the_know(self, sim):
        builder = await build_heist(sim, upto=27)
        corridor = room(sim, "Maintenance Corridor")
        mook = sim.player("Mook", location=corridor)  # no skills at all

        assert obj(sim, "loose grate").has_tag("invisible")
        await sim.do(mook, "loose grate")
        assert mook.location is room(sim, "Vault Antechamber")


# --- 16. Combination safe ----------------------------------------------------------


class TestCombinationSafe:

    async def test_dial_wrong_then_right_and_loot(self, sim):
        builder = await build_heist(sim, upto=16)
        vault = room(sim, "Nexagen Vault")
        raven = sim.player("Raven", location=vault)

        await sim.do(raven, "open wall safe")
        assert "doesn't budge" in text(sim, raven)

        # A wrong full sequence resets silently -- no digit-by-digit oracle.
        for line in ("dial 1", "dial 2"):
            await sim.do(raven, line)
        assert text(sim, raven).count("Click.") == 2
        await sim.do(raven, "dial 3")
        assert "spins back to zero" in text(sim, raven)
        assert obj(sim, "wall safe").db.get("locked") is True

        for line in ("dial 17", "dial 4"):
            await sim.do(raven, line)
        sim.seen(raven)
        await sim.do(raven, "dial 33")
        assert "the wall safe unlocks" in text(sim, raven)
        assert obj(sim, "wall safe").db.get("locked") is False

        await sim.do(raven, "open wall safe")
        await sim.do(raven, "get prototype schematics from wall safe")
        assert obj(sim, "prototype schematics").location is raven

    async def test_lockpicking_is_a_valid_alternate_route(self, sim):
        builder = await build_heist(sim, upto=16)
        vault = room(sim, "Nexagen Vault")
        sly = sim.player("Sly", location=vault, skill_lockpicking=14)

        # Improvised (no lockpicks): 14 - 4 - 5 = 5 < 10.
        await sim.do(sly, "pick wall safe")
        assert "resists" in text(sim, sly)
        assert obj(sim, "wall safe").db.get("locked") is True

        # With tools: 14 - 4 = 10.
        sim.obj("lockpick set", location=sly, tags=["thing", "lockpicks"])
        await sim.do(sly, "pick wall safe")
        assert "defeat the lock" in text(sim, sly)
        assert obj(sim, "wall safe").db.get("locked") is False

    async def test_owner_resets_code_via_prompt_and_secret_flag_hides_it(self, sim):
        builder = await build_heist(sim, upto=16)
        vault = room(sim, "Nexagen Vault")
        raven = sim.player("Raven", location=vault)
        safe = obj(sim, "wall safe")

        # Not the owner: refused outright.
        await sim.do(raven, "setcode")
        assert "Only the owner may reset the dial." in text(sim, raven)

        # The owner, but through a closed door: refused.
        await sim.do(builder, "@teleport me = Nexagen Vault")
        sim.seen(builder)
        await sim.do(builder, "setcode")
        assert "Open the safe first" in text(sim, builder)

        # Open it (dial the code), then the prompt wizard fires.
        for line in ("dial 17", "dial 4", "dial 33", "open wall safe"):
            await sim.do(builder, line)
        sim.seen(builder)
        await sim.do(builder, "setcode")
        assert "New combination" in text(sim, builder)
        handler = sim.session(builder).input_handler
        assert handler is not None, "prompt() should capture the next line"
        await handler(sim.session(builder), "5 25 45")
        assert "New combination: 5 25 45" in text(sim, builder)

        # Old code is dead; the new one opens it.
        await run_lines(sim, builder, ["close wall safe",
                                       "@set wall safe/locked = true"])
        for line in ("dial 17", "dial 4", "dial 33"):
            await sim.do(raven, line)
        assert obj(sim, "wall safe").db.get("locked") is True
        for line in ("dial 5", "dial 25", "dial 45"):
            await sim.do(raven, line)
        assert obj(sim, "wall safe").db.get("locked") is False

        # The secret attr flag: a stranger's softcode reads nothing,
        # the safe's owner still reads it.
        stolen, _err = await sim.eval(raven, "result = get_attr(get('wall safe'), 'code')")
        assert stolen is None
        own, _err = await sim.eval(builder, "result = get_attr(get('wall safe'), 'code')")
        assert own == "5 25 45"


# --- 49. Landmine -------------------------------------------------------------------


class TestLandmine:

    async def test_sharp_eyes_freeze_midstep_and_ward_blocks_pickup(self, sim):
        builder = await build_heist(sim, upto=49)
        corridor = room(sim, "Maintenance Corridor")
        hawk = sim.player("Hawk", location=corridor,
                          skill_observation=14, hp=13, max_hp=13)

        await sim.do(hawk, "loose grate")   # hidden exits walk by name
        out = text(sim, hawk)
        # contest: obs 14 (margin 4) beats concealment 13 (margin 3).
        assert "You freeze mid-step" in out
        assert hawk.db.get("hp") == 13
        mine = obj(sim, "anti-personnel mine")
        assert not mine.has_tag("invisible")
        assert mine.db.get("armed") == 1

        # Spotted is not safe to pocket: the on_check ward vetoes the get.
        await sim.do(hawk, "get anti-personnel mine")
        assert "wedged into the floor" in text(sim, hawk)
        assert mine.location is room(sim, "Vault Antechamber")

        # Known mines are walked around.
        await sim.do(hawk, "duct")
        sim.seen(hawk)
        await sim.do(hawk, "loose grate")
        assert "You step around the exposed mine." in text(sim, hawk)

    async def test_dull_eyes_detonate_it(self, sim):
        builder = await build_heist(sim, upto=49)
        corridor = room(sim, "Maintenance Corridor")
        mook = sim.player("Mook", location=corridor,
                          skill_observation=6, hp=13, max_hp=13)
        witness = sim.player("Witness", location=room(sim, "Vault Antechamber"),
                             skill_observation=14, hp=13, max_hp=13)
        sim.seen(witness)

        await sim.do(mook, "loose grate")
        out = text(sim, mook)
        assert "KA-WHUMP!" in out
        assert mook.db.get("hp") < 13                      # 2d6 landed
        assert "Mook sets off a buried mine!" in text(sim, witness)
        mine = obj(sim, "anti-personnel mine")
        assert mine.db.get("armed") == 0                   # spent
        assert not mine.has_tag("invisible")               # and exposed

    async def test_search_finds_it_before_you_step_on_it(self, sim):
        builder = await build_heist(sim, upto=49)
        antechamber = room(sim, "Vault Antechamber")
        raven = sim.player("Raven", location=antechamber, skill_observation=13)

        await sim.do(raven, "search")
        # Flat observation vs conceal_difficulty 3: 13 - 3 = 10.
        assert "a pressure plate, wired and live!" in text(sim, raven)
        assert not obj(sim, "anti-personnel mine").has_tag("invisible")


# --- 54. Security camera & monitor ---------------------------------------------------


class TestSecurityCamera:

    async def test_watch_relays_speech_and_movement_until_unwatch(self, sim):
        builder = await build_heist(sim, upto=54)
        await sweep_mine(sim, builder)
        office = room(sim, "The Security Office")
        antechamber = room(sim, "Vault Antechamber")
        raven = sim.player("Raven", location=office)
        zeke = sim.player("Zeke", location=antechamber)

        await sim.do(raven, "watch")
        assert "You settle in at the console" in text(sim, raven)

        await sim.do(zeke, "say psst")
        assert '[security camera] Zeke says, "psst"' in text(sim, raven)

        await sim.do(zeke, "duct")
        out = text(sim, raven)
        assert out.count("[security camera] Zeke leaves.") == 1
        await sim.do(zeke, "loose grate")
        out = text(sim, raven)
        assert out.count("[security camera] Zeke arrives.") == 1

        await sim.do(raven, "unwatch")
        sim.seen(raven)
        await sim.do(zeke, "say anyone there?")
        assert "[security camera]" not in text(sim, raven)

    async def test_walking_away_prunes_and_cutting_kills_the_feed(self, sim):
        builder = await build_heist(sim, upto=54)
        await sweep_mine(sim, builder)
        office = room(sim, "The Security Office")
        antechamber = room(sim, "Vault Antechamber")
        raven = sim.player("Raven", location=office)
        sly = sim.player("Sly", location=antechamber, skill_electronics=12)

        await sim.do(raven, "watch")
        # Wander off: the next relay only reaches watchers still at the
        # console, and the stale subscription is pruned.
        await sim.do(raven, "east")
        sim.seen(raven)
        await sim.do(sly, "say all clear")
        assert "[security camera]" not in text(sim, raven)
        assert obj(sim, "security monitor").db.get("watchers") == []

        # Sabotage: electronics 12 - 2 = 10 cuts the power.
        await sim.do(sly, "cut camera")
        assert "the camera light dies" in text(sim, sly)
        assert obj(sim, "security camera").db.get("powered") == 0

        # Even a fresh watcher gets nothing from a dead camera.
        await sim.do(raven, "west")
        await sim.do(raven, "watch")
        sim.seen(raven)
        await sim.do(sly, "say still watching?")
        assert "[security camera]" not in text(sim, raven)


# --- 48. Gas bomb --------------------------------------------------------------------


class TestGasBomb:

    async def test_arm_spread_resist_linger_and_dissipate(self, sim):
        builder = await build_heist(sim, upto=48)
        await sweep_mine(sim, builder)
        # Stage the demo: vault door shut (closed doors hold gas back),
        # and a zero-second fuse so the test needn't sleep.
        await run_lines(sim, builder, [
            "@teleport me = Vault Antechamber",
            "close vault door",
            "@set gas bomb/fuse = 0",
        ])

        corridor = room(sim, "Maintenance Corridor")
        antechamber = room(sim, "Vault Antechamber")
        office = room(sim, "The Security Office")
        vault = room(sim, "Nexagen Vault")

        raven = sim.player("Raven", location=corridor,
                           hp=13, max_hp=13, health=12)   # fortitude 12-1=11: resists
        mook = sim.player("Mook", location=antechamber,
                          hp=13, max_hp=13, health=8)     # fortitude 8-1=7: chokes

        # Arming it in your hands is refused.
        await sim.do(raven, "get gas bomb")
        await sim.do(raven, "arm bomb")
        assert "Set it down first" in text(sim, raven)

        # Carry it downstairs, set it, arm it, run.
        await sim.do(raven, "loose grate")
        await sim.do(raven, "drop gas bomb")
        sim.seen(raven)
        sim.seen(mook)
        await sim.do(raven, "arm bomb")
        assert "twists the fuse cap" in text(sim, mook)
        await sim.do(raven, "duct")
        await sim.do(raven, "west")
        assert raven.location is office

        # The fuse is a wait(): fire it.
        await sim.engine.tick_waits()

        clouds = sim.store.find_cached(name="a cloud of stinging gas")
        cloud_rooms = {c.location for c in clouds}
        assert antechamber in cloud_rooms          # ground zero
        assert corridor in cloud_rooms             # up the open duct
        assert vault not in cloud_rooms            # closed door holds it
        assert office not in cloud_rooms           # not adjacent
        assert len(clouds) == 2
        assert sim.store.find_cached(name="gas bomb") == [], \
            "the bomb should be destroyed"
        assert "A thick bank of stinging gas billows in!" in text(sim, mook)

        # Exposure runs on the cloud's ticker: HT-based fortitude roll.
        for cloud in clouds:
            for behavior in cloud.get_behaviors():
                await behavior.tick(cloud, 4.0)
        assert "The gas sears your lungs!" in text(sim, mook)
        assert mook.db.get("hp") < 13
        assert raven.db.get("hp") == 13            # safe in the office

        # A latecomer wading in is warned by the cloud's ON_ENTER.
        await sim.do(raven, "east")
        assert "Stinging yellow gas fills this room!" in text(sim, raven)

        # Dissipation is expire(): the world tick reaps the clouds.
        reaped = await reap_expired(sim.store, now=time.time() + 120)
        assert reaped == 2
        assert sim.store.find_cached(name="a cloud of stinging gas") == []


# --- 160. Sneaking -------------------------------------------------------------------


class TestSneaking:

    async def test_visible_arrivals_are_challenged(self, sim):
        builder = await build_heist(sim, upto=160)
        await sweep_mine(sim, builder)
        antechamber = room(sim, "Vault Antechamber")
        hawk = sim.player("Hawk", location=antechamber, skill_observation=16)

        await sim.do(hawk, "vault door")
        assert 'Vault Sentry says, "This wing is off limits."' in text(sim, hawk)

    async def test_creaky_floor_alerts_the_sentry_who_then_spots_you(self, sim):
        builder = await build_heist(sim, upto=160)
        await sweep_mine(sim, builder)
        antechamber = room(sim, "Vault Antechamber")
        vault = room(sim, "Nexagen Vault")
        sentry = obj(sim, "Vault Sentry")
        hawk = sim.player("Hawk", location=vault, skill_observation=16)
        shade = sim.player("Shade", location=antechamber, skill_stealth=12)
        sim.seen(hawk)

        await sim.do(shade, "hide")
        assert "You slip out of sight." in text(sim, shade)

        # First pass: stealth 12 ties the sentry's observation 12 -- ties
        # go to the hider -- but the floorboard check at -3 fails: creak.
        await sim.do(shade, "vault door")
        assert shade.has_tag("hidden")
        out = text(sim, hawk)
        assert "Someone arrives." in out           # who, not that, is hidden
        assert "A floorboard creaks sharply!" in out
        assert 'Vault Sentry says, "Who goes there?"' in out
        assert int(sentry.db.get("alert_level") or 0) == 1

        # Second pass: the alerted sentry (obs 12 + 1) wins the contest.
        await sim.do(shade, "antechamber")
        sim.seen(shade)
        await sim.do(shade, "vault door")
        assert not shade.has_tag("hidden")
        out = text(sim, shade)
        assert "Vault Sentry spots you!" in out
        assert int(sentry.db.get("alert_level") or 0) == 2

    async def test_master_sneak_slips_in_but_speaking_gives_you_away(self, sim):
        builder = await build_heist(sim, upto=160)
        await sweep_mine(sim, builder)
        antechamber = room(sim, "Vault Antechamber")
        vault = room(sim, "Nexagen Vault")
        hawk = sim.player("Hawk", location=vault, skill_observation=16)
        wraith = sim.player("Wraith", location=antechamber, skill_stealth=15)

        await sim.do(wraith, "hide")
        sim.seen(hawk)
        await sim.do(wraith, "vault door")
        out = text(sim, wraith)
        assert wraith.has_tag("hidden")            # sentry misses margin 5
        assert "You cross the boards without a sound." in out
        assert "spots you" not in out
        # Hidden actors are unnamed in what bystanders see.
        assert "Wraith" not in text(sim, hawk)

        # Loud actions break stealth (the engine's stealth observer).
        await sim.do(wraith, "say the vault is ours")
        assert "Your action gives you away!" in text(sim, wraith)
        assert not wraith.has_tag("hidden")

    async def test_search_contests_a_hiders_stealth(self, sim):
        builder = await build_heist(sim, upto=160)
        await sweep_mine(sim, builder)
        vault = room(sim, "Nexagen Vault")
        hawk = sim.player("Hawk", location=vault, skill_observation=16)
        wraith = sim.player("Wraith", location=vault, skill_stealth=15)

        await sim.do(wraith, "hide")
        assert wraith.has_tag("hidden")
        sim.seen(wraith)

        await sim.do(hawk, "search")               # obs 16 vs stealth 15
        assert not wraith.has_tag("hidden")
        assert "Hawk spots you!" in text(sim, wraith)
