"""
`realm init` scaffolding: a fresh project must come with a pre-wired
rules.py — the user's own GameSystem subclass — that config.py imports
and selects. This guards the "blessed place to customize" developer
experience (never patch the engine).
"""

from __future__ import annotations

import sys

import pytest

from realm.cli import _sanitize_system_id, cmd_init
from realm.config.loader import load_config
from realm.std.rules.system import resolve_game_system


class _Args:
    def __init__(self, name, force=False, template=None, features="classic", system=None):
        self.name = name
        self.force = force
        self.template = template
        self.features = features
        self.system = system


@pytest.fixture
def clean_import_state():
    """Loading a generated config imports a top-level `rules` module and
    mutates sys.path — undo both so tests stay isolated."""
    before_path = list(sys.path)
    yield
    sys.modules.pop("rules", None)
    sys.modules.pop("game", None)
    sys.path[:] = before_path
    from realm.features import install_default
    install_default()


def test_init_creates_prewired_rules(tmp_path, monkeypatch, clean_import_state):
    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove")) == 0

    project = tmp_path / "questcove"
    config_py = project / "config.py"
    rules_py = project / "rules.py"
    assert config_py.exists() and rules_py.exists()

    # config selects GameRules by a dotted import path — one greppable
    # value that leads straight to rules.py, no registry lookup.
    config_text = config_py.read_text()
    assert 'GAME_SYSTEM = "rules.GameRules"' in config_text
    assert 'system_id = "questcove"' in rules_py.read_text()

    # And it actually resolves: the path imports rules.GameRules and the
    # resolver instantiates it (behaving like GURPS until customized).
    settings = load_config(project)                        # puts project on sys.path
    assert settings.game_system == "rules.GameRules"
    system = resolve_game_system(settings.game_system)
    assert type(system).__name__ == "GameRules"
    assert type(system).__mro__[1].__name__ == "GurpsSystem"
    assert len(system.chargen_steps()) == 2   # stock GURPS flow, unchanged


def test_resolve_game_system_accepts_path_class_and_instance():
    from realm.games.gurps.system import GurpsSystem

    # a dotted import path -> imported and instantiated
    assert isinstance(resolve_game_system("realm.games.gurps.system.GurpsSystem"), GurpsSystem)
    assert type(resolve_game_system("realm.games.d20.system.D20System")).__name__ == "D20System"
    # an already-resolved class -> instantiated
    assert isinstance(resolve_game_system(GurpsSystem), GurpsSystem)
    # an instance -> passed through
    inst = GurpsSystem()
    assert resolve_game_system(inst) is inst


def test_resolve_game_system_bad_path_fails_loudly():
    # A typo'd path (or a bare id that isn't a dotted path) must raise,
    # not silently fall back to some default.
    with pytest.raises(ValueError):
        resolve_game_system("realm.games.NoSuchSystem")
    with pytest.raises(ValueError):
        resolve_game_system("gurps")           # not a dotted path


def test_sanitize_system_id():
    assert _sanitize_system_id("MyGame") == "mygame"
    assert _sanitize_system_id("space-frontier") == "space_frontier"
    assert _sanitize_system_id("2cool") == "g_2cool"    # id can't start with a digit
    assert _sanitize_system_id("___") == "game"         # never empty


async def test_scaffold_feature_examples_boot(tmp_path, monkeypatch, clean_import_state):
    """game.py ships three commented examples (a command, a behavior, a
    softcode function). Uncommented, the scaffold boots with all three, and
    config.py lists the game in FEATURES (KERNEL_PLAN 4.3)."""
    import re

    from realm.core.behaviors import BehaviorRegistry
    from realm.scripting.registry import registered
    from realm.server.game import GameServer

    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove")) == 0
    project = tmp_path / "questcove"
    assert 'FEATURES = [*CLASSIC, "game"]' in (project / "config.py").read_text()

    game_py = project / "game.py"
    text = game_py.read_text()
    # Uncomment the example code; keep the "# A ..." prose comments.
    text = re.sub(r"^# (?!A )", "", text, flags=re.M)
    text = re.sub(r"^#$", "", text, flags=re.M)
    game_py.write_text(text)

    settings = load_config(project)
    assert "game" in settings.features
    server = GameServer(settings, enable_telnet=False, tick_interval=0)
    await server.start()
    try:
        assert server.dispatcher.get_command("wave") is not None
        assert BehaviorRegistry.get("questcove_chime") is not None
        assert registered()["double"].fn(4) == 8
    finally:
        await server.stop()


