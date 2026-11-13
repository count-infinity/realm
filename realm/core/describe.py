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


def may_examine(obj: GameObject, viewer: GameObject | None) -> bool:
    """Does viewer pass obj's ``examine`` lock?

    Gates the DETAIL sections of ``examine`` and ``look`` (detail lines,
    visual attributes, tags) — never the name or base description, which
    remain the public surface. Open by default; a builder sets
    ``lock_examine`` to hide an object's detail from prying eyes.
    """
    if viewer is None:
        return True
    from realm.permissions.locks import LockType, check_lock
    return check_lock(obj, LockType.EXAMINE, viewer)


def detail_lines(obj: GameObject, viewer: GameObject | None) -> list[str]:
    """The extra description lines this viewer perceives on obj."""
    extras = obj.db.get(DETAILS_ATTR)
    if not isinstance(extras, list) or viewer is None:
        return []

    from realm.scripting.namespace import build_namespace
    # The `detail` profile: read-only functions and `viewer`, with the viewer
    # as the subject of skill()/check(). Conditions are not run through the
    # script sandbox, so `viewer` is a read-only handle: a hostile row like
    # ["viewer.db.set('marked',1) or False", ...] must not mutate whoever
    # looks (docs/design/sandbox-security.md, Wall 2).
    namespace, _frame = build_namespace(
        'detail', executor=obj, enactor=viewer, location=obj.location,
        subject=viewer)

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
