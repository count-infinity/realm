"""
The public names (KERNEL_PLAN 9.1).

Public means ``realm.__all__``, ``realm.features``, ``realm.testing`` and
each ``realm.std.<feature>.__all__`` (docs/reference/public-api.md).
Everything else may move without notice. The lists are frozen here, so
changing the public surface is a deliberate edit to this file.
"""

from __future__ import annotations

import ast
import importlib
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

import realm

ROOT = Path(__file__).resolve().parent.parent

REALM_ALL = [
    "Action", "ActionType", "Behavior", "CLASSIC", "CommandContext", "Feature",
    "FeatureError", "GameObject", "OpError", "Pool", "Settings", "Store", "World",
    "check_lock", "controls", "defs", "dice", "fire_event", "get_world", "has_entitlement",
    "import_objects", "import_pack", "ops", "pools", "propagate", "softcode_function",
]

FEATURE_ALL = {
    "abilities": ["AbilityAction", "invoke_ability"],
    "achievements": [],
    "accounts": ["account_of", "characters_of"],
    "basics": [],
    "building": [],
    "channels": [],
    "clans": ["clan_of", "clans_of", "find_clan", "has_power"],
    "clock": [],
    "companions": ["ACCOMPANIED", "companions_of", "master_of", "set_master"],
    "combat": ["AttackResult", "CombatAction", "CombatView", "Combatant",
               "DamageResult", "DamageType", "RollResult", "Ruleset", "deal_damage"],
    "crime": [],
    "economy": ["EconomyAction"],
    "effects": [],
    "instances": [],
    "items": ["ItemAction", "gate_item_action"],
    "look": [],
    "mail": [],
    "movement": [],
    "needs": [],
    "npc": [],
    "operations": [],
    "quests": ["accept", "complete", "credit", "fail", "find_quest", "state"],
    "rules": ["ChargenStep", "CheckResult", "ChoiceStep", "GameSystem", "PointBuyMixin",
              "check", "default_resolver", "define_class", "define_skill"],
    "sight": ["can_see_room", "room_is_lit"],
    "social": [],
    "spawning": [],
    "stealth": [],
    "talk": ["TalkAction"],
    "tasks": [],
    "vitals": [],
    "wilderness": [],
}

GAME_ALL = {
    "d20": ["CLASSES", "D20Ruleset", "D20System"],
    "gurps": ["GURPSRuleset", "GurpsSystem", "TEMPLATES"],
    "merc": ["MERC_CLASSES", "MercRuleset", "MercSystem"],
}


# --- the frozen lists -------------------------------------------------------------


def test_realm_all_is_frozen():
    assert sorted(realm.__all__) == REALM_ALL


def test_every_public_name_resolves():
    for name in realm.__all__:
        assert getattr(realm, name) is not None, name


