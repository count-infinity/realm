"""
Add-on features as installable packages (KERNEL_PLAN 9.2).

A package declares a feature in the entry-point group ``realm.features``.
Installed means available, not enabled: it runs only when a game lists it
in ``FEATURES``. Each test installs a fake distribution: a ``*.dist-info``
with an ``entry_points.txt``, under ``tmp_path`` on ``sys.path``.
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

import pytest

from realm.features import FeatureError, load

WEATHER = '''
from realm import Feature

feature = Feature("weather", requires=["talk"], doc="Rain and shine.")

async def forecast(ctx):
    await ctx.session.send("Rain.")

feature.command("forecast", forecast, help_text="Tomorrow's weather")
feature.setting("WEATHER_SEED", 1, "Seed for the weather.")
'''


def install(root: Path, dist: str, entries: dict[str, str], modules: dict[str, str],
            version: str = "1.0") -> None:
    """A fake installed distribution ``dist`` under ``root``."""
    info = root / f"{dist.replace('-', '_')}-{version}.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {dist}\nVersion: {version}\n")
    lines = "".join(f"{name} = {target}\n" for name, target in entries.items())
    (info / "entry_points.txt").write_text(f"[realm.features]\n{lines}")
    for module, source in modules.items():
        (root / f"{module}.py").write_text(textwrap.dedent(source))


@pytest.fixture
def site(tmp_path, monkeypatch):
    root = tmp_path / "site"
    root.mkdir()
    monkeypatch.syspath_prepend(str(root))
    yield root
    for name in [m for m in sys.modules if m.startswith("realm_")]:
        del sys.modules[name]


class TestResolution:

    def test_an_installed_feature_loads_by_name(self, site):
        install(site, "realm-weather", {"weather": "realm_weather:feature"},
                {"realm_weather": WEATHER})
        loaded = load(["talk", "weather"])
        assert loaded.names == ["talk", "weather"]

    def test_installed_is_available_not_enabled(self, site):
        install(site, "realm-weather", {"weather": "realm_weather:feature"},
                {"realm_weather": WEATHER})
        loaded = load(["talk"])
        assert loaded.names == ["talk"]
        assert "realm_weather" not in sys.modules      # never even imported

    def test_its_requirements_are_checked_like_any_feature(self, site):
        install(site, "realm-weather", {"weather": "realm_weather:feature"},
                {"realm_weather": WEATHER})
        with pytest.raises(FeatureError, match="'weather' requires 'talk'"):
            load(["weather"])

    def test_a_built_in_name_cannot_be_claimed(self, site):
        install(site, "realm-chatter", {"talk": "realm_chatter:feature"},
                {"realm_chatter": 'from realm import Feature\nfeature = Feature("talk")\n'})
        with pytest.raises(FeatureError, match="'talk'.*built.in.*realm-chatter"):
            load(["basics"])                              # any load, not only talk

    def test_two_packages_cannot_claim_one_name(self, site):
        for dist, module in (("realm-rain", "realm_rain"), ("realm-sun", "realm_sun")):
            install(site, dist, {"weather": f"{module}:feature"},
                    {module: 'from realm import Feature\nfeature = Feature("weather")\n'})
        with pytest.raises(FeatureError, match="'weather'.*realm-rain.*realm-sun"):
            load(["weather"])

    def test_the_entry_point_must_name_its_feature(self, site):
        install(site, "realm-weather", {"climate": "realm_weather:feature"},
                {"realm_weather": WEATHER})
        with pytest.raises(FeatureError, match="'climate'.*named 'weather'"):
            load(["talk", "climate"])

    def test_the_entry_point_must_be_a_feature(self, site):
        install(site, "realm-weather", {"weather": "realm_weather:OOPS"},
                {"realm_weather": "OOPS = 3\n"})
        with pytest.raises(FeatureError, match="'weather'.*realm-weather.*not a Feature"):
            load(["weather"])

    def test_an_unknown_name_lists_what_is_installed(self, site):
        install(site, "realm-weather", {"weather": "realm_weather:feature"},
                {"realm_weather": WEATHER})
        with pytest.raises(FeatureError, match="installed.*weather"):
            load(["wether"])


# --- realm features --------------------------------------------------------------


def _game(tmp_path: Path, features: list[str], game_py: str | None = None) -> Path:
    game = tmp_path / "mygame"
    game.mkdir()
    (game / "config.py").write_text(f"FEATURES = {features!r}\n")
    if game_py is not None:
        (game / "game.py").write_text(textwrap.dedent(game_py))
    return game


def _run(monkeypatch, game: Path, *, check: bool) -> int:
    from realm.cli import cmd_features
    monkeypatch.chdir(game)
    monkeypatch.syspath_prepend(str(game))
    try:
        return cmd_features(argparse.Namespace(check=check))
    finally:
        sys.modules.pop("game", None)


class TestTheCommand:

    def test_it_lists_every_source(self, site, tmp_path, monkeypatch, capsys):
        install(site, "realm-weather", {"weather": "realm_weather:feature"},
                {"realm_weather": WEATHER})
        game = _game(tmp_path, ["talk", "game"], """
            from realm import Feature
            feature = Feature("mygame", requires=["talk"])
            """)
        assert _run(monkeypatch, game, check=False) == 0
        out = capsys.readouterr().out
        lines = {line.split()[0]: line for line in out.splitlines() if line.strip()
                 and not line.startswith(" ")}
        assert "built-in" in lines["talk"]
        assert "installed: realm-weather 1.0" in lines["weather"]
        assert "requires talk" in lines["weather"]
        assert "1 command" in lines["weather"] and "1 setting" in lines["weather"]
        assert "game directory" in lines["mygame"]
        assert "combat" in lines                       # built-ins not in FEATURES too

    def test_check_passes_a_sound_game(self, site, tmp_path, monkeypatch, capsys):
        install(site, "realm-weather", {"weather": "realm_weather:feature"},
                {"realm_weather": WEATHER})
        game = _game(tmp_path, ["talk", "weather"])
        assert _run(monkeypatch, game, check=True) == 0
        assert "OK: 2 features" in capsys.readouterr().out

    def test_check_reports_a_missing_requirement(self, site, tmp_path, monkeypatch, capsys):
        install(site, "realm-weather", {"weather": "realm_weather:feature"},
                {"realm_weather": WEATHER})
        game = _game(tmp_path, ["weather"])
        assert _run(monkeypatch, game, check=True) == 1
        assert "'weather' requires 'talk'" in capsys.readouterr().out

    def test_check_reports_a_collision(self, site, tmp_path, monkeypatch, capsys):
        install(site, "realm-weather", {"weather": "realm_weather:feature"},
                {"realm_weather": WEATHER})
        game = _game(tmp_path, ["talk", "weather", "game"], """
            from realm import Feature
            feature = Feature("mygame")

            async def forecast(ctx):
                pass

            feature.command("forecast", forecast)
            """)
        assert _run(monkeypatch, game, check=True) == 1
        out = capsys.readouterr().out
        assert "'forecast'" in out and "'weather'" in out and "'mygame'" in out
