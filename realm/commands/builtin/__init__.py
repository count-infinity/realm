"""
Built-in commands for REALM.

These are the core commands available in every REALM game.
"""

from realm.commands.builtin.communication import register_communication_commands
from realm.commands.builtin.inventory import register_inventory_commands
from realm.commands.builtin.look import register_look_commands
from realm.commands.builtin.manipulation import register_manipulation_commands
from realm.commands.builtin.movement import register_movement_commands
from realm.commands.builtin.utility import register_utility_commands
from realm.commands.olc import register_olc_commands


def register_all_commands(dispatcher) -> None:
    """Register all built-in commands with the dispatcher."""
    register_movement_commands(dispatcher)
    register_communication_commands(dispatcher)
    register_look_commands(dispatcher)
    register_inventory_commands(dispatcher)
    register_manipulation_commands(dispatcher)
    register_utility_commands(dispatcher)
    register_olc_commands(dispatcher)


__all__ = [
    "register_all_commands",
    "register_movement_commands",
    "register_communication_commands",
    "register_look_commands",
    "register_inventory_commands",
    "register_manipulation_commands",
    "register_utility_commands",
    "register_olc_commands",
]
