# SWFotE Force System vs REALM

A survey of **Star Wars: Future of the Empire** (SWFotE / "FotE") — a
C, SMAUG-1.4a-derived Star Wars codebase (SWR → SMAUG lineage, ~54 `.c`
in `~/SWFOTEFUSS/src/`) — with emphasis on its signature subsystem, the
**Force powers** engine, plus its **empire/faction** machinery (clans +
planetary control). Mapped onto what REALM has, is missing, or covers
differently. Pulled from `force.c` (the Force runtime), `fskills.c` (the
21 hardcoded power bodies), `finfo.c` (the data-file loader + string→function
dispatch), `mud.h` (the structs), and `planets.c` / `clans.c` (factions).
A **sister review covers FotE's space/ship layer** — this doc stays on the
Force and faction systems and only gestures at the shared SMAUG/space
machinery.

The headline framing, before the detail: **FotE's Force is a *hybrid*
system — a data-registered ability catalog bolted onto hardcoded C effect
functions.** Each power's *metadata* (cost, stat requirements, rank gate,
alignment class, the five room/victim/self message strings) lives in a flat
key/value file under `../force/` and is hot-editable in-game via `fset`
(`force.c:625`) — that half is genuinely data-driven. But each power's
*effect* is a compiled `void fskill_x(CHAR_DATA*, char*)` function in
`fskills.c`, bound to its data record by a **string→function-pointer switch**
(`get_force_skill_function`, `finfo.c:402`), and the character's proficiency
in it is stored in a **fixed-size array indexed by a hardcoded enum**
(`force_skill[MAX_FORCE_SKILL]`, `mud.h:2611`; enum at `mud.h:330`). So you
can add a *message* or retune a *cost* without recompiling, but you cannot
add a *new power* — a new effect, a new proficiency slot — without editing C.

**REALM would express the Force as a PACK.** REALM's abilities/skills are
DATA (`skill_def`/`class_def` in importable packs); a power's *effect*
composes from genre-neutral dice PRIMITIVES through the entity-agnostic
resolver (`GameSystem.resolve_rule`), so there is no C function to bind and
no fixed enum slot to allocate. FotE's `ITEM_ANTI_JEDI` flag
(`handler.c:2861`) — an item that suppresses Force use — is in REALM just a
**ward whose `on_check` masks the `magic` action-category tag**
(`has_atag('magic')`); "anti-Force field" and "anti-magic field" are the
same primitive under a different genre label. The Force lore is content; the
mechanisms underneath (a bipolar alignment track, a regenerating pool, a
rank-gated ability graph) are the reusable parts.

---

## Part 1 — The Force ability model

### How a power is declared and stored

A power is a `FORCE_SKILL` record (`mud.h:359`), loaded at boot from one
file per skill under `FORCE_DIR` (`../force/`, `mud.h:4756`) via
`load_force_skills` → `fread_forceskill` (`finfo.c:368`, `:239`). The record
carries:

| Field | Meaning | REALM home |
|---|---|---|
| `name` | command word (`lightning`, `heal`, …) | `skill_def.name` |
| `type` | alignment class: `GENERAL` / `JEDI` / `SITH` (`mud.h:350`) | pack tag / `atag` |
| `index` | **slot into `force_skill[]` — must match a compiled enum** | — (REALM has no fixed slot) |
| `control` / `sense` / `alter` | which innate stats gate + power it | `skill_def` attr refs |
| `cost` | **`mana`** deducted per use | resource-pool cost (data) |
| `status` | rank gate: `APPRENTICE`/`KNIGHT`/`MASTER` (`mud.h:345`) | prereq predicate (data) |
| `wait_state` | cooldown / round-lock | beat cost / cooldown |
| `code` | **string naming the C effect fn** (`"fskill_lightning"`) | — (no analog needed) |
| `ch_effect[5]`, `victim_effect[5]`, `room_effect[5]` | staged message strings | `add_message` templates |
| `do_fun` | resolved function pointer | — |

The `code` string is the load-bearing hack: `check_force_skill`
(`force.c:80`) matches the typed command to a record, then
`get_force_skill_function(fskill->code)` (`finfo.c:402`) runs a hand-written
`switch` on `name[7]` to return one of 21 `fskill_*` pointers, else
`skill_notfound`. **This is the seam that makes it "not fully data-driven":
the catalog is data, the behaviors are an enumerated, closed set of compiled
functions.**

### How an effect resolves

Every power body follows the same SMAUG idiom (see
`fskill_force_lightning`, `fskills.c:1153`):

