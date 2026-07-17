"""
Showcase verification — Communication Systems (standalone tutorials).

Items: 74 custom channel, 75 in-game mail, 76 bulletin boards,
77 handheld radios, 78 station PA system, 81 graffiti, 82 newspaper,
83 message in a bottle.  (79/80/84/85 are [small] speech-pipeline gaps
and are not covered here.)

Every command line in each tutorial's "Build it" section is read
straight out of its markdown (docs/showcase/NNN_*.md) and driven
through the real dispatcher (raw input in -> session output out) by a
builder player, exactly as typed in the docs — so a doc edit that
breaks the build breaks this suite. The plays then exercise the
tutorials' "Try it" flows and assert outcomes.

Time is virtual: script_ticker heartbeats are ticked by hand and
expire() lifetimes are reaped with a forged clock (reap_expired).
Connection events (ON_CONNECT / ON_DISCONNECT) are emitted with
fire_event, the same action shapes the live server propagates at
login/logout.
"""

from __future__ import annotations

from pathlib import Path
import re
import time

import pytest

from realm.core.events import fire_event, reap_expired
from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"


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


BUILD_RED_FLAGS = (
    "Unknown command", "Usage:", "not found", "Script error",
    "can't", "don't", "No permission",
)


# --- Harness -------------------------------------------------------------------


@pytest.fixture
def sim():
    simulator = Simulator()
    yield simulator
    simulator.close()


async def build(sim, doc_name):
    """Run one tutorial's build transcript — read from the doc — as a
    builder from Limbo."""
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
    builder.add_tag("builder")
    for line in build_lines(doc_name):
        await sim.do(builder, line)
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


async def tick(sim, thing):
    """Fire an attached script_ticker once (fresh countdown fires
    immediately and re-arms)."""
    for behavior in list(thing.get_behaviors()):
        await behavior.tick(thing, 1.0)


# --- 74. Custom channel ---------------------------------------------------------


class TestCustomChannel:

    async def test_join_talk_across_rooms_and_alias(self, sim):
        bob = await build(sim, "074_custom_channel.md")
        assert bob.location is room(sim, "The Docking Ring")
        kess = sim.player("Kess", location=room(sim, "The Observation Deck"))

        await sim.do(bob, "join pub")
        assert "You tune in to [pub]." in text(sim, bob)
        await sim.do(kess, "join pub")
        sim.seen(kess)

        await sim.do(bob, "+pub anyone near the airlock?")
        # Delivered a room away, and back to the speaker.
        assert "[pub] Bob: anyone near the airlock?" in text(sim, kess)
        assert "[pub] Bob: anyone near the airlock?" in text(sim, bob)

        # The short alias is the same subroutine.
        await sim.do(kess, "+p on my way")
        assert "[pub] Kess: on my way" in text(sim, bob)

        # Double-join is refused politely.
        await sim.do(bob, "join pub")
        assert "You are already tuned to [pub]." in text(sim, bob)

    async def test_nonsubscribers_neither_speak_nor_hear(self, sim):
        bob = await build(sim, "074_custom_channel.md")
        raven = sim.player("Raven", location=room(sim, "The Observation Deck"))
        await sim.do(bob, "join pub")
        sim.seen(bob)

        await sim.do(raven, "+pub hi")
        assert "You are not tuned to [pub]. JOIN PUB first." in text(sim, raven)

        await sim.do(bob, "+pub secret handshakes at nine")
        assert "secret handshakes" not in text(sim, raven)

        # Off the world zone the master is out of trigger reach entirely.
        limbo_lurker = sim.player("Lurk", location=room(sim, "Limbo"))
        await sim.do(limbo_lurker, "+pub hello?")
        assert "[pub]" not in text(sim, limbo_lurker)

    async def test_mute_history_unmute_leave(self, sim):
        bob = await build(sim, "074_custom_channel.md")
        kess = sim.player("Kess", location=room(sim, "The Observation Deck"))
        await sim.do(bob, "join pub")
        await sim.do(kess, "join pub")
        await sim.do(bob, "+pub first call")
        sim.seen(kess)

        await sim.do(kess, "mute pub")
        assert "[pub] muted." in text(sim, kess)
        await sim.do(bob, "+pub kess? you there?")
        assert "kess? you there?" not in text(sim, kess)

        # History replays what muting skipped.
        await sim.do(kess, "history pub")
        out = text(sim, kess)
        assert "[pub] Bob: first call" in out
        assert "[pub] Bob: kess? you there?" in out

        await sim.do(kess, "unmute pub")
        sim.seen(kess)
        await sim.do(bob, "+pub welcome back")
        assert "[pub] Bob: welcome back" in text(sim, kess)

        # Leaving stops both delivery and speech.
        await sim.do(kess, "leave pub")
        assert "You drop off [pub]." in text(sim, kess)
        await sim.do(kess, "+pub hello?")
        assert "You are not tuned to [pub]. JOIN PUB first." in text(sim, kess)

    async def test_history_is_capped_at_twenty(self, sim):
        bob = await build(sim, "074_custom_channel.md")
        await sim.do(bob, "join pub")
        for i in range(25):
            await sim.do(bob, f"+pub line {i}")
        hist = obj(sim, "Comms Nexus").db.get("hist")
        assert len(hist) == 20
        assert hist[0] == "[pub] Bob: line 5"
        assert hist[-1] == "[pub] Bob: line 24"


