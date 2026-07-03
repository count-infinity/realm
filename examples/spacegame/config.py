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

    Called on first startup when the database is empty.
    """
    from world import create_world
    from equipment import create_equipment_prototypes
    from ships import create_ship_prototypes

    # Create the world
    world = await create_world(server.persistence)

    # Mark docking bay as start room
    docking_bay = world.get("docking_bay")
    if docking_bay:
        docking_bay.add_tag("start_room")
        await server.persistence.save(docking_bay)
        server.startup_room = docking_bay

    # Create equipment and ship prototypes
    await create_equipment_prototypes(server.persistence)
    await create_ship_prototypes(server.persistence)

    print(f"Created {len(world)} locations")
    print(f"Starting room: {server.startup_room.name if server.startup_room else 'None'}")
