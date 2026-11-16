"""
Clans and their members (MUD_PLAN 14.2, 14.4, 14.6), after CoffeeMud.

A clan is an object tagged ``clan`` with no location. It holds ``name``,
``government`` (a ``clan_government_def`` name), ``members`` (character id
to ``{position, joined, donated_xp, donated_gold}``), ``premise``,
``motd``, ``treasury``, ``home`` and ``donate_room`` (room ids), ``tax``
(a percentage), ``xp``, ``level``, ``relations`` (clan name to relation),
``status`` (``pending`` or ``active``), ``founded``, its open ``votes``
and its talk ``history``. A character's ``clans`` maps a category to the
id of its clan there (one clan per category).

An applicant (a member in the government's ``applicant_position``) holds
its place in the category but is not yet in the clan: ``clan()`` in
softcode, ``who`` and the head count leave it out.

Times are wall-clock seconds (``now()``, which tests replace). A game day
is the ``clock`` service's (``HOURS_PER_DAY`` game hours at
``GAME_TIME_RATIO``); without ``clock`` it is one real hour.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from realm.core.events import fire_event
from realm.core.world import find_world, get_world
from realm.gateway.session import is_online
from realm.std.clans.governments import CAN, CANNOT, Government, Position, government

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)

CLAN_TAG = "clan"
CLANS_ATTR = "clans"
PENDING, ACTIVE = "pending", "active"
RELATIONS = ("war", "hostile", "neutral", "friendly", "ally")
JOIN = "clan:on_join"
LEAVE = "clan:on_leave"
ASSIGN = "clan:on_assign"
LEVEL = "clan:on_level"
TALK = "clan:on_talk"


def now() -> float:
    """The wall clock clan times are kept in (tests replace it)."""
    return time.time()


def day_seconds() -> float:
    """Real seconds in one game day: the ``clock`` service's calendar, or
    one hour in a game without ``clock``."""
    world = find_world()
    clock = world.services.get("clock") if world is not None else None
    if clock is None:
        return 3600.0
    calendar = clock.calendar()
    return 3600.0 * float(calendar["hours"]) / max(0.001, float(calendar["ratio"]))


def setting(name: str) -> Any:
    return get_world().setting(name)


_pending: set[asyncio.Task] = set()


def soon(coro: Coroutine) -> None:
    """Run ``coro`` after the current synchronous work (the tax filter is
    synchronous; its promotions and level events fire this way)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        coro.close()
        return
    task = loop.create_task(coro)
    _pending.add(task)
    task.add_done_callback(_pending.discard)


def _level(obj: GameObject) -> int:
    """A character's level; one with none counts as level 1."""
    value = obj.db.get("level")
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 1


# --- finding clans --------------------------------------------------------------


def _store():
    world = find_world()
    return world.store if world is not None else None


def all_clans() -> list[GameObject]:
    store = _store()
    found = store.find_cached(tag=CLAN_TAG) if store is not None else []
    return sorted(found, key=lambda c: c.name.lower())


def find_clan(name: str | None) -> GameObject | None:
    """The clan called ``name`` (any case), else the one it uniquely starts."""
    if not name:
        return None
    want = str(name).strip().lower()
    clans = all_clans()
    for clan in clans:
        if clan.name.lower() == want:
            return clan
    found = [c for c in clans if c.name.lower().startswith(want)]
    return found[0] if len(found) == 1 else None


def clan_by_id(clan_id: Any) -> GameObject | None:
    store = _store()
    clan = store.get_cached(str(clan_id)) if store is not None and clan_id else None
    return clan if clan is not None and clan.has_tag(CLAN_TAG) else None


def government_of(clan: GameObject) -> Government | None:
    return government(clan.db.get("government"))


def is_active(clan: GameObject) -> bool:
    return clan.db.get("status") == ACTIVE


# --- the roster -----------------------------------------------------------------


def members(clan: GameObject) -> dict[str, dict]:
    """Character id to member record. A member id that no longer resolves
    to a character is dropped here, so deleting a character needs no call
    into ``clans`` (MUD_PLAN 14.6)."""
    raw = clan.db.get("members") or {}
    store = _store()
    kept = {}
    for member_id, record in raw.items():
        obj = store.get_cached(str(member_id)) if store is not None else None
        if obj is not None and obj.is_player:
            kept[member_id] = dict(record)
    if len(kept) != len(raw):
        clan.db.members = kept
    return kept


