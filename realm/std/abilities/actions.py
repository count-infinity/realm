"""The action types of casting (the ``abilities`` feature).

A :class:`~enum.StrEnum` like the kernel's ``ActionType``: each member is its
string value, so saved worlds and softcode see the same strings.
"""

from __future__ import annotations

from enum import StrEnum


class AbilityAction(StrEnum):
    ON_CAST = "event:on_cast"


__all__ = ["AbilityAction"]
