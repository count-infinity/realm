"""
Nexagen Tower — the corporate infiltration zone.

Implements the scenario from the infiltration user stories: after-hours
tower, guarded lobby, dark stairwells, badge-locked executive suite, a
wall safe concealed behind a painting on floor 46, and the target
documents inside it.

Everything is lean data on ordinary GameObjects, per REALM's
architecture: `closed`/`locked` state and `key_id`/`lock_difficulty`
attributes for doors and the safe, `dark` rooms with a `light`-tagged
work lamp, `check_skill` on the fire-escape climb, `conceal_difficulty`
on the hidden safe, Watchful/Patrol behaviors on the guards, and a
softcode ON_USE script on the utility panel that blacks out floor 46.

Route in from Space Station Alpha: a tram at the Station Promenade.
"""

from __future__ import annotations

from realm.behaviors import SpawnerBehavior
from realm.core.objects import GameObject


async def _link(repo, name, room_a, room_b, *, back_name=None,
                aliases=None, back_aliases=None, **attrs):
    """Create an exit pair between two rooms; attrs apply to the A→B side."""
    out_exit = GameObject(id=f"exit_{room_a.id}_{name.replace(' ', '_')}", name=name)
    out_exit.add_tag("exit")
    out_exit.db.destination = room_b.id
    if aliases:
        out_exit.db.aliases = aliases
    for key, value in attrs.items():
        out_exit.db.set(key, value)
    out_exit.location = room_a
    await repo.save(out_exit)

    if back_name:
        back = GameObject(id=f"exit_{room_b.id}_{back_name.replace(' ', '_')}", name=back_name)
        back.add_tag("exit")
        back.db.destination = room_a.id
        if back_aliases:
            back.db.aliases = back_aliases
        back.location = room_b
        await repo.save(back)
        return out_exit, back
    return out_exit, None


def _room(room_id, name, desc, *tags):
    room = GameObject(id=room_id, name=name)
    room.add_tag("room")
    room.add_tag("zone:nexagen")
    for tag in tags:
        room.add_tag(tag)
    room.db.description = desc.strip()
    return room


