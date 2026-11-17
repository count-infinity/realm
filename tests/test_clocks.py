"""
Clocks a test can move (BACKLOG, MUD_PLAN step 17: "Clocks that are not
call-through").

Every time the engine reads for a game reason goes through a module-level
``now()`` the code calls through its module, so ``monkeypatch.setattr(
"realm.std.mail.mail.now", ...)`` moves it. Each test below sets a fake time
and shows the behaviour move with it. ``realm.testing.FakeClock`` patches
all of them at once; the last test keeps its list honest by scanning the
package for every read of the time.
"""

from __future__ import annotations

import ast
import time
from pathlib import Path

import pytest

import realm
from realm.testing import Simulator

EPOCH = 1_800_000_000.0                  # 2027-01-15 08:00 UTC


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.world.services["combat"].stop_all()
        s.close()


def _at(monkeypatch, target: str, start: float = EPOCH) -> list[float]:
    """Replace one module's ``now`` with a clock the test moves (``t[0]``)."""
    t = [start]
    monkeypatch.setattr(target, lambda: t[0])
    return t


def _text(sim, who) -> str:
    return "\n".join(sim.seen(who))


# --- the five the BACKLOG names --------------------------------------------------


async def test_an_ability_cooldown_runs_on_its_clock(sim, monkeypatch):
    t = _at(monkeypatch, "realm.std.abilities.abilities.now")
    sim.obj("kick", tags=["ability_def"], target="victim", cost={"cooldown": 2},
            effects=[{"type": "damage", "dice": "3", "damage_type": "bludgeoning",
                      "magical": False}])
    room = sim.room("Yard")
    pat = sim.player("Pat", location=room, hp=20, max_hp=20, level=1)
    sim.obj("rat", location=room, tags=["npc"], hp=20, max_hp=20)
    await sim.do(pat, "kick rat")
    assert pat.db.ability_ready["kick"] == EPOCH + 2 * sim.world.setting("WORLD_BEAT")
    sim.seen(pat)
    await sim.do(pat, "abilities")
    assert f"(ready in {int(2 * sim.world.setting('WORLD_BEAT')) + 1}s)" in _text(sim, pat)
    t[0] += 2 * sim.world.setting("WORLD_BEAT")
    await sim.do(pat, "abilities")
    assert "ready in" not in _text(sim, pat)


async def test_a_corpse_lock_lifts_on_its_clock(monkeypatch):
    from realm.config.loader import Settings
    from realm.core.pools import harm, settle
    t = _at(monkeypatch, "realm.std.combat.corpses.now")
    s = Simulator(settings=Settings(raw={"PLAYER_DEATH": "respawn"}))
    try:
        field, home = s.room("Field"), s.room("Home")
        pat = s.player("Pat", location=field, hp=10, max_hp=10, home=home.id)
        sword = s.obj("a sword", location=pat, tags=["thing", "weapon"])
        await settle(harm(pat, "hp", 30))
        thief = s.player("Thief", location=field)
        t[0] += s.world.setting("CORPSE_LOCK_SECONDS") - 1
        await s.do(thief, "get sword from corpse")
        assert sword.location is not thief
        t[0] += 1
        await s.do(thief, "get sword from corpse")
        assert sword.location is thief
    finally:
        s.close()


async def test_a_letter_is_dated_by_the_mail_clock(sim, monkeypatch):
    _at(monkeypatch, "realm.std.mail.mail.now")
    inn = sim.room("Inn")
    ann = sim.player("Ann", location=inn)
    sim.account("ann", ann)
    sim.account("gus", sim.obj("Gus", tags=["player"]))
    await sim.do(ann, "mail gus = Supper/Come by at six.")
    letter = sim.store.find_cached(tag="mail")[0]
    assert letter.db.sent == EPOCH
    from realm.std.mail.mail import _when
    assert _when(letter.db.sent) == "2027-01-15 08:00"


