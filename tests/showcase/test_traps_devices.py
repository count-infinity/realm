"""
Showcase verification — Traps, Hazards & Devices (standalone tutorials).

Items: 50 tripwire alarm, 51 pit trap, 52 poison dart trap, 53 snare,
55 motion sensor log, 56 self-destruct sequence, 57 EMP charge,
58 spreading fire, 59 tranquilizer mechanics.

Every command line in each tutorial's "Build it" section is driven
through the real dispatcher (raw input in -> session output out) by a
builder player, exactly as typed in the docs; the plays then exercise
the tutorials' "Try it" flows and assert outcomes.

Dice are removed via the pluggable check resolver (same convention as
tests/test_infiltration.py and test_heist.py): a check succeeds iff
effective skill >= 10, margin = effective - 10, so contests go to the
higher skill. Several builds run @reload (skill_def registration),
which re-installs the GURPS dice resolver — the line runner re-pins
the deterministic resolver after every command.

Time is virtual throughout: wait() fuses fire on tick_waits() pumps,
beat-driven effects (poison, sedation) advance via deliver_beat(),
script_ticker heartbeats are ticked by hand, and expire() lifetimes
are reaped with a forged clock.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from realm.core.beats import deliver_beat
from realm.core.checks import CheckResult, set_check_resolver, skill_level
from realm.core.events import reap_expired
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

# docs/showcase/050_tripwire_alarm.md
BUILD_50 = [
    "@dig The Curio Shop = shop, out",
    "shop",
    "@dig The Stockroom = stockroom, shop",
    "stockroom",
    "@create tripwire",
    "drop tripwire",
    "@desc tripwire = A hair-fine wire at ankle height, easy to miss.",
    "@set tripwire/armed = 1",
    "@set tripwire/conceal_difficulty = 2",
    "@set tripwire/reveal_msg = A glint at ankle height -- a wire, stretched taut across the doorway!",
    "@set tripwire/on_enter = x = enactor; (None if not (V('armed', 0) and (has_tag(x, 'player') or has_tag(x, 'npc')) and x != owner(me)) else (pemit(x, 'You step over the exposed tripwire.') if not has_tag(me, 'invisible') else (incr('trips'), pemit(owner(me), f'[tripwire] {name(x)} crossed {name(loc(me))}.'))))",
    "@tag tripwire = invisible",
    "shop",
]

# docs/showcase/051_pit_trap.md
BUILD_51 = [
    "@dig The Dusty Gallery = gallery, out",
    "@dig The Oubliette",
    "gallery",
    "@create rigged flagstone",
    "drop rigged flagstone",
    "@desc rigged flagstone = One flagstone sits a shade lower than its brothers.",
    "@set rigged flagstone/armed = 1",
    "@set rigged flagstone/on_enter = x = enactor; (None if not (V('armed', 0) and (has_tag(x, 'player') or has_tag(x, 'npc')) and x != owner(me)) else (pemit(x, 'A flagstone shifts under your toe -- you step around it just in time.') if skill_check(x, 'observation', -3) else (set_attr(me, 'armed', 0), remit(loc(me), f'{name(x)} vanishes through the floor with a crash!'), pemit(x, 'The floor drops away beneath you!'), teleport_obj(x, 'The Oubliette'), pemit(x, 'You land hard on cold stone, far below.'))))",
    "@teleport me = The Oubliette",
    "@desc here = A stone box that smells of old rain. The only light is a grey coin of sky at the top of a rough shaft.",
    "@open climb = The Dusty Gallery",
    "@desc climb = A rough shaft, half handholds, half wishful thinking.",
    "@set climb/check_skill = climbing",
    "@set climb/check_difficulty = 2",
    "@set climb/check_fail_msg = You claw halfway up the slick stone and slide back down.",
    "@teleport me = The Dusty Gallery",
]

# docs/showcase/052_poison_dart_trap.md
BUILD_52 = [
    "@dig The Reliquary = reliquary, out",
    "reliquary",
    "@create fortitude",
    "@tag fortitude = skill_def",
    "@set fortitude/stat = health",
    "@set fortitude/penalty = 0",
    "@reload",
    "@create jade idol",
    "drop jade idol",
    "@desc jade idol = A grinning green figurine on a wall bracket. Its eyes follow you.",
    "@set jade idol/dart = remit(loc(me), 'A hidden nozzle spits a needle-thin dart!'); damage(enactor, roll('1d2')); (pemit(enactor, 'A cold numbness spreads from the scratch.'), apply_effect(enactor, 'damage_over_time', kind='poison', damage=1, interval=1, duration=6, tick_msg='Venom burns through your veins!', room_msg='{name} shivers, grey-faced and sweating.', expire_msg='The fever finally breaks.')) if not skill_check(enactor, 'fortitude', -2) else pemit(enactor, 'Your head swims for a moment -- then clears. Only a scratch.')",
    "@set jade idol/cmd_touch = $touch idol: eval_attr(me, 'dart')",
    "@set jade idol/on_get = eval_attr(me, 'dart')",
    "@create antidote vial",
    "drop antidote vial",
    "@desc antidote vial = A stoppered vial of milky liquid, labeled in a careful hand: AFTER THE IDOL.",
    "@set antidote vial/cmd_drink = $drink antidote: (remove_effect(enactor, 'poison'), pemit(enactor, 'Bitter warmth washes the numbness out of your blood.'), destroy_obj(me)) if has_tag(enactor, 'poison') else pemit(enactor, 'You are not poisoned. Save it.')",
]

# docs/showcase/053_snare.md
BUILD_53 = [
    "@dig The Game Trail = trail, out",
    "trail",
    "@create might",
    "@tag might = skill_def",
    "@set might/stat = strength",
    "@set might/penalty = 0",
    "@reload",
    "@create hunting snare",
    "drop hunting snare",
    "@desc hunting snare = A whippy sapling, a loop of ground wire, and patience.",
    "@set hunting snare/armed = 1",
    "@set hunting snare/skill_hold = 12",
    "@set hunting snare/on_enter = x = enactor; (set_attr(me, 'armed', 0), remit(loc(me), f\"A wire loop snaps tight around {name(x)}'s ankle!\"), apply_effect(x, 'modifier_effect', kind='snared', duration=0, apply_msg='The world jerks sideways -- you are caught fast!')) if V('armed', 0) and (has_tag(x, 'player') or has_tag(x, 'npc')) and x != owner(me) else None",
    "@set here/on_check = block('The snare around your ankle jerks taut! (STRUGGLE to break free)') if atype == 'event:on_leave' and has_tag(actor, 'snared') else None",
    "@set hunting snare/cmd_struggle = $struggle: pemit(enactor, 'You are not caught in anything.') if not has_tag(enactor, 'snared') else ((remove_effect(enactor, 'snared'), remit(loc(me), f'{name(enactor)} tears free of the snare!')) if contest(enactor, 'might', me, 'hold') else (decr('skill_hold'), pemit(enactor, 'You strain against the wire. It gives a little -- and holds.')))",
]

# docs/showcase/055_motion_sensor.md
BUILD_55 = [
    "@dig The Server Vault = vault, out",
    "vault",
    "@create motion sensor",
    "drop motion sensor",
    "@desc motion sensor = A black dome in the corner. A red LED blinks, twice a second, forever. REVIEW plays back its log.",
    "@set motion sensor/on_enter = set_attr(me, 'log', ((V('log') or []) + [[name(enactor), 'entered', now()]])[-20:]) if has_tag(enactor, 'player') or has_tag(enactor, 'npc') else None",
    "@set motion sensor/on_leave = set_attr(me, 'log', ((V('log') or []) + [[name(enactor), 'left', now()]])[-20:]) if has_tag(enactor, 'player') or has_tag(enactor, 'npc') else None",
    "@set motion sensor/cmd_review = $review: entries = V('log') or []; (pemit(enactor, 'The log is empty.') if not entries else [pemit(enactor, f'[{now() - e[2]}s ago] {e[0]} {e[1]}.') for e in entries])",
]

# docs/showcase/056_self_destruct.md
BUILD_56 = [
    "@dig Reactor Core = core, out",
    "core",
    "@zone here = station",
    "@dig Cargo Bay = bay, core",
    "bay",
    "@zone here = station",
    "core",
    "@create Station Brain",
    "drop Station Brain",
    "@desc Station Brain = A pillar of screens and switches. A red panel reads: SELF DESTRUCT. A smaller one reads: ABORT.",
    "@zone/master Station Brain = station",
    "@set Station Brain/interval = 10",
    "@set Station Brain/code = ZEBRA-9",
    "@attr Station Brain/code = secret",
    "@set Station Brain/cmd_selfdestruct = $self destruct: pemit(enactor, 'The console demands command authority.') if enactor != owner(me) else (pemit(enactor, 'The countdown is already running.') if V('pending') else (set_attr(me, 'count', 5), act(me, f'KLAXON: SELF-DESTRUCT SEQUENCE INITIATED. {5 * V(\"interval\", 10)} SECONDS TO ZERO. ABORT requires command code.', targeting='zone'), set_attr(me, 'pending', wait(V('interval', 10), 'trigger me/countdown'))))",
    "@set Station Brain/countdown = n = V('count', 0) - 1; (eval_attr(me, 'boom') if n <= 0 else (set_attr(me, 'count', n), act(me, f'SELF-DESTRUCT IN {n * V(\"interval\", 10)} SECONDS.', targeting='zone'), set_attr(me, 'pending', wait(V('interval', 10), 'trigger me/countdown'))))",
    "@set Station Brain/cmd_abort = $abort: prompt(enactor, 'Enter the abort code:', 'abort_check') if V('pending') else pemit(enactor, 'The self-destruct is not armed.')",
    "@set Station Brain/abort_check = (cancel_wait(V('pending')), del_attr(me, 'pending'), del_attr(me, 'count'), act(me, f'KLAXON: SELF-DESTRUCT ABORTED. Authorization: {name(enactor)}.', targeting='zone')) if trim(arg0) == str(V('code')) else pemit(enactor, 'INVALID CODE. The countdown continues.')",
    "@set Station Brain/blast_tick = [(pemit(o, 'Fire roars over you!'), damage(o, roll('2d6'))) for o in contents(loc(me)) if has_tag(o, 'player') or has_tag(o, 'npc')]",
    "@set Station Brain/boom = del_attr(me, 'pending'); del_attr(me, 'count'); act(me, 'The deck heaves. Fire tears through every compartment!', targeting='zone'); blasts = [b for b in [create_obj('a sheet of roaring flame', location=r) for r in zone_rooms('station')] if b]; [set_attr(b, 'on_tick', V('blast_tick')) for b in blasts]; [attach_behavior(b, 'script_ticker', interval=1) for b in blasts]; [expire(b, 20) for b in blasts]",
]

# docs/showcase/057_emp_charge.md
BUILD_57 = [
    "@dig The Drone Lab = lab, out",
    "lab",
    "@create sweeper drone",
    "drop sweeper drone",
    "@tag sweeper drone = electronic",
    "@desc sweeper drone = A knee-high maintenance drone, rotors idling. PING it for a status check.",
    "@set sweeper drone/cmd_ping = $ping drone: pemit(enactor, 'The drone chirps: ALL SYSTEMS NOMINAL.') if not has_tag(me, 'disabled') else pemit(enactor, 'The drone lies inert, rotors still.')",
    "@create wall terminal",
    "drop wall terminal",
    "@tag wall terminal = electronic",
    "@desc wall terminal = A recessed screen glowing standby-green. LOGIN to use it.",
    "@set wall terminal/cmd_login = $login: pemit(enactor, 'ACCESS GRANTED. Directory listings scroll past.') if not has_tag(me, 'disabled') else pemit(enactor, 'The screen is dead glass.')",
    "@create EMP charge",
    "@set EMP charge/cmd_arm = $arm emp: eval_attr(me, 'pulse') if loc(me) and has_tag(loc(me), 'room') else pemit(enactor, 'Not while you are holding it. Set it down first.')",
    "@set EMP charge/pulse = hit = [o for o in contents(loc(me)) if has_tag(o, 'electronic') and not has_tag(o, 'disabled') and o != me]; [add_tag(o, 'disabled') for o in hit]; set_attr(me, 'hit', [o.id for o in hit]); remit(loc(me), 'A soundless white PULSE. Every status light in the room goes dark.'); expire(me, 30)",
    "@set EMP charge/on_expire = [remove_tag(get(f'#{i}'), 'disabled') for i in (V('hit') or [])]; remit(loc(me), 'One by one, status lights flicker back to life. The spent EMP casing crumbles to slag.')",
    "drop EMP charge",
]

# docs/showcase/058_spreading_fire.md
BUILD_58 = [
    "@dig The Hayloft = hayloft, yard",
    "hayloft",
    "@dig The Stable = ladder, loft",
    "ladder",
    "@dig The Tack Room = tack door, stable",
    "@tag tack door = closed",
    "loft",
    "@tag yard = closed",
    "@create fire prototype",
    "@set fire prototype/fire_tick = s = V('stage', 1); ([(pemit(o, 'The blaze sears you!'), damage(o, roll(f'{s - 1}d4'))) for o in contents(loc(me)) if has_tag(o, 'player') or has_tag(o, 'npc')] if s >= 2 else remit(loc(me), 'Smoke thickens. Flames crawl wider.')); (eval_attr(me, 'spread') if s >= 3 else None); (set_attr(me, 'stage', s + 1) if s < 3 else None)",
    "@set fire prototype/fire_spread = proto = get('fire prototype'); dests = [get(f\"#{get_attr(e, 'destination', '')}\") for e in exits(loc(me)) if not has_tag(e, 'closed')]; fresh = [d for d in dests if d and not [o for o in contents(d) if has_tag(o, 'fire')]]; new = [f for f in [create_obj('a hungry fire', ['thing', 'fire'], location=r) for r in fresh] if f]; [set_attr(f, 'on_tick', get_attr(proto, 'fire_tick')) for f in new]; [set_attr(f, 'spread', get_attr(proto, 'fire_spread')) for f in new]; [attach_behavior(f, 'script_ticker', interval=2) for f in new]; [expire(f, 120) for f in new]; [remit(loc(f), 'Fire licks through the doorway -- it catches!') for f in new]",
    "@create box of matches",
    "@set box of matches/cmd_light = $light fire: proto = get('fire prototype'); f = create_obj('a hungry fire', ['thing', 'fire'], location=loc(enactor)); (set_attr(f, 'on_tick', get_attr(proto, 'fire_tick')), set_attr(f, 'spread', get_attr(proto, 'fire_spread')), attach_behavior(f, 'script_ticker', interval=2), expire(f, 120), remit(loc(enactor), f'{name(enactor)} drops a lit match into the straw. Flames catch!')) if f else pemit(enactor, 'The match gutters out.')",
    "@create fire extinguisher",
    "@set fire extinguisher/cmd_spray = $spray *: fires = [o for o in contents(loc(enactor)) if has_tag(o, 'fire')]; s = get_attr(fires[0], 'stage', 1) if fires else 0; (pemit(enactor, 'Nothing here is burning.') if not fires else ((destroy_obj(fires[0]), remit(loc(enactor), f'{name(enactor)} smothers the last flames in a white cloud. Steam hisses.')) if s <= 1 else (set_attr(fires[0], 'stage', s - 1), remit(loc(enactor), f'{name(enactor)} drives the fire back with a jet of foam!'))))",
]

# docs/showcase/059_tranquilizer.md
BUILD_59 = [
    "@dig The Med Bay = medbay, out",
    "medbay",
    "@create fortitude",
    "@tag fortitude = skill_def",
    "@set fortitude/stat = health",
    "@set fortitude/penalty = 0",
    "@reload",
    "@create tranq pistol",
    "drop tranq pistol",
    "@desc tranq pistol = A snub-nosed gas pistol on a swivel mount by the door, rotary drum full of red-feathered darts. SHOOT someone with it.",
    "@set tranq pistol/cmd_shoot = $shoot *: t = get(trim(arg0)); (pemit(enactor, 'No sign of them in reach.') if not (t and loc(t) == loc(enactor) and (has_tag(t, 'player') or has_tag(t, 'npc'))) else (remit(loc(enactor), f\"{name(enactor)} plants a red-feathered dart in {name(t)}'s neck!\"), (pemit(t, 'Your vision swims... then steadies. Your neck is numb.') if skill_check(t, 'fortitude', -3) else (apply_effect(t, 'modifier_effect', kind='unconscious', duration=6, apply_msg='The room smears sideways. Then nothing.', expire_msg='You come to, cheek on the cold deck.'), remit(loc(enactor), f'{name(t)} crumples bonelessly to the floor.')))))",
    "@create stim injector",
    "drop stim injector",
    "@desc stim injector = An emergency stim injector in a wall cradle. JAB the sedated with it.",
    "@set stim injector/cmd_jab = $jab *: t = get(trim(arg0)); (remove_effect(t, 'unconscious'), remit(loc(enactor), f\"{name(enactor)} slams a stim injector against {name(t)}'s arm. They jolt awake.\")) if t and loc(t) == loc(enactor) and has_tag(t, 'unconscious') else pemit(enactor, 'They are not sedated.')",
]

BUILD_RED_FLAGS = (
    "Unknown command", "Usage:", "not found", "Script error",
    "can't", "don't", "No permission",
)


# --- Harness -------------------------------------------------------------------


@pytest.fixture
def sim():
    simulator = Simulator()
    set_check_resolver(level_resolver)
    # GameServer wires the session manager at startup; the Simulator
    # leaves it to the test (needed by prompt()).
    simulator.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(simulator._sessions.values()))
    yield simulator
    set_check_resolver(None)
    simulator.close()


async def run_lines(sim, player, lines):
    """Drive raw command lines through the dispatcher, keeping the
    deterministic resolver pinned (a build's @reload re-installs the
    GURPS dice resolver)."""
    for line in lines:
        await sim.do(player, line)
        set_check_resolver(level_resolver)


async def build(sim, lines):
    """Run one tutorial's build transcript as a builder from Limbo."""
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
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


