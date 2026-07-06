"""
Combat strategies: condition → action rules for automated selection.

A strategy is plain data on the combatant —

    db.combat_strategy = [
        ["!me.hp_percent < 30", "flee"],
        ["target.hp < 3", "attack"],
        ["", "attack"],
    ]

Rules are evaluated top-down at beat time. A plain rule fires only when
nothing is manually queued (declared intent wins); a rule whose
condition starts with ``!`` is an OVERRIDE — a reflex that preempts
even a queued action (``wimpy`` writes one). Empty condition = always.

Conditions are lock-style safe expressions (same validator as @lock)
over a small view namespace:

    me / target : .name .hp .max_hp .hp_percent .is_alive
    round       : current round number
    enemies     : count of living opponents
    chance(pct) : True pct% of the time

This one engine drives player automation AND NPC combat AI — a guard's
brain is just a strategy list on its db, inspectable via @examine.
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Any

from realm.combat.maneuver import QueuedAction

if TYPE_CHECKING:
    from realm.combat.encounter import CombatEncounter, Participant

logger = logging.getLogger(__name__)


class CombatView:
    """Read-only view of a combatant for strategy conditions."""

    def __init__(self, participant: Participant | None):
        if participant is None:
            self.name = ""
            self.hp = 0
            self.max_hp = 0
            self.is_alive = False
        else:
            combatant = participant.combatant
            self.name = participant.obj.name
            self.hp = combatant.hp
            self.max_hp = max(1, combatant.max_hp)
            self.is_alive = combatant.is_alive

    @property
    def hp_percent(self) -> float:
        return 100.0 * self.hp / self.max_hp if self.max_hp else 0.0


def _evaluate_condition(condition: str, namespace: dict[str, Any]) -> bool:
    """Validate + evaluate a strategy condition; errors fail closed."""
    from realm.core.safe_eval import eval_bool

    return eval_bool(condition, namespace)


def parse_strategy_action(
    action_str: str,
    encounter: CombatEncounter,
    participant: Participant,
) -> QueuedAction | None:
    """'attack', 'attack guard', 'flee north', 'defend' → QueuedAction."""
    parts = str(action_str).strip().split(None, 1)
    if not parts:
        return None
    maneuver = encounter.combat_system.ruleset.get_maneuver(parts[0])
    if maneuver is None:
        return None
    args = parts[1] if len(parts) > 1 else ""

    target_id = None
    if maneuver.needs_target and args:
        wanted = args.lower()
        for other in encounter.participants.values():
            if other.obj.id == participant.obj.id:
                continue
            if other.obj.name.lower().startswith(wanted):
                target_id = other.obj.id
                args = ""
                break
    return QueuedAction(maneuver=maneuver.key, target_id=target_id, args=args)


def select_strategy_action(
    encounter: CombatEncounter,
    participant: Participant,
    *,
    override_only: bool = False,
) -> QueuedAction | None:
    """
    Pick an action from the participant's strategy rules, or None.

    With ``override_only=True`` (a manual action is queued), only
    ``!``-flagged reflex rules are considered.
    """
    rules = participant.obj.db.get('combat_strategy')
    if not rules:
        return None

    # Build the condition namespace once per selection.
    me_view = CombatView(participant)
    target = encounter.participants.get(participant.target_id or "")
    target_view = CombatView(target)
    enemies = sum(
        1 for other in encounter.participants.values()
        if other.obj.id != participant.obj.id and other.combatant.is_alive
    )
    namespace = {
        'me': me_view,
        'target': target_view,
        'round': encounter.round_number,
        'enemies': enemies,
        'chance': lambda pct: random.random() * 100 < float(pct),
    }

    for entry in rules:
        try:
            condition, action_str = str(entry[0]), str(entry[1])
        except (TypeError, IndexError, KeyError):
            continue

        is_override = condition.startswith('!')
        if is_override:
            condition = condition[1:]
        if override_only and not is_override:
            continue

        if condition.strip() and not _evaluate_condition(condition, namespace):
            continue

        action = parse_strategy_action(action_str, encounter, participant)
        if action is not None:
            return action
    return None


__all__ = ["CombatView", "select_strategy_action", "parse_strategy_action"]
