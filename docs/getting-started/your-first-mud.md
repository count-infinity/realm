# Your First MUD

## Play Midgaard

Four commands make a running Diku game and connect to it:

```bash
realm init midgaard --system merc --template midgaard
cd midgaard
realm start
telnet localhost 4000          # from another terminal; or Mudlet, TinTin++
```

(`TELNET_PORT` in `config.py` is the port; REALM is installed as in
[Installation](installation.md).) At the welcome screen, `create <account>
<password>`, name a character and pick a class. You wake in the Common
Square with 20 hit points, a weapon and the Mud School's banner, vest and
shield. The beastly fidos, level 0 dogs, roam the town; six of them make
level 2. A real first fight, as a mage on a server someone else started
(the dice will roll differently for you):

```text
> create Kit correcthorse
Account 'Kit' created. Name your first character:
> Kit
> mage
You grip a gnarled dagger, ready for trouble.
You have been equipped by the Mud School: a war banner, a sub issue vest, a sub issue shield.
Welcome to the world, Kit!
> where fido
the beastly fido  Grubby Inn
the beastly fido  The Main Street
> north
> east
> east
The Main Street
...
You see:
  the beastly fido
> consider fido
The perfect match!
> kill fido
You square off against the beastly fido!
*** Combat begins! Next beat in 3s — queue your action. ***
You hit the beastly fido for 1 damage!
The beastly fido hits you for 2 damage!
...
CRITICAL! You hit the beastly fido for 4 damage! The beastly fido is defeated!
The beastly fido falls dead!
You gain 170 experience.
*** The fight is over. ***
```

Five fidos later (resting in between: `rest`, then `stand` when full):

```text
You hit the beastly fido for 2 damage! The beastly fido is defeated!
The beastly fido falls dead!
You gain 170 experience.
You raise a level!!  You are now level 2.
You gain 2 hit points, 10 mana, 2 practices and 1 training session.
> score
You are Kit, a level 2 mage.
Experience: 20 / 2000 to level 3
HP: 22/22   Mana: 120/120   Move: 100/100
Practices: 7   Training sessions: 4
```

(Roll lines and prompts are left out; "The Main Street" names two rooms,
so the first one tried was empty.)

`help newbie` has the rest: `rest` then `stand` to heal, the corpse to
loot, your guild to `practice` at, the Mud School up from the Temple.

**The first character on a new server is its superuser.** It plays as
everyone does (a fido fight, experience and levels are the same), but
aggressive monsters leave it alone, every lock opens for it (any class
walks into any guild) and it never goes hungry. Type `quell` to play as a
mortal, and `unquell` to have your powers back; or make your own account
first and a second one to play.

## From an empty directory

This page is for a developer who wants a Diku-style game and wants to
build it. In about an hour it takes you from an empty directory to a
running game you have played, opened to builders and added to: a room, a
trainer, a channel, a quest and a clan. Every command and every line of
game output below was run and copied from a real session (the dice in a
fight will roll differently for you).

You need REALM installed ([Installation](installation.md)), a terminal,
and a MUD client or plain `telnet`.

## 1. Make the game

```bash
realm init demo --system merc --template midgaard
cd demo
realm start
```

`realm init` copies the Midgaard example into `demo/`; `--system merc`
says which rules it is built on (the Midgaard template is a Merc game, so
`--system` may be left out):

```text
Creating REALM project: demo (from template: midgaard)
  Created README.md
  Created config.py
  Created data/achievements.json
  Created data/areas/midgaard.json
  Created data/areas/school.json
  Created data/help.json
  Created data/quests.json
  Created data/skills.json
  Created data/stable.json
  Created game.py
  Created rules.py
  Created tests/test_game.py
```

| File | What it is |
|---|---|
| `config.py` | the settings, `FEATURES`, and `init_world`, which loads the world on the first start |
| `rules.py` | `GameRules`, your own copy of the Merc rules (classes, skills, advancement) |
| `game.py` | your game's own commands, behaviors and softcode functions |
| `data/areas/midgaard.json` | the town: 143 rooms, converted from ROM 2.4's `midgaard.are` |
| `data/areas/school.json` | ROM's Mud School, the newbie area up from the Temple (`school.are`) |
| `data/help.json` | `help newbie`, the first steps |
| `data/quests.json`, `achievements.json` | the baker's quest, and the achievement it pays |
| `data/stable.json`, `skills.json` | a horse for the pet shop, and lore, a skill you study |
| `tests/test_game.py` | a smoke test: `pytest` boots the game in memory |

`realm start` loads the world on its first run and listens for telnet on
port 4000:

