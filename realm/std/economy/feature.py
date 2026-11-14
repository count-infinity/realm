"""
The ``economy`` feature.

Money, shops and payment.
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.economy import softcode
from realm.std.economy.actions import EconomyAction
from realm.std.economy.commands import (
    cmd_buy,
    cmd_credits,
    cmd_list,
    cmd_pay,
    cmd_sell,
)
from realm.std.economy.shop import ShopkeeperBehavior

feature = Feature(
    'economy',
    requires=['items'],
    doc='Money, shops and payment.',
)

feature.command(
    'buy',
    cmd_buy,
    aliases=['purchase'],
    category='economy',
    help_text='Buy from the merchant here',
    usage='buy <item>',
)
feature.command(
    'sell',
    cmd_sell,
    category='economy',
    help_text='Sell to the merchant here',
    usage='sell <item>',
)
feature.command(
    'list',
    cmd_list,
    aliases=['wares'],
    category='economy',
    help_text='See what the merchant here sells',
    usage='list',
)
feature.command(
    'pay',
    cmd_pay,
    category='economy',
    help_text='Pay someone (softcode sees ON_PAYMENT)',
    usage='pay <amount> to <target>',
    parse_equals=True,
)
feature.command(
    'credits',
    cmd_credits,
    aliases=['money', 'balance'],
    category='economy',
    help_text='Show your balance',
    usage='credits',
)

feature.behavior(ShopkeeperBehavior)



feature.event(EconomyAction.PAYMENT, hook="PAYMENT", doc="this object was paid",
              payload={"amount": "the sum paid"})


# --- softcode ------------------------------------------------------------------

feature.softfn(softcode.credits, group='Money', readonly=True)
feature.softfn(softcode.adjust_credits, group='Money', harm=True)
feature.softfn(softcode.transfer_credits, group='Money')


@feature.on_install
def _offer_money(world) -> None:
    """Other features read and move money through
    ``world.services["economy"]`` (``get_credits``, ``transfer_credits``,
    ``currency_name``) when ``economy`` is in the world."""
    from realm.std.economy import credits
    world.services["economy"] = credits
