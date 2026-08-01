"""Canonical vocabulary of propagation action types.

Every action that flows through the propagation chain carries an
``action_type`` string of the form ``"namespace:verb"`` (``"event:on_enter"``,
``"combat:on_damage"``, ``"item:on_get"``). Behaviors decide whether to react
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

Data-driven namespaces (an ability whose domain is minted at runtime, e.g.
``f"{domain}:{slug}"`` in :mod:`realm.systems.abilities`) are deliberately *not*
enumerated here — their vocabulary is open by design.
"""

from __future__ import annotations

from enum import StrEnum


class ActionType(StrEnum):
    """The fixed ``namespace:verb`` action types the engine propagates.

    Grouped by namespace for readability; every member's value carries its own
    namespace prefix, so call sites read ``ActionType.ON_GET`` and the string
    ``"item:on_get"`` travels with it.
    """

    # -- event: movement, perception, communication, lifecycle ---------------
    ON_ENTER = "event:on_enter"
    ON_LEAVE = "event:on_leave"
    PRE_ENTER = "event:pre_enter"
    LOOK = "event:look"
    CONNECT = "event:connect"
    DISCONNECT = "event:disconnect"
    ON_FAIL = "event:on_fail"
    # speech & poses
    SPEECH = "event:speech"
    SHOUT = "event:shout"
    OOC = "event:ooc"
    WHISPER = "event:whisper"
    EMOTE = "event:emote"
    SEMIPOSE = "event:semipose"
    EMIT = "event:emit"
    ACT = "event:act"
    # object / economy lifecycle
    PAYMENT = "event:payment"
    ON_RECEIVE = "event:on_receive"
    ON_RESET = "event:on_reset"
    ON_LOAD = "event:on_load"
    ON_EXPIRE = "event:on_expire"
    ON_CAST = "event:on_cast"
    ON_HITPRCNT = "event:on_hitprcnt"

    # -- combat ---------------------------------------------------------------
    ON_ATTACK = "combat:on_attack"
    ON_DAMAGE = "combat:on_damage"
    ON_DEATH = "combat:on_death"
    NARRATE = "combat:narrate"

    # -- item: manipulation ---------------------------------------------------
    ON_GET = "item:on_get"
    ON_DROP = "item:on_drop"
    ON_GIVE = "item:on_give"
    ON_PUT = "item:on_put"
    ON_WEAR = "item:on_wear"
    ON_REMOVE = "item:on_remove"
    ON_WIELD = "item:on_wield"
    ON_UNWIELD = "item:on_unwield"
    ON_USE = "item:on_use"
    ON_OPEN = "item:on_open"
    ON_CLOSE = "item:on_close"
    ON_LOCK = "item:on_lock"
    ON_UNLOCK = "item:on_unlock"
