"""
MUD_PLAN step 14: clans with governments, after CoffeeMud
(``resources/clangovernments.xml``, ``Common/interfaces/Clan.java``).
"""

from __future__ import annotations

import logging

import pytest

from realm.config.loader import Settings
from realm.core.defs import all_defs
from realm.packs import import_pack
from realm.permissions.locks import check_lock
from realm.std.clans import clans as clan_clock
from realm.std.clans.clans import (
    add_member,
    clan_of,
    find_clan,
    position_of,
    record_of,
    upkeep,
)
from realm.std.clans.governments import CAN, CANNOT, VOTE, government
from realm.std.clans.votes import close_expired, open_votes
from realm.std.rules.system import award
from realm.testing import Simulator

SHIPPED = ["gang", "guild", "union", "fellowship", "anarchy", "co-op", "meritocracy",
           "plutocracy"]
MERC = "realm.games.merc.system.MercSystem"


class Clock:
    """The injected wall clock clans read (``realm.std.clans.clans.now``)."""

    def __init__(self, monkeypatch, start: float = 1_000_000.0):
        self.t = start
        monkeypatch.setattr(clan_clock, "now", lambda: self.t)

    def days(self, n: float) -> None:
        self.t += n * clan_clock.day_seconds()


def _sim(**raw) -> Simulator:
    game_system = raw.pop("game_system", None)
    return Simulator(settings=Settings(raw=raw), game_system=game_system)


@pytest.fixture
async def sim():
    s = _sim()
    await import_pack("clan-governments", s.store)
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def clock(monkeypatch):
    return Clock(monkeypatch)


def _people(sim, *names, credits=20000):
    hall = sim.room("Hall")
    return hall, [sim.player(n, location=hall, credits=credits) for n in names]


async def _say(sim, who, line) -> str:
    await sim.do(who, line)
    return "\n".join(sim.seen(who))


def _drain(sim, *people) -> None:
    for p in people:
        sim.seen(p)


async def _gang(sim):
    """Alice founds the Ravens (a gang); Bob is accepted."""
    hall, (alice, bob, cass) = _people(sim, "Alice", "Bob", "Cass")
    await sim.do(alice, "clan found Ravens = gang")
    await sim.do(bob, "clan apply Ravens")
    await sim.do(alice, "clan accept Bob")
    _drain(sim, alice, bob, cass)
    return hall, alice, bob, cass, find_clan("Ravens")


def _government(sim, name, **attrs):
    base = {
        "description": "a test government",
        "positions": [
            {"id": "chief", "rank": 0, "max": 1,
             "powers": ["accept", "assign", "exile", "withdraw", "deposit", "channel",
                        "benefits", "list_members", "home_privs"]},
            {"id": "member", "rank": 1, "powers": ["deposit", "channel", "benefits"]},
        ],
        "accept_position": "member",
    }
    base.update(attrs)
    return sim.obj(name, tags=["clan_government_def"], **base)


# --- 14.1 governments as data ---------------------------------------------------------


async def test_each_shipped_government_loads_and_validates(sim):
    loaded = all_defs("clan_government")
    assert sorted(loaded) == sorted(SHIPPED)
    gang, guild, union = government("gang"), government("guild"), government("union")
    assert [p.id for p in gang.positions][:2] == ["boss", "lieutenant"]
    assert gang.applicant_position == "applicant" and gang.auto_promote == "rank"
    assert government("anarchy").applicant_position is None
    assert government("meritocracy").auto_promote == "xp"
    assert government("plutocracy").auto_promote == "gold"
    assert government("plutocracy").top.limit(250) == 3          # 1%, rounded up
    # A gang decides nothing by vote; a guild votes on assignments among
    # guildmasters and secretaries; a union's citizens vote on them too.
    assert not any(gang.voted(p) for p in ("assign", "accept", "tax"))
    assert guild.authority("guildmaster", "assign") == VOTE
    assert guild.authority("treasurer", "assign") == CANNOT
    assert union.authority("citizen", "assign") == VOTE
    assert union.authority("citizen", "accept") == CANNOT
    assert union.authority("senator", "accept") == VOTE
    # The co-op cannot tax or declare at all: nobody holds it, nobody votes.
    assert not government("co-op").usable("tax")
    assert not government("co-op").usable("declare")


@pytest.mark.parametrize("attrs, problem", [
    ({"positions": [{"id": "boss", "rank": 0, "powers": ["accept", "conquer"]}],
      "accept_position": "boss"}, "unknown power"),
    ({"positions": [], "accept_position": "boss"}, "no positions"),
    ({"positions": [{"id": "boss", "rank": 0, "powers": []}],
      "accept_position": "grunt"}, "accept_position 'grunt'"),
])
async def test_a_malformed_government_is_refused_with_its_name(sim, caplog, attrs, problem):
    sim.obj("Tyranny", tags=["clan_government_def"], **attrs)
    with caplog.at_level(logging.WARNING):
        loaded = all_defs("clan_government")
    assert "tyranny" not in loaded
    assert "gang" in loaded
    warned = "\n".join(r.getMessage() for r in caplog.records)
    assert "clan government 'Tyranny'" in warned and problem in warned


