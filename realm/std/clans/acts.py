"""
The acts a clan power allows (MUD_PLAN 14.2 to 14.5), shared by the
commands and by passed votes.

``act`` decides how a member's request goes: a position that holds the
power does it at once; one that may only vote on it opens a vote
(``votes``); otherwise it is refused, saying whether the government allows
the power at all. ``perform`` carries an act out, checking again what may
have changed while a vote ran. A passed vote performs "as if a holder of
the power had typed it": the rank rule (nobody touches a position at or
above their own unless they hold the top one) applies only to acts typed
directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from realm.core.world import get_world
from realm.std.clans.clans import (
    RELATIONS,
    activate_if_ready,
    assign,
    authority,
    find_clan,
    fire_join,
    full,
    government_of,
    holders,
    is_active,
    is_applicant,
    position_of,
    qualifies,
    record_of,
    remove_member,
    set_position,
    setting,
    tell_clan,
)
from realm.std.clans.governments import CAN, VOTE

if TYPE_CHECKING:
    from realm.core.objects import GameObject

#: How a refusal names each act: "A gang cannot <verb>."
VERBS = {
    "accept": "accept members", "reject": "reject applicants",
    "assign": "assign positions", "exile": "exile members",
    "set_home": "set its home", "set_donate": "set its donation room",
    "premise": "write its premise", "motd_write": "write its message of the day",
    "motd_read": "read its message of the day",
    "withdraw": "withdraw from its treasury", "deposit": "deposit to its treasury",
    "deposit_list": "list its deposits", "tax": "levy a tax",
    "declare": "declare relations", "channel": "use clan talk",
    "list_members": "list its members", "home_privs": "recall to its home",
}


class Refused(str):
    """What ``perform`` returns when the act could not be done (a passed
    vote announces it)."""


def refusal(clan: GameObject, actor: GameObject, power: str) -> str:
    gov = government_of(clan)
    verb = VERBS.get(power, power)
    if gov is not None and not gov.usable(power):
        return f"A {gov.name} cannot {verb}: no position holds that power or votes on it."
    pos = position_of(clan, actor)
    named = pos.name if pos is not None else "member"
    return f"As {named} of {clan.name} you cannot {verb}."


def _obj(obj_id: Any) -> GameObject | None:
    store = get_world().store
    return store.get_cached(str(obj_id)) if obj_id else None


def _outranks(clan: GameObject, actor: GameObject | None, rank: int) -> bool:
    """May ``actor`` touch a position of ``rank``? Only one above it, or a
    holder of the top position."""
    gov = government_of(clan)
    pos = position_of(clan, actor) if actor is not None else None
    if pos is None or gov is None:
        return False
    return pos.id in gov.top_ids() or pos.rank < rank


async def act(clan: GameObject, actor: GameObject, power: str, args: dict,
              describe: str) -> str:
    """Do ``power`` in ``clan`` for ``actor``, open a vote on it, or say
    why not. Returns the line for ``actor``."""
    how = authority(clan, actor, power)
    if how == CAN:
        return await perform(clan, power, args, actor)
    if how == VOTE:
        from realm.std.clans.votes import open_vote
        return await open_vote(clan, actor, power, args, describe)
    return refusal(clan, actor, power)


async def perform(clan: GameObject, power: str, args: dict, actor: GameObject | None, *,
                  by_vote: bool = False) -> str:
    """Carry out ``power`` with ``args``. Returns what happened, or why
    it could not."""
    handler = _HANDLERS[power]
    return await handler(clan, args, actor, by_vote)


async def _accept(clan, args, actor, by_vote) -> str:
    gov = government_of(clan)
    who = _obj(args.get("member"))
    if who is None or not is_applicant(clan, who):
        return Refused("There is no such applicant.")
    pos = gov.position(gov.accept_position)
    if full(clan, pos):
        return Refused(f"{clan.name} has no room for another {pos.name}.")
    set_position(clan, who, pos.id)
    tell_clan(clan, f"{who.name} is accepted into {clan.name} as {pos.name}.")
    who.msg(f"You are accepted into {clan.name} as {pos.name}.")
    await fire_join(clan, who, pos.id, "accepted")
    activate_if_ready(clan)
    return f"{who.name} is accepted."


async def _reject(clan, args, actor, by_vote) -> str:
    who = _obj(args.get("member"))
    if who is None or not is_applicant(clan, who):
        return Refused("There is no such applicant.")
    await remove_member(clan, who, reason="rejected")
    who.msg(f"Your application to {clan.name} is rejected.")
    return f"{who.name}'s application is rejected."


async def _assign(clan, args, actor, by_vote) -> str:
    gov = government_of(clan)
    who = _obj(args.get("member"))
    pos = gov.position(args.get("position"))
    if who is None or record_of(clan, who) is None:
        return Refused("There is no such member.")
    if is_applicant(clan, who):
        return Refused(f"{who.name} has only applied; accept them first.")
    if pos is None or pos.id == gov.applicant_position:
        return Refused("There is no such position.")
    current = position_of(clan, who)
    if current is not None and current.id == pos.id:
        return Refused(f"{who.name} is already {pos.name}.")
    if not by_vote and not (_outranks(clan, actor, pos.rank)
                            and _outranks(clan, actor, current.rank)):
        return Refused("You may only assign members below your rank to positions below your own.")
    if not qualifies(clan, who, pos):
        return Refused(f"{who.name} may not be {pos.name}.")
    top = gov.top_ids()
    if current.id in top and pos.id not in top and not [
            o for p in top for o in holders(clan, p) if o is not who]:
        return Refused(f"{who.name} is the last {current.name} and must be replaced first.")
    if full(clan, pos, ignoring=who):
        if pos.id not in top:
            return Refused(f"The position of {pos.name} is full.")
        # The top position changes hands (CoffeeMud): the longest holder
        # steps down to the accept position.
        displaced = sorted(holders(clan, pos.id),
                           key=lambda o: float(record_of(clan, o).get("joined") or 0))[0]
        await assign(clan, displaced, gov.accept_position, how="displaced")
        accept = gov.position(gov.accept_position)
        tell_clan(clan, f"{displaced.name} steps down to {accept.name}.")
    await assign(clan, who, pos.id, how="voted" if by_vote else "assigned")
    tell_clan(clan, f"{who.name} is now {pos.name}.")
    who.msg(f"You are now {pos.name} of {clan.name}.")
    return f"{who.name} is now {pos.name}."


async def _exile(clan, args, actor, by_vote) -> str:
    who = _obj(args.get("member"))
    if who is None or record_of(clan, who) is None:
        return Refused("There is no such member.")
    if who is actor:
        return Refused("Leave instead: clan leave.")
    current = position_of(clan, who)
    if not by_vote and not _outranks(clan, actor, current.rank):
        return Refused(f"You may not exile {who.name}: they do not rank below you.")
    await remove_member(clan, who, reason="exiled")
    tell_clan(clan, f"{who.name} is exiled from {clan.name}.")
    who.msg(f"You are exiled from {clan.name}.")
    return f"{who.name} is exiled."


async def _set_room(clan, args, attr, label) -> str:
    room = _obj(args.get("room"))
    if room is None:
        return Refused("That place is gone.")
    clan.db.set(attr, room.id)
    tell_clan(clan, f"{room.name} is now the {label} of {clan.name}.")
    return f"{room.name} is now the {label} of {clan.name}."


async def _set_home(clan, args, actor, by_vote) -> str:
    return await _set_room(clan, args, "home", "home")


async def _set_donate(clan, args, actor, by_vote) -> str:
    return await _set_room(clan, args, "donate_room", "donation room")


async def _premise(clan, args, actor, by_vote) -> str:
    clan.db.premise = str(args.get("text") or "")
    tell_clan(clan, f"{clan.name} has a new premise.")
    return "The premise is set."


async def _motd(clan, args, actor, by_vote) -> str:
    clan.db.motd = str(args.get("text") or "")
    tell_clan(clan, f"{clan.name} has a new message of the day.")
    return "The message of the day is set."


async def _withdraw(clan, args, actor, by_vote) -> str:
    economy = get_world().services.get("economy")
    amount = int(args.get("amount") or 0)
    if economy is None:
        return Refused(f"The treasury of {clan.name} is unavailable here.")
    if actor is None or record_of(clan, actor) is None:
        return Refused("Nobody is left to take the money.")
    treasury = int(clan.db.get("treasury") or 0)
    if amount <= 0 or amount > treasury:
        return Refused(f"The treasury holds only {treasury} {economy.currency_name()}.")
    clan.db.treasury = treasury - amount
    economy.adjust_credits(actor, amount)
    money = economy.currency_name()
    tell_clan(clan, f"{actor.name} withdraws {amount} {money} from the treasury.")
    return f"You withdraw {amount} {money}; the treasury holds {clan.db.treasury}."


async def _tax(clan, args, actor, by_vote) -> str:
    percent = int(args.get("percent") or 0)
    ceiling = int(setting("CLAN_MAX_TAX") or 0)
    if not is_active(clan):
        return Refused(f"{clan.name} is not yet fully founded and may not levy a tax.")
    if not 0 <= percent <= ceiling:
        return Refused(f"A tax runs from 0 to {ceiling} percent.")
    clan.db.tax = percent
    tell_clan(clan, f"{clan.name} now taxes {percent}% of its members' experience.")
    return f"The tax is now {percent}%."


async def _declare(clan, args, actor, by_vote) -> str:
    gov = government_of(clan)
    other = find_clan(args.get("clan"))
    relation = str(args.get("relation") or "")
    if other is None or other is clan:
        return Refused("There is no such other clan.")
    other_gov = government_of(other)
    if relation not in RELATIONS:
        return Refused(f"Declare one of: {', '.join(RELATIONS)}.")
    if not is_active(clan) or not is_active(other):
        return Refused("Both clans must be fully founded to declare relations.")
    if not gov.rivalrous or other_gov is None or not other_gov.rivalrous:
        return Refused("Only clans whose governments are rivalrous declare relations.")
    relations = dict(clan.db.get("relations") or {})
    if relation == "neutral":
        relations.pop(other.name, None)
    else:
        relations[other.name] = relation
    clan.db.relations = relations
    tell_clan(clan, f"{clan.name} declares {relation} toward {other.name}.")
    tell_clan(other, f"{clan.name} declares {relation} toward {other.name}.")
    return f"{clan.name} declares {relation} toward {other.name}."


_HANDLERS = {
    "accept": _accept, "reject": _reject, "assign": _assign, "exile": _exile,
    "set_home": _set_home, "set_donate": _set_donate, "premise": _premise,
    "motd_write": _motd, "withdraw": _withdraw, "tax": _tax, "declare": _declare,
}


def relation(clan: GameObject, other: GameObject) -> str:
    """``clan``'s declared relation toward ``other`` (``neutral`` when
    none)."""
    return str((clan.db.get("relations") or {}).get(other.name) or "neutral")


__all__ = ["VERBS", "Refused", "refusal", "act", "perform", "relation"]