# --- 75. In-game mail -----------------------------------------------------------


class TestIngameMail:

    async def test_send_cc_attach_read_claim(self, sim):
        bob = await build(sim, "075_ingame_mail.md")
        assert bob.location is room(sim, "The Post Office")
        walk = room(sim, "The Promenade")
        zeke = sim.player("Zeke", location=walk)
        kess = sim.player("Kess", location=walk)
        compass = sim.obj("brass compass", location=bob, tags=["thing"])

        await sim.do(bob, "give brass compass to Postmaster")
        assert "The clerk tags your brass compass" in text(sim, bob)
        assert compass.location is obj(sim, "Postmaster")

        await sim.do(bob, "send Zeke,Kess = The dig starts at dawn. Compass attached for the lead cart.")
        assert "stamps the letter for 2 recipient(s) with 1 parcel(s) attached" in text(sim, bob)
        assert "a letter from Bob has arrived for you" in text(sim, zeke)
        assert "a letter from Bob has arrived for you" in text(sim, kess)

        # The inbox works from any world-zone room; parcels ride with the
        # first recipient only.
        await sim.do(zeke, "mail")
        assert "1. From Bob (to Zeke,Kess) [1 parcel(s)]" in text(sim, zeke)
        await sim.do(kess, "mail")
        out = text(sim, kess)
        assert "1. From Bob (to Zeke,Kess)" in out
        assert "parcel" not in out

        await sim.do(zeke, "mail 1")
        out = text(sim, zeke)
        assert "From Bob, to Zeke,Kess:" in out
        assert "The dig starts at dawn." in out
        assert "CLAIM 1 collects them." in out

        await sim.do(zeke, "claim 1")
        assert "slides 1 parcel(s) under the grille" in text(sim, zeke)
        assert compass.location is zeke

        # A bearer can only collect once.
        await sim.do(zeke, "claim 1")
        assert "empty palms" in text(sim, zeke)

    async def test_the_clerk_ignores_parcels_handed_to_other_people(self, sim):
        """event:on_receive is witnessed room-wide, not delivered only to
        the recipient, so the hook's `target is me` guard is what keeps
        the Postmaster from escrowing every handover in the lobby."""
        bob = await build(sim, "075_ingame_mail.md")
        zeke = sim.player("Zeke", location=bob.location)
        compass = sim.obj("brass compass", location=bob, tags=["thing"])

        # Handed to Zeke, in the Post Office. The clerk is a witness only.
        await sim.do(bob, "give brass compass to Zeke")
        assert compass.location is zeke
        assert compass.db.get("escrow") is None
        assert "The clerk tags your" not in text(sim, bob)

        # Handed to the clerk himself, it escrows as advertised.
        await sim.do(zeke, "give brass compass to Postmaster")
        assert compass.location is obj(sim, "Postmaster")
        assert compass.db.get("escrow") == zeke.id

    async def test_bad_address_bounces_whole_letter(self, sim):
        bob = await build(sim, "075_ingame_mail.md")
        zeke = sim.player("Zeke", location=room(sim, "The Promenade"))
        await sim.do(bob, "send Zeke,Nobody = half-good addresses fail whole")
        assert "no such citizen on the rolls" in text(sim, bob)
        pm = obj(sim, "Postmaster")
        assert pm.db.get("mail_" + zeke.id) is None

    async def test_connect_notice_only_with_waiting_mail(self, sim):
        bob = await build(sim, "075_ingame_mail.md")
        walk = room(sim, "The Promenade")
        zeke = sim.player("Zeke", location=walk)
        raven = sim.player("Raven", location=walk)
        await sim.do(bob, "send Zeke = ping")
        sim.seen(zeke)

        await fire_event(zeke, walk, "event:connect")
        assert "The postal wire hums: 1 letter(s) wait for you" in text(sim, zeke)

        await fire_event(raven, walk, "event:connect")
        assert "postal wire hums" not in text(sim, raven)

        await sim.do(zeke, "mail")
        assert "1. From Bob" in text(sim, zeke)

    async def test_empty_inbox_and_bad_numbers(self, sim):
        bob = await build(sim, "075_ingame_mail.md")
        zeke = sim.player("Zeke", location=room(sim, "The Promenade"))
        await sim.do(zeke, "mail")
        assert "nothing for you" in text(sim, zeke)
        await sim.do(zeke, "mail 3")
        assert "No letter numbered 3." in text(sim, zeke)
        await sim.do(zeke, "claim 3")
        assert "empty palms" in text(sim, zeke)