# --- the presets and the scaffold's own tests (KERNEL_PLAN 9.4) -------------------


PRESETS = {
    "classic": None,
    "social": ["accounts", "basics", "talk", "movement", "look", "items", "building",
               "game"],
    "bare": ["accounts", "look", "building", "game"],
}


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_each_preset_passes_its_own_tests(preset, tmp_path, monkeypatch, clean_import_state):
    """Scaffold, then run the scaffold's own tests in a subprocess from its
    directory, as its author would (``pytest``)."""
    import os
    import subprocess

    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove", features=preset)) == 0
    project = tmp_path / "questcove"
    for name in ("config.py", "game.py", "README.md", "data/welcome.txt",
                 "tests/test_game.py"):
        assert (project / name).is_file(), name
    assert (project / "rules.py").exists() == (preset == "classic")

    config = (project / "config.py").read_text()
    if PRESETS[preset] is None:
        assert 'FEATURES = [*CLASSIC, "game"]' in config
        assert 'GAME_SYSTEM = "rules.GameRules"' in config
    else:
        assert f"FEATURES = {PRESETS[preset]!r}".replace("'", '"') in config
        assert "\nGAME_SYSTEM" not in config            # no rules feature, no rules.py

    env = {k: v for k, v in os.environ.items() if k != "PYTEST_ADDOPTS"}
    run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:randomly",
                          "-p", "no:cacheprovider"],
                         cwd=project, env=env, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "1 passed" in run.stdout


def test_the_readme_is_short_and_points_to_one_page(tmp_path, monkeypatch, clean_import_state):
    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove")) == 0
    readme = (tmp_path / "questcove" / "README.md").read_text()
    assert len(readme.strip().splitlines()) <= 10
    assert "getting-started/first-game" in readme
    assert "realm start" in readme and "pytest" in readme and "game.py" in readme


def test_an_unknown_preset_is_refused(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove", features="huge")) == 1
    assert "classic, social, bare" in capsys.readouterr().out
    assert not (tmp_path / "questcove").exists()


@pytest.mark.parametrize("preset,system", [(p, None) for p in sorted(PRESETS)]
                         + [("classic", s) for s in ("d20", "merc")])
def test_the_scaffold_imports_only_public_names(preset, system, tmp_path, monkeypatch):
    """KERNEL_PLAN step 9 acceptance: every file the scaffold writes imports
    from ``realm``, ``realm.std.<x>``, ``realm.games.<x>`` and
    ``realm.testing`` only, and only names in their ``__all__``; the
    commented examples too (they are what an author uncomments)."""
    import ast
    import importlib
    import re

    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove", features=preset, system=system)) == 0
    public = re.compile(r"^realm(\.testing|\.std\.\w+|\.games\.\w+)?$")
    commented = re.compile(r"^\s*#\s*((?:from|import) realm\S*.*)$", re.M)
    problems = []
    for path in sorted((tmp_path / "questcove").rglob("*.py")):
        text = path.read_text()
        sources = [text] + commented.findall(text)
        for source in sources:
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.Import):
                    pairs = [(a.name, None) for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    pairs = [(node.module, a.name) for a in node.names]
                else:
                    continue
                for module, name in pairs:
                    if module.split(".")[0] != "realm":
                        continue
                    where = f"{path.name}: {module}" + (f".{name}" if name else "")
                    if not public.match(module):
                        problems.append(f"{where} (not a public home)")
                    elif name and name not in importlib.import_module(module).__all__:
                        problems.append(f"{where} (not in __all__)")
    assert problems == []


# --- `--system` and the templates as scaffolds (MUD_PLAN step 1) ---------------


def _run_own_tests(project):
    """The scaffold's own ``pytest``, run in a subprocess from its directory
    as its author would."""
    import os
    import subprocess

    env = {k: v for k, v in os.environ.items() if k != "PYTEST_ADDOPTS"}
    run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:randomly",
                          "-p", "no:cacheprovider"],
                         cwd=project, env=env, capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "1 passed" in run.stdout


