"""
Economy commands: credits, list, buy, sell, pay, split.

Shops are ShopkeeperBehavior NPCs whose stock is their inventory.
``pay`` moves money AND propagates ``event:payment`` — softcode can
react with ON_PAYMENT triggers (the bribed ogre steps aside).
"""

from __future__ import annotations

from realm.commands import CommandContext
from realm.commands.base import find_object
from realm.core.language import singular_name
from realm.core.propagation import (
    Action,
    deliver_messages,
    gate_action,
)
from realm.core.search import match_one
from realm.core.world import get_world
from realm.std.economy.actions import EconomyAction
from realm.std.economy.credits import (
    currency_name,
    get_credits,
    split_money,
    transfer_credits,
)
from realm.std.economy.shop import find_shopkeeper
from realm.std.items.equipment import take_it_off_first
from realm.std.items.inventory import find_carried


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
    pets = _pets_for_sale(behavior)
    if not wares and not pets:
        await ctx.session.send(f"{keeper.name.capitalize()} has nothing to sell.")
        return
    lines = []
    if pets:
        lines.append("Pets for sale:")
        for pet in pets:
            price = behavior.price_to_buy(keeper, pet, ctx.player)
            mount = " (mount)" if pet.has_tag("mount") else ""
            lines.append(f"  {pet.name}{mount} — {price} {currency_name()}")
    if wares:
        lines.append(f"{keeper.name.capitalize()}'s wares:")
    for item in wares:
        price = behavior.price_to_buy(keeper, item, ctx.player)
        lines.append(f"  {item.name} — {price} {currency_name()}")
    await ctx.session.send("\n".join(lines))


def _pets_for_sale(behavior) -> list:
    """A pet shop's stock, when the world has ``companions`` to bond what
    it sells (MUD_PLAN 13.2); otherwise nothing."""
    pets = behavior.pets()
    if pets and get_world().services.get("companions") is None:
        return []
    return pets


async def _buy_pet(ctx: CommandContext, keeper, behavior, pet) -> None:
    """Buy a copy of ``pet``: the ``companions`` service refuses one past
    the buyer's limit, clones it beside the buyer and bonds it."""
    companions = get_world().services["companions"]
    refusal = companions.bond_refusal(pet, ctx.player)
    if refusal:
        await ctx.session.send(refusal)
        return
    price = behavior.price_to_buy(keeper, pet, ctx.player)
    if not transfer_credits(ctx.player, keeper, price):
        await ctx.session.send(
            f"You can't afford {pet.name} ({price} {currency_name()}; "
            f"you have {get_credits(ctx.player)}).")
        return
    bought = await companions.buy_pet(ctx.player, pet)
    await ctx.session.send(f"You buy {singular_name(bought)} for {price} {currency_name()}. "
                           f"Enjoy your pet.")
    ctx.player.location.msg_contents(
        f"{ctx.player.name} buys {singular_name(bought)} as a pet.", exclude=[ctx.player])


async def cmd_buy(ctx: CommandContext) -> None:
    """
    Buy from the merchant here.

    Usage: buy <item>

    Example:
        buy medkit
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

    pet = match_one(ctx.args.strip(), _pets_for_sale(behavior))
    if pet is not None:
        await _buy_pet(ctx, keeper, behavior, pet)
        return
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

    Example:
        sell scrap
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

    item = find_carried(ctx, ctx.args.strip())
    if item is None:
        await ctx.session.send(f"You aren't carrying '{ctx.args.strip()}'.")
        return
    refusal = take_it_off_first(item)
    if refusal:
        await ctx.session.send(refusal)
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

    Example:
        pay 25 to ogre         (fires the ogre's ON_PAYMENT softcode)
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

    # Before/apply/after: wards may veto the payment BEFORE any money
    # moves; the transfer is the apply step; ON_PAYMENT (and every other
    # reaction) fires after it, seeing the moved money. An insufficient
    # wallet refuses inside apply, reading exactly like a ward veto.
    def _transfer(a):
        if not transfer_credits(ctx.player, target, amount):
            a.block(f"You don't have {amount} {currency_name()}.")

    action = Action(
        actor=ctx.player,
        target=target,
        action_type=EconomyAction.PAYMENT,
        extra={"amount": amount},
    )
    action.add_message("actor",
                       f"You pay {{target}} {amount} {currency_name()}.",
                       success_only=True)
    action.add_message("target",
                       f"{{actor}} pays you {amount} {currency_name()}.",
                       success_only=True)
    action.add_message("room", "{actor} pays {target}.", success_only=True)
    if not await gate_action(action, apply=_transfer,
                             fail_msg="The payment is refused."):
        return
    deliver_messages(action)




async def cmd_split(ctx: CommandContext) -> None:
    """
    Share money with your party here: each gets an equal share and you
    keep what is left over.

    Usage: split <amount>

    Example:
        split 30
    """
    words = (ctx.args or "").strip()
    if not words.isdigit():
        engine = get_world().scripts
        if engine is not None and await engine.handle_unknown_command(ctx):
            return                          # a world $split comes first
        await ctx.session.send("Split how much?")
        return
    refusal = split_money(ctx.player, int(words))
    if refusal:
        await ctx.session.send(refusal)
