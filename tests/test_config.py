"""The config loader: every documented key must actually be consumed.

Two bug classes guarded here, both of the same silent-death family as a
typo'd action type:

- a REAL key the loader forgets to read (``WELCOME_BANNER``, ``EMOTE_SIGIL``
  and ``RECURSION_LIMIT`` all shipped ignored at some point — the dataclass
  default silently won), and
- a TYPO'D key in a game's config.py (``WELCOME_BANER``), which merges into
  the dict, matches nothing, and vanishes without a trace.

The first is pinned by loading a config that sets the once-dead keys and
asserting they flow through; by the KNOWN_CONFIG_KEYS/source cross-check;
and the second by the near-miss warning.
"""

from __future__ import annotations

import ast
import logging
import pathlib

from realm.config.loader import KNOWN_CONFIG_KEYS, load_config

LOADER_SRC = pathlib.Path(load_config.__code__.co_filename)


def _write_config(tmp_path, body: str):
    (tmp_path / "config.py").write_text(body, encoding="utf-8")
    return tmp_path


class TestKeysAreConsumed:

    def test_welcome_banner_flows_through(self, tmp_path):
        game = _write_config(tmp_path, 'WELCOME_BANNER = "Hail, adventurer!"\n')
        settings = load_config(game)
        assert settings.welcome_banner == "Hail, adventurer!"

    def test_welcome_banner_defaults_to_none(self, tmp_path):
        game = _write_config(tmp_path, 'GAME_NAME = "Bare"\n')
        settings = load_config(game)
        assert settings.welcome_banner is None

    def test_once_dead_keys_flow_through(self, tmp_path):
        # EMOTE_SIGIL and RECURSION_LIMIT were documented and silently
        # ignored — the Settings build never read them from config.
        game = _write_config(
            tmp_path,
            'EMOTE_SIGIL = "!"\nRECURSION_LIMIT = 2000\n',
        )
        settings = load_config(game)
        assert settings.emote_sigil == "!"
        assert settings.recursion_limit == 2000


class TestOneSourceOfDefaults:
    """Settings declares every key once; the scaffold template and the code
    must agree with it (KERNEL_PLAN 2.1)."""

    def _template(self):
        from realm.templates import render_template
        return render_template("config.py.template", game_name="Testia")

    def _active_assignments(self) -> dict[str, object]:
        out = {}
        for node in ast.parse(self._template()).body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id.isupper()):
                try:
                    out[node.targets[0].id] = ast.literal_eval(node.value)
                except ValueError:      # FEATURES = [*CLASSIC, "game"]
                    out[node.targets[0].id] = None
        return out

    def test_every_template_key_is_known(self):
        import re
        active = set(self._active_assignments())
        commented = set(re.findall(r"^#\s*([A-Z][A-Z0-9_]+)\s*=", self._template(),
                                   flags=re.MULTILINE))
        from realm.config.loader import known_config_keys
        unknown = (active | commented) - known_config_keys()
        assert not unknown, f"template keys neither Settings nor a feature declares: {sorted(unknown)}"

    def test_active_template_values_equal_the_defaults(self):
        from dataclasses import fields

        from realm.config.loader import Settings
        defaults = {f.metadata["key"]: f.default
                    for f in fields(Settings) if "key" in f.metadata}
        differ = {}
        for key, value in self._active_assignments().items():
            if key in ("GAME_NAME", "GAME_SYSTEM", "FEATURES"):
                continue
            default = defaults[key]
            if isinstance(default, pathlib.Path):
                value = pathlib.Path(value)
            if value != default:
                differ[key] = (value, default)
        assert not differ, f"template value vs Settings default: {differ}"

    def test_no_getattr_settings_fallbacks_in_the_engine(self):
        realm_dir = LOADER_SRC.parent.parent
        offenders = [str(p.relative_to(realm_dir.parent))
                     for p in realm_dir.rglob("*.py")
                     if "getattr(settings" in p.read_text(encoding="utf-8")]
        assert offenders == []

    def test_config_reference_is_current(self):
        """docs/reference/config.md is generated from Settings; rerun
        scripts/gen_config_docs.py after changing a field."""
        import importlib.util
        root = LOADER_SRC.parent.parent.parent
        spec = importlib.util.spec_from_file_location(
            "gen_config_docs", root / "scripts" / "gen_config_docs.py")
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        on_disk = (root / "docs" / "reference" / "config.md").read_text(encoding="utf-8")
        assert on_disk == gen.render(), "run: python scripts/gen_config_docs.py"

    def test_every_key_has_a_doc(self):
        from dataclasses import fields

        from realm.config.loader import Settings
        undocumented = [f.name for f in fields(Settings)
                        if ("key" in f.metadata or f.metadata.get("callback"))
                        and not f.metadata["doc"].strip()]
        assert undocumented == []


