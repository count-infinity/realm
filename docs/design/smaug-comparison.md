# SMAUG (SmaugFUSS) vs REALM

A survey of **SmaugFUSS** — the maintained fork of **SMAUG**, itself a
DikuMUD → Merc → ROM → SMAUG descendant, ~55 `.c` files under `src/` — read
as a reference for **REALM**. SMAUG is not a framework; it is a *complete,
shipped fantasy MUD* (Realms of Despair's engine) with clans, deities,
housing, weather, polymorph, and a full spell list baked in. That makes it
the richest **game-content** reference of the lot, and the sharpest test of
REALM's kernel/game line: almost everything SMAUG is famous for is *content*
that, in REALM, belongs in a pack — not the engine.

The headline framing, before the detail. It is tempting to say "SMAUG =
hardcoded C, REALM = data" — and **that would be wrong.** Modern SmaugFUSS is
aggressively data-driven: classes (`classes/*.class`), races
(`races/*.race`), skills/spells (`system/skills.dat`), liquids, herbs, even
the **command table** (`system/commands.dat`) all load from editable text
files at boot, and are editable in-game through OLC. The real difference is
one level deeper, and it is about **what kind of thing the data is**:

- **SMAUG data-drives fixed-schema *descriptors* and binds *behavior* to
  compiled C by name.** A skill is a ~45-field `struct skill_type`
  (`mud.h:2851`); its *effect* is a C function (`spell_acid_blast`) located
  at load time by **`dlsym()` on the running binary** (`tables.c:49`) from a
  `Code` string in the data file. The data says *which* C function; the C
  function is *what happens*. New behavior = recompile.
- **REALM data-drives *composable primitives* and expresses *behavior* as
  softcode.** A `skill_def` is a small composition; its effect is a
  sandboxed-Python action any builder writes live. New behavior = type it in.

So SMAUG's `skill_type`/`class_type`/`race_type` structs are the textbook
form of REALM's **mega-descriptor anti-pattern** (VISION invariant 6 — the
"struct-of-flags / Win32 signature"), and its in-area **MOBprograms** are the
one place SMAUG has genuine in-data programmability — a fixed-vocabulary
`if/else/endif` mini-language that is the Diku-family analog of REALM's
`^listen` / `ON_<EVENT>` triggers, but far short of a language. **SMAUG bakes
into C what REALM expresses as data; where SMAUG does use data, it is a rigid
descriptor, not a program.** Everything below is detail on that sentence.

---

## Part 1 — The world/area data model (`.are` + OLC)

SMAUG's world is a set of **area files** (`area/*.are`, 24 stock areas),
each a flat text file of tilde-terminated records. SmaugFUSS uses the
**FUSS format**: tagged blocks (`#ROOM … #ENDROOM`, `#MOBILE`, `#OBJECT`,
`#MUDPROG`) rather than stock Diku's positional `#NNNN` records. Everything
is addressed by a global integer **vnum**. A room carries inline **resets**
(`Reset M 0 101 1 100` = load mob 101 into room 100) and the OLC editors
(`redit`/`medit`/`oedit`) write these files back out.

| Concern | SMAUG | REALM |
|---|---|---|
| Unit of world | `.are` file, tagged blocks (`#ROOM`/`#MOBILE`/`#OBJECT`/`#MUDPROG`), area file `newgate.are` | area import/export as data (`worldio`) |
| Identity | global integer **vnum** (`Vnum 100`), one namespace for rooms/mobs/objs | UUID per `GameObject`; tags for classification |
| Object model | fixed kinds: room / mob / obj / exit, each a distinct C struct (`ROOM_INDEX_DATA`, `MOB_INDEX_DATA`, `OBJ_DATA`) | one `GameObject` (uuid, tags, db attrs, behaviors); room/mob/item are tag+behavior compositions, no type tree |
| Prototype vs instance | `MOB_INDEX_DATA` prototype → `create_mobile()` clones instances (`db.c:2660`); objs likewise | data-driven definitions instantiated into objects |
| Stats storage | fixed struct fields + bitvector flag words (`Actflags`, `Affected`, `WFlags`) | open `db` attribute bag + tags |
| Room→behavior link | `#MUDPROG` block attached to mob/obj/room by vnum | triggers/behaviors attached to the object |
| Repopulation | **area reset** — timed re-run of the reset list (`area_update` `db.c:2602`, `reset_area` `reset.c:912`) | (per-room spawner behavior only — see steal-list) |
| Building | in-game **OLC**: `do_redit` (`build.c:4725`), `do_medit`, `do_oset` (`build.c:3108`), `do_aset` (`build.c:7128`), `do_mpedit` (`build.c:7693`) | OLC + softcode `dig`/`open`/`create_obj` |
| Persistence | flat text files, hand-parsed with KEY macros | SQLite |

