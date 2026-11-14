"""Canonical vocabulary of propagation action types.

Every action that flows through the propagation chain carries an
``action_type`` string of the form ``"namespace:verb"`` (``"event:on_enter"``,
``"event:on_leave"``, ``"item:on_get"``). Behaviors decide whether to react
by comparing against that string:

    if action.action_type != "event:on_enter":
        return

The hazard that motivates this module: a *typo* in one of those literals
(``"event:on_entre"``) does not raise — the comparison simply never matches,
so the behavior silently stops firing. That failure mode has bitten this
codebase more than once and is invisible until someone notices the feature is
dead.

Routing every reference through :class:`ActionType` turns that class of bug
into an ``AttributeError`` at import time: ``ActionType.ON_ENTRE`` fails loudly
the moment the module loads, long before a player wonders why the guard let
them walk past.

:class:`ActionType` is a :class:`~enum.StrEnum`, so each member *is* its string
value. ``ActionType.ON_ENTER == "event:on_enter"`` is ``True``, membership in
string sets and dict lookups keyed by the raw string both work, and it
serialises as the plain string. It is a drop-in for the literals it replaces.

This module holds only the kernel's own types: movement, looking,
connection, failure, lifecycle. A feature declares its own enum next to it
(``realm.std.talk.actions.TalkAction``, ``ItemAction``, ``CombatAction``,
``EconomyAction``, ``AbilityAction``) and its events with ``feature.event``.
Data-driven namespaces (an ability whose domain is minted at runtime, e.g.
``f"{domain}:{slug}"``) are deliberately *not* enumerated — their vocabulary is
open by design.
"""

from __future__ import annotations

from enum import StrEnum


class ActionType(StrEnum):
    """The kernel's ``namespace:verb`` action types.

    Every member's value carries its own namespace prefix, so call sites read
    ``ActionType.ON_ENTER`` and the string ``"event:on_enter"`` travels with it.
    """

    # -- movement and looking --------------------------------------------------
    ON_ENTER = "event:on_enter"
    ON_LEAVE = "event:on_leave"
    PRE_ENTER = "event:pre_enter"
    LOOK = "event:look"
    ON_FAIL = "event:on_fail"
    # -- connection --------------------------------------------------------------
    CONNECT = "event:connect"
    DISCONNECT = "event:disconnect"
    # -- narration (an object's own act line) ---------------------------------
    ACT = "event:act"
    # -- object lifecycle --------------------------------------------------------
    ON_RECEIVE = "event:on_receive"
    ON_RESET = "event:on_reset"
    ON_LOAD = "event:on_load"
    ON_EXPIRE = "event:on_expire"
    # -- pools (realm.core.pools.settle) ---------------------------------------
    POOL_CHANGE = "pool:on_change"
    POOL_SPENT = "pool:on_spent"
