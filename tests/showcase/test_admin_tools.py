"""
Showcase verification — Admin, Moderation & Staff Tools.

Items: 176 staff dashboard, 177 jail system, 179 character approval queue,
181 announcement system, 182 object snapshot/restore, 183 permission tiers
in practice, 184 new-player onboarding, 186 watchlist & alerts.  (178/180/185
are [small] engine-gap items and are not covered here.)

Every command line in each tutorial's "Build it" section is driven through
the real dispatcher (raw input in -> session output out) by a *staff* builder,
exactly as typed in the docs; the plays then exercise the tutorials' "Try it"
flows and assert outcomes.

These are ADMIN tools: the consoles are admin-owned world-zone masters, so
their scripts run with owner authority and may legitimately act on players
(teleport, tag, credit, restore) — the boundary the tutorials document.

Connection/death/attack events (ON_CONNECT / ON_DISCONNECT / ON_DEATH /
ON_ATTACK) are emitted with fire_event, the same action shapes the live
server propagates; expire() lifetimes are reaped with a forged clock
(reap_expired), exactly as on the world tick.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from realm.core.events import fire_event, reap_expired
from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

# --- 176 Staff dashboard --------------------------------------------------------

# docs/showcase/176_staff_dashboard.md
BUILD_176 = [
    "@dig The Operations Center = ops, out",
    "ops",
    "@zone here = world",
    "@create Ops Console",
    "drop Ops Console",
    "@desc Ops Console = A wall of glass and telemetry. DASHBOARD prints station health at a glance.",
    "@zone/master Ops Console = world",
    "@eval set_attr(get('Ops Console'), 'booted_at', now())",
    "@set Ops Console/on_connect = set_attr(me, 'online', [i for i in (get_attr(me,'online') or []) if i != enactor.id] + [enactor.id])",
    "@set Ops Console/on_disconnect = set_attr(me, 'online', [i for i in (get_attr(me,'online') or []) if i != enactor.id])",
    "@set Ops Console/on_death = set_attr(me, 'incidents', ((get_attr(me,'incidents') or []) + ['death: ' + name(enactor) + ' in ' + name(here)])[-20:])",
    "@set Ops Console/render = up = now() - get_attr(me,'booted_at', now()); on = [i for i in (get_attr(me,'online') or []) if get('#'+str(i))]; inc = get_attr(me,'incidents') or []; [pemit(enactor, ln) for ln in (['=== STATION OPS ===', 'uptime: ' + str(up) + 's since boot', 'online: ' + str(len(on)) + ' / ' + str(len(search_world(tag='player'))) + ' characters', 'world: ' + str(len(search_world(tag='room'))) + ' rooms, ' + str(len(search_world(tag='npc'))) + ' npcs, ' + str(len(search_world(tag='thing'))) + ' things', '--- recent incidents ---'] + (inc[-5:] if inc else ['(none logged)']))]",
    "@set Ops Console/cmd_dashboard = $dashboard: pemit(enactor, 'The ops console stays dark for you.') if not has_tag(enactor,'admin') else eval_attr(me, 'render')",
]

# --- 177 Jail system ------------------------------------------------------------

# docs/showcase/177_jail_system.md
BUILD_177 = [
    "@dig The Precinct = precinct, out",
    "precinct",
    "@zone here = world",
    "@dig The Holding Cell = cell, back",
    "cell",
    "@zone here = world",
    "@lock back = not caller.has_tag('jailed')",
    "precinct",
    "@create Warden",
    "drop Warden",
    "@desc Warden = A duty desk with a wall of cell keys. JAIL <name> = <minutes>, FREE <name>, JAIL LOG.",
    "@zone/master Warden = world",
    "@set Warden/arm = t = create_obj('a sentence timer', ['thing','jail_timer'], 'The Holding Cell'); set_attr(t, 'prisoner', arg0); set_attr(t, 'warden', me.id); set_attr(t, 'on_expire', \"p = get('#'+str(get_attr(me,'prisoner'))); w = get('#'+str(get_attr(me,'warden'))); (remove_tag(p,'jailed'), teleport_obj(p,'The Precinct'), pemit(p,'The cell door clicks open. Time served.'), set_attr(w,'log', ((get_attr(w,'log') or []) + ['auto-released ' + name(p)])[-50:])) if p and w else None\"); expire(t, int(arg1) * 60)",
    "@set Warden/cmd_jail = $jail * = *: p = get(trim(arg0)); mins = int(trim(arg1)) if trim(arg1).isdigit() else 5; (pemit(enactor,'Only staff may work the Warden.') if not has_tag(enactor,'admin') else (pemit(enactor,'No one named ' + trim(arg0) + ' to jail.') if not (p and has_tag(p,'player')) else (add_tag(p,'jailed'), teleport_obj(p,'The Holding Cell'), pemit(p,'You are hauled off to the Holding Cell. Sentence: ' + str(mins) + ' minute(s).'), set_attr(me,'log', ((get_attr(me,'log') or []) + [name(enactor) + ' jailed ' + name(p) + ' (' + str(mins) + 'm)'])[-50:]), eval_attr(me,'arm', p.id, mins), pemit(enactor,'Jailed ' + name(p) + ' for ' + str(mins) + ' minute(s).'))))",
    "@set Warden/cmd_free = $free *: p = get(trim(arg0)); (pemit(enactor,'Only staff may work the Warden.') if not has_tag(enactor,'admin') else (pemit(enactor, trim(arg0) + ' is not currently jailed.') if not (p and has_tag(p,'jailed')) else (remove_tag(p,'jailed'), teleport_obj(p,'The Precinct'), pemit(p,'You are released early. Stay out of trouble.'), [destroy_obj(t) for t in contents(get('The Holding Cell')) if has_tag(t,'jail_timer') and get_attr(t,'prisoner') == p.id], set_attr(me,'log', ((get_attr(me,'log') or []) + [name(enactor) + ' freed ' + name(p)])[-50:]), pemit(enactor,'Freed ' + name(p) + '.'))))",
    "@set Warden/cmd_jaillog = $jail log: (pemit(enactor,'Only staff may work the Warden.') if not has_tag(enactor,'admin') else (pemit(enactor,'The blotter is empty.') if not get_attr(me,'log') else [pemit(enactor, ln) for ln in get_attr(me,'log')[-10:]]))",
]

# --- 179 Character approval queue -----------------------------------------------

# docs/showcase/179_approval_queue.md
BUILD_179 = [
    "@dig The Arrivals Lounge = arrivals, out",
    "arrivals",
    "@zone here = world",
    "@dig The Concourse = concourse, back",
    "@lock concourse = not caller.has_tag('unapproved')",
    "@create Approvals Desk",
    "drop Approvals Desk",
    "@desc Approvals Desk = A clerk's window for new citizens. PENDING, APPROVE <name>, REJECT <name> = <reason>.",
    "@zone/master Approvals Desk = world",
    "@set Approvals Desk/cmd_pending = $pending: q = search_world(tag='unapproved'); (pemit(enactor,'Only staff may review arrivals.') if not has_tag(enactor,'admin') else (pemit(enactor,'The approval queue is empty.') if not q else [pemit(enactor,'- ' + name(p) + ' (#' + str(p.id)[:8] + ')') for p in q]))",
    "@set Approvals Desk/cmd_approve = $approve *: p = get(trim(arg0)); (pemit(enactor,'Only staff may clear arrivals.') if not has_tag(enactor,'admin') else (pemit(enactor, trim(arg0) + ' is not awaiting approval.') if not (p and has_tag(p,'unapproved')) else (remove_tag(p,'unapproved'), add_tag(p,'approved'), pemit(p,'Your character has been approved. Welcome aboard — the concourse is open to you.'), set_attr(me,'log', ((get_attr(me,'log') or []) + [name(enactor) + ' approved ' + name(p)])[-50:]), pemit(enactor,'Approved ' + name(p) + '.'))))",
    "@set Approvals Desk/cmd_reject = $reject * = *: p = get(trim(arg0)); (pemit(enactor,'Only staff may clear arrivals.') if not has_tag(enactor,'admin') else (pemit(enactor, trim(arg0) + ' is not awaiting approval.') if not (p and has_tag(p,'unapproved')) else (pemit(p,'Your character needs work before approval: ' + escape(trim(arg1))), set_attr(me,'log', ((get_attr(me,'log') or []) + [name(enactor) + ' bounced ' + name(p) + ': ' + trim(arg1)])[-50:]), pemit(enactor,'Sent ' + name(p) + ' back with notes.'))))",
]

# --- 181 Announcement system ----------------------------------------------------

# docs/showcase/181_announcements.md
BUILD_181 = [
    "@dig The Broadcast Booth = booth, out",
    "booth",
    "@zone here = world",
    "@create Announcer",
    "drop Announcer",
    "@desc Announcer = A brass microphone wired to every character on the grid.",
    "@zone/master Announcer = world",
    "@set Announcer/cmd_announce = $announce *: (pemit(enactor,'Only staff may broadcast.') if not has_tag(enactor,'admin') else (set_attr(me,'history', ((get_attr(me,'history') or []) + [escape(arg0) + '  --' + name(enactor)])[-30:]), [pemit(p, ansi('yh','[NOTICE] ') + escape(arg0)) for p in search_world(tag='player') if not has_tag(p,'no_announce')], pemit(enactor,'Broadcast sent to all listening players.')))",
    "@set Announcer/cmd_news = $news: h = get_attr(me,'history') or []; pemit(enactor,'No notices on file.') if not h else [pemit(enactor, str(i+1) + '. ' + ln) for i, ln in enumerate(h[-10:])]",
    "@set Announcer/cmd_mute = $mute news: (add_tag(enactor,'no_announce'), pemit(enactor,'You opt out of live notices. NEWS still shows history; UNMUTE NEWS resumes delivery.'))",
    "@set Announcer/cmd_unmute = $unmute news: (remove_tag(enactor,'no_announce'), pemit(enactor,'Live notices resumed.'))",
]

# --- 182 Object snapshot / restore ----------------------------------------------

# docs/showcase/182_snapshot_restore.md
BUILD_182 = [
    "@dig The Archive = archive, out",
    "archive",
    "@create market stall",
    "drop market stall",
    "@desc market stall = A trestle table of goods.",
    "@set market stall/price = 10",
    "@set market stall/stock = 5",
    "@create Restoration Vault",
    "drop Restoration Vault",
    "@desc Restoration Vault = A humming cabinet of saved states. SNAPSHOT <obj> = <fields>, RESTORE <obj>, SNAPSHOTS.",
    "@set Restoration Vault/cmd_snapshot = $snapshot * = *: t = get(trim(arg0)); fields = [f for f in trim(arg1).split() if f]; (pemit(enactor,'Only staff may snapshot.') if not has_tag(enactor,'admin') else (pemit(enactor,'No object named ' + trim(arg0) + '.') if not t else (set_attr(me, 'snap_'+t.id, {f: get_attr(t, f) for f in fields}), set_attr(me, 'label_'+t.id, name(t)), set_attr(me, 'index', [i for i in (get_attr(me,'index') or []) if i != t.id] + [t.id]), pemit(enactor,'Snapshot of ' + name(t) + ' saved: ' + ', '.join(fields) + '.'))))",
    "@set Restoration Vault/cmd_restore = $restore *: t = get(trim(arg0)); snap = get_attr(me,'snap_'+t.id) if t else None; (pemit(enactor,'Only staff may restore.') if not has_tag(enactor,'admin') else (pemit(enactor,'No object named ' + trim(arg0) + '.') if not t else (pemit(enactor,'No snapshot on file for ' + name(t) + '.') if snap is None else ([set_attr(t, k, v) for k, v in snap.items()], pemit(enactor,'Restored ' + str(len(snap)) + ' field(s) to ' + name(t) + '.')))))",
    "@set Restoration Vault/cmd_snaps = $snapshots: idx = get_attr(me,'index') or []; (pemit(enactor,'Only staff.') if not has_tag(enactor,'admin') else (pemit(enactor,'No snapshots on file.') if not idx else [pemit(enactor,'- ' + str(get_attr(me,'label_'+i,'?')) + ' (#' + str(i)[:8] + ')') for i in idx]))",
]

# --- 183 Permission tiers in practice -------------------------------------------

# docs/showcase/183_permission_tiers.md
BUILD_183 = [
    "@dig The Security Office = secoff, out",
    "secoff",
    "@create strongbox",
    "drop strongbox",
    "@desc strongbox = A heavy lockbox. Only the cleared may lift it.",
    "@lock strongbox = caller.has_tag('cleared')",
]

# --- 184 New-player onboarding --------------------------------------------------

# docs/showcase/184_onboarding.md
BUILD_184 = [
    "@dig The Orientation Bay = obay, out",
    "obay",
    "@zone here = world",
    "@create Greeter",
    "drop Greeter",
    "@desc Greeter = A cheerful welcome-bot bolted by the airlock.",
    "@zone/master Greeter = world",
    "@set Greeter/on_connect = mentors = [m for m in search_world(tag='mentor') if m != enactor]; (set_attr(enactor,'oriented', now()), adjust_credits(enactor, 100), create_obj('a welcome datapad', ['thing'], enactor), pemit(enactor, 'Welcome aboard, ' + name(enactor) + '! Your kit holds a datapad and 100 credits. Type HELP anytime.'), [pemit(m, ansi('c','[mentor] ') + 'New arrival: ' + name(enactor) + ' — say hello.') for m in mentors]) if not get_attr(enactor,'oriented') else None",
]

# --- 186 Watchlist & alerts -----------------------------------------------------

# docs/showcase/186_watchlist.md
BUILD_186 = [
    "@dig The Security Hub = hub, out",
    "hub",
    "@zone here = world",
    "@create Watch Office",
    "drop Watch Office",
    "@desc Watch Office = Banks of monitors. WATCH <name> = <note>, UNWATCH <name>, WATCHLIST.",
    "@zone/master Watch Office = world",
    "@set Watch Office/alert = [pemit(s, ansi('rh','[WATCH] ') + str(arg0)) for s in search_world(tag='admin')]",
    "@set Watch Office/cmd_watch = $watch * = *: p = get(trim(arg0)); (pemit(enactor,'Only staff may set watches.') if not has_tag(enactor,'admin') else (pemit(enactor,'No one named ' + trim(arg0) + '.') if not (p and has_tag(p,'player')) else (add_tag(p,'watched'), set_attr(me,'note_'+p.id, escape(trim(arg1))), pemit(enactor,'Now watching ' + name(p) + '.'))))",
    "@set Watch Office/cmd_unwatch = $unwatch *: p = get(trim(arg0)); (pemit(enactor,'Only staff may clear watches.') if not has_tag(enactor,'admin') else (pemit(enactor, trim(arg0) + ' is not being watched.') if not (p and has_tag(p,'watched')) else (remove_tag(p,'watched'), pemit(enactor,'Stopped watching ' + name(p) + '.'))))",
    "@set Watch Office/cmd_watchlist = $watchlist: w = search_world(tag='watched'); (pemit(enactor,'Only staff.') if not has_tag(enactor,'admin') else (pemit(enactor,'No one is being watched.') if not w else [pemit(enactor,'- ' + name(p) + ' :: ' + str(get_attr(me,'note_'+p.id,''))) for p in w]))",
    "@set Watch Office/on_connect = eval_attr(me,'alert', name(enactor) + ' (watched) just connected.') if has_tag(enactor,'watched') else None",
    "@set Watch Office/on_attack = eval_attr(me,'alert', name(enactor) + ' (watched) is throwing punches.') if has_tag(enactor,'watched') else None",
]

BUILD_RED_FLAGS = (
    "Unknown command", "Usage:", "not found", "Script error",
    "No permission", "Invalid lock", "Permission denied",
)

# Every Build-it line exercised below must appear verbatim in its tutorial,
# so the docs can never drift from what the tests prove works.
DOC_TRANSCRIPTS = {
    "176_staff_dashboard.md": BUILD_176,
    "177_jail_system.md": BUILD_177,
    "179_approval_queue.md": BUILD_179,
    "181_announcements.md": BUILD_181,
    "182_snapshot_restore.md": BUILD_182,
    "183_permission_tiers.md": BUILD_183,
    "184_onboarding.md": BUILD_184,
    "186_watchlist.md": BUILD_186,
}


def test_tutorial_docs_contain_the_exact_tested_command_lines():
    for doc_name, lines in DOC_TRANSCRIPTS.items():
        text = (DOCS / doc_name).read_text(encoding="utf-8")
        for line in lines:
            assert line in text, (
                f"{doc_name} is missing a tested tutorial line:\n{line}")


# --- Harness -------------------------------------------------------------------


@pytest.fixture
def sim():
    simulator = Simulator()
    yield simulator
    simulator.close()


async def build(sim, lines, *, staff="admin"):
    """Run one tutorial's build transcript as a staff builder from Limbo."""
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
    builder.add_tag(staff)
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