async def test_an_achievement_is_dated_by_its_clock(sim, monkeypatch):
    _at(monkeypatch, "realm.std.achievements.achievements.now")
    room = sim.room("Crypt")
    bree = sim.player("Bree", location=room)
    sim.account("Ann", bree)
    altar = sim.obj("altar", location=room)
    sim.obj("Banshee Slayer", tags=["achievement_def"], description="Slay the banshee.")
    await sim.eval(altar, "grant_achievement(get('Bree'), 'Banshee Slayer')")
    sim.seen(bree)
    await sim.do(bree, "achievements")
    assert f"{'Banshee Slayer':24} 2027-01-15" in _text(sim, bree)


async def test_channel_history_is_stamped_by_its_clock(monkeypatch):
    from realm.packs import import_pack
    t = _at(monkeypatch, "realm.std.channels.channels.now")
    s = Simulator()
    try:
        await import_pack("channels", s.store)
        ann = s.player("Ann", location=s.room("Inn"))
        await s.do(ann, "gossip first")
        t[0] += 90 * 60
        await s.do(ann, "gossip second")
        gossip = s.store.find_cached(name="gossip")[0]
        assert [stamp for stamp, _line in gossip.db.history] == [EPOCH, EPOCH + 5400]
        s.seen(ann)
        await s.do(ann, "channel gossip history")
        out = _text(s, ann)
        assert "08:00 [gossip] Ann: first" in out and "09:30 [gossip] Ann: second" in out
    finally:
        s.close()


# --- the combat beat --------------------------------------------------------------


async def test_a_round_comes_due_on_the_encounter_clock(sim, monkeypatch):
    t = _at(monkeypatch, "realm.std.combat.encounter.now")
    room = sim.room("Pit")
    pat = sim.player("Pat", location=room, hp=200, max_hp=200)
    rat = sim.obj("rat", location=room, tags=["npc"], hp=200, max_hp=200)
    encounter = await sim.world.services["combat"].initiate(pat, rat)
    beat = encounter.beat_seconds
    assert encounter.seconds_to_beat == beat
    t[0] += beat - 1
    assert encounter.seconds_to_beat == 1
    assert await encounter.beat() is True            # not due: nothing fires
    assert encounter.round_number == 0
    t[0] += 1
    assert await encounter.beat() is True            # due: one round
    assert encounter.round_number == 1
    assert await encounter.beat() is True            # the next beat is a beat away
    assert encounter.round_number == 1 and encounter.seconds_to_beat == beat


async def test_the_beat_that_ends_a_fight_finishes_it(sim, monkeypatch):
    t = _at(monkeypatch, "realm.std.combat.encounter.now")
    room = sim.room("Pit")
    pat = sim.player("Pat", location=room, hp=200, max_hp=200)
    rat = sim.obj("rat", location=room, tags=["npc"], hp=200, max_hp=200)
    combat = sim.world.services["combat"]
    encounter = await combat.initiate(pat, rat)
    encounter.remove(rat.id)                         # it fled
    t[0] += encounter.beat_seconds
    assert await encounter.beat() is False
    assert combat.encounter_of(pat) is None and not pat.has_tag("in_combat")
    assert "*** The fight is over. ***" in _text(sim, pat)
    assert await encounter.beat() is False           # once over, stays over
    assert _text(sim, pat) == ""


# --- the rest of the inventory ----------------------------------------------------


async def test_a_zone_resets_on_its_clock(sim, monkeypatch):
    from realm.core.behaviors import BehaviorRegistry
    t = _at(monkeypatch, "realm.std.spawning.zone_reset.now")
    crypt = sim.room("Crypt")
    crypt.add_tag("zone:crypt")
    master = sim.obj("crypt master", tags=["zone:crypt"])
    master.db.reset_interval = 600
    master.db.last_reset = EPOCH
    behavior = BehaviorRegistry.create("zone_reset")
    master.add_behavior(behavior)
    t[0] += 599
    await behavior.tick(master, 4.0)
    assert master.db.last_reset == EPOCH
    t[0] += 1
    await behavior.tick(master, 4.0)
    assert master.db.last_reset == EPOCH + 600


