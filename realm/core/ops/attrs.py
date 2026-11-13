"""
Ops on an object's data: attributes, tags, locks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from realm.core.ops import Invalid, NotAllowed, OpResult, Refused, require_control

if TYPE_CHECKING:
    from realm.core.objects import GameObject


# --- attributes --------------------------------------------------------------

def check_attr_name(name: str) -> None:
    """Refuse the protected identity attributes (``password``, ``keyid``)."""
    from realm.core.attrflags import PROTECTED_ATTRS
    from realm.persistence.keyid import KEYID_ATTR
    if not name:
        raise Invalid("Attribute name required.")
    if name == KEYID_ATTR:
        raise Refused("'keyid' is a unique identity handle — set it with @keyid, not "
                      "@set, so its uniqueness is enforced.")
    if name in PROTECTED_ATTRS:
        raise Refused(f"'{name}' is protected and can't be written here.")


def check_set_attr(actor: GameObject | None, obj: GameObject, name: str) -> None:
    """Control, then the protected names, then the attribute's flags
    (``safe``, ``system``)."""
    from realm.core.attrflags import writable_attr
    require_control(actor, obj)
    check_attr_name(str(name))
    ok, reason = writable_attr(obj, str(name), actor)
    if not ok:
        raise Refused(reason)


def set_attr(actor: GameObject | None, obj: GameObject, name: str, value: Any) -> OpResult:
    """Set an attribute. A script attribute that will not run comes back as a
    warning, not a refusal (placeholders and @import are legitimate)."""
    from realm.scripting.triggers import script_code_of, validate_script
    check_set_attr(actor, obj, name)
    obj.db.set(str(name), value)
    result = OpResult(value=value, touched=[obj])
    code = script_code_of(str(name), value)
    if code is not None:
        errors = validate_script(code)
        if errors:
            result.warnings.append(f"{obj.name}/{name} will not run — {errors[0]}")
    return result


def check_del_attr(actor: GameObject | None, obj: GameObject, name: str) -> None:
    """Deleting is a write: the same gate as ``set_attr``."""
    check_set_attr(actor, obj, name)


def del_attr(actor: GameObject | None, obj: GameObject, name: str) -> OpResult:
    """Delete an attribute. ``value`` is whether it existed."""
    check_del_attr(actor, obj, name)
    existed = str(name) in obj.db
    if existed:
        obj.db.delete(str(name))
    return OpResult(value=existed, touched=[obj] if existed else [])


# --- tags --------------------------------------------------------------------

def _check_tag(actor: GameObject | None, obj: GameObject, tag: str, verb: str) -> str:
    from realm.permissions.roles import may_change_role_tag
    tag = str(tag).strip().lower()
    if not tag:
        raise Invalid("Tag name required.")
    require_control(actor, obj)
    if actor is not None and not may_change_role_tag(actor, tag):
        raise NotAllowed(f"You can't {verb} the '{tag}' privilege — it outranks you.")
    return tag


def check_tag(actor: GameObject | None, obj: GameObject, tag: str) -> None:
    _check_tag(actor, obj, tag, "grant")


def tag(actor: GameObject | None, obj: GameObject, tag: str) -> OpResult:
    """Add a tag (lowercased). Role tags need a role that outranks them.
    ``value`` is whether the tag was new."""
    name = _check_tag(actor, obj, tag, "grant")
    if obj.has_tag(name):
        return OpResult(value=False)
    obj.add_tag(name)
    return OpResult(value=True, touched=[obj])


def check_untag(actor: GameObject | None, obj: GameObject, tag: str) -> None:
    _check_tag(actor, obj, tag, "revoke")


def untag(actor: GameObject | None, obj: GameObject, tag: str) -> OpResult:
    """Remove a tag (lowercased). ``value`` is whether it was there."""
    name = _check_tag(actor, obj, tag, "revoke")
    if not obj.has_tag(name):
        return OpResult(value=False)
    obj.remove_tag(name)
    return OpResult(value=True, touched=[obj])


# --- locks -------------------------------------------------------------------

def _lock_type(lock_type: str) -> str:
    """Any lowercase name is a lock type: the registered ones, or a game's
    own (``crack``) that works as soon as a builder sets it."""
    from realm.permissions.locks import LOCK_TYPE_RE
    name = str(lock_type).lower()
    if not LOCK_TYPE_RE.match(name):
        raise Invalid(f"'{name}' is not a lock type name (lowercase letters, digits, _).")
    return name


def _lock_type_warning(name: str) -> list[str]:
    from realm.permissions.locks import near_lock_type
    near = near_lock_type(name)
    return [f"'{name}' is not a known lock type. Did you mean '{near}'?"] if near else []


def check_set_lock(actor: GameObject | None, obj: GameObject, lock_type: str,
                   expression: str) -> None:
    from realm.permissions.locks import parse_lock
    name = _lock_type(lock_type)
    require_control(actor, obj)
    valid, error = parse_lock(str(expression), name).validate()
    if not valid:
        raise Invalid(f"Invalid lock expression: {error}")


def set_lock(actor: GameObject | None, obj: GameObject, lock_type: str,
             expression: str) -> OpResult:
    """Set a lock, validated at write time. A type that is a near miss of a
    registered one (``baisc``) is set, with a "did you mean" warning."""
    check_set_lock(actor, obj, lock_type, expression)
    name = _lock_type(lock_type)
    obj.locks[name] = str(expression)
    return OpResult(value=str(expression), touched=[obj], warnings=_lock_type_warning(name))


def check_clear_lock(actor: GameObject | None, obj: GameObject,
                     lock_type: str | None = None) -> None:
    if lock_type is not None:
        _lock_type(lock_type)
    require_control(actor, obj)


def clear_lock(actor: GameObject | None, obj: GameObject,
               lock_type: str | None = None) -> OpResult:
    """Clear one lock type, or every lock when ``lock_type`` is None.
    ``value`` is how many locks were removed."""
    check_clear_lock(actor, obj, lock_type)
    if lock_type is None:
        count = len(obj.locks)
        obj.locks.clear()
    else:
        count = 1 if obj.locks.pop(_lock_type(lock_type), None) is not None else 0
    return OpResult(value=count, touched=[obj] if count else [])


# --- keyid -------------------------------------------------------------------

_KEYID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-")


def check_set_keyid(actor: GameObject | None, obj: GameObject, keyid: str, store) -> None:
    """A keyid is a slug (letters, digits, ``_ . : -``, at most 64, not ``#``)."""
    require_control(actor, obj)
    if not keyid or len(keyid) > 64:
        raise Invalid("A keyid must be 1-64 characters.")
    if keyid.startswith('#'):
        raise Invalid("A keyid may not start with '#' (the raw-id prefix).")
    if any(c not in _KEYID_CHARS for c in keyid):
        raise Invalid("A keyid may use only letters, digits, and _ . : - "
                      "(no spaces or sigils).")
    if store is None:
        raise Invalid("No persistence available — cannot register a keyid.")


def set_keyid(actor: GameObject | None, obj: GameObject, keyid: str, store) -> OpResult:
    """Give ``obj`` a unique friendly handle. A handle held by another object
    is refused (conflict, never merge)."""
    from realm.persistence.keyid import KEYID_ATTR
    check_set_keyid(actor, obj, keyid, store)
    claimed, why = store.claim_keyid(obj, keyid)
    if not claimed:
        raise Refused(f"Refused: {why}. Clear it there first, or choose another handle.")
    obj.db.set(KEYID_ATTR, keyid)
    return OpResult(value=keyid, touched=[obj])


def check_clear_keyid(actor: GameObject | None, obj: GameObject) -> None:
    from realm.persistence.keyid import KEYID_ATTR
    require_control(actor, obj)
    if not obj.db.get(KEYID_ATTR):
        raise Invalid(f"{obj.name} has no keyid to clear.")


def clear_keyid(actor: GameObject | None, obj: GameObject, store) -> OpResult:
    """Free ``obj``'s keyid. ``value`` is the old handle."""
    from realm.persistence.keyid import KEYID_ATTR
    check_clear_keyid(actor, obj)
    old = obj.db.get(KEYID_ATTR)
    if store is not None:
        store.release_keyid(obj)
    obj.db.delete(KEYID_ATTR)
    return OpResult(value=old, touched=[obj])