def _set_members(clan: GameObject, roster: dict[str, dict]) -> None:
    clan.db.members = roster


def roster(clan: GameObject) -> list[tuple[GameObject, dict]]:
    """``(character, record)`` for every member, highest rank first, then
    longest-serving."""
    store = _store()
    gov = government_of(clan)
    rank = {p.id: p.rank for p in gov.positions} if gov is not None else {}
    out = [(store.get_cached(mid), rec) for mid, rec in members(clan).items()]
    out.sort(key=lambda pair: (rank.get(pair[1].get("position"), 99),
                               float(pair[1].get("joined") or 0)))
    return out


def record_of(clan: GameObject, obj: GameObject) -> dict | None:
    return members(clan).get(obj.id)


def is_applicant(clan: GameObject, obj: GameObject) -> bool:
    gov = government_of(clan)
    rec = record_of(clan, obj)
    return (rec is not None and gov is not None and gov.applicant_position is not None
            and rec.get("position") == gov.applicant_position)


def is_member(clan: GameObject, obj: GameObject) -> bool:
    """In the clan, past any applicant position."""
    return record_of(clan, obj) is not None and not is_applicant(clan, obj)


def full_members(clan: GameObject) -> list[tuple[GameObject, dict]]:
    gov = government_of(clan)
    applicant = gov.applicant_position if gov is not None else None
    return [(o, r) for o, r in roster(clan) if r.get("position") != applicant]


def size(clan: GameObject) -> int:
    return len(full_members(clan))


def clans_of(obj: GameObject | None) -> list[GameObject]:
    """Every clan ``obj`` is in (or has applied to), one per category,
    the default category first."""
    if obj is None:
        return []
    held = obj.db.get(CLANS_ATTR) or {}
    out = []
    for category in sorted(held, key=lambda c: (c != "", c)):
        clan = clan_by_id(held[category])
        if clan is not None and record_of(clan, obj) is not None:
            out.append(clan)
    return out


def clan_of(obj: GameObject | None, category: str = "") -> GameObject | None:
    """The clan ``obj`` is a member of in ``category`` (not one it has only
    applied to), or None."""
    if obj is None:
        return None
    held = obj.db.get(CLANS_ATTR) or {}
    clan = clan_by_id(held.get(str(category or "").lower()))
    return clan if clan is not None and is_member(clan, obj) else None


def position_of(clan: GameObject, obj: GameObject) -> Position | None:
    rec = record_of(clan, obj)
    gov = government_of(clan)
    return gov.position(rec.get("position")) if rec is not None and gov is not None else None


def authority(clan: GameObject, obj: GameObject, power: str) -> str:
    rec = record_of(clan, obj)
    gov = government_of(clan)
    if rec is None or gov is None:
        return CANNOT
    return gov.authority(rec.get("position"), power)


def has_power(clan: GameObject, obj: GameObject, power: str) -> bool:
    return authority(clan, obj, power) == CAN


def holders(clan: GameObject, position_id: str) -> list[GameObject]:
    return [o for o, r in roster(clan) if r.get("position") == position_id]


def qualifies(clan: GameObject, obj: GameObject, position: Position) -> bool:
    """Does ``obj`` pass ``position``'s lock?"""
    if not position.lock:
        return True
    from realm.permissions.locks import LockEvaluator
    return LockEvaluator().evaluate(position.lock, obj, clan)


def full(clan: GameObject, position: Position, *, ignoring: GameObject | None = None) -> bool:
    """Is ``position`` at its limit (not counting ``ignoring``)?"""
    limit = position.limit(size(clan))
    if limit is None:
        return False
    return len([o for o in holders(clan, position.id) if o is not ignoring]) >= limit


def tell_clan(clan: GameObject, text: str) -> None:
    """Announce on clan talk: every member whose position has ``channel``
    hears it, and it joins the clan's talk history."""
    line = f"[{clan.name}] {text}"
    from realm.std.clans.talk import remember
    remember(clan, line)
    for obj, _rec in full_members(clan):
        if has_power(clan, obj, "channel"):
            obj.msg(line)


# --- joining, leaving, positions ------------------------------------------------


