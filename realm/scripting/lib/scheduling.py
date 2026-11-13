"""
Softcode functions: Time and scheduling.

Each function is registered with ``@softfn``; one that takes the run's
``ScriptFrame`` as ``frame`` reads the executor, enactor, store and queue
from it. See ``realm/scripting/registry.py`` for the flags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.scripting.registry import softfn

if TYPE_CHECKING:
    from realm.core.objects import GameObject

@softfn(group='Time & scheduling')
def expire(frame, target: GameObject | str | None, seconds: float) -> bool:
    """
    Give an object a lifetime: after ``seconds`` it fires ``ON_EXPIRE``
    and is destroyed by the world tick (a summoned creature, a smoke
    cloud, a temp portal). Unlike ``wait()``, the countdown lives on the
    object and survives across ticks. ``ON_EXPIRE`` may renew the lease
    by calling ``expire`` again. Requires control of the target.

    Example: expire(create_obj('a wisp of smoke'), 30)
    """
    import time as _clock
    tgt = frame.resolve(target)
    if tgt is None or not frame.may_mutate(tgt):
        return False
    tgt.db.set('expires_at', _clock.time() + float(seconds))
    frame.command_queue.append(('save', tgt, ''))
    return True

@softfn(group='Time & scheduling')
def wait(frame, seconds: float, command: str) -> str | None:
    """
    Run a script command as the executor exactly ``seconds`` from now
    (one-shot, its own timer — a 0.15s fuse fires at 0.15s, not quantized
    to the heartbeat; pending waits don't survive a reboot). Returns a
    HANDLE id you can pass to ``cancel_wait`` to call the wait off before
    it fires — a defuse, an abort.

    Example:
        t = wait(30, 'detonate')
        ... set_attr(me, 'fuse', t) ...          # stash the handle
        ... if defused: cancel_wait(get_attr(me, 'fuse'))
    """
    if frame.executor is None:
        return None
    import uuid
    wait_id = uuid.uuid4().hex
    frame.command_queue.append(
        ('wait', frame.executor, (float(seconds), str(command), wait_id)))
    return wait_id

@softfn(group='Time & scheduling')
def cancel_wait(frame, wait_id: str | None) -> bool:
    """
    Cancel a pending wait by the handle ``wait()`` returned, before it
    fires. You must control the object that scheduled it. Returns True if
    the cancellation was queued (a no-op if the handle is unknown or
    already fired).

    Example: cancel_wait(get_attr(me, 'fuse'))
    """
    if not wait_id:
        return False
    frame.command_queue.append(('cancel_wait', frame.executor, str(wait_id)))
    return True

@softfn(takes_frame=False, group='Time & scheduling', readonly=True)
def now() -> int:
    """Current time as epoch seconds — cache expiry, cooldowns.

    Example: now() - get_attr(me, 'lit_at', 0) > 300
    """
    import time
    return int(time.time())
