"""
MUD_PLAN step 9: operating a live game.

Idle and link-dead sessions, flood control, presence in softcode and
``who``, ``@wall`` / ``@shutdown`` / ``@reboot``, ``@snoop`` and
``@freeze``, backup and restore, and schema migrations.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3

import pytest

from realm.config.loader import Settings
from realm.server.game import GameServer
from realm.testing import Simulator
from tests.test_accounts import Instant, _client


@pytest.fixture
def clock(monkeypatch):
    now = [50_000.0]
    monkeypatch.setattr("realm.gateway.session.clock", lambda: now[0])
    return now


async def _server(**overrides):
    srv = GameServer(db_path=":memory:", enable_telnet=False, tick_interval=0,
                     game_system=Instant, **overrides)
    await srv.start()
    return srv


def _alive(srv, client) -> bool:
    return client.session.id in [s.id for s in srv.session_manager.all_sessions()]


async def _player(srv, account, name, address="127.0.0.1"):
    c = await _client(srv, address=address)
    await c.send(f"create {account} correcthorse")
    await c.send(name)
    return c


# --- idle and link-dead ---------------------------------------------------------------


class TestIdleAndLinkdead:

    async def test_an_idle_session_is_closed_but_admins_are_exempt(self, clock):
        srv = await _server(idle_timeout=10)
        try:
            boss = await _player(srv, "root", "Boss")         # the superuser
            ann = await _player(srv, "ann", "Ann", "10.0.0.2")
            clock[0] += 9 * 60
            await srv._reap()
            assert _alive(srv, ann)
            clock[0] += 2 * 60
            await srv._reap()
            assert not _alive(srv, ann)
            assert any("idle" in line for line in ann.out)
            assert _alive(srv, boss)
            player = srv.persistence.find_cached(tag="player", name="Ann")[0]
            assert not player.has_tag("linkdead")             # a timeout is a quit
        finally:
            await srv.stop()

    async def test_a_dropped_link_waits_in_the_room_then_leaves(self, clock):
        srv = await _server()
        try:
            ann = await _player(srv, "ann", "Ann")
            bob = await _player(srv, "bob", "Bob", "10.0.0.2")
            player = ann.player
            room = player.location
            await srv.session_manager.connection_lost(ann.session)   # the line drops
            await bob.session.flush_output()
            assert player.has_tag("linkdead") and player.location is room
            assert any("has lost their link" in line for line in bob.out)
            out = await bob.send("look")
            assert "Ann (linkdead)" in out
            clock[0] += 121
            await srv._reap()
            await bob.session.flush_output()
            assert not player.has_tag("linkdead")
            assert any("Ann has disconnected" in line for line in bob.out)
        finally:
            await srv.stop()

    async def test_reconnecting_in_time_resumes_in_place(self, clock):
        srv = await _server()
        try:
            ann = await _player(srv, "ann", "Ann")
            player = ann.player
            await srv.session_manager.connection_lost(ann.session)
            clock[0] += 60
            again = await _client(srv)
            out = await again.send("connect ann correcthorse")
            assert again.player is player and not player.has_tag("linkdead")
            assert "Welcome back" in out
        finally:
            await srv.stop()

    async def test_quit_is_not_linkdead(self, clock):
        srv = await _server()
        try:
            ann = await _player(srv, "ann", "Ann")
            player = ann.player
            await ann.send("quit")
            assert not player.has_tag("linkdead")
        finally:
            await srv.stop()

    async def test_a_fighter_keeps_fighting_when_the_link_drops(self, clock):
        srv = await _server()
        try:
            ann = await _player(srv, "ann", "Ann")
            player = ann.player
            player.db.hp, player.db.max_hp = 20, 20
            from realm.core.objects import GameObject
            wolf = GameObject("wolf", tags=["npc"], location=player.location)
            wolf.db.hp, wolf.db.max_hp = 20, 20
            await srv.persistence.save(wolf)
            combat = srv.world.services["combat"]
            encounter = await combat.initiate(wolf, player)
            await srv.session_manager.connection_lost(ann.session)
            assert player.has_tag("linkdead")
            assert encounter.get(player.id) is not None      # still in the fight
            combat.stop_all()
        finally:
            await srv.stop()


# --- flood control ---------------------------------------------------------------------


class TestFlood:

    async def _session(self, sim):
        manager = sim.world.sessions
        out, closed = [], []

        async def writer(text):
            out.append(text)

        session = await manager.create_session(protocol="test", writer=writer)
        session.set_closer(lambda: closed.append(True))
        return session, out, closed

    def _queued(self, session) -> int:
        n = 0
        while True:
            try:
                session._input_queue.get_nowait()
            except asyncio.QueueEmpty:
                return n
            n += 1

    async def test_a_burst_then_the_rate(self, clock):
        sim = Simulator(settings=Settings(command_rate=2, command_burst=3))
        try:
            session, out, _closed = await self._session(sim)
            for n in range(6):
                session.submit_input(f"say {n}")
            assert self._queued(session) == 3
            await session.flush_output()
            assert sum("too fast" in line for line in out) == 1   # one warning
            clock[0] += 1.0                                  # two more tokens
            for n in range(3):
                session.submit_input(f"say {n}")
            assert self._queued(session) == 2
        finally:
            sim.close()

    async def test_a_sustained_flood_is_disconnected_and_logged(self, clock, caplog):
        sim = Simulator(settings=Settings(command_rate=1, command_burst=2,
                                          flood_disconnect_seconds=5))
        try:
            session, out, closed = await self._session(sim)
            with caplog.at_level(logging.WARNING):
                for _ in range(8):                       # 1.67 lines a second: over, but
                    session.submit_input("spam")         # less than five seconds of it
                    clock[0] += 0.6
                assert not closed
                for _ in range(12):
                    session.submit_input("spam")
                    clock[0] += 0.6
                for _ in range(5):
                    await asyncio.sleep(0)
            assert closed
            assert any("flood" in r.message.lower() for r in caplog.records)
        finally:
            sim.close()

    async def test_a_test_harness_session_is_not_limited(self, clock):
        sim = Simulator()
        try:
            session = sim.session(sim.player("Ann", location=sim.room("Hall")))
            for n in range(50):
                session.submit_input(f"line {n}")
            assert self._queued(session) == 50
        finally:
            sim.close()

    async def test_rate_zero_is_off(self, clock):
        sim = Simulator(settings=Settings(command_rate=0))
        try:
            session, _out, _closed = await self._session(sim)
            for n in range(50):
                session.submit_input(f"line {n}")
            assert self._queued(session) == 50
        finally:
            sim.close()


# --- presence -----------------------------------------------------------------------------


class TestPresence:

    async def test_online_players_and_idle_seconds(self, clock):
        sim = Simulator()
        try:
            room = sim.room("Hall")
            ann = sim.player("Ann", location=room)
            sim.player("Bob", location=room)
            sim.obj("Gus", tags=["player"])                  # offline
            clock[0] += 30
            sim.session(ann).touch()
            clock[0] += 5
            result, _e = await sim.eval(ann, "result = sorted(name(p) for p in online_players())")
            assert result == ["Ann", "Bob"]
            result, _e = await sim.eval(ann, "result = idle_seconds(me)")
            assert result == 5
            result, _e = await sim.eval(ann, "result = idle_seconds(get('Gus'))")
            assert result is None
        finally:
            sim.close()

    async def test_who_shows_idle_marks_and_hides_the_unseen(self, clock):
        sim = Simulator()
        try:
            room = sim.room("Hall")
            ann = sim.player("Ann", location=room)
            bob = sim.player("Bob", location=room)
            ghost = sim.player("Ghost", location=room)
            ghost.add_tag("invisible")
            await sim.do(bob, "afk tea")
            sim.world.services["who"].fields.append(
                lambda viewer, player: "the Brave" if player.name == "Ann" else None)
            clock[0] += 125
            sim.seen(ann)
            await sim.do(ann, "who")
            out = "\n".join(sim.seen(ann))
            assert "Ann" in out and "the Brave" in out
            assert "Bob" in out and "afk" in out.lower()
            assert "Ghost" not in out
            assert "2m" in out
        finally:
            sim.close()


# --- announce and stop ------------------------------------------------------------------------


class TestStopping:

    async def test_wall_reaches_every_session(self):
        srv = await _server()
        try:
            boss = await _player(srv, "root", "Boss")
            ann = await _player(srv, "ann", "Ann", "10.0.0.2")
            await boss.send("@wall The server restarts tonight.")
            await ann.session.flush_output()
            assert any("The server restarts tonight." in line for line in ann.out)
        finally:
            await srv.stop()

    async def test_shutdown_counts_down_saves_and_stops(self):
        srv = await _server()
        try:
            boss = await _player(srv, "root", "Boss")
            ann = await _player(srv, "ann", "Ann", "10.0.0.2")
            await boss.send("@shutdown 1 = maintenance")
            await ann.session.flush_output()
            assert any("shutting down in 1 second" in line and "maintenance" in line
                       for line in ann.out)
            for _ in range(40):
                if not srv._running:
                    break
                await asyncio.sleep(0.05)
            assert not srv._running and srv.exit_code == 0
        finally:
            if srv._running:
                await srv.stop()

    async def test_shutdown_can_be_cancelled(self):
        srv = await _server()
        try:
            boss = await _player(srv, "root", "Boss")
            ann = await _player(srv, "ann", "Ann", "10.0.0.2")
            await boss.send("@shutdown 600")
            out = await boss.send("@shutdown/cancel")
            assert "cancelled" in out.lower()
            await asyncio.sleep(0.05)
            assert srv._running
            await ann.session.flush_output()
            assert any("cancelled" in line.lower() for line in ann.out)
            assert "nothing to cancel" in (await boss.send("@shutdown/cancel")).lower()
        finally:
            await srv.stop()

    async def test_reboot_exits_with_the_restart_status(self):
        from realm.server.game import REBOOT_EXIT_CODE
        srv = await _server()
        try:
            boss = await _player(srv, "root", "Boss")
            await boss.send("@reboot 0")
            for _ in range(40):
                if not srv._running:
                    break
                await asyncio.sleep(0.05)
            assert not srv._running and srv.exit_code == REBOOT_EXIT_CODE != 0
        finally:
            if srv._running:
                await srv.stop()

    async def test_an_announcement_ends_with_one_prompt(self):
        """BACKLOG (first hour): ``@shutdown`` and ``@wall`` wrote the
        typist's prompt twice, once after the announcement (flushed at once)
        and once after the command. What the connection is written, in
        order, is the announcement and then one prompt."""
        srv = await _server()
        try:
            boss = await _player(srv, "root", "Boss")
            boss.session.set_prompt_writer(lambda text: boss.out.append(f"PROMPT {text}"))
            for line, said in (("@wall hi", "*** Boss announces: hi ***"),
                               ("@shutdown 600", "shutting down in 600 seconds"),
                               ("@shutdown/cancel", "cancelled by Boss")):
                start = len(boss.out)
                await boss.send(line)
                written = boss.out[start:]
                assert len(written) == 2 and said in written[0], (line, written)
                assert written[1].startswith("PROMPT "), (line, written)
            start = len(boss.out)
            await boss.send("")                          # a line that prints nothing
            assert [w for w in boss.out[start:] if w.startswith("PROMPT ")] != []
        finally:
            await srv.stop()

    async def test_mortals_may_not(self):
        srv = await _server()
        try:
            await _player(srv, "root", "Boss")
            ann = await _player(srv, "ann", "Ann", "10.0.0.2")
            for line in ("@wall hi", "@shutdown 5", "@reboot", "@snoop Boss", "@freeze Boss"):
                assert "Permission denied." in await ann.send(line)
        finally:
            await srv.stop()


# --- snoop and freeze ---------------------------------------------------------------------------


class TestSnoopAndFreeze:

    def _world(self, sim):
        room = sim.room("Hall")
        boss = sim.player("Boss", location=room)
        boss.add_tag("admin")
        bob = sim.player("Bob", location=sim.room("Dock"))
        return boss, bob

    async def test_snoop_echoes_and_is_logged(self, caplog):
        sim = Simulator()
        try:
            boss, bob = self._world(sim)
            with caplog.at_level(logging.INFO, logger="realm.admin"):
                await sim.do(boss, "@snoop bob")
            assert any("Boss" in r.message and "Bob" in r.message for r in caplog.records)
            sim.seen(boss)
            bob.msg("The tide turns.")
            assert any("Bob" in line and "The tide turns." in line for line in sim.seen(boss))
            await sim.do(boss, "@snoop")
            sim.seen(boss)
            bob.msg("Again.")
            assert not any("Again." in line for line in sim.seen(boss))
        finally:
            sim.close()

    async def test_freeze_and_thaw(self):
        sim = Simulator()
        try:
            boss, bob = self._world(sim)
            await sim.do(boss, "@freeze bob")
            assert bob.has_tag("frozen")
            sim.seen(bob)
            await sim.input(bob, "look")
            assert sim.seen(bob) == ["You are frozen and cannot act."]
            await sim.do(boss, "@thaw bob")
            await sim.input(bob, "look")
            assert any("Dock" in line for line in sim.seen(bob))
        finally:
            sim.close()


# --- backup and restore --------------------------------------------------------------------------


async def _filled_db(path, n):
    from realm.core.objects import GameObject
    from realm.persistence.manager import PersistenceManager
    store = PersistenceManager(path)
    await store.initialize()
    for i in range(n):
        await store.save(GameObject(f"thing {i}", tags=["thing"]))
    return store


def _count(path) -> int:
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0]


class TestBackup:

    async def test_a_backup_during_writes_restores_to_the_same_count(self, tmp_path):
        from realm.persistence.backup import backup_database, restore_database
        live = tmp_path / "game.db"
        store = await _filled_db(live, 50)
        try:
            from realm.core.objects import GameObject

            async def writer():
                for i in range(50):
                    await store.save(GameObject(f"late {i}", tags=["thing"]))
                    await asyncio.sleep(0)

            task = asyncio.create_task(writer())
            copy = await asyncio.to_thread(backup_database, live, tmp_path / "snap.db")
            await task
            with sqlite3.connect(copy) as conn:
                assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            taken = _count(copy)
            assert 50 <= taken <= 100
        finally:
            await store.close()
        target = tmp_path / "restored.db"
        restore_database(copy, target)
        assert _count(target) == taken

    def test_default_name_and_pruning(self, tmp_path):
        import time

        from realm.persistence.backup import backup_database, prune_backups
        live = tmp_path / "data" / "game.db"
        live.parent.mkdir()
        sqlite3.connect(live).execute("CREATE TABLE objects (id TEXT)").connection.close()
        made = []
        for _ in range(4):
            made.append(backup_database(live))
            time.sleep(0.01)
        assert all(p.parent == live.parent / "backups" and p.name.startswith("game-")
                   for p in made)
        removed = prune_backups(live, keep=2)
        assert len(removed) == 2
        assert sorted((live.parent / "backups").iterdir()) == sorted(made[-2:])

    def test_restore_refuses_while_the_server_runs(self, tmp_path):
        import os

        from realm.persistence.backup import restore_database
        from realm.persistence.pidfile import ServerRunningError
        live = tmp_path / "game.db"
        snap = tmp_path / "snap.db"
        sqlite3.connect(snap).execute("CREATE TABLE objects (id TEXT)").connection.close()
        (tmp_path / "game.db.pid").write_text(str(os.getpid()))
        with pytest.raises(ServerRunningError):
            restore_database(snap, live)

    async def test_the_server_writes_and_removes_its_pid_file(self, tmp_path):
        db = tmp_path / "game.db"
        srv = GameServer(db_path=str(db), enable_telnet=False, tick_interval=0)
        await srv.start()
        try:
            assert (tmp_path / "game.db.pid").exists()
        finally:
            await srv.stop()
        assert not (tmp_path / "game.db.pid").exists()


# --- migrations ----------------------------------------------------------------------------------


class TestMigrate:

    def _version_one(self, path):
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE objects (id TEXT PRIMARY KEY, name TEXT NOT NULL,
                description TEXT DEFAULT '', location_id TEXT, parent_id TEXT,
                owner_id TEXT, tags TEXT DEFAULT '[]', attributes TEXT DEFAULT '{}',
                behaviors TEXT DEFAULT '[]', locks TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO objects (id, name, tags) VALUES ('r1', 'Old Room', '["room"]');
            PRAGMA user_version = 1;
        """)
        conn.close()

    async def test_an_old_file_is_refused_until_migrated(self, tmp_path):
        from realm.persistence.manager import PersistenceManager, SchemaOutOfDateError
        from realm.persistence.migrate import migrate
        db = tmp_path / "old.db"
        self._version_one(db)
        store = PersistenceManager(db)
        with pytest.raises(SchemaOutOfDateError, match="realm migrate"):
            await store.initialize()
        await store.close()
        done = migrate(db)
        assert done == [2]
        with sqlite3.connect(db) as conn:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == \
                PersistenceManager.SCHEMA_VERSION
            indexes = {r[1] for r in conn.execute("PRAGMA index_list(objects)")}
            assert "idx_objects_parent" in indexes
        store = PersistenceManager(db)
        await store.initialize()
        try:
            assert [o.name for o in await store.load_all()] == ["Old Room"]
        finally:
            await store.close()
        assert migrate(db) == []                         # nothing left to do

    def test_the_cli_migrates(self, tmp_path, monkeypatch, capsys):
        import argparse

        from realm.cli import cmd_migrate
        db = tmp_path / "data" / "game.db"
        db.parent.mkdir()
        self._version_one(db)
        (tmp_path / "config.py").write_text('GAME_NAME = "Old"\nDB_PATH = "data/game.db"\n')
        monkeypatch.chdir(tmp_path)
        assert cmd_migrate(argparse.Namespace()) == 0
        assert "2" in capsys.readouterr().out
        with sqlite3.connect(db) as conn:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == 2

    async def test_an_unstamped_file_counts_as_version_one(self, tmp_path):
        from realm.persistence.manager import PersistenceManager, SchemaOutOfDateError
        from realm.persistence.migrate import migrate
        db = tmp_path / "older.db"
        self._version_one(db)
        with sqlite3.connect(db) as conn:
            conn.execute("PRAGMA user_version = 0")
        store = PersistenceManager(db)
        with pytest.raises(SchemaOutOfDateError, match="v1"):
            await store.initialize()
        assert migrate(db) == [2]

    async def test_a_new_file_is_made_current(self, tmp_path):
        from realm.persistence.manager import PersistenceManager
        db = tmp_path / "new.db"
        store = PersistenceManager(db)
        await store.initialize()
        await store.close()
        with sqlite3.connect(db) as conn:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == \
                PersistenceManager.SCHEMA_VERSION

    def test_every_version_has_a_step(self):
        from realm.persistence.manager import PersistenceManager
        from realm.persistence.migrate import MIGRATIONS
        assert sorted(MIGRATIONS) == list(range(2, PersistenceManager.SCHEMA_VERSION + 1))


def test_the_backup_cli_writes_and_prunes(tmp_path, monkeypatch, capsys):
    import argparse

    from realm.cli import cmd_backup, cmd_restore
    db = tmp_path / "data" / "game.db"
    db.parent.mkdir()
    sqlite3.connect(db).execute("CREATE TABLE objects (id TEXT)").connection.close()
    (tmp_path / "config.py").write_text('GAME_NAME = "Old"\nDB_PATH = "data/game.db"\n')
    monkeypatch.chdir(tmp_path)
    for _ in range(3):
        assert cmd_backup(argparse.Namespace(file=None, keep=2)) == 0
    kept = sorted((db.parent / "backups").iterdir())
    assert len(kept) == 2
    assert "Removed" in capsys.readouterr().out
    assert cmd_restore(argparse.Namespace(file=str(kept[-1]))) == 0
    assert cmd_restore(argparse.Namespace(file=str(tmp_path / "nope.db"))) == 1
