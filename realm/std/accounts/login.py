"""
The login flow: connect and create, character creation, entering the world.

One :class:`Accounts` per world (``world.services["accounts"]``), made when
the world is built. It reads the world's store, sessions, settings and rules
(``world.rules``: a character is built with the game system's chargen steps
when one is installed) and its ``startup_room``.

Character creation is reboot-safe: the step lives in ``db.chargen_step``,
and a character still in creation has its input routed here by an input
interceptor rather than the dispatcher.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from realm.core.action_types import ActionType
from realm.core.propagation import ROOM_TARGET_CHAIN, Action, propagate
from realm.std.accounts.auth import AuthService

if TYPE_CHECKING:
    from realm.commands.dispatcher import CommandContext
    from realm.core.objects import GameObject
    from realm.core.world import World
    from realm.gateway.session import Session

logger = logging.getLogger(__name__)


class Accounts:
    """Logging in, creating characters, and the welcome screen."""

    def __init__(self, world: World) -> None:
        self.world = world
        self.auth = AuthService(world.store)

    # --- the login prompt -------------------------------------------------------

    async def handle_login(self, ctx: CommandContext) -> None:
        """Input from a session with no player."""
        args = ctx.args.split()
        if not args:
            return
        cmd = args[0].lower()
        if cmd == 'connect' and len(args) >= 3:
            await self.connect(ctx.session, args[1], args[2])
        elif cmd == 'create' and len(args) >= 3:
            await self.create(ctx.session, args[1], args[2])
        elif cmd == 'quit':
            await ctx.session.send("Goodbye!")
            await self.world.sessions.destroy_session(ctx.session)
        elif cmd == 'who':
            await self.who(ctx.session)
        else:
            await ctx.session.send(
                "Commands: connect <name> <password>, create <name> <password>, who, quit"
            )

    async def connect(self, session: Session, name: str, password: str) -> None:
        """``connect <name> <password>``."""
        player, error = await self.auth.authenticate(name, password)
        if player is None:
            await session.send(error)
            return

        self.world.sessions.link_player_to_session(session, player)

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

        await self.announce_connect(player, returning=True)
        await self.show_room(session, player)

    async def create(self, session: Session, name: str, password: str) -> None:
        """``create <name> <password>``."""
        rules = self.world.rules
        player, error = await self.auth.create_account(name, password, system=rules)
        if player is None:
            await session.send(error)
            return

        self.world.sessions.link_player_to_session(session, player)
        await session.send(f"\nCharacter '{name}' created.")
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
            return

        await self.enter_world(session, player)

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
            "Enter 'connect <name> <password>' to log in",
            "Enter 'create <name> <password>' to create a new character",
            "",
        ]
        return "\n".join(lines)


__all__ = ["Accounts"]