```text
[INFO] realm.gateway.telnet: Telnet server listening on 0.0.0.0:4000
[INFO] realm.server.game: Midgaard game server started
...
Imported 1048 objects (143 rooms) from Midgaard, 30 spells from merc-classic.
Imported 315 objects (59 rooms) from the Mud School, up from the Temple.
Starting room: The Common Square
```

Everything is kept in `midgaard.db`. Stop the server with `Ctrl+C`;
`realm start` again carries on where it stopped.

## 2. Make an account

Connect from another terminal (`telnet localhost 4000`, or Mudlet,
TinTin++ or any MUD client):

```text
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
```

A person logs in to an **account**, and an account holds up to five
characters (`MAX_CHARACTERS`, which an administrator or an achievement can
raise for one account):

```text
> create Ann correcthorse
Account 'Ann' created. Name your first character:
> Bree
Character 'Bree' created.
As the first character on this server you have SUPERUSER powers (builder and admin commands — see 'help').

Choose your class:
  1. warrior — a front-line fighter: best hit die and THAC0, no spells
  2. barbarian — a savage warrior: the biggest hit die, a brutal club, no spells
  3. thief — a skirmisher: stealth, locks, and a wicked backstab
  4. cleric — a divine caster: healing and protective prayers
  5. mage — an arcane caster: fragile, but the deadliest spells
Choose by number or name.
> warrior
Class: warrior.
You grip a short sword, ready for trouble.
You have been equipped by the Mud School: a war banner, a sub issue vest, a sub issue shield.
Your warrior steps into the world, ready to earn their name.

Welcome to the world, Bree!

The Common Square
-----------------
The common square, people pass you, talking to each other.  To the west is
the poor alley and to the east is the dark alley.  To the north, this square
is connected to the market square.  From the south you notice a nasty smell.

You see:
  the beastly fido

Exits: north, east, south, west
<20hp 100m 100mv>
```

The first character made on a server is the superuser. The last line is
the prompt: hit points, mana and movement (`PROMPT` in `config.py`; each
player can change their own with `prompt`). Every new character has 20
hit points, its class weapon, and what ROM's `do_outfit` hands out: the
Mud School's war banner, vest and shield.

A second character on the same account:

```text
> characters
Account: Ann
Your characters (1 of 5):
  Bree             level 1 warrior
Commands: play <name>, new <name>, delete <name>, password <old> <new>, quit
> new Cole
Character 'Cole' created.
...
> cleric
...
Welcome to the world, Cole!
> characters
Account: Ann
Your characters (2 of 5):
  Bree             level 1 warrior
  Cole             level 1 cleric
Commands: play <name>, new <name>, delete <name>, password <old> <new>, quit
> play Bree
Welcome back, Bree!
```

From now on `connect Ann correcthorse` shows that menu. One character at a
time is in play; the other is out of the world until it is played.

## 3. The first hour

This is what a player does in Midgaard; try it before you change anything.
`help` lists every command, and `help <command>` explains one.

**Look at yourself.** `score` is the character sheet, `equipment` the wear
slots, `skills` what you know:

```text
> score
You are Bree, a level 1 warrior.
Experience: 0 / 1000 to level 2
HP: 20/20   Mana: 100/100   Move: 100/100
THAC0: 20   AC: 8
Alignment: 0 (neutral)
Wielding: a short sword
Wearing:  a war banner, a sub issue vest, a sub issue shield
```

**Fight.** Fidos roam the town (`where fido` says where); ROM's fido
bites only someone asleep, so you pick the fight. Things are called as
ROM calls them ("the beastly fido", "a long sword") and answer to their
ROM keywords (`fido`, `dog`). `consider` sizes one up; `kill` starts a
fight, which goes in rounds every 3 seconds (ROM's; `COMBAT_BEAT_DEFAULT`
in `config.py`), with the dice shown (`SHOW_ROLLS`; `showrolls off` hides
them):

```text
> consider fido
The perfect match!
The beastly fido seems well-disposed toward you.
> kill fido
You square off against the beastly fido!
*** Combat begins! Next beat in 3s — queue your action. ***
CRITICAL! You hit the beastly fido for 6 damage!
  [d20(20) vs need 10 (THAC0 20 - AC 10)]  [2d6(5)+1 = 6]
CRITICAL! The beastly fido hits you for 3 damage!
  [d20(20) vs need 12 (THAC0 20 - AC 8)]  [2d4(3)+0 = 3]
-- Round 1 done. Next beat in 3s; you will: Attack the beastly fido. (queue <maneuver> to change)
<17hp 100m 100mv>
You miss the beastly fido.
  [d20(9) vs need 10 (THAC0 20 - AC 10)]
You block the beastly fido's attack with your shield.
  [d20(12) vs need 12 (THAC0 20 - AC 8)]
...
You hit the beastly fido for 4 damage! The beastly fido is defeated!
  [d20(12) vs need 10 (THAC0 20 - AC 10)]  [1d6(3)+1 = 4]
The beastly fido falls dead!
You gain 170 experience.
*** The fight is over. ***
```