# --- 176. Staff dashboard -------------------------------------------------------


class TestStaffDashboard:

    async def test_dashboard_reports_health_players_and_incidents(self, sim):
        bob = await build(sim, BUILD_176)
        assert bob.location is room(sim, "The Operations Center")
        ops = room(sim, "The Operations Center")
        console = obj(sim, "Ops Console")

        kess = sim.player("Kess", location=ops)
        zeke = sim.player("Zeke", location=ops)
        await fire_event(kess, ops, "event:connect")
        await fire_event(zeke, ops, "event:connect")
        assert console.db.get("online") == [kess.id, zeke.id]

        # A death anywhere on the world zone is logged as an incident.
        await fire_event(zeke, ops, "event:death")
        assert any("death: Zeke in The Operations Center" in x
                   for x in console.db.get("incidents"))

        sim.seen(bob)
        await sim.do(bob, "dashboard")
        out = text(sim, bob)
        assert "=== STATION OPS ===" in out
        assert "uptime:" in out
        assert "online: 2 / 3 characters" in out          # kess+zeke online, +bob total
        assert "death: Zeke in The Operations Center" in out

    async def test_disconnect_drops_from_the_roster(self, sim):
        bob = await build(sim, BUILD_176)
        ops = room(sim, "The Operations Center")
        console = obj(sim, "Ops Console")
        kess = sim.player("Kess", location=ops)
        await fire_event(kess, ops, "event:connect")
        assert console.db.get("online") == [kess.id]
        await fire_event(kess, ops, "event:disconnect")
        assert console.db.get("online") == []

    async def test_non_staff_get_a_dark_console(self, sim):
        bob = await build(sim, BUILD_176)
        ops = room(sim, "The Operations Center")
        mortal = sim.player("Mort", location=ops)
        await sim.do(mortal, "dashboard")
        assert "The ops console stays dark for you." in text(sim, mortal)

    async def test_builtin_stats_is_the_engine_internals_view(self, sim):
        bob = await build(sim, BUILD_176)
        sim.seen(bob)
        await sim.do(bob, "@stats")
        assert "Engine stats:" in text(sim, bob)


