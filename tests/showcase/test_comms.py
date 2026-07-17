"""
Showcase verification — Communication Systems (standalone tutorials).

Items: 74 custom channel, 75 in-game mail, 76 bulletin boards,
77 handheld radios, 78 station PA system, 81 graffiti, 82 newspaper,
83 message in a bottle.  (79/80/84/85 are [small] speech-pipeline gaps
and are not covered here.)

Every command line in each tutorial's "Build it" section is driven
through the real dispatcher (raw input in -> session output out) by a
builder player, exactly as typed in the docs; the plays then exercise
the tutorials' "Try it" flows and assert outcomes.

Time is virtual: script_ticker heartbeats are ticked by hand and
expire() lifetimes are reaped with a forged clock (reap_expired).
Connection events (ON_CONNECT / ON_DISCONNECT) are emitted with
fire_event, the same action shapes the live server propagates at
login/logout.
"""

from __future__ import annotations

import time

import pytest

from realm.core.events import fire_event, reap_expired
from realm.testing import Simulator

# --- Build transcripts (the tutorials' exact "Build it" lines) -----------------

# docs/showcase/074_custom_channel.md
BUILD_74 = [
    "@dig The Docking Ring = ring, out",
    "ring",
    "@zone here = world",
    "@dig The Observation Deck = deck, ring",
    "deck",
    "@zone here = world",
    "ring",
    "@create Comms Nexus",
    "drop Comms Nexus",
    "@desc Comms Nexus = A humming rack of relays. JOIN PUB subscribes; +pub <message> talks; HISTORY PUB replays; MUTE PUB / UNMUTE PUB quiet it.",
    "@zone/master Comms Nexus = world",
    "@set Comms Nexus/cmd_join = $join pub: subs = get_attr(me, 'subs') or []; (pemit(enactor, 'You are already tuned to [pub].') if enactor.id in subs else (set_attr(me, 'subs', subs + [enactor.id]), pemit(enactor, 'You tune in to [pub]. Talk with +pub <message>.')))",
    "@set Comms Nexus/cmd_leave = $leave pub: set_attr(me, 'subs', [i for i in (get_attr(me, 'subs') or []) if i != enactor.id]); set_attr(me, 'quiet', [i for i in (get_attr(me, 'quiet') or []) if i != enactor.id]); pemit(enactor, 'You drop off [pub].')",
    "@set Comms Nexus/speak = subs = get_attr(me, 'subs') or []; line = '[pub] ' + name(enactor) + ': ' + escape(str(arg0)); (pemit(enactor, 'You are not tuned to [pub]. JOIN PUB first.') if enactor.id not in subs else (set_attr(me, 'hist', ((get_attr(me, 'hist') or []) + [line])[-20:]), [pemit(get('#' + str(i)), line) for i in subs if i not in (get_attr(me, 'quiet') or [])]))",
    "@set Comms Nexus/cmd_pub = $+pub *: eval_attr(me, 'speak', arg0)",
    "@set Comms Nexus/cmd_p = $+p *: eval_attr(me, 'speak', arg0)",
    "@set Comms Nexus/cmd_hist = $history pub: rows = get_attr(me, 'hist') or []; pemit(enactor, '[pub] Nothing has been said yet.') if not rows else [pemit(enactor, r) for r in rows]",
    "@set Comms Nexus/cmd_mute = $mute pub: q = get_attr(me, 'quiet') or []; (set_attr(me, 'quiet', q if enactor.id in q else q + [enactor.id]), pemit(enactor, '[pub] muted. HISTORY PUB still works; UNMUTE PUB resumes delivery.'))",
    "@set Comms Nexus/cmd_unmute = $unmute pub: set_attr(me, 'quiet', [i for i in (get_attr(me, 'quiet') or []) if i != enactor.id]); pemit(enactor, '[pub] unmuted.')",
]