async def test_a_wait_comes_due_on_its_clock(sim, monkeypatch):
    t = _at(monkeypatch, "realm.scripting.waits.now")
    gong = sim.obj("gong", location=sim.room("Hall"))
    gong.db.boom = "set_attr(me, 'fired', 1)"
    await sim.eval(gong, "wait(30, 'trigger me/boom')")
    t[0] += 29
    await sim.engine.waits.tick()
    assert gong.db.get("fired") is None
    t[0] += 1
    await sim.engine.waits.tick()
    assert gong.db.fired == 1


async def test_expiry_and_softcode_now_share_the_kernel_clock(sim, monkeypatch):
    from realm.core.events import reap_expired
    t = _at(monkeypatch, "realm.core.events.now")
    room = sim.room("Hall")
    smoke = sim.obj("smoke", location=room)
    result, err = await sim.eval(smoke, "expire(me, 30); result = now()")
    assert err is None and result == int(EPOCH)
    assert smoke.db.expires_at == EPOCH + 30
    t[0] += 29
    assert await reap_expired(sim.store) == 0
    t[0] += 1
    assert await reap_expired(sim.store) == 1


async def test_the_login_throttle_drains_on_its_clock(monkeypatch):
    from realm.std.accounts.account import new_account
    from realm.std.accounts.auth import AuthService, hash_password
    from tests.test_olc import MockPersistence
    t = _at(monkeypatch, "realm.std.accounts.auth.now")
    store = MockPersistence()
    store.add(new_account("Bob", hash_password("s2")))
    auth = AuthService(store, max_attempts=2, window_seconds=60)
    for _ in range(2):
        await auth.authenticate("Bob", "wrong")
    assert (await auth.authenticate("Bob", "s2"))[0] is None
    t[0] += 60
    assert (await auth.authenticate("Bob", "s2"))[0] is not None


# --- the heartbeat ----------------------------------------------------------------


async def test_the_heartbeat_pulses_on_its_clock(monkeypatch):
    """``GameServer.pulse()`` is one heartbeat, deciding on ``now()`` which
    behaviors are due and whether the ambient world beat fires; the loop
    only sleeps between pulses on real time (as ``beat()`` was split out of
    the encounter loop)."""
    from realm.core.beats import BeatBehavior
    from realm.core.behaviors import Behavior
    from realm.core.objects import GameObject
    from realm.server.game import GameServer

    t = _at(monkeypatch, "realm.server.game.now")
    monkeypatch.setattr("realm.server.game.random.random", lambda: 0.0)   # no jitter
    ticks: list[float] = []
    beats: list[int] = []

    class Ticker(Behavior):
        behavior_id = "test_ticker"

        @property
        def should_tick(self) -> bool:
            return True

        @property
        def tick_interval(self) -> float:
            return 10.0

        async def tick(self, obj, delta: float) -> None:
            ticks.append(delta)

    class Beat(BeatBehavior):
        behavior_id = "test_beat"

        async def on_beat(self, obj) -> None:
            beats.append(1)

    srv = GameServer(db_path=":memory:", enable_telnet=False, tick_interval=0)
    await srv.start()
    try:
        world_beat = srv.world.setting("WORLD_BEAT")
        thing = GameObject("metronome")
        thing.add_behavior(Ticker())
        thing.add_behavior(Beat())
        await srv.persistence.save(thing)
        # A namesake that is not this world's object (an earlier world's, a
        # deleted one still referenced) is not the heartbeat's to tick.
        ghost = GameObject("metronome", id=thing.id)
        ghost.add_behavior(Ticker())
        await srv.pulse()                    # first sight: its phase is set, no tick
        assert ticks == [] and beats == []
        t[0] += 9.9
        await srv.pulse()                    # a WORLD_BEAT has passed: one beat
        assert ticks == [] and beats == [1]
        t[0] += 0.1
        await srv.pulse()                    # the ticker is due on the clock
        assert ticks == [10.0] and beats == [1]
        await srv.pulse()                    # nothing due twice
        assert ticks == [10.0] and beats == [1]
        t[0] += world_beat
        await srv.pulse()
        assert ticks == [10.0] and beats == [1, 1]
    finally:
        await srv.stop()


