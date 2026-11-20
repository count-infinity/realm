"""
Midgaard - a playable Diku/Merc game on REALM.

`realm start` from this directory loads it. Everything ships as content,
imported the way a builder would:

- **World**: ``data/areas/midgaard.json`` - the classic Midgaard, converted
  from its ROM ``.are`` with ``realm import-rom --repop`` so its mobs
  (the beastly fido, beggars, cityguards) respawn on death; and
  ``data/areas/school.json``, ROM's Mud School (``school.are``, converted
  the same way), up from the Temple. Import any other converted ROM area
  alongside them the same way.
- **Rules**: ``rules.py``, a subclass of the ``merc`` game system - THAC0
  combat, percentile skills, XP-and-level advancement. Pick a class at
  character creation; a level-1 barbarian starts kitted with a club in the
  Common Square, ready to thrash fidos and trade at the shops next door.
- **Guilds**: the mage, cleric, thief and warrior guildmasters teach
  ``practice``; each guild's bar lets in only its own class
  (``GUILD_BARS``), as ROM's do.
- **A quest**: ``data/quests.json``, "Fido trouble": the baker in the
  Bakery wants five fidos dead (``quest list`` there, ``quests`` for the
  journal), and makes the killer a Friend of the Baker
  (``data/achievements.json``), on every character of their account.
- **Help**: ``data/help.json``, ``help newbie``: the first steps, as ROM's
  "newbie info" (the banner points to it).
- **A skill to study**: ``data/skills.json``, lore, which ``study lore``
  trains over real time, logged in or not.
- **A horse**: ``data/stable.json``, a brown horse the pet shop sells
  beside its ROM pets; ridden, it pays for the walking.
- **Spells**: the built-in ``merc-classic`` content pack (the mage/cleric
  lines plus the breaths), imported at boot the way ``@pack import`` would.
- **Code**: ``game.py``, the game's own feature (commands, behaviors,
  softcode functions).
"""

GAME_NAME = "Midgaard"
DB_PATH = "midgaard.db"

TELNET_PORT = 4000
TELNET_HOST = "0.0.0.0"
ENABLE_TELNET = True
ENABLE_WEBSOCKET = False

# The rules: GameRules in rules.py, which subclasses the built-in Merc
# system. Its base class is what makes this a Diku; change the hooks there.
GAME_SYSTEM = "rules.GameRules"

# The line after each batch of output: hit points, mana, movement.
PROMPT = "<{hp}hp {mana}m {move}mv> "

# Every narrated line starts with a capital, as ROM's act() writes it
# ("The cityguard arrives.").
CAPITALIZE_LINES = True

# A combat round every 3 seconds, ROM's PULSE_VIOLENCE (players may still
# `pace` slower).
COMBAT_BEAT_DEFAULT = 3.0
COMBAT_BEAT_MIN = 3.0

# Every built-in feature, and this game's own game.py.
from realm import CLASSIC  # noqa: E402

FEATURES = [*CLASSIC, "game"]

# Show the dice: every combat line carries its roll arithmetic
# (players can turn theirs off with `showrolls off`).
SHOW_ROLLS = True

WELCOME_BANNER = """
+==============================================================+
|                        M I D G A A R D                       |
|            The classic Diku town, running on REALM           |
+==============================================================+
|  Choose a class (try 'barbarian') and you will wake in the   |
|  Common Square with a weapon in hand. Kill the fidos, sell   |
|  what drops, and earn your name.                             |
+==============================================================+
|  create <account> <password>    make an account              |
|  connect <account> <password>   log in to yours              |
|  New here? Once you are in, type 'help newbie'.              |
+==============================================================+
"""

# The Common Square (ROM vnum 3025): the town center. Fidos spawn here and
# the General Store / Weapon Shop / Armoury are a step away.
START_ROOM_VNUM = 3025

# Each guild's bar (ROM vnum) and the classes it lets in: the Mage's Bar,
# the Cleric's Bar, the Thieves Bar and the Bar of Swordsmen, with each
# guildmaster beyond.
GUILD_BARS = {3018: ("mage",), 3003: ("cleric",), 3028: ("thief",),
              3022: ("warrior", "barbarian")}


