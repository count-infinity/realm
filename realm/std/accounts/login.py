"""
The login flow: accounts, the character menu, character creation,
entering the world (MUD_PLAN 6.3).

One :class:`Accounts` per world (``world.services["accounts"]``), made when
the world is built. It reads the world's store, sessions, settings and rules
(``world.rules``: a character is built with the game system's chargen steps
when one is installed) and its ``startup_room``.

A connection moves through three states, all on its ``Session``:

1. no account: the welcome screen (``connect``, ``create``, ``who``, ``quit``);
2. an account and no character: the menu (``play``, ``new``, ``delete``,
   ``password``, ``quit``); a question the menu asked (a first character's
   name, the password before a delete) waits in the session's
   ``account_pending`` data;
3. a character: play. ``characters`` returns to 2, ``logout`` to 1.

Character creation is reboot-safe: the step lives in ``db.chargen_step``,
and a character still in creation has its input routed here by an input
interceptor rather than the dispatcher.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from realm.core.action_types import ActionType
from realm.core.propagation import ROOM_TARGET_CHAIN, Action, propagate
from realm.std.accounts import account as accounts_clock
from realm.std.accounts.account import (
    account_of,
    ban_message,
    characters_of,
    sitelocked,
    unlink_character,
)
from realm.std.accounts.auth import AuthService

if TYPE_CHECKING:
    from realm.commands.dispatcher import CommandContext
    from realm.core.objects import GameObject
    from realm.core.world import World
    from realm.gateway.session import Session

logger = logging.getLogger(__name__)

PENDING = "account_pending"
MENU_HELP = ("Commands: play <name>, new <name>, delete <name>, "
             "password <old> <new>, quit")


class Accounts:
    """Logging in, the character menu, creating characters, and the
    welcome screen."""

    def __init__(self, world: World) -> None:
        self.world = world
        self.auth = AuthService(world.store)

    def _setting(self, key: str, default):
        try:
            return self.world.setting(key)
        except (KeyError, AttributeError):
            return default

    # --- the login prompt and the menu ------------------------------------------

    async def handle_login(self, ctx: CommandContext) -> None:
        """Input from a session with no character: the welcome screen, or
        the account's menu."""
        session = ctx.session
        line = (ctx.raw_input or "").strip()
        pending = session.get_data(PENDING)
        if pending:
            session.set_data(PENDING, None)
            await self.answer(session, pending, line)
            return
        args = line.split()
        if not args:
            return
        cmd = args[0].lower()
        if session.account is None:
            if cmd == 'connect' and len(args) >= 3:
                await self.connect(session, args[1], args[2])
            elif cmd == 'create' and len(args) >= 3:
                await self.create(session, args[1], args[2])
            elif cmd == 'quit':
                await self.quit(session)
            elif cmd == 'who':
                await self.who(session)
            else:
                await session.send("Commands: connect <account> <password>, "
                                   "create <account> <password>, who, quit")
            return
        if cmd == 'play' and len(args) >= 2:
            await self.play_named(session, args[1])
        elif cmd == 'new' and len(args) >= 2:
            await self.new_character(session, args[1])
        elif cmd == 'delete' and len(args) >= 2:
            await self.ask_delete(session, args[1])
        elif cmd == 'password' and len(args) >= 3:
            await self.change_password(session, session.account, args[1], args[2])
        elif cmd == 'quit':
            await self.quit(session)
        elif cmd == 'who':
            await self.who(session)
        else:
            await self.show_menu(session)

    async def answer(self, session: Session, pending: tuple, line: str) -> None:
        """The reply to a question the menu asked."""
        kind = pending[0]
        if kind == "first_name":
            if not line:
                session.set_data(PENDING, pending)
                await session.send("Name your first character:")
                return
            if not await self.new_character(session, line.split()[0]):
                session.set_data(PENDING, pending)
        elif kind == "delete":
            await self.delete_character(session, pending[1], line)

    async def quit(self, session: Session) -> None:
        await session.send("Goodbye!")
        await self.world.sessions.destroy_session(session)

    async def connect(self, session: Session, name: str, password: str) -> None:
        """``connect <account> <password>``."""
        account, error = await self.auth.authenticate(name, password)
        if account is None:
            await session.send(error)
            return
        banned = ban_message(account)
        if banned:
            await session.send(banned)
            return
        if not self._setting("ACCOUNT_MULTIPLAY", False):
            await self._take_over(session, account)
        session.account = account
        account.db.last_login = accounts_clock.now()
        account.db.last_address = session.address
        await self.world.store.save(account)
        characters = characters_of(account)
        if len(characters) == 1:                         # Decision D2
            await self.play(session, characters[0])
        else:
            await self.show_menu(session)

    async def _take_over(self, session: Session, account: GameObject) -> None:
        """One account, one connection: an older one is closed."""
        for other in self.world.sessions.all_sessions():
            if other is not session and other.account is account:
                await other.send("Your account has been logged in from elsewhere.")
                await self.world.sessions.destroy_session(other)

    async def create(self, session: Session, name: str, password: str) -> None:
        """``create <account> <password>``: then the first character's name."""
        locked = sitelocked(session.address)
        if locked:
            await session.send(f"New accounts cannot be made from your site: {locked}")
            return
        account, error = await self.auth.create_account(name, password)
        if account is None:
            await session.send(error)
            return
        session.account = account
        account.db.last_login = accounts_clock.now()
        account.db.last_address = session.address
        await self.world.store.save(account)
        session.set_data(PENDING, ("first_name",))
        await session.send(f"\nAccount '{account.name}' created. "
                           "Name your first character:")

    async def show_menu(self, session: Session) -> None:
        """The account's characters and what to do next."""
        account = session.account
        characters = characters_of(account)
        lines = [f"\nAccount: {account.name}"]
        if characters:
            lines.append("Your characters:")
            for char in characters:
                lines.append(f"  {char.name:16} {self.describe(char)}")
        else:
            lines.append("You have no characters yet; 'new <name>' makes one.")
        lines.append(MENU_HELP)
        await session.send("\n".join(lines))

    def describe(self, char: GameObject) -> str:
        """"level 3 warrior", from the attributes the rules system keeps."""
        parts = []
        if char.db.get("level") is not None:
            parts.append(f"level {char.db.get('level')}")
        kind = char.db.get("character_class") or char.db.get("template")
        if kind:
            parts.append(str(kind))
        if char.db.get("chargen_step") is not None:
            parts.append("(unfinished)")
        return " ".join(parts)

    def _named(self, session: Session, name: str) -> GameObject | None:
        want = name.strip().lower()
        return next((c for c in characters_of(session.account)
                     if c.name.lower() == want), None)

    async def play_named(self, session: Session, name: str) -> None:
        char = self._named(session, name)
        if char is None:
            await session.send(f"You have no character called '{name}'.")
            return
        await self.play(session, char)

    async def new_character(self, session: Session, name: str) -> bool:
        """``new <name>``: a character on the account, into chargen."""
        account = session.account
        limit = int(self._setting("MAX_CHARACTERS", 5))
        if len(characters_of(account)) >= limit:
            await session.send(f"An account may hold at most {limit} characters.")
            return False
        rules = self.world.rules
        player, error = await self.auth.create_character(account, name, system=rules)
        if player is None:
            await session.send(error)
            return False
        self._link(session, player)
        await session.send(f"\nCharacter '{player.name}' created.")
        if player.has_tag('god'):
            await session.send(
                "As the first character on this server you have SUPERUSER "
                "powers (builder and admin commands — see 'help').")
        steps = rules.chargen_steps() if rules else []
        if steps:
            player.db.chargen_step = 0
            await self.world.store.save(player)
            await session.send("")
            await session.send(steps[0].prompt(player))
            return True
        await self.enter_world(session, player)
        return True

    async def ask_delete(self, session: Session, name: str) -> None:
        char = self._named(session, name)
        if char is None:
            await session.send(f"You have no character called '{name}'.")
            return
        session.set_data(PENDING, ("delete", char.id))
        await session.send(f"Type your password to delete {char.name} forever:")

    async def delete_character(self, session: Session, char_id: str, password: str) -> None:
        account = session.account
        char = self.world.store.get_cached(char_id)
        if char is None or account_of(char) is not account:
            await self.show_menu(session)
            return
        if not self.auth.check_password(account, password):
            await session.send("Wrong password; nothing was deleted.")
            return
        if char.has_tag('god') and not any(
                o is not char for o in self.world.store.find_cached(tag='god')):
            await session.send(f"{char.name} is the last superuser and cannot be deleted.")
            return
        unlink_character(account, char)
        char.location = None
        await self.world.store.delete(char)
        await self.world.store.save(account)
        await session.send(f"{char.name} is gone.")
        await self.show_menu(session)

    async def change_password(self, session: Session, account: GameObject | None,
                              old: str, new: str) -> None:
        """``password <old> <new>``, from the menu or in play."""
        if account is None:
            await session.send("You are not logged in to an account.")
            return
        if not self.auth.check_password(account, old):
            await session.send("Wrong password; your password is unchanged.")
            return
        if len(new) < 4:
            await session.send("Choose a password of at least 4 characters.")
            return
        self.auth.set_password(account, new)
        await self.world.store.save(account)
        await session.send("Your password has been changed.")

    def _link(self, session: Session, player: GameObject) -> None:
        self.world.sessions.link_player_to_session(session, player)

    async def play(self, session: Session, player: GameObject) -> None:
        """Enter play as ``player``: a character already in another
        session is taken over (only possible with ``ACCOUNT_MULTIPLAY``)."""
        old = self.world.sessions.get_session_by_player(player)
        if old is not None and old is not session:
            await old.send(f"{player.name} has been taken over from elsewhere.")
            self.world.sessions.unlink_player_from_session(old)
        self._link(session, player)

        # A persistent softcode prompt outstanding from before a reboot
        # resumes: the player's next line runs its callback again.
        pending = player.db.get('input_prompt')
        if pending and self.world.scripts is not None:
            self.world.scripts._install_softcode_prompt(
                player, "(resuming...)", pending.get('callback'),
                pending.get('executor'), True)

        # Warn if the character was made under a different rules package
        # (config is boot-time-fixed; a mid-life swap leaves old sheets
        # authored under the wrong rules).
        rules = self.world.rules
        made_under = player.db.get('game_system')
        if made_under and rules and made_under != rules.system_id:
            await session.send(
                f"[!] {player.name} was created under the '{made_under}' "
                f"rules but this server now runs '{rules.system_id}'. "
                "Your character sheet may not match the current rules.")

        # Unfinished chargen resumes where it left off.
        if player.db.get('chargen_step') is not None and rules:
            steps = rules.chargen_steps()
            index = min(int(player.db.get('chargen_step') or 0),
                        max(0, len(steps) - 1))
            await session.send("\nWelcome back — let's finish your character.\n")
            if steps:
                await session.send(steps[index].prompt(player))
            return

        if player.location is None:
            await self.enter_world(session, player)
            return
        await self.announce_connect(player, returning=True)
        await self.show_room(session, player)

    async def leave_character(self, session: Session) -> None:
        """``characters``: the character leaves play as on ``logout``, and
        the connection returns to the account's menu."""
        player = session.player
        if player is not None:
            session.cancel_prompt()
            if player.location is not None:
                action = Action(actor=player, target=player.location,
                                action_type=ActionType.DISCONNECT, chain=ROOM_TARGET_CHAIN)
                action.add_message("room", "{actor} leaves the game.")
                await propagate(action)
            await self.world.store.save(player)
            self.world.sessions.unlink_player_from_session(session)
        if session.account is None:
            await session.send("You are not logged in to an account.")
            return
        await self.show_menu(session)

    # --- character creation -----------------------------------------------------

    async def chargen_interceptor(self, world: World, session: Session, line: str) -> bool:
        """The input interceptor: a character still in creation answers the
        current chargen step instead of reaching the dispatcher."""
        if session.player is None or session.player.db.get('chargen_step') is None:
            return False
        await self.chargen(session, line)
        return True

    async def chargen(self, session: Session, response: str) -> None:
        """
        Drive the game system's chargen flow (Template Method: the loop
        lives here, the steps come from the system). State is
        ``db.chargen_step`` — reboot-safe mid-creation.
        """
        player = session.player
        if response.strip().lower() in ('quit', 'logout'):
            await session.send("Goodbye! Your unfinished character will wait.")
            await self.world.sessions.destroy_session(session)
            return
        rules = self.world.rules
        steps = rules.chargen_steps() if rules else []
        index = int(player.db.get('chargen_step') or 0)

        if not steps or index >= len(steps):
            player.db.delete('chargen_step')
            await self.enter_world(session, player)
            return

        if response.strip():
            advance, feedback = steps[index].handle(player, response)
            await session.send(feedback)
            if advance:
                index += 1
        if index >= len(steps):
            player.db.delete('chargen_step')
            welcome = rules.finish_chargen(player)
            await self.world.store.save(player)
            # Starting kit (a weapon, armor): async companion to
            # finish_chargen, since minting items needs the store.
            await rules.outfit_new_character(player, self.world.store)
            await session.send(welcome)
            await self.enter_world(session, player)
        else:
            player.db.chargen_step = index
            await session.send("")
            await session.send(steps[index].prompt(player))

    # --- entering the world -----------------------------------------------------

    async def enter_world(self, session: Session, player: GameObject) -> None:
        """Place a finished character in the world and announce them."""
        if player.location is None:
            player.location = self.world.startup_room
        await self.world.store.save(player)
        await session.send(f"\nWelcome to the world, {player.name}!\n")
        await self.announce_connect(player, returning=False)
        await self.show_room(session, player)

    async def announce_connect(self, player: GameObject, *, returning: bool) -> None:
        """Tell the player and bystanders that the player has connected."""
        location = player.location
        if location is None:
            return
        verb = "has reconnected" if returning else "arrives"
        action = Action(
            actor=player,
            target=location,
            action_type=ActionType.CONNECT,
            chain=ROOM_TARGET_CHAIN,
            extra={"returning": returning},
        )
        if returning:
            action.add_message("actor", f"\nWelcome back, {player.name}!\n")
        action.add_message("room", f"{{actor}} {verb}.")
        await propagate(action)

    async def show_room(self, session: Session, player: GameObject) -> None:
        """Show the player's room, when the world has ``look``."""
        look = self.world.services.get("look")
        if look is not None:
            await session.send(look.render_room(player.location, player))

    async def who(self, session: Session) -> None:
        """``who`` at the login prompt: who is online."""
        playing = self.world.sessions.playing_sessions()
        await session.send(f"\n{len(playing)} player(s) online:")
        for s in playing:
            if s.player:
                idle = int(s.idle_time)
                await session.send(f"  {s.player.name} (idle {idle}s)")
        await session.send("")

    # --- the welcome screen -----------------------------------------------------

    def welcome_screen(self) -> str:
        """
        The connection welcome screen, by priority:

        1. WELCOME_BANNER (inline in config.py — the most deliberate)
        2. WELCOME_FILE (resolved from the game directory; default
           data/welcome.txt)
        3. The default screen.
        """
        settings = self.world.settings
        if settings.welcome_banner:
            return settings.welcome_banner
        if settings.welcome_file and settings.welcome_file.exists():
            try:
                return settings.welcome_file.read_text(encoding='utf-8')
            except Exception as e:
                logger.warning(f"Failed to read welcome file: {e}")
        return self.default_welcome_screen()

    def default_welcome_screen(self) -> str:
        """The screen a game without its own banner shows."""
        lines = [
            "",
            "=" * 60,
            f"  Welcome to {self.world.settings.game_name}",
            "  Powered by REALM",
            "=" * 60,
            "",
            "Enter 'connect <account> <password>' to log in",
            "Enter 'create <account> <password>' to make an account",
            "",
        ]
        return "\n".join(lines)


__all__ = ["Accounts"]