async def pulse(fire):
    """Advance a script_ticker (interval:2) by exactly one on_tick run:
    from a zeroed countdown, the first tick fires and re-arms to 1, the
    second decrements back to 0 without firing."""
    for behavior in list(fire.get_behaviors()):
        await behavior.tick(fire, 4.0)
    for behavior in list(fire.get_behaviors()):
        await behavior.tick(fire, 4.0)


# --- 50. Tripwire alarm ---------------------------------------------------------


class TestTripwireAlarm:

    async def test_silent_alert_reaches_owner_and_not_the_intruder(self, sim):
        builder = await build(sim, BUILD_50)
        assert builder.location is room(sim, "The Curio Shop")
        zeke = sim.player("Zeke", location=room(sim, "The Curio Shop"))

        await sim.do(zeke, "stockroom")
        assert "[tripwire] Zeke crossed The Stockroom." in text(sim, builder)
        out = text(sim, zeke)
        assert "[tripwire]" not in out          # silent to the walker
        assert "tripwire" not in out            # hidden from the room display
        assert obj(sim, "tripwire").db.get("trips") == 1

        # Every crossing pages; the counter remembers.
        await sim.do(zeke, "shop")
        sim.seen(builder)
        await sim.do(zeke, "stockroom")
        assert "[tripwire] Zeke crossed The Stockroom." in text(sim, builder)
        assert obj(sim, "tripwire").db.get("trips") == 2  # back in again

    async def test_search_reveals_and_a_seen_wire_reports_nothing(self, sim):
        builder = await build(sim, BUILD_50)
        raven = sim.player("Raven", location=room(sim, "The Stockroom"),
                           skill_observation=12)
        sim.seen(builder)
        trips_before = obj(sim, "tripwire").db.get("trips") or 0

        await sim.do(raven, "search")
        # Deliberate search rolls at -conceal_difficulty: 12 - 2 = 10.
        assert "A glint at ankle height" in text(sim, raven)
        assert not obj(sim, "tripwire").has_tag("invisible")

        await sim.do(raven, "shop")
        sim.seen(raven)
        sim.seen(builder)
        await sim.do(raven, "stockroom")
        assert "You step over the exposed tripwire." in text(sim, raven)
        assert "[tripwire]" not in text(sim, builder)     # no alert once seen
        assert (obj(sim, "tripwire").db.get("trips") or 0) == trips_before

    async def test_owner_never_pages_themselves(self, sim):
        builder = await build(sim, BUILD_50)
        sim.seen(builder)
        await sim.do(builder, "stockroom")
        assert "[tripwire]" not in text(sim, builder)
        assert (obj(sim, "tripwire").db.get("trips") or 0) == 0


