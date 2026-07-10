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
from realm.systems.base import GameSystemRegistry


class _Args:
    def __init__(self, name, force=False, template=None):
        self.name = name
        self.force = force
        self.template = template


@pytest.fixture
def clean_import_state():
    """Loading a generated config imports a top-level `rules` module and
    mutates sys.path — undo both so tests stay isolated."""
    before_path = list(sys.path)
    yield
    sys.modules.pop("rules", None)
    sys.path[:] = before_path


def test_init_creates_prewired_rules(tmp_path, monkeypatch, clean_import_state):
    monkeypatch.chdir(tmp_path)
    assert cmd_init(_Args("questcove")) == 0

    project = tmp_path / "questcove"
    config_py = project / "config.py"
    rules_py = project / "rules.py"
    assert config_py.exists() and rules_py.exists()

    # config selects the game's own system and imports rules.py for it.
    config_text = config_py.read_text()
    assert 'GAME_SYSTEM = "questcove"' in config_text
    assert "import rules" in config_text
    assert 'system_id = "questcove"' in rules_py.read_text()

    # And it actually resolves: loading the config registers GameRules and
    # GAME_SYSTEM points at it (behaving like GURPS until customized).
    settings = load_config(project)
    assert settings.game_system == "questcove"
    system = GameSystemRegistry.create(settings.game_system)
    assert system is not None
    assert type(system).__name__ == "GameRules"
    assert type(system).__mro__[1].__name__ == "GurpsSystem"
    assert len(system.chargen_steps()) == 2   # stock GURPS flow, unchanged


def test_sanitize_system_id():
    assert _sanitize_system_id("MyGame") == "mygame"
    assert _sanitize_system_id("space-frontier") == "space_frontier"
    assert _sanitize_system_id("2cool") == "g_2cool"    # id can't start with a digit
    assert _sanitize_system_id("___") == "game"         # never empty