# docs/showcase/075_ingame_mail.md
BUILD_75 = [
    "@dig The Post Office = post, out",
    "post",
    "@zone here = world",
    "@dig The Promenade = walk, post",
    "walk",
    "@zone here = world",
    "post",
    "@create Postmaster",
    "@tag Postmaster = npc",
    "drop Postmaster",
    "@desc Postmaster = A clerk of brass and patience behind a grille. SEND <names> = <message> posts a letter (commas CC extras); MAIL lists yours; MAIL <n> reads one; CLAIM <n> collects parcels. GIVE it an item first to attach it.",
    "@zone/master Postmaster = world",
    "@set Postmaster/on_receive = new = [o for o in contents(me) if not has_attr(o, 'escrow')]; [(set_attr(o, 'escrow', enactor.id), pemit(enactor, 'The clerk tags your ' + name(o) + ': it will ride along with your next SEND.')) for o in new]",
    "@set Postmaster/cmd_send = $send * = *: names = [trim(n) for n in trim(arg0).split(',') if trim(n)]; rcpts = [get(n) for n in names]; ok = [p for p in rcpts if p and has_tag(p, 'player')]; parcels = [o for o in contents(me) if get_attr(o, 'escrow') == enactor.id]; (pemit(enactor, 'The clerk taps the address line: no such citizen on the rolls.') if len(ok) < len(names) or not ok else ([set_attr(me, 'mail_' + p.id, (get_attr(me, 'mail_' + p.id) or []) + [[name(enactor), escape(trim(arg1)), [o.id for o in parcels] if p is ok[0] else [], escape(trim(arg0))]]) for p in ok], [set_attr(o, 'escrow', '') for o in parcels], [pemit(p, 'The postal wire clicks: a letter from ' + name(enactor) + ' has arrived for you.') for p in ok], pemit(enactor, 'The clerk stamps the letter for ' + str(len(ok)) + ' recipient(s)' + (' with ' + str(len(parcels)) + ' parcel(s) attached' if parcels else '') + '.')))",
    "@set Postmaster/cmd_mail = $mail: rows = get_attr(me, 'mail_' + enactor.id) or []; pemit(enactor, 'The clerk checks the pigeonholes: nothing for you.') if not rows else [pemit(enactor, str(i + 1) + '. From ' + r[0] + ' (to ' + r[3] + ')' + (' [' + str(len(r[2])) + ' parcel(s)]' if r[2] else '')) for i, r in enumerate(rows)]",
    "@set Postmaster/cmd_mailn = $mail *: rows = get_attr(me, 'mail_' + enactor.id) or []; k = int(trim(arg0)) if trim(arg0).isdigit() else 0; pemit(enactor, 'No letter numbered ' + trim(arg0) + '.') if not (1 <= k <= len(rows)) else (pemit(enactor, 'From ' + rows[k-1][0] + ', to ' + rows[k-1][3] + ':'), pemit(enactor, '  ' + rows[k-1][1]), (pemit(enactor, str(len(rows[k-1][2])) + ' parcel(s) wait behind the grille. CLAIM ' + str(k) + ' collects them.') if rows[k-1][2] else None))",
    "@set Postmaster/cmd_claim = $claim *: rows = get_attr(me, 'mail_' + enactor.id) or []; k = int(trim(arg0)) if trim(arg0).isdigit() else 0; items = [get('#' + str(i)) for i in (rows[k-1][2] if 1 <= k <= len(rows) else [])]; live = [o for o in items if o and loc(o) == me]; (pemit(enactor, 'The clerk turns up empty palms: nothing to collect under that number.') if not live else ([teleport_obj(o, enactor) for o in live], set_attr(me, 'mail_' + enactor.id, [r if j != k - 1 else [r[0], r[1], [], r[3]] for j, r in enumerate(rows)]), pemit(enactor, 'The clerk slides ' + str(len(live)) + ' parcel(s) under the grille.')))",
    "@set Postmaster/on_connect = n = len(get_attr(me, 'mail_' + enactor.id) or []); pemit(enactor, 'The postal wire hums: ' + str(n) + ' letter(s) wait for you at the Post Office.') if n else None",
]

# docs/showcase/076_bulletin_boards.md
BUILD_76 = [
    "@dig The Tavern Commons = tavern, out",
    "tavern",
    "@create notice board",
    "drop notice board",
    "@desc notice board = Cork and thumbtacks. POST <text> pins a notice for a while; BOARD reads what has not yet curled off.",
    "@set notice board/ttl = 120",
    "@set notice board/sweep = rows = get_attr(me, 'posts') or []; keep = [p for p in rows if p[2] > now()]; (set_attr(me, 'posts', keep), remit(loc(me), str(len(rows) - len(keep)) + ' curled notice(s) drop off the ' + name(me) + '.')) if len(keep) < len(rows) else None",
    "@set notice board/cmd_post = $post *: eval_attr(me, 'sweep'); set_attr(me, 'posts', (get_attr(me, 'posts') or []) + [[name(enactor), escape(arg0), now() + get_attr(me, 'ttl', 120)]]); remit(loc(me), name(enactor) + ' pins a notice to the ' + name(me) + '.')",
    "@set notice board/cmd_board = $board: eval_attr(me, 'sweep'); rows = get_attr(me, 'posts') or []; pemit(enactor, 'The board is bare cork.') if not rows else [pemit(enactor, str(i + 1) + '. ' + r[1] + ' --' + r[0] + ' (' + str(r[2] - now()) + 's left)') for i, r in enumerate(rows)]",
    "@set notice board/on_tick = eval_attr(me, 'sweep')",
    "@behavior notice board = script_ticker, interval:30",
    "@dig The Docks = docks, tavern",
    "@clone notice board = harbor board",
    "get harbor board",
    "docks",
    "drop harbor board",
    "@desc harbor board = Salt-stained planks and a few nails. POST and BOARD work here too, on this dock's own notices.",
    "tavern",
]

