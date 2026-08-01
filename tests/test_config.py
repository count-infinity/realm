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

    def test_known_keys_match_what_the_source_reads(self):
        """KNOWN_CONFIG_KEYS must equal the config.get('UPPER') calls in the
        loader — if someone adds a key without registering it (or registers
        one that is never read), this fails and names it."""
        tree = ast.parse(LOADER_SRC.read_text(encoding="utf-8"))
        read = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                    and node.args[0].value.isupper()):
                read.add(node.args[0].value)
        assert read == set(KNOWN_CONFIG_KEYS), (
            f"unregistered-but-read: {sorted(read - KNOWN_CONFIG_KEYS)}; "
            f"registered-but-never-read: {sorted(KNOWN_CONFIG_KEYS - read)}"
        )


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
        from realm.server.game import GameServer
        server = GameServer.__new__(GameServer)
        server.game_name = "Testia"
        server.welcome_banner = None
        server.welcome_file = None
        for key, value in attrs.items():
            setattr(server, key, value)
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
