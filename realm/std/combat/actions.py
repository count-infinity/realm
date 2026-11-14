"""The action types of fighting (the ``combat`` feature).

A :class:`~enum.StrEnum` like the kernel's ``ActionType``: each member is its
string value, so saved worlds and softcode see the same strings.
"""

from __future__ import annotations

from enum import StrEnum


class CombatAction(StrEnum):
    ON_ATTACK = "combat:on_attack"
    ON_DAMAGE = "combat:on_damage"
    ON_DEATH = "combat:on_death"
    NARRATE = "combat:narrate"
    ON_HITPRCNT = "event:on_hitprcnt"


__all__ = ["CombatAction"]
