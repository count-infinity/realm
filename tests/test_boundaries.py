"""
The boundary tests: the definition of "kernel" (KERNEL_PLAN 7.6).

The kernel is ``realm/core``, ``scripting``, ``commands``, ``permissions``,
``persistence``, ``gateway``, ``server``, ``config``, ``packs`` and
``realm/features.py``. It imports nothing from a feature (``realm/std``) or
a game (``realm/games``); it names the built-ins only as strings, in the
two places listed in ``KERNEL_STRINGS``. A feature imports another
feature's parts only when it ``requires`` that feature (naming another
feature's action types, ``realm.std.<x>.actions``, is allowed: the strings
simply never match in a world without it). Where new code goes follows from
these tests; see docs/development/contributing.md.
"""

from __future__ import annotations

import ast
import importlib
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
REALM = ROOT / "realm"
KERNEL = [REALM / d for d in ("core", "scripting", "commands", "permissions",
                              "persistence", "gateway", "server", "config", "packs")]
KERNEL += [REALM / "features.py"]
FEATURE_ROOTS = ("realm.std", "realm.games")

#: The only places the kernel names a built-in, and only as strings: the
#: FEATURES and GAME_SYSTEM defaults, and where built-in names resolve.
KERNEL_STRINGS = {
    ("realm/config/loader.py", "realm.std.CLASSIC"),
    ("realm/config/loader.py", "realm.games.gurps.system.GurpsSystem"),
    ("realm/features.py", "realm.std"),
    ("realm/features.py", "realm.games"),
}


