"""
Quest tracking (MUD_PLAN 15.2, 15.3).

A character's progress lives in two attributes: ``quests``, ``{quest:
{"stage", "counts", "accepted", "deadline"}}`` (``stage`` is 1-based, or
``"ready"`` once the last stage is met and the quest waits to be handed
in), and ``quests_done``, ``{quest: timestamp}``. For a quest of scope
``account`` the second lives on the account, so it is done once for
every character on it.

One observer (``quest_observer``) turns what happens into progress:
``combat:on_death`` for ``kill`` (the killer's, its master's when it is a
companion, and the party's in the room), ``item:on_get`` and
``item:on_give`` for ``collect`` and ``deliver``, ``event:on_enter`` for
``visit``, ``quest:on_talk`` for ``talk`` and ``item:on_use`` for
``use``. An index of which online characters have an active objective of
each kind lets it return at once for an action nobody is waiting on.

Times are wall-clock (``now()``, which tests replace).
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from realm.core.action_types import ActionType
from realm.core.events import fire_event
from realm.core.world import find_world, get_world
from realm.std.quests.definitions import Quest, find_prototype

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action
    from realm.std.quests.definitions import Objective

logger = logging.getLogger(__name__)

QUESTS_ATTR = "quests"
DONE_ATTR = "quests_done"
READY = "ready"
DONE = "done"
ACCEPT = "quest:on_accept"
ADVANCE = "quest:on_advance"
COMPLETE = "quest:on_complete"
FAIL = "quest:on_fail"
TALK = "quest:on_talk"

#: The action types the observer reads, and the objective kinds each feeds.
WATCHED = {
    "combat:on_death": ("kill",),
    "item:on_get": ("collect",),
    "item:on_give": ("collect", "deliver"),
    ActionType.ON_ENTER: ("visit",),
    TALK: ("talk",),
    "item:on_use": ("use",),
}


def now() -> float:
    """The wall clock quest times are kept in (tests replace it)."""
    return time.time()


# --- definitions -------------------------------------------------------------------


def definitions() -> dict[str, Quest]:
    from realm.core.defs import all_defs
    return all_defs("quest")


def find_quest(name: str | None) -> Quest | None:
    """A quest by name (any case), else a unique prefix."""
    from realm.core.defs import find_def
    return find_def("quest", str(name or ""))


def quest_object(quest: Quest) -> GameObject | None:
    store = get_world().store
    return store.get_cached(quest.obj_id) if store is not None else None


# --- records -------------------------------------------------------------------


def records(player: GameObject) -> dict[str, dict]:
    """A copy of ``player``'s active quests (write back with ``_write``)."""
    held = player.db.get(QUESTS_ATTR)
    return {k: dict(v) for k, v in held.items()} if isinstance(held, dict) else {}


def record(player: GameObject, quest: Quest) -> dict | None:
    return records(player).get(quest.key)


def _write(player: GameObject, held: dict[str, dict]) -> None:
    if held:
        player.db.set(QUESTS_ATTR, held)
    else:
        player.db.delete(QUESTS_ATTR)


def _account(player: GameObject) -> GameObject | None:
    account_id = player.db.get("account")
    store = get_world().store
    found = store.get_cached(str(account_id)) if account_id and store is not None else None
    return found if found is not None and found.has_tag("account") else None


def _done_holder(player: GameObject, quest: Quest) -> GameObject:
    """Where ``quests_done`` is kept for ``quest``: the account for scope
    ``account`` (when the character has one), else the character."""
    if quest.scope == "account":
        return _account(player) or player
    return player


def done_at(player: GameObject, quest: Quest) -> float | None:
    done = _done_holder(player, quest).db.get(DONE_ATTR)
    stamp = done.get(quest.key) if isinstance(done, dict) else None
    return float(stamp) if stamp is not None else None