# --- 177. Jail system -----------------------------------------------------------


class TestJailSystem:

    async def test_jail_confines_then_auto_releases(self, sim):
        bob = await build(sim, BUILD_177)
        precinct = room(sim, "The Precinct")
        cell = room(sim, "The Holding Cell")
        vandal = sim.player("Vandal", location=precinct)

        await sim.do(bob, "jail Vandal = 1")
        assert "Jailed Vandal for 1 minute(s)." in text(sim, bob)
        assert vandal.location is cell
        assert vandal.has_tag("jailed")
        assert "hauled off to the Holding Cell" in text(sim, vandal)

        # The locked cell exit refuses the prisoner.
        sim.seen(vandal)
        await sim.do(vandal, "back")
        assert vandal.location is cell
        assert "can't go back" in text(sim, vandal).lower()

        # The sentence timer auto-releases on the world tick.
        sim.seen(vandal)
        reaped = await reap_expired(sim.store, now=time.time() + 120)
        assert reaped == 1
        assert vandal.location is precinct
        assert not vandal.has_tag("jailed")
        assert "Time served." in text(sim, vandal)
        assert not objs(sim, "a sentence timer")   # timer consumed

    async def test_free_releases_early_and_clears_the_timer(self, sim):
        bob = await build(sim, BUILD_177)
        precinct = room(sim, "The Precinct")
        cell = room(sim, "The Holding Cell")
        vandal = sim.player("Vandal", location=precinct)

        await sim.do(bob, "jail Vandal = 30")
        assert vandal.location is cell
        assert len(objs(sim, "a sentence timer")) == 1

        await sim.do(bob, "free Vandal")
        assert "Freed Vandal." in text(sim, bob)
        assert vandal.location is precinct
        assert not vandal.has_tag("jailed")
        assert not objs(sim, "a sentence timer")   # early release cancels it

        # Reaping now finds nothing to release.
        assert await reap_expired(sim.store, now=time.time() + 3600) == 0

    async def test_logging_and_staff_gate(self, sim):
        bob = await build(sim, BUILD_177)
        precinct = room(sim, "The Precinct")
        vandal = sim.player("Vandal", location=precinct)
        rook = sim.player("Rook", location=precinct)

        await sim.do(bob, "jail Vandal = 5")
        await sim.do(bob, "free Vandal")
        sim.seen(bob)
        await sim.do(bob, "jail log")
        out = text(sim, bob)
        assert "Bob jailed Vandal (5m)" in out
        assert "Bob freed Vandal" in out

        # A non-staff prisoner cannot work the Warden.
        await sim.do(rook, "jail Vandal = 99")
        assert "Only staff may work the Warden." in text(sim, rook)
        assert not vandal.has_tag("jailed")