# --- 76. Bulletin boards --------------------------------------------------------


class TestBulletinBoards:

    async def test_post_read_and_per_location_state(self, sim):
        bob = await build(sim, "076_bulletin_boards.md")
        assert bob.location is room(sim, "The Tavern Commons")

        await sim.do(bob, "post Buyer wanted: forty crates of salt cod, ask for Bilda.")
        assert "Bob pins a notice to the notice board." in text(sim, bob)
        await sim.do(bob, "board")
        out = text(sim, bob)
        assert "1. Buyer wanted: forty crates of salt cod, ask for Bilda. --Bob" in out
        assert "s left)" in out

        # The harbor board is the same mechanism with its own blank state.
        await sim.do(bob, "docks")
        sim.seen(bob)
        await sim.do(bob, "board")
        assert "The board is bare cork." in text(sim, bob)
        await sim.do(bob, "post Dock crew wanted, no questions.")
        sim.seen(bob)
        await sim.do(bob, "board")
        out = text(sim, bob)
        assert "Dock crew wanted" in out
        assert "salt cod" not in out

        await sim.do(bob, "tavern")
        sim.seen(bob)
        await sim.do(bob, "board")
        out = text(sim, bob)
        assert "salt cod" in out
        assert "Dock crew" not in out

    async def test_expiry_sweeps_lazily_and_keeps_deadlines(self, sim):
        bob = await build(sim, "076_bulletin_boards.md")
        await sim.do(bob, "post Buyer wanted: forty crates of salt cod, ask for Bilda.")
        await sim.do(bob, "@set notice board/ttl = 0")
        await sim.do(bob, "post SOLD, never mind.")
        sim.seen(bob)

        # The zero-TTL notice was born due; any touch of the board sweeps it.
        await sim.do(bob, "board")
        out = text(sim, bob)
        assert "1 curled notice(s) drop off the notice board." in out
        assert "SOLD" not in out
        # The older notice keeps its original posted deadline.
        assert "salt cod" in out
        posts = obj(sim, "notice board").db.get("posts")
        assert len(posts) == 1

    async def test_heartbeat_sweeps_without_readers(self, sim):
        bob = await build(sim, "076_bulletin_boards.md")
        await sim.do(bob, "@set notice board/ttl = 0")
        await sim.do(bob, "post ghosts of notices past")
        sim.seen(bob)

        board = obj(sim, "notice board")
        assert len(board.db.get("posts")) == 1
        await tick(sim, board)
        assert board.db.get("posts") == []
        assert "1 curled notice(s) drop off the notice board." in text(sim, bob)


# --- 77. Handheld radios --------------------------------------------------------