def test_the_heartbeat_visits_objects_in_the_order_they_got_behaviors():
    """Behavior owners are kept by identity, in the order each got its first
    behavior: the heartbeat's seeded dice fall the same way whatever
    ``PYTHONHASHSEED`` orders a set by, and an object sharing another's id
    (a world loaded again) is an owner too."""
    from realm.core.behaviors import Behavior, behavior_owners
    from realm.core.objects import GameObject

    class Mark(Behavior):
        behavior_id = "test_mark"

    made = [GameObject(f"thing {n}", id=f"order-{n:03}") for n in range(60)]
    for obj in reversed(made):
        obj.add_behavior(Mark())
    twin = GameObject("thing 0 again", id="order-000")
    twin.add_behavior(Mark())
    mine = [o for o in behavior_owners() if o.id.startswith("order-")]
    assert [o.name for o in mine] == [o.name for o in reversed(made)] + ["thing 0 again"]


# --- every clock at once, and the list kept honest --------------------------------


def test_fake_clock_moves_every_engine_clock(monkeypatch):
    import importlib

    from realm.testing import FakeClock
    from realm.testing.clock import ENGINE_CLOCKS
    clock = FakeClock().install(monkeypatch)
    for name in ENGINE_CLOCKS:
        assert importlib.import_module(name).now() == clock.t, name
    clock.advance(60)
    for name in ENGINE_CLOCKS:
        assert importlib.import_module(name).now() == EPOCH + 60, name


#: The reads of the time that stay real, by (module, function): they measure
#: or report the machine, and no game state is decided by them.
REAL_TIME = {
    ("realm.persistence.backup", "default_backup_path"): "a backup file's name",
    ("realm.scripting.sandbox", "_make_watchdog"): "a script's CPU budget",
    ("realm.scripting.sandbox", "_wrap_function"): "a script's CPU budget",
    ("realm.scripting.sandbox", "execute"): "a script's CPU budget",
    ("realm.server.game", "start"): "the process start, for uptime",
    ("realm.server.game", "_tick_loop"): "the heartbeat's own schedule",
    ("realm.std.basics.commands", "cmd_time"): "the machine's clock, reported",
    ("realm.std.basics.commands", "cmd_uptime"): "the process's uptime, reported",
    ("realm.std.clock.commands", "cmd_time"): "the machine's clock, reported",
}

_TIME_FUNCS = {"time", "monotonic", "perf_counter", "time_ns", "monotonic_ns",
               "perf_counter_ns", "localtime", "gmtime", "ctime", "asctime"}
_NOW_FUNCS = {"now", "utcnow", "today"}


