"""
Canonical presentation of world objects as player-facing text.

There is exactly one way to render a room. Movement, ``look``, login, and
OLC teleport all call :func:`render_room` so the display can never drift
between code paths. Rendering is pure — no propagation, no session I/O —
so callers decide what events to fire (``cmd_look`` propagates
``event:look``; movement deliberately does not) and where the text goes.

Identical things are grouped for display ("3 apples" instead of three
"apple" lines) — presentation only, the objects stay individual. Objects
tagged ``no_group`` are always listed on their own line. Games can
restyle the grouped line via :func:`set_group_formatter`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from realm.core.language import numbered_name

if TYPE_CHECKING:
    from realm.core.objects import GameObject

# A group formatter takes (representative object, count) and returns the
# display line body. Replaceable per game via set_group_formatter — e.g.
# lambda obj, n: f"{obj.name} (x{n})" for an "apple (x3)" style.
GroupFormatter = Callable[["GameObject", int], str]


def default_group_formatter(obj: GameObject, count: int) -> str:
    """"an apple" for one, "3 apples" for several."""
    return numbered_name(obj, count)


_group_formatter: GroupFormatter = default_group_formatter


def set_group_formatter(formatter: GroupFormatter | None) -> None:
    """
    Replace how grouped contents lines are styled (None restores the
    default). An extension point for games — call it from a config
    callback like ``on_start``.
    """
    global _group_formatter
    _group_formatter = formatter or default_group_formatter


def group_contents(objects: list[GameObject]) -> list[tuple[GameObject, int]]:
    """
    Group visually identical objects for display.

    Groups by lowercased name, preserving first-seen order; objects
    tagged ``no_group`` stand alone. Returns (representative, count)
    pairs. O(n) — a hash pass, safe for very full rooms.
    """
    groups: dict[str, tuple[GameObject, int]] = {}
    order: list[str] = []
    solo_key = 0

    for obj in objects:
        if obj.has_tag('no_group'):
            solo_key += 1
            key = f"\x00solo{solo_key}"
        else:
            key = obj.name.lower()
        if key in groups:
            rep, count = groups[key]
            groups[key] = (rep, count + 1)
        else:
            groups[key] = (obj, 1)
            order.append(key)

    return [groups[key] for key in order]


def room_description(room: GameObject) -> str:
    """
    Resolve a room's description.

    The ``description`` field (set by OLC ``@desc`` and the constructor)
    wins; the ``db.description`` attribute is honored as a fallback since
    world-building code may set descriptions as plain attributes.
    """
    return room.description or room.db.get('description') or ""


def render_room(room: GameObject | None, viewer: GameObject | None = None) -> str:
    """
    Render a room as the text a player sees on ``look`` or arrival.

    Args:
        room: The room to render. ``None`` renders the "nowhere" message.
        viewer: The looker, excluded from the contents listing.

    Returns:
        The complete multi-line room display, ready for ``session.send``
        or ``player.msg``.
    """
    if room is None:
        return "You are nowhere."

    from realm.core.perception import can_see, can_see_room

    if not can_see_room(viewer, room):
        return "It is pitch black here. You can't see a thing."

    lines = ["", room.name, "-" * len(room.name)]

    desc = room_description(room)
    if desc:
        lines.append(desc)

    things: list[GameObject] = []
    players: list[GameObject] = []
    exits: list[GameObject] = []
    for obj in room.contents:
        if viewer is not None and obj == viewer:
            continue
        if viewer is not None and not can_see(viewer, obj):
            continue  # invisible to this viewer (secret exits included)
        if obj.has_tag('exit'):
            exits.append(obj)
        elif obj.has_tag('player'):
            players.append(obj)
        else:
            things.append(obj)

    if things:
        lines.append("")
        lines.append("You see:")
        lines.extend(
            f"  {_group_formatter(rep, count)}"
            for rep, count in group_contents(things)
        )

    if players:
        lines.append("")
        lines.append("Players here:")
        lines.extend(f"  {obj.name}" for obj in players)

    lines.append("")
    if exits:
        lines.append(f"Exits: {', '.join(e.name for e in exits)}")
    else:
        lines.append("Exits: None")
    lines.append("")

    return "\n".join(lines)


__all__ = [
    "render_room",
    "room_description",
    "group_contents",
    "set_group_formatter",
    "default_group_formatter",
]