1. `force_test_skill_use(name, ch, COMBAT|NONCOMBAT|NORESTRICT)`
   (`force.c:302`) — the universal gate: verifies the caster is
   Force-identified, meets the rank `status`, knows the skill
   (`force_skill[index] > 0`), isn't on cooldown, and **can pay the `mana`
   cost** — then deducts mana and, if the power is off-alignment for the
   caster, shifts `force_align` (see below).
2. Effect resolves via **raw `number_range()` rolls** scaled by the caster's
   three innate stats — e.g. lightning damage is
   `number_range(50, (force_alter*2 + force_sense*2 + force_control*2))`
   (`fskills.c:1204`); the hit/miss check is
   `number_range(0,100) > force_skill[index]` (`fskills.c:1190`). There is
   **no shared resolver** — each function open-codes its own dice and
   thresholds.
3. Staged over game pulses via `add_timer(ch, TIMER_DO_FUN, …)` — a wind-up
   message, then a resolution beat, with a `SUB_TIMER_DO_ABORT` path if
   interrupted.
4. On resolve, `force_learn_from_success` / `_from_failure` (`force.c:270`,
   `:238`) nudge `force_skill[index]` upward — **use-based skill improvement**
   (classic SMAUG), amount scaled by innate stats and a master-training
   multiplier.

### Resource pool, alignment, and progression

- **Pool:** powers spend **`mana`** (`ch->mana`, `mud.h:2626`), regenerated
  every tick by `mana_gain()` (`update.c:1663`, capped at `max_mana`). It is
  the generic SMAUG mana bar re-skinned as Force energy — not a bespoke pool.
- **Alignment — two independent tracks.** FotE keeps the base SMAUG
  `alignment` (−1000..1000 good/evil, `mud.h:2464`) **and** adds a *second*,
  Force-specific **`force_align` (−100..100 light↔dark**, `mud.h:2618`;
  bounds `MAX/MIN_FORCE_ALIGN`, `mud.h:385`). Using an off-type power shifts
  `force_align` toward that pole (`force.c:377-388`: a Jedi using a Sith
  power loses 1–5 light). `update_force()` (`force.c:396`, on
  `PULSE_FORCE`/minute) drifts `force_align` toward the caster's declared
  `force_type`, **and decays off-alignment proficiencies** — a Jedi who
  drifts dark watches Jedi skills erode (`force.c:462`). This bipolar,
  self-correcting track is the mechanically interesting part.
- **Progression** is three stacked ladders:
  1. **Discovery/latency:** a character is inert until *another* Force user
     `sense`s them (`fskill_identify`, `fskills.c:419`), which rolls their
     hidden potential (`force_chance`/`perm_frc`) into the three innate stats
     `force_control` / `force_alter` / `force_sense` (0–100) and sets
     `force_identified` (`fskills.c:467-475`). You cannot self-start.
  2. **Per-power skill:** `force_skill[index]` 0–100, raised by use.
  3. **Rank:** `force_level_status` None→Apprentice→Knight→Master
     (`mud.h:345`), gated by `force_promote_ready` (avg skill at your tier
     ≥ 50, `force.c:490`) and conferred by a master (`fskill_promote`,
     `fskills.c:526`); the master/apprentice bond is a name string
     `force_master` (`mud.h:2621`). So progression is a **prerequisite graph**
     — rank gates which powers `force_test_skill_use` will run.

### Is it hardcoded or table-driven? — the verdict

**Hybrid, leaning hardcoded.** Data-driven surface: the power *catalog*,
costs, gates, and messages are files under `../force/`, live-editable via
`fset` (`force.c:625`) / `fhset` (help entries, `force.c:1302`). Hardcoded
core: the *effects* (`fskills.c`, closed set of 21), the string→pointer
dispatch (`finfo.c:402`), the proficiency **enum + fixed array**
(`mud.h:330`, `:2611`), the `mana` pool, and the alignment-drift rules
(`force.c:396`) are all compiled C. Adding a power means editing three C
sites (enum, dispatch switch, new `fskill_` body) plus a data file — exactly
the coupling REALM's pack model dissolves.

---

## Part 2 — Empire / faction control

FotE's "empire" layer is **clans governing planets**, tracked by simple
counters — no per-player reputation ledger.