# --- 179. Character approval queue ----------------------------------------------


class TestApprovalQueue:

    async def test_unapproved_gated_then_approved_and_freed(self, sim):
        bob = await build(sim, BUILD_179)
        arrivals = room(sim, "The Arrivals Lounge")
        newbie = sim.player("Newbie", location=arrivals)
        # New characters arrive tagged 'unapproved' (chargen/onboarding does this);
        # here we stamp it by hand to represent a fresh arrival.
        await sim.do(bob, "@tag Newbie = unapproved")
        assert newbie.has_tag("unapproved")

        # The gate holds: an unapproved arrival cannot reach the concourse.
        sim.seen(newbie)
        await sim.do(newbie, "concourse")
        assert newbie.location is arrivals
        assert "can't go concourse" in text(sim, newbie).lower()

        # Staff see the queue and approve.
        await sim.do(bob, "pending")
        assert "- Newbie (#" in text(sim, bob)
        sim.seen(newbie)
        await sim.do(bob, "approve Newbie")
        assert "Approved Newbie." in text(sim, bob)
        assert not newbie.has_tag("unapproved")
        assert newbie.has_tag("approved")
        assert "Your character has been approved." in text(sim, newbie)

        # Now the gate opens.
        await sim.do(newbie, "concourse")
        assert newbie.location is room(sim, "The Concourse")

    async def test_reject_notifies_and_keeps_them_pending(self, sim):
        bob = await build(sim, BUILD_179)
        arrivals = room(sim, "The Arrivals Lounge")
        rowdy = sim.player("Rowdy", location=arrivals)
        await sim.do(bob, "@tag Rowdy = unapproved")

        sim.seen(rowdy)
        await sim.do(bob, "reject Rowdy = name violates the setting; pick another")
        assert "Sent Rowdy back with notes." in text(sim, bob)
        assert "name violates the setting; pick another" in text(sim, rowdy)
        # Rejection keeps them pending — still gated.
        assert rowdy.has_tag("unapproved")

    async def test_only_staff_may_review(self, sim):
        bob = await build(sim, BUILD_179)
        arrivals = room(sim, "The Arrivals Lounge")
        newbie = sim.player("Newbie", location=arrivals)
        await sim.do(bob, "@tag Newbie = unapproved")
        # A non-staff arrival cannot approve anyone (not even themselves).
        await sim.do(newbie, "approve Newbie")
        assert "Only staff may clear arrivals." in text(sim, newbie)
        assert newbie.has_tag("unapproved")


