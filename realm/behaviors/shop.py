"""
ShopkeeperBehavior: the merchant as a behavior, CoffeeMud-style.

The shop's stock IS the shopkeeper's inventory — restocking is a
spawner or softcode dropping goods on the keeper. Prices derive from
each item's ``db.value`` (default 10) times the keeper's markup, and —
because systems compose — the keeper's DISPOSITION toward the buyer
moves the price: persuade the merchant, get a discount; insult them,
pay through the nose (±5% per disposition point, capped ±15%).

    keeper.add_behavior(ShopkeeperBehavior(markup=1.3, buyback=0.4))

Players interact via the ``list``/``buy``/``sell`` commands, which find
the room's shopkeeper by this behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.behaviors import Behavior, BehaviorRegistry

if TYPE_CHECKING:
    from realm.core.objects import GameObject

DEFAULT_VALUE = 10


@BehaviorRegistry.register
class ShopkeeperBehavior(Behavior):
    """
    Marks an NPC as a merchant and prices its wares.

    Params:
        markup (float): sell-to-player multiplier on db.value (default 1.2)
        buyback (float): buy-from-player multiplier (default 0.5)
        no_buy (bool): keeper refuses to buy from players (default False)
    """

    behavior_id = "shopkeeper"

    def _disposition_factor(self, keeper: GameObject, customer: GameObject,
                            *, selling: bool) -> float:
        from realm.core.disposition import get_disposition

        disp = max(-3, min(3, get_disposition(keeper, customer)))
        # Friendly keepers charge less and pay more.
        swing = 0.05 * disp
        return (1.0 - swing) if selling else (1.0 + swing)

    def price_to_buy(self, keeper: GameObject, item: GameObject,
                     customer: GameObject) -> int:
        """What the customer pays the keeper for item."""
        base = int(item.db.get('value') or DEFAULT_VALUE)
        markup = float(self.get_param('markup', 1.2))
        factor = self._disposition_factor(keeper, customer, selling=True)
        return max(1, round(base * markup * factor))

    def price_to_sell(self, keeper: GameObject, item: GameObject,
                      customer: GameObject) -> int:
        """What the keeper pays the customer for item."""
        base = int(item.db.get('value') or DEFAULT_VALUE)
        buyback = float(self.get_param('buyback', 0.5))
        factor = self._disposition_factor(keeper, customer, selling=False)
        return max(1, round(base * buyback * factor))

    def wares(self, keeper: GameObject) -> list[GameObject]:
        return [item for item in keeper.contents
                if not item.has_tag('no_sell') and not item.has_tag('wielded')]


def find_shopkeeper(room: GameObject) -> tuple[GameObject, ShopkeeperBehavior] | None:
    """The room's merchant, if any: (keeper, behavior)."""
    if room is None:
        return None
    for obj in room.contents:
        for behavior in obj.get_behaviors():
            if behavior.behavior_id == ShopkeeperBehavior.behavior_id:
                return obj, behavior
    return None


__all__ = ["ShopkeeperBehavior", "find_shopkeeper", "DEFAULT_VALUE"]
