"""
Space game specific commands.

Commands for combat, trading, ship operations, etc.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.commands.base import Command, command
from realm.commands.registry import CommandRegistry

if TYPE_CHECKING:
    from realm.commands.context import CommandContext


@command("attack", aliases=["kill", "fight"])
async def cmd_attack(ctx: CommandContext) -> None:
    """
    Attack a target.

    Usage: attack <target>

    Initiates combat with the specified target using the GURPS ruleset.
    """
    if not ctx.args:
        await ctx.send("Attack who?")
        return

    target_name = ctx.args.lower()

    # Find target in room
    if not ctx.player.location:
        await ctx.send("You're not anywhere!")
        return

    target = None
    for obj in ctx.player.location.contents:
        if obj == ctx.player:
            continue
        if obj.name.lower() == target_name or target_name in obj.name.lower():
            target = obj
            break

    if not target:
        await ctx.send(f"You don't see '{ctx.args}' here.")
        return

    # Check if target can be attacked
    if not target.has_tag("npc") and not target.has_tag("player"):
        await ctx.send("You can't attack that.")
        return

    # Get combat system
    from realm.combat.system import get_combat_system

    combat = get_combat_system()
    if not combat:
        await ctx.send("Combat system not available.")
        return

    # Perform attack
    result = await combat.attack(ctx.player, target)

    # Send messages
    if "attacker_msg" in result.messages:
        await ctx.send(result.messages["attacker_msg"])

    # Broadcast to room
    if "others_msg" in result.messages and ctx.player.location:
        for obj in ctx.player.location.contents:
            if obj != ctx.player and obj != target and obj.has_tag("player"):
                # Would send to other players
                pass


@command("status", aliases=["hp", "health"])
async def cmd_status(ctx: CommandContext) -> None:
    """
    Check your status.

    Usage: status

    Shows your current health, credits, and other stats.
    """
    from examples.spacegame.characters import SpaceCharacter

    char = SpaceCharacter(ctx.player)
    await ctx.send(char.get_status_string())


@command("scan", aliases=["sensors"])
async def cmd_scan(ctx: CommandContext) -> None:
    """
    Scan your surroundings.

    Usage: scan [target]

    Without arguments, scans the current location for hostiles and items.
    With a target, provides detailed scan of that target.
    """
    if not ctx.player.location:
        await ctx.send("You're not anywhere to scan!")
        return

    location = ctx.player.location

    if ctx.args:
        # Scan specific target
        target_name = ctx.args.lower()
        for obj in location.contents:
            if obj.name.lower() == target_name or target_name in obj.name.lower():
                await _scan_target(ctx, obj)
                return
        await ctx.send(f"No target matching '{ctx.args}' found.")
        return

    # Scan area
    lines = ["=== SCAN RESULTS ==="]

    # Count objects by type
    hostiles = []
    neutrals = []
    items = []
    ships = []

    for obj in location.contents:
        if obj == ctx.player:
            continue
        if obj.has_tag("exit"):
            continue

        if obj.has_tag("ship"):
            ships.append(obj)
        elif obj.has_tag("npc"):
            # Check if hostile
            if obj.db.get("hostile"):
                hostiles.append(obj)
            else:
                neutrals.append(obj)
        elif obj.has_tag("equipment") or obj.has_tag("thing"):
            items.append(obj)

    if hostiles:
        lines.append(f"HOSTILES: {len(hostiles)}")
        for h in hostiles:
            lines.append(f"  - {h.name}")

    if neutrals:
        lines.append(f"NEUTRALS: {len(neutrals)}")
        for n in neutrals:
            lines.append(f"  - {n.name}")

    if ships:
        lines.append(f"SHIPS: {len(ships)}")
        for s in ships:
            lines.append(f"  - {s.name}")

    if items:
        lines.append(f"ITEMS: {len(items)}")
        for i in items:
            lines.append(f"  - {i.name}")

    if len(lines) == 1:
        lines.append("No significant readings.")

    await ctx.send("\n".join(lines))


async def _scan_target(ctx: CommandContext, target: GameObject) -> None:
    """Perform detailed scan of a target."""
    lines = [f"=== SCAN: {target.name} ==="]

    if target.has_tag("npc") or target.has_tag("player"):
        # Character scan
        hp = target.db.get("hp", 0)
        max_hp = target.db.get("max_hp", 0)
        lines.append(f"Life signs: {hp}/{max_hp}")

        dr = target.db.get("damage_resistance", 0)
        if dr > 0:
            lines.append(f"Armor rating: {dr}")

        if target.has_tag("npc"):
            if target.db.get("hostile"):
                lines.append("Status: HOSTILE")
            else:
                lines.append("Status: Neutral")

    elif target.has_tag("ship"):
        from examples.spacegame.ships import Spaceship
        ship = Spaceship(target)
        lines.append(f"Class: {target.db.get('ship_type', 'Unknown')}")
        lines.append(f"Hull: {ship.hull}/{ship.max_hull}")
        lines.append(f"Shields: {ship.shields}/{ship.max_shields}")
        lines.append(f"Armor: {ship.armor}")

    elif target.has_tag("equipment"):
        lines.append(f"Type: Equipment")
        if target.db.get("damage_dice"):
            lines.append(f"Damage: {target.db.damage_dice} {target.db.get('damage_type', '')}")
        if target.db.get("damage_resistance"):
            lines.append(f"Protection: DR {target.db.damage_resistance}")
        lines.append(f"Value: {target.db.get('cost', 0)} credits")

    # Description
    desc = target.db.get("description")
    if desc:
        lines.append("")
        lines.append(desc[:200])  # Truncate long descriptions

    await ctx.send("\n".join(lines))


@command("buy")
async def cmd_buy(ctx: CommandContext) -> None:
    """
    Buy an item from a shopkeeper.

    Usage: buy <item>

    You must be in a location with a shopkeeper.
    """
    if not ctx.args:
        await ctx.send("Buy what?")
        return

    if not ctx.player.location:
        await ctx.send("You're not anywhere!")
        return

    # Find shopkeeper
    shopkeeper = None
    for obj in ctx.player.location.contents:
        if obj.has_tag("shopkeeper"):
            shopkeeper = obj
            break

    if not shopkeeper:
        await ctx.send("There's no one here to buy from.")
        return

    # For now, just acknowledge the intent
    await ctx.send(f"You ask {shopkeeper.name} about purchasing '{ctx.args}'...")
    # Full implementation would check inventory, prices, etc.


@command("sell")
async def cmd_sell(ctx: CommandContext) -> None:
    """
    Sell an item to a shopkeeper.

    Usage: sell <item>

    You must be in a location with a shopkeeper.
    """
    if not ctx.args:
        await ctx.send("Sell what?")
        return

    if not ctx.player.location:
        await ctx.send("You're not anywhere!")
        return

    # Find shopkeeper
    shopkeeper = None
    for obj in ctx.player.location.contents:
        if obj.has_tag("shopkeeper"):
            shopkeeper = obj
            break

    if not shopkeeper:
        await ctx.send("There's no one here to sell to.")
        return

    # Find item in inventory
    item = None
    for obj in ctx.player.contents:
        if obj.name.lower() == ctx.args.lower() or ctx.args.lower() in obj.name.lower():
            item = obj
            break

    if not item:
        await ctx.send(f"You don't have '{ctx.args}'.")
        return

    await ctx.send(f"You offer {item.name} to {shopkeeper.name}...")
    # Full implementation would handle transaction


@command("use")
async def cmd_use(ctx: CommandContext) -> None:
    """
    Use an item.

    Usage: use <item> [on target]

    Uses an item from your inventory, optionally on a target.
    """
    if not ctx.args:
        await ctx.send("Use what?")
        return

    # Parse "use X on Y"
    args = ctx.args
    target = None
    if " on " in args.lower():
        parts = args.lower().split(" on ", 1)
        args = parts[0].strip()
        target_name = parts[1].strip()
        # Find target
        if ctx.player.location:
            for obj in ctx.player.location.contents:
                if obj.name.lower() == target_name or target_name in obj.name.lower():
                    target = obj
                    break

    # Find item
    item = None
    for obj in ctx.player.contents:
        if obj.name.lower() == args.lower() or args.lower() in obj.name.lower():
            item = obj
            break

    if not item:
        await ctx.send(f"You don't have '{args}'.")
        return

    # Handle specific item types
    if item.has_tag("medical"):
        await _use_medical(ctx, item, target or ctx.player)
    else:
        await ctx.send(f"You're not sure how to use {item.name}.")


async def _use_medical(ctx: CommandContext, item: GameObject, target: GameObject) -> None:
    """Use a medical item."""
    from examples.spacegame.characters import SpaceCharacter
    from realm.combat.system import get_combat_system

    char = SpaceCharacter(target)

    if char.hp >= char.max_hp:
        if target == ctx.player:
            await ctx.send("You're not injured.")
        else:
            await ctx.send(f"{target.name} isn't injured.")
        return

    # Heal based on item
    heal_amount = 10  # Default
    if "surgical" in item.name.lower():
        heal_amount = 25

    combat = get_combat_system()
    if combat:
        actual = await combat.heal(ctx.player, target, heal_amount)
    else:
        actual = char.heal(heal_amount)

    if target == ctx.player:
        await ctx.send(f"You use {item.name} and heal {actual} HP.")
    else:
        await ctx.send(f"You use {item.name} on {target.name}, healing {actual} HP.")


@command("credits", aliases=["money", "wallet"])
async def cmd_credits(ctx: CommandContext) -> None:
    """
    Check your credit balance.

    Usage: credits
    """
    from examples.spacegame.characters import SpaceCharacter

    char = SpaceCharacter(ctx.player)
    await ctx.send(f"You have {char.credits} credits.")


def register_spacegame_commands(registry: CommandRegistry) -> None:
    """Register all space game commands with a registry."""
    registry.register(cmd_attack)
    registry.register(cmd_status)
    registry.register(cmd_scan)
    registry.register(cmd_buy)
    registry.register(cmd_sell)
    registry.register(cmd_use)
    registry.register(cmd_credits)
