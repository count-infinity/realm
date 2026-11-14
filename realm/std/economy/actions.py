"""The action types of money changing hands (the ``economy`` feature).

A :class:`~enum.StrEnum` like the kernel's ``ActionType``: each member is its
string value, so saved worlds and softcode see the same strings.
"""

from __future__ import annotations

from enum import StrEnum


class EconomyAction(StrEnum):
    PAYMENT = "event:payment"


__all__ = ["EconomyAction"]
