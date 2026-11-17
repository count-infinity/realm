"""
The ``accounts`` feature.

Logging in to an account, the character menu, character creation from the
game system's chargen steps, entering the world, account data in softcode,
and account administration (MUD_PLAN step 6; docs/guides/accounts.md).
Requires nothing; uses ``world.rules`` for chargen when the world has a
game system.
"""

from __future__ import annotations

import logging

from realm.features import Feature
from realm.std.accounts import softcode
from realm.std.accounts.admin import cmd_account, cmd_sitelock

feature = Feature(
    'accounts',
    doc='Accounts with several characters, logging in, character creation, bans.',
)

feature.setting(
    "MAX_CHARACTERS", 5,
    "How many characters one account may hold, before its own extra slots "
    "(`@account/slots`, and achievements that grant `characters`).")
feature.setting(
    "ACCOUNT_MULTIPLAY", False,
    "Whether one account may play several of its characters at once (one "
    "connection per character). Off: a second login takes over the first.")

_log = logging.getLogger(__name__)


@feature.on_install
def _install(world) -> None:
    from realm.std.accounts.login import Accounts
    accounts = Accounts(world)
    world.services["accounts"] = accounts
    # The screen a new connection sees, and `logout` shows again.
    world.dispatcher.welcome_screen = accounts.welcome_screen
    if world.sessions is not None:
        world.sessions.on_connect(_refuse_sitelocked)


async def _refuse_sitelocked(session) -> None:
    """A connection from a locked-out site is told why and closed."""
    from realm.core.world import find_world
    from realm.std.accounts.account import sitelocked
    reason = sitelocked(session.address)
    world = find_world()
    if reason and world is not None and world.sessions is not None:
        await session.send(f"Connections from your site are not accepted: {reason}")
        await world.sessions.destroy_session(session)


@feature.on_boot
async def _carry_characters_over(world) -> None:
    """A world saved before accounts: every player with a password and no
    account gets an account of the same name holding that password, and
    the password leaves the character. A no-op once done."""
    from realm.std.accounts.account import (
        find_account,
        link_character,
        new_account,
    )
    store = world.store
    for player in list(store.find_cached(tag='player')):
        password = player.db.get('password')
        if not password or player.db.get('account'):
            continue
        if find_account(player.name) is not None:
            _log.warning(f"Character {player.name} ({player.id}) has its own password but "
                         f"an account called {player.name} already exists; it was not "
                         f"carried over. Give it an account by hand (link it with "
                         f"realm.std.accounts.account.link_character).")
            continue
        account = new_account(player.name, str(password))
        link_character(account, player)
        player.db.delete('password')
        await store.save(account)
        await store.save(player)
        _log.info(f"Made account {account.name} for the character of that name")


@feature.login
async def login(ctx) -> None:
    """Input from a session with no player: the login prompt, or the menu."""
    from realm.core.world import get_world
    await get_world().services["accounts"].handle_login(ctx)


@feature.input_interceptor
async def chargen(world, session, line) -> bool:
    """A character still in creation answers its chargen step."""
    return await world.services["accounts"].chargen_interceptor(world, session, line)


async def cmd_characters(ctx) -> None:
    """
    Leave this character and return to your account's character menu,
    without disconnecting.

    Usage: characters
    """
    from realm.core.world import get_world
    await get_world().services["accounts"].leave_character(ctx.session)


async def cmd_password(ctx) -> None:
    """
    Change your account's password.

    Usage: password <old> <new>
    """
    from realm.core.world import get_world
    from realm.std.accounts.account import account_of
    words = (ctx.args or "").split()
    if len(words) != 2:
        await ctx.session.send("Usage: password <old> <new>")
        return
    account = ctx.session.account or account_of(ctx.player)
    await get_world().services["accounts"].change_password(
        ctx.session, account, words[0], words[1])


feature.command('characters', cmd_characters, aliases=['chars'], category='utility',
                help_text='Return to your character menu', usage='characters')
feature.command('password', cmd_password, category='utility',
                help_text='Change your password', usage='password <old> <new>')
feature.command('@account', cmd_account, category='building', permission='admin',
                help_text='Show, ban, reset, boot an account or give it slots',
                usage='@account[/password|/ban|/unban|/boot|/slots] <name> [...]',
                parse_equals=True)
feature.command('@sitelock', cmd_sitelock, category='building', permission='admin',
                help_text='Lock out an address or prefix',
                usage='@sitelock[/remove|/list] <address-or-prefix> [= reason]',
                parse_equals=True)

feature.softfn(softcode.account_attr, group='Accounts', readonly=True)
feature.softfn(softcode.set_account_attr, group='Accounts')
feature.softfn(softcode.incr_account_attr, group='Accounts')
feature.softfn(softcode.account_characters, group='Accounts', readonly=True)
feature.softfn(softcode.character_limit, group='Accounts', readonly=True)
