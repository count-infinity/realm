"""
Money, lean: one integer attribute and three functions.

``db.credits`` is the balance; the active GameSystem names the currency
("credits" in the space game, "gold" under D20 and Merc). No wallets, no coin
objects — money items are a game-design choice softcode can layer on.

Balances never go negative; transfers are atomic-enough (single
process, single loop). ``split_money`` shares a sum with the party in the
room (``split``, and ``autosplit`` after a kill).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.world import get_world

if TYPE_CHECKING:
    from realm.core.objects import GameObject

CREDITS_ATTR = "credits"


def currency_name() -> str:
    """The active game system's currency label (fallback: credits)."""

    system = get_world().rules
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


def split_money(player: GameObject, amount: int) -> str | None:
    """Share ``amount`` of ``player``'s money with their party in the room
    (ROM's ``split``): an equal share each, the remainder kept by the
    splitter. Returns why it cannot, or None when it was shared. The party
    is the ``social`` feature's (``services["social"]``); without it there
    is nobody to share with."""
    amount = int(amount)
    if amount <= 0:
        return "Split how much?"
    if get_credits(player) < amount:
        return "You don't have that much to split."
    social = get_world().services.get("social")
    party = social.party_members(player) if social is not None else [player]
    members = [m for m in party if m.is_player]
    if len(members) < 2:
        return "Just keep it all."
    share, extra = divmod(amount, len(members))
    if share < 1:
        return "Don't even bother, cheapskate."
    money = currency_name()
    for member in members:
        if member is player:
            continue
        transfer_credits(player, member, share)
        member.msg(f"{player.name} splits {amount} {money}. "
                   f"Your share is {share} {money}.")
    player.msg(f"You split {amount} {money}. Your share is {share + extra} {money}.")
    return None


__all__ = [
    "split_money",
    "CREDITS_ATTR",
    "currency_name",
    "get_credits",
    "adjust_credits",
    "transfer_credits",
]