# --- 51. Pit trap ---------------------------------------------------------------


class TestPitTrap:

    async def test_sharp_eyes_sidestep_dull_eyes_drop(self, sim):
        builder = await build(sim, BUILD_51)
        limbo = room(sim, "Limbo")
        scout = sim.player("Scout", location=limbo, skill_observation=13,
                           hp=13, max_hp=13)
        mook = sim.player("Mook", location=limbo, skill_observation=6,
                          hp=13, max_hp=13)

        await sim.do(scout, "gallery")
        # observation 13 - 3 = 10: sidestep (and the plate stays armed).
        assert "you step around it just in time" in text(sim, scout)
        assert scout.location is room(sim, "The Dusty Gallery")
        assert obj(sim, "rigged flagstone").db.get("armed") == 1

        await sim.do(mook, "gallery")
        out = text(sim, mook)
        assert "The floor drops away beneath you!" in out
        assert "You land hard on cold stone, far below." in out
        assert mook.location is room(sim, "The Oubliette")
        # The gallery watched it happen, and the fall sprang the doors.
        assert "Mook vanishes through the floor with a crash!" in text(sim, scout)
        assert obj(sim, "rigged flagstone").db.get("armed") == 0

    async def test_climb_out_is_a_skill_gated_exit(self, sim):
        builder = await build(sim, BUILD_51)
        limbo = room(sim, "Limbo")
        mook = sim.player("Mook", location=limbo, skill_observation=6,
                          hp=13, max_hp=13)
        sly = sim.player("Sly", location=limbo, skill_observation=6,
                         skill_climbing=12, hp=13, max_hp=13)

        await sim.do(mook, "gallery")
        assert mook.location is room(sim, "The Oubliette")
        # The fall sprang the doors -- re-arm for the next victim.
        await run_lines(sim, builder, ["@set rigged flagstone/armed = 1"])
        await sim.do(sly, "gallery")
        assert sly.location is room(sim, "The Oubliette")
        sim.seen(mook)
        sim.seen(sly)

        # Untrained climbing defaults to DX-5 = 5; 5 - 2 = 3: slide back.
        await sim.do(mook, "climb")
        assert "slide back down" in text(sim, mook)
        assert mook.location is room(sim, "The Oubliette")

        # Climbing 12 - 2 = 10: out -- and the surfacing is safe, because
        # the climber's own fall left the trapdoor hanging open.
        await sim.do(sly, "climb")
        assert sly.location is room(sim, "The Dusty Gallery")
        assert "floor drops away" not in text(sim, sly)

    async def test_owner_walks_their_own_gallery_safely(self, sim):
        builder = await build(sim, BUILD_51)
        sim.seen(builder)
        await sim.do(builder, "out")
        await sim.do(builder, "gallery")
        assert builder.location is room(sim, "The Dusty Gallery")
        assert "floor drops away" not in text(sim, builder)


