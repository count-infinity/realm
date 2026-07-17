"""
Showcase "Rooms & Environment" — checklist items 36-47.

Verifies the tutorials docs/showcase/036_weather_system.md ..
047_falling.md by driving a real in-process world — the
realm.testing.Simulator wires the same store/propagation/scripting/
dispatcher stack a live GameServer does — with the tutorials' EXACT
command lines (raw input in, session output out).

The build transcripts below are copied verbatim from the docs' "Build
it" sections; the doc-sync test at the bottom keeps them from drifting.

Determinism: skill checks are pinned with a level-based resolver (the
infiltration-test trick); rand()/dice()/roll() are pinned by patching
random.randint in both realm.scripting.functions and realm.core.dice.
Behavior ticks are pumped by calling the attached behavior's tick()
directly (no wall-clock heartbeat), like the living-NPCs arc tests.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from realm.core import instances, wilderness
from realm.testing import Simulator

# Output that must never appear while running a "Build it" transcript.
BUILD_FAILURE_MARKERS = (
    "Unknown command",
    "Permission denied",
    "Usage:",
    "not found",
    "Script error",
    "Eval error",
    "Bad condition",
    "Bad parameter",
    "Unknown behavior",
)


# --- Harness ---------------------------------------------------------------


@pytest.fixture
def sim():
    s = Simulator()
    wilderness.reset()
    try:
        yield s
    finally:
        wilderness.reset()
        s.close()


@pytest.fixture
def leveled(sim):
    """Diceless checks: success iff skill level + modifier >= 10.

    Yields an installer to call AFTER the build transcript — a build's
    @reload line re-installs the game system's dice resolver, so the
    deterministic one must go in last.
    """
    from realm.core.checks import CheckResult, set_check_resolver, skill_level

    def level_resolver(obj, skill, modifier):
        effective = skill_level(obj, skill) + modifier
        return CheckResult(effective >= 10, effective - 10, 10,
                           effective, skill)

    def install():
        set_check_resolver(level_resolver)

    yield install
    set_check_resolver(None)


@pytest.fixture
def pinned_rand(monkeypatch):
    """Pin every randint both rand()/dice() and core roll() draw from."""
    holder = {"value": 1}

    def fake_randint(low, high):
        return max(low, min(holder["value"], high))

    monkeypatch.setattr(
        "realm.scripting.functions.random.randint", fake_randint)
    monkeypatch.setattr("realm.core.dice.random.randint", fake_randint)
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
    return "\n".join(sim.seen(player))


def find_one(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no object named {name!r} in the world"
    return matches[0]


def _behavior(obj, behavior_id="script_ticker"):
    return next(b for b in obj.get_behaviors()
                if b.behavior_id == behavior_id)


async def tick(obj, times=1):
    behavior = _behavior(obj)
    for _ in range(times):
        await behavior.tick(obj, 4.0)


# =========================================================================
# 036. Weather system — docs/showcase/036_weather_system.md
# =========================================================================

WEATHER_BUILD = [
    "@dig Harbor Quay = quay, back",
    "quay",
    "@zone here = harbor",
    "@dig Fishmarket Row = row, quay",
    "row",
    "@zone here = harbor",
    "quay",
    "@create Harbor Sky",
    "@zone/master Harbor Sky = harbor",
    "drop Harbor Sky",
    "@set Harbor Sky/weather = clear",
    '@set Harbor Sky/wx_states = ["clear", "overcast", "rain", "storm"]',
    '@set Harbor Sky/wx_msgs = {"clear": "The cloud breaks; pale sun lights '
    'the water.", "overcast": "A grey ceiling slides in off the sea.", '
    '"rain": "Rain sets in, beading on rope and rail.", "storm": "The wind '
    'climbs to a howl; rain comes in sideways."}',
    '@set Harbor Sky/wx_descs = {"clear": "Sunlight hammers the tin roofs.", '
    '"overcast": "The light sits flat under a grey lid of cloud.", '
    '"rain": "Rain hisses on the harbor water.", "storm": "Spray and rain '
    'scour the planking."}',
    "@set Harbor Sky/on_tick = states = V('wx_states', []); "
    "i = member(V('weather', 'clear'), states) - 1; "
    "j = clamp(i + rand(0, 2) - 1, 0, len(states) - 1); "
    "(set_attr(me, 'weather', states[j]), [(set_attr(r, 'wx_line', "
    "V('wx_descs', {}).get(states[j], '')), remit(r, "
    "V('wx_msgs', {}).get(states[j], ''))) for r in "
    "zone_rooms('harbor')]) if i >= 0 and j != i else None",
    "@behavior Harbor Sky = script_ticker, interval:15",
    "@set here/wx_line = Sunlight hammers the tin roofs.",
    "@desc here = Tarred pilings, drying nets, gulls arguing over fish "
    "heads. [[result = V('wx_line', '')]]",
]


class TestWeatherSystem:

    async def test_drift_broadcasts_to_the_whole_zone(
            self, sim, pinned_rand):
        _room, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess")
        outsider = sim.player("Odd")
        outsider.location = _room
        await build(sim, bilda, WEATHER_BUILD)
        kess.location = find_one(sim, "Fishmarket Row")
        sky = find_one(sim, "Harbor Sky")
        sim.seen(kess), sim.seen(outsider)

        # Force one drift roll through the dispatcher (the Try-it line).
        pinned_rand["value"] = 3          # rand(0, 2) -> 2 -> step +1
        out = await do(sim, bilda, "@tr Harbor Sky/on_tick")
        assert sky.db.get("weather") == "overcast"
        assert "A grey ceiling slides in off the sea." in out
        assert ("A grey ceiling slides in off the sea."
                in "\n".join(sim.seen(kess)))
        # Outside the zone: silence.
        assert "grey ceiling" not in "\n".join(sim.seen(outsider))

        # The desc reads the shared state.
        out = await do(sim, bilda, "look")
        assert "The light sits flat under a grey lid of cloud." in out

    async def test_ticker_drifts_and_the_table_clamps(self, sim, pinned_rand):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, WEATHER_BUILD)
        sky = find_one(sim, "Harbor Sky")

        # The attached ticker drives the same drift (interval:15).
        pinned_rand["value"] = 3
        await tick(sky, 15)
        assert sky.db.get("weather") == "overcast"

        # A no-step roll changes nothing and says nothing.
        sim.seen(bilda)
        pinned_rand["value"] = 1          # rand(0, 2) -> 1 -> step 0
        await tick(sky, 15)
        assert sky.db.get("weather") == "overcast"
        assert sim.seen(bilda) == []

        # Clamped at the top: storm + worsening roll stays storm, silently.
        await do(sim, bilda, "@set Harbor Sky/weather = storm")
        sim.seen(bilda)
        pinned_rand["value"] = 3
        await tick(sky, 15)
        assert sky.db.get("weather") == "storm"
        assert sim.seen(bilda) == []

        # And it can clear again.
        pinned_rand["value"] = 0          # rand(0, 2) -> 0 -> step -1
        await tick(sky, 15)
        assert sky.db.get("weather") == "rain"
        assert ("Rain sets in, beading on rope and rail."
                in "\n".join(sim.seen(bilda)))


# =========================================================================
# 037. Day/night cycle — docs/showcase/037_day_night_descs.md
# =========================================================================

DAYNIGHT_BUILD = [
    "@dig Sundial Plaza = plaza, back",
    "plaza",
    "@zone here = town",
    "@tag here = outdoors",
    "@create town clock",
    "drop town clock",
    "@set town clock/hour = 8",
    "@set town clock/on_tick = h = (V('hour', 0) + 1) % 24; "
    "set_attr(me, 'hour', h); night = h >= 21 or h < 6; "
    "dp = 'night' if night else ('morning' if h < 12 else 'afternoon'); "
    "[(set_attr(r, 'daypart', dp), (add_tag(r, 'dark') if night else "
    "remove_tag(r, 'dark'))) for r in zone_rooms('town') "
    "if has_tag(r, 'outdoors')]",
    "@behavior town clock = script_ticker, interval:1",
    "@desc here = A worn sundial crowns the plaza. [[dp = V('daypart', "
    "'morning'); result = 'Lamplight pools on the cobbles, "
    "and the gnomon points at nothing.' if dp == 'night' else "
    "('Long morning shadows sweep the dial.' if dp == 'morning' else "
    "'The gnomon leans into the afternoon light.')]]",
]


class TestDayNightCycle:

    async def test_desc_and_darkness_follow_the_clock(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, DAYNIGHT_BUILD)
        clock = find_one(sim, "town clock")
        plaza = find_one(sim, "Sundial Plaza")

        out = await do(sim, bilda, "look")               # hour 8
        assert "Long morning shadows sweep the dial." in out

        await tick(clock, 5)                             # hour 13
        assert clock.db.get("hour") == 13
        out = await do(sim, bilda, "look")
        assert "The gnomon leans into the afternoon light." in out
        assert not plaza.has_tag("dark")

        await tick(clock, 9)                             # hour 22: night
        assert clock.db.get("hour") == 22
        assert plaza.has_tag("dark")
        out = await do(sim, bilda, "look")
        assert "It is pitch black here." in out

        # Night sight reads the night line of the same desc.
        bilda.add_tag("nightvision")
        out = await do(sim, bilda, "look")
        assert ("Lamplight pools on the cobbles, and the gnomon points "
                "at nothing." in out)

        await tick(clock, 8)                             # hour 6: dawn
        assert clock.db.get("hour") == 6
        assert not plaza.has_tag("dark")
        out = await do(sim, bilda, "look")
        assert "Long morning shadows sweep the dial." in out


# =========================================================================
# 038. Dark room — docs/showcase/038_dark_room.md
# =========================================================================

DARKROOM_BUILD = [
    "@dig The Undercroft = down, up",
    "@create storm lantern",
    "@tag storm lantern = light",
    "@create tinker goggles",
    "@tag tinker goggles = wearable",
    "@set tinker goggles/slot = eyes",
    '@set tinker goggles/grants_tags = ["nightvision"]',
    "down",
    "@tag here = dark",
    "@desc here = Brick vaults sweat cold water. Something small scurries "
    "at the edge of hearing.",
    "@create scattered bones",
    "drop scattered bones",
    "up",
]


class TestDarkRoom:

    async def test_darkness_blinds_and_light_or_goggles_beat_it(self, sim):
        room, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=room)
        await build(sim, bilda, DARKROOM_BUILD)
        undercroft = find_one(sim, "The Undercroft")
        bones = find_one(sim, "scattered bones")
        sim.seen(kess)

        # No light: pitch black, and unseen means untargetable.
        out = await do(sim, kess, "down")
        assert "It is pitch black here. You can't see a thing." in out
        out = await do(sim, kess, "get bones")
        assert "You don't see 'bones' here." in out
        assert bones.location is undercroft
        await do(sim, kess, "up")

        # Goggles: wearable grants_tags confers nightvision while worn.
        out = await do(sim, bilda, "give tinker goggles to Kess")
        out = await do(sim, kess, "wear tinker goggles")
        assert "You put on the tinker goggles." in out
        assert kess.has_tag("nightvision")
        out = await do(sim, kess, "down")
        assert "The Undercroft" in out
        assert "scattered bones" in out

        # A carried lantern lights nothing until it's held up.
        out = await do(sim, bilda, "down")
        assert "It is pitch black here. You can't see a thing." in out
        out = await do(sim, bilda, "wield storm lantern")
        assert "You ready storm lantern." in out
        out = await do(sim, bilda, "look")
        assert "The Undercroft" in out and "scattered bones" in out

        # Set down, the light source lights the room for everyone.
        await do(sim, bilda, "drop storm lantern")
        out = await do(sim, bilda, "look")
        assert "The Undercroft" in out


# =========================================================================
# 039. Underwater room — docs/showcase/039_underwater_room.md
# =========================================================================

UNDERWATER_BUILD = [
    "@create swimming",
    "@tag swimming = skill_def",
    "@set swimming/stat = health",
    "@set swimming/penalty = -4",
    "@reload",
    "@dig Flooded Cistern = dive, surface",
    "dive",
    "@desc here = Green water in a drowned vault; light falls in wavering "
    "shafts from a grate far above.",
    "@set here/breath_max = 3",
    "@set here/on_enter = pemit(enactor, 'You knife under. The cold clamps "
    "down; hold your breath.') if has_tag(enactor, 'player') else None",
    "@set here/on_leave = (del_attr(me, 'breath_' + enactor.id), "
    "pemit(enactor, 'You break the surface and drag in a long breath.')) "
    "if has_tag(enactor, 'player') else None",
    "@set here/soak = o = get('#' + arg0); k = 'breath_' + o.id; "
    "pemit(o, 'You pace your strokes and hold what air you have.') "
    "if skill_check(o, 'swimming') else (set_attr(me, k, V(k, "
    "V('breath_max', 3)) - 1), pemit(o, 'Your chest heaves. "
    "You are running out of air!') if V(k, 0) > 0 else "
    "(damage(o, roll('1d6')), pemit(o, 'Water forces its way in. "
    "You are drowning!')))",
    "@set here/on_tick = [eval_attr(me, 'soak', o.id) for o in contents(me) "
    "if has_tag(o, 'player')]",
    "@behavior here = script_ticker, interval:1",
    "surface",
]


class TestUnderwaterRoom:

    async def test_breath_meter_drowning_and_surfacing(
            self, sim, leveled, pinned_rand):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, UNDERWATER_BUILD)
        leveled()
        cistern = find_one(sim, "Flooded Cistern")
        key = "breath_" + bilda.id

        for line in ("@set me/hp = 12", "@set me/max_hp = 12",
                     "@set me/health = 12", "@set me/skill_swimming = 14"):
            await do(sim, bilda, line)

        out = await do(sim, bilda, "dive")
        assert "You knife under. The cold clamps down; hold your breath." in out

        # A made roll spends nothing.
        await tick(cistern)
        assert ("You pace your strokes and hold what air you have."
                in "\n".join(sim.seen(bilda)))
        assert cistern.db.get(key) is None

        # Failed rolls burn the meter: 3 -> 2 -> 1 -> 0.
        await do(sim, bilda, "@set me/skill_swimming = 3")
        await tick(cistern)
        assert cistern.db.get(key) == 2
        assert ("Your chest heaves. You are running out of air!"
                in "\n".join(sim.seen(bilda)))
        await tick(cistern)
        assert cistern.db.get(key) == 1
        pinned_rand["value"] = 3                  # roll('1d6') -> 3
        await tick(cistern)
        assert cistern.db.get(key) == 0
        assert "Water forces its way in. You are drowning!" in "\n".join(
            sim.seen(bilda))
        assert bilda.db.get("hp") == 9

        # Every further failed tick drowns for another die.
        await tick(cistern)
        assert bilda.db.get("hp") == 6

        # Surfacing resets the meter and says so.
        out = await do(sim, bilda, "surface")
        assert "You break the surface and drag in a long breath." in out
        assert cistern.db.get(key) is None


# =========================================================================
# 040. Zero-G compartment — docs/showcase/040_zero_g_room.md
# =========================================================================

ZEROG_BUILD = [
    "@create freefall",
    "@tag freefall = skill_def",
    "@set freefall/stat = dexterity",
    "@set freefall/penalty = -5",
    "@reload",
    "@dig Cargo Bay Zero-G = bay, aft",
    "bay",
    "@desc here = Cargo nets sag from every bulkhead and nothing agrees "
    "on which way is down.",
    "@set here/on_check = block('You kick against nothing and drift in "
    "place. Grab a handhold and push <exit> instead.') if atype == "
    "'event:on_leave' and has_atag('movement') and not has_atag('zerog') "
    "and has_tag(actor, 'player') else None",
    "@set here/cmd_push = $push *: nm = trim(arg0).lower(); "
    "ex = [e for e in contents(me) if has_tag(e, 'exit') and name(e) == nm]; "
    "pemit(enactor, 'No handhold faces that way.') if not ex else "
    "((move_to(enactor, get('#' + str(get_attr(ex[0], 'destination', ''))), "
    "tags=['zerog']), pemit(enactor, f'You coil, kick off, and sail "
    "through the {nm} hatch.'), remit(me, f'{name(enactor)} kicks off a "
    "bulkhead and sails out through the {nm} hatch.')) "
    "if skill_check(enactor, 'freefall') else (pemit(enactor, 'You misjudge "
    "the kick and tumble; the hatch drifts past your fingers.'), "
    "remit(me, name(enactor) + ' tumbles slowly in midair, pawing at "
    "nothing.')))",
    "@set here/cmd_flail = $flail: pemit(enactor, 'You windmill your arms. "
    "It achieves nothing, beautifully.'); remit(me, name(enactor) + "
    "' windmills in place, going exactly nowhere.')",
]


class TestZeroGCompartment:

    async def test_walk_blocked_push_moves_tumble_stays(self, sim, leveled):
        workshop, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=workshop)
        await build(sim, bilda, ZEROG_BUILD)
        leveled()
        bay = find_one(sim, "Cargo Bay Zero-G")
        assert bilda.location is bay

        # Ordinary walking is vetoed with drift flavor.
        out = await do(sim, bilda, "aft")
        assert ("You kick against nothing and drift in place. Grab a "
                "handhold and push <exit> instead." in out)
        assert bilda.location is bay

        # Themed verbs the engine doesn't have.
        out = await do(sim, bilda, "flail")
        assert "You windmill your arms. It achieves nothing, beautifully." in out

        out = await do(sim, bilda, "push mainmast")
        assert "No handhold faces that way." in out

        # Walking IN is fine; the ward only guards leaving.
        await do(sim, kess, "bay")
        assert kess.location is bay
        sim.seen(kess)

        # A trained push sails through the ward (the zerog tag).
        await do(sim, bilda, "@set me/skill_freefall = 14")
        out = await do(sim, bilda, "push aft")
        assert "You coil, kick off, and sail through the aft hatch." in out
        assert bilda.location is workshop
        assert ("Bilda kicks off a bulkhead and sails out through the aft "
                "hatch." in "\n".join(sim.seen(kess)))

        # An untrained push tumbles in place.
        await do(sim, bilda, "bay")
        await do(sim, bilda, "@set me/skill_freefall = 3")
        sim.seen(kess)
        out = await do(sim, bilda, "push aft")
        assert ("You misjudge the kick and tumble; the hatch drifts past "
                "your fingers." in out)
        assert bilda.location is bay
        assert ("Bilda tumbles slowly in midair, pawing at nothing."
                in "\n".join(sim.seen(kess)))


# =========================================================================
# 041. Ambient room messages — docs/showcase/041_ambient_messages.md
# =========================================================================

AMBIENT_BUILD = [
    "@dig The Long Gallery = gallery, back",
    "gallery",
    "@create cold draft",
    "drop cold draft",
    '@set cold draft/lines = ["A cold draft worries the candle flames.", '
    '"Somewhere above, timbers settle with a groan.", "Dust sifts down '
    'from the rafters."]',
    "@set cold draft/chance = 25",
    "@set cold draft/on_tick = lines = V('lines', []); "
    "(remit(here, lines[rand(0, len(lines) - 1)]) if lines and "
    "[o for o in contents(here) if has_tag(o, 'player')] else None) "
    "if rand(1, 100) <= V('chance', 25) else None",
    "@behavior cold draft = script_ticker, interval:8",
    "@tag cold draft = invisible",
]


class TestAmbientMessages:

    async def test_gated_flavor_with_spam_discipline(self, sim, pinned_rand):
        workshop, bilda = workshop_and_builder(sim)
        await build(sim, bilda, AMBIENT_BUILD)
        draft = find_one(sim, "cold draft")

        # The emitter never shows in the room listing.
        out = await do(sim, bilda, "look")
        assert "cold draft" not in out

        # Gate open: the tick remits a line to the occupied room.
        pinned_rand["value"] = 1          # gate 1<=25; line index 1
        await tick(draft)                 # first pump fires (countdown at 0)
        assert ("Somewhere above, timbers settle with a groan."
                in "\n".join(sim.seen(bilda)))

        # Gate closed: the interval elapses in silence.
        pinned_rand["value"] = 100
        await tick(draft, 8)
        assert sim.seen(bilda) == []

        # Audience gate: an empty room doesn't perform.
        await do(sim, bilda, "back")
        sim.seen(bilda)
        pinned_rand["value"] = 1
        await tick(draft, 8)
        assert sim.seen(bilda) == []


# =========================================================================
# 042. Room details — docs/showcase/042_room_details.md
# =========================================================================

DETAILS_BUILD = [
    "@dig Records Annex = annex, out",
    "annex",
    "@desc here = Steel shelving marches into the gloom, every bay tagged "
    "in fading ink.",
    "@detail here = A brass plaque is bolted beside the door.",
    "@detail here = check('observation', -2) -> One shelf bay sits "
    "fractionally shallower than its neighbors - a false back, maybe.",
    '@set here/vtargets = {"plaque": "COLLECTION 9 - DONATED. The donor\'s '
    'name has been filed off.", "shelves": "Harbor manifests, mostly. '
    'A century of them, and nobody has opened one twice."}',
    "@set here/cmd_study = $study *: t = trim(arg0).lower(); "
    "d = V('vtargets', {}); pemit(enactor, d.get(t, f'You find "
    "nothing else worth studying about the {t}.'))",
]


class TestRoomDetails:

    async def test_details_render_per_viewer(self, sim, leveled):
        workshop, bilda = workshop_and_builder(sim)
        sharp = sim.player("Kess", location=workshop)
        sharp.db.set("skill_observation", 14)
        dull = sim.player("Tam", location=workshop)
        await build(sim, bilda, DETAILS_BUILD)
        leveled()

        out = await do(sim, sharp, "annex")
        assert "A brass plaque is bolted beside the door." in out
        assert "a false back, maybe." in out

        out = await do(sim, dull, "annex")
        assert "A brass plaque is bolted beside the door." in out
        assert "a false back, maybe." not in out

    async def test_named_virtual_targets_via_study(self, sim, leveled):
        workshop, bilda = workshop_and_builder(sim)
        await build(sim, bilda, DETAILS_BUILD)
        leveled()

        # The builtin boundary: look resolves objects, not details.
        out = await do(sim, bilda, "look plaque")
        assert "You don't see 'plaque' here." in out

        out = await do(sim, bilda, "study plaque")
        assert ("COLLECTION 9 - DONATED. The donor's name has been filed "
                "off." in out)
        out = await do(sim, bilda, "study shelves")
        assert "Harbor manifests, mostly." in out
        out = await do(sim, bilda, "study rug")
        assert "You find nothing else worth studying about the rug." in out

    async def test_detail_housekeeping(self, sim, leveled):
        workshop, bilda = workshop_and_builder(sim)
        sharp = sim.player("Kess", location=workshop)
        sharp.db.set("skill_observation", 14)
        await build(sim, bilda, DETAILS_BUILD)
        leveled()
        await do(sim, sharp, "annex")

        out = await do(sim, bilda, "@detail here")
        assert "1. [(always)] A brass plaque is bolted beside the door." in out
        assert "2. [check('observation', -2)]" in out

        out = await do(sim, bilda, "@detail/remove here = 2")
        assert "Removed detail #2" in out
        sim.seen(sharp)
        out = await do(sim, sharp, "look")
        assert "a false back, maybe." not in out
        assert "A brass plaque is bolted beside the door." in out


# =========================================================================
# 043. Hazard room — docs/showcase/043_hazard_room.md
# =========================================================================

HAZARD_BUILD = [
    "@create fortitude",
    "@tag fortitude = skill_def",
    "@set fortitude/stat = health",
    "@set fortitude/penalty = 0",
    "@reload",
    "@dig Reactor Gallery = catwalk, out",
    "catwalk",
    "@zone here = reactor",
    "@create Reactor Brain",
    "@zone/master Reactor Brain = reactor",
    "drop Reactor Brain",
    "@set Reactor Brain/rad_level = 1",
    "@desc here = A steel catwalk rings the exposed core. The air is warm "
    "and tastes of foil. [[result = 'Your dosimeter ticks ' + ('lazily.' "
    "if V('rad_sv', 1) < 3 else 'without pause.')]]",
    "@set here/on_tick = sv = get_attr('Reactor Brain', 'rad_level', 1); "
    "set_attr(me, 'rad_sv', sv); "
    "[(pemit(o, 'Heat prickles across your skin; you ride it out.') if "
    "skill_check(o, 'fortitude', -sv) else (damage(o, roll('1d6')), "
    "pemit(o, 'Nausea doubles you over. The core is cooking you.'))) "
    "for o in contents(me) if has_tag(o, 'player')]",
    "@behavior here = script_ticker, interval:2",
]


class TestHazardRoom:

    async def test_resisted_damage_scales_with_zone_severity(
            self, sim, leveled, pinned_rand):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, HAZARD_BUILD)
        leveled()
        gallery = find_one(sim, "Reactor Gallery")

        for line in ("@set me/health = 12", "@set me/hp = 12",
                     "@set me/max_hp = 12"):
            await do(sim, bilda, line)

        # Severity 1: HT 12 at -1 = 11 -> resisted.
        out = await do(sim, bilda, "look")
        assert "Your dosimeter ticks lazily." in out
        await tick(gallery)
        assert ("Heat prickles across your skin; you ride it out."
                in "\n".join(sim.seen(bilda)))
        assert bilda.db.get("hp") == 12

        # Crank the zone master: the next sweep burns AND re-stamps
        # the dosimeter label the desc reads.
        await do(sim, bilda, "@set Reactor Brain/rad_level = 3")
        pinned_rand["value"] = 4          # roll('1d6') -> 4
        await tick(gallery, 2)            # countdown skip + fire
        assert ("Nausea doubles you over. The core is cooking you."
                in "\n".join(sim.seen(bilda)))
        assert bilda.db.get("hp") == 8
        out = await do(sim, bilda, "look")
        assert "Your dosimeter ticks without pause." in out

        # The hazard ends at the hatch.
        await do(sim, bilda, "out")
        await tick(gallery, 2)
        assert bilda.db.get("hp") == 8


# =========================================================================
# 044. Instanced room — docs/showcase/044_instanced_room.md
# =========================================================================

INSTANCE_BUILD = [
    "@dig Dust Motel Suite",
    "@teleport me = Dust Motel Suite",
    "@zone here = suite",
    "@tag here = instance_template",
    "@tag here = instance_entry",
    "@desc here = Bed, basin, and a window painted shut. Not much - but "
    "tonight, it is yours alone.",
    "@open lobby = The Workshop",
    "@dig Suite Washroom = washroom, out",
    "washroom",
    "@zone here = suite",
    "out",
    "@teleport me = The Workshop",
    "@create suite door",
    "@tag suite door = exit",
    "drop suite door",
    "@set suite door/dest_resolver = instance",
    "@set suite door/instance_template = suite",
    "@set suite door/instance_mode = solo",
    "@set suite door/instance_ttl = 600",
    "@create desk clerk",
    "drop desk clerk",
    "@set desk clerk/cmd_checkin = $check in: enter_instance(enactor, "
    "'suite', mode='solo', return_room=here, idle_ttl=600); "
    "pemit(enactor, 'The clerk slides a brass key across the desk.')",
]


class TestInstancedRoom:

    async def test_private_copies_reuse_and_reaping(self, sim):
        workshop, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=workshop)
        await build(sim, bilda, INSTANCE_BUILD)
        template = find_one(sim, "The Workshop")  # sanity anchor
        assert bilda.location is template

        # Walking the portal materializes a private ephemeral copy.
        await do(sim, bilda, "suite door")
        copy = bilda.location
        assert copy.name == "Dust Motel Suite"
        assert copy.has_tag("ephemeral")
        assert copy.has_tag(f"instance:suite:{bilda.id}")

        # The whole zone came along, connections intact.
        await do(sim, bilda, "washroom")
        assert bilda.location.name == "Suite Washroom"
        assert bilda.location.has_tag("ephemeral")
        await do(sim, bilda, "out")
        assert bilda.location is copy

        # The authored static exit leads back to the real world...
        await do(sim, bilda, "lobby")
        assert bilda.location is workshop
        # ...and re-walking reuses the same copy.
        await do(sim, bilda, "suite door")
        assert bilda.location is copy

        # A second guest gets their own suite.
        await do(sim, kess, "suite door")
        assert kess.location is not copy
        assert kess.location.has_tag(f"instance:suite:{kess.id}")

        # The scripted seam: the clerk's $check in reuses your copy too.
        await do(sim, bilda, "lobby")
        await do(sim, kess, "lobby")
        out = await do(sim, bilda, "check in")
        assert "The clerk slides a brass key across the desk." in out
        assert bilda.location is copy

        # Empty past its TTL, a copy is reaped; re-walking makes it fresh.
        await do(sim, bilda, "lobby")
        reaped = await instances.reap_idle(
            sim.store, now=time.time() + 10_000)
        assert reaped == 2
        assert sim.store.get_cached(copy.id) is None
        await do(sim, bilda, "suite door")
        assert bilda.location is not copy
        assert bilda.location.has_tag(f"instance:suite:{bilda.id}")


# =========================================================================
# 045. Procedural wilderness — docs/showcase/045_procedural_wilderness.md
# =========================================================================

WILDS_BUILD = [
    "@create frontier",
    "@tag frontier = wilderness_region",
    "drop frontier",
    "@set frontier/is_valid = result = 0 <= x <= 20 and 0 <= y <= 20",
    "@set frontier/cell_name = result = ['Windswept Meadow', 'Pine Forest', "
    "'Rocky Scree', 'Creek Crossing'][(x * 7 + y * 13) % 4]",
    "@set frontier/cell_desc = result = ['Knee-high grass bends under a "
    "steady wind.', 'Pines crowd close, and the light falls in narrow "
    "blades.', 'Loose rock shifts underfoot between stubborn thistles.', "
    "'A cold creek chatters over smooth stones.'][(x * 7 + y * 13) % 4]",
    "@set frontier/edge_msg = The frontier ends in an impassable wall of "
    "bramble.",
    "@create trail gate",
    "@tag trail gate = exit",
    "drop trail gate",
    "@set trail gate/dest_resolver = wilderness",
    "@set trail gate/wild_region = frontier",
    "@set trail gate/wild_x = 10",
    "@set trail gate/wild_y = 10",
    "@create corner waystone",
    "drop corner waystone",
    "@set corner waystone/cmd_touch = $touch waystone: enter_wilderness("
    "enactor, 'frontier', 0, 0); pemit(enactor, 'The waystone drags the "
    "world sideways. You stand at the frontier corner-marker.')",
]


class TestProceduralWilderness:

    async def test_cells_materialize_share_and_edge(self, sim):
        workshop, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=workshop)
        await build(sim, bilda, WILDS_BUILD)

        # The gate drops the walker at the entry coordinate.
        await do(sim, bilda, "trail gate")
        entry_cell = bilda.location
        assert entry_cell.has_tag("wildcell:frontier:10,10")
        assert entry_cell.name == "Windswept Meadow"
        assert entry_cell.has_tag("ephemeral")

        # Walking materializes the neighbor on demand.
        out = await do(sim, bilda, "north")
        assert bilda.location.has_tag("wildcell:frontier:10,11")
        assert bilda.location.name == "Pine Forest"
        assert "Pines crowd close" in out

        # Cells are shared, not instanced.
        await do(sim, kess, "trail gate")
        assert kess.location is entry_cell

        # The scripted seam, and the map's edge.
        await do(sim, bilda, "@teleport me = The Workshop")
        out = await do(sim, bilda, "touch waystone")
        assert ("The waystone drags the world sideways. You stand at the "
                "frontier corner-marker." in out)
        assert bilda.location.has_tag("wildcell:frontier:0,0")

        out = await do(sim, bilda, "south")
        assert "The frontier ends in an impassable wall of bramble." in out
        assert bilda.location.has_tag("wildcell:frontier:0,0")
        out = await do(sim, bilda, "west")
        assert "The frontier ends in an impassable wall of bramble." in out
        assert wilderness.cell_for("frontier", 0, -1) is None

        # Empty cells reap; occupied ones survive.
        await do(sim, bilda, "@teleport me = The Workshop")
        reaped = await wilderness.reap_wilderness(
            sim.store, now=time.time() + 10_000)
        assert reaped >= 2                       # 10,11 and 0,0 were empty
        assert wilderness.cell_for("frontier", 10, 10) is entry_cell  # Kess
        kess.location = workshop
        # (the occupied sweep bumped last_active to its inflated now,
        # so the empty sweep must look even further ahead)
        await wilderness.reap_wilderness(sim.store, now=time.time() + 30_000)
        assert wilderness.cell_for("frontier", 10, 10) is None


# =========================================================================
# 046. Room capacity — docs/showcase/046_room_capacity.md
# =========================================================================

CAPACITY_BUILD = [
    "@dig Maintenance Closet = closet, out",
    "closet",
    "@set here/capacity = 2",
    "@set here/on_check = block(f'There is no room. {name(me)} is "
    "packed shoulder to shoulder.') if atype == 'event:pre_enter' and "
    "has_atag('movement') and has_tag(actor, 'player') and "
    "len([o for o in contents(me) if has_tag(o, 'player')]) >= "
    "V('capacity', 2) else None",
    "@desc here = Mop, bucket, fuse panel. Space for two people and one "
    "grudge. [[n = len([o for o in contents(me) if has_tag(o, 'player')]); "
    "result = f\"{n} of {V('capacity', 2)} spots are taken.\"]]",
    "out",
]


class TestRoomCapacity:

    async def test_third_body_is_bounced_until_a_spot_opens(self, sim):
        workshop, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=workshop)
        tam = sim.player("Tam", location=workshop)
        await build(sim, bilda, CAPACITY_BUILD)
        closet = find_one(sim, "Maintenance Closet")

        await do(sim, bilda, "closet")
        await do(sim, kess, "closet")
        assert bilda.location is closet and kess.location is closet

        out = await do(sim, tam, "closet")
        assert ("There is no room. Maintenance Closet is packed shoulder "
                "to shoulder." in out)
        assert tam.location is workshop

        # The count is live: one out, one in.
        await do(sim, kess, "out")
        await do(sim, tam, "closet")
        assert tam.location is closet

        out = await do(sim, bilda, "look")
        assert "2 of 2 spots are taken." in out


# =========================================================================
# 047. Falling between rooms — docs/showcase/047_falling.md
# =========================================================================

FALLING_BUILD = [
    "@dig Cliffside Ledge = ledge, back",
    "ledge",
    "@dig Scree Gully = down, up",
    "@desc here = A boot-wide shelf hugs the cliff face. Pebbles you "
    "dislodge take a long time to land.",
    "@set here/on_enter = k = 'fall_' + enactor.id; recent = now() - "
    "V(k, 0) < 5; safe = not has_tag(enactor, 'player') or "
    "recent or skill_check(enactor, 'climbing', -2); (pemit(enactor, "
    "'Scree shifts under your boots. You hug the rock and find your "
    "footing.') if has_tag(enactor, 'player') and not recent else None) "
    "if safe else (set_attr(me, k, now()), pemit(enactor, 'The lip "
    "crumbles under your boot. You are falling.'), teleport_obj(enactor, "
    "'Scree Gully'), damage(enactor, roll('2d6')), remit(me, name(enactor) "
    "+ ' misses a step and pitches over the edge!'), pemit(enactor, "
    "'You slam into the scree below. Everything hurts.'))",
    "back",
]


class TestFalling:

    async def test_climb_gate_fall_damage_and_reentry_guard(
            self, sim, leveled, pinned_rand):
        workshop, bilda = workshop_and_builder(sim)
        kess = sim.player("Kess", location=workshop)
        kess.db.set("skill_climbing", 14)
        await build(sim, bilda, FALLING_BUILD)
        leveled()
        ledge = find_one(sim, "Cliffside Ledge")
        gully = find_one(sim, "Scree Gully")

        # A witness who makes the roll keeps their footing.
        out = await do(sim, kess, "ledge")
        assert ("Scree shifts under your boots. You hug the rock and find "
                "your footing." in out)
        assert kess.location is ledge

        for line in ("@set me/hp = 14", "@set me/max_hp = 14",
                     "@set me/skill_climbing = 14"):
            await do(sim, bilda, line)

        # Trained: the ledge holds.
        out = await do(sim, bilda, "ledge")
        assert "find your footing." in out
        assert bilda.location is ledge
        await do(sim, bilda, "back")

        # Untrained: over the edge, 2d6 lighter, the room saw it happen.
        await do(sim, bilda, "@set me/skill_climbing = 4")
        sim.seen(kess)
        pinned_rand["value"] = 3                 # 2d6 -> 6
        out = await do(sim, bilda, "ledge")
        assert "The lip crumbles under your boot. You are falling." in out
        assert "You slam into the scree below. Everything hurts." in out
        assert bilda.location is gully
        assert bilda.db.get("hp") == 8
        assert ("Bilda misses a step and pitches over the edge!"
                in "\n".join(sim.seen(kess)))

        # The 5-second stamp: climbing right back up neither re-rolls
        # nor re-drops — the reentrancy guard.
        out = await do(sim, bilda, "up")
        assert bilda.location is ledge
        assert bilda.db.get("hp") == 8
        assert "falling" not in out


# =========================================================================
# Docs <-> tests sync — the transcripts above must match the tutorials
# =========================================================================

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

DOC_TRANSCRIPTS = {
    "036_weather_system.md": WEATHER_BUILD,
    "037_day_night_descs.md": DAYNIGHT_BUILD,
    "038_dark_room.md": DARKROOM_BUILD,
    "039_underwater_room.md": UNDERWATER_BUILD,
    "040_zero_g_room.md": ZEROG_BUILD,
    "041_ambient_messages.md": AMBIENT_BUILD,
    "042_room_details.md": DETAILS_BUILD,
    "043_hazard_room.md": HAZARD_BUILD,
    "044_instanced_room.md": INSTANCE_BUILD,
    "045_procedural_wilderness.md": WILDS_BUILD,
    "046_room_capacity.md": CAPACITY_BUILD,
    "047_falling.md": FALLING_BUILD,
}


def test_tutorial_docs_contain_the_exact_tested_command_lines():
    """Every Build-it line exercised above appears verbatim in its doc,
    so the tutorials can never drift from what the tests prove works."""
    for doc_name, lines in DOC_TRANSCRIPTS.items():
        text = (DOCS / doc_name).read_text(encoding="utf-8")
        for line in lines:
            assert line in text, (
                f"{doc_name} is missing a tested tutorial line:\n{line}")