| FotE mechanism | Where | What it does | REALM analog |
|---|---|---|---|
| **Clan** (`CLAN_DATA`, `mud.h:1103`) | `clans.c` | faction: leader/officers, members, funds, `atwar` target, military assets (`troops`/`vehicles`/`spacecraft`), guard/patrol mob vnums, subclans | data-defined faction entity (pack) |
| **Clan type** (`mud.h:894`) | — | `PLAIN`/`CRIME`/`GUILD`/`SUBCLAN`/`CORPORATION` — gates capability (crime/guild clans *can't* capture planets, `planets.c:751`) | faction-kind tag |
| **Membership** | `pcdata->clan_name` (`mud.h:2746`) | single-clan belonging; officer slots are name strings, not a rank enum | disposition / affiliation attr |
| **Territory** (`PLANET_DATA`, `mud.h:929`) | `planets.c` | `governed_by` = controlling clan; planets carry `population`, `pop_support` (float loyalty), `controls` | world-region ownership attr |
| **Planetary loyalty** | `pop_support` (`planets.c:210`) | float 0–100 per planet; capturing requires the current owner's support to have decayed to ≤ 0 and the aggregate support across *your* planets ≥ 0 (`planets.c:789-808`) | resource/standing attr |
| **Capture** | `planets.c:740` | flips `governed_by`, resets support to 50; blocked by orbiting friendly ships, planetary guards, or "Neutral" status | scripted region event |
| **Faction combat score** | `pkills`/`pdeaths`/`mkills`/`mdeaths` (`mud.h:1120`) | crude clan-vs-clan tally | log-derived stat |

Two things stand out. (1) **Territory is a first-class, capturable resource
with a loyalty economy** (`pop_support`) — planets flip only when loyalty is
ground down and the aggressor has spare support to spend; this is a genuine
strategic layer, not just a flag. (2) There is **no personal faction
reputation** — a character's standing *is* their clan membership plus their
Force alignment; FotE has nothing like a per-faction favor score. REALM's
**DISPOSITION** system (per-observer NPC reaction/standing) is actually
*richer* on the personal axis than anything FotE ships.

*(Shared SMAUG/space machinery — clans, ship combat, planets-in-starsystems,
the space grid — overlaps heavily with base SWR and is covered in the sister
space review; not re-audited here.)*

---

## Part 3 — What FotE adds over base SMAUG

Briefly, since most of the codebase *is* SMAUG 1.4a: (1) the **Force system**
(`force.c` + `fskills.c` + `finfo.c` + the `../force/` data dir) — entirely
FotE/SWR; (2) the **bipolar `force_align` track** distinct from SMAUG
`alignment`; (3) **planetary control with a loyalty economy** (`planets.c`);
(4) Star Wars re-skins of stock systems — `mana`→Force energy, spells→Force
powers, the `ITEM_ANTI_JEDI`/`ACT_JEDI`/`ACT_SITH` flags. The space/ship
layer, `swskills.c`, and `tech.c` are the sister review's domain.

---

## Capabilities REALM lacks (worth noting)

Assessed against REALM's stated model (data-pack abilities, entity-agnostic
resolver, action-category-tag wards, disposition, beat-driven combat,
attributes on `GameObject.db`):

