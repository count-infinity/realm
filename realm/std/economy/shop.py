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

import logging
from typing import TYPE_CHECKING

from realm.core.behaviors import Behavior
from realm.core.world import get_world

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)

DEFAULT_VALUE = 10


class ShopkeeperBehavior(Behavior):
    """
    Marks an NPC as a merchant and prices its wares.

    Params:
        markup (float): sell-to-player multiplier on db.value (default 1.2)
        buyback (float): buy-from-player multiplier (default 0.5)
        no_buy (bool): keeper refuses to buy from players (default False)
        sells_pets (bool): a pet shop: ``buy`` clones a creature from
            ``pet_stock`` and makes it the buyer's companion (the
            ``companions`` feature; default False)
        pet_stock (list): ids of the creatures a pet shop sells copies of
    """

    behavior_id = "shopkeeper"
    param_spec = {
        'markup': (1.2, 'sale price as a multiple of item value'),
        'buyback': (0.5, 'buy price as a fraction of item value'),
        'sells_pets': (False, 'a pet shop: sells copies of pet_stock as companions'),
        'pet_stock': ([], 'ids of the creatures a pet shop sells copies of'),
    }

    def _disposition_factor(self, keeper: GameObject, customer: GameObject,
                            *, selling: bool) -> float:

        social = get_world().services.get("social")
        disp = (max(-3, min(3, social.get_disposition(keeper, customer)))
                if social is not None else 0)
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
        """What the keeper sells: what it carries, not what it wields or
        wears (tagged ``wielded`` or ``worn``: a converted ROM keeper's
        E-reset gear too), nor anything tagged ``no_sell``."""
        return [item for item in keeper.contents
                if not item.has_tag('no_sell') and not item.has_tag('wielded')
                and not item.has_tag('worn')]

    def pets(self) -> list[GameObject]:
        """The creatures a pet shop sells copies of: its ``pet_stock`` ids
        that name an object (an unknown id is logged and skipped). Empty
        unless ``sells_pets``."""
        if not self.get_param('sells_pets'):
            return []
        store = get_world().store
        found = []
        for ref in self.get_param('pet_stock') or []:
            obj = store.get_cached(str(ref).lstrip('#')) if store is not None else None
            if obj is None:
                logger.warning(f"pet shop: pet_stock names {ref!r}, which is not an "
                               f"object; fix the shopkeeper's pet_stock")
                continue
            found.append(obj)
        return found


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
