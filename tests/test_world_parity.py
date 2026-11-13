"""
The live server and the Simulator build the world with the same function
(KERNEL_PLAN step 2.2), so a test cannot pass on wiring the live game lacks.

Each side is snapshotted while it is up, then torn down: the propagation
engine is a module singleton, so the two cannot be compared side by side.
"""

from __future__ import annotations

from dataclasses import dataclass

from realm.combat.manager import get_combat_manager
from realm.core.propagation import get_engine
from realm.scripting.functions import ScriptFrame
from realm.server.game import GameServer
from realm.testing import Simulator


@dataclass
class Wiring:
    commands: set[str]
    observers: set[str]
    ruleset: type | None
    softcode_names: set[str]


def _qualname(fn) -> str:
    target = getattr(fn, "__func__", fn)
    return f"{target.__module__}.{target.__qualname__}"


def _snapshot(dispatcher, store) -> Wiring:
    manager = get_combat_manager()
    return Wiring(
        commands=set(dispatcher._commands),
        observers={_qualname(o) for o in get_engine()._observers},
        ruleset=type(manager.combat_system.ruleset) if manager else None,
        softcode_names=set(ScriptFrame(persistence=store).to_dict()),
    )


async def test_server_and_simulator_are_wired_alike():
    server = GameServer(db_path=":memory:", enable_telnet=False)
    await server.start()
    try:
        live = _snapshot(server.dispatcher, server.persistence)
    finally:
        await server.stop()

    sim = Simulator()
    try:
        simulated = _snapshot(sim.dispatcher, sim.store)
    finally:
        sim.close()

    assert simulated.commands == live.commands
    assert simulated.observers == live.observers
    assert live.ruleset is not None
    assert simulated.ruleset is live.ruleset
    assert simulated.softcode_names == live.softcode_names


async def test_closing_the_world_undoes_its_registrations():
    sim = Simulator()
    sim.close()
    assert get_engine()._observers == []
    assert get_combat_manager() is None
