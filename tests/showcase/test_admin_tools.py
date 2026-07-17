"""
Showcase verification — Admin, Moderation & Staff Tools.

Items: 176 staff dashboard, 177 jail system, 179 character approval queue,
181 announcement system, 182 object snapshot/restore, 183 permission tiers
in practice, 184 new-player onboarding, 186 watchlist & alerts.  (178/180/185
are [small] engine-gap items and are not covered here.)

Every command line in each tutorial's "Build it" section is read straight out
of its markdown (docs/showcase/NNN_*.md) at run time and driven through the
real dispatcher (raw input in -> session output out) by a *staff* builder — so
these tests execute what the tutorial says, and a doc edit that breaks a build
breaks this suite.  The plays then exercise the tutorials' "Try it" flows and
assert outcomes.

These are ADMIN tools: the consoles are admin-owned world-zone masters, so
their scripts run with owner authority and may legitimately act on players
(teleport, tag, credit, restore) — the boundary the tutorials document.

Connection/death/attack events (ON_CONNECT / ON_DISCONNECT / ON_DEATH /
ON_ATTACK) are emitted with fire_event, built to the same action shapes the
live server propagates — including who is actor vs. target and what rides
in `extra` for `adata()` to read, since the witnesses under test depend on
exactly that (see announce_death).  expire() lifetimes are reaped with a
forged clock (reap_expired), exactly as on the world tick.
"""

from __future__ import annotations

import time
from pathlib import Path
import re

import pytest

from realm.core.events import fire_event, reap_expired
from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

BUILD_RED_FLAGS = (
    "Unknown command", "Usage:", "not found", "Script error",
    "No permission", "Invalid lock", "Permission denied",
)


def build_lines(doc_name: str) -> list[str]:
    """Every command line in the tutorial's "Build it" fenced blocks."""
    body = (DOCS / doc_name).read_text(encoding="utf-8")
    match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
    assert match, f"{doc_name}: no Build it section"
    lines: list[str] = []
    for block in re.findall(r"```text\n(.*?)```", match.group(1), re.S):
        lines.extend(line for line in block.splitlines() if line.strip())
    assert lines, f"{doc_name}: empty Build it"
    return lines


# --- Harness -------------------------------------------------------------------


@pytest.fixture
def sim():
    simulator = Simulator()
    yield simulator
    simulator.close()


async def build(sim, doc_name, *, staff="admin", cast=()):
    """Run one tutorial's build transcript as a staff builder from Limbo.

    ``cast`` names players the transcript itself refers to (184 deputizes a
    mentor by name); they are created in Limbo before the build runs.
    """
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
    builder.add_tag(staff)
    for name in cast:
        sim.player(name, location=limbo)
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


async def announce_death(victim, killer=None):
    """Announce a death exactly as the engine's one death path does.

    Mirrors realm.combat.manager._propagate_death: the *killer* is the
    actor (None for a poison tick, a trap, a long fall), the victim is the
    target, ``killer`` is a NAME, and ``fatal`` is False for a player, who
    is knocked unconscious rather than killed.
    """
    await fire_event(killer, victim, "combat:on_death", extra={
        "killer": killer.name if killer is not None else None,
        "fatal": not victim.has_tag("player"),
    })


# --- 176. Staff dashboard -------------------------------------------------------


class TestStaffDashboard:

    async def test_dashboard_reports_health_players_and_incidents(self, sim):
        bob = await build(sim, "176_staff_dashboard.md")
        assert bob.location is room(sim, "The Operations Center")
        ops = room(sim, "The Operations Center")
        console = obj(sim, "Ops Console")

        kess = sim.player("Kess", location=ops)
        zeke = sim.player("Zeke", location=ops)
        await fire_event(kess, ops, "event:connect")
        await fire_event(zeke, ops, "event:connect")
        assert console.db.get("online") == [kess.id, zeke.id]

        # A death anywhere on the world zone is logged as an incident. The
        # engine announces combat:on_death from its ONE death path, so the
        # feed sees a killed NPC and a dropped player alike — and the hook
        # reads the action itself (target = who fell, adata for the rest)
        # rather than assuming the enactor is the victim: the enactor is
        # the KILLER.
        rat = sim.obj("a rat", location=ops, tags=["npc"])
        await announce_death(rat, killer=kess)
        incidents = console.db.get("incidents")
        assert any("death: a rat in The Operations Center (by Kess)" in x
                   for x in incidents)

        # A player going down is logged too, and honestly: unconscious, not
        # dead (adata('fatal') is False), and no killer to name.
        await announce_death(zeke)
        incidents = console.db.get("incidents")
        assert any("down: Zeke in The Operations Center" in x
                   for x in incidents)
        assert not any("(by " in x for x in incidents if "Zeke" in x)

        sim.seen(bob)
        await sim.do(bob, "dashboard")
        out = text(sim, bob)
        assert "=== STATION OPS ===" in out
        assert "uptime:" in out
        assert "online: 2 / 3 characters" in out          # kess+zeke online, +bob total
        assert "death: a rat in The Operations Center (by Kess)" in out
        assert "down: Zeke in The Operations Center" in out

    async def test_disconnect_drops_from_the_roster(self, sim):
        bob = await build(sim, "176_staff_dashboard.md")
        ops = room(sim, "The Operations Center")
        console = obj(sim, "Ops Console")
        kess = sim.player("Kess", location=ops)
        await fire_event(kess, ops, "event:connect")
        assert console.db.get("online") == [kess.id]
        await fire_event(kess, ops, "event:disconnect")
        assert console.db.get("online") == []

    async def test_non_staff_get_a_dark_console(self, sim):
        bob = await build(sim, "176_staff_dashboard.md")
        ops = room(sim, "The Operations Center")
        mortal = sim.player("Mort", location=ops)
        await sim.do(mortal, "dashboard")
        assert "The ops console stays dark for you." in text(sim, mortal)

    async def test_builtin_stats_is_the_engine_internals_view(self, sim):
        bob = await build(sim, "176_staff_dashboard.md")
        sim.seen(bob)
        await sim.do(bob, "@stats")
        assert "Engine stats:" in text(sim, bob)