def _files(path: pathlib.Path) -> list[pathlib.Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*.py") if "__pycache__" not in p.parts)


def _imports(path: pathlib.Path):
    """Every imported module path, at any depth (functions, TYPE_CHECKING)."""
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.lineno, node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name


def _strings(path: pathlib.Path):
    """String constants that are not docstrings."""
    tree = ast.parse(path.read_text())
    docstrings = {id(n.value) for n in ast.walk(tree)
                  if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings):
            yield node.lineno, node.value


def _rel(path: pathlib.Path) -> str:
    return str(path.relative_to(ROOT))


def test_kernel_imports_nothing_above_it():
    offenders = []
    for top in KERNEL:
        for path in _files(top):
            for line, module in _imports(path):
                if module.startswith(FEATURE_ROOTS) or module in ("realm.std", "realm.games"):
                    offenders.append(f"{_rel(path)}:{line} imports {module}")
            for line, text in _strings(path):
                if text.startswith(FEATURE_ROOTS) and (_rel(path), text) not in KERNEL_STRINGS:
                    offenders.append(f"{_rel(path)}:{line} names {text!r}")
    assert not offenders, "the kernel reaches a feature:\n" + "\n".join(offenders)


def test_std_features_do_not_import_games():
    offenders = [f"{_rel(path)}:{line} imports {module}"
                 for path in _files(REALM / "std")
                 for line, module in _imports(path)
                 if module.startswith("realm.games")]
    assert not offenders, "\n".join(offenders)


def _feature_packages():
    for root in ("std", "games"):
        for pkg in sorted((REALM / root).iterdir()):
            if (pkg / "feature.py").exists():
                yield root, pkg


def test_feature_requires_match_imports():
    from realm.features import _resolve
    offenders = []
    for root, pkg in _feature_packages():
        feature = _resolve(pkg.name, None)
        allowed = set(feature.requires) | {pkg.name}
        for path in _files(pkg):
            for line, module in _imports(path):
                parts = module.split(".")
                if module.startswith(FEATURE_ROOTS) and len(parts) > 2:
                    other = parts[2]
                    if other in allowed:
                        continue
                    if len(parts) == 4 and parts[3] == "actions":
                        continue            # naming another feature's action types
                    offenders.append(f"{_rel(path)}:{line} imports {module}, but "
                                     f"{feature.name!r} does not require {other!r}")
    assert not offenders, "\n".join(offenders)


def test_every_import_resolves():
    """Every ``from realm.x import y`` in realm/, nested ones included, names
    something that exists (a moved module breaks a deferred import only when
    it runs)."""
    broken = []
    for path in _files(REALM):
        if "templates" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if not (isinstance(node, ast.ImportFrom) and node.module
                    and node.module.startswith("realm") and node.level == 0):
                continue
            module = importlib.import_module(node.module)
            for alias in node.names:
                if alias.name == "*" or hasattr(module, alias.name):
                    continue
                try:
                    importlib.import_module(f"{node.module}.{alias.name}")
                except ImportError:
                    broken.append(f"{_rel(path)}:{node.lineno} "
                                  f"{node.module} has no {alias.name}")
    assert not broken, "\n".join(broken)


@pytest.mark.asyncio
async def test_bare_kernel_boots(tmp_path):
    from realm.core import ops
    from realm.features import load
    from realm.persistence.manager import PersistenceManager
    from realm.server.world import build_world
    from realm.testing import Simulator

    with Simulator(features=[]) as sim:
        # No command at all: nothing but the dispatcher's unknown handler.
        assert sim.dispatcher._commands == {} and sim.dispatcher._tokens == {}
        assert sim.dispatcher._fallbacks == []

        # Objects and a room, through ops.
        room = ops.dig(None, "Hall").value[0]
        bell = ops.create(None, "bell", location=room).value
        post = ops.create(None, "post", location=room).value
        for obj in (room, bell, post):
            sim.add(obj)
        ops.set_attr(None, bell, "colour", "bronze")
        assert bell.db.get("colour") == "bronze"

        # Softcode that calls pemit.
        alice = sim.player("Alice", location=room)
        _result, error = await sim.eval(bell, "pemit(enactor, 'Dong.')", enactor=alice)
        assert error is None
        assert "Dong." in sim.seen(alice)

        # A custom act() propagates, and an ON_<HOOK> fires on a witness.
        ops.set_attr(None, post, "on_toll", "set_attr(me, 'heard', 1)")
        _result, error = await sim.eval(
            bell, "act(here, 'The bell tolls.', targeting='room', action_type='event:toll')")
        assert error is None
        assert post.db.get("heard") == 1

        # Saved to SQLite and loaded by a second world.
        db = tmp_path / "bare.db"
        store = PersistenceManager(db)
        await store.initialize()
        for obj in (room, bell, post):
            await store.save(obj)
        await store.close()

    features = load([])
    features.install_registries()
    store = PersistenceManager(db)
    await store.initialize()
    world = build_world(store, features=features)
    try:
        await store.load_all()
        loaded = store.get_cached(bell.id)
        assert loaded is not None and loaded.db.get("colour") == "bronze"
        assert loaded.location is store.get_cached(room.id)
        assert world.dispatcher._commands == {}
    finally:
        world.close()
        await store.close()


def test_stock_game_is_only_a_feature_list():
    """In a fresh interpreter: a world of no features loads no feature
    module; the default world loads exactly CLASSIC's packages."""
    code = (
        "import json, sys\n"
        "from realm.testing import Simulator\n"
        "roots = ('realm.std', 'realm.games')\n"
        "def loaded():\n"
        "    return sorted(m for m in sys.modules if m in roots or m.startswith"
        "(('realm.std.', 'realm.games.')))\n"
        "s = Simulator(features=[]); bare = loaded(); s.close()\n"
        "s = Simulator()\n"
        "pkgs = sorted({'.'.join(m.split('.')[:3]) for m in loaded() if m.count('.') >= 2})\n"
        "s.close()\n"
        "print(json.dumps([bare, pkgs]))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True,
                         text=True, check=True)
    bare, packages = json.loads(out.stdout.strip().splitlines()[-1])
    assert bare == []
    from realm.features import _module_path, feature_names
    from realm.std import CLASSIC
    expected = sorted(_module_path(name).rpartition(".")[0]
                      for name in feature_names(list(CLASSIC)))
    assert packages == expected