# --- 181. Announcement system ---------------------------------------------------


class TestAnnouncements:

    async def test_server_wide_notice_reaches_everyone_and_keeps_history(self, sim):
        bob = await build(sim, BUILD_181)
        booth = room(sim, "The Broadcast Booth")
        near = sim.player("Kess", location=booth)
        far = sim.player("Zeke", location=room(sim, "Limbo"))   # off the world zone

        await sim.do(bob, "announce Reactor drill at 0300. This is only a drill.")
        assert "Broadcast sent to all listening players." in text(sim, bob)
        nout = text(sim, near)
        assert "[NOTICE]" in nout
        assert "Reactor drill at 0300. This is only a drill." in nout
        # Server-wide: even a player nowhere near the booth hears it.
        assert "Reactor drill at 0300. This is only a drill." in text(sim, far)

        await sim.do(near, "news")
        assert ("1. Reactor drill at 0300. This is only a drill.  --Bob"
                in text(sim, near))

    async def test_opt_out_skips_live_delivery_but_not_history(self, sim):
        bob = await build(sim, BUILD_181)
        booth = room(sim, "The Broadcast Booth")
        kess = sim.player("Kess", location=booth)

        await sim.do(kess, "mute news")
        assert "You opt out of live notices." in text(sim, kess)
        sim.seen(kess)
        await sim.do(bob, "announce Second notice, please ignore.")
        assert "Second notice" not in text(sim, kess)         # muted: no live line

        await sim.do(kess, "news")
        assert "Second notice, please ignore." in text(sim, kess)   # history has it

        await sim.do(kess, "unmute news")
        sim.seen(kess)
        await sim.do(bob, "announce Third notice.")
        kout = text(sim, kess)
        assert "[NOTICE]" in kout and "Third notice." in kout

    async def test_only_staff_may_broadcast(self, sim):
        bob = await build(sim, BUILD_181)
        booth = room(sim, "The Broadcast Booth")
        kess = sim.player("Kess", location=booth)
        await sim.do(kess, "announce free credits!")
        assert "Only staff may broadcast." in text(sim, kess)


