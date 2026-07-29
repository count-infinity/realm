# Importing ROM areas

`scripts/rom_import.py` converts a ROM 2.4 `.are` file (the Diku/Merc/ROM
lineage — Midgaard and the thousands of areas built on it) into a REALM
area file (worldio JSON) you can `@import` or load at boot.

```bash
python scripts/rom_import.py midgaard.are -o midgaard.area.json --report
```

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
| mobile (`#MOBILES`) | object tagged `npc` + `prototype`; `level`, `alignment`, `sex`, `gold`, `hp`/`max_hp` (from the hit dice), `damage_dice`; `race:<x>` tag |
| object (`#OBJECTS`) | object tagged `thing` + `prototype` + the item-type word; `weight`, `value` (cost), `slot` for wearables, `wieldable` for weapons; the five ROM value fields kept raw in `rom_values` |
| reset `M`/`O`/`G`/`E`/`P` | **instantiated at convert time**: the world ships with mobs and gear already placed (a static snapshot, the way a builder's `@export` looks), not a reset script |
| shop (`#SHOPS`) | the keeper mob gains the `shopkeeper` behavior with `markup`/`buyback` derived from its profit margins; per-item-type buy filters kept as `rom_shop_buys` |

The prototypes are emitted too (tagged `prototype`), so even a mob or item
that no reset places can be `@clone`d by a builder later.

## Capability gaps (what does not map, and why)

These are the honest lossy edges. Most are *stored* on `rom_*` attributes
rather than dropped, so nothing is lost — it just has no first-class home
in REALM yet, and a builder can wire it up in softcode.

- **Combat stat model.** ROM mobs carry Diku **armor class** (THAC0-style,
  lower-is-better) and `hitroll`; REALM resolves defense through
  dodge/DR/skills. AC and hitroll are **dropped** (not stored) because they
  have no meaningful target. `hp`/`level`/`damage_dice` do carry over, so a
  mob is present and killable, but its defenses will need tuning to your
  ruleset.
- **Immunity / resist / vulnerability flags.** ROM has a damage-type
  resist table; REALM has no equivalent table yet (an `on_check` ward is
  the manual path, see the interception guide). Kept as `rom_imm`/
  `rom_res`/`rom_vuln` attrs for hand-porting.
- **Weapon & object value semantics.** A ROM object's five value fields
  mean different things per item type (a weapon's dice, a container's
  capacity, a wand's spell). The converter maps weapon damage to a
  `damage` attr and keeps all five raw in `rom_values`; a light's duration,
  a potion's spells, a container's key, etc. are **not** wired to REALM
  mechanics — they are data waiting for softcode.
- **Resets are frozen, not respawning.** ROM resets are a *repop spec* the
  server re-runs on a cycle; the converter runs them **once** to place the
  initial population. The dynamic respawn maps to REALM's `zone_reset`
  behavior + `reset_spec` (showcase 147), which the converter does **not**
  emit — an imported area is a static world until you add repop. Reset `R`
  (randomize exits) and reset `D` door-state are noted in `--report`.
- **`#SPECIALS` (spec_procs).** Compiled C behavior functions
  (`spec_cast_mage`, `spec_thief`, …). No portable equivalent; the mob is
  tagged `rom_spec:<name>` so you can find them and reimplement in softcode
  or a behavior. This is the biggest "content looks imported but isn't
  alive" trap — a shopkeeper works (it became a behavior), a casting mage
  does not.
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