class TestNearMissWarning:

    def test_typo_of_a_real_key_warns(self, tmp_path, caplog):
        game = _write_config(tmp_path, 'WELCOME_BANER = "oops"\n')
        with caplog.at_level(logging.WARNING, logger="realm.config.loader"):
            settings = load_config(game)
        assert settings.welcome_banner is None       # the typo did nothing
        assert any("WELCOME_BANER" in r.message and "WELCOME_BANNER" in r.message
                   for r in caplog.records)

    def test_honest_user_constants_stay_silent(self, tmp_path, caplog):
        # Configs legitimately define their own constants for init_world.
        game = _write_config(tmp_path, 'START_ROOM_VNUM = 3025\n')
        with caplog.at_level(logging.WARNING, logger="realm.config.loader"):
            load_config(game)
        assert not any("START_ROOM_VNUM" in r.message for r in caplog.records)


class TestWelcomeScreenPriority:

    def _server(self, **attrs):
        # _get_welcome_screen touches only these attributes; a full
        # GameServer() boot mutates ambient module state (sigils etc.).
        from realm.config.loader import Settings
        from realm.server.game import GameServer
        server = GameServer.__new__(GameServer)
        server.settings = Settings(**{"game_name": "Testia", "welcome_file": None, **attrs})
        return server

    def test_banner_wins_over_file(self, tmp_path):
        welcome = tmp_path / "welcome.txt"
        welcome.write_text("from the file", encoding="utf-8")
        server = self._server(welcome_banner="from the config",
                              welcome_file=welcome)
        assert server._get_welcome_screen() == "from the config"

    def test_file_wins_when_no_banner(self, tmp_path):
        welcome = tmp_path / "welcome.txt"
        welcome.write_text("from the file", encoding="utf-8")
        server = self._server(welcome_file=welcome)
        assert server._get_welcome_screen() == "from the file"

    def test_default_when_neither(self):
        server = self._server()
        assert "Testia" in server._get_welcome_screen()


class TestTickIntervalDefault:

    def test_bare_config_gets_the_settings_heartbeat(self, tmp_path):
        """defaults.py said 4.0 while Settings, GameServer and the time
        design doc said 0.1; a fresh scaffold silently ran a 4 s heartbeat."""
        from realm.config.loader import Settings
        game = _write_config(tmp_path, 'GAME_NAME = "Bare"\n')
        settings = load_config(game)
        assert settings.tick_interval == Settings().tick_interval == 0.1


class TestDebugSetting:
    """DEBUG in config.py used to be read into Settings and then ignored;
    only --debug changed the log level (KERNEL_PLAN 1.9 C)."""

    def _level(self, tmp_path, body, debug_flag):
        import argparse

        from realm.cli import _log_level
        settings = load_config(_write_config(tmp_path, body))
        return _log_level(argparse.Namespace(debug=debug_flag), settings)

    def test_config_debug_turns_on_debug_logging(self, tmp_path):
        assert self._level(tmp_path, "DEBUG = True\n", False) == logging.DEBUG

    def test_flag_still_works(self, tmp_path):
        assert self._level(tmp_path, 'GAME_NAME = "X"\n', True) == logging.DEBUG

    def test_default_is_info(self, tmp_path):
        assert self._level(tmp_path, 'GAME_NAME = "X"\n', False) == logging.INFO
