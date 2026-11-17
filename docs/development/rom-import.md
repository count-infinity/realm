# Importing ROM areas

`realm import-rom` converts a ROM 2.4 `.are` file (the Diku/Merc/ROM
lineage — Midgaard and the thousands of areas built on it) into a REALM
area file (worldio JSON) you can `@import` or load at boot. Pair it with
the [`merc` game system](../guides/game-systems.md) and a converted area
plays like a real Diku.

```bash
realm import-rom midgaard.are --out midgaard.area.json --report

# --repop: mobs respawn on death (see "Repopulation" below) — the flag the
# playable Midgaard example (realm/examples/midgaard) is built with:
realm import-rom midgaard.are --out midgaard.json --repop

# a whole directory tree at once: one JSON per area under converted/, and
# the parity report written to parity.md
realm import-rom areas/ --out converted/ --report parity.md
```

With one area file, `--out` is the JSON to write (stdout without it) and a
bare `--report` prints that area's gaps to stderr. With several files or a
directory (searched for `*.are` and `*.are.txt`), `--out` is a directory,
one JSON per area at its path under the input, and `--report FILE` writes
the parity report there (stdout without it); the command exits 1 if any
area failed to parse. The converter itself is `realm.tools.rom_import`
(`convert`, `convert_tree`).