def _write_member(clan: GameObject, obj: GameObject, position_id: str) -> str | None:
    """Put ``obj`` in ``position_id``; returns the position it held."""
    roster_ = members(clan)
    rec = roster_.get(obj.id)
    previous = rec.get("position") if rec is not None else None
    if rec is None:
        rec = {"position": position_id, "joined": now(), "donated_xp": 0, "donated_gold": 0}
        gov = government_of(clan)
        held = dict(obj.db.get(CLANS_ATTR) or {})
        held[gov.category if gov is not None else ""] = clan.id
        obj.db.clans = held
    rec["position"] = position_id
    roster_[obj.id] = rec
    _set_members(clan, roster_)
    return previous


def _forget(clan: GameObject, obj: GameObject) -> None:
    roster_ = members(clan)
    roster_.pop(obj.id, None)
    _set_members(clan, roster_)
    held = {k: v for k, v in (obj.db.get(CLANS_ATTR) or {}).items() if v != clan.id}
    if held:
        obj.db.clans = held
    else:
        obj.db.delete(CLANS_ATTR)


async def _run_government_script(clan: GameObject, obj: GameObject, which: str,
                                 action) -> None:
    gov = government_of(clan)
    code = None if gov is None else gov.on_join if which == "on_join" else gov.on_leave
    world = get_world()
    store = world.store
    gov_obj = store.get_cached(gov.obj_id) if gov is not None and store is not None else None
    if code and gov_obj is not None and world.scripts is not None:
        await world.scripts.run_behavior_script(gov_obj, str(code), action=action,
                                                enactor=obj)


async def add_member(clan: GameObject, obj: GameObject, position_id: str, *,
                     how: str) -> None:
    """``obj`` joins (or applies to) ``clan`` in ``position_id``: unless
    it only applied, the ``clan:on_join`` event (hook ``CLANJOIN``) and the
    government's ``on_join`` run; benefits apply, and a clan that now has
    enough members becomes active."""
    _write_member(clan, obj, position_id)
    _refresh(obj)
    if not is_applicant(clan, obj):
        await fire_join(clan, obj, position_id, how)
    activate_if_ready(clan)


async def fire_join(clan: GameObject, obj: GameObject, position_id: str, how: str) -> None:
    action = await fire_event(obj, clan, "clan:on_join",
                              extra={"clan": clan.name, "position": position_id, "how": how})
    await _run_government_script(clan, obj, "on_join", action)


def activate_if_ready(clan: GameObject) -> None:
    if clan.db.get("status") == PENDING and size(clan) >= int(setting("CLAN_MIN_MEMBERS") or 0):
        clan.db.status = ACTIVE
        tell_clan(clan, f"{clan.name} now has enough members and is fully founded.")


async def remove_member(clan: GameObject, obj: GameObject, *, reason: str) -> None:
    """``obj`` leaves ``clan`` (``reason``: left, exiled, rejected,
    removed, dissolved): ``clan:on_leave`` (hook ``CLANLEAVE``) and the
    government's ``on_leave`` run, benefits go, a vacant top position is
    filled, and a clan left empty is dissolved."""
    if record_of(clan, obj) is None:
        return
    joined = is_member(clan, obj)
    _forget(clan, obj)
    _refresh(obj)
    if joined:                                  # an applicant never joined
        action = await fire_event(obj, clan, "clan:on_leave",
                                  extra={"clan": clan.name, "reason": reason})
        await _run_government_script(clan, obj, "on_leave", action)
    if reason == "dissolved":
        return
    if not members(clan):
        await dissolve(clan, "it has no members left")
        return
    await promote(clan)


def set_position(clan: GameObject, obj: GameObject, position_id: str) -> str | None:
    """Move a member to ``position_id`` (no checks, no event); returns the
    position it held. ``fire_assign`` announces it."""
    previous = _write_member(clan, obj, position_id)
    _refresh(obj)
    return previous


async def fire_assign(clan: GameObject, obj: GameObject, position_id: str,
                      previous: str | None, how: str) -> None:
    await fire_event(obj, clan, "clan:on_assign",
                     extra={"clan": clan.name, "position": position_id,
                            "previous": previous, "how": how})


