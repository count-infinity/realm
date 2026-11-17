"""
One-shot softcode waits: ``wait(seconds, command)`` and ``cancel_wait(id)``.

LDMud ``call_out``/``remove_call_out``, MOO ``fork``/``kill_task``. Each wait
is its OWN asyncio task sleeping the exact duration, so a ``wait(0.15, ...)``
fires at 0.15s, not quantized to the heartbeat (see
docs/design/time-and-beats.md, decision 2). Waits are in-memory only, like
MUSH ``@wait``: they don't survive a reboot; :meth:`WaitScheduler.shutdown`
cancels the tasks on stop.

The script engine owns one (``engine.waits``) and gives it the function that
runs a command as an object. In virtual-clock mode (``defer``, which the
Simulator sets) waits spawn no timers: they fire when a test calls
:meth:`WaitScheduler.tick`.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

#: The longest wait a script may schedule, in seconds.
MAX_WAIT = 3600.0


def now() -> float:
    """The clock a wait's due time is kept on (seconds, monotonic): what
    :meth:`WaitScheduler.tick` fires by (tests replace it)."""
    return time.monotonic()


class WaitScheduler:
    """Pending waits, by handle id."""

    def __init__(self, run: Callable[[GameObject, str], Awaitable[None]]) -> None:
        self._run = run
        #: handle -> (due on ``now()``, executor, command, timer task or None)
        self.pending: dict[
            str, tuple[float, GameObject, str, asyncio.Task[None] | None]] = {}
        #: Virtual clock: no real timers; :meth:`tick` fires what is due.
        self.defer: bool = False

    def schedule(self, executor: GameObject, seconds: float, command: str,
                 *, wait_id: str | None = None) -> str:
        """Run ``command`` as ``executor`` *exactly* ``seconds`` from now
        (clamped to 0..MAX_WAIT). Returns the handle id; pass ``wait_id`` to
        register under a caller-chosen id (so ``wait()`` can hand the id
        back before its queued op drains)."""
        seconds = max(0.0, min(float(seconds), MAX_WAIT))
        wait_id = wait_id or uuid.uuid4().hex
        task = None if self.defer else asyncio.ensure_future(self._timer(wait_id, seconds))
        self.pending[wait_id] = (now() + seconds, executor, str(command), task)
        return wait_id

    def cancel(self, wait_id: str, *, by: GameObject | None = None) -> bool:
        """Cancel a pending wait by its handle. When ``by`` is given, only a
        controller of the wait's executor may cancel it (the id alone is not
        authority — it may have been stored in a readable attr)."""
        entry = self.pending.get(wait_id)
        if entry is None:
            return False
        if by is not None:
            from realm.permissions.locks import controls
            if not controls(by, entry[1]):
                return False
        entry = self.pending.pop(wait_id, None)
        if entry is None:
            return False
        if entry[3] is not None:
            entry[3].cancel()
        return True

    async def _timer(self, wait_id: str, seconds: float) -> None:
        """The per-wait timer: sleep the exact duration, then deliver."""
        try:
            if seconds > 0:
                await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            return
        await self._deliver(wait_id)

    async def _deliver(self, wait_id: str) -> None:
        """Run a wait's command once. Atomically claims the entry (pop), so a
        wait can't fire twice even if its timer and :meth:`tick` race."""
        entry = self.pending.pop(wait_id, None)
        if entry is None:
            return
        _at, executor, command, _task = entry
        if executor.is_halted:
            return
        await self._run(executor, command)

    async def tick(self) -> None:
        """Fire any waits already due *now*.

        Production waits fire on their own exact timers; this is the
        deterministic drive for tests (and a catch-up if a timer was
        starved). Only past-deadline waits fire — future ones wait for their
        timer.
        """
        if not self.pending:
            return
        at = now()
        due = [wid for wid, entry in self.pending.items() if entry[0] <= at]
        for wid in due:
            entry = self.pending.get(wid)
            if entry is not None and entry[3] is not None:
                entry[3].cancel()      # stop its timer; we deliver now
            await self._deliver(wid)

    def shutdown(self) -> None:
        """Cancel every pending wait timer (stop/reboot). Idempotent."""
        for _at, _executor, _command, task in list(self.pending.values()):
            if task is not None:
                task.cancel()
        self.pending.clear()


__all__ = ["WaitScheduler", "MAX_WAIT"]
