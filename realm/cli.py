"""
REALM CLI - Command line interface for running REALM-based games.

Usage:
    realm init <gamename>    Create a new game project
    realm init <gamename> --template midgaard   ... from a shipped example
    realm start              Start the game server from current directory
    realm start --reset-db   Reset database and start
    realm features [--check] List the available features / check FEATURES
    realm import-rom <area files> [--out out.json]   Convert ROM areas
    realm version            Show version info

Typical workflow:
    1. pip install realm
    2. realm init spacegame
    3. cd spacegame
    4. realm start
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.resources
import logging
import shutil
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from realm.config.loader import load_config
from realm.server.game import GameServer
from realm.templates import get_template, render_template


def _examples() -> Any:
    """The shipped example games (``realm/examples``), inside the package so
    an installed wheel has them."""
    return importlib.resources.files("realm.examples")



#: The two parts of config.py.template a preset rewrites: from the first
#: line given through the end of the second.
_RULES_BLOCK = ("# Your game's rules", 'GAME_SYSTEM = "rules.GameRules"\n\n')
_FEATURES_BLOCK = ("# The features your game is made of.", 'FEATURES = [*CLASSIC, "game"]\n')


def _rewrite(text: str, block: tuple[str, str], new: str) -> str:
    """``text`` with the template block ``block`` replaced by ``new``."""
    start = text.index(block[0])
    end = text.index(block[1], start) + len(block[1])
    return text[:start] + new + text[end:]


#: ``realm init --features``: the FEATURES list a preset writes (None:
#: every built-in, CLASSIC) and whether it gets a rules.py.
PRESETS: dict[str, tuple[list[str] | None, bool]] = {
    "classic": (None, True),
    "social": (["accounts", "basics", "talk", "movement", "look", "items",
                "building", "game"], False),
    "bare": (["accounts", "look", "building", "game"], False),
}


def _features_settings(names: list[str]) -> str:
    listed = ", ".join(f'"{n}"' for n in names)
    return ("# The features your game is made of: built-in features by name, and\n"
            "# \"game\" is your own game.py. Add more from realm.CLASSIC as you\n"
            "# need them (`realm features` lists them all). With no \"rules\"\n"
            "# feature there is no game system: no skill checks, combat or\n"
            "# advancement, and no rules.py.\n"
            f"FEATURES = [{listed}]\n")


def cmd_init(args: argparse.Namespace) -> int:
    """
    Initialize a new game project.

    Creates a directory with:
    - config.py: Game configuration
    - rules.py: the game system (a GameSystem subclass)
    - game.py: the game's own feature (commands, behaviors, softcode)
    - data/welcome.txt: Welcome screen
    - data/: Directory for database and data files
    - tests/test_game.py: a smoke test (``pytest``)
    - README.md: how to start, test, and where code goes

    ``--features`` picks the preset: ``classic`` (every built-in, and
    rules.py), ``social`` (no rules, combat or money) or ``bare``
    (accounts, look, building and the game).

    With --template, copies the shipped example ``realm/examples/<template>/``.
    """
    game_name = args.name
    project_dir = Path.cwd() / game_name

    preset = args.features
    if preset not in PRESETS:
        print(f"Error: unknown --features preset '{preset}'. "
              f"Choose one of: {', '.join(PRESETS)}.")
        return 1
    feature_list, with_rules = PRESETS[preset]

    # Validate name
    if not game_name.isidentifier():
        print(f"Error: '{game_name}' is not a valid project name.")
        print("Use only letters, numbers, and underscores.")
        return 1

    # Check if directory exists
    if project_dir.exists():
        if not args.force:
            print(f"Error: Directory '{game_name}' already exists.")
            print("Use --force to overwrite.")
            return 1
        print(f"Warning: Overwriting existing directory '{game_name}'")
        shutil.rmtree(project_dir)

    # Handle --template option
    if args.template:
        return _init_from_template(game_name, project_dir, args.template)

    # Create minimal project structure
    print(f"Creating REALM project: {game_name}")

    # Create directories
    project_dir.mkdir(exist_ok=True)
    (project_dir / "data").mkdir(exist_ok=True)

    display_name = game_name.replace("_", " ").title()
    # A Python-safe id for this game's registered rules package.
    system_id = _sanitize_system_id(game_name)

    # Create config.py from template
    config_content = render_template("config.py.template", game_name=display_name)
    if not with_rules:
        config_content = _rewrite(config_content, _RULES_BLOCK, "")
    if feature_list is not None:
        config_content = _rewrite(config_content, _FEATURES_BLOCK,
                                  _features_settings(feature_list))
    (project_dir / "config.py").write_text(config_content)
    print("  Created config.py")

    def from_template(name: str, **extra: str) -> str:
        text = (get_template(name).replace("__GAME_NAME__", display_name)
                .replace("__GAME_ID__", system_id))
        for key, value in extra.items():
            text = text.replace(key, value)
        return text

    if with_rules:
        # rules.py — the game's own GameSystem subclass, pre-wired and
        # selected by config.py. This is where the user shapes chargen/skills.
        (project_dir / "rules.py").write_text(from_template("rules.py.template"))
        print("  Created rules.py")

    # Create game.py — the game's own feature (commands, behaviors, softcode
    # functions), listed in config.py's FEATURES as "game".
    (project_dir / "game.py").write_text(from_template("game.py.template"))
    print("  Created game.py")

    (project_dir / "tests").mkdir(exist_ok=True)
    (project_dir / "tests" / "test_game.py").write_text(
        from_template("test_game.py.template"))
    print("  Created tests/test_game.py")

    rules_line = " **Your rules:** `rules.py`." if with_rules else ""
    (project_dir / "README.md").write_text(
        from_template("README.md.template", __RULES_LINE__=rules_line))
    print("  Created README.md")

    # Create welcome.txt from template
    welcome_content = render_template(
        "welcome.txt.template",
        game_name=display_name,
    )
    (project_dir / "data" / "welcome.txt").write_text(welcome_content)
    print("  Created data/welcome.txt")

    print()
    print("Project created! Next steps:")
    print(f"  cd {game_name}")
    print("  realm start")
    print()
    print("Add commands and behaviors in game.py"
          + ("; customize your rules in rules.py" if with_rules else "")
          + "; other settings are in config.py. Run the tests with pytest.")

    return 0


def _sanitize_system_id(game_name: str) -> str:
    """A valid, lowercase Python identifier for the game's system id."""
    cleaned = "".join(c if c.isalnum() else "_" for c in game_name.lower())
    cleaned = cleaned.strip("_") or "game"
    if cleaned[0].isdigit():
        cleaned = f"g_{cleaned}"
    return cleaned