async def assign(clan: GameObject, obj: GameObject, position_id: str, *, how: str) -> None:
    previous = set_position(clan, obj, position_id)
    await fire_assign(clan, obj, position_id, previous, how)
    activate_if_ready(clan)


def _refresh(obj: GameObject) -> None:
    from realm.std.clans.benefits import refresh
    refresh(obj)


def refresh_members(clan: GameObject) -> None:
    for obj, _rec in roster(clan):
        _refresh(obj)


# --- founding and dissolving ----------------------------------------------------


def name_refusal(name: str) -> str | None:
    name = name.strip()
    if not name:
        return "Name the clan."
    if len(name) > 30 or not all(ch.isalnum() or ch in " '-" for ch in name):
        return "A clan name is up to 30 letters, digits, spaces, hyphens and apostrophes."
    taken = next((c for c in all_clans() if c.name.lower() == name.lower()), None)
    if taken is not None:
        return f"There is already a clan called {taken.name}."
    return None


async def found(name: str, gov: Government, leader: GameObject, *,
                how: str = "founded") -> GameObject:
    """Make clan ``name`` under ``gov`` with ``leader`` in its top
    position. It is ``pending`` until it has ``CLAN_MIN_MEMBERS``
    members."""
    from realm.core.objects import GameObject
    clan = GameObject(name=name.strip(), tags=[CLAN_TAG], location=None)
    store = get_world().store
    store.register(clan)
    clan.db.government = gov.name
    clan.db.members = {}
    clan.db.premise = ""
    clan.db.motd = ""
    clan.db.treasury = 0
    clan.db.tax = 0
    clan.db.xp = 0
    clan.db.level = 1
    clan.db.relations = {}
    clan.db.founded = now()
    _write_member(clan, leader, gov.top.id)
    clan.db.status = ACTIVE if size(clan) >= int(setting("CLAN_MIN_MEMBERS") or 0) \
        else PENDING
    _refresh(leader)
    await fire_join(clan, leader, gov.top.id, how)
    await store.save(clan)
    return clan


async def dissolve(clan: GameObject, reason: str) -> None:
    """Dissolve ``clan``: every member leaves (``clan:on_leave`` with
    reason ``dissolved``), other clans' relations toward it are dropped,
    and the clan object is deleted. Its treasury is lost (``disband``
    pays it out first)."""
    for obj, _rec in roster(clan):
        obj.msg(f"{clan.name} is dissolved: {reason}.")
    logger.info(f"Clan {clan.name} ({clan.id}) dissolved: {reason}")
    for obj, _rec in roster(clan):
        await remove_member(clan, obj, reason="dissolved")
    for other in all_clans():
        relations = dict(other.db.get("relations") or {})
        if relations.pop(clan.name, None) is not None:
            other.db.relations = relations
    await get_world().store.delete(clan)


# --- experience, levels and promotion -------------------------------------------


def next_level_xp(clan: GameObject) -> int | None:
    """The clan experience at which ``clan`` reaches its next level, or
    None when its government's rule fails (logged)."""
    gov = government_of(clan)
    if gov is None:
        return None
    from realm.core.safe_eval import eval_expression
    from realm.scripting.namespace import build_namespace
    level = int(clan.db.get("level") or 1)
    namespace, _frame = build_namespace('rule', executor=clan, enactor=clan, location=None,
                                        subject=clan, extra={"level": level})
    try:
        return int(eval_expression(gov.xp_per_level, namespace))
    except Exception as exc:
        logger.warning(f"clan government {gov.name!r}: xp_per_level {gov.xp_per_level!r} "
                       f"failed at level {level} ({exc}); fix the definition")
        return None


def add_xp(clan: GameObject, amount: int, member: GameObject | None = None) -> list[int]:
    """Add clan experience (credited to ``member``'s ``donated_xp``); the
    levels reached are returned (members are told; the caller fires
    ``clan:on_level``). Experience is cumulative, as in CoffeeMud: a clan
    of level ``n`` rises when its total reaches ``xp_per_level`` of ``n``."""
    amount = int(amount)
    if amount <= 0:
        return []
    clan.db.xp = int(clan.db.get("xp") or 0) + amount
    if member is not None:
        roster_ = members(clan)
        rec = roster_.get(member.id)
        if rec is not None:
            rec["donated_xp"] = int(rec.get("donated_xp") or 0) + amount
            _set_members(clan, roster_)
    reached = []
    for _ in range(1000):
        need = next_level_xp(clan)
        if need is None or int(clan.db.xp) < need:
            break
        clan.db.level = int(clan.db.get("level") or 1) + 1
        reached.append(int(clan.db.level))
        tell_clan(clan, f"{clan.name} has reached clan level {clan.db.level}!")
    if reached:
        refresh_members(clan)
    return reached