# --- 52. Poison dart trap -------------------------------------------------------


class TestPoisonDartTrap:

    async def test_touch_resisted_and_unresisted_with_ticking_venom(self, sim):
        builder = await build(sim, BUILD_52)
        reliquary = room(sim, "The Reliquary")
        raven = sim.player("Raven", location=reliquary,
                           hp=13, max_hp=13, health=13)   # fortitude 13-2=11
        zeke = sim.player("Zeke", location=reliquary,
                          hp=13, max_hp=13, health=8)     # fortitude 8-2=6

        await sim.do(raven, "touch idol")
        out = text(sim, raven)
        assert "A hidden nozzle spits a needle-thin dart!" in out
        assert "Only a scratch." in out
        assert 11 <= raven.db.get("hp") <= 12              # 1d2 dart
        assert not raven.has_tag("poison")

        await sim.do(zeke, "touch idol")
        assert "A cold numbness spreads from the scratch." in text(sim, zeke)
        assert zeke.has_tag("poison")
        hp0 = zeke.db.get("hp")

        # The venom is a beat-driven engine effect.
        sim.seen(raven)
        for _ in range(3):
            await deliver_beat(zeke)
        assert zeke.db.get("hp") == hp0 - 3
        assert "Venom burns through your veins!" in text(sim, zeke)
        assert "Zeke shivers, grey-faced and sweating." in text(sim, raven)

        # ...and it expires on its own (5 pulses across 6 beats).
        for _ in range(3):
            await deliver_beat(zeke)
        assert not zeke.has_tag("poison")
        assert "The fever finally breaks." in text(sim, zeke)
        assert zeke.db.get("hp") == hp0 - 5

    async def test_grabbing_the_idol_also_darts_you(self, sim):
        builder = await build(sim, BUILD_52)
        reliquary = room(sim, "The Reliquary")
        hawk = sim.player("Hawk", location=reliquary,
                          hp=13, max_hp=13, health=13)

        await sim.do(hawk, "get jade idol")
        out = text(sim, hawk)
        assert "A hidden nozzle spits a needle-thin dart!" in out
        assert hawk.db.get("hp") < 13
        assert obj(sim, "jade idol").location is hawk      # the grab succeeded

    async def test_antidote_cures_and_spends_itself(self, sim):
        builder = await build(sim, BUILD_52)
        reliquary = room(sim, "The Reliquary")
        raven = sim.player("Raven", location=reliquary,
                           hp=13, max_hp=13, health=13)
        zeke = sim.player("Zeke", location=reliquary,
                          hp=13, max_hp=13, health=8)

        await sim.do(raven, "drink antidote")
        assert "You are not poisoned. Save it." in text(sim, raven)
        assert objs(sim, "antidote vial")                  # unspent

        await sim.do(zeke, "touch idol")
        assert zeke.has_tag("poison")
        await sim.do(zeke, "drink antidote")
        assert "Bitter warmth washes the numbness out of your blood." in text(sim, zeke)
        assert not zeke.has_tag("poison")
        assert objs(sim, "antidote vial") == []            # spent

        hp_after_cure = zeke.db.get("hp")
        for _ in range(3):
            await deliver_beat(zeke)
        assert zeke.db.get("hp") == hp_after_cure          # ticking stopped


