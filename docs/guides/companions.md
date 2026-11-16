# Pets, Charm and Mounts

A character can own a creature that follows, obeys and fights for it, can
charm one for a while, and can ride one. All three are the `companions`
feature (MUD_PLAN step 13), modeled on CoffeeMud's followers and on ROM's
pet shops and charm person:

- **Companions**: a creature bonded to a master follows it, obeys
  `order`, fights beside it, never turns on it, and leaves and returns
  with it when it logs out.
- **Pet shops**: a shopkeeper that sells copies of the creatures in its
  stock, each bonded to the buyer.
- **Charm**: a timed effect that makes a creature the caster's companion
  until it wears off.
- **Mounts**: a companion tagged `mount` that its master rides; it pays
  for each step where the game charges movement.

`companions` requires `social` (following) and `effects` (the charm is a
timed effect). It is in `CLASSIC`, so every game has it unless it leaves
it out.

## Companions

A companion is an NPC whose `master` attribute holds a character's id.
That is the whole relationship: it does not change who owns or controls
the object for building purposes. Bonding also sets the `social`
feature's `following` attribute, so the companion walks after its master
through every exit (locks and guards judge it as they would anyone), and
the `companion` tag and behavior (the tag is how a character's companions
are found; the behavior is the ward described under
[fighting together](#fighting-together)). Releasing takes all four away.

From Python, the feature's public names:

```python
from realm.std.companions import master_of, companions_of, set_master

refusal = await set_master(kitten, alice)    # None, or why not ("You can't accept
                                             # any more followers.")
master_of(kitten)                            # alice
companions_of(alice)                         # [kitten], wherever it is
await set_master(kitten, None)               # released: it stays where it is
```

`set_master` fires `companion:on_bond` (the `BOND` hook, `adata('how')`
is `bought`, `charmed` or `set`) and `companion:on_release` (`RELEASE`,
`adata('reason')`: `dismissed`, `released`, `charm_ended`, `master_left`,
`master_gone`, `attacked` or `rebonded`) on the creature, with the master
as `enactor`.

A player sees their companions with `companions`:

```text
> companions
Your followers:
  grey mare (mount, ridden)        30/30 hp  here
  kitten                           18/18 hp  in The Kennel
You have 2 of 2 followers.
```

Each line shows the creature's vital pool (when it has one) and where it
is: `here`, `in <room>`, or `waiting` (out of the world with its
logged-out master). The marks say what it is to you: a `mount`,
`charmed`, `ridden` (by you).

### How many

How many followers a character may keep is Decision D8: configurable, as
CoffeeMud derives it from charisma. The first of these that answers wins:

1. The setting `COMPANION_LIMIT_RULE`, a rule expression (the softcode
   `rule` profile, like a skill's `progress_rule`) with `me` bound to the
   character and `level` to its level. CoffeeMud's own formula,
   `1 + (charisma - 6) / 3`, written for a game whose characters have a
   `charisma` attribute:

   ```python
   # config.py
   COMPANION_LIMIT_RULE = "1 + (get_attr(me, 'charisma', 10) - 6) // 3"
   ```

   A rule that fails is logged at WARNING and the next layer answers.
2. The game system's `companion_limit(character) -> int`, for a system
   that wants code. `MercSystem` answers `1 + level // 10` (Diku has no
   charisma).
3. The neutral `GameSystem.companion_limit`: 2.

The count is CoffeeMud's `totalFollowers`: each companion, plus that
companion's own companions. A wolf with a cub counts two. Bonding,
buying a pet and a charm that lands all refuse past the limit with "You
can't accept any more followers."

`COMPANION_LEVEL_DIFF` (default 0, off), after CoffeeMud's
`FOLLOWLEVELDIFF`: a creature more than that many levels above the
character cannot be bonded ("The dragon is too advanced for you.").

### Orders

```text
order kitten kill fido
order all follow me
dismiss kitten
```

`order <name|all> <command>` runs the command as each companion in the
room, through the real dispatcher (the mechanism `@force` uses), so the
companion's own permissions apply; a command's reply to it (a target it
cannot find, a missing argument) comes back to you prefixed with its
name, and the room sees what it does. It refuses any command whose permission is above
`player`, `order` itself, and `quit` ("You can't order anyone to
'@dig Lair'."). A game narrows it further with `ORDER_REFUSED`, a list
of command names:

```python
# config.py
ORDER_REFUSED = ["drop", "give"]
```

A creature that is not yours answers "Do it yourself!"; a character who
is itself someone's companion "You feel like taking, not giving,
orders." `dismiss <name>` releases a companion where it stands.

A companion does not wander off or attack on sight while it has a
master: the `wandering` and `aggressive` behaviors leave it alone (ROM
skips a charmed mob the same way). Delete its `following` attribute and
it stays put while staying yours; `order <name> follow <you>` brings it
along again.

### Fighting together

When a master attacks or is attacked (any hostile action in the room,
each round's swing included), each of its companions in the room joins
the encounter against the other side: "kitten leaps to Alice's side!".
This goes through the `combat` service; without `combat`, companions
only follow. A kill by a companion is credited to its master and the
master's party (`CombatManager` asks the `companions` service before
paying the award); the `combat:on_death` event still names the companion
as the killer.

A companion never attacks its master while the relationship holds: the
`companion` behavior it carries blocks any hostile action from it at its
master ("You like Alice too much."). A master who turns on their own
companion breaks the bond (CoffeeMud ends a charm so), and the fight goes
on as any fight.

### Logging out and back in

When the master leaves play (`quit`, `logout`, a dropped link once it
times out), its companions go with it: each is taken out of the world
(location none, its room remembered in `companion_room`) with "kitten
goes with Alice." When the master enters play again they come back
beside it. A charmed creature does not wait: the charm ends when the
charmer leaves (CoffeeMud and ROM both end it). A companion whose master
no longer exists (deleted) is released by a sweep and, if it was waiting,
put back where it waited.

## Pet shops

A shopkeeper with `sells_pets` sells copies of the creatures named in its
`pet_stock`, a list of object ids. The stock can be anywhere (a back room
nobody can enter, a prototype out of the world); a copy is made for each
sale and bonded to the buyer, and the stock itself never leaves.

```text
@dig The Kennel = kennel, shop
kennel
@create kitten
@tag kitten = npc
@set kitten/value = 12
drop kitten
@examine kitten                 (note its ID: 4eb65e0e-...)
shop
@create shopkeeper
@tag shopkeeper = npc
drop shopkeeper
@behavior shopkeeper = shopkeeper, sells_pets:true, pet_stock:["#4eb65e0e-..."]
```

`list` shows the pets first, `buy` checks the buyer's limit, takes the
money and hands over the copy:

```text
> list
Pets for sale:
  kitten — 14 credits
> buy kitten
You buy a kitten for 14 credits. Enjoy your pet.
```

The price is the creature's `value` times the keeper's `markup` (1.2 by
default), in the game's currency (`credits` unless it names another), moved by
the keeper's disposition toward the buyer, exactly as for wares. A mount
shop is a pet shop whose stock is tagged `mount` (`list` marks them
"(mount)"). Without the `companions` feature, a pet shop sells only its
wares.

The `economy` feature reads the stock and the `companions` service does
the bonding, so neither imports the other.

### From ROM areas

The ROM importer handles `ROOM_PET_SHOP` (room flag `M`) as ROM does: the
mobs reset into the following room (vnum + 1) are the pets the shop room's
shopkeeper sells, and each is priced at ROM's `10 * level * level`
silver, in gold, unless it has a `value`. Midgaard's pet shop (room 3031)
sells the kitten, puppy, beagle, rottweiler and wolf. ROM's pet-shop
rules that are left out: a pet shop with no shopkeeper (ROM needs none;
here the room needs one), naming the pet as you buy it, and ROM's
one-pet-per-character (the companion limit counts pets instead).

## Charm

The `charmed` effect makes a creature its caster's companion while it
lasts. It is applied by an ability's `charm` effect, which checks the
limit and bonds first:

```json
{"type": "charm", "duration": 0, "per_level": 4, "save": "negates",
 "level_check": true, "turns_hostile": false}
```

- `duration` + `per_level` x the caster's level is how many beats it
  lasts.
- `save: "negates"`: a target that makes the game system's saving throw
  is not charmed.
- `level_check` (default true): a target above the caster's level is "too
  strong-willed".
- `turns_hostile`: when the charm wears off, the creature attacks its
  former master if it is in the room. Without it the creature simply goes
  free: "The bear's free will returns."

A player can be charmed only where the zone allows player-versus-player
(a zone master with `pvp`, read by `zone_property(room, "pvp")`). A
creature that already follows someone, a caster who is itself charmed,
and the caster themself ("You like yourself even better!") are refused.

The `merc-classic` pack ships ROM's `charm person` (a mage spell, level
20, 5 mana, `per_level: 4` so a level-20 caster's charm lasts 80 beats).
A charmed creature is a companion like any other: it follows, obeys
`order`, fights beside you and counts against your limit, shared with
your pets.

## Mounts

A companion tagged `mount` can be ridden by its master:

```text
@tag mare = mount
mount mare                      (or: ride mare)
north
dismount
```

Riding is one attribute each way: `riding` on the rider, `ridden_by` on
the mount (which is also tagged `ridden`). A mount carries one rider and
a rider rides one mount; nobody mounts in a fight; a rider who sleeps, is
knocked out or dies comes off ("You fall from the grey mare!"), and so
does one moved without its mount (a recall, a teleport).

**Moving.** The mount follows as any companion does. What the rooms see
is the movement-describer seam (below): the room left sees "Alice rides
north on a grey mare.", the room reached "Alice arrives, riding a grey
mare.", the rider "You ride north on a grey mare.", and the mount's own
steps print nothing. In a room the rider is listed "Alice (riding a grey
mare)" and the mount is left out of the listing (it is still there to
`look` at). A ridden mount does not walk off from under its rider.

**Paying.** Where the game charges movement (Merc), the step is paid from
the mount's `move` pool instead of the rider's: the Merc movement gate
asks the `companions` service who pays. A mount with no movement left
refuses ("Your mount is too exhausted."); a mount with no `move` pool
carries its rider free. A rider also spends no food or water walking
(the `needs` feature asks the same question). A fleeing rider's mount
bolts with it.

**Where riders cannot go.** A room tagged `no_mount`, and a room tagged
`sector:inside` unless `MOUNTS_INDOORS` is True: "You can't ride in
there." Dismount and walk in; the mount follows on foot.

**Mounted combat.** `GameSystem.mounted_modifiers(rider, mount) -> dict`
is asked when a rider attacks or is attacked: `{"attack": n}` is added to
the rider's attack roll and `{"defense": n}` counts against attacks on
the rider. The neutral system and Merc return `{}`.

## Softcode

| Function | |
|---|---|
| `master(obj)` | the character `obj` is a companion of, or None (read-only) |
| `companions(obj)` | `obj`'s companions, wherever they are (read-only) |
| `set_master(obj, master)` | bond an NPC the executor controls to `master`; False past the limit, the level difference, or for a player. Happens after the script |
| `release(obj)` | free an NPC the executor controls from its master. After the script |

```text
@set Biscuit/listen_heel = ^*heel*:set_master(me, enactor)
@set Biscuit/on_bond = pose('wags his whole back end.')
@set Biscuit/on_release = pose('slinks off, tail low.')
```

[Showcase 65](../showcase/065_pet.md) builds a pet with spoken tricks on
top of this, and [showcase 158](../showcase/158_mounts.md) a mount.

## The movement-describer seam

The kernel's movement lines ("{actor} leaves north.", "{actor} arrives.",
"You leave north.") are asked of the world's move describers first. A
feature declares one:

```python
@feature.move_describer
def sneaking(actor, direction, phase):
    """phase: "leave" (the room left), "arrive" (the room reached) or
    "own" (the walker's own line)."""
    if not actor.has_tag("sneaking"):
        return None                 # no opinion: the next describer, or the default
    return {"own": f"You slip {direction}.", "leave": "", "arrive": ""}[phase]
```

The first answer that is not None replaces the line, `{actor}` naming the
walker to each onlooker; `""` prints no line at all. Describers are asked
in feature order, for walks through exits (not for teleports). The same
seam serves sneaking and flying.

## Settings

| Key | Default | |
|---|---|---|
| `COMPANION_LIMIT_RULE` | None | a rule expression for the companion limit (`me`, `level`) |
| `COMPANION_LEVEL_DIFF` | 0 | a creature this many levels above cannot be bonded (0: off) |
| `ORDER_REFUSED` | `[]` | command names `order` never runs |
| `MOUNTS_INDOORS` | False | riders may ride into `sector:inside` rooms |

## Where it comes from

CoffeeMud (`coffeemud.ini` `FORMULA_MAXFOLLOW` and `FOLLOWLEVELDIFF`;
`Libraries/CharCreation.java` `getMaxFollowers`; `MOBS/StdMOB.java`
`totalFollowers` and its `TYP_FOLLOW` checks; `Commands/Order.java`;
`Abilities/Spells/Spell_Charm.java`; `Libraries/CoffeeShops.java`;
`Libraries/MUDTracker.java` riding) and ROM 2.4 (`do_buy` and `do_list`
in pet shops, `spell_charm_person`, `do_order`), with SMAUG's `do_mount`,
`do_dismount` and riding lines in `act_move.c`.

Taken: the limit as a formula, its follower count and its "You can't
accept any more followers."; `FOLLOWLEVELDIFF` and "is too advanced for
you"; order refusing what may not be ordered, "Do it yourself!", "You
feel like taking, not giving, orders." and "You have no followers here."
(ROM); a companion that will not attack its master ("You like ... too
much.") and a charm broken by its master's attack; a charm that ends when
the charmer quits and frees the creature ("free will returns"); "Isn't
... just so nice?" and "... looks at you with adoring eyes." (ROM);
ROM's pet shop (the next room's mobs, `10 * level * level`) and its
followers saved with the character; SMAUG's "You're already mounted!",
"You're not mounted." and "Your mount is too exhausted."; the mount paying
for the step and the rider spending no energy (CoffeeMud).

Changed: CoffeeMud's `FOLLOWLEVELDIFF` also refuses a creature too far
*below*; here only above. CoffeeMud's expired charm wanders off or (half
the time) attacks; here it goes free, or attacks with `turns_hostile`.
ROM's charm person is offensive (a failed charm starts a fight); here it
is not hostile, so a failed charm only fails. Anyone may mount a SMAUG
mount with the `mount` skill; here only its master, with no skill roll.

Left out: ROM's `ROOM_LAW` "The mayor does not allow charming in the city
limits." (a zone ward on the `charm` ability does it), naming a bought
pet, pets following their master on `recall`, CoffeeMud's riding of
objects (boats, carts, chairs), several riders on one mount, a flying
mount carrying its rider over water, and CoffeeMud's follower-death
depression.
