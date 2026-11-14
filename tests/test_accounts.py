"""
The ``accounts`` feature (KERNEL_PLAN 7.4): logging in and character
creation are a feature's, not the server's. The server keeps the input
funnel: a session's own prompt, then the features' input interceptors,
then the dispatcher (whose login slot ``feature.login`` fills).
"""

from __future__ import annotations

import pytest

from realm.server.game import GameServer


async def _connect(server):
    out: list[str] = []

    async def writer(msg):
        out.append(msg)

    session = await server.session_manager.create_session(protocol="test", writer=writer)
    await session.flush_output()
    return session, out


@pytest.mark.asyncio
async def test_classic_greets_creates_and_routes_chargen():
    server = GameServer(db_path=":memory:", enable_telnet=False, tick_interval=0)
    await server.start()
    try:
        session, out = await _connect(server)
        assert any("connect <name> <password>" in m for m in out)   # the welcome screen
        await server._on_command(session, "create Bob correcthorse")
        await session.flush_output()
        assert session.player is not None and session.player.name == "Bob"
        assert session.player.db.get("chargen_step") == 0           # GURPS has steps
        out.clear()
        # Mid-creation input goes to chargen (the interceptor), not the
        # dispatcher: quit here keeps the unfinished character.
        await server._on_command(session, "quit")
        await session.flush_output()
        assert any("unfinished character will wait" in m for m in out)
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_without_accounts_the_server_says_so():
    server = GameServer(db_path=":memory:", enable_telnet=False, tick_interval=0,
                        features=["basics", "talk"])
    await server.start()
    try:
        session, out = await _connect(server)
        assert out == ["This world has no login feature installed."]
        await server._on_command(session, "connect Bob correcthorse")
        await session.flush_output()
        assert out[-1] == "This world has no login feature installed."
        assert session.player is None
    finally:
        await server.stop()


def test_interceptors_run_lowest_order_first(world):
    from realm.features import Feature, FeatureSet
    a, b = Feature("alpha"), Feature("beta")

    @a.input_interceptor(order=10)
    async def late(world, session, line):
        return False

    @b.input_interceptor(order=-5)
    async def early(world, session, line):
        return False

    fs = FeatureSet([a, b])
    fs.install_runtime(world)
    assert [fn for _o, fn in world.input_interceptors] == [early, late]
