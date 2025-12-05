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
import os
import sys
from pathlib import Path

from realm.config.loader import load_config
from realm.server.game import GameServer
from realm.templates import render_template, get_template


def cmd_init(args: argparse.Namespace) -> int:
    """
    Initialize a new game project.

    Creates a directory with:
    - config.py: Game configuration
    - data/welcome.txt: Welcome screen
    - data/: Directory for database and data files
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

    # Create project structure
    print(f"Creating REALM project: {game_name}")

    # Create directories
    project_dir.mkdir(exist_ok=True)
    (project_dir / "data").mkdir(exist_ok=True)

    # Create config.py from template
    config_content = render_template(
        "config.py.template",
        game_name=game_name.replace("_", " ").title(),
    )
    (project_dir / "config.py").write_text(config_content)
    print(f"  Created config.py")

    # Create welcome.txt from template
    welcome_content = render_template(
        "welcome.txt.template",
        game_name=game_name.replace("_", " ").title(),
    )
    (project_dir / "data" / "welcome.txt").write_text(welcome_content)
    print(f"  Created data/welcome.txt")

    print()
    print(f"Project created! Next steps:")
    print(f"  cd {game_name}")
    print(f"  realm start")
    print()
    print("Edit config.py to customize your game.")

    return 0


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
    elif args.command == "version":
        return cmd_version(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