def history(player: GameObject) -> dict[str, float]:
    """Every quest ``player`` has finished, by key: its own and its
    account's."""
    out: dict[str, float] = {}
    for holder in (_account(player), player):
        done = holder.db.get(DONE_ATTR) if holder is not None else None
        if isinstance(done, dict):
            out.update(done)
    return out


def state(player: GameObject, quest: Quest) -> int | str | None:
    """The current stage number, ``'ready'`` (waiting to be handed in),
    ``'done'``, or None."""
    rec = record(player, quest)
    if rec is not None:
        return rec.get("stage")
    return DONE if done_at(player, quest) is not None else None


def refusal(player: GameObject, quest: Quest) -> str | None:
    """Why ``player`` may not take ``quest`` now, or None."""
    if record(player, quest) is not None:
        return f"You are already on {quest.name}."
    finished = done_at(player, quest)
    if finished is not None:
        if quest.repeatable is None:
            return f"You have already done {quest.name}."
        wait = finished + quest.repeatable - now()
        if wait > 0:
            return f"You may take {quest.name} again in {_duration(wait)}."
    if quest.accept_lock:
        from realm.permissions.locks import LockEvaluator
        definition = quest_object(quest)
        if definition is None or not LockEvaluator().evaluate(quest.accept_lock, player,
                                                              definition):
            return f"{quest.name} is not for you."
    return None


def _duration(seconds: float) -> str:
    seconds = int(seconds + 0.999)
    if seconds < 120:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    if seconds < 7200:
        return f"{seconds // 60} minutes"
    return f"{seconds // 3600} hours"


def time_left(rec: dict) -> float | None:
    deadline = rec.get("deadline")
    return None if deadline is None else float(deadline) - now()


# --- progress --------------------------------------------------------------------


def _carried(player: GameObject) -> list[GameObject]:
    """Everything ``player`` carries, inside containers too."""
    out, stack = [], list(player.contents)
    while stack:
        obj = stack.pop()
        out.append(obj)
        stack.extend(obj.contents)
    return out


def _held(player: GameObject, objective: Objective) -> list[GameObject]:
    return [o for o in _carried(player) if objective.match.matches(o)]


def progress(player: GameObject, quest: Quest, objective: Objective,
             rec: dict | None = None) -> int:
    """How far ``player`` is on ``objective`` of their current stage: a
    ``collect`` counts what they hold now; the rest count what happened."""
    if objective.kind == "collect":
        return min(objective.count, len(_held(player, objective)))
    rec = rec if rec is not None else record(player, quest) or {}
    return int((rec.get("counts") or {}).get(objective.key, 0))


def _stage_met(player: GameObject, quest: Quest, number: int, rec: dict) -> bool:
    stage = quest.stage(number)
    return stage is not None and all(progress(player, quest, o, rec) >= o.count
                                     for o in stage.objectives)


async def _consume(player: GameObject, quest: Quest, number: int) -> None:
    """Take the items of the stage's ``consume`` collect objectives; worn
    gear comes off first (``items``' ``unequip``), so what it granted goes
    with it."""
    stage = quest.stage(number)
    from realm.core.ops.objects import destroy
    world = get_world()
    store, items = world.store, world.services.get("items")
    for objective in (stage.objectives if stage is not None else ()):
        if objective.kind != "collect" or not objective.consume:
            continue
        for item in _held(player, objective)[:objective.count]:
            if items is not None and item.location is player:
                items.unequip(player, item)
            if store is not None:
                await destroy(None, item, store)
            else:
                item.location = None


def missing(player: GameObject, quest: Quest) -> list[Objective]:
    """The objectives of the last stage no longer met (a collected item
    dropped since): checked again at the hand-in."""
    rec = record(player, quest) or {}
    stage = quest.stages[-1]
    return [o for o in stage.objectives if progress(player, quest, o, rec) < o.count]


