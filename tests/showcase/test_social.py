"""
Showcase verification — Social & Player Systems (items 219-229).

Items: 219 friends list, 220 titles & badges, 221 player organizations,
222 org treasury & storage, 223 elections, 224 petition/ticket system,
225 player-to-player notes, 226 mentor program, 227 event calendar &
RSVP, 228 leaderboards, 229 login streak rewards.

Every command line in each tutorial's "Build it" section is read
straight out of its markdown (docs/showcase/NNN_*.md) and driven through
the real dispatcher by a builder — so a doc edit that breaks the build
breaks this suite. The plays then walk the tutorials' "Try it" flows and
assert outcomes.

The builder Vala is an admin: she owns the masters she creates (so their
owner-authority reaches players and world props) and doubles as the
"staff" actor the staff-gated verbs check for the `admin` tag. Bob and
Cass are ordinary players.

Connection events (ON_CONNECT / ON_DISCONNECT) are emitted with
fire_event, the same action shape the live server propagates at
login/logout; script_ticker heartbeats are ticked by hand.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

import realm.behaviors  # noqa: F401 — registers script_ticker
from realm.core.economy import get_credits
from realm.core.events import fire_event
from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

BUILD_RED_FLAGS = (
    "Unknown command", "Script error", "Syntax error", "Traceback",
    "Forbidden name", "Forbidden construct", "Private name",
    "Private attribute",
)


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


# --- Harness -------------------------------------------------------------------


class World:
    """Vala (admin builder+staff), Bob and Cass (mortals). Each tutorial
    digs its own room live; the mortals follow the builder in."""

    def __init__(self):
        self.sim = Simulator()
        self.landing = self.sim.room("The Landing")
        self.vala = self.sim.player("Vala", location=self.landing)
        self.vala.add_tag("admin")
        self.bob = self.sim.player("Bob", location=self.landing)
        self.cass = self.sim.player("Cass", location=self.landing)

    async def build(self, *docs: str):
        """Run one or more tutorials' build transcripts as Vala, then
        gather the mortals into her room. Red-flag scanned."""
        for doc in docs:
            for line in build_lines(doc):
                await self.sim.do(self.vala, line)
        out = "\n".join(self.sim.seen(self.vala))
        for flag in BUILD_RED_FLAGS:
            assert flag not in out, f"{docs} build tripped {flag!r}:\n{out}"
        room = self.vala.location
        self.bob.location = room
        self.cass.location = room
        for p in (self.vala, self.bob, self.cass):
            self.sim.seen(p)
        return room

    def text(self, player) -> str:
        return "\n".join(self.sim.seen(player))

    def find(self, name):
        hits = self.sim.store.find_cached(name=name)
        return hits[0] if hits else None

    async def connect(self, player):
        await fire_event(player, player.location, "event:connect")

    async def disconnect(self, player):
        await fire_event(player, player.location, "event:disconnect")

    async def fund(self, player, amount):
        await self.sim.do(
            self.vala, f"@eval adjust_credits(get('{player.name}'), {amount})")

    def close(self):
        self.sim.close()


@pytest.fixture
async def world():
    w = World()
    try:
        yield w
    finally:
        w.close()


# --- 219. Friends list ----------------------------------------------------------


@pytest.mark.asyncio
class TestFriends:

    async def test_befriend_list_and_unfriend(self, world):
        w = world
        await w.build("219_friends_list.md")

        await w.sim.do(w.bob, "befriend Vala")
        assert "Added Vala to your contacts." in w.text(w.bob)
        await w.sim.do(w.bob, "befriend Cass")
        assert "Added Cass to your contacts." in w.text(w.bob)
        await w.sim.do(w.bob, "befriend Vala")            # dupe refused
        assert "already a contact" in w.text(w.bob)

        await w.sim.do(w.bob, "friends")
        out = w.text(w.bob)
        assert "Your contacts:" in out
        assert "Vala - offline" in out and "Cass - offline" in out

        await w.sim.do(w.bob, "unfriend Cass")
        assert "Removed Cass from your contacts." in w.text(w.bob)
        await w.sim.do(w.bob, "friends")
        assert "Cass" not in w.text(w.bob)

    async def test_connect_notifies_watchers_and_hide_silences(self, world):
        w = world
        await w.build("219_friends_list.md")
        # Bob watches Vala; Bob is online (on the roster).
        await w.sim.do(w.bob, "befriend Vala")
        await w.connect(w.bob)
        w.sim.seen(w.bob)

        await w.connect(w.vala)
        assert "Vala has come online." in w.text(w.bob)

        await w.disconnect(w.vala)
        assert "Vala has gone offline." in w.text(w.bob)

        # Vala cloaks; her comings and goings stop announcing.
        await w.sim.do(w.vala, "cloak")
        assert "Cloaked" in w.text(w.vala)
        await w.connect(w.vala)
        assert "Vala has come online." not in w.text(w.bob)
        await w.sim.do(w.vala, "uncloak")
        await w.connect(w.vala)
        assert "Vala has come online." in w.text(w.bob)

    async def test_connect_greets_with_online_contact_count(self, world):
        w = world
        await w.build("219_friends_list.md")
        await w.sim.do(w.vala, "befriend Bob")
        await w.connect(w.bob)                            # Bob now on roster
        w.sim.seen(w.vala)
        await w.connect(w.vala)
        assert "1 of your contacts are online." in w.text(w.vala)


# --- 220. Titles & badges -------------------------------------------------------


@pytest.mark.asyncio
class TestTitles:

    async def test_award_shows_in_look_and_finger(self, world):
        w = world
        await w.build("220_titles_badges.md")

        await w.sim.do(w.vala, "award Bob = First Blood")
        assert 'Awarded "First Blood" to Bob.' in w.text(w.vala)
        await w.sim.do(w.vala, "award Bob = Void Champion")
        assert "You have been awarded the title: Void Champion" in w.text(w.bob)

        await w.sim.do(w.cass, "look Bob")
        out = w.text(w.cass)
        assert "Void Champion - badges: First Blood, Void Champion" in out

        await w.sim.do(w.cass, "finger Bob")
        assert "Bob - Void Champion - badges: First Blood, Void Champion" \
            in w.text(w.cass)

    async def test_settitle_picks_an_earned_badge(self, world):
        w = world
        await w.build("220_titles_badges.md")
        await w.sim.do(w.vala, "award Bob = First Blood")
        await w.sim.do(w.vala, "award Bob = Void Champion")

        await w.sim.do(w.bob, "settitle First Blood")
        assert "Now displaying: First Blood" in w.text(w.bob)
        await w.sim.do(w.cass, "look Bob")
        assert "First Blood - badges: First Blood, Void Champion" in w.text(w.cass)

        await w.sim.do(w.bob, "settitle Unearned Glory")
        assert "You have not earned that title." in w.text(w.bob)

        await w.sim.do(w.bob, "titles")
        out = w.text(w.bob)
        assert "Displaying: First Blood" in out
        assert "Earned: First Blood, Void Champion" in out

    async def test_only_staff_award(self, world):
        w = world
        await w.build("220_titles_badges.md")
        await w.sim.do(w.bob, "award Cass = Cheater")
        assert "Only staff award titles" in w.text(w.bob)
        await w.sim.do(w.cass, "finger Cass")
        assert "no title" in w.text(w.cass)


# --- 221. Player organizations --------------------------------------------------


@pytest.mark.asyncio
class TestOrganizations:

    async def _founded(self, w):
        await w.build("221_organizations.md")
        await w.sim.do(w.vala, "org found")
        await w.sim.do(w.vala, "org invite Bob")
        await w.sim.do(w.bob, "org join")
        for p in (w.vala, w.bob, w.cass):
            w.sim.seen(p)

    async def test_found_invite_join_and_roster(self, world):
        w = world
        await w.build("221_organizations.md")
        org = w.find("the Void Runners")

        await w.sim.do(w.vala, "org found")
        assert "Vala founds the Void Runners" in w.text(w.vala)
        assert org.db.get("leader") == w.vala.id
        await w.sim.do(w.vala, "org found")              # already led
        assert "already have a leader" in w.text(w.vala)

        await w.sim.do(w.vala, "org invite Bob")
        assert "Invitation sent to Bob." in w.text(w.vala)
        assert "invites you to join" in w.text(w.bob)
        await w.sim.do(w.bob, "org join")
        assert "Bob joins the Void Runners as a Recruit." in w.text(w.bob)

        await w.sim.do(w.bob, "org")
        out = w.text(w.bob)
        assert "Vala - Commander" in out and "Bob - Recruit" in out

    async def test_rank_authority(self, world):
        w = world
        await self._founded(w)
        org = w.find("the Void Runners")

        # Non-officer cannot invite.
        await w.sim.do(w.bob, "org invite Cass")
        assert "Only officers invite" in w.text(w.bob)

        # Commander promotes Bob; Bob still cannot touch the Commander.
        await w.sim.do(w.vala, "org promote Bob")
        assert "promotes Bob to Officer" in w.text(w.vala)
        assert org.db.get("rank_" + w.bob.id) == 2
        await w.sim.do(w.bob, "org kick Vala")
        assert "must outrank a fellow member" in w.text(w.bob)
        assert org.db.get("leader") == w.vala.id

        # Now an officer, Bob may invite Cass.
        await w.sim.do(w.bob, "org invite Cass")
        assert "Invitation sent to Cass." in w.text(w.bob)
        await w.sim.do(w.cass, "org join")
        await w.sim.do(w.vala, "org kick Cass")
        assert "expels Cass" in w.text(w.vala)
        assert w.cass.id not in org.db.get("roster")

    async def test_leader_cannot_leave_with_members(self, world):
        w = world
        await self._founded(w)
        await w.sim.do(w.vala, "org leave")
        assert "must promote a successor" in w.text(w.vala)
        await w.sim.do(w.bob, "org leave")
        assert "Bob leaves the Void Runners." in w.text(w.bob)


# --- 222. Org treasury & storage ------------------------------------------------


@pytest.mark.asyncio
class TestTreasury:

    async def _crew(self, w):
        await w.build("221_organizations.md", "222_org_treasury.md")
        await w.sim.do(w.vala, "org found")
        await w.sim.do(w.vala, "org invite Bob")
        await w.sim.do(w.bob, "org join")
        for p in (w.vala, w.bob, w.cass):
            w.sim.seen(p)
        return w.find("the Void Runners")

    async def test_deposit_open_withdraw_officer_gated(self, world):
        w = world
        org = await self._crew(w)
        await w.fund(w.bob, 100)

        await w.sim.do(w.bob, "treasury deposit 40")
        assert "Deposited 40 credits." in w.text(w.bob)
        assert get_credits(org) == 40
        assert get_credits(w.bob) == 60

        await w.sim.do(w.bob, "treasury withdraw 10")    # recruit blocked
        assert "Officers only" in w.text(w.bob)
        assert get_credits(org) == 40

        await w.sim.do(w.vala, "treasury withdraw 10")
        assert "Withdrew 10 credits." in w.text(w.vala)
        assert get_credits(org) == 30

        await w.sim.do(w.vala, "treasury")
        out = w.text(w.vala)
        assert "Void Runners treasury: 30 credits." in out
        assert "Bob deposited 40" in out and "Vala withdrew 10" in out

    async def test_lockers_are_rank_sealed(self, world):
        w = world
        org = await self._crew(w)

        # Cass, no rank at all, cannot even open the common locker.
        await w.sim.do(w.cass, "open the crew footlocker")
        assert "sealed to Void Runners members" in w.text(w.cass)

        # Officers' safe (min_rank 2): the recruit bounces.
        await w.sim.do(w.bob, "open the officers safe")
        assert "Officers only" in w.text(w.bob)

        # Common footlocker (min_rank 1): the member opens it.
        await w.sim.do(w.bob, "open the crew footlocker")
        out = w.text(w.bob)
        assert "You open" in out and "crew footlocker" in out

        # Promote Bob; the safe now reads his new rank and opens.
        await w.sim.do(w.vala, "org promote Bob")
        await w.sim.do(w.bob, "open the officers safe")
        out = w.text(w.bob)
        assert "You open" in out and "officers safe" in out


# --- 223. Elections -------------------------------------------------------------


@pytest.mark.asyncio
class TestElections:

    async def _crew(self, w):
        await w.build("221_organizations.md", "223_elections.md")
        await w.sim.do(w.vala, "org found")
        await w.sim.do(w.vala, "org invite Bob")
        await w.sim.do(w.bob, "org join")
        for p in (w.vala, w.bob, w.cass):
            w.sim.seen(p)
        return w.find("the Void Runners")

    async def test_ballot_dedupes_and_tally_installs_leader(self, world):
        w = world
        org = await self._crew(w)

        await w.sim.do(w.vala, "election start 60")
        assert "calls an election for Commander" in w.text(w.vala)
        await w.sim.do(w.bob, "nominate Bob")
        assert "Bob is nominated" in w.text(w.bob)
        await w.sim.do(w.vala, "nominate Vala")

        await w.sim.do(w.bob, "vote Bob")
        await w.sim.do(w.vala, "vote Vala")
        assert len(org.db.get("ballots")) == 2
        # Vala changes her mind — her single slot moves, no new ballot.
        await w.sim.do(w.vala, "vote Bob")
        assert len(org.db.get("ballots")) == 2

        await w.sim.do(w.bob, "poll")
        assert "Bob - 2 vote(s)" in w.text(w.bob)

        # Close the term and beat the ticker.
        await w.sim.do(
            w.vala, "@eval set_attr(get('the Void Runners'), 'close_at', now() - 1)")
        await w.sim.do(w.vala, "@tr the Void Runners/on_tick")
        assert "Bob is elected Commander with 2 vote(s)." in w.text(w.vala)
        assert org.db.get("leader") == w.bob.id
        assert org.db.get("rank_" + w.bob.id) == 3
        assert org.db.get("rank_" + w.vala.id) == 2
        assert not org.db.get("poll_open")

    async def test_only_leader_starts_and_members_only_vote(self, world):
        w = world
        org = await self._crew(w)
        await w.sim.do(w.bob, "election start 60")       # not the leader
        assert "Only the leader calls an election" in w.text(w.bob)
        assert not org.db.get("poll_open")

        await w.sim.do(w.vala, "election start 60")
        await w.sim.do(w.vala, "nominate Vala")
        await w.sim.do(w.cass, "vote Vala")              # not a member
        assert "you are not a member" in w.text(w.cass)


# --- 224. Petition / ticket system ----------------------------------------------


@pytest.mark.asyncio
class TestPetitions:

    async def test_file_list_claim_resolve_and_notify(self, world):
        w = world
        await w.build("224_petitions.md")
        desk = w.find("the Requests Desk")

        await w.sim.do(w.bob, "petition The airlock on Deck 3 is stuck.")
        assert "Filed request #1." in w.text(w.bob)
        await w.sim.do(w.bob, "petition Requesting a name change.")
        assert "Filed request #2." in w.text(w.bob)

        await w.sim.do(w.bob, "petitions")
        out = w.text(w.bob)
        assert "#1 [open] Bob: The airlock on Deck 3 is stuck." in out
        assert "#2 [open]" in out

        # Cass sees only her own (none); Vala (staff) sees all.
        await w.sim.do(w.cass, "petitions")
        assert "No requests on file for you." in w.text(w.cass)
        await w.sim.do(w.vala, "petitions")
        assert "#1 [open] Bob:" in w.text(w.vala)

        await w.sim.do(w.cass, "claim 1")               # not staff
        assert "you are not staff" in w.text(w.cass)

        await w.sim.do(w.vala, "claim 1")
        assert "You claim request #1." in w.text(w.vala)
        assert "Vala is now handling your request #1." in w.text(w.bob)

        await w.sim.do(
            w.vala, "resolve 1 = Maintenance dispatched; cycle the override.")
        assert "Resolved request #1." in w.text(w.vala)
        assert "was resolved by Vala: Maintenance dispatched" in w.text(w.bob)
        assert desk.db.get("ticket_1")["status"] == "closed"

    async def test_connect_nudges_staff_about_backlog(self, world):
        w = world
        await w.build("224_petitions.md")
        await w.sim.do(w.bob, "petition Something is broken.")
        w.sim.seen(w.vala)

        await w.connect(w.vala)
        assert "1 open request(s) awaiting staff." in w.text(w.vala)
        # A non-staff connect gets no nudge.
        await w.connect(w.bob)
        assert "awaiting staff" not in w.text(w.bob)


# --- 225. Player-to-player notes ------------------------------------------------


@pytest.mark.asyncio
class TestNotes:

    async def test_public_profile_and_layered_staff_notes(self, world):
        w = world
        await w.build("225_player_notes.md")
        registry = w.find("the Registry")

        await w.sim.do(w.bob, "bio Freelance salvager. Ask about the Kessari job.")
        assert "Your public profile is updated." in w.text(w.bob)
        await w.sim.do(w.cass, "look Bob")
        assert "Profile: Freelance salvager." in w.text(w.cass)
        await w.sim.do(w.cass, "profile Bob")
        assert "Bob profile: Freelance salvager." in w.text(w.cass)

        # Vala annotates Bob. The marker line shows only to staff.
        await w.sim.do(
            w.vala, "note Bob = Flagged for griefing on Deck 3. Watching.")
        assert "Staff note added to Bob." in w.text(w.vala)

        await w.sim.do(w.vala, "look Bob")
        out_staff = w.text(w.vala)
        assert "Profile: Freelance salvager." in out_staff
        assert "[staff notes: 1 on file" in out_staff

        await w.sim.do(w.cass, "look Bob")
        out_mortal = w.text(w.cass)
        assert "Profile: Freelance salvager." in out_mortal
        assert "staff notes" not in out_mortal          # gated per-viewer

    async def test_notes_contents_are_secret(self, world):
        w = world
        await w.build("225_player_notes.md")
        await w.sim.do(w.vala, "note Bob = Confidential incident report.")

        await w.sim.do(w.vala, "notes Bob")
        assert "Confidential incident report." in w.text(w.vala)

        await w.sim.do(w.cass, "notes Bob")
        assert "Only staff read notes." in w.text(w.cass)

        # The secret flag defeats even a crafted read from a mortal's script.
        result, _ = await w.sim.eval(
            w.cass, "pemit(enactor, str(get_attr(get('the Registry'), "
                    "'staff_notes', 'BLOCKED')))",
            enactor=w.cass)
        assert "Confidential" not in w.text(w.cass)


# --- 226. Mentor program --------------------------------------------------------


@pytest.mark.asyncio
class TestMentor:

    async def test_veteran_signup_match_and_connect_nudge(self, world):
        w = world
        await w.build("226_mentor_program.md")

        # No flag, no mentoring.
        await w.sim.do(w.bob, "mentor signup")
        assert "Only veterans may mentor" in w.text(w.bob)

        await w.sim.do(w.vala, "@tag Vala = veteran")
        await w.sim.do(w.vala, "mentor signup")
        assert "You are now a mentor." in w.text(w.vala)

        await w.sim.do(w.bob, "mentor request")
        assert "matched with mentor Vala" in w.text(w.bob)
        assert "Bob has been matched to you as a new mentee." in w.text(w.vala)
        await w.sim.do(w.vala, "mentor")
        assert "Your mentees: Bob" in w.text(w.vala)

        # Presence: with the mentor online, Bob logging in nudges her.
        await w.connect(w.vala)
        w.sim.seen(w.vala)
        await w.connect(w.bob)
        assert "Your mentee Bob just logged in." in w.text(w.vala)

    async def test_least_loaded_match_and_graduate(self, world):
        w = world
        await w.build("226_mentor_program.md")
        await w.sim.do(w.vala, "@tag Vala = veteran")
        await w.sim.do(w.vala, "mentor signup")
        await w.sim.do(w.bob, "mentor request")          # Vala: 1 mentee

        # Cass volunteers with zero mentees; a new newcomer matches Cass.
        await w.sim.do(w.vala, "@tag Cass = veteran")
        await w.sim.do(w.cass, "mentor signup")
        newbie = w.sim.player("Dax", location=w.vala.location)
        await w.sim.do(newbie, "mentor request")
        assert "matched with mentor Cass" in "\n".join(w.sim.seen(newbie))

        await w.sim.do(w.bob, "mentor graduate")
        assert "You have graduated." in w.text(w.bob)
        assert "Bob has graduated from your mentorship." in w.text(w.vala)


# --- 227. Event calendar & RSVP -------------------------------------------------


@pytest.mark.asyncio
class TestEvents:

    async def test_add_rsvp_and_reminder_tick(self, world):
        w = world
        await w.build("227_event_calendar.md")
        board = w.find("the Community Board")

        await w.sim.do(w.bob, "event add 300 = Cargo Bay Fight Night")
        assert "Scheduled Cargo Bay Fight Night as event #1." in w.text(w.bob)
        await w.sim.do(w.cass, "events")
        out = w.text(w.cass)
        assert "Cargo Bay Fight Night by Bob" in out and "1 attending" in out

        await w.sim.do(w.cass, "rsvp 1")
        assert "You RSVP to Cargo Bay Fight Night." in w.text(w.cass)
        assert w.cass.id in board.db.get("event_1")["rsvps"]
        await w.sim.do(w.cass, "rsvp 1")                 # toggle off
        assert "You cancel your RSVP" in w.text(w.cass)
        assert w.cass.id not in board.db.get("event_1")["rsvps"]
        await w.sim.do(w.cass, "rsvp 1")                 # back on for the ping

        # Pull the start time inside the reminder window and beat.
        await w.sim.do(
            w.vala, "@eval set_attr(get('the Community Board'), 'event_1', "
                    "dict(get_attr(get('the Community Board'), 'event_1'), "
                    "at=now() + 30))")
        await w.sim.do(w.vala, "@tr the Community Board/on_tick")
        assert "starts in under" in w.text(w.bob)        # host on the list
        assert "starts in under" in w.text(w.cass)
        assert board.db.get("event_1")["reminded"] == 1

        # A second beat must not re-remind.
        w.sim.seen(w.bob)
        await w.sim.do(w.vala, "@tr the Community Board/on_tick")
        assert "starts in under" not in w.text(w.bob)

    async def test_host_cancel_notifies_attendees(self, world):
        w = world
        await w.build("227_event_calendar.md")
        board = w.find("the Community Board")
        await w.sim.do(w.bob, "event add 300 = Poetry Night")
        await w.sim.do(w.cass, "rsvp 1")
        w.sim.seen(w.cass)

        await w.sim.do(w.cass, "event cancel 1")          # not the host
        assert "you are not its host" in w.text(w.cass)
        await w.sim.do(w.bob, "event cancel 1")
        assert "Poetry Night has been cancelled by Bob." in w.text(w.cass)
        assert board.db.get("event_1") is None


# --- 228. Leaderboards ----------------------------------------------------------


@pytest.mark.asyncio
class TestLeaderboards:

    async def test_periodic_aggregation_and_cached_reads(self, world):
        w = world
        await w.build("228_leaderboards.md")
        board = w.find("the Hall of Fame board")

        await w.sim.do(w.vala, "@eval set_attr(get('Bob'), 'craft_score', 120)")
        await w.sim.do(w.vala, "@eval set_attr(get('Cass'), 'craft_score', 80)")
        await w.fund(w.cass, 500)
        await w.sim.do(w.vala, "@tr the Hall of Fame board/rebuild")

        assert board.db.get("board_craft")[0] == "Bob - 120"
        assert board.db.get("board_craft")[1] == "Cass - 80"

        await w.sim.do(w.bob, "leaderboard crafters")
        out = w.text(w.bob)
        assert "Top crafters:" in out
        assert "1. Bob - 120" in out and "2. Cass - 80" in out

        await w.sim.do(w.bob, "leaderboard richest")
        assert "Cass - 500" in w.text(w.bob)

        await w.sim.do(w.bob, "leaderboard")
        assert "LEADERBOARD CRAFTERS" in w.text(w.bob)

    async def test_reads_are_cached_not_live(self, world):
        w = world
        await w.build("228_leaderboards.md")
        await w.sim.do(w.vala, "@eval set_attr(get('Bob'), 'craft_score', 50)")
        await w.sim.do(w.vala, "@tr the Hall of Fame board/rebuild")
        await w.sim.do(w.vala, "@eval set_attr(get('Bob'), 'craft_score', 999)")
        # No re-tally: the board still shows the cached number.
        await w.sim.do(w.bob, "leaderboard crafters")
        assert "Bob - 50" in w.text(w.bob)


# --- 229. Login streak rewards --------------------------------------------------


@pytest.mark.asyncio
class TestLoginStreaks:

    async def test_first_login_consecutive_grace_and_reset(self, world):
        w = world
        await w.build("229_login_streaks.md")
        kiosk = w.find("the Daily Rewards")

        await w.connect(w.bob)
        assert "Day 1 streak! 10 credits paid." in w.text(w.bob)
        assert get_credits(w.bob) == 10
        assert kiosk.db.get("streak_" + w.bob.id) == 1

        # Yesterday -> day 2 (scaling payout).
        await w.sim.do(
            w.vala, "@eval set_attr(get('the Daily Rewards'), 'last_' + "
                    "get('Bob').id, now() // 86400 - 1)")
        await w.connect(w.bob)
        assert "Day 2 streak! 20 credits paid." in w.text(w.bob)
        assert get_credits(w.bob) == 30

        # Missed one day (gap 2): grace keeps the streak climbing.
        await w.sim.do(
            w.vala, "@eval set_attr(get('the Daily Rewards'), 'last_' + "
                    "get('Bob').id, now() // 86400 - 2)")
        await w.connect(w.bob)
        out = w.text(w.bob)
        assert "Day 3 streak! 30 credits paid." in out
        assert "grace: welcome back" in out

        # Missed three days: the streak resets to 1.
        await w.sim.do(
            w.vala, "@eval set_attr(get('the Daily Rewards'), 'last_' + "
                    "get('Bob').id, now() // 86400 - 5)")
        await w.connect(w.bob)
        assert "Day 1 streak! 10 credits paid." in w.text(w.bob)

    async def test_second_login_same_day_pays_nothing(self, world):
        w = world
        await w.build("229_login_streaks.md")
        await w.connect(w.bob)
        assert get_credits(w.bob) == 10
        w.sim.seen(w.bob)

        await w.connect(w.bob)
        assert "already claimed today" in w.text(w.bob)
        assert get_credits(w.bob) == 10                  # no double pay

    async def test_streak_status_verb(self, world):
        w = world
        await w.build("229_login_streaks.md")
        await w.connect(w.bob)
        await w.sim.do(w.bob, "streak")
        out = w.text(w.bob)
        assert "Current login streak: 1 day(s)." in out
        assert "Next reward: 20 credits" in out
