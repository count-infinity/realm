"""
Per-attribute flags — the five that earn their keep (of PennMUSH's ~30):

    secret    unreadable except by controllers (softcode + @examine)
    visual    shown on plain player ``examine``
    safe      @set/@wipe/set_attr refuse until the flag is cleared
    system    system-owned: only ADMIN+ (CONTROL_ALL, delegated) may write
              or delete it. Character stats (ST/DX/HT…) are stamped this at
              creation so neither the player nor a plain builder can rewrite
              them; the native GameSystem, writing raw ``db.set`` in Python,
              is unaffected (it is the "system" that owns them).
    no_clone  skipped by @clone / prototype extraction
    public    callable AS this object via call() by non-controllers — the
              deliberate cross-owner "public method" opt-in (co-owned callers
              never need it, control already suffices). Independent of secret:
              a secret+public attr is an opaque public method (invoke as the
              object, source stays hidden, and cannot be run as the caller).

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
VALID_FLAGS = ("secret", "visual", "safe", "system", "no_clone", "public")


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


def writable_attr(obj: GameObject, name: str,
                  writer: GameObject | None = None) -> tuple[bool, str]:
    """May this attribute be written (or deleted)? Returns (ok, reason).

    - ``safe`` refuses everyone until cleared (a manual, per-attr brake).
    - ``system`` refuses everyone below ADMIN+ (``CONTROL_ALL``, walked up
      the writer's owner chain so an admin's own script still qualifies).
      ``writer=None`` means no authenticated writer in context, so a
      system attr is refused — the native GameSystem never calls this; it
      writes ``db.set`` directly.
    """
    if has_attr_flag(obj, name, 'safe'):
        return False, (f"'{name}' is flagged safe — "
                       f"@attr it !safe to modify it.")
    if has_attr_flag(obj, name, 'system'):
        from realm.permissions.entitlements import CONTROL_ALL
        from realm.permissions.roles import has_entitlement_delegated
        if not has_entitlement_delegated(writer, CONTROL_ALL):
            return False, (f"'{name}' is system-owned and cannot be changed "
                           f"here.")
    return True, ""


def add_attr_flag(obj: GameObject, name: str, flag: str) -> None:
    """Union one flag onto an attribute, keeping any it already has.

    ``set_attr_flags`` replaces the whole flag list; this is the additive
    form for stamping a single flag (e.g. chargen marking each stat
    ``system``) without clobbering an unrelated ``secret``/``visual``.
    """
    current = attr_flags(obj, name)
    if flag not in current:
        set_attr_flags(obj, name, sorted(current | {flag}))


def mark_system(obj: GameObject, *names: str) -> None:
    """Stamp each named attribute ``system`` (chargen locking stats)."""
    for name in names:
        add_attr_flag(obj, name, 'system')


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
           "set_attr_flags", "add_attr_flag", "mark_system",
           "readable_attr", "writable_attr",
           "visual_attrs", "cloneable_attrs"]
