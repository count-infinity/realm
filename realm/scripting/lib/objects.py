"""
Softcode functions: Object lookup, creation, destruction and subroutines.

Each function is registered with ``@softfn``; one that takes the run's
``ScriptFrame`` as ``frame`` reads the executor, enactor, store and queue
from it. See ``realm/scripting/registry.py`` for the flags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.attrflags import PROTECTED_ATTRS
from realm.core.world import setting
from realm.scripting.registry import softfn

if TYPE_CHECKING:
    from realm.core.objects import GameObject

@softfn(group='Objects & attributes', readonly=True)
def get(frame, spec: str) -> GameObject | None:
    """
    Get an object by ID, friendly keyid, or name.

    Three forms, chosen by prefix:

    - ``#<uuid>`` — exact raw-id lookup (the canonical, stable address).
    - ``$<keyid>`` — a friendly, unique handle set with ``@keyid``
      (``get('$banknet_core')``); resolves through the keyid index, so it
      is collision-proof and survives renames. The ``$`` is the default
      keyid sigil and is game-configurable.
    - anything else — a NAME match, local first (the executor's room and
      inventory) then the whole world, taking the FIRST match and never
      raising on ambiguity. Prefer ``#id``/``$keyid`` when identity matters.
      A name never finds an account (a character's login record, often of
      the same name); ``#id`` still does.

    Returns the GameObject, or None if not found.

    Example: get('rusty key')  or  get('#3fa9...')  or  get('$banknet_core')
    """
    spec = str(spec).strip()

    # ID lookup
    if spec.startswith('#'):
        if not frame.store:
            return None
        return frame.store.get_cached(spec[1:])

    # Friendly keyid lookup ($<keyid> by default) — an exact, unique,
    # rename-proof handle resolved through the keyid index.
    sigil = setting("KEYID_SIGIL")
    if spec.startswith(sigil):
        if not frame.store:
            return None
        return frame.store.keyid_holder(spec[len(sigil):])

    # Name lookup — local first (executor's room + inventory), like
    # player commands; then the whole world. Same tiered matcher as
    # commands; scripts take the first match rather than raising on
    # ambiguity.
    from realm.core.search import in_world, match_objects

    local: list[GameObject] = []
    if frame.executor is not None:
        room = frame.executor.location
        if room is not None:
            local.extend(room.contents)
            local.append(room)
        local.extend(frame.executor.contents)
        local.append(frame.executor)
    matches = match_objects(spec, local).matches
    if matches:
        return matches[0]

    if not frame.store:
        return None
    matches = match_objects(spec, in_world(frame.store.all_cached())).matches
    return matches[0] if matches else None

@softfn(group='Objects & attributes', readonly=True)
def name(frame, obj: GameObject | str | None) -> str:
    """Get an object's name.

    Example: name(enactor)
    """
    target = frame.resolve(obj)
    return target.name if target else ""

@softfn(group='Objects & attributes', readonly=True)
def loc(frame, obj: GameObject | str | None) -> GameObject | None:
    """Get an object's location.

    Example: loc(enactor)
    """
    target = frame.resolve(obj)
    return target.location if target else None

@softfn(group='Objects & attributes', readonly=True)
def owner(frame, obj: GameObject | str | None) -> GameObject | None:
    """Get an object's owner.

    Example: owner(me) == enactor
    """
    target = frame.resolve(obj)
    return target.owner if target else None

@softfn(group='Objects & attributes', readonly=True)
def contents(frame, obj: GameObject | str | None) -> list[GameObject]:
    """Get an object's contents.

    Example: [o for o in contents(here) if has_tag(o, 'npc')]
    """
    target = frame.resolve(obj)
    return target.contents if target else []

@softfn(group='Objects & attributes', readonly=True)
def controls(frame, obj: GameObject | str | None) -> bool:
    """Does the executor control this object? (The mutation gate.)

    Example: controls('lever')
    """
    from realm.permissions.locks import controls as _controls
    target = frame.resolve(obj)
    return _controls(frame.executor, target)

@softfn(group='Objects & attributes', readonly=True)
def exits(frame, room: GameObject | str | None = None) -> list[GameObject]:
    """Open exits of a room (default: the executor's location).

    Example: move(name(exits(here)[0]))
    """
    room_obj = frame.resolve(room) if room is not None else frame.location
    if room_obj is None:
        return []
    return [o for o in room_obj.contents if o.is_exit]

@softfn(group='Objects & attributes')
def create_obj(
    frame,
    name: str,
    tags: list[str] | None = None,
    location: GameObject | str | None = None,
    description: str = "",
    attrs: dict | None = None,
) -> GameObject | None:
    """
    Create a new thing, owned by the executor's owner (or the
    executor itself), at the executor's location by default.

    ``description`` sets the render description ``look`` shows; ``attrs``
    is a dict of attributes stamped on at birth. Together they mint a whole
    item in one call, instead of a ``create_obj``/``set_attr`` chain:

        create_obj('bulb of cold coffee',
                   description='A dented bulb, beaded with condensation.',
                   attrs={'weight': 1})

    Example: sword = create_obj('iron sword')
    """
    from realm.core import ops
    where = frame.resolve(location) if location is not None else (
        frame.executor.location if frame.executor else None)
    # Creation lands in the executor itself, its room, or a location it
    # controls; attributes pass the same name gate as set_attr.
    result = frame.apply(ops.create, str(name), location=where,
                         description=str(description),
                         tags=[str(t) for t in (tags or ['thing'])], attrs=attrs)
    return result.value if result is not None else None

@softfn(group='Objects & attributes')
def destroy_obj(frame, obj: GameObject | str | None) -> bool:
    """Destroy an object the executor controls. Players and ``safe``-tagged
    objects are refused (returns False). Like ``@destroy``: players inside
    are sent home, player-owned items go to their owner's home, and
    everything else inside is destroyed with it.

    Example: destroy_obj('slag')
    """
    from realm.core import ops
    target = frame.resolve(obj)
    if target is None or not frame.allowed(ops.check_destroy, target):
        return False
    frame.command_queue.append(('destroy', target, ''))
    return True


@softfn(group='Objects & attributes')
def clone_obj(frame, obj: GameObject | str | None, name: str | None = None,
              location: GameObject | str | None = None) -> GameObject | None:
    """Copy an object the executor controls: attributes, tags, behaviors,
    locks and parent (not its unique keyid). The copy lands in the
    executor's room unless ``location`` names one it controls. Players and
    rooms can't be cloned.

    Example: twin = clone_obj('brass key', 'spare key')
    """
    from realm.core import ops
    original = frame.resolve(obj)
    if original is None:
        return None
    where = frame.resolve(location) if location is not None else (
        frame.executor.location if frame.executor else None)
    result = frame.apply(ops.clone, original, name=name, location=where)
    return result.value if result is not None else None


@softfn(group='Objects & attributes')
def set_name(frame, obj: GameObject | str | None, name: str) -> bool:
    """Rename an object the executor controls (like ``@name``).

    Example: set_name(me, 'humming lantern')
    """
    from realm.core import ops
    target = frame.resolve(obj)
    return target is not None and frame.apply(ops.rename, target, str(name)) is not None


@softfn(group='Objects & attributes')
def set_desc(frame, obj: GameObject | str | None, text: str) -> bool:
    """Set the description ``look`` shows on an object the executor controls
    (like ``@desc``; an empty string clears it).

    Example: set_desc(me, 'The lantern glows a steady amber.')
    """
    from realm.core import ops
    target = frame.resolve(obj)
    return target is not None and frame.apply(ops.describe, target, str(text)) is not None


@softfn(group='Objects & attributes')
def teleport_obj(
    frame,
    obj: GameObject | str | None,
    destination: GameObject | str | None,
) -> bool:
    """
    Move an object the executor controls straight to a destination — the
    wizard/admin relocation. Now a thin alias for ``move_to(force=True)``:
    it tunnels past on_check **wards** (a Bound field), but still honors
    the destination's **locks** (its teleport lock included) and requires
    control of the object. A forced arrival still fires ``on_enter``.

    Example: teleport_obj(enactor, 'The Oubliette')
    """
    return frame.move_to(obj, destination, force=True)

@softfn(group='Objects & attributes', readonly=True)
def search_world(frame, tag=None, attr=None, value=None,
                 name=None, limit: int = 100):
    """
    Query the world: search_world(tag='zone:castle'),
    search_world(attr='xp_multiplier'), combinable. Results capped
    (default 100). Protected attributes can't be queried.

    Example: search_world(tag='zone:castle')
    """
    from realm.core.query import _UNSET, find_objects
    if attr is not None and str(attr) in PROTECTED_ATTRS:
        return []
    if attr is not None:
        from realm.core.attrflags import readable_attr
        results = find_objects(
            tag=str(tag) if tag else None,
            attr=str(attr),
            value=value if value is not None else _UNSET,
            name_like=str(name) if name else None,
            limit=max(1, min(int(limit), 500)),
        )
        return [o for o in results
                if readable_attr(o, str(attr), frame.executor)]
    return find_objects(
        tag=str(tag) if tag else None,
        attr=str(attr) if attr else None,
        value=value if value is not None else _UNSET,
        name_like=str(name) if name else None,
        limit=max(1, min(int(limit), 500)),
    )

@softfn(group='Objects & attributes')
def eval_attr(frame, obj, attr_name: str, *args):
    """
    Evaluate an attribute as a SUBROUTINE and return its ``result``.

    Runs with the CALLER's authority — the executor is unchanged —
    with args bound as arg0..argN / %0..%9. Secret attributes respect
    their read gate; errors return None.

    NOT Penn's u(), despite the resemblance (this docstring used to
    claim it was): Penn swaps the executor to the object holding the
    attribute (call_ufun_int -> process_expression(..., ufun->thing,
    caller, ...)), so v() there reads the *attribute owner's* data and
    the call can escalate — which is why Penn gates @function behind a
    power. This runs as the caller and cannot escalate. The practical
    consequence: inside the routine ``me`` is the CALLER, not ``obj``,
    so a shared library routine must resolve its own object by name
    (``get('Quest Warden')``) to read its own attrs. See BACKLOG's
    @function entry for the Penn-semantics library-call mechanism.

    Example: eval_attr(me, 'render_side', n)
    """
    if getattr(frame, '_eval_depth', 0) >= 8:
        return None
    target = frame.resolve(obj)
    if target is None:
        return None
    from realm.core.attrflags import readable_attr
    if str(attr_name) in PROTECTED_ATTRS or not readable_attr(
            target, str(attr_name), frame.executor):
        return None
    code = target.db.get(str(attr_name))
    if not isinstance(code, str) or not code.strip():
        return None

    from realm.scripting.sandbox import (
        ScriptContext,
        ScriptError,
        ScriptSandbox,
    )
    ctx = ScriptContext(
        enactor=frame.enactor,
        executor=frame.executor,
        location=frame.location,
        captures=[str(a) for a in args],
    )
    frame._eval_depth = getattr(frame, '_eval_depth', 0) + 1
    try:
        result, _output = ScriptSandbox().execute(
            code, ctx, functions=frame.to_dict())
    except ScriptError:
        return None
    finally:
        frame._eval_depth -= 1
    return result

@softfn(group='Objects & attributes')
def call(frame, obj, attr_name: str, *args):
    """
    Call an attribute as a METHOD on ``obj`` — runs AS ``obj`` (``me`` is
    obj, ``V()``/``get_attr(me, ...)`` read obj's own data, ``here`` is
    obj's room), with ``enactor`` preserved and args bound as arg0..argN.
    Returns the routine's ``result``.

    Unlike ``eval_attr`` (which runs as the CALLER — a subroutine of
    your own object), ``call`` is a method invocation on another object:
    the shared-service / "function object" form. Allowed when the executor
    CONTROLS ``obj`` (co-owned, admin, or owner) OR the attribute is
    flagged ``public`` (the cross-owner opt-in). Protected attrs are never
    callable; errors return None. Because ``here`` is the target's room,
    reach the caller's scene with ``pemit(enactor, ...)`` or
    ``remit(loc(enactor), ...)``.

    Example: call(get('#' + V('bank_core_id')), 'net_deposit', trim(arg0))
    """
    if getattr(frame, '_eval_depth', 0) >= 8:
        return None
    target = frame.resolve(obj)
    if target is None:
        return None
    attr = str(attr_name)
    if attr in PROTECTED_ATTRS:
        return None
    from realm.core.attrflags import has_attr_flag
    from realm.permissions.locks import controls
    if not (controls(frame.executor, target)
            or has_attr_flag(target, attr, 'public')):
        return None
    code = target.db.get(attr)
    if not isinstance(code, str) or not code.strip():
        return None

    from realm.scripting.sandbox import (
        ScriptContext,
        ScriptError,
        ScriptSandbox,
    )
    ctx = ScriptContext(
        enactor=frame.enactor,
        executor=target,
        location=target.location,
        captures=[str(a) for a in args],
    )
    # Run AS the target: rebind executor/location for the duration so the
    # injected V()/set_attr()/me read the target's own data, then restore.
    # The shared command_queue and persistence carry through, so the
    # routine's pemits and saves flush with the outer script.
    saved_exec, saved_loc = frame.executor, frame.location
    frame.executor, frame.location = target, target.location
    frame._eval_depth = getattr(frame, '_eval_depth', 0) + 1
    try:
        result, _output = ScriptSandbox().execute(
            code, ctx, functions=frame.to_dict())
    except ScriptError:
        return None
    finally:
        frame._eval_depth -= 1
        frame.executor, frame.location = saved_exec, saved_loc
    return result