async def init_world(server):
    """First-boot world load (empty database only)."""
    import json
    from pathlib import Path

    from realm import import_objects, import_pack

    area = Path(__file__).parent / "data" / "areas" / "midgaard.json"
    # preserve_ids: the area's exits and resets reference rooms by their
    # rom_<vnum> ids, which a fresh-id clone would break.
    created = await import_objects(json.loads(area.read_text()),
                                   server.persistence, preserve_ids=True)

    # ROM's Mud School (school.are, vnums 3700-3799), up from the Temple of
    # Midgaard: the newbie area, its trainer and the gear ROM's outfit gives.
    school = Path(__file__).parent / "data" / "areas" / "school.json"
    schooled = await import_objects(json.loads(school.read_text()),
                                    server.persistence, preserve_ids=True)

    # Drop new characters into the Common Square.
    for obj in created:
        if obj.has_tag("room") and obj.db.get("rom_vnum") == START_ROOM_VNUM:
            server.startup_room = obj
            break

    # Spells: the classic Diku spellbook, importable into any merc game.
    pack = await import_pack("merc-classic", server.persistence)
    # Talk beyond the room: gossip, newbie, immtalk; and the common socials.
    await import_pack("channels", server.persistence)
    await import_pack("socials-classic", server.persistence)
    await import_pack("clan-governments", server.persistence)

    # The guilds (ROM's class_table): each class's bar, the way in to its
    # guildmaster, turns the other classes away, so each practises at its
    # own guild. Barbarians, a class ROM never had, drink with the swordsmen.
    from realm import ops
    for vnum, classes in GUILD_BARS.items():
        bar = server.persistence.get_cached(f"rom_{vnum}")
        ops.set_lock(None, bar, "enter", "not has_tag(caller, 'player') or "
                     f"get_attr(caller, 'character_class') in {list(classes)!r}")
        bar.db.lock_fail_enter = "You aren't allowed in there."
        await server.persistence.save(bar)

    # The town's first quest: the baker, in the Bakery (vnum 3009), wants
    # five fidos dead (data/quests.json). Its reward, besides experience
    # and a loaf: an achievement every character of the account shares
    # (data/achievements.json). And `help newbie` (data/help.json), the
    # first steps, as ROM's "newbie info".
    for name in ("achievements.json", "quests.json", "help.json"):
        data = Path(__file__).parent / "data" / name
        await import_objects(json.loads(data.read_text()), server.persistence)

    # The pet shop (vnum 3031) sells a brown horse besides ROM's pets
    # (data/stable.json): `buy horse`, lead it outside, `mount horse`.
    stable = Path(__file__).parent / "data" / "stable.json"
    horses = await import_objects(json.loads(stable.read_text()), server.persistence)
    pet_shop = server.persistence.get_cached("rom_3031")
    for keeper in pet_shop.contents if pet_shop is not None else []:
        for behavior in keeper.get_behaviors():
            if behavior.behavior_id == "shopkeeper" and behavior.get_param("sells_pets"):
                behavior.params["pet_stock"] = [*behavior.get_param("pet_stock", []),
                                                *(horse.id for horse in horses)]
                await server.persistence.save(keeper)

    # Lore, a skill studied over real time (`study lore`): it improves while
    # its student is logged out. Merc's other skills improve by use.
    skills = Path(__file__).parent / "data" / "skills.json"
    await import_objects(json.loads(skills.read_text()), server.persistence)

    rooms = sum(1 for o in created if o.has_tag("room"))
    print(f"Imported {len(created)} objects ({rooms} rooms) from Midgaard, "
          f"{len(pack)} spells from merc-classic.")
    rooms = sum(1 for o in schooled if o.has_tag("room"))
    print(f"Imported {len(schooled)} objects ({rooms} rooms) from the Mud School, "
          "up from the Temple.")
    start = server.startup_room
    print(f"Starting room: {start.name if start else '(default)'}")