| FotE capability | REALM today | Verdict |
|---|---|---|
| **Bipolar alignment track** (`force_align`, −100..100, self-correcting) | disposition is *per-observer standing*, not a *self* bipolar axis; no karma/morality track | ✗ **gap — needs a small kernel/pack primitive** |
| **Alignment-driven skill decay** (drift dark → Jedi skills erode, `force.c:462`) | no periodic "attribute decays toward a pole" driver | ✗ gap (a tick-script could do it, but there's no convention) |
| **Regenerating resource pool** (`mana`/`mana_gain`, tick-based) | attributes on `db`; no *generic* regenerating-pool-with-cap primitive or tick-regen convention | ◑ partial — expressible as a script, but no first-class pool |
| **Ability prerequisite graph** (rank gates which powers run) | `skill_def` can hold prereq data, but is there a resolver-checked prereq predicate? | ◑ **partial — data can express it; confirm the resolver enforces prereqs** |
| **Latent/discovery gating** (power dormant until sensed by another) | no "ability unlocked by another actor's action" convention | ◑ partial (scriptable via events) |
| **Use-based skill improvement** (success/failure nudges proficiency) | resolver returns outcomes; a "learn on use" hook would need wiring | ◑ partial |
| **Territory with a loyalty economy** (capturable planets, `pop_support`) | region ownership + a numeric loyalty attr; capture is a scripted event | ● expressible in a pack |
| **Staged multi-beat powers** (wind-up → resolve → abort path) | **beat-driven combat is a native strength** | ● have — cleaner than `add_timer` |
| **Anti-Force field** (`ITEM_ANTI_JEDI`) | **`has_atag('magic')` ward `on_check`** | ● have — the category-tag ward *is* this, genre-neutral |
| **Genre-neutral effect resolution** | **`GameSystem.resolve_rule` + dice primitives** | ● **REALM wins** — FotE open-codes `number_range` per power |

The pattern: everything **content-shaped** (the catalog, costs, messages,
gates, territory) maps cleanly onto REALM **packs**. The genuine gaps are a
few **self-state mechanisms** that FotE happens to have and REALM has not yet
named: a **bipolar self-alignment axis**, a **regenerating capped pool with a
tick driver**, and a **resolver-enforced ability-prerequisite check**. None
are large, but they are kernel/convention-level, not pure pack data.

---

## Steal-list (ranked) — mechanism vs genre content

Distinguishing the reusable **mechanism** (worth lifting into the kernel or a
reference pack) from the **genre content** (belongs in a Star Wars pack, if
ever):

1. **Bipolar alignment track** *(mechanism)* — a bounded, self-correcting
   `−N..+N` axis that (a) shifts on tagged actions and (b) drifts toward a
   declared allegiance each tick. This is the single most reusable idea here:
   light/dark, law/chaos, honor/corruption, Sith/Jedi are all one primitive.
   REALM lacks a *self* morality axis (disposition is other-facing). Candidate
   for a small kernel attribute + a "shift on action-category" hook.
2. **Regenerating capped resource pool + tick driver** *(mechanism)* — FotE's
   `mana`/`mana_gain` is generic; formalize a pack-declarable pool
   (`max`, `regen_per_beat`, `cost` refs from `skill_def`) so mana / stamina /
   Force / spell-slots are one data shape. Currently only ad-hoc on `db`.
3. **Resolver-enforced ability prerequisite graph** *(mechanism)* — FotE's
   rank→power gate (`status` vs `force_level_status`) is a prereq predicate
   the runtime checks before executing. Make `skill_def` prereqs (rank, other
   skills, attribute floors) a **declarative predicate the resolver
   evaluates**, so ability trees are data.
4. **"Learn on use" improvement hook** *(mechanism)* — a post-resolution hook
   that nudges a proficiency on success/failure, so use-based advancement is a
   pack option, not per-ability C.
5. **Territory with a loyalty economy** *(mechanism, lighter)* — capturable
   regions gated by a decaying loyalty scalar + an aggregate-support spend
   rule. A nice reference pack for faction-warfare games.
6. **Latent-ability discovery** *(mechanism, niche)* — an ability that stays
   dormant until another actor's action reveals it; scriptable today, but a
   named convention would help.
7. **The Force lore itself** *(genre content)* — powers (lightning, heal,
   lightsaber construction), the Jedi/Sith duality, `ITEM_ANTI_JEDI`, the
   message strings: **pure pack content.** Do not lift; it's the example a
   Star Wars pack would ship *using* mechanisms 1–4.

Explicitly **not worth stealing:** the `code`-string→function-pointer
`switch` (`finfo.c:402`) and the fixed `force_skill[]` enum array — these are
the C-language workarounds REALM's data-pack + resolver model exists to
delete.

---

## Verdict

- **Force = hybrid, mostly hardcoded.** Data-driven catalog (`../force/`,
  live-editable) over a closed set of 21 compiled effect functions bound by a
  string switch, with proficiency in a fixed enum-indexed array. REALM's
  pack + entity-agnostic resolver would make the *whole* thing data,
  including new powers.
- **The anti-Force field is already REALM's category-tag ward** —
  `ITEM_ANTI_JEDI` ≡ `has_atag('magic')` `on_check`. No work needed.
- **Real gaps are three self-state mechanisms:** a **bipolar self-alignment
  track**, a **regenerating capped resource pool with a tick driver**, and a
  **resolver-enforced ability-prerequisite predicate**. All small, all
  kernel/convention-level, all directly motivated by making a Force-style
  pack expressible without kernel edits.
- **Factions:** clans-govern-planets with a **planetary loyalty economy** is a
  genuinely interesting territory mechanic (worth a reference pack); but FotE
  has **no personal faction reputation** — REALM's disposition system already
  exceeds it on that axis.

*Status: reference survey, no decisions taken — captured for evaluation.
Sister review covers FotE space/ships. See also
[PennMUSH Softcode Inventory](pennmush-inventory.md).*