# --- 182. Object snapshot / restore ---------------------------------------------


class TestSnapshotRestore:

    async def test_snapshot_and_restore_named_fields(self, sim):
        bob = await build(sim, BUILD_182)
        stall = obj(sim, "market stall")

        await sim.do(bob, "snapshot market stall = price stock")
        assert "Snapshot of market stall saved: price, stock." in text(sim, bob)

        # An event mangles the stall's state...
        await sim.do(bob, "@set market stall/price = 999")
        await sim.do(bob, "@set market stall/stock = 0")
        assert stall.db.get("price") == 999

        # ...and restore rolls exactly those fields back.
        sim.seen(bob)
        await sim.do(bob, "restore market stall")
        assert "Restored 2 field(s) to market stall." in text(sim, bob)
        assert stall.db.get("price") == 10
        assert stall.db.get("stock") == 5

    async def test_snapshots_index_and_missing_snapshot(self, sim):
        bob = await build(sim, BUILD_182)
        await sim.do(bob, "snapshot market stall = price stock")
        sim.seen(bob)
        await sim.do(bob, "snapshots")
        assert "- market stall (#" in text(sim, bob)

        await sim.do(bob, "restore Restoration Vault")   # never snapshotted
        assert "No snapshot on file for Restoration Vault." in text(sim, bob)

    async def test_admin_authority_restores_a_player_field(self, sim):
        bob = await build(sim, BUILD_182)
        vandal = sim.player("Vandal", location=room(sim, "Limbo"), title="Rookie")

        await sim.do(bob, "snapshot Vandal = title")
        assert "Snapshot of Vandal saved: title." in text(sim, bob)
        vandal.db.set("title", "Overlord Supreme")   # some later drift

        sim.seen(bob)
        await sim.do(bob, "restore Vandal")
        assert vandal.db.get("title") == "Rookie"

    async def test_non_staff_cannot_snapshot(self, sim):
        bob = await build(sim, BUILD_182)
        archive = room(sim, "The Archive")
        zeke = sim.player("Zeke", location=archive)
        await sim.do(zeke, "snapshot market stall = price")
        assert "Only staff may snapshot." in text(sim, zeke)