# --- 53. Snare ------------------------------------------------------------------


class TestSnare:

    async def test_snare_holds_movement_until_strength_wins(self, sim):
        builder = await build(sim, BUILD_53)
        limbo = room(sim, "Limbo")
        zeke = sim.player("Zeke", location=limbo, strength=12,
                          hp=13, max_hp=13)

        await sim.do(zeke, "trail")
        out = text(sim, zeke)
        assert "The world jerks sideways -- you are caught fast!" in out
        assert zeke.has_tag("snared")
        assert obj(sim, "hunting snare").db.get("armed") == 0
        assert "A wire loop snaps tight around Zeke's ankle!" in text(sim, builder)

        # The ward vetoes every departure while the tag holds.
        await sim.do(zeke, "out")
        assert "The snare around your ankle jerks taut!" in text(sim, zeke)
        assert zeke.location is room(sim, "The Game Trail")

        # ST 12 vs hold 12: tie, and ties go to the snare -- which loosens.
        await sim.do(zeke, "struggle")
        assert "It gives a little -- and holds." in text(sim, zeke)
        assert obj(sim, "hunting snare").db.get("skill_hold") == 11
        assert zeke.has_tag("snared")

        # ST 12 vs hold 11: free.
        await sim.do(zeke, "struggle")
        assert "Zeke tears free of the snare!" in text(sim, zeke)
        assert not zeke.has_tag("snared")

        await sim.do(zeke, "out")
        assert zeke.location is limbo

    async def test_sprung_snare_ignores_the_next_walker(self, sim):
        builder = await build(sim, BUILD_53)
        limbo = room(sim, "Limbo")
        zeke = sim.player("Zeke", location=limbo, strength=12,
                          hp=13, max_hp=13)
        mook = sim.player("Mook", location=limbo, strength=10,
                          hp=13, max_hp=13)

        await sim.do(zeke, "trail")                        # springs it
        assert zeke.has_tag("snared")
        await sim.do(mook, "trail")
        assert not mook.has_tag("snared")                  # armed = 0

        await sim.do(mook, "struggle")
        assert "You are not caught in anything." in text(sim, mook)
        await sim.do(mook, "out")
        assert mook.location is limbo                      # free to go


