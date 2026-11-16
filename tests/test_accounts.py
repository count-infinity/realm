"""
MUD_PLAN step 6.1 to 6.3 and 6.6: accounts.

A person logs in to an account (``connect <account> <password>``), which
owns up to ``MAX_CHARACTERS`` characters. With one character the login goes
straight into play; otherwise a menu offers ``play``, ``new``, ``delete``,
``password`` and ``quit``. Worlds saved before accounts existed are carried
over at boot. Admins ban accounts and sitelock addresses.

(KERNEL_PLAN 7.4 still holds: logging in is the ``accounts`` feature's; the
server keeps the input funnel.)
"""

from __future__ import annotations

import pytest

from realm.server.game import GameServer
from realm.std.rules.system import ChoiceStep, GameSystem


class Instant(GameSystem):
    """A game system with no character creation steps."""

    system_id = "instant"


class OneStep(GameSystem):
    """A game system with one creation step."""

    system_id = "onestep"

    def chargen_steps(self):
        def pick(player, name):
            player.db.colour = name
        return [ChoiceStep("colour", "Pick a colour:", {"red": "red", "blue": "blue"}, pick)]


class Client:
    """One connection: send a line, read what came back."""

    def __init__(self, server, session, out):
        self.server, self.session, self.out = server, session, out

    async def send(self, line: str) -> str:
        start = len(self.out)
        await self.server._on_command(self.session, line)
        await self.session.flush_output()
        return "\n".join(self.out[start:])

    @property
    def player(self):
        return self.session.player

    @property
    def account(self):
        return self.session.account


async def _client(server, address="127.0.0.1") -> Client:
    out: list[str] = []

    async def writer(msg):
        out.append(msg)

    session = await server.session_manager.create_session(
        protocol="test", address=address, writer=writer)
    await session.flush_output()
    return Client(server, session, out)


@pytest.fixture
async def server():
    srv = GameServer(db_path=":memory:", enable_telnet=False, tick_interval=0,
                     game_system=Instant)
    await srv.start()
    try:
        yield srv
    finally:
        await srv.stop()


async def _with_characters(server, account="Ann", password="correcthorse", *names):
    c = await _client(server)
    await c.send(f"create {account} {password}")
    await c.send(names[0])
    for name in names[1:]:
        await c.send("characters")
        await c.send(f"new {name}")
    return c


# --- 6.1 the account object --------------------------------------------------------------


class TestTheAccountObject:

    async def test_create_makes_an_account_and_asks_for_a_first_character(self, server):
        c = await _client(server)
        assert "connect <account> <password>" in "\n".join(c.out)    # the welcome screen
        out = await c.send("create Ann correcthorse")
        assert c.account is not None and c.account.has_tag("account")
        assert c.account.location is None
        assert c.player is None
        assert "name your first character" in out.lower()
        out = await c.send("Bree")
        assert c.player is not None and c.player.name == "Bree"
        assert c.player.db.account == c.account.id
        assert c.account.db.characters == [c.player.id]
        assert c.account.db.created and c.account.db.last_login
        assert c.player.db.get("password") is None         # the hash is on the account

    async def test_the_first_character_of_the_first_account_is_the_superuser(self, server):
        c = await _with_characters(server, "Ann", "correcthorse", "Bree", "Cole")
        bree, cole = (server.persistence.find_cached(tag="player", name=n)[0]
                      for n in ("Bree", "Cole"))
        assert bree.has_tag("god") and not cole.has_tag("god")
        d = await _client(server)
        await d.send("create Dan correcthorse")
        await d.send("Eve")
        assert not d.player.has_tag("god")
        assert c.player is not None

    async def test_names_are_unique_in_their_own_namespace(self, server):
        await _with_characters(server, "Ann", "correcthorse", "Bree")
        d = await _client(server)
        assert "already exists" in await d.send("create ann other")
        # An account may share a character's name: separate namespaces.
        await d.send("create Bree secretword")
        assert d.account is not None and d.account.name == "Bree"
        out = await d.send("Bree")                          # but a character may not
        assert "already exists" in out and d.player is None
        await d.send("Ann")                                 # an account's name is free for one
        assert d.player is not None and d.player.name == "Ann"

    async def test_the_links_both_ways(self, server):
        from realm.std.accounts import account_of, characters_of
        c = await _with_characters(server, "Ann", "correcthorse", "Bree", "Cole")
        account = c.account
        names = [o.name for o in characters_of(account)]
        assert names == ["Bree", "Cole"]
        assert all(account_of(o) is account for o in characters_of(account))

    async def test_the_hash_is_not_readable_from_softcode(self, server):
        c = await _with_characters(server, "Ann", "correcthorse", "Bree")
        account = c.account
        assert str(account.db.password).startswith("scrypt$")
        result, err = await server.script_engine.run_code(
            c.player, "result = account_attr(me, 'password')")
        assert result is None
        result, err = await server.script_engine.run_code(
            c.player, f"result = get_attr(get('#{account.id}'), 'password')")
        assert result is None