A fido is worth 85 experience to a level-1 character and ROM doubles what
a new character earns (the bonus fades by level 6), so six fidos make
level 2. A cityguard passing by joins a fight against anything evil
("PROTECT THE INNOCENT!!  BANZAI!!"), and when his blow kills the fido the
experience is his: fight where no guard stands.

Hurt, you recover on your own; `rest` or `sleep` is faster, and `stand`
gets up. A warrior's class skills are commands: `kick fido` in a fight
(`abilities` lists yours and their cooldowns). Every skill you use gets
better by use ("You have become better at melee!"), and `skills` shows how
close the next point is.

**Die.** Lose a fight and you wake in the Common Square with 1 hit point,
up to a quarter of a level's experience poorer; what you carried waits in
your corpse where you fell:

```text
CRITICAL! The vagabond hits you for 10 damage! You have been defeated!
You have been KILLED!!
You lose 170 experience.
...
> get all from corpse
You pick up a short sword, a war banner, a sub issue vest, and a sub issue shield.
> wield sword
You ready a short sword.
> wear all
You put on the war banner.
You put on the sub issue vest.
You put on the sub issue shield.
```

**Level.** Experience past the level's mark raises you a level, and the
game says what came with it:

```text
The vagabond falls dead!
You gain 1600 experience.
You raise a level!!  You are now level 2.
You gain 6 hit points, 1 practice and 1 training session. Your THAC0 is now 19.
```

`score` shows the practices and training sessions waiting to be spent
(below).

**Work.** The baker, north, west and north of the square, sells bread and
pies, and has a quest:

```text
> list
The baker's wares:
  a big pot pie — 24 gold
  a bread — 10 gold
  a cinnamon roll — 18 gold
  a batch of Sara's cookies — 12 gold
  a blueberry danish — 6 gold
> buy potpie
You buy a big pot pie for 24 gold.
> quest list
The baker offers:
  Fido trouble - The baker says the beastly fidos have been at the flour sacks again. Kill five of them and there is experience and a loaf in it for you.
(quest accept <name> to take one)
> quest accept fido trouble
Quest accepted: Fido trouble.
The baker says the beastly fidos have been at the flour sacks again. Kill five of them and there is experience and a loaf in it for you.
[Fido trouble] Stage 1: Kill five of the beastly fidos that roam the streets.
> quests
Your quests:
  Fido trouble (stage 1 of 1)
    Kill five of the beastly fidos that roam the streets.
      fidos killed: 0/5
```

Each fido you kill counts (`[Fido trouble] fidos killed: 1/5`). Back at the
baker, `quest complete` pays 250 experience and a loaf, and makes you a
Friend of the Baker, an achievement every character of your account
shares (`achievements`).

**Spend.** `get all from corpse` loots (the vagabond, beaten, gives up his
small sword and his jerkin); shopkeepers buy and sell (`list`, `buy`,
`sell`, `value`). When two things answer to a word the game asks which:

```text
> sell small
You sell a small sword for 100 gold.
> list
The leather worker's wares:
  a leather jerkin — 297 gold
  a leather cap — 150 gold
...
> buy cap
Which 'cap' do you mean?
  a leather cap-1 (in the leather worker)
  a hard leather cap-2 (in the leather worker)
(Use e.g. 'cap-1' to pick one.)
> buy cap-1
You buy a leather cap for 150 gold.
> wear cap
You put on the leather cap.
```

`equipment` now shows `<head>    a leather cap`, and `score` a better armor
class.

**Learn.** A new character has five practice sessions and three training
sessions, and each level brings more; practices are spent at your own guild:
each class's bar lets in only that class ("You aren't allowed in there."),
and the guildmaster is beyond it. The warriors' Guild of Swordsmen is
east, east and south of Market Square, then east through the bar and
south to the Tournament and Practice Yard; the thieves' is south of the
Dark Alley, the clerics' west of the Temple Square, the mages' south of
the west end of Main Street:

```text
> practice
The guildmaster teaches:
  melee               40  (learned; use it to improve)
  kick                40  (learned; use it to improve)
  bash                30
...
> practice bash
You practice bash (31).
```