> **Field-tested at scale.** The batch tool was run over the full public
> ansalon.net area collection — **189 files, 8 MB** — and converted **all
> 189 with zero parse failures**: 9,794 rooms, 22,487 exits, 3,236 mob and
> 4,407 object prototypes, 13,285 placed instances. Every output file is
> valid worldio JSON and imports into a live world with its exits linked.
> The [MERC parity](#merc-parity-the-punch-list) section below is the
> aggregate gap analysis from that run.

> **Playable example.** `realm/examples/midgaard` is a complete, runnable game
> built from this pipeline: the ROM Midgaard converted with `--repop`, the
> `merc` game system (subclassed in its own `rules.py`), and the
> `merc-classic` spell pack. `realm init
> --template midgaard`, connect, make a level-1 **barbarian**, and you wake
> in the Common Square with a club to thrash respawning fidos and shops to
> trade at. `tests/test_midgaard_playable.py` walks that whole loop
> (chargen → kit → kill → XP → respawn → trade → a mage's fireball).

```python
# then, in-game or in init_world:
from realm import import_objects
await import_objects(json.load(open("midgaard.area.json")), persistence,
                     preserve_ids=True)
```

`--report` lists every lossy mapping it made and how many times — read it
before shipping an imported area.

## The ROM `.are` format, briefly

Section-based text. Each section opens with `#NAME`; records are keyed by
`#vnum`; strings end with `~`; bit-vectors are decimal numbers **or** ROM
letter-flags (`A`=bit 0, `B`=bit 1 … `Z`=bit 25, `a`=bit 26 …). A decimal
one is read as the letters of its bits, so Midgaard's pet shop, whose room
flags are written `266248`, keeps `D`, `M` and `S` (`ROOM_PET_SHOP` is
`M`). The
sections the converter reads: `#AREA`/`#AREADATA`, `#MOBILES`, `#OBJECTS`,
`#ROOMS`, `#RESETS`, `#SHOPS`, `#SPECIALS`. `#HELPS`/`#SOCIALS` are skipped;
`#MOBPROGS`/`#OBJPROGS` are skipped with a warning (see below).

The header, mobile, object, and room record layouts were verified against
the canonical Midgaard file (ROM 2.4 "new format": a `race~` line on mobs,
letter-flag bitvectors, item types written as words like `drink`/`weapon`,
the `<0> <flags> <sector>` room line, and `D0`..`D5` door blocks). Resets,
shops, and specials follow the ROM 2.4 `db.c` field order.

## How ROM maps onto REALM

| ROM | REALM |
|---|---|
| room (`#ROOMS`) | object tagged `room`; `sector:<name>` tag + `sector` attr; room-flag letters kept as `rom_room_flags`, and `ROOM_NO_RECALL` (N) tagged `no_recall`; `ROOM_PET_SHOP` (M): the room's shopkeeper sells the mobs reset into the next room (vnum + 1) as pets (`sells_pets`, `pet_stock` naming their prototypes, each priced at ROM's `10 * level * level` silver in gold as `value`) |
| door `D0..D5` | an object tagged `exit` in the origin room, `db.destination` = the target room's id; a lockable door adds `door`/`closed` tags, the key vnum as a `key` attr |
| names | a mob or object is called by its **short description** (`the wizard`, `a long sword`): that is its `name`, shown in rooms, inventory, shop lists and combat. Its ROM **keywords** are its `aliases`, the whole list and each word (`["sword long", "sword", "long"]`), so `get sword`, `get long` and `get sword long` all find it. With no short description the keywords are the name |
| mobile (`#MOBILES`) | object tagged `npc` + `prototype`; `level`, `alignment`, `sex`, `credits` (its money in gold: ROM's `wealth`, which is silver, over 100; the raw figure kept as `rom_wealth`), `points` (level-scaled kill XP), `hp`/`max_hp` (from the hit dice), `damage_dice`; `race:<x>` tag. **ACT flags → the shipped NPC-AI behaviors**: non-SENTINEL → `wandering` (`stay_in_zone` if ACT_STAY_AREA), ACT_AGGRESSIVE → `aggressive` (attack-on-sight), ACT_SCAVENGER → `scavenger` that picks up what lies about and eats no corpse (`eat_corpses: false`; only `spec_fido` eats them). Shopkeepers are stripped of `wandering` and kept at the counter |
| room (`#ROOMS`), continued | also tagged `zone:<area>` (one zone per imported area — bounds STAY_AREA wanderers, and the room-set a `zone_reset` or `population` orchestrator draws on) and `outdoor` for any non-interior sector (so an orchestrator can populate "all outdoor rooms") |
| object (`#OBJECTS`) | object tagged `thing` + `prototype` + the item-type word; `ITEM_MAGIC` tagged `magic` and `ITEM_ANTI_GOOD`/`_EVIL`/`_NEUTRAL` tagged `anti_good`/`anti_evil`/`anti_neutral`; `level` (the least level to use it under Merc), `weight`, `value` (cost), `slot` for wearables (Merc's slot names: the hold flag is `held`, a light source `light`), `wieldable` for weapons; potions, pills, scrolls, wands and staves get `spells`, `spell_level` and `charges`; food gets `nourishment` (its hours of fullness times 20), drink containers `liquid` (the liquid's name; an old-format number is looked up in ROM's liquid table), `liquid_held` and `liquid_remaining` (units times 30, CoffeeMud's importer's scale) and the `drink` tag, fountains `liquid` and the `drink` and `fountain` tags (they never run dry); the five ROM value fields kept raw in `rom_values` |
| reset `M`/`O`/`G`/`E`/`P` | **instantiated at convert time**: the world ships with mobs and gear already placed (a static snapshot, the way a builder's `@export` looks), not a reset script. Read as ROM's `load_resets` reads them: a line starting with `*` is a comment, and after a reset's fields the rest of its line is one too. `P` puts into an object, never a mob that shares its vnum |
| shop (`#SHOPS`) | the keeper mob (never an object with the same vnum) gains the `shopkeeper` behavior with `markup`/`buyback` derived from its profit margins; per-item-type buy filters kept as `rom_shop_buys` |

The prototypes are emitted too (tagged `prototype`), so even a mob or item
that no reset places can be `@clone`d by a builder later.

## Capability gaps (what does not map, and why)

These are the honest lossy edges. Most are *stored* on `rom_*` attributes
rather than dropped, so nothing is lost — it just has no first-class home
in REALM yet, and a builder can wire it up in softcode.

- **Combat stat model.** ROM mobs carry Diku **armor class** (descending,
  lower-is-better) and level-based to-hit. These now map straight onto the
  [`merc` game system](../guides/game-systems.md): the converter emits
  `armor_class`, a level-derived `thac0`, and a natural-attack
  `damage_dice`, so a converted mob is combat-ready on `merc` with no
  hand-work (see [MERC parity](#merc-parity-the-punch-list)). On a
  *non-Diku* ruleset (GURPS/D20), those attrs carry as data but the
  defenses still want tuning, since AC/THAC0 have no target there.
- **Immunity / resist / vulnerability flags.** *Now mapped.* The converter
  normalizes ROM's imm/res/vuln damage bits into a portable `resistances`
  attr — a damage-taken multiplier per type (immune → 0.0, resist → 0.5,
  vuln → 1.5) that `merc`'s `apply_damage` consumes directly (see [MERC
  parity](#merc-parity-the-punch-list)). The map is continuous, so a
  hand-authored `0.85` (15% resistance) works too. The raw `rom_imm`/
  `rom_res`/`rom_vuln` letters are kept alongside, since ROM's *affect*
  immunities (summon/charm/disease/…) carry no damage-type meaning and are
  intentionally dropped from the multiplier map.
- **Weapon & object value semantics.** A ROM object's five value fields
  mean different things per item type (a weapon's dice, a container's
  capacity, a wand's spell). The converter maps weapon damage to a
  `damage` attr, armor to `ac_apply`, and consumables to the fields
  `quaff`, `recite`, `zap`, `eat` and `drink` read ([The Character
  Sheet](../guides/character-sheet.md#consumables)). Old-format areas name
  spells by ROM slot number; the converter translates them. A spell the
  `merc-classic` pack does not define, and a slot number it does not know,
  are reported as gaps, and so is a potion, pill, scroll, wand or staff
  that names no spell at all (it does nothing until it is given a
  `spells` attribute). It keeps all five values raw in `rom_values`; a
  light's duration, a container's key and the like are not wired to REALM
  mechanics. Food carries `nourishment` and drink containers `liquid`,
  `liquid_held` and `liquid_remaining`, which fill the Merc `food` and
  `water` pools (MUD_PLAN step 12); fountains are tagged `fountain`. A
  converted area already on disk is brought up to date with `python
  scripts/dev/refresh_rom_items.py <area.json>`, which also drops the
  `restores` and `charges` an earlier converter wrote on food and drink.
- **Resets: static by default, respawning with `--repop`.** ROM resets are
  a *repop spec* the server re-runs on a cycle; the converter runs them
  **once** to place the initial population (a static snapshot). Pass
  `--repop` and it *also* attaches a `spawner` behavior to each room a mob
  reset into: the spawner **adopts** the statically-placed instances (so no
  duplication) and respawns each on death (`respawn_ticks`, not
  presence-gated — the classic "keep killing them" loop, unlike the
  whole-zone `zone_reset` which only fires when a zone empties). A
  respawned mob carries `prototype_vnum` as the placed one does, so a
  quest objective or a lock that names the vnum counts it.
  **Objects restock too**: a room's floor loot (O resets) and a keeper's
  wares get a `restock` behavior that snapshots the canonical objects at
  boot and re-mints any that get taken or sold, so shops never run dry.
  Shopkeepers themselves stay static fixtures.
  **`--zone-reset` is the alternative strategy**: instead of per-room
  spawners it emits one zone master carrying a `zone_reset` behavior whose
  `reset_spec` reloads the area's canonical mobs and objects — the SMAUG
  *whole-area restore*, presence-gated (fires only when the zone empties).
  Use `--repop` to keep a lived-in world stocked continuously, `--zone-reset`
  for a dungeon that should snap back between delves (see [maintain vs
  restore](../guides/world-management.md#keeping-a-world-alive-four-tools)).
  Reset `R` (randomize exits) and reset `D` door-state are noted in
  `--report`.
- **`#SPECIALS` (spec_procs).** Compiled C behavior functions, **mapped to
  shipped behaviors** where one fits: `spec_cast_*` / `spec_breath_*` →
  `caster` (with that proc's canonical spell list; import the `merc-classic`
  pack — see [Spells as Data](../guides/spells.md)), `spec_fido` /
  `spec_janitor` → `scavenger`, `spec_thief` → `steal` (pickpocket),
  `spec_poison` → `venomous` (poisons on a landed hit; the DoT routes through
  the damage path, so poison resistance/immunity apply), and the town watch
  → `peacekeeper` (attacks WANTED criminals — see the
  [crime layer](../guides/crime.md)): `spec_executioner` only that,
  `spec_guard` with `protect="evil"` (also the most evil fighter in a
  brawl), `spec_patrolman` with `protect="fights"` (breaks up any fight,
  going for the stronger side). The movement-blocking `guard` behavior is
  a different idea and is not used. The faction and one-off procedures
  (`spec_*_member`, `spec_mayor`, `spec_nasty`, ...) stay tagged
  `rom_spec:<name>` and are reported.
- **`#MOBPROGS` / `#OBJPROGS`.** ROM's trigger-scripting (a MOBprog is the
  Diku-family answer to REALM softcode). Skipped with a warning. These
  *could* be transpiled to `$`-commands / `ON_<EVENT>` hooks — a worthwhile
  future enhancement — but the languages differ enough that it is its own
  project, not a field mapping.
- **Sector movement cost.** The sector becomes a tag and attr, and the
  `merc` feature charges ROM's `movement_loss` for it ([Life and
  Death](../guides/life-and-death.md)). Other terrain rules (swimming,
  flying) do not carry.
- **Cross-area exits.** A door leading to a vnum outside the file is emitted
  with a `rom_<vnum>` destination that resolves **only if** that room is
  imported alongside (import all the areas a zone references together, or
  the exit dangles). Flagged per-occurrence in `--report`.

## Recommended workflow

1. Convert with `--report` and read the gaps.
2. Import into a scratch database and walk the area (`look`, move through
   the exits, `examine` a mob and a shopkeeper).
3. Decide what to bring alive: add a `zone_reset` for respawns, port any
   `rom_spec:*` mobs and MOBprogs to softcode, and reconcile combat stats
   with your ruleset.

The converter's job is to get the **world** — geography, population, and
gear — in faithfully and to tell you exactly what it could not carry. The
*liveliness* (respawns, special behaviors, scripted mobs) is deliberately
left for you to add with REALM's own tools, because that is where ROM and
REALM genuinely diverge.

## MERC parity: the punch list

Running the whole ansalon collection (189 area files) through the
converter turned the abstract "capability gaps" into a ranked punch list.
MUD_PLAN step 11 finished it: a converted area plays the way a Diku
player expects on the [`merc` game system](../guides/game-systems.md#what-merc-implements).
What is left is one item, mob programs. (Counts are areas affected, out of
189.)

### What converts now

| ROM | REALM, on `merc` |
|---|---|
| mob armor class, THAC0, natural attack (145) | `armor_class`, a level-derived `thac0`, `damage_dice` |
| weapon dice and attack word | `damage_dice` (and a `damage` alias), `damage_type` (`slash` → `slashing`; old-format letters read back) |
| armor value | `ac_apply`, which `MercSystem.recompute_ac` subtracts whenever gear changes (`item:on_wear`/`item:on_remove` reach `on_equipment_change`) |
| imm/res/vuln (115) | a `resistances` multiplier per damage type (immune 0.0, resist 0.5, vuln 1.5) every shipped ruleset applies; `IMM_WEAPON`/`IMM_MAGIC` become the family keys `physical`/`magical`, decided by delivery (`ITEM_MAGIC` → the `magic` tag on a weapon), so "you need an enchanted blade" holds |
| wear flags | Merc's 14 places (`equipment`), the hold flag as `held`, a light as `light`; `float` has no place and is reported |
| object level | the least level to wear or wield it |
| `ITEM_ANTI_GOOD`/`_EVIL`/`_NEUTRAL` | `anti_good`/`anti_evil`/`anti_neutral`: worn by that alignment, the item zaps off to the floor |
| potions, pills, scrolls, wands, staves | `quaff`, `recite`, `zap`, `brandish` ([The Character Sheet](../guides/character-sheet.md#consumables)); spells by name or by ROM slot |
| food, drink containers, fountains | `eat` (`nourishment`), `drink` and `fill` (`liquid`, `liquid_held`, `liquid_remaining`; a fountain never runs dry), feeding the `food` and `water` pools of the `needs` feature ([Life and Death](../guides/life-and-death.md#hunger-thirst-and-fatigue)). The liquid is only a name: a drink's thirst, fullness and drunkenness (ROM's `liq_affect`) and a poisoned food or drink (value 3) are not modeled |
| shops (`#SHOPS`) | the `shopkeeper` behavior with markup and buyback from the profit margins |
| mob `wealth` | its money (`credits`), carried to its corpse; `get all from corpse`, `autoloot`, `autogold`, `autosplit` |
| mob alignment | `alignment`; kills move the killer's (Merc's rule) |
| ACT flags | `wandering` (`stay_in_zone` for STAY_AREA), `aggressive`, `scavenger`; `ACT_PRACTICE`/`ACT_TRAIN` → `trainer` (guildmasters) |
| `#SPECIALS`: casters and breathers (86 areas, 649 mobs) | `caster` with the proc's spell list, from the `merc-classic` pack |
| `spec_thief` (49) | `steal` |
| `spec_guard`, `spec_patrolman`, `spec_executioner` (32) | `peacekeeper`, with `protect` `evil`, `fights` and none |
| `spec_poison` (32) | `venomous` |
| `spec_fido`, `spec_janitor` (30) | `scavenger`, eating corpses (the fido) or picking up litter (the janitor) |
| resets | the mobs and objects placed at convert time; `--repop` respawns them and restocks shops, `--zone-reset` restores the whole zone |
| doors, keys | exits with `door`/`closed` tags and a `key` attribute |
| sectors | `sector:<name>`, `outdoor`, `lamplit` city streets; movement points per sector; night darkens outdoor rooms |
| `ROOM_NO_RECALL` | `no_recall`: `recall` is refused there |
| `ROOM_PET_SHOP` | the keeper sells the next room's mobs as pets that follow, obey `order` and fight beside their owner ([Pets, Charm and Mounts](../guides/companions.md#pet-shops)) |

The Diku player's side (all on `merc`): experience and levels to
`LEVEL_CAP` with class titles on `who`, practices at a guildmaster, the
class skills as commands, groups (`follow`, `group`, experience shared by
level, `split`, `report`), `scan`, `exits`, `where`, `consider` by level,
`recall` (half your movement), `brief` and `autoexit`, corpses and
respawn. A converted area already on disk is brought up to date with
`python scripts/dev/refresh_rom_items.py <area.json>` (a developer tool in
the source checkout, not the installed package): it re-derives every field
the importer now maps from the raw `rom_*` values the file keeps, renames
things named by their keywords, and can give back what the source file
lost (`--room-flags VNUM=LETTERS`, `--spells VNUM[,VNUM]=spell[+spell]`).

### What still does not

- **MOBprogs / OBJprogs (13 areas).** ROM's trigger scripting. Skipped
  with a warning; transpiling them to `$`-commands and `ON_<EVENT>` hooks
  is a language port, not a field mapping, and REALM leaves it to softcode
  (MUD_PLAN non-goal).
- **The faction and one-off spec_procs** (`spec_*_member`, `spec_mayor`,
  `spec_snake_charm`, `spec_nasty`; about 8 areas): tagged
  `rom_spec:<name>` and reported, for a builder to write in softcode.
- **Exotic item types.** `portal` (64), `warp_stone` (12) and `map` (17)
  import as objects without their behavior (a teleport is showcase 157 /
  033 in softcode); corpses in the file are containers.
- Smaller losses are listed under [Capability gaps](#capability-gaps-what-does-not-map-and-why):
  a light's duration, a container's key, reset `R` and `D`, cross-area
  exits.

## The shipped Midgaard

`realm/examples/midgaard/data/areas/midgaard.json`, the area the
`midgaard` template loads, is generated, never edited by hand. To make it
again:

1. **The source.** `area/midgaard.are` from ROM 2.4b6 (`README.version`:
   "ROM 2.4b6, May 29, 1998"), as found in the copy of the ROM
   distribution at `github.com/DikuMUDOmnibus/ROM` (6,505 lines;
   `#AREADATA` `Name Midgaard`, `VNUMs 3000 3399`).
2. **Convert** it with respawning mobs:

    ```bash
    realm import-rom path/to/area/midgaard.are --out midgaard.json --repop --report
    ```

3. **Give back the spells this copy lost.** Every potion, pill, scroll,
   wand and staff in that distribution's area files has `0` where ROM 2.4
   writes its spell names (`10 0 0 0 0`, not `10 'detect invis' ...`), so
   even ROM's own loader would find no spell. The converter reports each
   one. The spells below are those of the earlier conversion this one
   replaced (made from a Midgaard whose values still named them by ROM slot
   number); a spell an earlier source listed three times (the antidote, the
   potion of cure blindness) is given once. The scroll of cancellation and
   the potion of negation named slot 507, which ROM 2.4's table does not
   have, and stay empty.

    ```bash
    python scripts/dev/refresh_rom_items.py midgaard.json \
      --spells 3040,3240=identify \
      --spells 3041,3241="detect invis" \
      --spells 3042,3242="word of recall" \
      --spells 3080,3280=heal \
      --spells 3081,3281=sanctuary \
      --spells 3082="sanctuary+shield" \
      --spells 3282="sanctuary+armor+shield" \
      --spells 3083,3283="cure light" \
      --spells 3084,3284="cure serious" \
      --spells 3085,3285="cure critical" \
      --spells 3086,3286="cure poison" \
      --spells 3087,3287="cure blindness" \
      --spells 3088,3288=bless \
      --spells 3089,3289=armor \
      --spells 3091,3291=fly \
      --spells 3092,3292="detect invis+detect hidden+detect magic"
    ```

   The refresh writes the file back with one-space indentation (the
   converter writes two). Nothing else in a fresh conversion changes. No
   `--room-flags` is needed: the converter reads Midgaard's decimal room
   flags itself (the pet shop's `M` among them).
4. Copy the result over `realm/examples/midgaard/data/areas/midgaard.json`
   and run `tests/test_first_hour.py`, `tests/test_midgaard_playable.py`
   and the rest of the suite: they play this exact file.

**The `.are` is not in the repository.** The Diku licence
(`doc/license.doc` in the ROM distribution) must go "as is" with any copy
of any part of DikuMud, and ROM's (`doc/rom.license`) asks a derivative to
carry ROM's README and credits files; REALM ships as a pip package and
vendors none of them. So the source stays where you downloaded it, and the
converted JSON (derived work, as the earlier conversion already was) is
what ships. Its `#AREADATA` credits line, `{ All } Diku    Midgaard`,
stays the area's provenance. Those licences also ask a *running* Diku,
Merc or ROM game to name their authors at login and in a `credits`
command; whether a REALM game that loads a converted area owes that is a
question for the maintainer (BACKLOG, "After the MUD plan").

The template adds what ROM keeps in its C code rather than the area file:
ROM's `class_table` closes each guild's bar to the other classes (the
Mage's Bar 3018, the Cleric's Bar 3003, the Thieves Bar 3028, the Bar of
Swordsmen 3022), which `init_world` does with an `enter` lock on each
(`GUILD_BARS` in the template's `config.py`; barbarians, a class ROM never
had, use the swordsmen's).
