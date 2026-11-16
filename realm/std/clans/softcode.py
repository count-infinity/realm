"""
Softcode functions: clans (MUD_PLAN 14.5, 14.7).

The read-only ones are also there in lock expressions, where the one
trying is ``caller``: a hall door is ``@lock door = clan(caller) ==
'Ravens'``, an armory ``clan_has_power(caller, 'home_privs')``. ``clan_add`` and
``clan_remove`` are for builders (the HARM entitlement); they act after
the script, when ``CLANJOIN`` and ``CLANLEAVE`` fire.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.std.clans.acts import relation
from realm.std.clans.clans import (
    clan_of,
    clans_of,
    find_clan,
    full_members,
    government_of,
    has_power,
    position_of,
    record_of,
)

if TYPE_CHECKING:
    from realm.core.objects import GameObject


def clan(frame, obj: GameObject | str | None, category: str = '') -> str | None:
    """The name of the clan ``obj`` belongs to (in ``category``; one who
    has only applied is not in it yet), or None.

    Example: clan(enactor) == 'Ravens'
    """
    target = frame.resolve(obj)
    found = clan_of(target, category) if target is not None else None
    return found.name if found is not None else None


def clan_position(frame, obj: GameObject | str | None, category: str = '') -> str | None:
    """The id of ``obj``'s position in its clan (``boss``, ``member``), or
    None.

    Example: clan_position(enactor) == 'treasurer'
    """
    target = frame.resolve(obj)
    found = clan_of(target, category) if target is not None else None
    pos = position_of(found, target) if found is not None else None
    return pos.id if pos is not None else None


def clan_rank(frame, obj: GameObject | str | None, category: str = '') -> int | None:
    """The rank of ``obj``'s position in its clan, 0 the highest; None
    outside a clan.

    Example: clan_rank(enactor) is not None and clan_rank(enactor) <= 1
    """
    target = frame.resolve(obj)
    found = clan_of(target, category) if target is not None else None
    pos = position_of(found, target) if found is not None else None
    return pos.rank if pos is not None else None


def clan_has_power(frame, obj: GameObject | str | None, power: str,
                   category: str = '') -> bool:
    """Does ``obj``'s position in its clan hold ``power`` outright (not
    merely vote on it)?

    Example: clan_has_power(enactor, 'home_privs')
    """
    target = frame.resolve(obj)
    found = clan_of(target, category) if target is not None else None
    return found is not None and has_power(found, target, str(power).lower())


def clan_level(frame, name: str) -> int | None:
    """A clan's level, or None when there is no such clan.

    Example: clan_level('Ravens') >= 3
    """
    found = find_clan(name)
    return int(found.db.get("level") or 1) if found is not None else None


def clan_members(frame, name: str) -> list[GameObject]:
    """A clan's members (not its applicants), highest rank first.

    Example: [name(m) for m in clan_members('Ravens')]
    """
    found = find_clan(name)
    return [o for o, _r in full_members(found)] if found is not None else []


def clan_relation(frame, a: str, b: str) -> str | None:
    """Clan ``a``'s declared relation toward clan ``b``: war, hostile,
    neutral, friendly or ally (None when either is not a clan). One-sided:
    an alliance holds only when both say ally.

    Example: clan_relation(clan(enactor), 'Smiths') == 'war'
    """
    one, two = find_clan(a), find_clan(b)
    if one is None or two is None:
        return None
    return relation(one, two)


def clans_at_war(frame, a: str, b: str) -> bool:
    """True when either clan has declared war on the other.

    Example: clans_at_war(clan(enactor), clan(target))
    """
    one, two = find_clan(a), find_clan(b)
    if one is None or two is None or one is two:
        return False
    return "war" in (relation(one, two), relation(two, one))


def clan_add(frame, obj: GameObject | str | None, name: str,
             position: str | None = None) -> bool:
    """Put a character in a clan (at ``position``, else the government's
    accept position), as if accepted. False, changing nothing, for a
    non-character, a missing clan or position, or one already in a clan of
    that kind. Builders only; it lands after the script.

    Example: clan_add(enactor, 'Ravens')
    """
    target = frame.resolve(obj)
    found = find_clan(name)
    gov = government_of(found) if found is not None else None
    if target is None or not target.is_player or gov is None:
        return False
    pos = gov.position(position) if position else gov.position(gov.accept_position)
    taken = any(government_of(c) is not None and government_of(c).category == gov.category
                for c in clans_of(target))
    if pos is None or taken or record_of(found, target) is not None:
        return False
    frame.command_queue.append(('clan_add', target, (found.id, pos.id)))
    return True


def clan_remove(frame, obj: GameObject | str | None, name: str) -> bool:
    """Take a character out of a clan (``CLANLEAVE`` fires, reason
    ``removed``). Builders only; it lands after the script.

    Example: clan_remove(enactor, 'Ravens')
    """
    target = frame.resolve(obj)
    found = find_clan(name)
    if target is None or found is None or record_of(found, target) is None:
        return False
    frame.command_queue.append(('clan_remove', target, found.id))
    return True


async def queued_add(engine, frame, target, payload) -> None:
    """Queued by softcode ``clan_add()``."""
    from realm.std.clans.clans import add_member, clan_by_id
    clan_id, position_id = payload
    found = clan_by_id(clan_id)
    if found is not None and record_of(found, target) is None:
        await add_member(found, target, position_id, how="added")


async def queued_remove(engine, frame, target, clan_id) -> None:
    """Queued by softcode ``clan_remove()``."""
    from realm.std.clans.clans import clan_by_id, remove_member
    found = clan_by_id(clan_id)
    if found is not None:
        await remove_member(found, target, reason="removed")


__all__ = ["clan", "clan_position", "clan_rank", "clan_has_power", "clan_level",
           "clan_members", "clan_relation", "clans_at_war", "clan_add", "clan_remove",
           "queued_add", "queued_remove"]