# docs/showcase/077_handheld_radios.md
BUILD_77 = [
    "@dig The Warehouse Floor = floor, out",
    "floor",
    "@dig The Rooftop = roof, floor",
    "@create field radio",
    "@desc field radio = A brick of olive plastic with a stubby antenna and a worn send key. [[result = 'The dial is set to ' + str(get_attr(me, 'freq', 'static'))]].",
    "@tag field radio = radio",
    "@set field radio/freq = alpha",
    "@set field radio/power = 1",
    "@set field radio/xmit = f = str(get_attr(me, 'freq', '')); [(pemit(loc(r), '[' + f + '] ' + str(arg0)) if has_tag(loc(r), 'player') else remit(loc(r), name(r) + ' crackles: [' + f + '] ' + str(arg0))) for r in search_world(tag='radio', attr='freq', value=get_attr(me, 'freq', '')) if r != me and get_attr(r, 'power', 1) and loc(r)]",
    "@set field radio/cmd_radio = $radio *: (pemit(enactor, 'Pick the radio up first; the send key is on the grip.') if loc(me) != enactor else (pemit(enactor, 'You key the mic: [' + str(get_attr(me, 'freq', '')) + '] ' + name(enactor) + ': ' + escape(arg0)), eval_attr(me, 'xmit', name(enactor) + ': ' + escape(arg0))))",
    "@set field radio/cmd_tune = $tune *: (pemit(enactor, 'Hold the radio to work the dial.') if loc(me) != enactor else (set_attr(me, 'freq', trim(arg0)), pemit(enactor, 'You click the dial over to [' + trim(arg0) + '].')))",
    "@set field radio/vox = 0",
    "@set field radio/cmd_vox = $vox *: (set_attr(me, 'vox', 1 if trim(arg0).lower() == 'on' else 0), pemit(enactor, 'You flip the VOX toggle ' + trim(arg0).lower() + '. It only matters while the set is put down somewhere.'))",
    "@set field radio/listen_vox = ^*: eval_attr(me, 'xmit', name(enactor) + ' (open mic): ' + escape(arg0)) if enactor and get_attr(me, 'vox', 0) and get_attr(me, 'power', 1) else None",
    "@clone field radio = spare radio",
]

# docs/showcase/078_pa_system.md
BUILD_78 = [
    "@dig Operations = ops, out",
    "ops",
    "@zone here = station",
    "@dig The Mess Hall = mess, ops",
    "mess",
    "@zone here = station",
    "@dig The Brig = brig, mess",
    "brig",
    "@zone here = station",
    "mess",
    "ops",
    "@create PA console",
    "drop PA console",
    "@desc PA console = A gooseneck microphone over a punchboard of room switches. ANNOUNCE <message> pages the whole station.",
    "@zone/master PA console = station",
    "@set PA console/cmd_announce = $announce *: (pemit(enactor, 'The console wants the station master. It ignores you.') if enactor != owner(me) else ([remit(r, ansi('yh', 'BONG-bong. ') + escape(arg0) + ansi('c', ' (PA)')) for r in zone_rooms('station')], pemit(enactor, 'Your voice rolls out of every speaker on the station.')))",
]

# docs/showcase/081_graffiti.md
BUILD_81 = [
    "@dig The Underpass = underpass, out",
    "underpass",
    "@desc here = Sodium light and old concrete. The long wall invites comment.",
    "@set here/cmd_scrawl = $scrawl *: rows = get_attr(me, 'desc_extras') or []; (pemit(enactor, 'No bare concrete left. The wall is full; someone with the deed must SCRUB it.') if len(rows) >= 8 else (set_attr(me, 'desc_extras', rows + [['', 'Scrawled on the wall: \"' + escape(arg0) + '\" --' + name(enactor)]]), remit(me, name(enactor) + ' shakes a marker and writes on the wall.')))",
    "@set here/cmd_scrub = $scrub wall: (pemit(enactor, 'Only whoever holds the deed scrubs this wall.') if enactor != owner(me) else (del_attr(me, 'desc_extras'), remit(me, name(enactor) + ' scrubs the wall back to bare concrete.')))",
]