SYSTEMS = {
    "gurps": ("GurpsSystem", "from realm.games.gurps import GurpsSystem", "TEMPLATES"),
    "d20": ("D20System", "from realm.games.d20 import D20System", "CLASSES"),
    "merc": ("MercSystem", "from realm.games.merc import MercSystem", "MERC_CLASSES"),
}


@pytest.mark.parametrize("system", sorted(SYSTEMS))
def test_each_system_scaffolds_and_passes_its_tests(system, tmp_path, monkeypatch,
                                                     clean_import_state):
    base, import_line, table = SYSTEMS[system]
    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove", system=system)) == 0
    project = tmp_path / "questcove"

    rules = (project / "rules.py").read_text()
    assert import_line in rules
    assert f"class GameRules({base}):" in rules
    # Its commented examples are this system's: they name its class table.
    assert table in rules
    for other, (other_base, _line, other_table) in SYSTEMS.items():
        if other != system:
            assert other_base not in rules and f"import {other_table}" not in rules

    system_obj = resolve_game_system(load_config(project).game_system)
    assert type(system_obj).__name__ == "GameRules"
    assert type(system_obj).__mro__[1].__name__ == base
    _run_own_tests(project)


def test_the_default_system_is_gurps(tmp_path, monkeypatch, clean_import_state):
    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove")) == 0
    gurps = (tmp_path / "questcove" / "rules.py").read_text()
    monkeypatch.chdir(tmp_path / "questcove")
    assert cmd_init(_Args("other", system="gurps")) == 0
    other = (tmp_path / "questcove" / "other" / "rules.py").read_text()
    assert other.replace("other", "questcove").replace("Other", "Questcove") == gurps


async def test_score_in_a_merc_scaffold_speaks_merc(tmp_path, monkeypatch,
                                                     clean_import_state):
    from realm.testing import Simulator

    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove", system="merc")) == 0
    sim = Simulator.from_game(tmp_path / "questcove")
    try:
        await sim.start()
        player = sim.player("Tester", location=sim.startup_room)
        await sim.do(player, "score")
        text = "\n".join(sim.seen(player))
        assert "THAC0" in text and "a level 1" in text
    finally:
        sim.close()


@pytest.mark.parametrize("preset", ["social", "bare"])
def test_system_with_a_preset_without_rules_is_refused(preset, tmp_path, monkeypatch,
                                                        capsys):
    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove", features=preset, system="merc")) == 1
    out = capsys.readouterr().out
    assert "--system" in out and preset in out and "no rules" in out
    assert not (tmp_path / "questcove").exists()