# --- 14.2 founding and members ---------------------------------------------------------


async def test_founding_costs_clan_cost(sim):
    _hall, (alice, bob) = _people(sim, "Alice", "Bob")
    bob.db.credits = 50
    assert "costs 10000" in await _say(sim, bob, "clan found Smiths = guild")
    assert find_clan("Smiths") is None and bob.db.credits == 50
    out = await _say(sim, alice, "clan found Ravens = gang")
    assert "You found Ravens, a gang, and are its Boss." in out
    ravens = find_clan("Ravens")
    assert alice.db.credits == 10000
    assert position_of(ravens, alice).id == "boss"
    assert clan_of(alice) is ravens and ravens.db.status == "active"
    assert "already a clan called Ravens" in await _say(sim, bob, "clan found ravens = gang")
    assert "no government 'empire'" in await _say(sim, bob, "clan found X = empire")


async def test_without_a_cost_only_administrators_found():
    s = _sim(CLAN_COST=None, CLAN_MIN_MEMBERS=2)
    await import_pack("clan-governments", s.store)
    try:
        _hall, (alice, root) = _people(s, "Alice", "Root")
        root.add_tag("admin")
        assert "Only an administrator" in await _say(s, alice, "clan found Ravens = gang")
        out = await _say(s, root, "@clan create Ravens = gang, Alice")
        assert "Created Ravens, a gang led by Alice." in out
        ravens = find_clan("Ravens")
        assert position_of(ravens, alice).id == "boss" and alice.db.credits == 20000
        # Pending until it has CLAN_MIN_MEMBERS members: no tax, no relations.
        assert ravens.db.status == "pending"
        assert "not yet fully founded" in await _say(s, alice, "clan tax 5")
        assert not ravens.db.get("tax")
    finally:
        s.close()


async def test_the_life_of_a_gang_member(sim):
    _hall, (alice, bob, cass) = _people(sim, "Alice", "Bob", "Cass")
    await sim.do(alice, "clan found Ravens = gang")
    ravens = find_clan("Ravens")
    _drain(sim, alice)
    assert "You apply to join Ravens." in await _say(sim, bob, "clan apply Ravens")
    assert "Bob applies to join" in "\n".join(sim.seen(alice))
    assert clan_of(bob) is None and record_of(ravens, bob)["position"] == "applicant"
    assert "Bob is accepted." in await _say(sim, alice, "clan accept Bob")
    assert position_of(ravens, bob).id == "member" and clan_of(bob) is ravens
    # A member holds none of the boss's powers.
    await sim.do(cass, "clan apply Ravens")
    assert "you cannot accept members" in await _say(sim, bob, "clan accept Cass")
    assert "you cannot reject" in await _say(sim, bob, "clan reject Cass")
    assert "you cannot assign" in await _say(sim, bob, "clan assign Cass = staff")
    assert "you cannot exile" in await _say(sim, bob, "clan exile Alice")
    assert "you cannot withdraw" in await _say(sim, bob, "clan withdraw 5")
    assert "rejected" in await _say(sim, alice, "clan reject Cass")
    assert record_of(ravens, cass) is None and not cass.db.get("clans")
    # The boss assigns and exiles.
    assert "Bob is now Lieutenant." in await _say(sim, alice, "clan assign Bob = lieutenant")
    assert position_of(ravens, bob).id == "lieutenant"
    # A lieutenant may accept, but not touch the boss.
    assert "you cannot exile" in await _say(sim, bob, "clan exile Alice")
    assert "Bob is exiled." in await _say(sim, alice, "clan exile Bob")
    assert record_of(ravens, bob) is None and clan_of(bob) is None
    assert "You are exiled from Ravens." in "\n".join(sim.seen(bob))


async def test_a_full_position_is_refused(sim):
    _hall, alice, bob, cass, ravens = await _gang(sim)
    await sim.do(cass, "clan apply Ravens")
    await sim.do(alice, "clan accept Cass")
    assert "Bob is now Treasurer." in await _say(sim, alice, "clan assign Bob = treasurer")
    out = await _say(sim, alice, "clan assign Cass = treasurer")
    assert "The position of Treasurer is full." in out
    assert position_of(ravens, cass).id == "member"


async def test_a_position_lock_refuses_an_unqualified_member(sim):
    _government(sim, "Order", positions=[
        {"id": "grandmaster", "rank": 0, "max": 1, "powers": ["accept", "assign"]},
        {"id": "knight", "rank": 1, "lock": "get_attr(caller, 'level', 0) >= 10",
         "powers": []},
        {"id": "squire", "rank": 2, "powers": []}], accept_position="squire")
    _hall, (alice, bob) = _people(sim, "Alice", "Bob")
    await sim.do(alice, "clan found Templars = order")
    await sim.do(bob, "clan apply Templars")
    order = find_clan("Templars")
    assert position_of(order, bob).id == "squire"     # no applicant position: in at once
    assert "Bob may not be Knight." in await _say(sim, alice, "clan assign Bob = knight")
    bob.db.level = 12
    assert "Bob is now Knight." in await _say(sim, alice, "clan assign Bob = knight")


