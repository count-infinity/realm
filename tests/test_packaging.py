"""
Everything the CLI needs is inside the package (KERNEL_PLAN 9.3).

The ``realm/`` directory alone is copied to ``tmp_path`` and put first on
``PYTHONPATH``; the CLI runs from an unrelated working directory. If any
command read a sibling of the package (``examples/`` or ``scripts/`` next
to ``realm/`` in a checkout), it would fail here as it would from a wheel.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _run(args: list[str], cwd: Path, site: Path, *extra: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(str(p) for p in (site, *extra))}
    return subprocess.run([sys.executable, *args], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=120)


def test_the_package_alone_runs_the_cli(tmp_path):
    site = tmp_path / "site"
    shutil.copytree(ROOT / "realm", site / "realm",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    work = tmp_path / "work"
    work.mkdir()

    where = _run(["-c", "import realm; print(realm.__file__)"], work, site)
    assert where.stdout.strip().startswith(str(site)), where.stdout + where.stderr

    init = _run(["-m", "realm.cli", "init", "demo", "--template", "spacegame"], work, site)
    assert init.returncode == 0, init.stdout + init.stderr
    assert (work / "demo" / "config.py").is_file()
    assert (work / "demo" / "ships.py").is_file()
    assert (work / "demo" / "data" / "areas" / "station.json").is_file()

    init = _run(["-m", "realm.cli", "init", "town", "--template", "midgaard"], work, site)
    assert init.returncode == 0, init.stdout + init.stderr
    for name in ("config.py", "game.py", "rules.py", "tests/test_game.py", "README.md",
                 "data/areas/midgaard.json"):
        assert (work / "town" / name).is_file(), name
    tests = _run(["-m", "pytest", "-q", "-p", "no:randomly", "-p", "no:cacheprovider"],
                 work / "town", site)
    assert tests.returncode == 0, tests.stdout + tests.stderr

    features = _run(["-m", "realm.cli", "features"], work / "demo", site)
    assert features.returncode == 0, features.stdout + features.stderr
    assert "combat" in features.stdout

    check = _run(["-m", "realm.cli", "features", "--check"], work / "demo", site)
    assert check.returncode == 0, check.stdout + check.stderr
    assert check.stdout.startswith("OK:")


def test_a_fresh_game_passes_its_own_tests(tmp_path):
    """KERNEL_PLAN step 9 acceptance: from an empty directory, with only the
    package on the path, ``realm init demo && cd demo && pytest -q && realm
    features --check`` succeeds."""
    site = tmp_path / "site"
    shutil.copytree(ROOT / "realm", site / "realm",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    work = tmp_path / "empty"
    work.mkdir()

    init = _run(["-m", "realm.cli", "init", "demo"], work, site)
    assert init.returncode == 0, init.stdout + init.stderr

    tests = _run(["-m", "pytest", "-q", "-p", "no:randomly", "-p", "no:cacheprovider"],
                 work / "demo", site)
    assert tests.returncode == 0, tests.stdout + tests.stderr
    assert "1 passed" in tests.stdout

    check = _run(["-m", "realm.cli", "features", "--check"], work / "demo", site)
    assert check.returncode == 0, check.stdout + check.stderr
    assert check.stdout.startswith("OK:")


PAGE = ROOT / "realm" / "web" / "index.html"
#: Added to the copy's page only, so a page read from anywhere else shows.
COPY_MARK = "<!-- the copy -->\n"


def _copy_package(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    shutil.copytree(ROOT / "realm", site / "realm",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    copied = site / "realm" / "web" / "index.html"
    copied.write_text(copied.read_text(encoding="utf-8") + COPY_MARK, encoding="utf-8")
    return site


def test_the_browser_client_ships_in_the_package(tmp_path):
    """MUD_PLAN step 16: the page is package data, read from the package."""
    site = _copy_package(tmp_path)
    read = _run(["-c", "import realm, sys; from realm.gateway.websocket import client_page; "
                       "print(realm.__file__); sys.stdout.write(client_page())"],
                tmp_path, site)
    assert read.returncode == 0, read.stderr
    where, page = read.stdout.split("\n", 1)
    assert where.startswith(str(site))
    assert page == PAGE.read_text(encoding="utf-8") + COPY_MARK


SERVE = """
import asyncio, realm, sys
from aiohttp.test_utils import TestClient, TestServer
from realm.gateway.session import SessionManager
from realm.gateway.websocket import WebSocketServer

async def main():
    server = WebSocketServer(SessionManager(), None, web_client=True, game_name="Shipped")
    async with TestClient(TestServer(server.make_app())) as client:
        response = await client.get("/")
        print(realm.__file__)
        print(response.status)
        sys.stdout.write(await response.text())

asyncio.run(main())
"""


@pytest.mark.skipif(importlib.util.find_spec("aiohttp") is None,
                    reason="aiohttp is not installed (pip install 'realm[websocket]')")
def test_the_browser_client_is_served_from_the_package_alone(tmp_path):
    import aiohttp
    site = _copy_package(tmp_path)
    # aiohttp's own install, wherever it is; nothing else from the checkout.
    served = _run(["-c", SERVE], tmp_path, site, Path(aiohttp.__file__).parent.parent)
    assert served.returncode == 0, served.stderr
    where, status, page = served.stdout.split("\n", 2)
    assert where.startswith(str(site)) and status == "200"
    assert page == (PAGE.read_text(encoding="utf-8") + COPY_MARK).replace(
        "{{GAME_NAME}}", "Shipped")
