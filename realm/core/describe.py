"""
Per-viewer conditional descriptions: what YOU see isn't what I see.

``db.desc_extras`` on any object is a list of [condition, text] pairs.
At render time each condition is evaluated PER VIEWER through the
unified safe-eval engine (same rules as locks and strategies), with a
viewer-bound namespace:

    viewer            the looker (GameObject)
    skill(name)       viewer's effective skill level (stable)
    check(name, mod)  fresh skill roll (condition modifiers apply) —
                      re-rolls every look; use skill() for stability
    has_tag(name)     viewer has the tag

The thief's passive detection:

    @detail here = check('observation', -2) -> You notice a small
        hole in the wall, low behind the crates.

Empty condition = shown to everyone (plain detail lines).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.safe_eval import eval_bool

if TYPE_CHECKING:
    from realm.core.objects import GameObject

DETAILS_ATTR = "desc_extras"


def detail_lines(obj: GameObject, viewer: GameObject | None) -> list[str]:
    """The extra description lines this viewer perceives on obj."""
    extras = obj.db.get(DETAILS_ATTR)
    if not isinstance(extras, list) or viewer is None:
        return []

    from realm.core.checks import check as _check
    from realm.core.checks import skill_level as _skill_level

    namespace = {
        'viewer': viewer,
        'skill': lambda name: _skill_level(viewer, str(name)),
        'check': lambda name, mod=0: bool(_check(viewer, str(name), int(mod))),
        'has_tag': lambda tag: viewer.has_tag(str(tag)),
    }

    lines: list[str] = []
    for entry in extras:
        try:
            condition, text = str(entry[0]), str(entry[1])
        except (TypeError, IndexError, KeyError):
            continue
        if not condition.strip() or eval_bool(condition, namespace):
            lines.append(text)
    return lines


__all__ = ["DETAILS_ATTR", "detail_lines"]
