"""
REALM Midgaard - a playable Diku/Merc reference game.

The classic Midgaard, running on REALM's ``merc`` game system, built the way
REALM wants games built:

- **World** - ``data/areas/midgaard.json``, the ROM Midgaard converted with
  ``scripts/rom_import.py --repop`` so mobs respawn (imported at first boot).
- **Rules** - the built-in ``merc`` game system (``GAME_SYSTEM`` in
  config.py): THAC0 combat, percentile skills, XP-and-level advancement,
  and a ``barbarian`` class kitted with a club.
- **Spells** - the built-in ``merc-classic`` content pack, imported like any
  ``@pack``.

``realm init --template midgaard`` scaffolds a game from this directory.
Nothing here is Python game logic: it is all data + config over the engine.
"""