class TestHandheldRadios:

    async def _crew(self, sim):
        bob = await build(sim, "077_handheld_radios.md")
        floor = room(sim, "The Warehouse Floor")
        zeke = sim.player("Zeke", location=floor)
        await sim.do(bob, "get spare radio")
        await sim.do(bob, "give spare radio to Zeke")
        await sim.do(zeke, "roof")
        sim.seen(bob)
        sim.seen(zeke)
        return bob, zeke

    async def test_same_frequency_carried_delivery(self, sim):
        bob, zeke = await self._crew(sim)

        await sim.do(bob, "radio moving in, two minutes")
        assert "You key the mic: [alpha] Bob: moving in, two minutes" in text(sim, bob)
        assert "[alpha] Bob: moving in, two minutes" in text(sim, zeke)

    async def test_retuning_refiles_the_registry(self, sim):
        bob, zeke = await self._crew(sim)

        await sim.do(zeke, "tune beta")
        assert "You click the dial over to [beta]." in text(sim, zeke)
        await sim.do(bob, "radio anyone copy?")
        assert "anyone copy?" not in text(sim, zeke)

        await sim.do(zeke, "tune alpha")
        sim.seen(zeke)
        await sim.do(bob, "radio how about now")
        assert "[alpha] Bob: how about now" in text(sim, zeke)

    async def test_dropped_radio_plays_out_loud_and_vox_bugs_the_room(self, sim):
        bob, zeke = await self._crew(sim)
        roof = room(sim, "The Rooftop")
        watch = sim.player("Watch", location=roof)

        # Set down, the spare plays traffic to the whole room.
        await sim.do(zeke, "drop spare radio")
        sim.seen(zeke)
        await sim.do(bob, "radio radio check")
        assert "spare radio crackles: [alpha] Bob: radio check" in text(sim, watch)

        # VOX: the set-down radio rebroadcasts room speech.
        await sim.do(zeke, "vox on")
        assert "You flip the VOX toggle on." in text(sim, zeke)
        await sim.do(zeke, "floor")
        sim.seen(bob)
        await sim.do(watch, "say the coast is clear")
        assert "[alpha] Watch (open mic): the coast is clear" in text(sim, bob)

    async def test_device_gating_demands_the_set_in_hand(self, sim):
        bob, zeke = await self._crew(sim)
        await sim.do(bob, "drop field radio")
        sim.seen(bob)
        await sim.do(bob, "radio hello")
        assert "Pick the radio up first" in text(sim, bob)
        await sim.do(bob, "tune gamma")
        assert "Hold the radio to work the dial." in text(sim, bob)
        # A pocketed radio never overhears: VOX on a carried set is inert.
        await sim.do(bob, "get field radio")
        await sim.do(bob, "vox on")
        sim.seen(bob)
        sim.seen(zeke)
        kess = sim.player("Kess", location=room(sim, "The Warehouse Floor"))
        await sim.do(kess, "say nobody hears this on the net")
        assert "(open mic)" not in text(sim, zeke)


# --- 78. Station PA system ------------------------------------------------------


class TestStationPA:

    async def test_announce_reaches_every_zone_room(self, sim):
        bob = await build(sim, "078_pa_system.md")
        assert bob.location is room(sim, "Operations")
        kess = sim.player("Kess", location=room(sim, "The Brig"))

        await sim.do(bob, "announce Docking clamps release in five minutes. Clear bay two.")
        assert "Docking clamps release in five minutes." in text(sim, kess)
        out = text(sim, bob)
        assert "Docking clamps release in five minutes." in out  # own room too
        assert "Your voice rolls out of every speaker on the station." in out

    async def test_zone_master_answers_from_any_station_room(self, sim):
        bob = await build(sim, "078_pa_system.md")
        kess = sim.player("Kess", location=room(sim, "The Brig"))
        await sim.do(bob, "mess")
        sim.seen(bob)
        await sim.do(bob, "announce Chow line closes early tonight.")
        assert "Chow line closes early tonight." in text(sim, kess)

    async def test_strangers_are_refused(self, sim):
        bob = await build(sim, "078_pa_system.md")
        zeke = sim.player("Zeke", location=room(sim, "Operations"))
        kess = sim.player("Kess", location=room(sim, "The Brig"))

        await sim.do(zeke, "announce free credits in ops!")
        assert "The console wants the station master. It ignores you." in text(sim, zeke)
        assert "free credits" not in text(sim, kess)


# --- 81. Graffiti ---------------------------------------------------------------