def _time_reads(tree: ast.AST) -> list[tuple[int, str]]:
    """Every read of the time in a module: (line, enclosing top-level
    function). ``time.gmtime(stamp)``/``localtime(stamp)`` given a value
    format it, so only their bare calls count."""
    time_mods, time_names, date_classes, date_mods = set(), set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "time":
                    time_mods.add(a.asname or "time")
                elif a.name == "datetime":
                    date_mods.add(a.asname or "datetime")
        elif isinstance(node, ast.ImportFrom) and node.module == "time":
            time_names |= {a.asname or a.name for a in node.names if a.name in _TIME_FUNCS}
        elif isinstance(node, ast.ImportFrom) and node.module == "datetime":
            date_classes |= {a.asname or a.name for a in node.names
                             if a.name in ("datetime", "date")}

    def is_read(node: ast.AST, parent: ast.AST | None) -> bool:
        if isinstance(node, ast.Attribute):
            base = node.value
            if isinstance(base, ast.Name) and base.id in time_mods and node.attr in _TIME_FUNCS:
                return not (node.attr in ("gmtime", "localtime", "ctime")
                            and isinstance(parent, ast.Call) and parent.args)
            if node.attr in _NOW_FUNCS:
                if isinstance(base, ast.Name) and base.id in date_classes:
                    return True
                if (isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name)
                        and base.value.id in date_mods and base.attr in ("datetime", "date")):
                    return True
        return isinstance(node, ast.Name) and node.id in time_names

    found: list[tuple[int, str]] = []

    def visit(node: ast.AST, scope: str, parent: ast.AST | None) -> None:
        if is_read(node, parent):
            found.append((node.lineno, scope))
        for child in ast.iter_child_nodes(node):
            inner = scope
            if scope == "<module>" and isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                inner = child.name
            if isinstance(node, ast.ClassDef) and isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                inner = child.name
            visit(child, inner, node)

    visit(tree, "<module>", None)
    return found


def test_every_read_of_the_time_is_a_known_clock_or_real_on_purpose():
    """A new ``time.time()`` (or ``monotonic``, ``datetime.now``) anywhere in
    ``realm/`` fails here until it is either a module's ``now()``, listed in
    ``ENGINE_CLOCKS`` so ``FakeClock`` moves it, or real time on purpose,
    listed in ``REAL_TIME`` with why."""
    from realm.testing.clock import ENGINE_CLOCKS
    root = Path(realm.__file__).parent
    clocks, stray = set(), []
    for path in sorted(root.rglob("*.py")):
        module = ".".join(path.relative_to(root.parent).with_suffix("").parts)
        for line, scope in _time_reads(ast.parse(path.read_text(), str(path))):
            if scope == "now":
                clocks.add(module)
            elif (module, scope) not in REAL_TIME:
                stray.append(f"{module}:{line} (in {scope})")
    assert not stray, ("reads of the time that a test cannot move; give the module a "
                       "now() and add it to realm.testing.clock.ENGINE_CLOCKS, or list "
                       f"it in REAL_TIME: {stray}")
    assert clocks == set(ENGINE_CLOCKS), (
        f"unknown to FakeClock: {sorted(clocks - set(ENGINE_CLOCKS))}; "
        f"listed but not a clock: {sorted(set(ENGINE_CLOCKS) - clocks)}")


def test_the_scan_sees_each_form_of_a_read():
    src = ("import time\nimport time as _t\nimport datetime\n"
           "from time import monotonic\nfrom datetime import datetime as dt, UTC\n"
           "def a(): return time.time()\n"
           "def b(): return _t.monotonic()\n"
           "def c(): return monotonic()\n"
           "def d(): return datetime.datetime.now()\n"
           "def e(): return dt.now(UTC)\n"
           "clock = time.monotonic\n"
           "def f(s): return time.gmtime(s)\n"
           "class K:\n    def g(self): return time.time()\n")
    assert [scope for _line, scope in _time_reads(ast.parse(src))] == [
        "a", "b", "c", "d", "e", "<module>", "g"]


def test_real_time_lists_only_reads_that_exist():
    root = Path(realm.__file__).parent
    seen = set()
    for path in root.rglob("*.py"):
        module = ".".join(path.relative_to(root.parent).with_suffix("").parts)
        seen |= {(module, scope) for _l, scope in _time_reads(ast.parse(path.read_text()))}
    assert set(REAL_TIME) <= seen, sorted(set(REAL_TIME) - seen)


def test_the_default_clocks_are_the_real_ones():
    # The default clocks are the real ones: wall clocks agree with time.time().
    from realm.std.mail import mail
    assert abs(mail.now() - time.time()) < 5
