"""
Crime & justice: the minimal-viable core (Diku-modernized).

A player who assaults or murders another player is flagged **wanted** — a
timed ``wanted:<crime>`` tag carrying ``heat``. Peacekeeper guards
(``PeacekeeperBehavior``) attack the wanted; the flag decays on a timer
(``WantedBehavior``) or clears on death. The load-bearing rule is Diku's
``check_killer``: **attacking someone already wanted is free** — the flag is
self-enforcing, so there are no courts. Detection is passive: one observer
on the existing ``combat:on_damage`` / ``combat:on_death`` events, flagging
the *initiator* (never the invoker).

This is the "core" tier. Jurisdiction (lawful/safe zones + PvP consent),
arrest, and jails are deliberately out of scope here (see BACKLOG).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.action_types import ActionType

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action

WANTED_PREFIX = "wanted:"
ASSAULT_HEAT = 1
MURDER_HEAT = 5
#: wanted duration (world beats) = heat * this
BEATS_PER_HEAT = 20


def is_wanted(obj: GameObject | None) -> bool:
    return obj is not None and any(
        t.startswith(WANTED_PREFIX) for t in obj.tags.to_list())


def wanted_heat(obj: GameObject | None) -> int:
    return int(obj.db.get("wanted_heat") or 0) if obj is not None else 0


def flag_wanted(offender: GameObject, crime: str, heat: int) -> None:
    """Flag ``offender`` wanted for ``crime`` at ``heat``, (re)starting the
    decay timer at the higher of the old and new heat."""
    from realm.core.behaviors import BehaviorRegistry

    tag = f"{WANTED_PREFIX}{crime}"
    if tag not in offender.tags.to_list():
        offender.add_tag(tag)
    heat = max(wanted_heat(offender), int(heat))
    offender.db.set("wanted_heat", heat)
    offender.msg(f"You are now WANTED for {crime}!")
    for behavior in list(offender.get_behaviors()):
        if behavior.behavior_id == "wanted":
            offender.remove_behavior(behavior)
    timer = BehaviorRegistry.create("wanted", duration=heat * BEATS_PER_HEAT)
    if timer is not None:
        offender.add_behavior(timer)


def clear_wanted(offender: GameObject) -> None:
    """Drop all wanted tags/heat/timer — a served sentence, or a death."""
    for tag in list(offender.tags.to_list()):
        if tag.startswith(WANTED_PREFIX):
            offender.remove_tag(tag)
    offender.db.delete("wanted_heat")
    for behavior in list(offender.get_behaviors()):
        if behavior.behavior_id == "wanted":
            offender.remove_behavior(behavior)


async def crime_observer(action: Action) -> None:
    """Passive detection on the combat events: flag the aggressor, pardon the
    slain. Registered at boot beside the stealth/hostile observers."""
    if action.blocked:
        return
    actor, target = action.actor, action.target

    if action.action_type == ActionType.ON_DEATH:
        # The victim's status at the moment of death decides both outcomes.
        victim_was_wanted = is_wanted(target)
        if (actor is not None and target is not None and actor is not target
                and actor.has_tag("player") and target.has_tag("player")
                and not victim_was_wanted):
            flag_wanted(actor, "murder", MURDER_HEAT)   # killing the innocent
        if victim_was_wanted and target is not None:
            clear_wanted(target)                        # death pardons the outlaw
        return

    if action.action_type == ActionType.ON_DAMAGE:
        if actor is None or target is None or actor is target:
            return
        if not (actor.has_tag("player") and target.has_tag("player")):
            return                                      # only PvP is a crime
        if is_wanted(target):
            return                                      # hitting an outlaw is free
        if not is_wanted(actor):                        # don't downgrade a murderer
            flag_wanted(actor, "assault", ASSAULT_HEAT)


__all__ = ["crime_observer", "flag_wanted", "clear_wanted", "is_wanted",
           "wanted_heat", "WANTED_PREFIX"]
