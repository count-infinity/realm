"""
REALM CLI - Command line interface for running REALM-based games.

Usage:
    realm start          Start the game server
    realm start --init   Initialize world and start server
    realm version        Show version info
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from realm.server.game import GameServer


def find_game_config() -> dict[str, Any]:
    """
    Find and load game configuration from current directory.

    Looks for:
    1. realm_config.py - Python config file
    2. realm.toml - TOML config file (future)

    Returns default config if nothing found.
    """
    cwd = Path.cwd()

    # Try realm_config.py
    config_py = cwd / "realm_config.py"
    if config_py.exists():
        spec = importlib.util.spec_from_file_location("realm_config", config_py)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.path.insert(0, str(cwd))
            try:
                spec.loader.exec_module(module)
            finally:
                sys.path.pop(0)

            config = {}
            for key in dir(module):
                if not key.startswith('_'):
                    config[key] = getattr(module, key)
            return config

    # Default config
    return {
        'GAME_NAME': 'REALM',
        'DB_PATH': 'game.db',
        'TELNET_PORT': 4000,
        'TELNET_HOST': '0.0.0.0',
        'WEBSOCKET_PORT': 4001,
        'ENABLE_TELNET': True,
        'ENABLE_WEBSOCKET': False,
    }


async def cmd_start(args: argparse.Namespace) -> int:
    """Start the game server."""
    config = find_game_config()

    game_name = config.get('GAME_NAME', 'REALM')
    db_path = config.get('DB_PATH', 'game.db')
    telnet_port = config.get('TELNET_PORT', 4000)
    telnet_host = config.get('TELNET_HOST', '0.0.0.0')

    # Set up logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger = logging.getLogger('realm.cli')
    logger.info(f"Starting {game_name}...")

    # Handle --init flag
    if args.init:
        db_file = Path(db_path)
        if db_file.exists():
            logger.info(f"Removing existing database: {db_path}")
            db_file.unlink()

    # Create server
    server = GameServer(
        db_path=db_path,
        telnet_port=telnet_port,
        telnet_host=telnet_host,
        enable_telnet=config.get('ENABLE_TELNET', True),
        enable_websocket=config.get('ENABLE_WEBSOCKET', False),
    )

    # Hook up world initialization if provided in config
    init_world = config.get('init_world')
    if init_world and callable(init_world):
        async def do_init():
            if server.persistence:
                # Check if world needs initialization
                obj_count = len(server.persistence._object_cache)
                if obj_count <= 1:  # Only default void room
                    logger.info("Initializing game world...")
                    await init_world(server)
                    logger.info("World initialized")

        server.on_start(do_init)

    # Hook up custom welcome banner if provided
    welcome_banner = config.get('WELCOME_BANNER')
    if welcome_banner:
        original_connect = server._on_session_connect
        async def custom_connect(session):
            await session.send(welcome_banner)
            # Still show default login prompts
            await session.send("\nEnter 'connect <name> <password>' to log in")
            await session.send("Enter 'create <name> <password>' to create a new character")
            await session.send("")
        server._on_session_connect = custom_connect

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
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # realm start
    start_parser = subparsers.add_parser("start", help="Start the game server")
    start_parser.add_argument(
        "--init", action="store_true",
        help="Initialize world from scratch (removes existing DB)"
    )
    start_parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug logging"
    )
    start_parser.add_argument(
        "--port", type=int,
        help="Override telnet port"
    )

    # realm version
    subparsers.add_parser("version", help="Show version info")

    args = parser.parse_args()

    if args.command == "start":
        return asyncio.run(cmd_start(args))
    elif args.command == "version":
        return cmd_version(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
