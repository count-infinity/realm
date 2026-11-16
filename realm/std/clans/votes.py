"""
Clan votes (MUD_PLAN 14.3), after CoffeeMud's ``ClanVote``.

An act no position holds outright is put to a vote, stored on the clan's
``votes``: its number, the power and its arguments, a line describing it,
the proposer, when it opened and closes (``vote_days`` game days later),
and the ballots (voter id to yes or no). The proposer's own yes is counted
when it opens.

The voters are the members whose position holds ``vote_assign`` (for an
assignment) or ``vote_other`` (anything else). A vote passes as soon as
more than half of them have said yes and fails as soon as that cannot
happen; otherwise it is counted when it closes: it passes with more yes
than no if at least ``vote_quorum`` percent of the voters voted. A passed
vote is carried out as if a holder of the power had typed it. Either
outcome is announced on clan talk and to the proposer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.world import get_world
from realm.std.clans import clans as clan_clock
from realm.std.clans.clans import (
    all_clans,
    day_seconds,
    full_members,
    government_of,
    has_power,
    is_member,
    tell_clan,
)

if TYPE_CHECKING:
    from realm.core.objects import GameObject


def open_votes(clan: GameObject) -> list[dict]:
    return [dict(v) for v in (clan.db.get("votes") or [])]


def _save(clan: GameObject, votes: list[dict]) -> None:
    clan.db.votes = votes


def find_vote(clan: GameObject, number: int) -> dict | None:
    return next((v for v in open_votes(clan) if int(v["id"]) == int(number)), None)


def voters(clan: GameObject, power: str) -> list[GameObject]:
    """The members who vote on ``power`` now."""
    gov = government_of(clan)
    if gov is None:
        return []
    needed = gov.vote_power(power)
    out = []
    for obj, rec in full_members(clan):
        pos = gov.position(rec.get("position"))
        if pos is not None and needed in pos.powers:
            out.append(obj)
    return out


def may_vote(clan: GameObject, obj: GameObject, power: str) -> bool:
    return obj in voters(clan, power)


async def open_vote(clan: GameObject, proposer: GameObject, power: str, args: dict,
                    describe: str) -> str:
    """Put an act to the vote. Returns the line for the proposer."""
    gov = government_of(clan)
    votes = open_votes(clan)
    for vote in votes:
        if vote["power"] == power and vote["args"] == args:
            return f"That is already being voted on (vote {vote['id']}: clan votes)."
    number = int(clan.db.get("next_vote") or 1)
    clan.db.next_vote = number + 1
    opened = clan_clock.now()
    vote = {"id": number, "power": power, "args": dict(args), "describe": describe,
            "proposer": proposer.id, "opened": opened,
            "closes": opened + float(gov.vote_days) * day_seconds(),
            "ballots": {proposer.id: True}}
    votes.append(vote)
    _save(clan, votes)
    tell_clan(clan, f"{proposer.name} calls a vote (vote {number}): {describe}. "
                    f"Vote with: clan vote {number} yes|no")
    if await settle(clan, vote):
        return f"Vote {number} ({describe}) was decided at once."
    return f"Vote {number} is open: {describe}."


async def cast(clan: GameObject, voter: GameObject, number: int, yes: bool) -> str:
    vote = find_vote(clan, number)
    if vote is None:
        return f"{clan.name} has no open vote {number}."
    if not may_vote(clan, voter, vote["power"]):
        return f"You have no vote on that in {clan.name}."
    votes = open_votes(clan)
    for held in votes:
        if int(held["id"]) == int(number):
            held["ballots"] = {**held["ballots"], voter.id: bool(yes)}
            vote = held
    _save(clan, votes)
    said = "yes" if yes else "no"
    if await settle(clan, vote):
        return f"You vote {said}; vote {number} is decided."
    return f"You vote {said} on vote {number}."


async def withdraw(clan: GameObject, who: GameObject, number: int) -> str:
    vote = find_vote(clan, number)
    if vote is None:
        return f"{clan.name} has no open vote {number}."
    if vote["proposer"] != who.id:
        return "Only the member who called a vote may withdraw it."
    _save(clan, [v for v in open_votes(clan) if int(v["id"]) != int(number)])
    tell_clan(clan, f"{who.name} withdraws vote {number} ({vote['describe']}).")
    return f"Vote {number} is withdrawn."


def tally(clan: GameObject, vote: dict) -> tuple[int, int, int]:
    """``(yes, no, eligible)``, counting only ballots of current voters."""
    eligible = {o.id for o in voters(clan, vote["power"])}
    ballots = {k: v for k, v in vote["ballots"].items() if k in eligible}
    yes = sum(1 for v in ballots.values() if v)
    return yes, len(ballots) - yes, len(eligible)


def outcome(clan: GameObject, vote: dict, *, closing: bool = False) -> bool | None:
    """True (passed), False (failed) or None (still open)."""
    gov = government_of(clan)
    yes, no, eligible = tally(clan, vote)
    if eligible == 0:
        return False
    if yes * 2 > eligible:
        return True
    if (yes + eligible - yes - no) * 2 <= eligible:
        return False
    if not closing:
        return None
    quorum = gov.vote_quorum if gov is not None else 100
    return (yes + no) * 100 >= quorum * eligible and yes > no


async def settle(clan: GameObject, vote: dict, *, closing: bool = False) -> bool:
    """Decide ``vote`` if it can be decided; True when it was."""
    result = outcome(clan, vote, closing=closing)
    if result is None:
        return False
    _save(clan, [v for v in open_votes(clan) if int(v["id"]) != int(vote["id"])])
    store = get_world().store
    proposer = store.get_cached(str(vote["proposer"]))
    yes, no, _eligible = tally(clan, vote)
    said = "passes" if result else "fails"
    line = f"Vote {vote['id']} ({vote['describe']}) {said}, {yes} to {no}."
    tell_clan(clan, line)
    hears = proposer is not None and is_member(clan, proposer) \
        and has_power(clan, proposer, "channel")
    if proposer is not None and not hears:
        proposer.msg(line)
    if result:
        from realm.std.clans.acts import Refused, perform
        done = await perform(clan, vote["power"], vote["args"], proposer, by_vote=True)
        if isinstance(done, Refused):
            tell_clan(clan, f"Vote {vote['id']} could not be carried out: {done}")
            if proposer is not None and not hears:
                proposer.msg(done)
    return True


async def close_expired() -> None:
    """Count every vote whose time has run out (the reaper)."""
    for clan in all_clans():
        for vote in open_votes(clan):
            if float(vote["closes"]) <= clan_clock.now():
                await settle(clan, vote, closing=True)


__all__ = ["open_votes", "find_vote", "voters", "may_vote", "open_vote", "cast", "withdraw",
           "tally", "outcome", "settle", "close_expired"]