# --- 6.2 carrying existing worlds over ------------------------------------------------------


async def test_a_world_saved_before_accounts_boots_and_its_players_log_in(tmp_path):
    from realm.core.objects import GameObject
    from realm.persistence.manager import PersistenceManager
    from realm.std.accounts.auth import hash_password

    db = tmp_path / "old.db"
    store = PersistenceManager(db)
    await store.initialize()
    room = GameObject("The Old Inn", tags=["room", "start_room"])
    await store.save(room)
    old = GameObject("Gil", tags=["player"], location=room)
    old.db.password = hash_password("hunter2hunter2")
    await store.save(old)
    await store.close()

    for boot in range(2):
        srv = GameServer(db_path=str(db), enable_telnet=False, tick_interval=0,
                         game_system=Instant)
        await srv.start()
        try:
            accounts = srv.persistence.find_cached(tag="account")
            assert [a.name for a in accounts] == ["Gil"]
            gil = srv.persistence.find_cached(tag="player", name="Gil")[0]
            assert gil.db.get("password") is None
            assert gil.db.account == accounts[0].id
            if boot == 1:
                c = await _client(srv)
                out = await c.send("connect Gil hunter2hunter2")
                assert c.player is gil                       # one character: straight in
                assert gil.location.name == "The Old Inn"
                assert "The Old Inn" in out
        finally:
            await srv.stop()


# --- 6.3 login and the menu -------------------------------------------------------------------


