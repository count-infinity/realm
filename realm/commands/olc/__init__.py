"""
OLC (Online Creation) commands for REALM.

Builder commands for creating and modifying the game world.
All OLC commands start with @ by convention.
"""

from realm.commands.olc.admin import register_admin_commands
from realm.commands.olc.create import register_create_commands
from realm.commands.olc.modify import register_modify_commands
from realm.commands.olc.softcode import register_softcode_commands


def register_olc_commands(dispatcher) -> None:
    """Register all OLC commands with the dispatcher."""
    register_create_commands(dispatcher)
    register_modify_commands(dispatcher)
    register_admin_commands(dispatcher)
    register_softcode_commands(dispatcher)


__all__ = [
    "register_olc_commands",
    "register_create_commands",
    "register_modify_commands",
    "register_admin_commands",
    "register_softcode_commands",
]