# --- 55. Motion sensor log ------------------------------------------------------


class TestMotionSensorLog:

    async def test_log_records_walkers_and_review_plays_back(self, sim):
        builder = await build(sim, BUILD_55)
        limbo = room(sim, "Limbo")
        zeke = sim.player("Zeke", location=limbo)

        await sim.do(zeke, "vault")
        await sim.do(zeke, "out")
        await sim.do(builder, "review")
        out = text(sim, builder)
        assert "Zeke entered." in out
        assert "Zeke left." in out
        assert out.index("Zeke entered.") < out.index("Zeke left.")
        assert "s ago]" in out

    async def test_teleport_skips_the_departure_event(self, sim):
        builder = await build(sim, BUILD_55)
        zeke = sim.player("Zeke", location=room(sim, "The Server Vault"))

        await run_lines(sim, builder, ["@teleport me = Limbo"])
        await run_lines(sim, builder, ["@teleport me = The Server Vault"])
        sim.seen(builder)
        await sim.do(builder, "review")
        out = text(sim, builder)
        assert "Bob entered." in out       # teleport arrivals fire on_enter
        assert "Bob left." not in out      # teleport departures are unseen

    async def test_log_is_capped_at_twenty_records(self, sim):
        builder = await build(sim, BUILD_55)
        limbo = room(sim, "Limbo")
        zeke = sim.player("Zeke", location=limbo)

        for _ in range(12):                # 24 records, capped to 20
            await sim.do(zeke, "vault")
            await sim.do(zeke, "out")
        log = obj(sim, "motion sensor").db.get("log")
        assert len(log) == 20
        assert log[-1][1] == "left"        # newest survives the slice


# --- 56. Self-destruct sequence -------------------------------------------------