**Reset semantics (the part worth stealing).** Every area has a
`reset_frequency` (default 15 minutes, `db.c:2609`). `area_update()` ages
each area every tick; when an area is empty of players *or* its age exceeds
the frequency, `reset_area()` re-runs the area's reset list, respawning mobs
and objects to their canonical placement (`db.c:2641`). A `resetmsg` ("You
hear some squeaking sounds…") warns players still inside. Resets are a
**declarative repopulation program** — command letters `M` (mob), `O`
(object), `P` (put in container), `E` (equip), `G` (give), `D` (door
state), `R` (randomize exits), `T` (trap/trigger) — evaluated by
`reset_room()` (`reset.c:73`+). This is a genuine engine *mechanism* REALM
has no equivalent for.

**Verdict on the data model.** SMAUG's is *narrower* than REALM's by design:
four fixed object kinds, a global-integer namespace, struct fields with
bit-flag words. REALM's UUID + tags + open-attr `GameObject` is strictly more
general (invariant 7, entity-agnostic — a ship and a door are the same shape,
which SMAUG's four-struct world cannot express). But SMAUG's **inline
declarative resets** and the **timed area-reset loop** are a real primitive
REALM lacks.

---

## Part 2 — The trigger/scripting model (MOBprograms) — the ^listen analog

This is the direct Diku-family analog of REALM's `^listen` / `ON_<EVENT>`.
SMAUG's **MOBprograms** (with parallel **objprograms** and **roomprograms**,
all driven by the same interpreter in `mud_prog.c`, 114 KB) let a builder
attach a script to a mob/obj/room that fires on an event. A `#MUDPROG` block
is `Progtype` + `Arglist` (the trigger filter) + `Comlist` (the script):

```
#MUDPROG
Progtype  act_prog~
Arglist   p arrives from above.~
Comlist   smile $n
say Welcome to the Realms of Despair reception chamber, $n.
mpechoat $n Please take the time to read everything you see along the way.
~
#ENDPROG
```

### Trigger vocabulary

Programs are typed by a fixed enum of **~40 trigger types** (`mud.h:5053`):

| Family | Trigger types |
|---|---|
| Speech | `speech_prog`, `speechiw_prog` (in-world), `tell_prog`, `cmd_prog` |
| Presence | `greet_prog`, `all_greet_prog`, `greet_in_fight_prog`, `entry_prog`, `leave_prog`, `login_prog` |
| Combat | `fight_prog`, `death_prog`, `hitprcnt_prog` (HP-threshold) |
| Give/econ | `give_prog`, `bribe_prog`, `sell_prog`, `buy` path |
| Item verbs | `get_prog`, `drop_prog`, `wear_prog`, `remove_prog`, `use_prog`, `sac_prog`, `look_prog`, `exa_prog`, `pull_prog`/`push_prog`, `damage_prog`, `repair_prog`, `zap_prog` |
| Ambient | `rand_prog`, `randiw_prog`, `time_prog`, `hour_prog`, `script_prog` (runs like a program each pulse) |
| Special | `act_prog` (matches any `act()` message the mob witnesses), `load_prog` |

`act_prog` matched against overheard `act()` output (`mprog_keyword_check`,
`mud_prog.c:2795`) **is exactly `^listen`** — a pattern-in-witnessed-text →
action reaction. `speech_prog` is `^listen` scoped to speech; `greet_prog` is
`ON_ENTER`; `death_prog`/`fight_prog`/`hitprcnt_prog` are combat `ON_<EVENT>`
hooks. REALM's event stream + `^listen` + `ON_<EVENT>` covers this family
with **one uniform mechanism** instead of 40 named entry points; SMAUG's list
is a menu of the events the *game* cares about (a pack concern), not distinct
*mechanisms*.

### Expressiveness — and its ceiling

The interpreter (`mprog_driver` `mud_prog.c:1944`, one line at a time via
`mprog_do_command` `:2390`) supports `if` / `and` / `or` / `else` / `endif`,
nested to depth 20 (`MAX_PROG_NEST`, `mud.h:966`). Conditions are a fixed
table of **~90 `ifchecks`** — `rand(n)`, `ispc`/`isnpc`, `level`, `class`,
`race`, `hps`, `hitprcnt`, `carryingvnum`, `mobinroom`, `isaffected`,
`istagged`, `clan`, `deity`, `favor`, `str`/`dex`/etc.
(`mud_prog.c:402–1573`) — each hardcoded as a `str_cmp` branch in C. The
action side is a fixed set of **~50 mob-commands** (`do_mp*` in `mud_comm.c`):
`mpecho`, `mpechoat`, `mpechoaround`, `mpforce`, `mpat`, `mpgoto`, `mptransfer`,
`mpmload`/`mpoload`, `mppurge`, `mpkill`, `mppeace`, `mpjunk`, `mpapply`,
`mpmset`/`mposet`, `mpmorph`, `mphate`/`mphunt`/`mpfear`, `mpscatter`…

Its **variable model** is the honest ceiling:

- **No local variables.** A program cannot bind a name to a value. There is
  no arithmetic beyond an `ifcheck`'s single `operator rval` comparison
  (`>`/`<`/`==` on one queried quantity), no expressions, **no loops** — the
  driver is strictly linear over `if`-gated lines.
- **Substitution codes only.** Values reach the text via ~25 fixed `$`-codes
  (`mprog_translate` `mud_prog.c:1619`): `$n`/`$N` actor, `$i`/`$I` self,
  `$t`/`$T` target, `$r`/`$R` a random mob in the room, `$e`/`$m`/`$s`
  pronouns. These are string interpolations, not variables you can compute
  on.
- **Persistent state = "tags".** The only mutable state is per-character
  **quest variables** (`VARIABLE_DATA`, `mud.h:555`) — typed str/int/xbit
  values set on a player and read back with the `istagged`/`isflagged`
  ifchecks (`get_tag`, `mud_prog.c:1315`). This is a genuine (if narrow)
  persistent key-value store for quest progress.
- **One concession to time:** `mpsleep` suspends a program mid-run and
  resumes it later, saving the `if`-state stack (`mud_prog.c:2117`) — a
  cooperative yield, the direct analog of REALM's `wait()`.

| Aspect | SMAUG MOBprograms | REALM softcode |
|---|---|---|
| Language | fixed `if/and/or/else/endif`, no loops, no locals | sandboxed **Python subset** (full expressions, comprehensions, functions) |
| Conditions | ~90 hardcoded `ifcheck` C branches | any Python expression over object data via `safe_eval` |
| Actions | ~50 hardcoded `do_mp*` commands | any command + `@softcode_function` native bindings |
| Values | ~25 `$`-substitution codes | real variables, data structures, math |
| Persistent state | per-char typed "tags" (quest vars) | object `db` attributes (open) |
| Events | ~40 named `*_prog` trigger types | uniform event stream + `^listen` + `ON_<EVENT>` |
| Yield | `mpsleep` | `wait()` / `prompt()` |
| Trust | builder-authored, interpreted, sandboxed by the fixed vocabulary | sandboxed softcode (any builder) vs native bindings (operators) — two-tier |

**Verdict on triggers.** SMAUG's trigger *vocabulary* is decades-tested and
worth mining name-by-name (below). But its *language* is a fixed
if/echo/force template — REALM's Python-subset softcode is a strict
superset of what any MOBprogram can express, and its uniform event stream
replaces 40 named entry points with one mechanism. The one thing SMAUG's
model has that REALM should note is the **`istagged` quest-variable
convention** — a blessed, queryable place for per-player quest state — and
the trigger-type *names* as a checklist of events a game will want.

---

## Part 3 — Rules tables (class / race / skill / spell / affect)

SMAUG's rules are **data-as-fixed-descriptor + effect-as-compiled-C**. The
runtime holds pointer arrays `class_table[]`, `race_table[]`, `skill_table[]`
(`tables.c:36`), populated at boot from text files; the *logic* is C bound by
name via `dlsym`.

| Concern | SMAUG | REALM |
|---|---|---|
| Class | `classes/*.class` → `struct class_type` (`mud.h:1036`): `attr_prime`, `thac0_00/32`, `hp_min/max`, `exp_base`, guild vnum + `Skill '<name>' <lvl> <adept%>` grants | `class_def` **PACK** (importable data), no C class |
| Race | `races/*.race` → `struct race_type` (`mud.h:1057`): `str_plus…lck_plus`, `hit`, `mana`, `class_restriction` bits, `exp_multiplier`, saves, `attacks`/`defenses` bitvectors | `skill_def`/race data pack |
| Skill/spell | `system/skills.dat` → **`struct skill_type`** (`mud.h:2851`, ~45 fields): per-class `skill_level[]`, per-race `race_level[]`, `min_mana`, `beats`, damage/miss/die/immune message sextets, `dice`, `SMAUG_AFF` list, `components` | `skill_def` pack + **softcode effect** |
| Effect binding | `Code spell_acid_blast` → **`dlsym()`** on running binary (`tables.c:49`); dispatched `(*skill_table[sn]->spell_fun)(...)` (`skills.c:442`) | effect **is** softcode, not a binding to C |
| Generic (no-C) spell | falls back to `spell_smaug` interpreter driven by the fixed `SMAUG_AFF` descriptor (`skills.c:1173`) | any effect authorable directly |
| Level/XP | hardcoded cubic `(level-1)³ × exp_base` (`exp_level` `handler.c:656`), `exp_base` from class file | data-driven advancement in the GameSystem |
| Timed modifier | **`struct affect_data`** (`mud.h:1288`): `type`, `duration`, `location` (`APPLY_*`), `modifier`, `bitvector`; applied by `switch(location)` in `affect_modify` (`handler.c:1083`); duration decremented each combat round (`fight.c:384`) | **effects = condition behaviors** (composed) |

The `.class`/`.race`/`.dat` files are legible and editable
(`Mage.class`: `Thac0 18`, `Expbase 1250`, `Skill 'armor' 5 95`), and OLC
`sedit`/`cedit` edits them live. **But two invariants are violated by the
shape of the data:**

1. **Mega-descriptor (invariant 6).** `skill_type` is a 45-field
   struct-of-flags carrying six message sextets, dice strings, class/race
   level arrays, mana, beats, components, and affect lists in one record.
   REALM composes these from small primitives; SMAUG enumerates every field
   a spell *might* need whether or not a given skill uses it.
2. **Effect is C, not data (invariants 1, 3).** The skill's *behavior* is
   `spell_acid_blast`, a compiled function `dlsym`'d by name. The data
   chooses among pre-written C behaviors; it cannot author a new one. This is
   the exact line REALM refuses: game-meaning (what a spell *does*) lives in
   the engine binary, not in the game layer. `spell_smaug` + `SMAUG_AFF` is a
   partial escape — a tiny data-driven interpreter for stat-buff spells — but
   anything novel needs C.

**Verdict on rules.** SMAUG is *more* data-driven than folklore admits, and
its `affect_data` (a clean intrusive list of `location`/`modifier`/`duration`
tuples, ticked in the combat pulse) is a tidy, proven **timed-modifier
primitive** — REALM's `effects = condition behaviors` should read like it.
But the descriptor shape (mega-struct) and the effect-binding model (C via
`dlsym`) are precisely what REALM exists to avoid. This is content that
belongs in a **GURPS/D20 pack**, expressed as composed primitives + softcode,
not a 45-field struct.

---

## Part 4 — Combat (the ROM/SMAUG round)

| Aspect | SMAUG | REALM |
|---|---|---|
| Round driver | `violence_update()` (`fight.c:287`), fired every `PULSE_VIOLENCE` = 3 s (`update.c:2053`) | beat-driven, ruleset-agnostic combat |
| To-hit | classic **THAC0 vs AC**: `interpolate(level, thac0_00, thac0_32) - hitroll` vs `AC/10`, d20 roll (`fight.c:1179`, miss at `:1220`) | resolution primitive (graded outcome), ruleset supplies the roll |
| Attacks/round | first swing guaranteed, then skill-gated extras: dual-wield, `second`…`fifth attack` gsn checks, NPC `numattacks`, berserk (`multi_hit` `fight.c:806`) | composed from primitives per ruleset |
| Damage | `one_hit` → `damage()` (`fight.c:1832`), messaged via `dam_message()` from `attack_table`/`s_message_table` (`const.c:257`) | graded resolution → effects |
| Affect tick | buff durations decremented in the same round loop (`fight.c:384`) | effect behaviors on the tick scheduler |

SMAUG's round is a **specific ruleset hardcoded in C** — THAC0, AC/10, a
fixed d20, class-specific attack tables. It is exactly one game's combat
math. REALM's combat is a **ruleset-agnostic beat engine** where the roll is
supplied by a swappable `GameSystem` (invariant 7: a ship and a person run
the same mechanic). SMAUG's value here is as a *worked example* of a
Diku-style round to reproduce **as a pack**, not as engine design to copy.

---

## Part 5 — Built-in social systems (the battle-tested content)

This is SMAUG's real wealth — and, to a one, **game content hardcoded in
C** with flat-file instance data. Each binds to the world through room/object
**vnums** and has its own `*_DIR` data directory.

| System | What it is | Where | Data |
|---|---|---|---|
| **Clans** | guilds w/ leader + 2 officers, per-level PK kill/death tallies, member roster, bound board/recall/storeroom/guard vnums | `clans.c`; `struct clan_data` `mud.h:1125` | `clans/*.gui` + `clan.lst`; roster as `#ROSTER` blocks |
| **Councils** | governance bodies (name, heads, free-text `powers`, meeting room) | `clans.c`; `struct council_data` `mud.h:1169` | `councils/` (empty by default) |
| **Deities** | worship + **favor economy**: struct is a table of favor deltas per action (kill/flee/sac/steal…); `supplicate` spends favor to teleport corpse, summon an avatar mob, etc.; favor thresholds grant resist/element/affect flags | `deity.c`; `struct deity_data` `mud.h:1186`; `adjust_favor` `fight.c:2721` | `deity/` + `deity.lst` |
| **Boards** | message boards **and balloting** (notes carry yes/no/abstain vote tallies); per-board read/post/remove levels, group gating | `boards.c`; `struct board_data` `mud.h:1254` | `boards/*.brd` + `boards.txt` |
| **Corpses & decay** | death → `make_corpse()` clones a corpse obj (NPC `timer=6`, PC `timer=40`); `obj_update` decrements `obj->timer`, swaps grislier `corpse_descs[]` strings, `extract_obj()` at zero (PC decays 8× slower) | `makeobjs.c:123`, `update.c:1378` | prototype vnums |
| **Houses** | player housing: a room assigned to an owner + generated key, contents persisted per-owner | `house.c`; `HOME_DATA` | `HOUSE_DIR` per-owner files |

Plus (not detailed): weather (`weather.c`, 160 KB), polymorph (`polymorph.c`),
shops (`shops.c`), liquids/cooking (`liquids.c`), calendar, mounts, a chess
board. **All of it C.** Every one of these is a subsystem REALM would express
as a **pack + softcode composition** (invariant 9: subsystems are
compositions, not kernel features). SMAUG proves these systems *work* and
what fields they need — the corpse-decay timer, the favor-delta table, the
board vote tally — but their *implementation* is the opposite of REALM's
thesis.

---

## Part 6 — The server model

| Component | SMAUG | REALM |
|---|---|---|
| Game loop | `game_loop()` (`comm.c:789`), `select()` on descriptors, then `update_handler()` (`update.c:2017`) each pulse; sleeps to clock (`comm.c:959`) | Twisted-style reactor + tick scheduler |
| Pulse rate | `PULSE_PER_SECOND = 4` (`db.c:392`), ~250 ms; violence every 12 pulses (3 s), mobiles every 4 s | tick scheduler / heartbeat |
| Update dispatch | counters in `update_handler`: `area_update`, `mobile_update`, `violence_update`, `char_update`, `obj_update` | scheduled behaviors + `on_tick` |
| Command table | **hash table `command_hash[126]`** (`interp.c:38`), **loaded from `system/commands.dat`** at boot (`load_commands` `tables.c:1693`); each `cmd_type` binds a name → `do_fun` C pointer via `dlsym` + level/position/log | command dispatch; commands are data + softcode `$`-commands |
| Command dispatch | `interpret()` (`interp.c:235`) hashes first letter, prefix-matches, checks trust, calls `(*cmd->do_fun)(ch, arg)` (`interp.c:545`) | two-pass action propagation |
| Spec-procs | mob C behaviors bound by **`dlsym`** against a `specfuns.dat` whitelist (`spec_lookup` `special.c:128`): `spec_cast_mage`, `spec_guard`, `spec_janitor`, `spec_thief`… | behaviors (data + softcode), `on_tick` |

SmaugFUSS's server is notably more data-driven than stock Diku in exactly the
same *shape* as its rules: the **command table** and **spec-proc whitelist**
are loaded from disk and bound to C functions by name at runtime (`dlsym`).
So the dispatch *table* (name → level → function) is editable data, but the
dispatched *function* is compiled C. This is the identical pattern to skills —
**data-drives the table, hardcodes the behavior** — and the identical gap
from REALM, where the behavior itself is softcode. REALM's `$`-commands and
behaviors have no C to bind to; the command *is* the data.

---

## Capabilities REALM lacks or should learn from

SMAUG's decades of production shipping bought it battle-tested *game systems*
REALM has not built — but they arrive as C content, not engine mechanism.
Sorted by what's actually a **mechanism gap** vs a **pack REALM will write**:

**Genuine mechanism gaps (engine-level, worth building):**

1. **Timed area reset / repopulation.** `area_update`/`reset_area`
   (`db.c:2602`, `reset.c:912`) — a periodic, declarative respawn of an
   area's canonical contents, gated on player presence, with a warning
   message. REALM's `worldio` imports areas but has no *reset loop*. This is
   a real primitive with no *area-level* REALM analog — per-room
   `SpawnerBehavior` and wilderness `cell_populate` respawn from prototype
   dicts, but nothing resets a whole area's canonical contents on a
   presence-gated schedule.
2. **Declarative reset language.** The `M/O/P/E/G/D/R/T` reset commands are a
   tiny placement DSL (put-in-container nesting, equip, door-state,
   randomize-exits). Worth adopting as area data.
3. **Quest-variable convention (`istagged`).** A blessed, queryable
   per-player key-value store for quest progress (`VARIABLE_DATA`,
   `get_tag`). REALM has open `db` attrs but no *convention* for quest
   state that triggers can rely on.

**Proven content-designs to mine (belong in a REALM pack):**

4. **The MOBprogram trigger-type checklist.** Not the interpreter — the
   *names*: `hitprcnt` (HP-threshold), `bribe`/`give`, `greet`/`all_greet`,
   `rand`/`time`/`hour`, `death`/`fight`. A ready-made list of the events a
   fantasy game wants `ON_<EVENT>` triggers for.
5. **`affect_data` as the timed-modifier shape.** `location`/`modifier`/
   `duration`/`bitvector`, ticked in the round loop — a clean, minimal buff
   primitive REALM's effect behaviors can mirror.
6. **Deity favor economy.** A favor scalar driven by a table of per-action
   deltas, with thresholds that unlock powers — a tidy reputation-system
   design, as pack data.
7. **Board-as-ballot.** Notes carrying vote tallies — a neat fusion of comms
   and governance.
8. **Corpse decay staging.** A timer that swaps progressively grislier
   descriptions before extraction, with PC/NPC rate asymmetry — a small,
   evocative pattern.

---

## Different philosophy

- **SMAUG is a game; REALM is an engine.** SMAUG ships Realms of Despair:
  fixed classes, THAC0 combat, deities, clans, housing. Its data files
  *configure* that game. REALM ships no game — the game is a composition.
- **Data-as-descriptor vs data-as-program.** Both are data-driven, but
  SMAUG's data is a **fixed-schema descriptor** whose behavior is compiled C
  bound by name (`dlsym`). REALM's data is **composable primitives +
  Turing-complete softcode** whose behavior *is* the data. SMAUG's skill file
  picks a C function; REALM's writes one.
- **40 named events vs one stream.** SMAUG enumerates every event its game
  cares about as a distinct `*_prog` type. REALM has one event stream and
  matches on it (`^listen`/`ON_<EVENT>`) — the events are game vocabulary,
  not engine surface.
- **Four object structs vs one GameObject.** SMAUG's room/mob/obj/exit are
  distinct C types; a vehicle or a door that acts like a person is
  inexpressible. REALM's tag+behavior `GameObject` is entity-agnostic by
  construction (invariant 7).
- **Recompile vs type-it-in.** New SMAUG behavior — a novel spell, a new
  spec-proc, a new command — means a C function and a rebuild. New REALM
  behavior is softcode a builder writes live. SMAUG's `dlsym` binding is the
  seam where it *wishes* it were data.

---

## Steal-list (ranked, honest)

Most of SMAUG's richness is **game content that belongs in a REALM pack**,
not the kernel. Ranked by value to REALM *as an engine*:

1. **Area-reset loop + declarative reset language** (`area_update`,
   `reset.c` `M/O/P/E/G/D/R/T`). The one clear **kernel-level primitive**
   SMAUG has and REALM lacks: scheduled, data-declared, presence-gated
   repopulation. Build it as a REALM mechanism.
2. **MOBprogram trigger-type vocabulary as a checklist.** Mine the ~40
   `*_prog` names to audit REALM's `ON_<EVENT>` coverage — especially
   `hitprcnt` (HP-threshold), `bribe`, `all_greet`, `time`/`hour` (scheduled
   ambient). Names, not code.
3. **`istagged` quest-variable convention.** A blessed per-player key-value
   store for quest state that triggers query — cheap, and it fills a real gap
   between REALM's open `db` attrs and a *convention* quests can rely on.
4. **`affect_data` timed-modifier shape** as the reference for effect
   behaviors: `location`/`modifier`/`duration`, ticked on the beat. Proven
   minimal buff primitive.
5. **`mpsleep` = `wait()` confirmation.** SMAUG independently arrived at
   cooperative yield-and-resume inside a trigger, saving the control stack.
   REALM's `wait()`/`prompt()` is the same idea, done better (real
   continuations vs a saved `if`-stack) — validation, not a port.