async def create_nexagen(repo, promenade: GameObject) -> dict[str, GameObject]:
    """Build Nexagen Tower and connect it to the Station Promenade."""
    objects: dict[str, GameObject] = {}

    # === Rooms ===

    plaza = _room("nexagen_plaza", "Nexagen Corporate Plaza", """
Nexagen Tower rises fifty stories above the plaza, a monolith of dark
glass and corporate ambition. At this hour the plaza is deserted; light
spills from the lobby to the north. A service alley yawns to the east,
and the tram back to the station hums behind you.
""")

    alley = _room("nexagen_alley", "Service Alley", """
Dumpsters and steam vents crowd this narrow alley along the tower's
east face. A rusted fire escape zigzags up the wall, its lowest ladder
retracted well out of easy reach.
""", "dark")

    lobby = _room("nexagen_lobby", "Nexagen Tower Lobby", """
Polished marble and a five-meter holographic Nexagen logo dominate the
lobby. The reception desk is shuttered for the night. A security
station guards the stairwell entrance to the north.
""")

    stair_low = _room("nexagen_stair_low", "Stairwell: Lower Floors", """
Bare concrete stairs switchback upward into the tower's service core.
Emergency lighting paints everything a dim green. A utility room door
is set into the east wall.
""")

    stair_mid = _room("nexagen_stair_mid", "Stairwell: Floor 23", """
The lights on this landing are dead — someone smashed the fixture, and
maintenance never came. A service door leads west onto the maintenance
landing.
""", "dark")

    maintenance = _room("nexagen_maintenance", "Maintenance Landing", """
A cramped landing littered with cable spools and solvent drums. The
fire-escape door hangs ajar, night air leaking in from the alley far
below. A battered supply locker stands bolted to the wall.
""")

    stair_high = _room("nexagen_stair_high", "Stairwell: Floor 46", """
The stairwell dead-ends at a heavy fire door stenciled 46: EXECUTIVE.
The air conditioning up here whispers money.
""")

    floor46 = _room("nexagen_floor46", "Executive Corridor, Floor 46", """
Deep carpet swallows every footstep. Brushed-steel doors line the
corridor, each bearing a VP's nameplate; the largest, at the north end,
reads R. VOSS — VP, SPECIAL PROJECTS. A reception desk guards the
approach.
""")

    vp_office = _room("nexagen_vp_office", "VP Voss's Office", """
Floor-to-ceiling windows frame the station's glittering sprawl fifty
stories down. A vast desk of real Earth mahogany dominates the room.
On the wall hangs a garish corporate painting: 'SYNERGY', oil on
canvas.
""")

    utility = _room("nexagen_utility", "Utility Room", """
Conduit and breaker boxes cover every wall. A master power panel for
the executive floors blinks amber, its maintenance override helpfully
unlocked.
""")

    rooms = [plaza, alley, lobby, stair_low, stair_mid, maintenance,
             stair_high, floor46, vp_office, utility]
    for room in rooms:
        await repo.save(room)
        objects[room.id] = room

    # === Exits ===

    # Tram: promenade <-> plaza
    await _link(repo, "tram", promenade, plaza, back_name="tram",
                aliases=["nexagen"], back_aliases=["station"])

    # Plaza <-> lobby / alley
    await _link(repo, "north", plaza, lobby, back_name="south",
                aliases=["n"], back_aliases=["s", "out"])
    await _link(repo, "east", plaza, alley, back_name="west",
                aliases=["e"], back_aliases=["w"])

    # The burglar's route: a hard climb up the fire escape to maintenance.
    fire_up, _ = await _link(
        repo, "fire escape", alley, maintenance, back_name="fire escape",
        aliases=["up", "climb"], back_aliases=["down"],
        check_skill="climbing", check_difficulty=2,
        check_fail_msg=("You leap for the retracted ladder, miss, and land "
                        "hard among the dumpsters."),
    )

    # Lobby <-> stairwell (the guarded front route)
    await _link(repo, "north", lobby, stair_low, back_name="south",
                aliases=["n"], back_aliases=["s"])

    # Stairwell spine
    await _link(repo, "up", stair_low, stair_mid, back_name="down",
                aliases=["u"], back_aliases=["d"])
    await _link(repo, "up", stair_mid, stair_high, back_name="down",
                aliases=["u"], back_aliases=["d"])
    await _link(repo, "west", stair_mid, maintenance, back_name="east",
                aliases=["w"], back_aliases=["e"])

    # Utility room off the lower stairwell, behind a closed door.
    util_door, _ = await _link(repo, "east", stair_low, utility,
                               back_name="west",
                               aliases=["e"], back_aliases=["w"])
    util_door.add_tag("closed")
    await repo.save(util_door)

    # Floor 46: fire door, then the locked executive suite.
    await _link(repo, "east", stair_high, floor46, back_name="west",
                aliases=["e"], back_aliases=["w"])

    suite_door, suite_back = await _link(
        repo, "suite door", floor46, vp_office, back_name="suite door",
        aliases=["north", "n", "door"], back_aliases=["south", "s", "out"],
    )
    suite_door.add_tag("closed")
    suite_door.add_tag('locked')
    suite_door.db.key_id = "nexagen_vp_suite"
    suite_door.db.lock_skill = "electronics"
    suite_door.db.lock_difficulty = 3
    suite_door.db.locked_msg = ("The suite door's badge reader blinks red: "
                                "ACCESS DENIED.")
    await repo.save(suite_door)

    # === Furnishings & loot ===

    # Supply locker on the maintenance landing: the burglar's toolkit.
    locker = GameObject(id="nexagen_locker", name="supply locker")
    locker.add_tag("thing")
    locker.add_tag("no_group")
    locker.add_tag('container')
    locker.add_tag("closed")
    locker.db.description = "A dented steel locker stenciled NEXAGEN FACILITIES."
    locker.location = maintenance
    await repo.save(locker)

    goggles = GameObject(id="nexagen_goggles", name="nightvision goggles")
    goggles.add_tag("thing")
    goggles.add_tag("wearable")
    goggles.db.slot = "eyes"
    goggles.db.grants_tags = ["nightvision"]
    goggles.db.description = "Surplus military optics. The dark holds no secrets."
    goggles.location = locker
    await repo.save(goggles)

    picks = GameObject(id="nexagen_lockpicks", name="lockpick set")
    picks.add_tag("thing")
    picks.add_tag("lockpicks")
    picks.db.description = "Tension wrenches and rakes in a leather roll."
    picks.location = locker
    await repo.save(picks)

    lamp = GameObject(id="nexagen_lamp", name="work lamp")
    lamp.add_tag("thing")
    lamp.add_tag("light")
    lamp.db.description = "A battery work lamp, still serviceable."
    lamp.location = maintenance
    await repo.save(lamp)

    # Reception desk on 46 holds the executive keycard — the social/tech
    # alternative to picking the suite's electronic lock.
    desk = GameObject(id="nexagen_desk", name="reception desk")
    desk.add_tag("thing")
    desk.add_tag("no_group")
    desk.add_tag('container')
    desk.add_tag("closed")
    desk.db.description = "A curved slab of pale composite. A drawer sits beneath the top."
    desk.location = floor46
    await repo.save(desk)

    keycard = GameObject(id="nexagen_keycard", name="executive keycard")
    keycard.add_tag("thing")
    keycard.db.unlocks = "nexagen_vp_suite"
    keycard.db.description = "R. VOSS, VP embossed over the Nexagen logo."
    keycard.location = desk
    await repo.save(keycard)

    # The painting, and the safe it conceals.
    painting = GameObject(id="nexagen_painting", name="corporate painting")
    painting.add_tag("thing")
    painting.add_tag("no_group")
    painting.db.description = (
        "'SYNERGY': a gold spiral devouring a smaller silver spiral. "
        "It hangs a little proud of the wall, as if mounted on hinges."
    )
    painting.location = vp_office
    await repo.save(painting)

    safe = GameObject(id="nexagen_safe", name="wall safe")
    safe.add_tag("thing")
    safe.add_tag("no_group")
    safe.add_tag("invisible")
    safe.db.conceal_difficulty = 2
    safe.db.reveal_msg = ("The painting swings aside on hidden hinges, "
                          "revealing a wall safe!")
    safe.add_tag('container')
    safe.add_tag("closed")
    safe.add_tag('locked')
    safe.db.key_id = "nexagen_safe"
    safe.db.lock_difficulty = 5
    safe.db.locked_msg = "The safe's combination dial doesn't budge."
    safe.db.description = "A Krupp-Yamada wall safe, combination model."
    safe.location = vp_office
    await repo.save(safe)

    documents = GameObject(id="nexagen_documents", name="Nexagen documents")
    documents.add_tag("thing")
    documents.db.article = "the"
    documents.db.description = (
        "A sealed folio stamped PROJECT LONGSHADOW — BOARD EYES ONLY. "
        "This is what you came for."
    )
    documents.location = safe
    await repo.save(documents)

    # Utility panel: softcode blackout. Using it darkens the executive
    # floor — the Story 6 opener, authored as pure softcode.
    panel = GameObject(id="nexagen_panel", name="power panel")
    panel.add_tag("thing")
    panel.add_tag("no_group")
    panel.db.description = (
        "Breakers for floors 40-50. The EXECUTIVE LIGHTING master is not "
        "even locked out."
    )
    panel.db.on_use = (
        "if has_tag(get('#nexagen_floor46'), 'dark'):\n"
        "    remove_tag(get('#nexagen_floor46'), 'dark')\n"
        "    remove_tag(get('#nexagen_stair_high'), 'dark')\n"
        "    say('The executive floor lighting hums back to life.')\n"
        "else:\n"
        "    add_tag(get('#nexagen_floor46'), 'dark')\n"
        "    add_tag(get('#nexagen_stair_high'), 'dark')\n"
        "    say('Breakers slam open. Floor 46 goes black.')"
    )
    panel.location = utility
    await repo.save(panel)

    # === Guards (spawner-backed: the tower re-staffs itself) ===

    lobby.add_behavior(SpawnerBehavior(
        key="door_guard",
        respawn_ticks=150,
        announce="A relief guard steps out of the security office.",
        prototype={
            "name": "Nexagen door guard",
            "description": (
                "Broad, bored, and armored in corporate polyweave. Her eyes "
                "sweep the lobby in a practiced rhythm."
            ),
            "tags": ["npc", "zone:nexagen"],
            "attrs": {
                "strength": 12, "dexterity": 11, "intelligence": 10,
                "health": 12, "hp": 12, "max_hp": 12,
                "skill_observation": 12, "skill_melee": 12, "dodge": 8,
                "points": 60,
                "listen_help": "^*help*:say Move along. Tower's closed.",
            },
            "behaviors": [
                {"behavior_id": "watchful", "params": {
                    "challenge": "Building's closed. Authorized personnel only.",
                    "spot_msg": "Hey! You there — step out where I can see you!",
                }},
            ],
        },
    ))
    await repo.save(lobby)

    floor46.add_behavior(SpawnerBehavior(
        key="exec_guard",
        respawn_ticks=150,
        announce="The service lift chimes: a fresh guard steps out.",
        prototype={
            "name": "executive floor guard",
            "description": (
                "Lean and unsmiling, with a patrol route worn into the "
                "carpet and a stunner on his hip."
            ),
            "tags": ["npc", "zone:nexagen"],
            "attrs": {
                "strength": 11, "dexterity": 12, "intelligence": 11,
                "health": 11, "hp": 11, "max_hp": 11,
                "skill_observation": 13, "skill_melee": 13, "dodge": 9,
                "points": 80,
                "combat_strategy": [["!me.hp_percent < 25", "flee"],
                                     ["", "attack"]],
            },
            "behaviors": [
                {"behavior_id": "watchful", "params": {
                    "spot_msg": "Contact! Intruder on forty-six!",
                    "hostile": True,
                }},
                {"behavior_id": "patrol", "params": {
                    "route": ["west", "east"], "pause": 4,
                }},
            ],
        },
    ))
    await repo.save(floor46)

    objects.update({
        "locker": locker, "goggles": goggles, "picks": picks, "lamp": lamp,
        "desk": desk, "keycard": keycard, "painting": painting, "safe": safe,
        "documents": documents, "panel": panel,
        "suite_door": suite_door, "fire_escape": fire_up,
    })
    return objects