def _init_from_template(game_name: str, project_dir: Path, template: str) -> int:
    """Initialize a project by copying from an example template."""
    examples = _examples()
    source = examples / template

    if not source.is_dir():
        print(f"Error: Template '{template}' not found.")
        available = [d.name for d in examples.iterdir()
                     if d.is_dir() and not d.name.startswith("_")]
        if available:
            print(f"Available templates: {', '.join(sorted(available))}")
        return 1

    print(f"Creating REALM project: {game_name} (from template: {template})")

    # Copy the template directory. __init__.py makes the example an
    # importable package; a scaffolded game dir isn't one, and its imports
    # are repo-relative, so skip it. (The template folder itself carries
    # only the runnable game — config.py, ships.py, data/ — so there is no
    # build-time or pack-redundant Python left to exclude.)
    with importlib.resources.as_file(source) as template_dir:
        shutil.copytree(
            template_dir,
            project_dir,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.db",
                                          "*.sqlite*", "__init__.py"),
        )

    # List what was created
    for item in sorted(project_dir.rglob("*")):
        if item.is_file():
            rel_path = item.relative_to(project_dir)
            print(f"  Created {rel_path}")

    print()
    print("Project created! Next steps:")
    print(f"  cd {game_name}")
    print("  realm start")
    print()
    print("This template includes example game code - explore and modify!")

    return 0


@asynccontextmanager
async def _offline_world() -> AsyncIterator[Any]:
    """This game's world, loaded and installed, with no server around it
    (export, import, pack import). Its features' registries are installed
    before the load, as at boot, so saved behaviors find their classes."""
    from realm.features import load
    from realm.persistence.manager import PersistenceManager
    from realm.server.world import build_world

    settings = load_config()
    features = load(settings.features)
    features.install_registries()
    persistence = PersistenceManager(settings.db_path)
    await persistence.initialize()
    try:
        world = build_world(persistence, settings, features=features)
        try:
            await persistence.load_all()
            yield world
        finally:
            world.close()
    finally:
        await persistence.close()


async def cmd_export(args: argparse.Namespace) -> int:
    """Export the world (or one zone) to an area file."""
    import json as _json

    from realm.persistence.worldio import export_objects, export_zone

    async with _offline_world() as world:
        if args.zone:
            data = export_zone(args.zone)
        else:
            objects = [o for o in world.store.all_cached()
                       if args.include_players or not o.is_player]
            data = export_objects(objects)
        with open(args.file, 'w') as f:
            _json.dump(data, f, indent=2)
        print(f"Exported {len(data['objects'])} objects to {args.file}")
        return 0