async def fire_levels(clan: GameObject, levels: list[int]) -> None:
    for level in levels:
        await fire_event(None, clan, "clan:on_level", extra={"clan": clan.name, "level": level})


def _metric(gov: Government, obj: GameObject, rec: dict) -> float:
    if gov.auto_promote == "level":
        return _level(obj)
    if gov.auto_promote == "xp":
        return float(rec.get("donated_xp") or 0)
    return float(rec.get("donated_gold") or 0)


def promotions(clan: GameObject) -> list[tuple[GameObject, str, str | None]]:
    """Fill or contest the top position by the government's
    ``auto_promote`` (no events: ``promote`` fires them). ``rank`` fills a
    vacant top rank with the longest-serving member of the next rank down;
    ``level``, ``xp`` and ``gold`` give the first position to whoever
    leads by that measure, displacing a holder who is passed (to the
    accept position). Returns ``(member, new position, old position)``.
    (The "next rank down" is the highest rank anyone below the top
    holds, so a gang of a boss and members still finds an heir.)"""
    gov = government_of(clan)
    if gov is None or gov.auto_promote == "none":
        return []
    top = gov.top
    top_ids = gov.top_ids()
    full_roster = full_members(clan)
    changes: list[tuple[GameObject, str, str | None]] = []
    if gov.auto_promote == "rank":
        if any(r.get("position") in top_ids for _o, r in full_roster):
            return []
        rank = {p.id: p.rank for p in gov.positions}
        able = sorted(((o, r) for o, r in full_roster if qualifies(clan, o, top)),
                      key=lambda p: (rank.get(p[1].get("position"), 99),
                                     float(p[1].get("joined") or 0)))
        if able:
            obj = able[0][0]
            changes.append((obj, top.id, set_position(clan, obj, top.id)))
        return changes
    limit = top.limit(len(full_roster)) or len(full_roster)
    candidates = [(o, r) for o, r in full_roster if qualifies(clan, o, top)]
    candidates.sort(key=lambda p: (-_metric(gov, p[0], p[1]), p[1].get("position") != top.id,
                                   float(p[1].get("joined") or 0)))
    winners = [o for o, r in candidates[:limit] if _metric(gov, o, r) > 0
               or r.get("position") == top.id]
    for obj, rec in full_roster:
        if rec.get("position") == top.id and obj not in winners:
            changes.append((obj, gov.accept_position,
                            set_position(clan, obj, gov.accept_position)))
    for obj in winners:
        if record_of(clan, obj).get("position") != top.id:
            changes.append((obj, top.id, set_position(clan, obj, top.id)))
    return changes


def _announce_promotions(clan: GameObject, changes) -> None:
    gov = government_of(clan)
    for obj, new, _old in changes:
        pos = gov.position(new) if gov is not None else None
        tell_clan(clan, f"{obj.name} is now {pos.name if pos else new}.")


async def promote(clan: GameObject) -> None:
    changes = promotions(clan)
    _announce_promotions(clan, changes)
    for obj, new, old in changes:
        await fire_assign(clan, obj, new, old, "promoted")


def promote_soon(clan: GameObject) -> None:
    """``promote`` from synchronous code (the tax filter)."""
    changes = promotions(clan)
    _announce_promotions(clan, changes)

    async def fire() -> None:
        for obj, new, old in changes:
            await fire_assign(clan, obj, new, old, "promoted")
    if changes:
        soon(fire())


# --- tax ------------------------------------------------------------------------