class TestTheMenu:

    async def test_one_character_goes_straight_into_play(self, server):
        c = await _with_characters(server, "Ann", "correcthorse", "Bree")
        await c.send("logout")
        assert c.account is None and c.player is None
        out = await c.send("connect Ann correcthorse")
        assert c.player.name == "Bree"
        assert "Welcome back" in out

    async def test_several_characters_show_the_menu(self, server):
        c = await _with_characters(server, "Ann", "correcthorse", "Bree", "Cole")
        await c.send("logout")
        out = await c.send("connect Ann correcthorse")
        assert c.player is None and c.account is not None
        assert "Bree" in out and "Cole" in out and "play <name>" in out
        await c.send("play cole")
        assert c.player.name == "Cole"

    async def test_new_runs_chargen(self):
        srv = GameServer(db_path=":memory:", enable_telnet=False, tick_interval=0,
                         game_system=OneStep)
        await srv.start()
        try:
            c = await _client(srv)
            await c.send("create Ann correcthorse")
            out = await c.send("Bree")
            assert "Pick a colour" in out
            assert c.player.db.chargen_step == 0
            await c.send("red")
            assert c.player.db.colour == "red" and c.player.db.get("chargen_step") is None
            await c.send("characters")
            out = await c.send("new Cole")
            assert "Pick a colour" in out and c.player.name == "Cole"
        finally:
            await srv.stop()

    async def test_the_character_limit(self):
        srv = GameServer(db_path=":memory:", enable_telnet=False, tick_interval=0,
                         game_system=Instant, raw={"MAX_CHARACTERS": 2})
        await srv.start()
        try:
            c = await _with_characters(srv, "Ann", "correcthorse", "Bree", "Cole")
            await c.send("characters")
            out = await c.send("new Dov")
            assert "at most 2 characters" in out
            assert c.player is None
        finally:
            await srv.stop()

    async def test_characters_switches_without_disconnecting(self, server):
        c = await _with_characters(server, "Ann", "correcthorse", "Bree", "Cole")
        cole = c.player
        room = cole.location
        out = await c.send("characters")
        assert c.player is None and c.account is not None
        assert cole.location is None or cole.location is room
        assert "play <name>" in out
        await c.send("play Bree")
        assert c.player.name == "Bree"
        assert c.session.id in [s.id for s in server.session_manager.all_sessions()]

    async def test_delete_asks_for_the_password(self, server):
        c = await _with_characters(server, "Ann", "correcthorse", "Bree", "Cole")
        await c.send("characters")
        out = await c.send("delete Cole")
        assert "password" in out.lower()
        out = await c.send("wrongpassword")
        assert server.persistence.find_cached(tag="player", name="Cole")
        await c.send("delete Cole")
        await c.send("correcthorse")
        assert not server.persistence.find_cached(tag="player", name="Cole")
        assert len(c.account.db.characters) == 1

    async def test_the_last_god_is_not_deleted(self, server):
        c = await _with_characters(server, "Ann", "correcthorse", "Bree", "Cole")
        await c.send("characters")
        await c.send("delete Bree")
        out = await c.send("correcthorse")
        assert "superuser" in out
        assert server.persistence.find_cached(tag="player", name="Bree")

    async def test_password_from_the_menu_and_in_play(self, server):
        c = await _with_characters(server, "Ann", "correcthorse", "Bree")
        out = await c.send("password wrongpassword newhorse1")
        assert "Wrong password" in out
        out = await c.send("password correcthorse newhorse1")
        assert "changed" in out
        await c.send("logout")
        assert "Invalid password" in await c.send("connect Ann correcthorse")
        await c.send("connect Ann newhorse1")
        assert c.player is not None
        await c.send("characters")
        await c.send("password newhorse1 newhorse2")
        await c.send("quit")
        d = await _client(server)
        await d.send("connect Ann newhorse2")
        assert d.player is not None

    async def test_a_second_login_takes_over(self, server):
        c = await _with_characters(server, "Ann", "correcthorse", "Bree")
        d = await _client(server, address="10.0.0.2")
        await d.send("connect Ann correcthorse")
        assert d.player is not None and d.player.name == "Bree"
        assert any("logged in from elsewhere" in line for line in c.out)
        assert c.session.id not in [s.id for s in server.session_manager.all_sessions()]

    async def test_multiplay_allows_one_session_per_character(self):
        srv = GameServer(db_path=":memory:", enable_telnet=False, tick_interval=0,
                         game_system=Instant, raw={"ACCOUNT_MULTIPLAY": True})
        await srv.start()
        try:
            c = await _with_characters(srv, "Ann", "correcthorse", "Bree", "Cole")
            assert c.player.name == "Cole"
            d = await _client(srv, address="10.0.0.2")
            await d.send("connect Ann correcthorse")
            await d.send("play Bree")
            assert d.player.name == "Bree" and c.player.name == "Cole"
            e = await _client(srv, address="10.0.0.3")
            await e.send("connect Ann correcthorse")
            await e.send("play Cole")
            assert e.player.name == "Cole" and c.player is None   # Cole taken over
        finally:
            await srv.stop()

    async def test_the_rate_limit_keys_on_the_account(self, server):
        await _with_characters(server, "Ann", "correcthorse", "Bree")
        d = await _client(server)
        for _ in range(5):
            await d.send("connect Ann wrongpassword")
        out = await d.send("connect ANN correcthorse")
        assert "Too many failed attempts" in out

    async def test_unfinished_chargen_waits(self):
        srv = GameServer(db_path=":memory:", enable_telnet=False, tick_interval=0,
                         game_system=OneStep)
        await srv.start()
        try:
            c = await _client(srv)
            await c.send("create Ann correcthorse")
            await c.send("Bree")
            assert "unfinished character will wait" in await c.send("quit")
        finally:
            await srv.stop()


@pytest.mark.asyncio
async def test_without_accounts_the_server_says_so():
    srv = GameServer(db_path=":memory:", enable_telnet=False, tick_interval=0,
                     features=["basics", "talk"])
    await srv.start()
    try:
        c = await _client(srv)
        assert c.out == ["This world has no login feature installed."]
        await c.send("connect Bob correcthorse")
        assert c.out[-1] == "This world has no login feature installed."
        assert c.player is None
    finally:
        await srv.stop()


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