# --- 177. Jail system -----------------------------------------------------------


class TestJailSystem:

    async def test_jail_confines_then_auto_releases(self, sim):
        bob = await build(sim, "177_jail_system.md")
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
        bob = await build(sim, "177_jail_system.md")
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
        bob = await build(sim, "177_jail_system.md")
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
        bob = await build(sim, "179_approval_queue.md")
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
        bob = await build(sim, "179_approval_queue.md")
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
        bob = await build(sim, "179_approval_queue.md")
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
        bob = await build(sim, "181_announcements.md")
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
        bob = await build(sim, "181_announcements.md")
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
        bob = await build(sim, "181_announcements.md")
        booth = room(sim, "The Broadcast Booth")
        kess = sim.player("Kess", location=booth)
        await sim.do(kess, "announce free credits!")
        assert "Only staff may broadcast." in text(sim, kess)


# --- 182. Object snapshot / restore ---------------------------------------------


class TestSnapshotRestore:

    async def test_snapshot_and_restore_named_fields(self, sim):
        bob = await build(sim, "182_snapshot_restore.md")
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
        bob = await build(sim, "182_snapshot_restore.md")
        await sim.do(bob, "snapshot market stall = price stock")
        sim.seen(bob)
        await sim.do(bob, "snapshots")
        assert "- market stall (#" in text(sim, bob)

        await sim.do(bob, "restore Restoration Vault")   # never snapshotted
        assert "No snapshot on file for Restoration Vault." in text(sim, bob)

    async def test_admin_authority_restores_a_player_field(self, sim):
        bob = await build(sim, "182_snapshot_restore.md")
        vandal = sim.player("Vandal", location=room(sim, "Limbo"), title="Rookie")

        await sim.do(bob, "snapshot Vandal = title")
        assert "Snapshot of Vandal saved: title." in text(sim, bob)
        vandal.db.set("title", "Overlord Supreme")   # some later drift

        sim.seen(bob)
        await sim.do(bob, "restore Vandal")
        assert vandal.db.get("title") == "Rookie"

    async def test_non_staff_cannot_snapshot(self, sim):
        bob = await build(sim, "182_snapshot_restore.md")
        archive = room(sim, "The Archive")
        zeke = sim.player("Zeke", location=archive)
        await sim.do(zeke, "snapshot market stall = price")
        assert "Only staff may snapshot." in text(sim, zeke)


# --- 183. Permission tiers in practice ------------------------------------------


class TestPermissionTiers:

    async def test_tag_gated_lock_blocks_then_admits(self, sim):
        bob = await build(sim, "183_permission_tiers.md")
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
        bob = await build(sim, "183_permission_tiers.md")
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
        bob = await build(sim, "183_permission_tiers.md")
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
        # The tutorial's own last build line deputizes Mira by tag.
        await build(sim, "184_onboarding.md", cast=["Mira"])
        obay = room(sim, "The Orientation Bay")
        mira = obj(sim, "Mira")
        assert mira.has_tag("mentor")
        mira.location = obay
        newbie = sim.player("Newbie", location=obay, credits=0)

        await fire_event(newbie, obay, "event:connect")
        assert "Welcome aboard, Newbie!" in text(sim, newbie)
        assert newbie.db.get("credits") == 100
        assert newbie.db.get("oriented") is not None
        assert any(o.name == "a welcome datapad" for o in newbie.contents)
        mout = text(sim, mira)
        assert "[mentor]" in mout and "New arrival: Newbie" in mout

    async def test_kit_is_granted_once(self, sim):
        await build(sim, "184_onboarding.md", cast=["Mira"])
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
        bob = await build(sim, "186_watchlist.md")   # Bob is admin => staff, gets alerts
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

        # combat:on_attack's real shape: the attacker is the actor (so the
        # office's `enactor` check is the right one here), the defender is
        # the target. Mirrors CombatSystem._propagate_attack.
        rook = sim.player("Rook", location=hub)
        sim.seen(bob)
        await fire_event(vandal, rook, "combat:on_attack", extra={
            "weapon": None, "attacker_hp": 12, "defender_hp": 9})
        assert "Vandal (watched) is throwing punches." in text(sim, bob)

    async def test_watchlist_and_unwatch(self, sim):
        bob = await build(sim, "186_watchlist.md")
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
        bob = await build(sim, "186_watchlist.md")
        hub = room(sim, "The Security Hub")
        zeke = sim.player("Zeke", location=hub)
        kess = sim.player("Kess", location=hub)
        await sim.do(zeke, "watch Kess = x")
        assert "Only staff may set watches." in text(sim, zeke)
        assert not kess.has_tag("watched")