# --- 183. Permission tiers in practice ------------------------------------------


class TestPermissionTiers:

    async def test_tag_gated_lock_blocks_then_admits(self, sim):
        bob = await build(sim, BUILD_183)
        secoff = room(sim, "The Security Office")
        box = obj(sim, "strongbox")
        rook = sim.player("Rook", location=secoff)   # plain player

        await sim.do(rook, "get strongbox")
        assert box.location is secoff
        assert "can't pick up strongbox" in text(sim, rook).lower()

        await sim.do(bob, "@tag Rook = cleared")
        await sim.do(rook, "get strongbox")
        assert box.location is rook

    async def test_admin_bypass_and_quell(self, sim):
        bob = await build(sim, BUILD_183)
        secoff = room(sim, "The Security Office")
        box = obj(sim, "strongbox")

        # A hard-deny lock — nobody passes the expression.
        await sim.do(bob, "@lock strongbox = False")
        await sim.do(bob, "get strongbox")
        assert box.location is bob            # admin bypasses locks
        await sim.do(bob, "drop strongbox")

        # Quell drops the bypass: a quelled admin acts as a mortal.
        await sim.do(bob, "quell")
        await sim.do(bob, "get strongbox")
        assert box.location is secoff         # now blocked
        await sim.do(bob, "unquell")
        await sim.do(bob, "get strongbox")
        assert box.location is bob            # powers restored

    async def test_controls_authority_gates_softcode_mutation(self, sim):
        bob = await build(sim, BUILD_183)
        secoff = room(sim, "The Security Office")
        rook = sim.player("Rook", location=secoff)
        bel = sim.player("Bel", location=secoff)
        bel.add_tag("builder")

        # A builder does not control a player: the write returns False, no change.
        await sim.do(bel, "@eval result = set_attr(get('Rook'), 'hp', 7)")
        assert "=> False" in text(sim, bel)
        assert rook.db.get("hp") is None

        # An admin controls everything: the same write lands.
        await sim.do(bob, "@eval result = set_attr(get('Rook'), 'hp', 7)")
        assert "=> True" in text(sim, bob)
        assert rook.db.get("hp") == 7