class TestGraffiti:

    async def test_scrawl_persists_in_the_room_description(self, sim):
        bob = await build(sim, "081_graffiti.md")
        underpass = room(sim, "The Underpass")
        kess = sim.player("Kess", location=underpass)
        raven = sim.player("Raven", location=underpass)

        await sim.do(kess, "scrawl Kess was here before you.")
        assert "Kess shakes a marker and writes on the wall." in text(sim, kess)

        # Every looker sees it, rendered after the description.
        await sim.do(raven, "look")
        out = text(sim, raven)
        assert "Sodium light and old concrete." in out
        assert 'Scrawled on the wall: "Kess was here before you." --Kess' in out

        # It is ordinary detail data, so the builder's @detail tools see it.
        extras = underpass.db.get("desc_extras")
        assert extras == [["", 'Scrawled on the wall: "Kess was here before you." --Kess']]

    async def test_wall_capacity_caps_the_list(self, sim):
        bob = await build(sim, "081_graffiti.md")
        kess = sim.player("Kess", location=room(sim, "The Underpass"))
        for i in range(8):
            await sim.do(kess, f"scrawl tag number {i}")
        sim.seen(kess)
        await sim.do(kess, "scrawl one more")
        assert "No bare concrete left." in text(sim, kess)
        assert len(room(sim, "The Underpass").db.get("desc_extras")) == 8

    async def test_only_the_owner_scrubs(self, sim):
        bob = await build(sim, "081_graffiti.md")
        underpass = room(sim, "The Underpass")
        kess = sim.player("Kess", location=underpass)
        await sim.do(kess, "scrawl wash me")
        sim.seen(kess)

        await sim.do(kess, "scrub wall")
        assert "Only whoever holds the deed scrubs this wall." in text(sim, kess)
        assert underpass.db.get("desc_extras")

        sim.seen(bob)
        await sim.do(bob, "scrub wall")
        assert "scrubs the wall back to bare concrete" in text(sim, bob)
        assert underpass.db.get("desc_extras") is None
        await sim.do(kess, "look")
        assert "Scrawled" not in text(sim, kess)


# --- 82. Newspaper --------------------------------------------------------------


class TestNewspaper:

    async def test_submit_publish_and_vend(self, sim):
        bob = await build(sim, "082_newspaper.md")
        assert bob.location is room(sim, "Market Square")
        square = room(sim, "Market Square")
        kess = sim.player("Kess", location=square, credits=20)

        await sim.do(bob, "submit Dock fees to double, harbormaster blames pirates.")
        assert "The desk editor spikes your copy" in text(sim, bob)
        await sim.do(kess, "submit LOST: one glass eye, sentimental value.")
        sim.seen(kess)

        # The press runs on its ticker; the paperboy reaches the square.
        bureau = obj(sim, "Gazette Bureau")
        await tick(sim, bureau)
        assert "A paperboy hollers: GAZETTE No. 1! 2 stories!" in text(sim, kess)
        assert bureau.db.get("queue") == []
        assert bureau.db.get("issue") == 1

        await sim.do(kess, "pay 5 to news kiosk")
        assert "The vendor folds a Gazette No. 1 into your hands." in text(sim, kess)
        assert kess.db.get("credits") == 15
        paper = obj(sim, "the Gazette No. 1")
        assert paper.location is kess

        # The pages are desc_extras: plain look reads the issue.
        await sim.do(kess, "look gazette")
        out = text(sim, kess)
        assert "THE GAZETTE, No. 1." in out
        assert "Dock fees to double, harbormaster blames pirates. --Bob" in out
        assert "LOST: one glass eye, sentimental value. --Kess" in out

    async def test_underpay_and_early_buyers_get_refunds(self, sim):
        bob = await build(sim, "082_newspaper.md")
        square = room(sim, "Market Square")
        zeke = sim.player("Zeke", location=square, credits=3)

        # Before the first issue: full refund, no paper.
        await sim.do(zeke, "pay 3 to news kiosk")
        assert "nothing on the stand until the press runs" in text(sim, zeke)
        assert zeke.db.get("credits") == 3

        await sim.do(bob, "submit War over, reportedly.")
        bureau = obj(sim, "Gazette Bureau")
        await tick(sim, bureau)
        sim.seen(zeke)

        # Underpayment: price card, full refund.
        await sim.do(zeke, "pay 3 to news kiosk")
        assert "The vendor taps the price card: 5 credits." in text(sim, zeke)
        assert zeke.db.get("credits") == 3
        assert objs(sim, "the Gazette No. 1") == []

    async def test_editions_snapshot_and_advance(self, sim):
        bob = await build(sim, "082_newspaper.md")
        square = room(sim, "Market Square")
        kess = sim.player("Kess", location=square, credits=20)
        bureau = obj(sim, "Gazette Bureau")

        await sim.do(bob, "submit Old news.")
        await tick(sim, bureau)
        await sim.do(kess, "pay 5 to news kiosk")
        sim.seen(kess)

        # An empty queue publishes nothing.
        await sim.engine.run_object_script(bureau, "on_tick")
        assert bureau.db.get("issue") == 1

        await sim.do(bob, "submit Fresh news.")
        await sim.engine.run_object_script(bureau, "on_tick")
        assert bureau.db.get("issue") == 2

        await sim.do(kess, "pay 5 to news kiosk")
        assert "Gazette No. 2" in text(sim, kess)
        # The old copy still reads issue one; the archive keeps both.
        await sim.do(kess, "look the Gazette No. 1")
        assert "Old news. --Bob" in text(sim, kess)
        assert bureau.db.get("issue_1") == ["Old news. --Bob"]
        assert bureau.db.get("issue_2") == ["Fresh news. --Bob"]


