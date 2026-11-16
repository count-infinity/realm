"""
Softcode functions: quests (MUD_PLAN 15.3).

``quest_state`` and ``quest_count`` are read-only, so they are there in
lock expressions too, where the one trying is ``caller``: a door that
opens to those who finished a quest is ``@lock door = quest_state(caller,
'Fido trouble') == 'done'``. ``quest_offer``, ``quest_advance``,
``quest_complete`` and ``quest_fail`` are for builders (the HARM
entitlement) and act after the script.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.std.quests.quests import (
    accept,
    complete,
    credit,
    fail,
    find_quest,
    progress,
    record,
    refusal,
    state,
)

if TYPE_CHECKING:
    from realm.core.objects import GameObject


def quest_state(frame, obj: GameObject | str | None, quest: str) -> int | str | None:
    """Where ``obj`` stands on ``quest``: None (never taken, or failed), the
    current stage number (1 is the first), ``'ready'`` (every stage met,
    waiting to be handed in) or ``'done'``.

    Example: quest_state(enactor, 'Fido trouble') == 'done'
    """
    target = frame.resolve(obj)
    found = find_quest(quest)
    if target is None or found is None:
        return None
    return state(target, found)


def quest_count(frame, obj: GameObject | str | None, quest: str, key: str) -> int:
    """How far ``obj`` is on the objective ``key`` of their current stage
    of ``quest`` (0 when they are not on it, or the stage has no such
    objective). A ``collect`` objective counts what they hold now.

    Example: quest_count(enactor, 'Fido trouble', 'kill')
    """
    target = frame.resolve(obj)
    found = find_quest(quest)
    rec = record(target, found) if target is not None and found is not None else None
    if rec is None or not isinstance(rec.get("stage"), int):
        return 0
    stage = found.stage(rec["stage"])
    objective = next((o for o in (stage.objectives if stage else ())
                      if o.key == str(key).lower()), None)
    return progress(target, found, objective, rec) if objective is not None else 0


def _quest_for(frame, obj, quest):
    target = frame.resolve(obj)
    found = find_quest(quest)
    if target is None or not target.is_player or found is None:
        return None, None
    return target, found


def quest_offer(frame, obj: GameObject | str | None, quest: str) -> bool:
    """Start ``quest`` for ``obj`` as if they had accepted it (a note read,
    a stranger met): True when they may take it, False (and nothing
    happens) when not. Builders only; it lands after the script.

    Example: quest_offer(enactor, 'The Cinder Road')
    """
    target, found = _quest_for(frame, obj, quest)
    if found is None or refusal(target, found) is not None:
        return False
    frame.command_queue.append(("quest_offer", target, found.key))
    return True


def quest_advance(frame, obj: GameObject | str | None, quest: str, key: str,
                  by: int = 1) -> bool:
    """Count ``by`` toward the objective ``key`` of ``obj``'s current stage
    of ``quest``: a ``custom`` objective, or any other. False when they are
    not on that stage. Builders only; it lands after the script.

    Example: quest_advance(enactor, 'The Cinder Road', 'ledger')
    """
    target, found = _quest_for(frame, obj, quest)
    rec = record(target, found) if found is not None else None
    if rec is None or not isinstance(rec.get("stage"), int):
        return False
    stage = found.stage(rec["stage"])
    if stage is None or not any(o.key == str(key).lower() for o in stage.objectives):
        return False
    frame.command_queue.append(("quest_advance", target,
                                (found.key, str(key).lower(), int(by))))
    return True


def quest_complete(frame, obj: GameObject | str | None, quest: str) -> bool:
    """Complete ``obj``'s ``quest`` now, whatever is left of it, and pay its
    rewards. Builders only; it lands after the script.

    Example: quest_complete(enactor, 'The Cinder Road')
    """
    target, found = _quest_for(frame, obj, quest)
    if found is None or record(target, found) is None:
        return False
    frame.command_queue.append(("quest_complete", target, found.key))
    return True


def quest_fail(frame, obj: GameObject | str | None, quest: str) -> bool:
    """End ``obj``'s ``quest`` unfinished (``QUESTFAIL`` fires, reason
    ``failed``). Builders only; it lands after the script.

    Example: quest_fail(enactor, 'The Cinder Road')
    """
    target, found = _quest_for(frame, obj, quest)
    if found is None or record(target, found) is None:
        return False
    frame.command_queue.append(("quest_fail", target, found.key))
    return True


async def queued_offer(engine, frame, target, key) -> None:
    found = find_quest(key)
    if found is not None:
        await accept(target, found)


async def queued_advance(engine, frame, target, payload) -> None:
    key, objective, by = payload
    found = find_quest(key)
    if found is not None:
        await credit(target, found, objective, by)


async def queued_complete(engine, frame, target, key) -> None:
    found = find_quest(key)
    if found is not None and state(target, found) not in (None, "done"):
        await complete(target, found)


async def queued_fail(engine, frame, target, key) -> None:
    found = find_quest(key)
    if found is not None:
        await fail(target, found, "failed")


__all__ = ["queued_advance", "queued_complete", "queued_fail", "queued_offer",
           "quest_advance", "quest_complete", "quest_count", "quest_fail", "quest_offer",
           "quest_state"]