async def cmd_import(args: argparse.Namespace) -> int:
    """Import an area file into this game's world."""
    import json as _json

    from realm.persistence.worldio import import_objects

    with open(args.file) as f:
        data = _json.load(f)

    async with _offline_world() as world:
        created = await import_objects(data, world.store)
        print(f"Imported {len(created)} objects from {args.file} "
              f"(fresh ids, references remapped)")
        return 0


async def cmd_pack(args: argparse.Namespace) -> int:
    """List built-in content packs, or import one into this game's world."""
    from realm.packs import import_pack, list_packs, pack_manifest

    if args.action == "list":
        packs = list_packs()
        if not packs:
            print("No built-in packs.")
            return 0
        for name in packs:
            print(f"  {name} — {pack_manifest(name).get('description', '')}")
        return 0

    # import
    if not args.name:
        print("Usage: realm pack import <name>")
        return 1

    async with _offline_world() as world:
        try:
            created = await import_pack(args.name, world.store)
        except (FileNotFoundError, ValueError) as exc:
            print(f"Error: {exc}")
            return 1
        print(f"Imported {len(created)} objects from pack '{args.name}'.")
        return 0


def _log_level(args: argparse.Namespace, settings) -> int:
    """DEBUG when ``--debug`` is passed or the game's config sets DEBUG."""
    return logging.DEBUG if args.debug or settings.debug else logging.INFO


