"""
Events: one declaration per action type.

An :class:`EventDef` says everything about one action type in one place:
the ``ON_<HOOK>`` softcode attribute it fires, a line for the reference,
the payload keys ``adata()`` answers, the lock checked on its target or
tool, and whether its ``{actor}`` is a voice (``voice_as``).

Features declare their events (``feature.event(...)``); the kernel's own
are below. The installed set is the live world's
(``FeatureSet.install_registries``); with no world it is ``CLASSIC``.

An action type nobody declared still fires its derived hook
(``event:on_rumble`` -> ``ON_RUMBLE``), so softcode ``act()`` with a
made-up type works.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from realm.core.action_types import ActionType


@dataclass(frozen=True)
class EventDef:
    """One action type (or a hook fired outside propagation)."""

    action_type: str | None                # "item:on_get"; None for ARRIVE/PUSH/TICK
    hook: str | None = None                # "GET": the documented ON_GET attribute
    doc: str = ""                          # one line for the generated reference
    payload: dict[str, str] = field(default_factory=dict)   # extra key -> meaning
    target_lock: tuple[str, str] | None = None   # (lock type, failure template)
    tool_lock: tuple[str, str] | None = None
    speech: bool = False                   # {actor} is a voice (see voice_as)
    owner: str = "kernel"


def derived_hook(action_type: str) -> str:
    """``event:on_enter`` -> ``ENTER``; ``item:get`` -> ``GET``."""
    suffix = action_type.rsplit(":", 1)[-1].upper()
    return suffix[3:] if suffix.startswith("ON_") else suffix


class EventRegistry:
    """Installed event declarations, by action type and by hook."""

    def __init__(self) -> None:
        self._by_type: dict[str, EventDef] = {}
        self._by_hook: dict[str, EventDef] = {}

    def register(self, event: EventDef, *, replace: bool = False) -> None:
        from realm.features import FeatureError
        if event.action_type is not None:
            held = self._by_type.get(event.action_type)
            if held is not None and held is not event and not replace:
                raise FeatureError(
                    f"event {event.action_type!r} is declared by both {held.owner!r} "
                    f"and {event.owner!r}")
            self._by_type[event.action_type] = event
        if event.hook is not None:
            held = self._by_hook.get(event.hook)
            if held is not None and held is not event and not replace:
                raise FeatureError(
                    f"event hook ON_{event.hook} is declared by both {held.owner!r} "
                    f"and {event.owner!r}")
            self._by_hook[event.hook] = event

    def get(self, action_type: str) -> EventDef | None:
        return self._by_type.get(action_type)

    def hook_for(self, action_type: str) -> str:
        """The ``ON_<hook>`` an action fires: its declared hook, else the
        suffix derived from the type."""
        event = self._by_type.get(action_type)
        if event is not None and event.hook is not None:
            return event.hook
        return derived_hook(action_type)

    def hooks(self) -> dict[str, EventDef]:
        """Every documented hook, by name."""
        return dict(sorted(self._by_hook.items()))

    def events(self) -> list[EventDef]:
        """Every declaration with an action type, sorted by type."""
        return [self._by_type[t] for t in sorted(self._by_type)]


_installed: EventRegistry | None = None


def installed() -> EventRegistry:
    """The live world's events (the CLASSIC set when no world is live)."""
    if _installed is None:
        from realm.features import ensure_registries
        ensure_registries()
    return _installed if _installed is not None else EventRegistry()


def install(events: list[tuple[EventDef, bool]]) -> None:
    """Replace the installed set with the kernel events plus ``(event,
    replace)`` declarations."""
    global _installed
    registry = EventRegistry()
    for event in kernel_events():
        registry.register(event)
    for event, replace in events:
        registry.register(event, replace=replace)
    _installed = registry


_EXIT = {"exit": "the exit object", "direction": "the exit's name",
         "destination": "the room beyond"}


def kernel_events() -> list[EventDef]:
    """Movement, perception, session and object-lifecycle events."""
    return [
        EventDef(ActionType.ON_ENTER, "ENTER", "something enters this location"),
        EventDef(ActionType.ON_LEAVE, "LEAVE", "something leaves this location",
                 payload=dict(_EXIT)),
        EventDef(ActionType.PRE_ENTER, None, "a mover is about to enter (gated)"),
        EventDef(None, "ARRIVE", "this object arrives somewhere new"),
        EventDef(ActionType.ON_FAIL, "FAIL",
                 "a move was thwarted (dead-end/locked exit) — @afail",
                 payload={"reason": "'skill', 'closed', 'locked', ...", **_EXIT}),
        EventDef(ActionType.LOOK, "LOOK", "this object is looked at"),
        EventDef(ActionType.CONNECT, "CONNECT", "player connects",
                 payload={"returning": "True when the character already existed"}),
        EventDef(ActionType.DISCONNECT, "DISCONNECT", "player disconnects"),
        EventDef(ActionType.ACT, None, "a softcode act() with no type of its own"),
        EventDef(ActionType.ON_RECEIVE, "RECEIVE",
                 "this object is given something (recipient side)",
                 payload={"item": "what was given", "giver": "who gave it"}),
        EventDef(ActionType.ON_LOAD, "LOAD", "this object was just spawned",
                 payload={"marker": "the spawner's tracking tag"}),
        EventDef(ActionType.ON_EXPIRE, "EXPIRE",
                 "this object's db.expires_at elapsed (then it's destroyed)"),
        EventDef(ActionType.ON_RESET, "RESET",
                 "this zone master resets (empty + due) — repop, re-lock doors"),
        EventDef(None, "TICK", "periodic timer (on_tick behavior)"),
    ]


__all__ = ["EventDef", "EventRegistry", "derived_hook", "installed", "install",
           "kernel_events"]