class TestSelfDestruct:

    async def test_authority_idle_abort_and_double_arm(self, sim):
        builder = await build(sim, BUILD_56)
        raven = sim.player("Raven", location=room(sim, "Cargo Bay"),
                           hp=20, max_hp=20)

        await sim.do(raven, "self destruct")
        assert "The console demands command authority." in text(sim, raven)

        await sim.do(raven, "abort")
        assert "The self-destruct is not armed." in text(sim, raven)

        await run_lines(sim, builder, ["@set Station Brain/interval = 0"])
        sim.seen(builder)
        await sim.do(builder, "self destruct")
        assert "SELF-DESTRUCT SEQUENCE INITIATED" in text(sim, builder)
        await sim.do(builder, "self destruct")
        assert "The countdown is already running." in text(sim, builder)

    async def test_zone_wide_klaxons_and_coded_abort_from_another_room(self, sim):
        builder = await build(sim, BUILD_56)
        raven = sim.player("Raven", location=room(sim, "Cargo Bay"),
                           hp=20, max_hp=20)
        await run_lines(sim, builder, ["@set Station Brain/interval = 0"])
        brain = obj(sim, "Station Brain")

        await sim.do(builder, "self destruct")
        # The klaxon is zone-wide: Raven hears it a room away.
        assert "SELF-DESTRUCT SEQUENCE INITIATED" in text(sim, raven)
        assert brain.db.get("pending")

        await sim.engine.tick_waits()      # one chain stage
        assert "SELF-DESTRUCT IN" in text(sim, raven)
        assert brain.db.get("count") == 4

        # Wrong code first -- the countdown keeps its nerve.
        await sim.do(raven, "abort")
        assert "Enter the abort code:" in text(sim, raven)
        handler = sim.session(raven).input_handler
        assert handler is not None, "prompt() should capture the next line"
        await handler(sim.session(raven), "WOMBAT")
        assert "INVALID CODE. The countdown continues." in text(sim, raven)
        assert brain.db.get("pending")

        # Right code, from the Cargo Bay -- the zone master hears it there.
        sim.seen(builder)
        await sim.do(raven, "abort")
        handler = sim.session(raven).input_handler
        await handler(sim.session(raven), "ZEBRA-9")
        assert "SELF-DESTRUCT ABORTED. Authorization: Raven." in text(sim, builder)
        assert brain.db.get("pending") is None
        assert brain.db.get("count") is None

        # The cancelled wait never fires; nothing burns.
        await sim.engine.tick_waits()
        assert objs(sim, "a sheet of roaring flame") == []

        # The code itself is engine-secret to strangers, readable to the owner.
        stolen, _err = await sim.eval(
            raven, "result = get_attr(get('Station Brain'), 'code')")
        assert stolen is None
        own, _err = await sim.eval(
            builder, "result = get_attr(get('Station Brain'), 'code')")
        assert own == "ZEBRA-9"

    async def test_zero_hour_burns_every_compartment(self, sim):
        builder = await build(sim, BUILD_56)
        raven = sim.player("Raven", location=room(sim, "Cargo Bay"),
                           hp=20, max_hp=20)
        await run_lines(sim, builder, ["@set Station Brain/interval = 0"])

        await sim.do(builder, "self destruct")
        for _ in range(5):                 # stages 4, 3, 2, 1, boom
            await sim.engine.tick_waits()

        assert "Fire tears through every compartment!" in text(sim, raven)
        flames = objs(sim, "a sheet of roaring flame")
        assert {f.location for f in flames} == {
            room(sim, "Reactor Core"), room(sim, "Cargo Bay")}
        brain = obj(sim, "Station Brain")
        assert brain.db.get("pending") is None

        # The flames are proximity hazards on their own heartbeat.
        for flame in flames:
            for behavior in list(flame.get_behaviors()):
                await behavior.tick(flame, 1.0)
        assert "Fire roars over you!" in text(sim, raven)
        assert raven.db.get("hp") < 20

        # ...and they gutter out on their expire() fuel.
        reaped = await reap_expired(sim.store, now=time.time() + 120)
        assert reaped == 2
        assert objs(sim, "a sheet of roaring flame") == []


# --- 57. EMP charge -------------------------------------------------------------


class TestEmpCharge:

    async def test_pulse_disables_and_expiry_restores(self, sim):
        builder = await build(sim, BUILD_57)
        lab = room(sim, "The Drone Lab")
        raven = sim.player("Raven", location=lab)

        # Baseline: both gadgets answer.
        await sim.do(raven, "ping drone")
        assert "ALL SYSTEMS NOMINAL." in text(sim, raven)
        await sim.do(raven, "login")
        assert "ACCESS GRANTED." in text(sim, raven)

        # Refuses to fire in hand.
        await sim.do(builder, "get EMP charge")
        sim.seen(builder)
        await sim.do(builder, "arm emp")
        assert "Set it down first." in text(sim, builder)
        await sim.do(builder, "drop EMP charge")

        # The pulse: sweep, remember, go dark.
        await sim.do(raven, "arm emp")
        assert "A soundless white PULSE." in text(sim, raven)
        drone = obj(sim, "sweeper drone")
        terminal = obj(sim, "wall terminal")
        charge = obj(sim, "EMP charge")
        assert drone.has_tag("disabled")
        assert terminal.has_tag("disabled")
        assert len(charge.db.get("hit")) == 2
        assert charge.db.get("expires_at")

        await sim.do(raven, "ping drone")
        assert "The drone lies inert, rotors still." in text(sim, raven)
        await sim.do(raven, "login")
        assert "The screen is dead glass." in text(sim, raven)

        # The restore rides ON_EXPIRE; the casing dies with the effect.
        reaped = await reap_expired(sim.store, now=time.time() + 60)
        assert reaped == 1
        assert not drone.has_tag("disabled")
        assert not terminal.has_tag("disabled")
        assert objs(sim, "EMP charge") == []
        assert "status lights flicker back to life" in text(sim, raven)

        await sim.do(raven, "ping drone")
        assert "ALL SYSTEMS NOMINAL." in text(sim, raven)