Lore is a skill you study instead, and it keeps improving while you are
logged out:

```text
> study lore
You begin studying lore.
```

and the next time you log in, "You have finished training lore to level
9."

A training session raises a characteristic by one: `train strength` at the
adept of Furey, in ROM's Mud School (up from the Temple of Mota: north,
north, north and up from the Common Square), the newbie area, with weak
monsters to practise on and no cityguards.

**Talk.** Another player, anywhere in the game:

```text
> tell Eve Welcome to Midgaard!
You tell Eve, 'Welcome to Midgaard!'
> gossip The baker in the Bakery has work for fido hunters.
[gossip] Bree: The baker in the Bakery has work for fido hunters.
> tell Eve Are you there?
Eve is not online. Leave them a message with mail.
> mail Eve = Fido hunting/Meet me in the Common Square at dawn.
Mail sent to Eve.
```

`reply` answers the last tell; `channels` lists gossip and newbie (and
immtalk, for builders and staff). Eve finds the letter at her next login ("You have 1
unread message.").

**Eat.** Merc characters grow hungry and thirsty. `score` says "You are
hungry."; `eat bread`, `drink` at the Temple Square's fountain.

**Company.** The pet shop is east, east and north of the square:

```text
> list
Pets for sale:
  the kitten — 1 gold
  the puppy — 1 gold
  the beagle — 2 gold
  the rottweiler — 4 gold
  the wolf — 8 gold
  a brown horse (mount) — 10 gold
> buy rottweiler
You buy the rottweiler for 4 gold. Enjoy your pet.
```

A pet follows you and leaps into your fights ("The rottweiler leaps to
Bree's side!"). A Merc character keeps one companion until level
10, so `dismiss` the dog before you buy the horse, lead the horse out of
the shop and ride it; it pays for the walking:

```text
> mount horse
You can't ride in here.
> south
...
> mount horse
You mount the brown horse.
> west
You ride west on a brown horse.
```

**Clans.** `clan governments` lists the eight kinds; `clan found <name> =
<government>` founds one for 10000 gold (`CLAN_COST`). Section 9 does it
as the superuser.

## 4. Grant a builder

Everyone else starts as a player. Have a friend make an account (here
`create Dan opensesame`, character Eve, a thief), and from Bree:

```text
> @tag Eve = builder
Added tag 'builder' to Eve.
```

Eve can now use the building commands (`help` lists them under
Building). Builders work live: nothing below needs a restart.

## 5. Add a room

Eve walks south twice from the Common Square, to the South Bridge, and
digs a room below it, with an exit each way:

```text
> @dig The Training Yard = down, up
Room created: The Training Yard (#b787eb85)
  Exit 'down' created -> The Training Yard
  Exit 'up' created -> The South Bridge (paired with 'down')
> down
You leave down.
> @desc here = Straw dummies stand in a row on the packed earth.
Description set for The Training Yard.
```

## 6. A trainer

A character made with `@create` becomes an NPC with the `npc` tag; the
`trainer` behavior makes it a guildmaster for whoever stands before it
(`teaches:class` teaches each character their own class's skills):

```text
> @create Garrick
Created: Garrick (#26fc4ca8)
> @tag Garrick = npc
Added tag 'npc' to Garrick.
> drop Garrick
You drop Garrick.
> @behavior Garrick = trainer, teaches:class
Attached 'trainer' to Garrick with {"teaches": "class"}.
> practice
Garrick teaches:
  stealth             45  (learned; use it to improve)
  lockpicking         40  (learned; use it to improve)
  backstab            30
  trip                30
  disarm              20
  dodge               30
  melee               20
You have 0 practice sessions.
```

`@behavior Garrick = trainer, teaches:["melee", "parry"], max_level:30`
teaches named skills instead ([Progression](../guides/progression.md)).

## 7. A channel

A channel is a `channel_def` object; its name and alias become commands:

```text
> @create trade
Created: trade (#422027bd)
> @tag trade = channel_def
Added tag 'channel_def' to trade.
> @set trade/alias = trd
Set trade/alias = 'trd'
> @set trade/description = buying and selling
Set trade/description = 'buying and selling'
> trade Straw dummies, cheap!
[trade] Eve: Straw dummies, cheap!
```

Everyone online with it on hears it. Locks decide who may speak and listen
(`@lock/speak trade = has_tag(caller, 'merchant')`;
[Communication](../guides/communication.md)).

## 8. A quest

A quest is a `quest_def` object with a giver, stages of objectives and
rewards:

```text
> @create Straw and Sawdust
Created: Straw and Sawdust (#3a53b140)
> @tag Straw and Sawdust = quest_def
Added tag 'quest_def' to Straw and Sawdust.
> @set Straw and Sawdust/giver = Garrick
Set Straw and Sawdust/giver = 'Garrick'
> @set Straw and Sawdust/description = Garrick wants a fido for the dummies' stuffing.
Set Straw and Sawdust/description = "Garrick wants a fido for the dummies' stuffing."
> @set Straw and Sawdust/stages = [{"text": "Kill a fido.", "objectives": [{"kind": "kill", "name": "fido", "count": 1}]}]
Set Straw and Sawdust/stages = [{'text': 'Kill a fido.', 'objectives': [{'kind': 'kill', 'name': 'fido', 'count': 1}]}]
> @set Straw and Sawdust/rewards = {"award": 100, "credits": 20}
Set Straw and Sawdust/rewards = {'award': 100, 'credits': 20}
> quest list
Garrick offers:
  Straw and Sawdust - Garrick wants a fido for the dummies' stuffing.
(quest accept <name> to take one)
```

Objectives can also be to collect, deliver, visit, talk or use, and a
quest can run softcode when it starts, advances or ends
([Quests](../guides/quests.md)). `data/quests.json` is the same thing as a
file, which `init_world` imports.

## 9. A clan

```text
> clan governments
Clan governments (clan found <name> = <government>):
  anarchy      anyone may join, and every member may do almost anything
  co-op        a house mother and father run it; no tax, no relations
  fellowship   everything, from membership to the leader, is put to the vote
  gang         ruled by one boss, who assigns the underlings
  guild        ruled by up to five guildmasters, who vote on positions and policy
  meritocracy  ruled by whoever has given the clan the most experience
  plutocracy   ruled by whoever has given the clan the most money
  union        every member votes for senators and on membership, relations and the tax
> clan found Midgaard Watch = guild
Founding a clan costs 10000 gold.
> @set me/credits = 10000
Set Bree/credits = 10000
> clan found Midgaard Watch = guild
You found Midgaard Watch, a guild, and are its Guildmaster.
> clan info Midgaard Watch
Midgaard Watch: a guild (ruled by up to five guildmasters, who vote on positions and policy)
  Level 1, 1 member(s).
  Guildmaster: Bree
```

Others `clan apply Midgaard Watch`, and a guildmaster `clan accept`s them;
`ct` is clan talk:

```text
> clan accept Eve
[Midgaard Watch] Eve is accepted into Midgaard Watch as Member.
Eve is accepted.
```

and Eve, anywhere, types `ct Reporting for duty.` for every member online
to read `[Midgaard Watch] Eve: Reporting for duty.` A door can be locked to
the clan; here, the Temple Square's way up:

```text
> @lock up = clan(caller) == 'Midgaard Watch'
Lock/basic set on up.
```

([Clans](../guides/clans.md): positions, votes, the treasury, relations.)

## 10. Where to go next

**Change the rules.** `rules.py` is a subclass of the Merc rules, with
commented examples: a new class, a new skill, characters with no creation
menu. Uncomment one and restart the server (`Ctrl+C` and `realm start`;
under a supervisor, `@reboot` from inside the game): Python changes need a
restart, softcode does not. [Game Systems](../guides/game-systems.md) explains each
hook (how a check rolls, what a kill is worth, how a level is gained), and
[Add a Class](../guides/add-a-class.md) adds one.

**Add code.** `game.py` is your game's feature: commands, NPC behaviors,
softcode functions, reactions to events. [Where things
go](../guides/features.md#where-things-go) has a table, with an example of
each.

**Build more.** [The tutorial](../tutorial/index.md) builds a whole
adventure in softcode; [the showcase](../showcase/index.md) is a worked
example for most things a builder wants. `realm import-rom` converts other
ROM areas ([Importing ROM areas](../development/rom-import.md)).

**Run it.** Before you open the doors: `pytest` in `demo/` runs your
game's own test (add yours beside it), `realm features --check` checks
`FEATURES`, and `realm backup` copies the database while the game runs:

```text
$ pytest -q
1 passed
$ realm features --check
OK: 35 features (accounts, basics, talk, channels, movement, look, sight, items, building, rules, stealth, combat, effects, vitals, needs, abilities, economy, social, companions, crime, npc, spawning, instances, wilderness, tasks, achievements, mail, clock, clans, quests, operations, gurps, d20, merc, midgaard)
$ realm backup
Backed up .../demo/midgaard.db to .../demo/backups/midgaard-20261116-125544-447730.db
```

[Operations](../guides/operations.md) covers bans, shutdowns, backups,
restores and upgrades.
