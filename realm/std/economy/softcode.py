"""
Softcode functions: Money.

The ``economy`` feature declares each (``feature.py``, with its group and
flags); the first parameter is the run's ``ScriptFrame``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

def credits(frame, obj: GameObject | str | None) -> int:
    """An object's balance.

    Example: credits(enactor) >= 10
    """
    from realm.std.economy.credits import get_credits
    target = frame.resolve(obj)
    return get_credits(target) if target is not None else 0

def adjust_credits(frame, obj: GameObject | str | None, delta: int) -> bool:
    """Mint or burn money on an object the executor controls.

    Example: adjust_credits(me, 100)
    """
    from realm.std.economy.credits import adjust_credits as _adjust
    target = frame.resolve(obj)
    if target is None or not frame.may_mutate(target):
        return False
    if _adjust(target, int(delta)):
        frame.command_queue.append(('save', target, ''))
        return True
    return False

def transfer_credits(
    frame,
    source: GameObject | str | None,
    dest: GameObject | str | None,
    amount: int,
) -> bool:
    """Move money FROM something the executor controls.

    Example: transfer_credits(me, enactor, 25)
    """
    from realm.std.economy.credits import transfer_credits as _transfer
    src = frame.resolve(source)
    dst = frame.resolve(dest)
    if src is None or dst is None or not frame.may_mutate(src):
        return False
    if _transfer(src, dst, int(amount)):
        frame.command_queue.append(('save', src, ''))
        frame.command_queue.append(('save', dst, ''))
        return True
    return False
