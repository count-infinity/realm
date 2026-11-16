"""
Simulator — an in-process REALM world for integration testing.

It wires the same components a live GameServer does — an in-memory
store, the propagation engine, the softcode ScriptEngine, the command
dispatcher, and a game system — then lets you build a small world and
drive it two ways:

    sim.eval(obj, "pemit(enactor, 'hi')")   # run softcode AS obj
    await sim.do(player, "get sword")        # run a player command

Both go through the real in-game path, so ``sim.seen(player)`` is
exactly the text that player would have received on a live server.

    sim = Simulator()
    room  = sim.room("Cantina")
    zeke  = sim.obj("Zeke", location=room)
    alice = sim.player("Alice", location=room)

    await sim.eval(zeke, "pemit(enactor, 'Welcome, ' + name(enactor))",
                   enactor=alice)
    assert "Welcome, Alice" in sim.seen(alice)
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any

from realm.config.loader import Settings
from realm.core.objects import GameObject
from realm.gateway.session import Session
from realm.persistence.memory import MemoryStore


class Simulator:
    """A live, in-process REALM world for tests and content checks."""

    def __init__(self, *, game_system: Any = None, scripting: bool | None = None,
                 settings: Settings | None = None,
                 features: list[str] | None = None) -> None:
        """Build a world with the server's own ``build_world``.

        ``settings`` configures it like a game's config.py does
        (``Settings(command_sigil='!')``; feature keys go in
        ``Settings(raw={...})``). ``game_system``, ``scripting`` and
        ``features`` are shortcuts for its ``game_system``,
        ``enable_scripting`` and ``features`` (default: every built-in).
        Feature ``on_boot`` hooks run only when a test awaits ``boot()``.
        """
        from realm.features import load
        from realm.server.world import build_world

        overrides: dict[str, Any] = {}
        if game_system is not None:
            overrides["game_system"] = game_system
        if scripting is not None:
            overrides["enable_scripting"] = scripting
        if features is not None:
            overrides["features"] = list(features)
        settings = replace(settings or Settings(), **overrides)
        self.features = load(settings.features)
        self.features.install_registries()
        self.store = MemoryStore()
        # A real session manager, holding the sessions ``player()`` makes,
        # so "who is online" reads the same here as on a server.
        from realm.gateway.session import SessionManager
        self.sessions = SessionManager()
        # Virtual clock: waits fire when the test pumps waits.tick(), not on
        # wall-clock timers — deterministic like the rest of the Simulator.
        self.world = build_world(self.store, settings, defer_timers=True,
                                 features=self.features, sessions=self.sessions)
        self.dispatcher = self.world.dispatcher
        self.engine = self.world.scripts
        self.game_system = self.world.rules

        self._sessions: dict[str, Session] = {}

    @classmethod
    def from_game(cls, game_dir: Any) -> Simulator:
        """The world a game directory's ``config.py`` describes (its
        ``FEATURES``, ``GAME_SYSTEM`` and settings; the directory goes on
        ``sys.path`` so ``game.py`` and ``rules.py`` import). Await
        ``start()`` to run its first boot."""
        from realm.config.loader import load_config
        return cls(settings=load_config(game_dir))

    async def start(self) -> None:
        """Boot as a server does on an empty database: the game's
        ``init_world`` (with this Simulator as its server), role ranks, a
        default start room if none was made, then the features' ``on_boot``
        hooks."""
        from realm.server.world import prepare_world
        await prepare_world(self.world, self, empty=not list(self.store.all_cached()))
        await self.boot()

    # The two things ``init_world(server)`` uses, so a Simulator can host it.

    @property
    def persistence(self) -> MemoryStore:
        return self.store

    @property
    def startup_room(self) -> GameObject | None:
        return self.world.startup_room

    @startup_room.setter
    def startup_room(self, room: GameObject | None) -> None:
        self.world.startup_room = room

    # --- Building the world --------------------------------------------------

    def add(self, obj: GameObject) -> GameObject:
        """Put an already-built object into the world (e.g. a skill_def)."""
        self.store.add(obj)
        return obj

    def room(self, name: str, **attrs: Any) -> GameObject:
        return self._make(name, tags=["room"], attrs=attrs)

    def obj(self, name: str, *, location: GameObject | None = None,
            tags: list[str] | None = None, **attrs: Any) -> GameObject:
        return self._make(name, tags=tags or [], location=location, attrs=attrs)

    def player(self, name: str, *, location: GameObject | None = None,
               **attrs: Any) -> GameObject:
        """Create a player with a live Session (reachable via seen())."""
        p = self._make(name, tags=["player"], location=location, attrs=attrs)
        sess = Session(protocol="test", address="127.0.0.1")
        self.sessions.adopt(sess)
        self.sessions.link_player_to_session(sess, p)
        self._sessions[p.id] = sess
        return p

    def account(self, name: str, *characters: GameObject,
                password: str = "password") -> GameObject:
        """An account owning ``characters`` (made with ``player()``), the
        way logging in links them: each character's session gets the
        account too. ``player()`` alone makes a character with no account."""
        from realm.std.accounts.account import link_character, new_account
        from realm.std.accounts.auth import hash_password
        account = new_account(name, hash_password(password))
        self.store.add(account)
        for character in characters:
            link_character(account, character)
            session = self._sessions.get(character.id)
            if session is not None:
                session.account = account
        return account

    def _make(self, name, *, tags, location=None, attrs=None) -> GameObject:
        from realm.core.inflate import inflate
        obj = inflate({'name': name, 'tags': list(tags), 'attrs': attrs or {}})
        obj.location = location
        self.store.add(obj)
        return obj

    # --- Driving the world ---------------------------------------------------

    async def eval(self, obj: GameObject, code: str, *,
                   enactor: GameObject | None = None) -> tuple:
        """Run softcode AS ``obj`` (the @eval path). Returns (result, error)."""
        if self.engine is None:
            raise RuntimeError("Simulator built with scripting=False")
        return await self.engine.run_code(obj, code, enactor=enactor)

    async def do(self, player: GameObject, command: str) -> None:
        """Run a player command through the real dispatcher."""
        sess = self._sessions.get(player.id)
        if sess is None:
            raise ValueError(f"{player.name} was not created via .player()")
        await self.dispatcher.dispatch(sess, command)

    async def input(self, player: GameObject, line: str) -> None:
        """Feed one line as a live connection does: the features' input
        interceptors first (a sleeper's "You are asleep.", a character
        still in creation), then the dispatcher. ``do`` goes straight to
        the dispatcher."""
        sess = self._sessions.get(player.id)
        if sess is None:
            raise ValueError(f"{player.name} was not created via .player()")
        for _order, interceptor in self.world.input_interceptors:
            if await interceptor(self.world, sess, line):
                return
        await self.dispatcher.dispatch(sess, line)

    async def submit_line(self, player: GameObject, raw: str) -> None:
        """Feed ONE raw client line through the real input path — the same
        ``submit_input`` a live connection uses, so heredoc (multi-line)
        blocks accumulate exactly as they would in-game. A line mid-block
        dispatches nothing; the closing (or an ordinary) line dispatches the
        reconstructed command(s). Use this for build transcripts that contain
        multi-line ``'''`` blocks; ``do`` stays the direct single-command path.
        """
        sess = self._sessions.get(player.id)
        if sess is None:
            raise ValueError(f"{player.name} was not created via .player()")
        sess.submit_input(raw)
        while True:
            try:
                command = sess._input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            await self.dispatcher.dispatch(sess, command)

    # --- Observing -----------------------------------------------------------

    def seen(self, player: GameObject) -> list[str]:
        """Drain and return the messages this player has received."""
        sess = self._sessions.get(player.id)
        if sess is None:
            return []
        out: list[str] = []
        while not sess._output_queue.empty():
            out.append(sess._output_queue.get_nowait())
        return out

    def prompt(self, player: GameObject) -> str | None:
        """The prompt ``player`` would see now (prompts are not messages,
        so ``seen`` never includes them). None when the game shows none."""
        renderer = self.world.prompt_renderer
        if renderer is None:
            return None
        return renderer(player) or None

    def session(self, player: GameObject) -> Session | None:
        return self._sessions.get(player.id)

    async def boot(self) -> None:
        """Run the features' ``on_boot`` hooks, as a server does after loading."""
        await self.features.boot(self.world)

    def close(self) -> None:
        """Tear down every ambient registration this Simulator made."""
        self.world.close()

    def __enter__(self) -> Simulator:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