async def credit(player: GameObject, quest: Quest, key: str, by: int = 1) -> bool:
    """Count ``by`` toward the objective ``key`` of ``player``'s current
    stage of ``quest`` (never past its count), tell them, and move on if
    the stage is met. False when there is nothing to count."""
    held = records(player)
    rec = held.get(quest.key)
    if rec is None or not isinstance(rec.get("stage"), int):
        return False
    stage = quest.stage(rec["stage"])
    objective = next((o for o in (stage.objectives if stage else ()) if o.key == key), None)
    if objective is None:
        return False
    if objective.kind != "collect":
        counts = dict(rec.get("counts") or {})
        before = int(counts.get(key, 0))
        after = max(0, min(objective.count, before + int(by)))
        if after == before:
            return False
        counts[key] = after
        rec["counts"] = counts
        held[quest.key] = rec
        _write(player, held)
        player.msg(f"[{quest.name}] {objective.label()}: {after}/{objective.count}")
    await settle(player, quest)
    return True


async def settle(player: GameObject, quest: Quest) -> None:
    """Move ``player`` through every stage of ``quest`` now met: the next
    stage's text and ``on_stage``; after the last, completion at once
    (no giver) or ready to hand in."""
    while True:
        held = records(player)
        rec = held.get(quest.key)
        if rec is None or not isinstance(rec.get("stage"), int):
            return
        number = rec["stage"]
        if not _stage_met(player, quest, number, rec):
            return
        last = number >= len(quest.stages)
        if last and quest.giver is None:
            await complete(player, quest)
            return
        if not last:
            await _consume(player, quest, number)
        rec["stage"] = READY if last else number + 1
        if not last:                # the hand-in checks the last stage's counts
            rec["counts"] = {}
        held[quest.key] = rec
        _write(player, held)
        reindex(player)
        if last:
            player.msg(f"[{quest.name}] Done. Return to {quest.giver.describe()} "
                       f"(quest complete {quest.name}).")
        else:
            player.msg(f"[{quest.name}] Stage {number + 1}: {quest.stages[number].text}")
        action = await fire_event(player, _definition_target(quest), "quest:on_advance",
                                  extra={"quest": quest.name, "stage": rec["stage"]})
        await _run_script(quest, "on_stage", player, action)
        if last:
            return


# --- accepting, completing, failing --------------------------------------------------


def _definition_target(quest: Quest, giver: GameObject | None = None) -> GameObject | None:
    return giver if giver is not None else quest_object(quest)


async def _run_script(quest: Quest, which: str, player: GameObject, action: Action) -> None:
    code = quest.scripts.get(which)
    world = get_world()
    definition = quest_object(quest)
    if code and definition is not None and world.scripts is not None:
        await world.scripts.run_behavior_script(definition, code, action=action,
                                                enactor=player)


async def accept(player: GameObject, quest: Quest, giver: GameObject | None = None) -> str | None:
    """Start ``quest`` for ``player``; the refusal, or None once begun."""
    reason = refusal(player, quest)
    if reason is not None:
        return reason
    held = records(player)
    stamp = now()
    held[quest.key] = {"stage": 1, "counts": {}, "accepted": stamp,
                       "deadline": stamp + quest.time_limit if quest.time_limit else None}
    _write(player, held)
    reindex(player)
    player.msg(f"Quest accepted: {quest.name}.")
    if quest.description:
        player.msg(quest.description)
    player.msg(f"[{quest.name}] Stage 1: {quest.stages[0].text}")
    if quest.time_limit:
        player.msg(f"You have {_duration(quest.time_limit)} to finish it.")
    action = await fire_event(player, _definition_target(quest, giver), "quest:on_accept",
                              extra={"quest": quest.name})
    await _run_script(quest, "on_accept", player, action)
    await settle(player, quest)
    return None


