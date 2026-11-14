"""
Perception: who can see whom, and what unseen things are called.

The kernel knows two rules: you always see yourself, and a viewer with the
SEE_ALL entitlement (every built-in ADMIN+) sees everything. Everything
else is a feature's ``feature.sight_rule``: the ``sight`` feature's
darkness, light and invisibility, the ``stealth`` feature's ``hidden``.
Unseen things vanish from room displays and can't be targeted; an unseen
actor still acts, and bystanders read "Someone" in messages. Markers on
listed names (``a torch (glowing)``) are ``feature.marker``.

The single naming entry point is :func:`perceived_name` (exposed as
``GameObject.get_display_name(looker)``) — message formatting, room
rendering, and targeting all route through the same rules, so a
character can never be named in a message but hidden from ``look``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

def sees_all(viewer: GameObject) -> bool:
    """Whether ``viewer`` sees everything, whatever the sight rules say (the
    ``sight`` feature's darkness and invisibility, ``stealth``'s ``hidden``):
    the SEE_ALL entitlement (every built-in ADMIN+ has it; a custom role may
    too)."""
    from realm.permissions.entitlements import SEE_ALL
    from realm.permissions.roles import has_entitlement
    return has_entitlement(viewer, SEE_ALL)


def can_see(viewer: GameObject | None, obj: GameObject) -> bool:
    """
    Whether the viewer perceives the object.

    You always see yourself; SEE_ALL sees everything. Then the world's sight
    rules (``feature.sight_rule``): any False hides.
    """
    if viewer is None or viewer is obj:
        return True
    if sees_all(viewer):
        return True
    from realm.core.world import find_world
    world = find_world()
    if world is not None:
        for rule in world.sight_rules:
            if rule(viewer, obj) is False:
                return False
    return True


def display_markers(obj: GameObject, looker: GameObject | None) -> str:
    """
    CoffeeMud-style parenthetical dispositions appended to a name, from the
    world's markers (``feature.marker``) in feature order:
    ``a torch (glowing)``, ``a rusty key (hidden)``. Empty when none apply.
    """
    from realm.core.world import find_world
    world = find_world()
    marks = []
    for fn in (world.markers if world is not None else ()):
        mark = fn(obj, looker)
        if mark:
            marks.append(mark)
    return f" ({', '.join(marks)})" if marks else ""


import logging

logger = logging.getLogger(__name__)

def perceived_name(obj: GameObject, looker: GameObject | None = None) -> str:
    """
    The name the looker knows this object by — used in MESSAGES, so it
    stays clean (no markers): the real (or resolved) name when visible,
    else "Someone"/"something". Perception markers are a LOOK concern —
    see ``display_markers``, applied by the room renderer.

    When visible, the name passes through the world's name resolvers
    (recognition, disguise — ``feature.name_resolver``). With none, this
    is ``obj.name``.
    """
    if looker is None or can_see(looker, obj):
        name = obj.name
        from realm.core.world import find_world
        world = find_world()
        for fn in (world.name_resolvers if world is not None else ()):
            try:
                name = fn(obj, looker, name)
            except Exception as exc:   # noqa: BLE001 - never blank a name
                logger.error("name resolver %r failed: %s",
                             getattr(fn, "__name__", fn), exc)
        return name
    if obj.is_player or obj.is_npc:
        return "Someone"
    return "something"


__all__ = [
    "display_markers",
    "sees_all",
    "can_see",
    "perceived_name",
]
