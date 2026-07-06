"""
Money, lean: one integer attribute and three functions.

``db.credits`` is the balance; the active GameSystem names the currency
("credits" in the space game, "gold" under D20). No wallets, no coin
objects — money items are a game-design choice softcode can layer on.

Balances never go negative; transfers are atomic-enough (single
process, single loop).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

CREDITS_ATTR = "credits"


def currency_name() -> str:
    """The active game system's currency label (fallback: credits)."""
    from realm.systems.base import get_game_system

    system = get_game_system()
    return system.currency_name if system else "credits"


def get_credits(obj: GameObject) -> int:
    return max(0, int(obj.db.get(CREDITS_ATTR) or 0))


def adjust_credits(obj: GameObject, delta: int) -> bool:
    """
    Add (or remove) money. Fails without side effects if it would go
    negative.
    """
    balance = get_credits(obj) + int(delta)
    if balance < 0:
        return False
    obj.db.set(CREDITS_ATTR, balance)
    return True


def transfer_credits(source: GameObject, dest: GameObject, amount: int) -> bool:
    """Move money between objects; False if source can't afford it."""
    amount = int(amount)
    if amount <= 0:
        return False
    if not adjust_credits(source, -amount):
        return False
    adjust_credits(dest, amount)
    return True


__all__ = [
    "CREDITS_ATTR",
    "currency_name",
    "get_credits",
    "adjust_credits",
    "transfer_credits",
]