def test_an_unknown_system_is_refused(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove", system="rolemaster")) == 1
    assert "gurps, d20, merc" in capsys.readouterr().out
    assert not (tmp_path / "questcove").exists()


def test_template_with_another_system_is_refused(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove", template="midgaard", system="gurps")) == 1
    out = capsys.readouterr().out
    assert "the midgaard template is a merc game" in out and "--system merc" in out
    assert not (tmp_path / "questcove").exists()
    # A template without rules has no system to name.
    assert cmd_init(_Args("questcove", template="wilderness", system="merc")) == 1
    assert "the wilderness template has no rules system" in capsys.readouterr().out
    assert not (tmp_path / "questcove").exists()


def test_template_with_its_own_system_is_the_template(tmp_path, monkeypatch,
                                                       clean_import_state):
    """MUD_PLAN step 17: `realm init demo --system merc --template midgaard`,
    the line the guide and the acceptance use, makes the Midgaard game."""
    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("demo", template="midgaard", system="merc")) == 0
    assert cmd_init(_Args("plain", template="midgaard")) == 0
    for name in ("config.py", "rules.py", "game.py", "data/quests.json"):
        assert ((tmp_path / "demo" / name).read_text()
                == (tmp_path / "plain" / name).read_text()), name
    system = resolve_game_system(load_config(tmp_path / "demo").game_system)
    assert type(system).__mro__[1].__name__ == "MercSystem"


TEMPLATES = {
    "midgaard": ("MercSystem", "The Common Square"),
    "spacegame": ("GurpsSystem", "Docking Bay Alpha-1"),
}


@pytest.mark.parametrize("template", sorted(TEMPLATES))
async def test_each_template_is_a_full_scaffold(template, tmp_path, monkeypatch,
                                                 clean_import_state):
    from realm.testing import Simulator

    base, start_room = TEMPLATES[template]
    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove", template=template)) == 0
    project = tmp_path / "questcove"
    for name in ("config.py", "game.py", "rules.py", "tests/test_game.py", "README.md"):
        assert (project / name).is_file(), name
    assert not (project / "__init__.py").exists()

    config = (project / "config.py").read_text()
    assert 'GAME_SYSTEM = "rules.GameRules"' in config
    assert 'FEATURES = [*CLASSIC, "game"]' in config

    settings = load_config(project)
    system = resolve_game_system(settings.game_system)
    assert type(system).__name__ == "GameRules"
    assert type(system).__mro__[1].__name__ == base

    sim = Simulator.from_game(project)
    try:
        await sim.start()
        assert sim.startup_room is not None and sim.startup_room.name == start_room
    finally:
        sim.close()

    _run_own_tests(project)


def _uncomment_examples(text):
    """rules.py with its commented example code switched on, as an author
    would: each comment paragraph that starts with code (``from``, ``MY_``,
    ``def``) is uncommented, up to the next section header. The instant
    characters example (``return []``) stays off."""
    import re

    out, code, done = [], False, False
    for line in text.splitlines():
        if line.startswith("    # --- No creation"):
            done = True
        if done or not line.startswith("    #"):
            code = False
            out.append(line)
            continue
        if line == "    #":
            out.append("" if code else line)
            continue
        body = line[6:]
        if body.startswith("---"):
            code = False
        elif not code and re.match(r"(from |MY_|def )", body):
            code = True
        out.append("    " + body if code else line)
    return "\n".join(out) + "\n"


@pytest.mark.parametrize("system,new_class", [("gurps", "pilot"), ("d20", "ranger"),
                                              ("merc", "ranger")])
async def test_the_rules_examples_work_uncommented(system, new_class, tmp_path, monkeypatch,
                                                   clean_import_state):
    """rules.py's commented examples, switched on, add a class that
    character creation offers and finishes."""
    from realm.testing import Simulator

    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove", system=system)) == 0
    rules = tmp_path / "questcove" / "rules.py"
    rules.write_text(_uncomment_examples(rules.read_text()))

    sim = Simulator.from_game(tmp_path / "questcove")
    try:
        await sim.start()
        rules_obj = sim.game_system
        step = rules_obj.chargen_steps()[0]
        assert new_class in step.options
        player = sim.player("Tester", location=sim.startup_room)
        step.handle(player, new_class)
        assert new_class in rules_obj.finish_chargen(player)
        await rules_obj.outfit_new_character(player, sim.store)
    finally:
        sim.close()


def test_no_scaffold_restates_the_death_rule(tmp_path, monkeypatch, clean_import_state):
    """Decision D1 (decided 2026-11-16): ``respawn`` is the engine's default,
    so neither --system merc nor the Midgaard template writes
    PLAYER_DEATH; the Merc scaffold and Midgaard still set Merc's prompt."""
    monkeypatch.chdir(tmp_path)
    for system in SYSTEMS:
        assert cmd_init(_Args(f"g_{system}", system=system)) == 0
        config = (tmp_path / f"g_{system}" / "config.py").read_text()
        assert "PLAYER_DEATH" not in config, system
        assert ('PROMPT = "<{hp}hp {mana}m {move}mv> "' in config) == (system == "merc")
    assert cmd_init(_Args("town", template="midgaard")) == 0
    settings = load_config(tmp_path / "town")
    assert "PLAYER_DEATH" not in settings.raw
    assert settings.raw["PROMPT"] == "<{hp}hp {mana}m {move}mv> "


async def test_a_new_game_starts_with_channels_and_socials(tmp_path, monkeypatch,
                                                           clean_import_state):
    """MUD_PLAN 7.2/7.3: the scaffold's init_world imports the channels and
    socials-classic packs; step 14 the clan governments."""
    from realm.testing import Simulator
    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove")) == 0
    sim = Simulator.from_game(tmp_path / "questcove")
    try:
        await sim.start()
        channels = {o.name for o in sim.store.find_cached(tag="channel_def")}
        assert channels == {"gossip", "newbie", "immtalk"}
        assert len(sim.store.find_cached(tag="social_def")) >= 40
        governments = {o.name for o in sim.store.find_cached(tag="clan_government_def")}
        assert governments == {"gang", "guild", "union", "fellowship", "anarchy", "co-op",
                               "meritocracy", "plutocracy"}
    finally:
        sim.close()