# docs/showcase/082_newspaper.md
BUILD_82 = [
    "@dig The Gazette Office = office, out",
    "office",
    "@zone here = market",
    "@dig Market Square = square, office",
    "square",
    "@zone here = market",
    "office",
    "@create Gazette Bureau",
    "drop Gazette Bureau",
    "@desc Gazette Bureau = Ink, brass, and a thundering press. SUBMIT <text> files a story for the next issue.",
    "@zone/master Gazette Bureau = market",
    "@set Gazette Bureau/cmd_submit = $submit *: set_attr(me, 'queue', (get_attr(me, 'queue') or []) + [escape(arg0) + ' --' + name(enactor)]); pemit(enactor, 'The desk editor spikes your copy for the next issue.')",
    "@set Gazette Bureau/publish = q = get_attr(me, 'queue') or []; n = get_attr(me, 'issue', 0) + 1; (set_attr(me, 'issue', n), set_attr(me, 'issue_' + str(n), q), set_attr(me, 'queue', []), [remit(r, 'A paperboy hollers: GAZETTE No. ' + str(n) + '! ' + str(len(q)) + ' stories! Fresh at the kiosk!') for r in zone_rooms('market')]) if q else None",
    "@set Gazette Bureau/on_tick = eval_attr(me, 'publish')",
    "@behavior Gazette Bureau = script_ticker, interval:60",
    "square",
    "@create news kiosk",
    "drop news kiosk",
    "@desc news kiosk = A tin shed papered with old front pages. PAY 5 TO KIOSK for the latest Gazette.",
    "@set news kiosk/price = 5",
    "@set news kiosk/ledger = 0",
    "@set news kiosk/on_payment = b = get('Gazette Bureau'); paid = credits(me) - get_attr(me, 'ledger', 0); cost = get_attr(me, 'price', 5); n = get_attr(b, 'issue', 0); ok = bool(n) and paid >= cost; refund = paid - cost if ok else paid; (transfer_credits(me, enactor, refund) if refund > 0 else None); set_attr(me, 'ledger', credits(me)); (pemit(enactor, 'The vendor shrugs: nothing on the stand until the press runs. Coins returned.') if not n else (pemit(enactor, 'The vendor taps the price card: ' + str(cost) + ' credits. Coins returned.') if not ok else None)); [(set_attr(p, 'desc_extras', [['', 'Cheap ink on cheaper paper. The masthead reads THE GAZETTE, No. ' + str(n) + '.']] + [['', row] for row in (get_attr(b, 'issue_' + str(n)) or [])]), teleport_obj(p, enactor), pemit(enactor, 'The vendor folds a Gazette No. ' + str(n) + ' into your hands. LOOK gazette to read it.')) for p in ([create_obj('the Gazette No. ' + str(n), ['thing', 'paper'], me)] if ok else []) if p]",
]

# docs/showcase/083_message_in_bottle.md
BUILD_83 = [
    "@dig The Shingle Beach = beach, out",
    "beach",
    "@zone here = world",
    "@dig The Sea Cliff = cliff, beach",
    "cliff",
    "@zone here = world",
    "beach",
    "@dig The Open Sea",
    "@create Harbormaster",
    "drop Harbormaster",
    "@desc Harbormaster = A weathered official who seems to know exactly who is ashore at any hour.",
    "@zone/master Harbormaster = world",
    "@set Harbormaster/on_connect = set_attr(me, 'ashore', [i for i in (get_attr(me, 'ashore') or []) if i != enactor.id] + [enactor.id])",
    "@set Harbormaster/on_disconnect = set_attr(me, 'ashore', [i for i in (get_attr(me, 'ashore') or []) if i != enactor.id])",
    "@create green bottle",
    "@desc green bottle = Sea-scoured glass, stoppered with a cork. PEN <text> writes a note; TOSS BOTTLE gives it to the tide; UNCORK BOTTLE reads what is inside.",
    "@set green bottle/cmd_pen = $pen *: (pemit(enactor, 'Hold the bottle to write.') if loc(me) != enactor else (set_attr(me, 'note', escape(arg0) + ' --' + name(enactor)), pemit(enactor, 'You roll the note tight and work it down the neck.')))",
    "@set green bottle/cmd_uncork = $uncork bottle: pemit(enactor, 'The bottle is empty.') if not get_attr(me, 'note') else pemit(enactor, 'The note reads: ' + str(get_attr(me, 'note')))",
    "@set green bottle/cmd_toss = $toss bottle: (pemit(enactor, 'Hold the bottle to throw it.') if loc(me) != enactor else (pemit(enactor, 'It needs a note first. PEN <text>.') if not get_attr(me, 'note') else (remit(loc(enactor), name(enactor) + ' hurls the green bottle out past the breakers.'), teleport_obj(me, 'The Open Sea'), expire(me, rand(60, 300)))))",
    "@set green bottle/on_expire = hm = get('Harbormaster'); ids = [i for i in (get_attr(hm, 'ashore') or []) if get('#' + str(i))]; pool = ids or [p.id for p in search_world(tag='player')]; w = get('#' + str(pool[rand(0, len(pool) - 1)])) if pool else None; (del_attr(me, 'expires_at'), teleport_obj(me, loc(w)), pemit(w, 'A green glass bottle washes up at your feet.'), oemit(w, 'Something glints at the tide-line.')) if w and loc(w) else expire(me, 60)",
]

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


