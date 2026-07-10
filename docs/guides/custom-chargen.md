# How-To: Customize or Skip Character Creation

**Goal:** change *how* creation works — add or reorder questions, or
remove the creation menu entirely and let players build themselves in
the world.

Background: [How a Character Is Born](../concepts/character-creation.md).
To just add a class to the existing menu, see
[Add a Character Class](add-a-class.md) — that's the smaller change.

The whole flow comes from one method, `chargen_steps()`, on your
[GameSystem](game-systems.md). Override it and you own creation.

## Reshape the flow: add or reorder questions

A step is a `ChargenStep`. The built-in `ChoiceStep` handles any
"pick one of these" question; you can add your own subclass for anything
else (a name prompt, point-buy, a dice roll). Override `chargen_steps()`
to return the sequence you want:

```python
# mygame/mysystem.py
from realm.systems.gurps import GurpsSystem
from realm.systems.base import GameSystemRegistry, ChoiceStep

@GameSystemRegistry.register
class MyGurps(GurpsSystem):
    system_id = "mygurps"

    def chargen_steps(self):
        steps = super().chargen_steps()          # template + bonus skill
        steps.append(ChoiceStep(
            "homeworld", "Where are you from?",
            {"terra": "born on Earth (+1 will)",
             "belt":  "raised in the Belt (+1 dx)"},
            self._apply_homeworld,
        ))
        return steps

    @staticmethod
    def _apply_homeworld(player, choice):
        if choice == "terra":
            player.db.set("skill_will", int(player.db.get("skill_will") or 10) + 1)
        else:
            player.db.dexterity = int(player.db.get("dexterity") or 10) + 1
        player.db.homeworld = choice
```

The Template-Method flow (prompt → answer → advance → finish) is fixed
and reboot-safe; you only supply the steps. A custom step needs just two
methods:

```python
from realm.systems.base import ChargenStep

class NameStep(ChargenStep):
    key = "callsign"

    def prompt(self, player):
        return "Choose a callsign:"

    def handle(self, player, response):
        response = response.strip()
        if len(response) < 2:
            return False, "Too short — try again."   # (advance?, feedback)
        player.db.callsign = response
        return True, f"Callsign set: {response}."      # True = move on
```

## Skip it entirely: instant characters

Return an empty list and creation is a single step — `create` drops the
player straight into the world with just their baseline stats:

```python
@GameSystemRegistry.register
class SandboxSystem(GurpsSystem):
    system_id = "sandbox"

    def chargen_steps(self):
        return []          # no menu; everyone starts identical
```

```python
# config.py
GAME_SYSTEM = "sandbox"
```

## The "drop into a training school" start

A nice middle ground: no creation menu, but characters arrive in an
in-world academy with a pool of points to spend using the ordinary
`points` / `improve` commands. Nothing new to build — three pieces you
already have:

**1. No menu, and grant starting points.** Override `apply_baseline` to
seed a character-point pool on every fresh sheet:

```python
@GameSystemRegistry.register
class AcademySystem(GurpsSystem):
    system_id = "academy"

    def chargen_steps(self):
        return []

    def apply_baseline(self, player):
        super().apply_baseline(player)             # standard stats
        player.db.character_points = 25            # points to spend in-world
```

**2. Make the start room the academy.** The engine drops new characters
into whatever room is tagged `start_room`. Build one in your
`init_world` callback and tag it:

```python
# config.py
async def init_world(server):
    from realm.core.objects import GameObject
    academy = GameObject(
        name="The Academy Drill Hall",
        description=("Training dummies line the walls. A sign reads: spend "
                     "your points here.\nTry:  points   then   improve <skill>"),
        tags=["room", "start_room"],
    )
    await server.persistence.save(academy)
```

**3. Players build themselves.** The existing commands do the rest:

```text
points                 # Character points: 25   (with a skill list)
improve stealth        # 4 CP per level under GURPS
improve stealth
points                 # Character points: 17
```

You can gate the exit out of the academy behind a lock so players finish
allocating before they leave, or make it a soft one-way door — your
call. This is exactly the flow you'd reach for instead of a menu when you
want players to *feel* the choices rather than click through them.

## Verifying any of these

```bash
realm start
# telnet in and create a character; confirm the flow matches your steps
# (or that you land straight in the world), then:
points        # confirm starting points / applied skills
```

Remember creation is a **boot-time** decision — set `GAME_SYSTEM` before
opening to players. See
[Game Systems → changing systems after launch](game-systems.md#changing-systems-after-launch-dont).
