"""
Per-attribute flags — the four that earn their keep (of PennMUSH's ~30):

    secret    unreadable except by controllers (softcode + @examine)
    visual    shown on plain player ``examine``
    safe      @set/@wipe/set_attr refuse until the flag is cleared
    no_clone  skipped by @clone / prototype extraction

Stored in the house style: one dict on the object —
``db.attr_flags = {"gm_notes": ["secret"], "lore": ["visual"]}`` —
managed with the ``@attr`` command. REALM keeps Penn's opposite
default: attributes are READABLE unless flagged secret, because the
mechanics layer (traps reading hp, shops reading value) depends on it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

FLAGS_ATTR = "attr_flags"
VALID_FLAGS = ("secret", "visual", "safe", "no_clone")


def attr_flags(obj: GameObject, name: str) -> set[str]:
    table = obj.db.get(FLAGS_ATTR)
    if not isinstance(table, dict):
        return set()
    return set(table.get(name) or ())


def has_attr_flag(obj: GameObject, name: str, flag: str) -> bool:
    return flag in attr_flags(obj, name)


def set_attr_flags(obj: GameObject, name: str, flags: list[str]) -> None:
    """Replace an attribute's flags (empty list clears the entry)."""
    table = dict(obj.db.get(FLAGS_ATTR) or {})
    if flags:
        table[name] = sorted(set(flags))
    else:
        table.pop(name, None)
    if table:
        obj.db.set(FLAGS_ATTR, table)
    else:
        obj.db.delete(FLAGS_ATTR)


def readable_attr(obj: GameObject, name: str,
                  reader: GameObject | None) -> bool:
    """secret attrs are controller-only; everything else is open."""
    if not has_attr_flag(obj, name, 'secret'):
        return True
    from realm.permissions.locks import controls
    return controls(reader, obj)


def writable_attr(obj: GameObject, name: str) -> tuple[bool, str]:
    """safe attrs refuse writes; returns (ok, reason)."""
    if has_attr_flag(obj, name, 'safe'):
        return False, (f"'{name}' is flagged safe — "
                       f"@attr it !safe to modify it.")
    return True, ""


def visual_attrs(obj: GameObject) -> list[str]:
    table = obj.db.get(FLAGS_ATTR)
    if not isinstance(table, dict):
        return []
    return sorted(n for n, f in table.items() if 'visual' in (f or ()))


def cloneable_attrs(attrs: dict, flag_table: dict | None) -> dict:
    """Filter a db.all() dict for @clone/prototype extraction.

    Always drops 'keyid' — a unique identity handle can't be shared by a
    copy any more than a uuid can (see realm/persistence/keyid.py); the
    clone lands keyless and is re-keyed by hand if it should be a singleton.
    """
    skip = {'keyid'}
    if isinstance(flag_table, dict):
        skip |= {n for n, f in flag_table.items() if 'no_clone' in (f or ())}
    return {k: v for k, v in attrs.items() if k not in skip}


__all__ = ["FLAGS_ATTR", "VALID_FLAGS", "attr_flags", "has_attr_flag",
           "set_attr_flags", "readable_attr", "writable_attr",
           "visual_attrs", "cloneable_attrs"]
