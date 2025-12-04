"""
Space game world creation.

Creates the initial game world with:
- Space Station Alpha (starting area)
- Several sectors to explore
- NPCs with behaviors
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.persistence.repository import GameObjectRepository


async def create_world(repo: GameObjectRepository) -> dict[str, GameObject]:
    """
    Create the space game world.

    Returns a dict of key objects for reference.
    """
    from realm.core.objects import GameObject

    objects: dict[str, GameObject] = {}

    # === SPACE STATION ALPHA (Starting Area) ===

    # Docking Bay
    docking_bay = GameObject(
        id="room_docking_bay",
        name="Docking Bay Alpha-1",
    )
    docking_bay.add_tag("room")
    docking_bay.add_tag("zone:station_alpha")
    docking_bay.add_tag("indoor")
    docking_bay.db.description = """
You stand in a cavernous docking bay, its metallic walls humming with the
constant thrum of environmental systems. Massive airlocks line the eastern
wall, currently sealed against the vacuum of space. Cargo containers are
stacked neatly in designated zones, and a few small shuttles rest in their
berths.

A corridor leads NORTH to the station's interior. A security checkpoint
guards the way SOUTH to the restricted areas.
""".strip()
    objects["docking_bay"] = docking_bay
    await repo.save(docking_bay)

    # Station Promenade
    promenade = GameObject(
        id="room_promenade",
        name="Station Promenade",
    )
    promenade.add_tag("room")
    promenade.add_tag("zone:station_alpha")
    promenade.add_tag("indoor")
    promenade.db.description = """
The promenade is the social heart of Space Station Alpha. Holographic
advertisements flicker overhead, hawking everything from ship upgrades to
exotic alien cuisine. Vendors have set up kiosks along the curved walkway,
and the distant stars are visible through reinforced viewports.

The docking bay lies to the SOUTH. A cantina beckons to the WEST, while
the medical bay is to the EAST. NORTH leads to the station command center.
""".strip()
    objects["promenade"] = promenade
    await repo.save(promenade)

    # Cantina
    cantina = GameObject(
        id="room_cantina",
        name="The Void's Edge Cantina",
    )
    cantina.add_tag("room")
    cantina.add_tag("zone:station_alpha")
    cantina.add_tag("indoor")
    cantina.db.description = """
Dim lighting and the smell of recycled air mixed with exotic spices greet
you. The cantina is a favorite gathering spot for spacers, traders, and
those who prefer not to answer too many questions. A long bar runs along
one wall, tended by a grizzled human bartender. Booths line the opposite
wall, offering privacy for deals both legal and otherwise.

Music from a dozen worlds plays softly from hidden speakers.
""".strip()
    objects["cantina"] = cantina
    await repo.save(cantina)

    # Medical Bay
    medbay = GameObject(
        id="room_medbay",
        name="Medical Bay",
    )
    medbay.add_tag("room")
    medbay.add_tag("zone:station_alpha")
    medbay.add_tag("indoor")
    medbay.db.description = """
Sterile white walls and the sharp scent of antiseptic define the station's
medical facility. Diagnostic beds with holographic readouts line one wall,
while medical supply cabinets occupy another. An autodoc unit stands ready
in the corner, its robotic arms folded in standby mode.

A sign reads: "Dr. Vex - Chief Medical Officer"
""".strip()
    objects["medbay"] = medbay
    await repo.save(medbay)

    # Command Center
    command = GameObject(
        id="room_command",
        name="Station Command Center",
    )
    command.add_tag("room")
    command.add_tag("zone:station_alpha")
    command.add_tag("indoor")
    command.add_tag("restricted")
    command.db.description = """
The nerve center of Space Station Alpha hums with activity. Banks of
displays show sensor readouts, ship traffic, and system status. Officers
monitor their stations with practiced efficiency, and the station
commander's chair dominates the center of the room.

