"""
Economy commands: credits, list, buy, sell, pay.

Shops are ShopkeeperBehavior NPCs whose stock is their inventory.
``pay`` moves money AND propagates ``event:payment`` — softcode can
react with ON_PAYMENT triggers (the bribed ogre steps aside).
"""

from __future__ import annotations

from realm.behaviors.shop import find_shopkeeper
from realm.commands import CommandContext, CommandDispatcher
from realm.commands.base import find_object
from realm.core.economy import (
    currency_name,
    get_credits,
    transfer_credits,
)
from realm.core.propagation import Action, propagate
from realm.core.search import match_one


async def cmd_credits(ctx: CommandContext) -> None:
    """
    Show your balance.

    Usage: credits (alias: money, balance)
    """
    await ctx.session.send(
        f"You are carrying {get_credits(ctx.player)} {currency_name()}.")


async def cmd_list(ctx: CommandContext) -> None:
    """
    See what the merchant here is selling.

    Usage: list
    """
    if not ctx.player or ctx.player.location is None:
        return
    shop = find_shopkeeper(ctx.player.location)
    if shop is None:
        await ctx.session.send("There's no merchant here.")
        return
    keeper, behavior = shop
    wares = behavior.wares(keeper)
    if not wares:
        await ctx.session.send(f"{keeper.name.capitalize()} has nothing to sell.")
        return
    lines = [f"{keeper.name.capitalize()}'s wares:"]
    for item in wares:
        price = behavior.price_to_buy(keeper, item, ctx.player)
        lines.append(f"  {item.name} — {price} {currency_name()}")
    await ctx.session.send("\n".join(lines))


async def cmd_buy(ctx: CommandContext) -> None:
    """
    Buy from the merchant here.

    Usage: buy <item>
    """
    if not ctx.player or not ctx.args:
        await ctx.session.send("Buy what?")
        return
    if ctx.player.location is None:
        return
    shop = find_shopkeeper(ctx.player.location)
    if shop is None:
        await ctx.session.send("There's no merchant here.")
        return
    keeper, behavior = shop

    item = match_one(ctx.args.strip(), behavior.wares(keeper))
    if item is None:
        await ctx.session.send(
            f"{keeper.name.capitalize()} isn't selling '{ctx.args.strip()}'.")
        return

    price = behavior.price_to_buy(keeper, item, ctx.player)
    if not transfer_credits(ctx.player, keeper, price):
        await ctx.session.send(
            f"You can't afford {item.name} ({price} {currency_name()}; "
            f"you have {get_credits(ctx.player)}).")
        return

    item.location = ctx.player
    await ctx.session.send(
        f"You buy {item.name} for {price} {currency_name()}.")
    ctx.player.location.msg_contents(
        f"{ctx.player.name} buys {item.name} from {keeper.name}.",
        exclude=[ctx.player])


async def cmd_sell(ctx: CommandContext) -> None:
    """
    Sell something you're carrying to the merchant here.

    Usage: sell <item>
    """
    if not ctx.player or not ctx.args:
        await ctx.session.send("Sell what?")
        return
    if ctx.player.location is None:
        return
    shop = find_shopkeeper(ctx.player.location)
    if shop is None:
        await ctx.session.send("There's no merchant here.")
        return
    keeper, behavior = shop
    if behavior.get_param('no_buy'):
        await ctx.session.send(
            f"{keeper.name.capitalize()} isn't buying.")
        return

    item = find_object(ctx, ctx.args.strip(),
                       search_room=False, search_inventory=True)
    if item is None:
        await ctx.session.send(f"You aren't carrying '{ctx.args.strip()}'.")
        return

    price = behavior.price_to_sell(keeper, item, ctx.player)
    if not transfer_credits(keeper, ctx.player, price):
        await ctx.session.send(
            f"{keeper.name.capitalize()} can't afford that right now.")
        return

    item.location = keeper
    await ctx.session.send(
        f"You sell {item.name} for {price} {currency_name()}.")


async def cmd_pay(ctx: CommandContext) -> None:
    """
    Hand over money — and let the world react (ON_PAYMENT triggers,
    behaviors). Bribes are just payments someone was waiting for.

    Usage: pay <amount> to <target>
           pay <target> = <amount>
    """
    if not ctx.player or ctx.player.location is None:
        return

    amount = None
    target_spec = None
    if ctx.left_args and ctx.right_args:
        target_spec = ctx.left_args.strip()
        try:
            amount = int(ctx.right_args.strip())
        except ValueError:
            amount = None
    elif ctx.args and ' to ' in ctx.args.lower():
        idx = ctx.args.lower().index(' to ')
        try:
            amount = int(ctx.args[:idx].strip())
        except ValueError:
            amount = None
        target_spec = ctx.args[idx + 4:].strip()

    if amount is None or amount <= 0 or not target_spec:
        await ctx.session.send("Usage: pay <amount> to <target>")
        return

    target = find_object(ctx, target_spec,
                         search_room=True, search_inventory=False)
    if target is None or target is ctx.player:
        await ctx.session.send(f"You don't see '{target_spec}' here.")
        return

    if not transfer_credits(ctx.player, target, amount):
        await ctx.session.send(
            f"You don't have {amount} {currency_name()}.")
        return

    action = Action(
        actor=ctx.player,
        target=target,
        action_type="event:payment",
        extra={"amount": amount},
    )
    action.add_message("actor",
                       f"You pay {{target}} {amount} {currency_name()}.")
    action.add_message("target",
                       f"{{actor}} pays you {amount} {currency_name()}.")
    action.add_message("room", "{actor} pays {target}.")
    await propagate(action)


def register_economy_commands(dispatcher: CommandDispatcher) -> None:
    from functools import partial
    register = partial(dispatcher.register, category="economy")
    register("credits", cmd_credits, aliases=["money", "balance"],
                        help_text="Show your balance",
                        usage="credits")
    register("list", cmd_list, aliases=["wares"],
                        help_text="See what the merchant here sells",
                        usage="list")
    register("buy", cmd_buy, aliases=["purchase"],
                        help_text="Buy from the merchant here",
                        usage="buy <item>")
    register("sell", cmd_sell,
                        help_text="Sell to the merchant here",
                        usage="sell <item>")
    register("pay", cmd_pay,
                        help_text="Pay someone (softcode sees ON_PAYMENT)",
                        usage="pay <amount> to <target>",
                        parse_equals=True)