# --- 184. New-player onboarding -------------------------------------------------


class TestOnboarding:

    async def test_first_connect_grants_kit_greeting_and_mentor_ping(self, sim):
        bob = await build(sim, BUILD_184)
        obay = room(sim, "The Orientation Bay")
        mira = sim.player("Mira", location=obay)
        await sim.do(bob, "@tag Mira = mentor")
        newbie = sim.player("Newbie", location=obay, credits=0)

        await fire_event(newbie, obay, "event:connect")
        assert "Welcome aboard, Newbie!" in text(sim, newbie)
        assert newbie.db.get("credits") == 100
        assert newbie.db.get("oriented") is not None
        assert any(o.name == "a welcome datapad" for o in newbie.contents)
        mout = text(sim, mira)
        assert "[mentor]" in mout and "New arrival: Newbie" in mout

    async def test_kit_is_granted_once(self, sim):
        bob = await build(sim, BUILD_184)
        obay = room(sim, "The Orientation Bay")
        newbie = sim.player("Newbie", location=obay, credits=0)

        await fire_event(newbie, obay, "event:connect")
        sim.seen(newbie)
        await fire_event(newbie, obay, "event:connect")   # reconnect
        assert "Welcome aboard" not in text(sim, newbie)
        assert newbie.db.get("credits") == 100            # not doubled
        assert len([o for o in newbie.contents
                    if o.name == "a welcome datapad"]) == 1


# --- 186. Watchlist & alerts ----------------------------------------------------


class TestWatchlist:

    async def test_watch_alerts_on_connect_and_on_attack(self, sim):
        bob = await build(sim, BUILD_186)   # Bob is admin => staff, gets alerts
        hub = room(sim, "The Security Hub")
        vandal = sim.player("Vandal", location=hub)

        await sim.do(bob, "watch Vandal = suspected smurf")
        assert "Now watching Vandal." in text(sim, bob)
        assert vandal.has_tag("watched")

        sim.seen(bob)
        await fire_event(vandal, hub, "event:connect")
        cout = text(sim, bob)
        assert "[WATCH]" in cout
        assert "Vandal (watched) just connected." in cout

        sim.seen(bob)
        await fire_event(vandal, hub, "event:attack")
        assert "Vandal (watched) is throwing punches." in text(sim, bob)

    async def test_watchlist_and_unwatch(self, sim):
        bob = await build(sim, BUILD_186)
        hub = room(sim, "The Security Hub")
        vandal = sim.player("Vandal", location=hub)
        await sim.do(bob, "watch Vandal = suspected smurf")

        sim.seen(bob)
        await sim.do(bob, "watchlist")
        assert "- Vandal :: suspected smurf" in text(sim, bob)

        await sim.do(bob, "unwatch Vandal")
        assert not vandal.has_tag("watched")

        # An unwatched player's connect raises no alert.
        kess = sim.player("Kess", location=hub)
        sim.seen(bob)
        await fire_event(kess, hub, "event:connect")
        assert "[WATCH]" not in text(sim, bob)

    async def test_only_staff_may_set_watches(self, sim):
        bob = await build(sim, BUILD_186)
        hub = room(sim, "The Security Hub")
        zeke = sim.player("Zeke", location=hub)
        kess = sim.player("Kess", location=hub)
        await sim.do(zeke, "watch Kess = x")
        assert "Only staff may set watches." in text(sim, zeke)
        assert not kess.has_tag("watched")