async def complete(player: GameObject, quest: Quest, giver: GameObject | None = None) -> None:
    """Finish ``quest``: the last stage's items are taken, it is recorded
    as done, the rewards are paid, ``quest:on_complete`` fires and
    ``on_complete`` runs."""
    held = records(player)
    if held.pop(quest.key, None) is None:
        return
    await _consume(player, quest, len(quest.stages))
    _write(player, held)
    holder = _done_holder(player, quest)
    done = holder.db.get(DONE_ATTR)
    done = dict(done) if isinstance(done, dict) else {}
    done[quest.key] = now()
    holder.db.set(DONE_ATTR, done)
    reindex(player)
    player.msg(f"Quest complete: {quest.name}!")
    await pay(player, quest)
    action = await fire_event(player, _definition_target(quest, giver), "quest:on_complete",
                              extra={"quest": quest.name})
    await _run_script(quest, "on_complete", player, action)


async def fail(player: GameObject, quest: Quest, reason: str = "failed") -> bool:
    """End ``quest`` unfinished (``reason``: expired, abandoned or failed):
    ``quest:on_fail`` fires and ``on_fail`` runs. It may be taken again."""
    held = records(player)
    if held.pop(quest.key, None) is None:
        return False
    _write(player, held)
    reindex(player)
    player.msg({"expired": f"You have run out of time: {quest.name} has failed.",
                "abandoned": f"You abandon {quest.name}."}.get(
        reason, f"You have failed {quest.name}."))
    action = await fire_event(player, quest_object(quest), "quest:on_fail",
                              extra={"quest": quest.name, "reason": reason})
    await _run_script(quest, "on_fail", player, action)
    return True


async def pay(player: GameObject, quest: Quest) -> None:
    """The rewards, through what exists: the ``rules`` service's award
    (its filters apply: hunger, clan tax), the ``economy`` service, a
    clone of each item's prototype, the ``achievements`` service, tags. A
    reward whose feature is absent is skipped with a WARNING."""
    world = get_world()
    rewards = quest.rewards

    def absent(what: str, feature: str) -> None:
        logger.warning(f"quest {quest.name!r}: its {what} reward was not paid: the "
                       f"{feature!r} feature is not in this world")

    if rewards.award:
        rules = world.services.get("rules")
        if rules is None:
            absent("award", "rules")
        else:
            rules.award(player, rewards.award)
    if rewards.credits:
        economy = world.services.get("economy")
        if economy is None:
            absent("credits", "economy")
        elif economy.adjust_credits(player, rewards.credits):
            player.msg(f"You receive {rewards.credits} {economy.currency_name()}.")
    for ref in rewards.items:
        proto = find_prototype(ref)
        if proto is None:
            logger.warning(f"quest {quest.name!r}: reward item {ref!r} names no prototype; "
                           f"it was not given")
            continue
        from realm.core.ops.objects import clone
        item = clone(None, proto, location=player).value
        item.remove_tag("prototype")
        if world.store is not None:
            await world.store.save(item)
        player.msg(f"You receive {item.name}.")
    if rewards.achievement:
        achievements = world.services.get("achievements")
        if achievements is None:
            absent("achievement", "achievements")
        else:
            await achievements.grant(player, rewards.achievement)
    for tag in rewards.tags:
        player.add_tag(tag)


# --- the index ---------------------------------------------------------------------

#: objective kind -> ids of online characters with an active objective of
#: that kind in their current stage.
_watch: dict[str, set[str]] = {}
#: id -> character, for every indexed character with a deadline.
_timed: dict[str, GameObject] = {}
#: The definitions the index was built from (``all_defs`` returns a new
#: dict whenever a quest_def changes).
_built: dict[str, Any] = {"defs": None}


def clear_index(_world: Any = None) -> None:
    _watch.clear()
    _timed.clear()
    _built["defs"] = None


def drop(player: GameObject) -> None:
    for ids in _watch.values():
        ids.discard(player.id)
    _timed.pop(player.id, None)


