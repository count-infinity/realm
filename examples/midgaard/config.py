"""
Midgaard - a playable Diku/Merc game on REALM.

`realm start` from this directory loads it. Everything ships as content,
imported the way a builder would:

- **World**: ``data/areas/midgaard.json`` - the classic Midgaard, converted
  from its ROM ``.are`` with ``scripts/rom_import.py --repop`` so its mobs
  (the beastly fido, beggars, cityguards) respawn on death. Import any other
  converted ROM area alongside it the same way.
- **Rules**: the ``merc`` game system (``GAME_SYSTEM`` below) - THAC0
  combat, percentile skills, XP-and-level advancement. Pick a class at
  character creation; a level-1 barbarian starts kitted with a club in the
  Common Square, ready to thrash fidos and trade at the shops next door.
- **Spells**: the built-in ``merc-classic`` content pack (the mage/cleric
  lines plus the breaths), imported at boot the way ``@pack import`` would.
"""

GAME_NAME = "Midgaard"
DB_PATH = "midgaard.db"

TELNET_PORT = 4000
TELNET_HOST = "0.0.0.0"
ENABLE_TELNET = True
ENABLE_WEBSOCKET = False

# The rules package. This is the one line that makes it a Diku: swap it for
# realm.systems.GurpsSystem or .D20System and the same world runs those rules.
GAME_SYSTEM = "realm.systems.MercSystem"

WELCOME_BANNER = """
+==============================================================+
|                        M I D G A A R D                       |
|            The classic Diku town, running on REALM           |
+==============================================================+
|  Create a character, choose a class (try 'barbarian'), and   |
|  you will wake in the Common Square with a club in hand.     |
|  Kill the fidos, sell what drops, and earn your name.        |
+==============================================================+
"""

# The Common Square (ROM vnum 3025): the town center. Fidos spawn here and
# the General Store / Weapon Shop / Armoury are a step away.
START_ROOM_VNUM = 3025


async def init_world(server):
    """First-boot world load (empty database only)."""
    import json
    from pathlib import Path

    from realm.packs import import_pack
    from realm.persistence.worldio import import_objects

    area = Path(__file__).parent / "data" / "areas" / "midgaard.json"
    # preserve_ids: the area's exits and resets reference rooms by their
    # rom_<vnum> ids, which a fresh-id clone would break.
    created = await import_objects(json.loads(area.read_text()),
                                   server.persistence, preserve_ids=True)

    # Drop new characters into the Common Square.
    for obj in created:
        if obj.has_tag("room") and obj.db.get("rom_vnum") == START_ROOM_VNUM:
            server.startup_room = obj
            break

    # Spells: the classic Diku spellbook, importable into any merc game.
    pack = await import_pack("merc-classic", server.persistence)

    rooms = sum(1 for o in created if o.has_tag("room"))
    print(f"Imported {len(created)} objects ({rooms} rooms) from Midgaard, "
          f"{len(pack)} spells from merc-classic.")
    start = server.startup_room
    print(f"Starting room: {start.name if start else '(default)'}")