async def test_one_clan_per_category(sim):
    _government(sim, "Craft", category="trade")
    _hall, alice, bob, cass, ravens = await _gang(sim)
    assert "already in a clan of that kind" in await _say(sim, bob, "clan found Owls = gang")
    out = await _say(sim, bob, "clan found Smiths = craft")
    assert "You found Smiths" in out
    smiths = find_clan("Smiths")
    assert clan_of(bob) is ravens and clan_of(bob, "trade") is smiths
    await sim.do(cass, "clan found Owls = gang")
    assert "already in a clan of that kind" in await _say(sim, bob, "clan apply Owls")
    out = await _say(sim, bob, "clan")
    assert "Member of Ravens" in out and "Chief of Smiths" in out


async def test_joining_is_limited_by_level_lock_and_size():
    s = _sim(CLAN_MIN_LEVEL=5, CLAN_MAX_MEMBERS=2)
    await import_pack("clan-governments", s.store)
    try:
        _government(s, "Club", required_lock="get_attr(caller, 'cleared', False)")
        _hall, (alice, bob, cass, dan) = _people(s, "Alice", "Bob", "Cass", "Dan")
        assert "must be level 5" in await _say(s, alice, "clan found Ravens = gang")
        alice.db.level = 5
        assert "You found Ravens" in await _say(s, alice, "clan found Ravens = gang")
        await s.do(bob, "clan apply Ravens")
        await s.do(alice, "clan accept Bob")
        assert "has all the members it may" in await _say(s, cass, "clan apply Ravens")
        dan.db.level = 9
        assert "may not lead a club" in await _say(s, dan, "clan found Owls = club")
        dan.db.cleared = True
        assert "You found Owls" in await _say(s, dan, "clan found Owls = club")
        assert "Owls will not have you." in await _say(s, cass, "clan apply Owls")
    finally:
        s.close()


async def test_the_last_leader_must_be_replaced_first(sim):
    _hall, alice, bob, cass, ravens = await _gang(sim)
    out = await _say(sim, alice, "clan assign Alice = member")
    assert "Alice is the last Boss and must be replaced first." in out
    assert "Bob is now Boss." in await _say(sim, alice, "clan assign Bob = boss")
    assert position_of(ravens, alice).id == "member"     # the old boss steps down


async def test_the_message_of_the_day_at_login(sim):
    from realm.core.events import fire_event
    _hall, alice, bob, cass, ravens = await _gang(sim)
    await sim.do(alice, "clan motd = Raid at dawn.")
    _drain(sim, alice, bob)
    await fire_event(alice, alice.location, "event:connect")
    await fire_event(bob, bob.location, "event:connect")
    assert "[Ravens] Raid at dawn." in sim.seen(alice)
    assert "[Ravens] Raid at dawn." not in sim.seen(bob)     # a member lacks motd_read
    assert "you cannot read its message" in await _say(sim, bob, "clan motd")


async def test_importing_the_pack_twice_adds_nothing(sim):
    await import_pack("clan-governments", sim.store)
    assert len(sim.store.find_cached(tag="clan_government_def")) == len(SHIPPED)


async def test_nobody_acts_on_a_member_at_or_above_their_rank(sim):
    _government(sim, "Court", positions=[
        {"id": "king", "rank": 0, "max": 1, "powers": ["accept", "assign", "exile"]},
        {"id": "duke", "rank": 1, "powers": ["assign", "exile"]},
        {"id": "commoner", "rank": 2, "powers": []}], accept_position="commoner")
    _hall, (alice, bob, cass, dan) = _people(sim, "Alice", "Bob", "Cass", "Dan")
    await sim.do(alice, "clan found Realm = court")
    court = find_clan("Realm")
    for person in (bob, cass, dan):
        await sim.do(person, "clan apply Realm")
    await sim.do(alice, "clan assign Bob = duke")
    await sim.do(alice, "clan assign Cass = duke")
    assert "below your rank" in await _say(sim, bob, "clan assign Dan = duke")
    assert "do not rank below you" in await _say(sim, bob, "clan exile Cass")
    assert "do not rank below you" in await _say(sim, bob, "clan exile Alice")
    assert "Dan is exiled." in await _say(sim, bob, "clan exile Dan")
    assert record_of(court, cass) is not None and record_of(court, alice) is not None


# --- 14.3 voting ---------------------------------------------------------------------


async def _fellowship(sim, *names):
    """Alice founds a fellowship; everyone named joins (each acceptance is
    voted on, and passes)."""
    hall, people = _people(sim, "Alice", *names)
    alice = people[0]
    await sim.do(alice, "clan found Friends = fellowship")
    clan = find_clan("Friends")
    for person in people[1:]:
        await sim.do(person, "clan apply Friends")
        await add_member(clan, person, "citizen", how="accepted")  # set up directly
    _drain(sim, *people)
    return clan, people