def reindex(player: GameObject) -> None:
    """Index ``player``'s active objectives (call after any change)."""
    drop(player)
    defs = definitions()
    for key, rec in records(player).items():
        quest = defs.get(key)
        if quest is None:
            continue
        if rec.get("deadline") is not None:
            _timed[player.id] = player
        stage = quest.stage(rec["stage"]) if isinstance(rec.get("stage"), int) else None
        for objective in (stage.objectives if stage is not None else ()):
            _watch.setdefault(objective.kind, set()).add(player.id)


def _online() -> list[GameObject]:
    world = find_world()
    sessions = world.sessions if world is not None else None
    if sessions is None:
        return []
    return [s.player for s in sessions.playing_sessions() if s.player is not None]


def _fresh() -> None:
    """Rebuild the index for everyone online when the definitions changed
    (or it was never built)."""
    defs = definitions()
    if _built["defs"] is defs:
        return
    known = {pid for ids in _watch.values() for pid in ids} | set(_timed)
    _watch.clear()
    _timed.clear()
    _built["defs"] = defs
    store = get_world().store
    people = {p.id: p for p in _online()}
    for pid in known:
        found = store.get_cached(pid) if store is not None else None
        if found is not None:
            people.setdefault(pid, found)
    for player in people.values():
        reindex(player)


def rebuild(_world: Any = None) -> None:
    """``feature.on_reload`` and boot: read the definitions now (a
    malformed one is logged, by name, and skipped) and index again."""
    _built["defs"] = None
    definitions()
    _fresh()


def watching(kind: str, player: GameObject) -> bool:
    return player.id in _watch.get(kind, ())


# --- the observer ------------------------------------------------------------------


def _active(player: GameObject, kind: str):
    """(quest, objective) for each objective of ``kind`` in the current
    stage of each of ``player``'s quests."""
    defs = definitions()
    for key, rec in records(player).items():
        quest = defs.get(key)
        if quest is None or not isinstance(rec.get("stage"), int):
            continue
        stage = quest.stage(rec["stage"])
        for objective in (stage.objectives if stage is not None else ()):
            if objective.kind == kind:
                yield quest, objective


async def _count(player: GameObject, kind: str, test) -> None:
    if not watching(kind, player):
        return
    for quest, objective in list(_active(player, kind)):
        if test(objective):
            if objective.kind == "collect":
                held = progress(player, quest, objective)
                player.msg(f"[{quest.name}] {objective.label()}: {held}/{objective.count}")
                await settle(player, quest)
            else:
                await credit(player, quest, objective.key)


def _killers(killer: GameObject | None) -> list[GameObject]:
    """Who a kill counts for: the killer (its master when it is a
    companion) and their party in the room."""
    if killer is None:
        return []
    world = get_world()
    credited = killer
    companions = world.services.get("companions")
    if not killer.is_player and companions is not None:
        credited = companions.master_of(killer) or killer
    if not credited.is_player:
        return []
    social = world.services.get("social")
    party = social.party_members(credited) if social is not None else [credited]
    out = [m for m in party if m.is_player]
    return out if credited in out else [credited, *out]


async def quest_observer(action: Action) -> None:
    kind = action.action_type
    actor, target = action.actor, action.target
    if kind == ActionType.CONNECT and actor is not None:
        _fresh()
        reindex(actor)
        await expire(actor)
        return
    if kind == ActionType.DISCONNECT and actor is not None:
        drop(actor)
        return
    kinds = WATCHED.get(kind)
    if kinds is None or action.blocked:
        return
    _fresh()
    if not any(_watch.get(k) for k in kinds):
        return
    if kind == "combat:on_death":
        for member in _killers(actor):
            await _count(member, "kill", lambda o: o.match.matches(target))
        return
    if actor is None or not actor.is_player:
        if kind == "item:on_give" and target is not None and target.is_player:
            await _count(target, "collect", lambda o: o.match.matches(action.tool))
        return
    if kind == "item:on_get":
        await _count(actor, "collect", lambda o: o.match.matches(target))
    elif kind == "item:on_give":
        item = action.tool
        await _count(actor, "deliver",
                     lambda o: o.match.matches(item) and o.to.matches(target))
        if target is not None and target.is_player:
            await _count(target, "collect", lambda o: o.match.matches(item))
    elif kind == ActionType.ON_ENTER:
        await _count(actor, "visit", lambda o: o.match.matches(target))
    elif kind == TALK:
        await _count(actor, "talk", lambda o: o.match.matches(target))
    elif kind == "item:on_use":
        await _count(actor, "use", lambda o: o.match.matches(target)
                     or o.match.matches(action.tool))