A tactical holotable displays the local sector in three dimensions.
""".strip()
    # Add a lock - only crew can enter
    command.db.lock_enter = "caller.has_tag('crew') or caller.has_tag('admin')"
    objects["command"] = command
    await repo.save(command)

    # === EXITS ===

    # Docking Bay <-> Promenade
    exit_dock_to_prom = GameObject(id="exit_dock_north", name="north")
    exit_dock_to_prom.add_tag("exit")
    exit_dock_to_prom.db.destination = "room_promenade"
    exit_dock_to_prom.db.aliases = ["n"]
    exit_dock_to_prom.location = docking_bay
    docking_bay.contents.append(exit_dock_to_prom)
    await repo.save(exit_dock_to_prom)

    exit_prom_to_dock = GameObject(id="exit_prom_south", name="south")
    exit_prom_to_dock.add_tag("exit")
    exit_prom_to_dock.db.destination = "room_docking_bay"
    exit_prom_to_dock.db.aliases = ["s"]
    exit_prom_to_dock.location = promenade
    promenade.contents.append(exit_prom_to_dock)
    await repo.save(exit_prom_to_dock)

    # Promenade <-> Cantina
    exit_prom_to_cantina = GameObject(id="exit_prom_west", name="west")
    exit_prom_to_cantina.add_tag("exit")
    exit_prom_to_cantina.db.destination = "room_cantina"
    exit_prom_to_cantina.db.aliases = ["w"]
    exit_prom_to_cantina.location = promenade
    promenade.contents.append(exit_prom_to_cantina)
    await repo.save(exit_prom_to_cantina)

    exit_cantina_to_prom = GameObject(id="exit_cantina_east", name="east")
    exit_cantina_to_prom.add_tag("exit")
    exit_cantina_to_prom.db.destination = "room_promenade"
    exit_cantina_to_prom.db.aliases = ["e", "out"]
    exit_cantina_to_prom.location = cantina
    cantina.contents.append(exit_cantina_to_prom)
    await repo.save(exit_cantina_to_prom)

    # Promenade <-> Medical Bay
    exit_prom_to_med = GameObject(id="exit_prom_east", name="east")
    exit_prom_to_med.add_tag("exit")
    exit_prom_to_med.db.destination = "room_medbay"
    exit_prom_to_med.db.aliases = ["e"]
    exit_prom_to_med.location = promenade
    promenade.contents.append(exit_prom_to_med)
    await repo.save(exit_prom_to_med)

    exit_med_to_prom = GameObject(id="exit_med_west", name="west")
    exit_med_to_prom.add_tag("exit")
    exit_med_to_prom.db.destination = "room_promenade"
    exit_med_to_prom.db.aliases = ["w", "out"]
    exit_med_to_prom.location = medbay
    medbay.contents.append(exit_med_to_prom)
    await repo.save(exit_med_to_prom)

    # Promenade <-> Command Center
    exit_prom_to_cmd = GameObject(id="exit_prom_north", name="north")
    exit_prom_to_cmd.add_tag("exit")
    exit_prom_to_cmd.db.destination = "room_command"
    exit_prom_to_cmd.db.aliases = ["n"]
    exit_prom_to_cmd.location = promenade
    promenade.contents.append(exit_prom_to_cmd)
    await repo.save(exit_prom_to_cmd)

    exit_cmd_to_prom = GameObject(id="exit_cmd_south", name="south")
    exit_cmd_to_prom.add_tag("exit")
    exit_cmd_to_prom.db.destination = "room_promenade"
    exit_cmd_to_prom.db.aliases = ["s", "out"]
    exit_cmd_to_prom.location = command
    command.contents.append(exit_cmd_to_prom)
    await repo.save(exit_cmd_to_prom)

    # === NPCs ===

    # Bartender in Cantina
    bartender = await create_bartender_npc(repo, cantina)
    objects["bartender"] = bartender

    # Doctor in Medical Bay
    doctor = await create_doctor_npc(repo, medbay)
    objects["doctor"] = doctor

    # Guard at Command Center
    guard = await create_guard_npc(repo, command)
    objects["guard"] = guard

    return objects


async def create_bartender_npc(
    repo: GameObjectRepository,
    location: GameObject,
) -> GameObject:
    """Create the cantina bartender NPC."""
    from realm.core.objects import GameObject

    bartender = GameObject(
        id="npc_bartender",
        name="Zeke the Bartender",
    )
    bartender.add_tag("npc")
    bartender.add_tag("shopkeeper")
    bartender.add_tag("zone:station_alpha")
    bartender.location = location
    location.contents.append(bartender)

    bartender.db.description = """