async def build(sim, lines):
    """Run one tutorial's build transcript as a builder from Limbo."""
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
    builder.add_tag("builder")
    for line in lines:
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
        bob = await build(sim, BUILD_74)
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
        bob = await build(sim, BUILD_74)
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
        bob = await build(sim, BUILD_74)
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
        bob = await build(sim, BUILD_74)
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
        bob = await build(sim, BUILD_75)
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

    async def test_bad_address_bounces_whole_letter(self, sim):
        bob = await build(sim, BUILD_75)
        zeke = sim.player("Zeke", location=room(sim, "The Promenade"))
        await sim.do(bob, "send Zeke,Nobody = half-good addresses fail whole")
        assert "no such citizen on the rolls" in text(sim, bob)
        pm = obj(sim, "Postmaster")
        assert pm.db.get("mail_" + zeke.id) is None

    async def test_connect_notice_only_with_waiting_mail(self, sim):
        bob = await build(sim, BUILD_75)
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
        bob = await build(sim, BUILD_75)
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
        bob = await build(sim, BUILD_76)
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
        bob = await build(sim, BUILD_76)
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
        bob = await build(sim, BUILD_76)
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
        bob = await build(sim, BUILD_77)
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
        bob = await build(sim, BUILD_78)
        assert bob.location is room(sim, "Operations")
        kess = sim.player("Kess", location=room(sim, "The Brig"))

        await sim.do(bob, "announce Docking clamps release in five minutes. Clear bay two.")
        assert "Docking clamps release in five minutes." in text(sim, kess)
        out = text(sim, bob)
        assert "Docking clamps release in five minutes." in out  # own room too
        assert "Your voice rolls out of every speaker on the station." in out

    async def test_zone_master_answers_from_any_station_room(self, sim):
        bob = await build(sim, BUILD_78)
        kess = sim.player("Kess", location=room(sim, "The Brig"))
        await sim.do(bob, "mess")
        sim.seen(bob)
        await sim.do(bob, "announce Chow line closes early tonight.")
        assert "Chow line closes early tonight." in text(sim, kess)

    async def test_strangers_are_refused(self, sim):
        bob = await build(sim, BUILD_78)
        zeke = sim.player("Zeke", location=room(sim, "Operations"))
        kess = sim.player("Kess", location=room(sim, "The Brig"))

        await sim.do(zeke, "announce free credits in ops!")
        assert "The console wants the station master. It ignores you." in text(sim, zeke)
        assert "free credits" not in text(sim, kess)


# --- 81. Graffiti ---------------------------------------------------------------


class TestGraffiti:

    async def test_scrawl_persists_in_the_room_description(self, sim):
        bob = await build(sim, BUILD_81)
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
        bob = await build(sim, BUILD_81)
        kess = sim.player("Kess", location=room(sim, "The Underpass"))
        for i in range(8):
            await sim.do(kess, f"scrawl tag number {i}")
        sim.seen(kess)
        await sim.do(kess, "scrawl one more")
        assert "No bare concrete left." in text(sim, kess)
        assert len(room(sim, "The Underpass").db.get("desc_extras")) == 8

    async def test_only_the_owner_scrubs(self, sim):
        bob = await build(sim, BUILD_81)
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
        bob = await build(sim, BUILD_82)
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
        bob = await build(sim, BUILD_82)
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
        bob = await build(sim, BUILD_82)
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
        bob = await build(sim, BUILD_83)
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
        bob = await build(sim, BUILD_83)
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
        bob = await build(sim, BUILD_83)
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