# --- 6.6 bans and administration ---------------------------------------------------------------


@pytest.fixture
def clock(monkeypatch):
    now = [4_000_000.0]
    monkeypatch.setattr("realm.std.accounts.account.now", lambda: now[0])
    return now


class TestAdministration:

    async def _admin(self, server):
        admin = await _with_characters(server, "Root", "rootpassword", "Boss")
        assert admin.player.has_tag("god")
        return admin

    async def test_account_shows_the_account(self, server):
        admin = await self._admin(server)
        await _with_characters(server, "Ann", "correcthorse", "Bree")
        out = await admin.send("@account Ann")
        assert "Ann" in out and "Bree" in out and "127.0.0.1" in out

    async def test_a_ban_refuses_connect_until_it_expires(self, server, clock, caplog):
        import logging
        admin = await self._admin(server)
        ann = await _with_characters(server, "Ann", "correcthorse", "Bree")
        await ann.send("quit")
        with caplog.at_level(logging.INFO, logger="realm.admin"):
            out = await admin.send("@account/ban Ann 2h = flooding the channels")
        assert "banned" in out.lower()
        assert any("Boss" in r.message and "Ann" in r.message for r in caplog.records)
        d = await _client(server)
        out = await d.send("connect Ann correcthorse")
        assert d.account is None and "flooding the channels" in out
        clock[0] += 2 * 3600 + 1
        await d.send("connect Ann correcthorse")
        assert d.player is not None

    async def test_unban_and_a_permanent_ban(self, server, clock):
        admin = await self._admin(server)
        ann = await _with_characters(server, "Ann", "correcthorse", "Bree")
        await ann.send("quit")
        await admin.send("@account/ban Ann forever = no")
        d = await _client(server)
        assert "permanently" in await d.send("connect Ann correcthorse")
        await admin.send("@account/unban Ann")
        await d.send("connect Ann correcthorse")
        assert d.player is not None

    async def test_a_ban_boots_the_banned(self, server, clock):
        admin = await self._admin(server)
        ann = await _with_characters(server, "Ann", "correcthorse", "Bree")
        await admin.send("@account/ban Ann 1d = rude")
        assert ann.session.id not in [s.id for s in server.session_manager.all_sessions()]

    async def test_password_reset_and_boot(self, server, caplog):
        import logging
        admin = await self._admin(server)
        ann = await _with_characters(server, "Ann", "correcthorse", "Bree")
        with caplog.at_level(logging.INFO, logger="realm.admin"):
            await admin.send("@account/password Ann = brandnewpass")
        assert any("password" in r.message for r in caplog.records)
        await admin.send("@account/boot Ann")
        assert ann.session.id not in [s.id for s in server.session_manager.all_sessions()]
        d = await _client(server)
        await d.send("connect Ann brandnewpass")
        assert d.player is not None

    async def test_mortals_may_not(self, server):
        await self._admin(server)
        ann = await _with_characters(server, "Ann", "correcthorse", "Bree")
        out = await ann.send("@account Root")
        assert "Permission denied." in out and "last login" not in out
        out = await ann.send("@sitelock 1.2.3.")
        assert "Permission denied." in out

    async def test_sitelock(self, server):
        admin = await self._admin(server)
        out = await admin.send("@sitelock 10.9. = a botnet")
        assert "10.9." in out
        listing = await admin.send("@sitelock/list")
        assert "10.9." in listing and "a botnet" in listing
        d = await _client(server, address="10.9.1.4")
        assert any("a botnet" in line for line in d.out)
        assert d.session.id not in [s.id for s in server.session_manager.all_sessions()]
        e = await _client(server, address="10.8.1.4")
        assert e.session.id in [s.id for s in server.session_manager.all_sessions()]
        await admin.send("@sitelock/remove 10.9.")
        f = await _client(server, address="10.9.1.4")
        assert f.session.id in [s.id for s in server.session_manager.all_sessions()]

    async def test_create_from_a_locked_site_is_refused(self, server):
        admin = await self._admin(server)
        d = await _client(server, address="10.7.0.1")
        await admin.send("@sitelock 10.7. = no new accounts")
        out = await d.send("create Zed correcthorse")
        assert d.account is None and "no new accounts" in out