A grizzled human with cybernetic eyes and a mechanical left arm. Zeke has
been tending bar on this station longer than most can remember. His face
is weathered but his eyes are sharp, missing nothing that happens in his
establishment.
""".strip()

    # GURPS stats for bartender
    bartender.db.strength = 11
    bartender.db.dexterity = 12
    bartender.db.intelligence = 13
    bartender.db.health = 11
    bartender.db.skill_melee = 12  # He can handle himself
    bartender.db.hp = 11
    bartender.db.max_hp = 11
    bartender.db.damage_resistance = 0
    bartender.db.dodge = 9

    # Softcode: Respond to greetings
    bartender.db.cmd_greet = "$greet*:say Welcome to The Void's Edge. What'll it be?"
    bartender.db.cmd_buy = "$buy *:say That'll be 5 credits for a %0."
    bartender.db.listen_trouble = "^*trouble*:say We don't want any trouble here, friend."

    await repo.save(bartender)
    return bartender


async def create_doctor_npc(
    repo: GameObjectRepository,
    location: GameObject,
) -> GameObject:
    """Create the medical bay doctor NPC."""
    from realm.core.objects import GameObject

    doctor = GameObject(
        id="npc_doctor",
        name="Dr. Vex",
    )
    doctor.add_tag("npc")
    doctor.add_tag("healer")
    doctor.add_tag("crew")
    doctor.add_tag("zone:station_alpha")
    doctor.location = location
    location.contents.append(doctor)

    doctor.db.description = """
Dr. Vex is a tall, thin Centauran with pale blue skin and four slender
arms. Her multitasking ability makes her an excellent surgeon, and her
calm demeanor puts patients at ease. She wears a pristine white medical
coat with the station's insignia.
""".strip()

    # GURPS stats
    doctor.db.strength = 9
    doctor.db.dexterity = 14
    doctor.db.intelligence = 15
    doctor.db.health = 10
    doctor.db.skill_medicine = 16
    doctor.db.hp = 9
    doctor.db.max_hp = 9

    # Softcode: Healing service
    doctor.db.cmd_heal = "$heal:say Let me take a look at you..."
    doctor.db.cmd_help = "$help:say I can heal your wounds. Just say 'heal' when you're ready."

    await repo.save(doctor)
    return doctor


async def create_guard_npc(
    repo: GameObjectRepository,
    location: GameObject,
) -> GameObject:
    """Create the command center security guard NPC."""
    from realm.core.objects import GameObject
    from realm.core.behaviors import BehaviorRegistry

    guard = GameObject(
        id="npc_guard",
        name="Security Officer Chen",
    )
    guard.add_tag("npc")
    guard.add_tag("guard")
    guard.add_tag("crew")
    guard.add_tag("zone:station_alpha")
    guard.location = location
    location.contents.append(guard)

    guard.db.description = """
A stern-faced human in station security armor. Officer Chen stands at
attention near the command center entrance, her hand never far from the
stunner at her hip. A security badge identifies her as the shift commander.
""".strip()

    # GURPS stats - combat-ready
    guard.db.strength = 12
    guard.db.dexterity = 13
    guard.db.intelligence = 11
    guard.db.health = 12
    guard.db.skill_melee = 14
    guard.db.skill_ranged = 13
    guard.db.hp = 12
    guard.db.max_hp = 12
    guard.db.damage_resistance = 2  # Security armor
    guard.db.dodge = 10
    guard.db.parry = 10

    # Attach guard behavior
    try:
        guard_behavior = BehaviorRegistry.create(
            "guard",
            guard_tags=["player"],
            allow_tags=["crew", "admin", "god"],
            challenge_message="Halt! This area is restricted to authorized personnel only.",
        )
        if guard_behavior:
            guard.add_behavior(guard_behavior)
    except KeyError:
        pass  # Behavior not registered yet

    # Softcode
    guard.db.cmd_id = "$show id:say Let me see your credentials..."
    guard.db.listen_threat = "^*attack*:say I'd advise against that, civilian."

    await repo.save(guard)
    return guard
