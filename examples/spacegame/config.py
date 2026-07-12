"""
Space Game - A GURPS-based space exploration game built on REALM.

This config file is loaded by `realm start` when run from this directory.
"""

# Game identity
GAME_NAME = "Space Station Alpha"

# Database
DB_PATH = "spacegame.db"

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

    Called on first startup when the database is empty. The world (Space
    Station Alpha + Nexagen Tower) is **data** — an importable area file,
    ``data/areas/station.json``, generated from world.py/nexagen.py by
    ``scripts/build_spacegame_area.py``. init_world just imports it, the
    same way a builder would ``@import`` an area or ``@pack`` content.
    """
    import json
    from pathlib import Path

    from equipment import create_equipment_prototypes
    from ships import create_ship_prototypes

    from realm.persistence.worldio import import_objects

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

    # Equipment and ship prototypes (a richer standalone example subsystem).
    await create_equipment_prototypes(server.persistence)
    await create_ship_prototypes(server.persistence)

    print(f"Imported {len(created)} world objects from station.json")
    print(f"Starting room: {server.startup_room.name if server.startup_room else 'None'}")