6. **Content designs as pack data** (deity favor economy, board-ballots,
   corpse-decay staging, clan roster). Steal the *field lists and formulas*;
   implement as composed primitives + softcode, never as C.

**What NOT to steal:** the 45-field `skill_type` mega-descriptor; the
`dlsym`-bind-behavior-by-name model (commands, spec-procs, spells); the four
fixed object structs; THAC0/AC combat as engine (reproduce as a pack); any of
the C subsystems (clans/deities/houses/weather) as *engine* features. These
are the anti-patterns REALM's invariants name explicitly.

---

## Verdict

- **World model:** SMAUG's `.are` + vnum + OLC is narrower than REALM's
  UUID/tag/attr `GameObject` — but its **timed area-reset loop and
  declarative reset language are a genuine primitive REALM lacks.** Build it.
- **Triggers:** SMAUG's MOBprograms are the `^listen`/`ON_<EVENT>` analog with
  a **fixed if/echo/force vocabulary, no loops, no local variables** (only
  `$`-codes, an `if`-stack, and persistent quest "tags"). REALM's
  Python-subset softcode is a strict superset; steal the *trigger-type names*
  and the `istagged` convention, not the interpreter.
- **Rules:** more data-driven than folklore says (classes/races/skills load
  from text), but the data is a **mega-descriptor** and the effect is
  **compiled C bound by `dlsym`** — the exact shape REALM's invariants 1, 3,
  and 6 forbid. Belongs in a GURPS/D20 pack.
- **Combat & social systems:** THAC0 rounds, clans, deities, housing, decay —
  decades-tested **game content in C.** Mine the field lists and formulas;
  implement as packs and softcode compositions, never as kernel.
- **Server model:** SmaugFUSS data-drives its command table and spec-proc
  whitelist (`commands.dat`/`specfuns.dat`, `dlsym`-bound) — the *table* is
  data, the *behavior* is C. REALM closes that seam: the behavior is softcode,
  so there is no C to bind.

The deepest sentence: **SMAUG bakes into C what REALM expresses as data —
and where SMAUG does use data, it is a rigid descriptor pointing at compiled
behavior, not a program.** REALM's payoff is that the game layer is a
*language*, not a configuration file for a fixed game.

*Status: reference survey, no decisions taken — captured for evaluation. The
one action item with kernel implications is the **area-reset primitive**
(steal #1). See also [PennMUSH Inventory](pennmush-inventory.md),
[LambdaMOO Comparison](moo-comparison.md), and [LDMud
Comparison](ldmud-comparison.md).*