# --- 58. Spreading fire ---------------------------------------------------------


def fires_in(sim, where):
    return [f for f in objs(sim, "a hungry fire") if f.location is where]


class TestSpreadingFire:

    async def test_growth_spread_doors_and_extinguisher(self, sim):
        builder = await build(sim, BUILD_58)
        hayloft = room(sim, "The Hayloft")
        stable = room(sim, "The Stable")
        tack = room(sim, "The Tack Room")
        limbo = room(sim, "Limbo")
        assert builder.location is hayloft
        mook = sim.player("Mook", location=hayloft, hp=20, max_hp=20)
        groom = sim.player("Groom", location=stable, hp=20, max_hp=20)

        await sim.do(builder, "light fire")
        assert "drops a lit match into the straw. Flames catch!" in text(sim, mook)
        fire = fires_in(sim, hayloft)[0]

        # Stage 1: smolder, narration only.
        await pulse(fire)
        assert "Smoke thickens. Flames crawl wider." in text(sim, mook)
        assert mook.db.get("hp") == 20
        assert fire.db.get("stage") == 2

        # Stage 2: it burns whoever stands in it.
        await pulse(fire)
        assert "The blaze sears you!" in text(sim, mook)
        assert mook.db.get("hp") < 20
        assert fire.db.get("stage") == 3

        # Stage 3: inferno -- and it jumps the open ladderway.
        sim.seen(groom)
        await pulse(fire)
        assert "Fire licks through the doorway -- it catches!" in text(sim, groom)
        assert len(fires_in(sim, stable)) == 1
        assert fires_in(sim, tack) == []       # the shut tack door held
        assert fires_in(sim, limbo) == []      # so did the shut yard door
        assert fire.db.get("stage") == 3       # capped

        # Counterplay, stage by stage.
        sim.seen(builder)
        await sim.do(builder, "spray fire")
        assert "drives the fire back with a jet of foam!" in text(sim, builder)
        assert fire.db.get("stage") == 2
        await sim.do(builder, "spray fire")
        assert fire.db.get("stage") == 1
        await sim.do(builder, "spray fire")
        assert "smothers the last flames in a white cloud." in text(sim, builder)
        assert fires_in(sim, hayloft) == []

        # The stable fire is its own cell -- kill it before it rages.
        await sim.do(builder, "ladder")
        sim.seen(builder)
        await sim.do(builder, "spray fire")    # stage-1 fire dies to one spray
        assert "smothers the last flames" in text(sim, builder)
        assert objs(sim, "a hungry fire") == []

        await sim.do(builder, "spray fire")
        assert "Nothing here is burning." in text(sim, builder)


# --- 59. Tranquilizer mechanics -------------------------------------------------


class TestTranquilizer:

    async def test_knockout_engine_lockout_and_natural_wakeup(self, sim):
        builder = await build(sim, BUILD_59)
        medbay = room(sim, "The Med Bay")
        brick = sim.player("Brick", location=medbay,
                           hp=13, max_hp=13, health=13)   # fortitude 13-3=10
        zeke = sim.player("Zeke", location=medbay,
                          hp=13, max_hp=13, health=8)     # fortitude 8-3=5

        await sim.do(builder, "shoot Brick")
        assert "Your vision swims... then steadies." in text(sim, brick)
        assert not brick.has_tag("unconscious")

        await sim.do(builder, "shoot Zeke")
        assert "The room smears sideways. Then nothing." in text(sim, zeke)
        assert "Zeke crumples bonelessly to the floor." in text(sim, brick)
        assert zeke.has_tag("unconscious")
        assert zeke.db.get("hp") == 13         # no HP damage: a knockout

        # The engine's own gates close: no walking, no fighting.
        await sim.do(zeke, "out")
        assert "You are unconscious." in text(sim, zeke)
        assert zeke.location is medbay
        await sim.do(zeke, "attack Brick")
        assert "You are unconscious." in text(sim, zeke)

        # Six beats of sedation, then the effect expires itself.
        for _ in range(6):
            await deliver_beat(zeke)
        assert not zeke.has_tag("unconscious")
        assert "You come to, cheek on the cold deck." in text(sim, zeke)
        await sim.do(zeke, "out")
        assert zeke.location is room(sim, "Limbo")

    async def test_stim_injector_wakes_early_and_misses_gracefully(self, sim):
        builder = await build(sim, BUILD_59)
        medbay = room(sim, "The Med Bay")
        brick = sim.player("Brick", location=medbay,
                           hp=13, max_hp=13, health=13)
        zeke = sim.player("Zeke", location=medbay,
                          hp=13, max_hp=13, health=8)

        await sim.do(builder, "jab Brick")
        assert "They are not sedated." in text(sim, builder)

        await sim.do(builder, "shoot Zeke")
        assert zeke.has_tag("unconscious")
        await sim.do(builder, "jab Zeke")
        assert "They jolt awake." in text(sim, builder)
        assert not zeke.has_tag("unconscious")
        await sim.do(zeke, "out")
        assert zeke.location is room(sim, "Limbo")

    async def test_missing_target_is_a_clean_miss(self, sim):
        builder = await build(sim, BUILD_59)
        sim.seen(builder)
        await sim.do(builder, "shoot Nobody")
        assert "No sign of them in reach." in text(sim, builder)
