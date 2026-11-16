"""The action types of item manipulation (the ``items`` feature).

A :class:`~enum.StrEnum` like the kernel's ``ActionType``: each member is its
string value, so saved worlds and softcode see the same strings.
"""

from __future__ import annotations

from enum import StrEnum


class ItemAction(StrEnum):
    ON_GET = "item:on_get"
    ON_DROP = "item:on_drop"
    ON_GIVE = "item:on_give"
    ON_PUT = "item:on_put"
    ON_WEAR = "item:on_wear"
    ON_REMOVE = "item:on_remove"
    ON_WIELD = "item:on_wield"
    ON_UNWIELD = "item:on_unwield"
    ON_USE = "item:on_use"
    ON_EAT = "item:on_eat"
    ON_DRINK = "item:on_drink"
    ON_OPEN = "item:on_open"
    ON_CLOSE = "item:on_close"
    ON_LOCK = "item:on_lock"
    ON_UNLOCK = "item:on_unlock"


__all__ = ["ItemAction"]