def test_one_version():
    """``realm.__version__``, pyproject.toml and ``realm version`` agree."""
    import tomllib
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert realm.__version__ == project["version"] == "0.3.0"
    out = subprocess.run([sys.executable, "-m", "realm.cli", "version"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    assert "v0.3.0" in out


def test_pools_and_ops_are_the_modules():
    from realm.core import ops, pools
    assert realm.pools is pools and realm.ops is ops
    assert realm.Pool is pools.Pool


def test_feature_all_is_frozen():
    from realm.std import CLASSIC
    builtins = {n for n in CLASSIC if (ROOT / "realm" / "std" / n).is_dir()}
    assert set(FEATURE_ALL) == builtins
    for name, expected in FEATURE_ALL.items():
        package = importlib.import_module(f"realm.std.{name}")
        assert sorted(package.__all__) == expected, name
        for public in package.__all__:
            assert getattr(package, public) is not None, f"{name}.{public}"


def test_the_reference_lists_every_feature():
    """MUD_PLAN step 17: docs/reference/public-api.md has a row for every
    feature and game with public names, naming exactly them, and lists the
    rest as having none."""
    text = (ROOT / "docs" / "reference" / "public-api.md").read_text()
    rows = dict(re.findall(r"^\| `realm\.(?:std|games)\.(\w+)` \| (.*) \|$", text, re.M))
    listed = {name: sorted(re.findall(r"`(\w+)`", names)) for name, names in rows.items()}
    public = {name: names for name, names in {**FEATURE_ALL, **GAME_ALL}.items() if names}
    assert listed == public
    none = re.search(r"has no public names|have no public names", text)
    assert none is not None
    paragraph = text[text.rfind("\n\n", 0, none.start()):none.end()]
    for name, names in FEATURE_ALL.items():
        if not names:
            assert f"`{name}`" in paragraph, name


def test_game_all_is_frozen():
    games = {p.name for p in (ROOT / "realm" / "games").iterdir()
             if (p / "__init__.py").is_file()}
    assert set(GAME_ALL) == games
    for name, expected in GAME_ALL.items():
        package = importlib.import_module(f"realm.games.{name}")
        assert sorted(package.__all__) == expected, name
        for public in package.__all__:
            assert getattr(package, public) is not None, f"{name}.{public}"


def test_an_unknown_name_is_an_attribute_error():
    with pytest.raises(AttributeError, match="realm.*Nope"):
        realm.Nope  # noqa: B018
    rules = importlib.import_module("realm.std.rules")
    with pytest.raises(AttributeError, match="realm.std.rules.*Nope"):
        rules.Nope  # noqa: B018


def test_importing_realm_loads_no_feature():
    """``import realm`` and every root name load no ``realm.std.<feature>``
    or ``realm.games`` module (a bare world must not)."""
    code = (
        "import sys, realm\n"
        "for name in realm.__all__: getattr(realm, name)\n"
        "bad = sorted(m for m in sys.modules\n"
        "             if (m.startswith('realm.std.') or m.startswith('realm.games')))\n"
        "print(','.join(bad))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.strip()
    assert out == ""


# --- every documented import resolves -----------------------------------------------


FENCE = re.compile(r"^```python[^\n]*\n(.*?)^```", re.S | re.M)
SKIP = "# doctest: skip"


def _sources():
    for path in sorted((ROOT / "docs").rglob("*.md")) + [ROOT / "README.md"]:
        for i, block in enumerate(FENCE.findall(path.read_text())):
            yield f"{path.relative_to(ROOT)}#{i + 1}", block
    for path in sorted((ROOT / "realm" / "templates").glob("*.py.template")):
        yield str(path.relative_to(ROOT)), path.read_text()
    for path in sorted((ROOT / "realm" / "examples").rglob("*.py")):
        yield str(path.relative_to(ROOT)), path.read_text()


def _resolves(module: str, name: str | None) -> bool:
    try:
        mod = importlib.import_module(module)
    except ImportError:
        return False
    if name is None or name == "*" or hasattr(mod, name):
        return True
    try:
        importlib.import_module(f"{module}.{name}")
    except ImportError:
        return False
    return True


def _problems(where: str, source: str) -> list[str]:
    if source.lstrip().startswith(SKIP):
        return []
    try:
        # A method lifted out of its class is still Python: dedent it.
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError as err:
        return [f"{where}: does not parse ({err.msg}, line {err.lineno}); "
                f"mark it '{SKIP}' if it is meant to be partial"]
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "realm" and not _resolves(alias.name, None):
                    out.append(f"{where}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module \
                and node.module.split(".")[0] == "realm":
            for alias in node.names:
                if not _resolves(node.module, alias.name):
                    out.append(f"{where}: from {node.module} import {alias.name}")
    return out


def test_documented_imports_resolve():
    problems = [p for where, source in _sources() for p in _problems(where, source)]
    assert problems == []


# --- a game's tests get the fixtures with one line -----------------------------------


def test_a_game_gets_the_fixtures_with_one_line(tmp_path):
    (tmp_path / "conftest.py").write_text('pytest_plugins = ["realm.testing.fixtures"]\n')
    (tmp_path / "test_game.py").write_text(
        "import pytest\n"
        "from realm import get_world\n"
        "from realm.testing import Simulator\n\n"
        "def test_bare(world):\n"
        "    assert get_world() is world and world.features.names == []\n\n"
        "@pytest.mark.features('look')\n"
        "def test_marked(world):\n"
        "    assert 'look' in world.features.names\n\n"
        "def test_classic(classic_world):\n"
        "    assert 'combat' in classic_world.features.names\n\n"
        "def test_simulator():\n"
        "    with Simulator() as sim:\n"
        "        assert sim.room('Hall').name == 'Hall'\n")
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:randomly",
         "-p", "no:cacheprovider", "-W", "error::pytest.PytestUnknownMarkWarning",
         str(tmp_path)],
        cwd=tmp_path, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "4 passed" in run.stdout
