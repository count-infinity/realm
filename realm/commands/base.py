"""
Base utilities for command implementation.

Provides helper functions for common command patterns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.commands import CommandContext
    from realm.core.objects import GameObject


async def send(ctx: CommandContext, message: str) -> None:
    """Send a message to the command invoker."""
    await ctx.session.send(message)


async def send_to_room(
    ctx: CommandContext,
    message: str,
    exclude_self: bool = True,
) -> None:
    """Send a message to everyone in the player's room."""
    if not ctx.player or not ctx.player.location:
        return

    room = ctx.player.location
    for obj in room.contents:
        if obj.has_tag('player') and obj != ctx.player:
            # Get session for this player
            session = obj.db.get('session_id')
            # Note: In a real implementation, we'd look up the session
            # For now, we use the msg() method which can be overridden
            obj.msg(message)


def find_object(
    ctx: CommandContext,
    name: str,
    *,
    search_room: bool = True,
    search_inventory: bool = True,
    search_exits: bool = False,
) -> GameObject | None:
    """
    Find an object by name from the player's perspective.

    Searches in order:
    1. Inventory (if search_inventory)
    2. Room contents (if search_room)
    3. Exits (if search_exits)

    Returns the first match or None.
    """
    if not ctx.player:
        return None

    name_lower = name.lower()

    # Search inventory
    if search_inventory:
        for obj in ctx.player.contents:
            if obj.name.lower() == name_lower:
                return obj
            # Check aliases
            aliases = obj.db.get('aliases', [])
            if name_lower in [a.lower() for a in aliases]:
                return obj

    # Search room
    if search_room and ctx.player.location:
        for obj in ctx.player.location.contents:
            if obj == ctx.player:
                continue
            if search_exits or not obj.has_tag('exit'):
                if obj.name.lower() == name_lower:
                    return obj
                aliases = obj.db.get('aliases', [])
                if name_lower in [a.lower() for a in aliases]:
                    return obj

    return None


def find_objects(
    ctx: CommandContext,
    name: str,
    *,
    search_room: bool = True,
    search_inventory: bool = True,
) -> list[GameObject]:
    """
    Find all objects matching a name.

    Returns a list of all matches.
    """
    if not ctx.player:
        return []

    matches: list[GameObject] = []
    name_lower = name.lower()

    # Search inventory
    if search_inventory:
        for obj in ctx.player.contents:
            if obj.name.lower() == name_lower:
                matches.append(obj)
            elif name_lower in [a.lower() for a in obj.db.get('aliases', [])]:
                matches.append(obj)

    # Search room
    if search_room and ctx.player.location:
        for obj in ctx.player.location.contents:
            if obj == ctx.player:
                continue
            if not obj.has_tag('exit'):
                if obj.name.lower() == name_lower:
                    matches.append(obj)
                elif name_lower in [a.lower() for a in obj.db.get('aliases', [])]:
                    matches.append(obj)

    return matches


def find_player(ctx: CommandContext, name: str) -> GameObject | None:
    """
    Find a player by name in the current room.
    """
    if not ctx.player or not ctx.player.location:
        return None

    name_lower = name.lower()
    for obj in ctx.player.location.contents:
        if obj.has_tag('player') and obj.name.lower() == name_lower:
            return obj

    return None


def find_exit(ctx: CommandContext, direction: str) -> GameObject | None:
    """
    Find an exit by name or alias.
    """
    if not ctx.player or not ctx.player.location:
        return None

    direction_lower = direction.lower()
    for obj in ctx.player.location.contents:
        if obj.has_tag('exit'):
            if obj.name.lower() == direction_lower:
                return obj
            aliases = obj.db.get('aliases', [])
            if direction_lower in [a.lower() for a in aliases]:
                return obj

    return None


def format_list(items: list[str], conjunction: str = "and") -> str:
    """
    Format a list of items for display.

    Examples:
        [] -> ""
        ["apple"] -> "apple"
        ["apple", "banana"] -> "apple and banana"
        ["apple", "banana", "cherry"] -> "apple, banana, and cherry"
    """
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {conjunction} {items[1]}"
    return f"{', '.join(items[:-1])}, {conjunction} {items[-1]}"
