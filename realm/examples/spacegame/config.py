"""
Space Game - A GURPS-based space exploration game built on REALM.

This config file is loaded by `realm start` when run from this directory.
The rules are ``rules.py`` (GURPS, subclassed); the game's own commands,
behaviors and softcode functions go in ``game.py``.
"""

# Game identity
GAME_NAME = "Space Station Alpha"

# Database
DB_PATH = "spacegame.db"

# The rules: GameRules in rules.py, a subclass of the built-in GURPS system.
GAME_SYSTEM = "rules.GameRules"

# Every built-in feature, and this game's own game.py.
from realm import CLASSIC  # noqa: E402

FEATURES = [*CLASSIC, "game"]

# Network
TELNET_PORT = 4000
TELNET_HOST = "0.0.0.0"
ENABLE_TELNET = True
ENABLE_WEBSOCKET = False

# Welcome banner
WELCOME_BANNER = """
╔══════════════════════════════════════════════════════════════╗
║                    SPACE STATION ALPHA                       ║
║              A GURPS-based Space Adventure                   ║
╠══════════════════════════════════════════════════════════════╣
║  The year is 2387. You've just docked at Space Station      ║
║  Alpha, a bustling hub of commerce and intrigue at the      ║
║  edge of known space.                                        ║
╚══════════════════════════════════════════════════════════════╝
"""


async def init_world(server):
    """
    Initialize the space game world.

    Called on first startup when the database is empty. Everything the game
    ships with is content, imported the way a builder would:

    - **World** (Space Station Alpha + Nexagen Tower): the area file
      ``data/areas/station.json`` (imported like ``@import``).
    - **Classes, skills, and gear**: the built-in ``gurps-scifi`` content
      pack (imported like ``@pack import gurps-scifi``).
    - **Ships**: ``ships.py`` — ship templates and a small wrapper. A
      ship's shields, armor and hull are pools (shields overflow into an
      armored hull), so stock combat, spells and softcode ``damage()`` work
      on ships with no ship code (see the note in that file).

    The area file is generated from world.py/nexagen.py by
    ``scripts/build_spacegame_area.py``; those generators live in the engine
    repo, not in a scaffolded game.
    """
    import json
    from pathlib import Path

    from ships import create_ship_prototypes

    from realm import import_objects, import_pack

    area = Path(__file__).parent / "data" / "areas" / "station.json"
    # preserve_ids: this is the canonical first-boot world, and some NPC
    # softcode references rooms by absolute id (#nexagen_floor46), which a
    # fresh-id clone would break.
    created = await import_objects(json.loads(area.read_text()),
                                   server.persistence, preserve_ids=True)
    # The area carries its own start room (docking bay, tagged start_room).
    for obj in created:
        if obj.has_tag("start_room"):
            server.startup_room = obj
            break

    # Classes, skills, and gear come from the content pack — one source of
    # truth, importable into any REALM game.
    pack = await import_pack("gurps-scifi", server.persistence)

    # Ship prototypes, one per template (their health is pools).
    await create_ship_prototypes(server.persistence)

    print(f"Imported {len(created)} world objects from station.json, "
          f"{len(pack)} from the gurps-scifi pack.")
    print(f"Starting room: {server.startup_room.name if server.startup_room else 'None'}")
