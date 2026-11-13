"""
Softcode functions: Money.

Each function is registered with ``@softfn``; one that takes the run's
``ScriptFrame`` as ``frame`` reads the executor, enactor, store and queue
from it. See ``realm/scripting/registry.py`` for the flags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.scripting.registry import softfn

if TYPE_CHECKING:
    from realm.core.objects import GameObject

@softfn(owner='economy', group='Money', readonly=True)
def credits(frame, obj: GameObject | str | None) -> int:
    """An object's balance.

    Example: credits(enactor) >= 10
    """
    from realm.core.economy import get_credits
    target = frame.resolve(obj)
    return get_credits(target) if target is not None else 0

@softfn(owner='economy', group='Money', harm=True)
def adjust_credits(frame, obj: GameObject | str | None, delta: int) -> bool:
    """Mint or burn money on an object the executor controls.

    Example: adjust_credits(me, 100)
    """
    from realm.core.economy import adjust_credits as _adjust
    target = frame.resolve(obj)
    if target is None or not frame.may_mutate(target):
        return False
    if _adjust(target, int(delta)):
        frame.command_queue.append(('save', target, ''))
        return True
    return False

@softfn(owner='economy', group='Money')
def transfer_credits(
    frame,
    source: GameObject | str | None,
    dest: GameObject | str | None,
    amount: int,
) -> bool:
    """Move money FROM something the executor controls.

    Example: transfer_credits(me, enactor, 25)
    """
    from realm.core.economy import transfer_credits as _transfer
    src = frame.resolve(source)
    dst = frame.resolve(dest)
    if src is None or dst is None or not frame.may_mutate(src):
        return False
    if _transfer(src, dst, int(amount)):
        frame.command_queue.append(('save', src, ''))
        frame.command_queue.append(('save', dst, ''))
        return True
    return False
