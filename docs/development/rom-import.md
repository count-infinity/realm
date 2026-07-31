# Importing ROM areas

`scripts/rom_import.py` converts a ROM 2.4 `.are` file (the Diku/Merc/ROM
lineage — Midgaard and the thousands of areas built on it) into a REALM
area file (worldio JSON) you can `@import` or load at boot. Pair it with
the [`merc` game system](../guides/game-systems.md) and a converted area
plays like a real Diku.

```bash
python scripts/rom_import.py midgaard.are -o midgaard.area.json --report

# --repop: mobs respawn on death (see "Repopulation" below) — the flag the
# playable Midgaard example (examples/midgaard) is built with:
python scripts/rom_import.py midgaard.are -o midgaard.json --repop

# a whole directory tree at once, with a parity report:
python scripts/rom_import_batch.py areas/ -o converted/ --report parity.md
```

> **Field-tested at scale.** The batch tool was run over the full public
> ansalon.net area collection — **189 files, 8 MB** — and converted **all
> 189 with zero parse failures**: 9,794 rooms, 22,487 exits, 3,236 mob and
> 4,407 object prototypes, 13,285 placed instances. Every output file is
> valid worldio JSON and imports into a live world with its exits linked.
> The [MERC parity](#merc-parity-the-punch-list) section below is the
> aggregate gap analysis from that run.

> **Playable example.** `examples/midgaard` is a complete, runnable game
> built from this pipeline: the ROM Midgaard converted with `--repop`, the
> `merc` game system, and the `merc-classic` spell pack. `realm init
> --template midgaard`, connect, make a level-1 **barbarian**, and you wake
> in the Common Square with a club to thrash respawning fidos and shops to
> trade at. `tests/test_midgaard_playable.py` walks that whole loop
> (chargen → kit → kill → XP → respawn → trade → a mage's fireball).

```python
# then, in-game or in init_world:
from realm.persistence.worldio import import_objects
await import_objects(json.load(open("midgaard.area.json")), persistence,
                     preserve_ids=True)
```

`--report` prints, to stderr, every lossy mapping it made and how many
times — read it before shipping an imported area.

## The ROM `.are` format, briefly

Section-based text. Each section opens with `#NAME`; records are keyed by
`#vnum`; strings end with `~`; bit-vectors are decimal numbers **or** ROM
letter-flags (`A`=bit 0, `B`=bit 1 … `Z`=bit 25, `aa`=bit 26 …). The
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
| room (`#ROOMS`) | object tagged `room`; `sector:<name>` tag + `sector` attr; room-flag letters kept as `rom_room_flags` |
| door `D0..D5` | an object tagged `exit` in the origin room, `db.destination` = the target room's id; a lockable door adds `door`/`closed` tags, the key vnum as a `key` attr |
| mobile (`#MOBILES`) | object tagged `npc` + `prototype`; `level`, `alignment`, `sex`, `gold`, `points` (level-scaled kill XP), `hp`/`max_hp` (from the hit dice), `damage_dice`; `race:<x>` tag. **ACT flags → the shipped NPC-AI behaviors**: non-SENTINEL → `wandering` (`stay_in_zone` if ACT_STAY_AREA), ACT_AGGRESSIVE → `aggressive` (attack-on-sight), ACT_SCAVENGER → `scavenger` (eat corpses / pick up litter). Shopkeepers are stripped of `wandering` and kept at the counter |
| room (`#ROOMS`), continued | also tagged `zone:<area>` — one zone per imported area, which bounds STAY_AREA wanderers and lets a `zone_reset` find its rooms |
| object (`#OBJECTS`) | object tagged `thing` + `prototype` + the item-type word; `weight`, `value` (cost), `slot` for wearables, `wieldable` for weapons; the five ROM value fields kept raw in `rom_values` |
| reset `M`/`O`/`G`/`E`/`P` | **instantiated at convert time**: the world ships with mobs and gear already placed (a static snapshot, the way a builder's `@export` looks), not a reset script |
| shop (`#SHOPS`) | the keeper mob gains the `shopkeeper` behavior with `markup`/`buyback` derived from its profit margins; per-item-type buy filters kept as `rom_shop_buys` |

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
  `damage` attr and keeps all five raw in `rom_values`; a light's duration,
  a potion's spells, a container's key, etc. are **not** wired to REALM
  mechanics — they are data waiting for softcode.
- **Resets: static by default, respawning with `--repop`.** ROM resets are
  a *repop spec* the server re-runs on a cycle; the converter runs them
  **once** to place the initial population (a static snapshot). Pass
  `--repop` and it *also* attaches a `spawner` behavior to each room a mob
  reset into: the spawner **adopts** the statically-placed instances (so no
  duplication) and respawns each on death (`respawn_ticks`, not
  presence-gated — the classic "keep killing them" loop, unlike the
  whole-zone `zone_reset` which only fires when a zone empties).
  **Objects restock too**: a room's floor loot (O resets) and a keeper's
  wares get a `restock` behavior that snapshots the canonical objects at
  boot and re-mints any that get taken or sold, so shops never run dry.
  Shopkeepers themselves stay static fixtures. Reset `R` (randomize exits)
  and reset `D` door-state are noted in `--report`.
- **`#SPECIALS` (spec_procs).** Compiled C behavior functions. Two families
  are **mapped to shipped behaviors**: `spec_cast_*` / `spec_breath_*` →
  the `caster` behavior (with that proc's canonical spell list; import the
  `merc-classic` pack for the spell_defs — see [Spells as
  Data](../guides/spells.md)), and `spec_fido` / `spec_janitor` → the
  `scavenger` behavior. The rest (`spec_thief`, `spec_guard`, …) are tagged
  `rom_spec:<name>` for mapping later — see the punch list below.
- **`#MOBPROGS` / `#OBJPROGS`.** ROM's trigger-scripting (a MOBprog is the
  Diku-family answer to REALM softcode). Skipped with a warning. These
  *could* be transpiled to `$`-commands / `ON_<EVENT>` hooks — a worthwhile
  future enhancement — but the languages differ enough that it is its own
  project, not a field mapping.
- **Sector movement cost / terrain effects.** The sector becomes a tag and
  attr, but ROM's per-sector movement point cost and terrain rules are
  engine behavior REALM models differently; only the classification carries.
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

Running the whole ansalon collection through the converter turns the
abstract "capability gaps" into a ranked, real punch list. Where a gap is
already closed, it says so; where it is not, it names the best way to
reach parity. (Counts are areas-affected out of 189.)

### Already closed — imported areas are combat-ready on `merc`

The converter emits MERC-native combat stats, so a converted mob fights
with no hand-work (verified: an imported Midgaard sexton — hp 42, AC 7,
THAC0 17 — trades blows with a warrior on the `merc` ruleset):

- **Mob armor class** → `armor_class` (ROM's descending AC, straight to
  MERC's), and **THAC0** derived from level. (Was the #1 gap, 145 areas.)
- **Mob natural attack** → `damage_dice`; MercRuleset uses it when the mob
  is unarmed.
- **Weapon** → `damage_dice` (what MercRuleset reads) + a `damage` alias.
- **Armor** → `ac_apply`; MERC's `recompute_ac` subtracts it.
- **Damage-type resistance** (was 115 areas) → a portable `resistances`
  multiplier map. The converter decodes ROM's imm/res/vuln bits to a
  per-type damage-taken multiplier (immune 0.0, resist 0.5, vuln 1.5), and
  `MercRuleset.apply_damage` scales each typed hit through the neutral
  `apply_type_resistance` helper. Because the value is a float, not one of
  three tiers, a builder can author *any* resistance (`0.85` = 15%); Diku's
  tiers are just three points on it. `DamageType.TRUE` bypasses the map.
- **Worn-armor AC for players** (was 101 areas of equip resets) → live.
  `wear`/`remove` fire `item:on_wear`/`item:on_remove`; the boot-registered
  `equipment_observer` forwards an applied gear change to the active
  system's `on_equipment_change` hook, which `MercSystem` overrides to
  `recompute_ac`. The command stays system-neutral — the rules package is
  just one more reactor on the event bus, like the stealth and hostile
  observers. (Mob AC is authored in the file, so this is about players,
  not imported NPCs.)
- **Shops** → the `shopkeeper` behavior. **Doors** → initial lock tags.

### Spells — closed

Half the ROM special procedures are **spell casters** — `spec_cast_mage`,
`_cleric`, `_undead`, `_adept`, `_judge`, `_druid`, `_necromancer`, plus
the `spec_breath_*` family. These are now alive end to end (see [Spells
as Data](../guides/spells.md)):

- **`spell_def` objects** carry each spell as data (mana, level, target,
  typed damage, save, heal, timed-effect attachment); casting is one
  propagated `spell:<name>` action — wards, saves, and the damage-type
  `resistances` layer all apply.
- The **`caster` behavior** is the whole spec_cast family as one
  parameterized behavior; it casts through the same pipeline players use.
- The **importer attaches it automatically**: `spec_cast_*` /
  `spec_breath_*` mobs get `caster` with that proc's canonical spell list
  (ROM `special.c`). Over the ansalon collection this brings **86 areas
  and 649 caster mob prototypes** to life.
- The **`merc-classic` pack** (`@pack import merc-classic`) supplies the
  23 classic spells those lists reference — import it alongside a
  converted area and its guildmasters cast.

### Behavioral spec_procs — map to existing tools now

The non-casting procedures already have homes; the parity step is a
`rom_spec:* → behavior` mapping the importer applies:

| spec_proc | areas | maps to |
|---|---:|---|
| `spec_thief` | 49 | a steal behavior (showcase 070, pickpocket) |
| `spec_guard` / `spec_patrolman` / `spec_executioner` | 32 | the shipped `guard` behavior |
| `spec_poison` | 32 | `damage_over_time` behavior applied on hit |
| `spec_fido` / `spec_janitor` | 30 | a scavenger `behavior_def` (eat corpses / pick up trash) — a textbook data-defined behavior |
| `spec_*_member`, `spec_snake_charm`, `spec_mayor` | ~8 | faction / bespoke softcode |

The mobs are already tagged `rom_spec:<name>`, so a lookup table plus
`@behavior` (or the importer attaching them) is all it takes for the
behavioral half.

### Lower priority

- **MOBprogs / OBJprogs — 13 areas.** ROM's trigger scripting. Skipped
  today; transpiling to `$`-commands / `ON_<EVENT>` hooks is its own
  project (a language port, not a field mapping).
- **Exotic item types.** `portal` (64) and `warp_stone` (12) → a teleport
  behavior (showcase 157 / 033); `gem` (39) already works as a valued
  object; `map` (17) → a readable desc; corpses → containers. All import
  as objects; only their *behavior* is missing, and it is softcode.

### Summary

Geography, population, gear, shops, basic combat, **damage-type
resistance**, **live worn-armor AC**, and **spellcasting** are **done** —
189 areas convert, load, and fight on `merc` with imm/res/vuln honored,
player armor that matters, and 649 spec_cast/breath mobs casting from the
`merc-classic` pack. What remains is the behavioral spec-proc→behavior
map (mechanical) and MOBprogs (a language port). Nothing is blocked;
each gap has a named path.