async def test_a_fellowship_elects_its_leader(sim, clock):
    friends, (alice, bob, cass) = await _fellowship(sim, "Bob", "Cass")
    assert position_of(friends, alice).id == "first_citizen"
    out = await _say(sim, cass, "clan assign Bob = first citizen")
    assert "Vote 1 is open: make Bob First Citizen." in out
    assert "calls a vote" in "\n".join(sim.seen(bob))
    assert "You vote yes" in await _say(sim, bob, "clan vote 1 yes")
    # Two of three: passed at once. Bob leads; Alice steps down.
    assert position_of(friends, bob).id == "first_citizen"
    assert position_of(friends, alice).id == "citizen"
    assert not open_votes(friends)
    assert "Vote 1 (make Bob First Citizen) passes, 2 to 0." in "\n".join(sim.seen(cass))


async def test_a_vote_fails_early_when_a_majority_says_no(sim, clock):
    friends, (alice, bob, cass) = await _fellowship(sim, "Bob", "Cass")
    await sim.do(cass, "clan exile Bob")
    assert "Vote 1 is open" in "\n".join(sim.seen(cass))
    await sim.do(alice, "clan vote 1 no")
    assert open_votes(friends)                  # 1 yes, 1 no, Bob still to vote
    await sim.do(bob, "clan vote 1 no")
    assert not open_votes(friends)
    assert record_of(friends, bob) is not None
    assert "fails, 1 to 2" in "\n".join(sim.seen(cass))


async def test_a_vote_without_its_quorum_fails_at_the_deadline(sim, clock):
    # A fellowship's quorum is 33%: of six voters, two must vote.
    friends, people = await _fellowship(sim, "Bob", "Cass", "Dan", "Eve", "Fay")
    alice = people[0]
    await sim.do(alice, "clan premise = Friends forever.")
    assert len(open_votes(friends)) == 1        # 1 of 6: neither passed nor failed
    clock.days(99)
    await close_expired()
    assert open_votes(friends)                  # 100 game days to run
    clock.days(2)
    await close_expired()
    assert not open_votes(friends)
    assert not friends.db.get("premise")        # 1 ballot of 6: under the quorum
    assert "fails, 1 to 0" in "\n".join(sim.seen(alice))
    # With the quorum met, the majority of ballots cast carries it.
    await sim.do(alice, "clan premise = Friends forever.")
    await sim.do(people[1], "clan vote 2 yes")
    await sim.do(people[2], "clan vote 2 no")
    clock.days(101)
    await close_expired()
    assert friends.db.get("premise") == "Friends forever."


async def test_only_holders_of_vote_assign_vote_on_an_assignment(sim, clock):
    _hall, (alice, bob, cass, dan) = _people(sim, "Alice", "Bob", "Cass", "Dan")
    await sim.do(alice, "clan found Smiths = guild")
    smiths = find_clan("Smiths")
    for person, pos in ((bob, "secretary"), (cass, "treasurer"), (dan, "member")):
        await add_member(smiths, person, pos, how="accepted")
    out = await _say(sim, alice, "clan assign Dan = chief")
    assert "Vote 1 is open" in out
    assert "no vote on that" in await _say(sim, cass, "clan vote 1 yes")
    assert "you cannot assign" in await _say(sim, dan, "clan assign Cass = chief")
    assert "decided" in await _say(sim, bob, "clan vote 1 yes")
    assert position_of(smiths, dan).id == "chief"


async def test_a_gang_never_votes(sim):
    _hall, alice, bob, cass, ravens = await _gang(sim)
    assert "you cannot assign" in await _say(sim, bob, "clan assign Bob = boss")
    assert "you cannot write its premise" in await _say(sim, bob, "clan premise = Ours")
    assert "Bob is now Staff." in await _say(sim, alice, "clan assign Bob = staff")
    assert not open_votes(ravens)


async def test_the_proposer_withdraws_a_vote(sim, clock):
    friends, (alice, bob) = await _fellowship(sim, "Bob")
    await sim.do(alice, "clan exile Bob")
    assert "Only the member who called" in await _say(sim, bob, "clan vote 1 withdraw")
    assert "withdrawn" in await _say(sim, alice, "clan vote 1 withdraw")
    assert not open_votes(friends)


# --- 14.4 treasury, tax, levels and benefits ------------------------------------------


async def test_deposit_and_withdraw_by_power(sim):
    _hall, alice, bob, cass, ravens = await _gang(sim)
    out = await _say(sim, bob, "clan deposit 300")
    assert "You deposit 300 credits; the treasury holds 300." in out
    assert bob.db.credits == 19700 and record_of(ravens, bob)["donated_gold"] == 300
    assert "you cannot withdraw" in await _say(sim, bob, "clan withdraw 100")
    assert "You withdraw 100 credits" in await _say(sim, alice, "clan withdraw 100")
    assert alice.db.credits == 10100 and ravens.db.treasury == 200
    assert "holds only 200" in await _say(sim, alice, "clan withdraw 500")
    assert "you cannot list its deposits" in await _say(sim, bob, "clan deposits")
    out = await _say(sim, alice, "clan deposits")
    assert "Bob" in out and "300 credits" in out
    assert "You don't have that much." in await _say(sim, cass, "clan deposit 5") \
        or "not in a clan" in await _say(sim, cass, "clan deposit 5")