def tax_filter(player: GameObject, amount: int) -> int:
    """The ``rules`` service's award filter: each clan of ``player`` with
    a tax takes its share of an experience or character-point award, to
    its own experience and the member's ``donated_xp``."""
    if amount <= 1 or not player.is_player:
        return amount
    for clan in clans_of(player):
        rate = int(clan.db.get("tax") or 0)
        if rate <= 0 or not is_member(clan, player):
            continue
        share = round(amount * rate / 100)
        if share <= 0:
            continue
        amount -= share
        player.msg(f"{clan.name} takes {share} as its tax.")
        levels = add_xp(clan, share, player)
        if levels:
            soon(fire_levels(clan, levels))
        gov = government_of(clan)
        if gov is not None and gov.auto_promote == "xp":
            promote_soon(clan)
    return amount


# --- upkeep ---------------------------------------------------------------------


def last_seen(obj: GameObject, rec: dict) -> float:
    """When ``obj`` last played: now while online, else its account's
    ``last_login``, never earlier than joining the clan."""
    if is_online(obj):
        return now()
    seen = float(rec.get("joined") or 0)
    account_id = obj.db.get("account")
    store = _store()
    account = store.get_cached(str(account_id)) if account_id and store is not None else None
    login = account.db.get("last_login") if account is not None else None
    if isinstance(login, (int, float)):
        seen = max(seen, float(login))
    return seen


async def upkeep() -> None:
    """CoffeeMud's clan upkeep: dissolve a clan when fewer than
    ``CLAN_MIN_MEMBERS`` of its members have played within
    ``CLAN_DEATH_DAYS`` game days, and replace top-position holders all
    absent for ``CLAN_OVERTHROW_DAYS`` with the highest-ranking qualifying
    member who has played within that time."""
    death_days = float(setting("CLAN_DEATH_DAYS") or 0)
    overthrow_days = float(setting("CLAN_OVERTHROW_DAYS") or 0)
    minimum = int(setting("CLAN_MIN_MEMBERS") or 0)
    day = day_seconds()
    for clan in all_clans():
        gov = government_of(clan)
        if gov is None:
            continue
        full_roster = full_members(clan)
        if death_days > 0 and minimum > 0:
            recent = [o for o, r in full_roster if now() - last_seen(o, r) <= death_days * day]
            if len(recent) < minimum:
                await dissolve(clan, f"too few members have played in {int(death_days)} "
                                     f"game days")
                continue
        if overthrow_days > 0:
            await _overthrow(clan, gov, full_roster, overthrow_days * day)
        if gov.auto_promote == "level":
            await promote(clan)


async def _overthrow(clan: GameObject, gov: Government, full_roster, window: float) -> None:
    top_ids = gov.top_ids()
    tops = [(o, r) for o, r in full_roster if r.get("position") in top_ids]
    if not tops or any(now() - last_seen(o, r) <= window for o, r in tops):
        return
    rank = {p.id: p.rank for p in gov.positions}
    present = [(o, r) for o, r in full_roster if r.get("position") not in top_ids
               and now() - last_seen(o, r) <= window and qualifies(clan, o, gov.top)]
    if not present:
        return
    present.sort(key=lambda p: (rank.get(p[1].get("position"), 99),
                                float(p[1].get("joined") or 0)))
    heir = present[0][0]
    for obj, _rec in tops:
        previous = set_position(clan, obj, gov.accept_position)
        await fire_assign(clan, obj, gov.accept_position, previous, "overthrown")
    previous = set_position(clan, heir, gov.top.id)
    tell_clan(clan, f"Its leaders long absent, {clan.name} turns to {heir.name}, "
                    f"now {gov.top.name}.")
    await fire_assign(clan, heir, gov.top.id, previous, "overthrow")


__all__ = ["CLAN_TAG", "CLANS_ATTR", "PENDING", "ACTIVE", "RELATIONS", "JOIN", "LEAVE",
           "ASSIGN", "LEVEL", "TALK", "now", "day_seconds", "soon", "all_clans",
           "find_clan", "clan_by_id", "government_of", "is_active", "members", "roster",
           "record_of", "is_applicant", "is_member", "full_members", "size", "clans_of",
           "clan_of", "position_of", "authority", "has_power", "holders", "qualifies",
           "full", "tell_clan", "add_member", "fire_join", "activate_if_ready",
           "remove_member", "set_position", "fire_assign", "assign", "refresh_members",
           "name_refusal", "found", "dissolve", "next_level_xp", "add_xp", "fire_levels",
           "promotions", "promote", "promote_soon", "tax_filter", "last_seen", "upkeep"]
