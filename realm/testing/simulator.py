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

from typing import Any

from realm.core.objects import GameObject
from realm.core.propagation import get_engine, reset_engine
from realm.gateway.session import Session


class _Store:
    """Minimal in-memory persistence implementing the lookup API the
    engine, commands, and world queries use."""

    def __init__(self) -> None:
        self._cache: dict[str, GameObject] = {}

    async def save(self, obj: GameObject) -> None:
        self._cache[obj.id] = obj

    async def delete(self, obj: GameObject) -> None:
        self._cache.pop(obj.id, None)

    def add(self, obj: GameObject) -> None:
        self._cache[obj.id] = obj

    def unregister(self, obj: GameObject) -> None:
        self._cache.pop(obj.id, None)

    def get_cached(self, obj_id: str) -> GameObject | None:
        return self._cache.get(obj_id)

    def all_cached(self) -> list[GameObject]:
        return list(self._cache.values())

    def find_cached(self, *, tag: str | None = None,
                    name: str | None = None) -> list[GameObject]:
        needle = name.lower() if name is not None else None
        out = []
        for obj in self._cache.values():
            if tag is not None and not obj.has_tag(tag):
                continue
            if needle is not None and obj.name.lower() != needle:
                continue
            out.append(obj)
        return out


class Simulator:
    """A live, in-process REALM world for tests and content checks."""

    def __init__(self, *, game_system: Any = "realm.systems.GurpsSystem",
                 scripting: bool = True) -> None:
        from realm.commands.builtin import register_all_commands
        from realm.core.checks import set_check_resolver, set_skill_defaults
        from realm.persistence.manager import set_active_manager
        from realm.scripting.engine import ScriptEngine, set_script_engine
        from realm.server.dispatcher import CommandDispatcher
        from realm.systems import resolve_game_system, set_game_system

        reset_engine()
        self.store = _Store()
        set_active_manager(self.store)

        # Game system (dotted path / class / instance), installed like the
        # server does: skill defaults + non-combat check resolver.
        self.game_system = resolve_game_system(game_system)
        set_game_system(self.game_system)
        set_skill_defaults(self.game_system.skill_defaults())
        set_check_resolver(self.game_system.resolve_check)

        self.dispatcher = CommandDispatcher()
        register_all_commands(self.dispatcher)
        self.dispatcher.persistence = self.store

        self.engine: ScriptEngine | None = None
        if scripting:
            from realm.core.objects import set_check_hook
            self.engine = ScriptEngine(persistence=self.store)
            # Virtual clock: waits fire when the test pumps tick_waits(), not on
            # wall-clock timers — deterministic like the rest of the Simulator.
            self.engine.defer_waits = True
            get_engine().add_observer(self.engine.handle_action)
            set_script_engine(self.engine)
            set_check_hook(self.engine.run_check_hook)   # on_check interception
            self.engine.dispatcher = self.dispatcher
            self.dispatcher.set_unknown_handler(self.engine.handle_unknown_command)

        self._sessions: dict[str, Session] = {}

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
        sess.link_player(p)
        self._sessions[p.id] = sess
        return p

    def _make(self, name, *, tags, location=None, attrs=None) -> GameObject:
        obj = GameObject(name=name, tags=list(tags), location=location)
        for key, value in (attrs or {}).items():
            obj.db.set(key, value)
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

    def session(self, player: GameObject) -> Session | None:
        return self._sessions.get(player.id)

    def close(self) -> None:
        """Tear down ambient singletons this Simulator installed."""
        from realm.core.objects import set_check_hook
        from realm.persistence.manager import set_active_manager
        from realm.scripting.engine import set_script_engine
        from realm.systems import set_game_system
        if self.engine is not None:
            self.engine.shutdown_waits()   # cancel any pending wait timers
        set_active_manager(None)
        set_script_engine(None)
        set_check_hook(None)
        set_game_system(None)
        reset_engine()

    def __enter__(self) -> Simulator:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