async def test_without_economy_the_treasury_is_unavailable(sim):
    _hall, alice, bob, cass, ravens = await _gang(sim)
    del sim.world.services["economy"]
    assert "treasury of Ravens is unavailable" in await _say(sim, alice, "clan deposit 5")
    assert "treasury of Ravens is unavailable" in await _say(sim, alice, "clan withdraw 5")


async def test_the_tax_takes_a_share_of_a_kill_award():
    s = _sim(game_system=MERC)
    await import_pack("clan-governments", s.store)
    try:
        _hall, alice, bob, _cass, ravens = await _gang(s)
        assert "taxes 20%" in await _say(s, alice, "clan tax 20")
        assert "tax runs from 0 to 25" in await _say(s, alice, "clan tax 30")
        bob.db.xp = 0
        paid = award(bob, 100)
        assert paid == 80 and bob.db.xp == 80
        assert ravens.db.xp == 20 and record_of(ravens, bob)["donated_xp"] == 20
        assert "Ravens takes 20 as its tax." in "\n".join(s.seen(bob))
        # Donating directly, from experience toward the next level.
        assert "You give 50 experience" in await _say(s, bob, "clan donate xp 50")
        assert bob.db.xp == 30 and ravens.db.xp == 70
        assert "You have 30 to give" in await _say(s, bob, "clan donate xp 500")
    finally:
        s.close()


async def test_a_clan_level_brings_its_benefit_and_exile_takes_it(sim):
    _government(sim, "Lodge", xp_per_level="100 * level", benefits=[
        {"level": 2, "tags": ["lodge_sigil"], "check_mods": {"all": 1},
         "pool_max": {"hp": 5}}])
    _hall, (alice, bob) = _people(sim, "Alice", "Bob")
    bob.db.hp, bob.db.max_hp = 10, 10
    await sim.do(alice, "clan found Elks = lodge")
    await sim.do(bob, "clan apply Elks")
    elks = find_clan("Elks")
    _drain(sim, alice, bob)
    root = sim.player("Root", location=alice.location)
    root.add_tag("admin")
    await sim.do(root, "@clan xp Elks = 99")
    assert elks.db.level == 1 and not bob.has_tag("lodge_sigil")
    await sim.do(root, "@clan xp Elks = 1")
    assert elks.db.level == 2
    assert "Elks has reached clan level 2!" in "\n".join(sim.seen(bob))
    assert bob.has_tag("lodge_sigil") and bob.db.max_hp == 15
    from realm.std.rules.checks import condition_modifier
    assert condition_modifier(bob, "stealth") == 1
    await sim.do(alice, "clan exile Bob")
    assert not bob.has_tag("lodge_sigil") and bob.db.max_hp == 10 and bob.db.hp == 10
    assert condition_modifier(bob, "stealth") == 0


async def test_benefits_return_at_login(sim):
    from realm.core.events import fire_event
    _government(sim, "Lodge", xp_per_level="100 * level",
                benefits=[{"level": 1, "tags": ["lodge_sigil"]}])
    _hall, (alice,) = _people(sim, "Alice")
    await sim.do(alice, "clan found Elks = lodge")
    alice.remove_tag("lodge_sigil")
    alice.db.delete("clan_tags")
    await fire_event(alice, alice.location, "event:connect")
    assert alice.has_tag("lodge_sigil")


async def test_a_plutocracy_follows_the_money(sim):
    _hall, (alice, bob, cass) = _people(sim, "Alice", "Bob", "Cass")
    await sim.do(alice, "clan found Bankers = plutocracy")
    bankers = find_clan("Bankers")
    for person in (bob, cass):
        await sim.do(person, "clan apply Bankers")
        await sim.do(alice, f"clan accept {person.name}")
    await sim.do(alice, "clan deposit 100")
    assert position_of(bankers, alice).id == "tycoon"
    await sim.do(bob, "clan deposit 100")             # a tie keeps the holder
    assert position_of(bankers, alice).id == "tycoon"
    await sim.do(bob, "clan deposit 1")
    assert position_of(bankers, bob).id == "tycoon"
    assert position_of(bankers, alice).id == "serf"
    assert "Bob is now Tycoon." in "\n".join(sim.seen(cass))


# --- 14.5 relations ------------------------------------------------------------------


