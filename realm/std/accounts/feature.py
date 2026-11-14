"""
The ``accounts`` feature.

Logging in: the welcome screen, ``connect`` / ``create`` / ``who`` / ``quit``
at the login prompt, character creation from the game system's chargen
steps, and entering the world. Requires nothing; uses ``world.rules`` for
chargen when the world has a game system.
"""

from __future__ import annotations

from realm.features import Feature

feature = Feature(
    'accounts',
    doc='Logging in, character creation and the welcome screen.',
)


@feature.on_install
def _install(world) -> None:
    from realm.std.accounts.login import Accounts
    accounts = Accounts(world)
    world.services["accounts"] = accounts
    # The screen a new connection sees, and `logout` shows again.
    world.dispatcher.welcome_screen = accounts.welcome_screen


@feature.login
async def login(ctx) -> None:
    """Input from a session with no player: the login prompt."""
    from realm.core.world import get_world
    await get_world().services["accounts"].handle_login(ctx)


@feature.input_interceptor
async def chargen(world, session, line) -> bool:
    """A character still in creation answers its chargen step."""
    return await world.services["accounts"].chargen_interceptor(world, session, line)