async def cmd_start(args: argparse.Namespace) -> int:
    """Start the game server from the current directory."""
    logger = logging.getLogger('realm.cli')

    # Load configuration first: its DEBUG setting decides the log level.
    # (Until basicConfig runs, warnings and errors still reach stderr.)
    try:
        settings = load_config()
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1

    logging.basicConfig(
        level=_log_level(args, settings),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info(f"Starting {settings.game_name}...")

    # Handle --reset-db flag
    if args.reset_db:
        if settings.db_path.exists():
            logger.info(f"Removing existing database: {settings.db_path}")
            settings.db_path.unlink()

    # Create server from settings
    server = GameServer(settings)

    # Run server
    try:
        await server.run_forever()
    except KeyboardInterrupt:
        logger.info("Interrupted")

    return 0


def _plural(label: str, n: int) -> str:
    return f"{n} {label[:-1] if n == 1 and label.endswith('s') else label}"


def cmd_features(args: argparse.Namespace) -> int:
    """List every available feature, or (``--check``) load this game's
    ``FEATURES`` and report collisions and missing requirements."""
    from realm.features import FeatureError, available, feature_names, load

    try:
        settings = load_config()
    except FeatureError as exc:
        print(f"FEATURES does not load: {exc}")
        return 1
    if args.check:
        try:
            loaded = load(settings.features)
        except FeatureError as exc:
            print(f"FEATURES does not load: {exc}")
            return 1
        print(f"OK: {len(loaded.names)} features ({', '.join(loaded.names)})")
        return 0

    listed = feature_names(settings.features)
    items = available(listed)
    width = max(len(item.name) for item in items)
    for item in items:
        mark = "*" if item.name in listed else " "
        if item.error is not None:
            print(f"{item.name:<{width}} {mark} {item.source}: {item.error}")
            continue
        requires = ", ".join(item.feature.requires) or "nothing"
        counts = ", ".join(_plural(label, n) for label, n in item.declared().items())
        print(f"{item.name:<{width}} {mark} {item.source}; requires {requires}"
              + (f"; {counts}" if counts else ""))
        if item.feature.doc:
            print(f"{'':<{width}}     {item.feature.doc}")
    print("\n* listed in this game's FEATURES")
    return 0


def cmd_import_rom(args: argparse.Namespace) -> int:
    """Convert ROM 2.4 ``.are`` files to REALM area files (worldio JSON).

    One area file: its JSON goes to ``--out`` (default stdout), and
    ``--report`` prints its capability gaps to stderr. Several files, or a
    directory: ``--out`` is a directory of one JSON per area, and the MERC
    parity report goes to the file ``--report`` names (default stdout)."""
    import json

    from realm.tools import rom_import

    paths = [Path(p) for p in args.files]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        print(f"Error: no such file or directory: {', '.join(missing)}", file=sys.stderr)
        return 1
    single = len(paths) == 1 and paths[0].is_file()

    if single:
        area = rom_import.convert(paths[0].read_text(errors="replace"),
                                  repop=args.repop, zone_reset=args.zone_reset)
        text = json.dumps(rom_import.document(area), indent=2) + "\n"
        if args.out:
            Path(args.out).write_text(text)
        else:
            sys.stdout.write(text)
        print(f"[import-rom] {rom_import.summary(area)}", file=sys.stderr)
        if args.report is not None and area.gaps:
            print("\n[import-rom] capability gaps / lossy mappings:", file=sys.stderr)
            print("\n".join(rom_import.gap_lines(area)), file=sys.stderr)
        return 0

    files = rom_import.area_files(paths)
    root = paths[0] if len(paths) == 1 else None
    out = Path(args.out) if args.out else None
    result = rom_import.convert_tree(files, out, root=root, repop=args.repop,
                                     zone_reset=args.zone_reset)
    print(f"[import-rom] {result.converted} converted, {result.failed} failed "
          f"of {len(files)} files", file=sys.stderr)
    if args.report:
        Path(args.report).write_text("\n".join(result.report) + "\n")
        print(f"[import-rom] parity report -> {args.report}", file=sys.stderr)
    else:
        print("\n".join(result.report))
    return 1 if result.failed else 0


def cmd_version(args: argparse.Namespace) -> int:
    """Show version info."""
    from realm import __version__
    print(f"REALM Framework v{__version__}")
    print("Real-time Event-Action Layered MUD")
    return 0


def main() -> int:
    """Main entry point for the realm CLI."""
    parser = argparse.ArgumentParser(
        prog="realm",
        description="REALM MUD Framework CLI",
        epilog="Typical workflow: realm init mygame && cd mygame && realm start",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # realm init <name>
    init_parser = subparsers.add_parser(
        "init",
        help="Create a new game project",
    )
    init_parser.add_argument(
        "name",
        help="Name for the new game project (creates directory)",
    )
    init_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing directory",
    )
    init_parser.add_argument(
        "--template", "-t",
        help="Use an example template (e.g., spacegame)",
    )
    init_parser.add_argument(
        "--features", default="classic", choices=list(PRESETS),
        help="classic: every built-in feature and a rules.py (default); "
             "social: no rules, combat or money; bare: accounts, look, building")

    # realm export / import
    export_parser = subparsers.add_parser(
        "export", help="Export the world (or one zone) to an area file")
    export_parser.add_argument("file", help="Output file (.realm, JSON content)")
    export_parser.add_argument("--zone", help="Export only this zone")
    export_parser.add_argument("--include-players", action="store_true",
                               help="Include player characters (passwords always stripped)")

    import_parser = subparsers.add_parser(
        "import", help="Import an area file into this game's world")
    import_parser.add_argument("file", help="Area file to import")

    # realm pack list / realm pack import <name>
    pack_parser = subparsers.add_parser(
        "pack", help="List or import built-in content packs")
    pack_parser.add_argument("action", choices=["list", "import"],
                             help="list the packs, or import one")
    pack_parser.add_argument("name", nargs="?",
                             help="pack name (for 'import')")

    # realm start
    start_parser = subparsers.add_parser(
        "start",
        help="Start the game server from current directory",
    )
    start_parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Remove existing database and start fresh",
    )
    start_parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug logging",
    )

    # realm import-rom <area files> [--out ...]
    rom_parser = subparsers.add_parser(
        "import-rom", help="Convert ROM 2.4 .are files to REALM area files")
    rom_parser.add_argument(
        "files", nargs="+",
        help="ROM .are files, or directories searched for *.are / *.are.txt")
    rom_parser.add_argument(
        "--out", "-o",
        help="one file: the JSON to write (default stdout); several or a "
             "directory: the directory to write one JSON per area into")
    rom_parser.add_argument(
        "--repop", action="store_true",
        help="emit self-repopulating spawners for mob resets")
    rom_parser.add_argument(
        "--zone-reset", action="store_true",
        help="emit a zone master with a zone_reset behavior (whole-area "
             "restore when empty); an alternative to --repop")
    rom_parser.add_argument(
        "--report", nargs="?", const="", default=None,
        help="one file: print its capability gaps to stderr; several: write "
             "the parity report (markdown) to this file")

    # realm features [--check]
    features_parser = subparsers.add_parser(
        "features", help="List the available features, or check this game's FEATURES")
    features_parser.add_argument(
        "--check", action="store_true",
        help="Load FEATURES and report collisions and missing requirements")

    # realm version
    subparsers.add_parser("version", help="Show version info")

    args = parser.parse_args()

    if args.command == "init":
        return cmd_init(args)
    elif args.command == "start":
        return asyncio.run(cmd_start(args))
    elif args.command == "export":
        return asyncio.run(cmd_export(args))
    elif args.command == "import":
        return asyncio.run(cmd_import(args))
    elif args.command == "pack":
        return asyncio.run(cmd_pack(args))
    elif args.command == "import-rom":
        return cmd_import_rom(args)
    elif args.command == "features":
        return cmd_features(args)
    elif args.command == "version":
        return cmd_version(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