async def test_declaring_relations(sim):
    _hall, alice, bob, cass, ravens = await _gang(sim)
    await sim.do(cass, "clan found Smiths = gang")
    smiths = find_clan("Smiths")
    assert "Ravens declares war toward Smiths." in await _say(sim, alice,
                                                              "clan declare Smiths = war")
    assert "you cannot declare" in await _say(sim, bob, "clan declare Smiths = ally")
    out = await _say(sim, cass, "clan relations")
    assert "Ravens" in out and "they: war" in out
    result, err = await sim.eval(alice.location, "result = [clan_relation('Ravens', 'Smiths'),"
                                 " clan_relation('Smiths', 'Ravens'),"
                                 " clans_at_war('Smiths', 'Ravens')]")
    assert err is None and result == ["war", "neutral", True]
    # An alliance holds only when both sides declare it.
    await sim.do(alice, "clan declare Smiths = ally")
    assert "(alliance)" not in await _say(sim, alice, "clan relations")
    await sim.do(cass, "clan declare Ravens = ally")
    assert "(alliance)" in await _say(sim, alice, "clan relations")
    result, _err = await sim.eval(alice.location, "result = clans_at_war('Smiths', 'Ravens')")
    assert result is False
    smiths.db.status = "pending"
    assert "fully founded" in await _say(sim, alice, "clan declare Smiths = war")
    assert ravens.db.relations == {"Smiths": "ally"}


# --- 14.6 upkeep ---------------------------------------------------------------------


def _offline(sim, *people) -> None:
    for person in people:
        sim.sessions.unlink_player_from_session(sim.session(person))


async def test_a_clan_nobody_plays_in_is_dissolved(sim, clock):
    _hall, alice, bob, _cass, ravens = await _gang(sim)
    sim.account("alice", alice).db.last_login = clock.t + clan_clock.day_seconds()
    _offline(sim, alice, bob)
    clock.days(2160.5)                   # Bob is past it; Alice's login a day later is not
    await upkeep()
    assert find_clan("Ravens") is ravens
    clock.days(1)
    await upkeep()
    assert find_clan("Ravens") is None
    assert clan_of(alice) is None and not alice.db.get("clans")


async def test_absent_leaders_are_overthrown(sim, clock):
    _hall, alice, bob, cass, ravens = await _gang(sim)
    await sim.do(cass, "clan apply Ravens")
    await sim.do(alice, "clan accept Cass")
    await sim.do(alice, "clan assign Cass = treasurer")
    _offline(sim, alice)
    clock.days(951)
    await upkeep()
    assert position_of(ravens, alice).id == "boss"
    clock.days(2)
    await upkeep()
    # The highest-ranking member who has played lately: Cass (treasurer)
    # outranks Bob (member).
    assert position_of(ravens, cass).id == "boss"
    assert position_of(ravens, alice).id == "member"
    assert "turns to Cass" in "\n".join(sim.seen(bob))


async def test_the_upkeep_settings_at_zero_do_nothing(clock):
    s = _sim(CLAN_DEATH_DAYS=0, CLAN_OVERTHROW_DAYS=0)
    await import_pack("clan-governments", s.store)
    try:
        _hall, alice, bob, _cass, ravens = await _gang(s)
        _offline(s, alice, bob)
        clock.days(100000)
        await upkeep()
        assert find_clan("Ravens") is ravens and position_of(ravens, alice).id == "boss"
    finally:
        s.close()


async def test_a_deleted_character_leaves_the_roster(sim):
    _hall, alice, bob, _cass, ravens = await _gang(sim)
    await sim.store.delete(bob)
    assert set(ravens.db.members) == {alice.id, bob.id}       # nothing has read it yet
    out = await _say(sim, alice, "clan who")
    assert "Bob" not in out
    assert set(ravens.db.members) == {alice.id}


async def test_a_vacant_top_position_goes_to_the_longest_serving(sim, clock):
    _hall, alice, bob, cass, ravens = await _gang(sim)
    clock.days(1)
    await sim.do(cass, "clan apply Ravens")
    await sim.do(alice, "clan accept Cass")
    await sim.do(alice, "clan assign Bob = lieutenant")
    await sim.do(alice, "clan assign Cass = lieutenant")
    await sim.do(alice, "clan leave")
    assert position_of(ravens, bob).id == "boss"
    assert position_of(ravens, cass).id == "lieutenant"


async def test_a_leaderless_gang_takes_the_highest_ranked_heir(sim, clock):
    _hall, alice, bob, cass, ravens = await _gang(sim)
    clock.days(1)
    await sim.do(cass, "clan apply Ravens")
    await sim.do(alice, "clan accept Cass")
    await sim.do(alice, "clan leave")               # nobody below the boss but members
    assert position_of(ravens, bob).id == "boss"
    assert "Bob is now Boss." in "\n".join(sim.seen(cass))
    await sim.do(bob, "clan leave")
    await sim.do(cass, "clan leave")
    assert find_clan("Ravens") is None              # the last one out dissolves it


# --- 14.7 talk, who, locks and softcode ----------------------------------------------