# --- the time limit ----------------------------------------------------------------


async def expire(player: GameObject) -> int:
    """Fail every quest of ``player`` past its deadline."""
    failed = 0
    defs = definitions()
    stamp = now()
    for key, rec in records(player).items():
        deadline = rec.get("deadline")
        quest = defs.get(key)
        if deadline is not None and quest is not None and stamp >= float(deadline):
            failed += await fail(player, quest, "expired")
    return failed


async def expire_all(_store: Any = None) -> int:
    """The reaper: quests past their deadline fail (an offline character's
    when they next log in)."""
    _fresh()
    failed = 0
    for player in list(_timed.values()):
        failed += await expire(player)
    return failed


# --- givers ------------------------------------------------------------------------


def offered_by(npc: GameObject) -> list[Quest]:
    """The quests ``npc`` offers: those its ``quest_giver`` behavior lists,
    and those whose ``giver`` it is. A giver is an NPC (tagged ``npc``) or
    anything with the ``quest_giver`` behavior; nothing else is asked."""
    defs = definitions()
    if not defs:
        return []
    givers = [b for b in npc.get_behaviors() if b.behavior_id == "quest_giver"]
    if not givers and not npc.is_npc:
        return []
    out: list[Quest] = []
    for behavior in givers:
        names = behavior.get_param("quests") or []
        for name in ([names] if isinstance(names, str) else names):
            quest = defs.get(str(name).strip().lower())
            if quest is not None and quest not in out:
                out.append(quest)
    for quest in defs.values():
        if quest.giver is not None and quest not in out and quest.giver.matches(npc):
            out.append(quest)
    return out


def takes_back(npc: GameObject, quest: Quest) -> bool:
    return quest.giver is not None and quest.giver.matches(npc)


def givers_here(player: GameObject) -> list[GameObject]:
    """The NPCs in ``player``'s room that offer or take back a quest."""
    room = player.location
    from realm.core.perception import can_see
    return [o for o in (room.contents if room is not None else ())
            if o is not player and not o.is_player and can_see(player, o)
            and offered_by(o)]


def quest_marker(obj: GameObject, looker: GameObject | None) -> str | None:
    """``feature.marker``: ``(?)`` beside a giver waiting for the looker's
    hand-in, ``(!)`` beside one with a quest the looker may take."""
    if looker is None or not looker.is_player or obj is looker or obj.is_player:
        return None
    if obj.has_tag("room") or obj.is_exit:
        return None
    offers = offered_by(obj)
    if not offers:
        return None
    if any(takes_back(obj, q) and state(looker, q) == READY for q in offers):
        return "?"
    if any(refusal(looker, q) is None for q in offers):
        return "!"
    return None


__all__ = ["ACCEPT", "ADVANCE", "COMPLETE", "DONE", "FAIL", "READY", "TALK", "accept",
           "complete", "credit", "definitions", "done_at", "expire_all", "fail",
           "find_quest", "givers_here", "history", "missing", "now", "offered_by",
           "progress", "quest_marker", "quest_observer", "rebuild", "record", "records",
           "refusal", "reindex", "settle", "state", "takes_back", "time_left"]