# --- 83. Message in a bottle ----------------------------------------------------


class TestMessageInBottle:

    async def test_pen_toss_drift_and_random_landfall(self, sim):
        bob = await build(sim, "083_message_in_bottle.md")
        cliff = room(sim, "The Sea Cliff")
        zeke = sim.player("Zeke", location=cliff)
        # Zeke is the only player the Harbormaster knows is ashore.
        await fire_event(zeke, cliff, "event:connect")
        hm = obj(sim, "Harbormaster")
        assert hm.db.get("ashore") == [zeke.id]

        await sim.do(bob, "pen The lighthouse ledger is a fake. Check the cellar. Tell no one.")
        assert "You roll the note tight" in text(sim, bob)
        await sim.do(bob, "toss bottle")
        assert "hurls the green bottle out past the breakers" in text(sim, bob)
        bottle = obj(sim, "green bottle")
        assert bottle.location is room(sim, "The Open Sea")
        drift = bottle.db.get("expires_at")
        assert drift is not None
        assert 59 <= drift - time.time() <= 301

        # Landfall: ON_EXPIRE rescues the bottle instead of dying.
        reaped = await reap_expired(sim.store, now=time.time() + 400)
        assert reaped == 0
        assert bottle.location is cliff
        assert bottle.db.get("expires_at") is None
        assert "A green glass bottle washes up at your feet." in text(sim, zeke)

        await sim.do(zeke, "get green bottle")
        await sim.do(zeke, "uncork bottle")
        assert ("The note reads: The lighthouse ledger is a fake. "
                "Check the cellar. Tell no one. --Bob") in text(sim, zeke)

    async def test_tide_demands_the_bottle_in_hand(self, sim):
        bob = await build(sim, "083_message_in_bottle.md")
        # No note yet: the toss refuses.
        await sim.do(bob, "toss bottle")
        assert "It needs a note first." in text(sim, bob)
        # On the ground, pen and toss both refuse.
        await sim.do(bob, "drop green bottle")
        sim.seen(bob)
        await sim.do(bob, "pen ghost writing")
        assert "Hold the bottle to write." in text(sim, bob)
        await sim.do(bob, "toss bottle")
        assert "Hold the bottle to throw it." in text(sim, bob)
        await sim.do(bob, "uncork bottle")
        assert "The bottle is empty." in text(sim, bob)

    async def test_roster_tracks_connects_and_disconnects(self, sim):
        bob = await build(sim, "083_message_in_bottle.md")
        beach = room(sim, "The Shingle Beach")
        zeke = sim.player("Zeke", location=beach)
        kess = sim.player("Kess", location=beach)
        hm = obj(sim, "Harbormaster")

        await fire_event(zeke, beach, "event:connect")
        await fire_event(kess, beach, "event:connect")
        assert hm.db.get("ashore") == [zeke.id, kess.id]
        # Reconnect moves to the back, never duplicates.
        await fire_event(zeke, beach, "event:connect")
        assert hm.db.get("ashore") == [kess.id, zeke.id]

        await fire_event(kess, beach, "event:disconnect")
        assert hm.db.get("ashore") == [zeke.id]
        await fire_event(zeke, beach, "event:disconnect")
        assert hm.db.get("ashore") == []
