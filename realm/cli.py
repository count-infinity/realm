"""
REALM CLI - Command line interface for running REALM-based games.

Usage:
    realm init <gamename>    Create a new game project
    realm start              Start the game server from current directory
    realm start --reset-db   Reset database and start
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
import logging
import shutil
import sys
from pathlib import Path

from realm.config.loader import load_config
from realm.server.game import GameServer
from realm.templates import get_template, render_template

# Examples directory (for --template option)
EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def cmd_init(args: argparse.Namespace) -> int:
    """
    Initialize a new game project.

    Creates a directory with:
    - config.py: Game configuration
    - data/welcome.txt: Welcome screen
    - data/: Directory for database and data files

    With --template, copies from examples/<template>/ instead.
    """
    game_name = args.name
    project_dir = Path.cwd() / game_name

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
    config_content = render_template(
        "config.py.template",
        game_name=display_name,
        system_id=system_id,
    )
    (project_dir / "config.py").write_text(config_content)
    print("  Created config.py")

    # Create rules.py — the game's own GameSystem subclass, pre-wired and
    # selected by config.py. This is where the user shapes chargen/skills.
    rules_content = (
        get_template("rules.py.template")
        .replace("__GAME_NAME__", display_name)
        .replace("__GAME_ID__", system_id)
    )
    (project_dir / "rules.py").write_text(rules_content)
    print("  Created rules.py")

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
    print("Customize your rules in rules.py; other settings in config.py.")

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
    template_dir = EXAMPLES_DIR / template

    if not template_dir.exists():
        print(f"Error: Template '{template}' not found.")
        available = [d.name for d in EXAMPLES_DIR.iterdir()
                     if d.is_dir() and not d.name.startswith("_")]
        if available:
            print(f"Available templates: {', '.join(sorted(available))}")
        return 1

    print(f"Creating REALM project: {game_name} (from template: {template})")

    # Copy the template directory
    shutil.copytree(
        template_dir,
        project_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.db", "*.sqlite*"),
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


async def cmd_export(args: argparse.Namespace) -> int:
    """Export the world (or one zone) to an area file."""
    import json as _json

    from realm.config.loader import load_config
    from realm.persistence.manager import PersistenceManager, set_active_manager
    from realm.persistence.worldio import export_objects, export_zone

    settings = load_config()
    persistence = PersistenceManager(settings.db_path)
    await persistence.initialize()
    try:
        await persistence.load_all()
        set_active_manager(persistence)
        if args.zone:
            data = export_zone(args.zone)
        else:
            objects = [o for o in persistence.all_cached()
                       if args.include_players or not o.has_tag('player')]
            data = export_objects(objects)
        with open(args.file, 'w') as f:
            _json.dump(data, f, indent=2)
        print(f"Exported {len(data['objects'])} objects to {args.file}")
        return 0
    finally:
        set_active_manager(None)
        await persistence.close()


async def cmd_import(args: argparse.Namespace) -> int:
    """Import an area file into this game's world."""
    import json as _json

    from realm.config.loader import load_config
    from realm.persistence.manager import PersistenceManager, set_active_manager
    from realm.persistence.worldio import import_objects

    with open(args.file) as f:
        data = _json.load(f)

    settings = load_config()
    persistence = PersistenceManager(settings.db_path)
    await persistence.initialize()
    try:
        await persistence.load_all()
        set_active_manager(persistence)
        created = await import_objects(data, persistence)
        print(f"Imported {len(created)} objects from {args.file} "
              f"(fresh ids, references remapped)")
        return 0
    finally:
        set_active_manager(None)
        await persistence.close()


async def cmd_start(args: argparse.Namespace) -> int:
    """Start the game server from the current directory."""
    # Set up logging first
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger('realm.cli')

    # Load configuration from current directory
    try:
        settings = load_config()
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1

    logger.info(f"Starting {settings.game_name}...")

    # Handle --reset-db flag
    if args.reset_db:
        if settings.db_path.exists():
            logger.info(f"Removing existing database: {settings.db_path}")
            settings.db_path.unlink()

    # Create server from settings
    server = GameServer.from_settings(settings)

    # Run server
    try:
        await server.run_forever()
    except KeyboardInterrupt:
        logger.info("Interrupted")

    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """Show version info."""
    print("REALM Framework v0.1.0")
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
    elif args.command == "version":
        return cmd_version(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
