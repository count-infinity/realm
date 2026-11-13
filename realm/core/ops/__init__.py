"""
One service function per world operation.

Each world operation (create, destroy, set an attribute, tag, lock, attach
a behavior, rename, relocate, dig, ...) has exactly one implementation
here. A command parses and prints; a softcode function resolves and returns
a bool; both call the same op, and **the op checks authority**.

Rules every op follows:

- ``actor`` comes first. ``actor=None`` means the system itself (expiry,
  load-time sweeps) and skips authority checks, never other refusals.
- An op never parses command strings and never sends output to the actor.
  It raises an :class:`OpError` whose ``.reason`` is a sentence fit to show
  the actor, or returns an :class:`OpResult`.
- A synchronous op mutates in memory and lists what it changed in
  ``OpResult.touched``; the caller persists those. An op that needs the
  store or propagation is ``async`` and saves for itself.
- Every op has a ``check_<op>(actor, ...)`` sibling that raises the same
  errors without mutating. Softcode runs in a worker thread, so a softcode
  function calls ``check_<op>`` to answer at once and queues async ops to
  run on the loop.

Command wrapper::

    try:
        result = ops.tag(ctx.player, target, tag)
    except ops.OpError as err:
        await ctx.session.send(err.reason); return
    for obj in result.touched: await save_object(ctx, obj)

Softcode wrapper::

    try:
        result = ops.tag(frame.executor, target, tag)
    except ops.OpError:
        return False
    for obj in result.touched: frame.touch(obj)
    return True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject


class OpError(Exception):
    """An op refused. ``.reason`` is a sentence fit to show the actor."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class NotAllowed(OpError):  # noqa: N818 — a refusal, not an error
    """The actor lacks authority."""


class Refused(OpError):  # noqa: N818 — a refusal, not an error
    """The target refuses (a safe tag, a system attribute, a player)."""


class Invalid(OpError):  # noqa: N818 — a bad request, not an error
    """A bad argument (unknown lock type, empty name, no such behavior)."""


@dataclass
class OpResult:
    """What an op did. The caller persists ``touched``."""

    value: Any = None
    touched: list[GameObject] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def require_control(actor: GameObject | None, obj: GameObject) -> None:
    """Raise NotAllowed unless ``actor`` controls ``obj`` (system: always)."""
    from realm.permissions.locks import controls
    if actor is not None and not controls(actor, obj):
        raise NotAllowed(f"You don't control {obj.name}.")


def require_place(actor: GameObject | None, location: GameObject | None) -> None:
    """New things may land in the actor itself, the actor's room, or a
    location the actor controls."""
    if actor is None or location is None:
        return
    if location is actor or location is actor.location:
        return
    require_control(actor, location)


def _principal_holds(actor: GameObject | None, entitlement: str) -> bool:
    """Does the responsible principal behind ``actor`` hold ``entitlement``?

    Walks the owner chain like softcode's HARM gate: the entitlement
    anywhere allows; a mortal player or guest as the principal denies; an
    unowned world object or NPC is trusted by construction."""
    from realm.permissions import has_entitlement
    node, depth = actor, 0
    while node is not None and depth < 5:
        if has_entitlement(node, entitlement):
            return True
        if node.is_player or node.has_tag('guest'):
            return False
        node = node.owner
        depth += 1
    return True


def may_build(actor: GameObject | None) -> bool:
    """May ``actor`` attach, detach or configure behaviors? (BUILD)"""
    from realm.permissions.entitlements import BUILD
    return actor is None or _principal_holds(actor, BUILD)


from realm.core.ops.attrs import (  # noqa: E402
    check_clear_keyid,
    check_clear_lock,
    check_del_attr,
    check_set_attr,
    check_set_keyid,
    check_set_lock,
    check_tag,
    check_untag,
    clear_keyid,
    clear_lock,
    del_attr,
    set_attr,
    set_keyid,
    set_lock,
    tag,
    untag,
)
from realm.core.ops.behaviors import (  # noqa: E402
    attach_behavior,
    check_attach_behavior,
    check_configure_behavior,
    check_detach_behavior,
    configure_behavior,
    detach_behavior,
)
from realm.core.ops.exits import (  # noqa: E402
    check_dig,
    check_link,
    check_open_exit,
    check_pair,
    check_relocate,
    check_unlink,
    check_unpair,
    dig,
    link,
    open_exit,
    pair,
    relocate,
    unlink,
    unpair,
)
from realm.core.ops.objects import (  # noqa: E402
    check_chown,
    check_clone,
    check_create,
    check_describe,
    check_destroy,
    check_rename,
    chown,
    clone,
    create,
    describe,
    destroy,
    rename,
)
from realm.core.ops.sessions import boot, check_boot  # noqa: E402

__all__ = [
    "OpError", "NotAllowed", "Refused", "Invalid", "OpResult",
    "require_control", "require_place", "may_build",
    "create", "check_create", "clone", "check_clone", "destroy", "check_destroy",
    "rename", "check_rename", "describe", "check_describe", "chown", "check_chown",
    "set_attr", "check_set_attr", "del_attr", "check_del_attr",
    "tag", "check_tag", "untag", "check_untag",
    "set_lock", "check_set_lock", "clear_lock", "check_clear_lock",
    "set_keyid", "check_set_keyid", "clear_keyid", "check_clear_keyid",
    "attach_behavior", "check_attach_behavior", "detach_behavior",
    "check_detach_behavior", "configure_behavior", "check_configure_behavior",
    "relocate", "check_relocate", "dig", "check_dig", "open_exit", "check_open_exit",
    "link", "check_link", "unlink", "check_unlink", "pair", "check_pair",
    "unpair", "check_unpair", "boot", "check_boot",
]