async def test_clan_talk_reaches_members_with_the_power(sim):
    _hall, alice, bob, cass, ravens = await _gang(sim)
    await sim.do(cass, "clan apply Ravens")             # an applicant hears nothing
    dan = sim.player("Dan", location=alice.location)
    _drain(sim, alice, bob, cass)
    await sim.do(bob, "ct The hall at dusk.")
    line = "[Ravens] Bob: The hall at dusk."
    assert line in sim.seen(alice) and line in sim.seen(bob)
    assert line not in sim.seen(cass) and line not in sim.seen(dan)
    assert "not in a clan" in await _say(sim, dan, "clantalk hello")
    assert "does not speak" in await _say(sim, cass, "ct hello") \
        or "not in a clan" in await _say(sim, cass, "ct hello")
    assert "The hall at dusk." in await _say(sim, alice, "ct")      # the history
    del sim.world.services["channels"]
    assert "Clan talk is unavailable" in await _say(sim, bob, "ct hi")


async def test_a_softcode_ward_on_the_clan_hears_clan_talk(sim):
    _hall, alice, bob, _cass, ravens = await _gang(sim)
    ravens.db.ON_CLANTALK = "set_attr(me, 'heard', adata('message'))"
    await sim.do(bob, "ct Hello")
    assert ravens.db.get("heard") == "Hello"


async def test_who_shows_the_clan_and_a_public_title(sim):
    _hall, alice, bob, cass, ravens = await _gang(sim)
    out = await _say(sim, cass, "who")
    assert "Alice [Boss of Ravens]" in out
    assert "Bob [Ravens]" in out                         # a member's position is private
    assert "Cass (idle" in out


async def test_doors_locked_by_clan_rank_and_power(sim):
    hall, alice, bob, cass, ravens = await _gang(sim)
    door = sim.obj("door", location=hall, tags=["exit"])
    door.locks["basic"] = "clan(caller) == 'Ravens'"
    assert check_lock(door, "basic", alice) and check_lock(door, "basic", bob)
    assert not check_lock(door, "basic", cass)
    await sim.do(cass, "clan apply Ravens")
    assert not check_lock(door, "basic", cass)           # applied is not in
    door.locks["basic"] = "clan_rank(caller) is not None and clan_rank(caller) <= 1"
    assert check_lock(door, "basic", alice) and not check_lock(door, "basic", bob)
    door.locks["basic"] = "clan_has_power(caller, 'withdraw')"
    assert check_lock(door, "basic", alice) and not check_lock(door, "basic", bob)
    await sim.do(alice, "clan assign Bob = treasurer")
    assert check_lock(door, "basic", bob)


async def test_the_softcode_functions(sim):
    hall, alice, bob, cass, ravens = await _gang(sim)
    code = ("result = [clan(get('Bob')), clan_position(get('Bob')), clan_rank(get('Alice')),"
            " clan_has_power(get('Bob'), 'accept'), clan_level('Ravens'),"
            " [name(m) for m in clan_members('Ravens')], clan(get('Cass')),"
            " clan_level('Nobody')]")
    result, err = await sim.eval(hall, code)
    assert err is None
    assert result == ["Ravens", "member", 0, False, 1, ["Alice", "Bob"], None, None]
    gadget = sim.obj("gadget", location=hall)
    result, err = await sim.eval(gadget, "result = clan_add(get('Cass'), 'Ravens', 'staff')")
    assert err is None and result is True
    assert position_of(ravens, cass).id == "staff"
    result, _err = await sim.eval(gadget, "result = clan_add(get('Cass'), 'Ravens')")
    assert result is False                               # one clan per category
    ravens.db.ON_CLANLEAVE = "set_attr(me, 'gone', adata('reason'))"
    result, _err = await sim.eval(gadget, "result = clan_remove(get('Cass'), 'Ravens')")
    assert result is True and record_of(ravens, cass) is None
    assert ravens.db.get("gone") == "removed"


async def test_a_mortal_object_cannot_add_to_a_clan(sim):
    hall, alice, bob, cass, ravens = await _gang(sim)
    trinket = sim.obj("trinket", location=hall)
    trinket.owner = bob
    _result, err = await sim.eval(trinket, "result = clan_add(get('Cass'), 'Ravens')")
    assert err is not None and "clan_add" in err
    assert record_of(ravens, cass) is None


async def test_join_and_level_events_and_the_government_scripts(sim):
    gov = _government(sim, "Lodge", xp_per_level="10 * level",
                      on_join="add_tag(me, 'joined_' + name(enactor))",
                      on_leave="add_tag(me, 'left_' + name(enactor) + '_' + adata('reason'))")
    _hall, (alice, bob) = _people(sim, "Alice", "Bob")
    await sim.do(alice, "clan found Elks = lodge")
    elks = find_clan("Elks")
    elks.db.ON_CLANJOIN = "set_attr(me, 'last_join', [name(enactor), adata('how')])"
    elks.db.ON_CLANASSIGN = "set_attr(me, 'last_assign', adata('position'))"
    elks.db.ON_CLANLEVEL = "set_attr(me, 'last_level', adata('level'))"
    await sim.do(bob, "clan apply Elks")
    assert elks.db.get("last_join") == ["Bob", "joined"]
    assert gov.has_tag("joined_bob") and gov.has_tag("joined_alice")
    await sim.do(alice, "clan assign Bob = chief")
    assert elks.db.get("last_assign") == "chief"
    root = sim.player("Root", location=alice.location)
    root.add_tag("admin")
    await sim.do(root, "@clan xp Elks = 10")
    assert elks.db.get("last_level") == 2
    await sim.do(bob, "clan leave")
    assert gov.has_tag("left_bob_left")


