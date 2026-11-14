"""
Everything the CLI needs is inside the package (KERNEL_PLAN 9.3).

The ``realm/`` directory alone is copied to ``tmp_path`` and put first on
``PYTHONPATH``; the CLI runs from an unrelated working directory. If any
command read a sibling of the package (``examples/`` or ``scripts/`` next
to ``realm/`` in a checkout), it would fail here as it would from a wheel.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(args: list[str], cwd: Path, site: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(site)}
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