async def test_admin_set_and_delete(sim):
    _hall, alice, bob, _cass, ravens = await _gang(sim)
    root = sim.player("Root", location=alice.location)
    root.add_tag("admin")
    assert "Ravens/tax = 7" in await _say(sim, root, "@clan set Ravens/tax = 7")
    assert ravens.db.tax == 7
    assert "fields" in await _say(sim, root, "@clan set Ravens/name = Owls")
    assert "Deleted Ravens." in await _say(sim, root, "@clan delete Ravens")
    assert find_clan("Ravens") is None and clan_of(bob) is None
    out = await _say(sim, alice, "@clan delete Owls")
    assert "Deleted" not in out and "There is no clan" not in out


async def test_clan_recall_goes_home_under_recalls_rules(sim):
    hall, alice, bob, _cass, ravens = await _gang(sim)
    await sim.do(alice, "clan home")
    away = sim.room("Far Field")
    bob.location = away
    _drain(sim, bob)
    assert "You recall to Hall." in await _say(sim, bob, "clan recall")
    assert bob.location is hall
    away.add_tag("no_recall")
    bob.location = away
    assert "cannot recall from here" in await _say(sim, bob, "clan recall")


async def test_disband_needs_confirming_and_pays_out(sim):
    _hall, alice, bob, _cass, ravens = await _gang(sim)
    await sim.do(alice, "clan deposit 500")
    assert "Only a clan's leader" in await _say(sim, bob, "clan disband")
    out = await _say(sim, alice, "clan disband")
    assert "To go ahead: clan disband Ravens" in out and find_clan("Ravens") is ravens
    assert "You disband Ravens." in await _say(sim, alice, "clan disband Ravens")
    assert find_clan("Ravens") is None and alice.db.credits == 10000
    assert "Ravens is dissolved" in "\n".join(sim.seen(bob))


# --- Acceptance: every shipped government, who may accept, assign, withdraw ----------

#: (leader, member) -> (accept, assign, withdraw), read off clangovernments.xml.
EXPECTED = {
    "gang": ((CAN, CAN, CAN), (CANNOT, CANNOT, CANNOT)),
    "guild": ((CAN, VOTE, CAN), (CANNOT, CANNOT, CANNOT)),
    "union": ((VOTE, VOTE, CANNOT), (CANNOT, VOTE, CANNOT)),
    "fellowship": ((VOTE, VOTE, CANNOT), (VOTE, VOTE, CANNOT)),
    "anarchy": ((CANNOT, CANNOT, CAN), (CANNOT, CANNOT, CAN)),
    "co-op": ((CAN, CAN, CAN), (CANNOT, CANNOT, CANNOT)),
    "meritocracy": ((CAN, CANNOT, CAN), (CANNOT, CANNOT, CANNOT)),
    "plutocracy": ((CAN, CANNOT, CAN), (CANNOT, CANNOT, CANNOT)),
}


def _classify(out: str, clan) -> str:
    if "cannot" in out:
        return CANNOT
    if "Vote " in out or "being voted on" in out:
        return VOTE
    return CAN


@pytest.mark.parametrize("name", SHIPPED)
async def test_every_shipped_government(sim, name):
    _hall, (alice, bob, cass, dan) = _people(sim, "Alice", "Bob", "Cass", "Dan")
    out = await _say(sim, alice, f"clan found Test = {name}")
    clan = find_clan("Test")
    gov = government(name)
    assert position_of(clan, alice).id == gov.top.id, out
    # Bob joins; where accepting is voted on, the leader's lone vote decides it.
    await sim.do(bob, "clan apply Test")
    if gov.applicant_position is not None:
        await sim.do(alice, "clan accept Bob")
    assert position_of(clan, bob).id == gov.accept_position
    await sim.do(alice, "clan deposit 50")
    await sim.do(dan, "clan apply Test")              # Dan just joins in an anarchy
    await sim.do(cass, "clan apply Test")
    _drain(sim, alice, bob, cass, dan)
    middle = next((p for p in gov.positions if p.id not in gov.top_ids()
                   and p.id != gov.applicant_position), gov.top)
    leader_rights, member_rights = EXPECTED[name]
    for actor, rights, other in ((bob, member_rights, dan), (alice, leader_rights, bob)):
        got = (
            _classify(await _say(sim, actor, "clan accept Cass"), clan),
            _classify(await _say(sim, actor, f"clan assign {other.name} = {middle.id}"),
                      clan),
            _classify(await _say(sim, actor, "clan withdraw 1"), clan),
        )
        assert got == rights, (name, actor.name, got)
        for power, want in zip(("accept", "assign", "withdraw"), rights, strict=True):
            assert clan_clock.authority(clan, actor, power) == want, (name, power)
