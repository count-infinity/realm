# Skills: Model, Master List & Progression

A survey of every reference architecture's skill system (2026-08-02,
refined 2026-08-02), synthesized into **a model** — how skills stay
genre-neutral, how they deepen, and how they grow — plus the tagged
master list that the fantasy pack ships.

**Sources surveyed:** CoffeeMud (~170 artisan + ~190 thief + fighter/general
skills; the motherlode), SMAUG (86 skills + 7 weapon groups + 11 tongues),
tbaMUD (11 — the Diku floor), SWR (space/technical/crafting + 8 career
classes), AresMUSH FS3 (taxonomy + specialties), AwakeMUD (~155 Shadowrun
skills — the modern/social vocabulary), GoMud (15 tags + emergent
professions), DikuMUD3/VME (75 skills + a 72-entry weapon tree with
category defaulting), Solar Frontiers' own GURPS data (~100 skills), and —
added in the refinement — EVE Online (real-time queue training) and Melvor
Idle / RuneScape (per-skill use levels + per-target mastery).
Per-source highlights are in the appendix.

## What this document decides

Three axes that the first draft conflated. They are independent: a game
picks one answer from each, and REALM must not assume any of them.

| Axis | Question | Owner |
|---|---|---|
| **1. Vocabulary** | *Which* skills exist, and what are they called? | the game's content pack (genre) |
| **2. Structure** | How does a skill deepen into specifics? | the data (`skill_def` tree) |
| **3. Progression** | How does a number go up? | the system **and** the individual skill |

The thesis: **one dataset, three exposures.** The same `skill_def` tree
serves a 100-skill GURPS game (specializations exposed as first-class
skills), a 20-skill idler (spine skills are the grind tracks;
specializations become per-target mastery), and a Diku game (a flat
practiced subset) — because breadth-vs-depth is a *presentation and
progression* choice, not a content choice.

---

# Axis 1 — Genre neutrality

## The problem: the engine names skills

REALM already stores skills as data (`skill_def` objects, merged over a
system's built-ins) — but engine code still rolls **literal skill names**:

| Site | Hardcoded |
|---|---|
| [manipulation.py:206](realm/commands/builtin/manipulation.py#L206) | `lockpicking` (with `db.lock_skill` as a per-object override — the good precedent) |
| [manipulation.py:422-465](realm/commands/builtin/manipulation.py#L422-L465) | `stealth`, `observation` (sneak / hide / search) |
| [social.py:91](realm/commands/builtin/social.py#L91) | `persuasion` vs `will` |
| [checks.py:29](realm/core/checks.py#L29) | `flee` (already declared as the engine floor) |
| [describe.py](realm/core/describe.py), OLC `@detail` | `check('observation', -2)` as the documented idiom |

So a cyberpunk game that calls it *infiltration*, or a starship game that
calls it *EVA discipline*, has to either adopt fantasy vocabulary or fork
the commands. Behaviors got this right already —
[npc.py:62](realm/behaviors/npc.py#L62) exposes `perception` as a
**parameter** defaulting to `observation`. Commands should too.

> **Superseded in part (2026-08-04):** the plan in
> [Bare Kernel & Feature Packs](bare-kernel-and-packs.md) moves the stock
> skill commands *out of the kernel into feature packs*, which demotes
> the roles table below from a kernel concept to **per-pack
> configuration** (each pack's commands read their skill from the target
> attr → pack config → pack default). Only `flee` stays engine-floor.
> The resolution-order rule and the "attempts are actions" principle
> below stand unchanged — they just live in the packs now.

## Skill roles: the engine's entire skill vocabulary

A **role** is an engine-facing slot; a **skill** is a game-facing name.
The engine rolls roles and never sees a skill name. The closed list is
deliberately tiny — it contains only what engine code itself rolls:

| Role | Rolled by | Default binding |
|---|---|---|
| `flee` | combat disengage | `flee` |
| `sneak` | sneak/hide, stealth observer | `stealth` |
| `perceive` | search, `@detail` gates, NPC spotting | `observation` |
| `bypass_lock` | `pick` | `lockpicking` |
| `persuade` | social commands | `persuasion` |
| `resist_social` | the opposed side of the above | `will` |

Resolution order, widest override first (mirroring `db.lock_skill`):

```text
target object override  (db.lock_skill / db.check_skill)
  -> GameSystem.skill_roles()   { "perceive": "sensors", "sneak": "ghosting" }
    -> the default binding above
```

Two properties fall out. **Nothing breaks**: the default bindings are
today's literals, so an unconfigured game behaves identically. And **a
game can rebind without renaming** — a hard sci-fi game maps `perceive ->
sensors` and every stock command, `@detail` gate, and NPC behavior starts
rolling sensors.

Everything *not* in that table is content. `smithing` is not an engine
concern; the command that uses it lives in a pack.

**The rule that keeps this from being a second thing to memorize** (a
builder never asks "does this skill tie into the kernel?"):

> **The target names the skill; a role is only the fallback when the
> target doesn't; everything else is pure content.**

`db.lock_skill` on the vault beats the role binding beats the default. A
game that never touches roles still works; roles only matter on the day a
game wants the *stock commands'* defaults to speak its genre's vocabulary.
A game that skips the stock commands entirely (a social MU* registering
its own verbs) never meets the roles at all.

## Attempts are actions (the pick principle)

The heart of REALM is that everything is an action event and things react
to events — and the stock skill commands must obey that model rather than
sit beside it. `pick` is the worked example, because it is already
*half*-converted:

What [`cmd_pick`](realm/commands/builtin/manipulation.py#L185) does today:

1. Reads `lock_skill` / `lock_difficulty` **off the target** — the lock
   names its own rule; the command carries none.
2. Rolls `check()`.
3. On success, fires a **gated `ON_UNLOCK` action** (`picked: True`) —
   wards can veto a picked lock, `ON_UNLOCK` softcode hears it (alarms,
   mirrors), scripts can tell a jimmy from a key.

So the kernel content of `pick` is ~zero: the command is arg parsing, a
tool check, and messages — sugar over primitives that are all
softcode-reachable today (`$command` fallback + `check_roll()` + tags +
gated events). A builder could write a bespoke `$pick *` on one strange
lock with no engine change. The builtins exist as batteries, not as the
mechanism.

**The gap: failure is dead air.** On success the world hears the action;
on failure the player gets a message and *nothing propagates* — so a trap
on a failed pick, an alarm after three attempts, a guard hearing the
scrape, a fumble that jams the lock are all unbuildable against the stock
command. PennMUSH's `@fail`/`@ofail`/`@afail` verb attributes solved this
in 1991; REALM already conceded the point for movement (`event:on_fail`
carries a `reason`). The fix generalizes:

> **The *attempt* is the action, and both outcomes propagate.** The
> action carries the `CheckResult` (margin included, so a −1 miss and a
> −10 fumble are distinguishable). Success applies and fires the success
> event; failure propagates *unapplied* so `ON_<VERB>_FAIL` hooks hear
> it. This is not a new kernel concept — it is the existing gated-event
> helper learning to fire on the "no" branch too.

Convert `pick` first, then the same treatment for sneak, search, and
persuade. tbaMUD's wrong-way tracking and CoffeeMud's trapped locks (both
on the fun list) are this exact mechanism.

**Three shapes, one pattern.** REALM now has three levels of canning for
"verb → gate → check → effects": builtin command sugar, `$command`
softcode, and [`ability_def`](realm/systems/abilities.py) (`invoke → gate
→ propagate → apply effect-specs`). They are the same shape at different
levels of packaging — a future `pick` could literally be an ability_def.
Don't unify them yet; do require every *new* skill verb to follow the
shape (skill from the target, attempt as an action, both outcomes
propagated) instead of inventing a fourth.

## The spine: capability slots every genre has

Below the roles, a **spine** of ~35 capability slots. A slot is a
*capability* ("extract raw material from the world"), not a name — so the
genre columns are skins over the same slot, and a pack author's job is
naming and specializing, not re-deriving the taxonomy.

| Slot (capability) | Tag | Fantasy | Modern / noir | Sci-fi |
|---|---|---|---|---|
| strike in reach | combat, weapon | melee | knife fighting | vibroblade |
| strike at range | combat, weapon | archery | firearms | energy weapons |
| throw a thing | combat, weapon | thrown | thrown | thrown |
| fight without a weapon | combat, weapon | brawling | boxing | martial arts |
| avoid being hit | combat, passive | dodge | dodge | evasion |
| use protective gear | combat, passive | shields | cover use | deflector drill |
| read a fight | combat, lore | tactics | tactics | fleet tactics |
| move unseen | stealth | stealth | prowling | silent running |
| take what isn't yours | larceny | larceny | theft | lifting |
| open what's shut | larceny | lockpicking | safecracking | slicing |
| find/defeat devices | larceny, perception | traps | demolitions | countermeasures |
| look like someone else | deception | disguise | disguise | ident-masking |
| falsify a record | deception, craft | forgery | counterfeiting | data-forgery |
| notice | perception, passive | observation | perception | sensor read |
| search a scene | perception | investigation | investigation | forensics |
| follow a trail | perception, survival | tracking | shadowing | signature-tracing |
| talk someone round | social | persuasion | negotiation | negotiation |
| make someone afraid | social | intimidation | intimidation | intimidation |
| make someone believe a lie | social, deception | deception | con | con |
| make people follow | social | leadership | command | command |
| know how to behave here | social, lore | etiquette | streetwise | protocol |
| entertain | performance | performance | performance | performance |
| make a thing from materials | craft | smithing… | machining | fabrication |
| extract raw material | gather | mining… | scavenging | ore-harvesting |
| feed people | craft, survival | cooking | cooking | galley |
| mix reactive substances | craft, magic | alchemy | chemistry | xenochem |
| repair and maintain | craft, lore | engineering | mechanics | tech |
| keep a body working | medicine | medicine | trauma care | med-bay |
| live off the land | survival | survival | urban survival | xeno-survival |
| find your way | survival, lore | navigation | navigation | astrogation |
| move your body well | movement | athletics | athletics | zero-g drill |
| operate a mount/vehicle | animal / vehicle | riding | driving | piloting |
| handle non-people creatures | animal | animal handling | animal handling | xenobiology |
| know a body of facts | lore | lore | research | xenology |
| value and trade | trade | appraisal, trading | appraisal, trading | brokerage |
| speak to strangers | language | tongues | languages | xenolinguistics |
| **the exotic power** | magic | magic, spellcraft | the occult | psionics / the Force |

Two notes that matter more than they look:

- **"operate a mount/vehicle" is one slot.** Riding, driving, and piloting
  are the same capability against different vehicles — which makes them
  natural *specializations* of one spine skill, not three skills. SWR's
  per-ship-class piloting and AwakeMUD's per-chassis pilot+repair pairs
  are both this slot with a deep spec tree.
- **"the exotic power" is one slot.** Every genre has exactly one and
  calls it something different. Games with none simply omit it.

## Modules: opt-in genre groups

Anything not universal is a **module** a pack imports — not a spine
member, so no game carries dead vocabulary:

`firearms & explosives` · `vehicles & piloting` · `starship ops` (sensors,
gunnery, shields, astrogation — [already shipped in the `gurps-scifi`
pack](realm/packs/gurps-scifi/skills.json)) · `computers & networks`
(intrusion, cryptography, drone ops) · `magic` (spellcraft, meditation,
ritual) · `psionics` · `sail & sea` · `bureaucracy & corporate`.

## So what is the master list?

The 62-skill list further down is **the fantasy/adventure pack** — the
spine, skinned fantasy, with its specialization seeds. It is content, not
the model. A sci-fi pack skins the same spine differently and imports
different modules.

---

# Axis 2 — Depth: specialization

Every reference solves "get better -> get more specific" one of three ways:

1. **Vertical tiers as separate skills** — CoffeeMud's `Mining ->
   MasterMining -> Legendary*`; VME's weapon tree (leaf weapons default to
   their category parent); SMAUG's second/third/fourth attack chain.
2. **Horizontal expertises on one skill** — CoffeeMud's data-driven ladders
   (`Stealthy I-X`: one text line = ten stages, each with stat/level gates
   and costs, modifying one declared axis).
3. **Specialty labels on one rating** — FS3 (Medicine -> Surgeon):
   qualification markers, mechanically inert by design.

**REALM's model: vertical, as data — riding the existing `@parent` chain.**

The first draft proposed a `parent` *attr* on `skill_def`. That collides
with `GameObject.parent`, which is REALM's real attribute-inheritance
field ([objects.py:187](realm/core/objects.py#L187)). Use the real one
instead — it is the same relation, and it pays for itself:

```text
@create skill_def "mining unobtainium"
@parent mining unobtainium = mining   # the specialization link
@set mining unobtainium/requires = mining:60
# stat and penalty are INHERITED from mining — no need to restate them
```

- `db.get` already falls through the `@parent` chain
  ([objects.py:99](realm/core/objects.py#L99)), so a spec inherits `stat`
  and `penalty` for free and can shadow either locally when it governs
  differently (underwater work is HT, not ST).
- **Top-level skills train normally** — a pack ships spine skills first;
  specs are later content.
- **`requires` replaces `unlocks_at`.** A list of `skill:level`
  prerequisites is strictly more general than a single parent threshold,
  and it is exactly EVE's prerequisite graph — needed anyway for Axis 3's
  idle model. `requires = mining:60` is the common case; `requires =
  [piloting:40, sensors:30]` is the one `unlocks_at` couldn't express.
- Until its prereqs are met a spec is **hidden** (SMAUG's `SF_SECRETSKILL`
  pattern) — which also gives quest-taught skills free: a def with no
  parent, `hidden`, revealed by a quest.
- **Checks default upward.** Rolling an untrained spec falls back to the
  parent's level at a penalty (the GURPS default idiom; AwakeMUD's
  `DEFAULT_TO` chain; VME's leaf->category weapon defaulting). Knowing
  `mining` 70 means attempting unobtainium at 70-40 — hard, not impossible.
  Walk the chain, so a three-deep tree degrades gracefully.
- `skill_def`s are ordinary objects, so **grouping tags cost nothing**:
  `tags = [skill_def, gather]`.

**Specializations double as mastery tracks.** Melvor Idle's per-ore
mastery (each ore levels separately inside Mining) is structurally
identical to `mining unobtainium` under `mining`. A use-progression game
awards XP to *both* the spec and its parent (see Axis 3) and gets
RuneScape-shaped mastery out of the same tree a GURPS game reads as
"Mining (Unobtainium)". This is the single strongest argument for the
tree: it is the only structure that serves both readings.

Rejected for now: expertise ladders (model 2) — powerful but a second
currency; revisit if vertical specs feel flat. FS3 labels can ride along
later as pure flavor.

## Tag taxonomy

One primary group tag per skill; cross-cutting tags freely added.

| Tag | Meaning |
|---|---|
| `combat` | used in or around a fight |
| `weapon` | governs attacks with a weapon family |
| `stealth` | not being noticed |
| `larceny` | taking what isn't yours |
| `deception` | making someone believe wrongly |
| `perception` | noticing, finding, following |
| `social` | moving people with words |
| `performance` | audience-facing art |
| `craft` | making things (artisan) |
| `gather` | extracting raw materials |
| `animal` | beasts: taming, riding, husbandry |
| `survival` | living off the land |
| `medicine` | keeping bodies working |
| `movement` | athletics of all kinds |
| `lore` | knowing things |
| `language` | tongues |
| `trade` | buying, selling, valuing |
| `magic` | system-specific casting-adjacent |
| `passive` | consulted by the engine, not commanded |

---

# Axis 3 — Progression

Four models, all real, all shipped by some reference. REALM must support
each **and their mixture**, because the reference game wants three at once.

| Model | Reference | Currency | Earned by | Spent by | Works offline |
|---|---|---|---|---|---|
| **Point-buy** | GURPS, D20 — *shipped* | `character_points` | kills, quests, session awards | `improve <skill>` | n/a |
| **Trainer practice** | Diku/merc — *partly shipped* | `practices` + coin | leveling | a guildmaster NPC | n/a |
| **Use** | SMAUG, RuneScape/Melvor, UO | `skill_xp_<name>` | doing the thing | automatic | **no** — presence required |
| **Idle queue** | EVE Online | `sp_<name>` over wall-clock seconds | *time itself* | queue order | **yes** |

What REALM has today: point-buy end to end (`grant_award` ->
`character_points` -> [`improve`](realm/commands/builtin/combat.py#L492) at
`improve_cost` per level), and merc's `practices` counter with no
`practice` command to spend it. Use and idle are unbuilt.

**Teaching is not a fifth model** — the player-to-player training in the
fun list is an *award source* that feeds whichever model is active.

## Mixing: progression is a property of the skill

The decisive refinement. If progression lives only on the `GameSystem`, a
game gets exactly one model. Put it on the `skill_def`, defaulting to the
system's choice, and a single game runs all four:

```text
@set smithing/progression   = use      # grind it, Melvor-style
@set xenolinguistics/progression = idle  # study it, EVE-style
@set tactics/progression    = points   # buy it, GURPS-style
# unset -> GameSystem.default_progression
```

Each model owns its own attributes and never contends with another:

| Model | Attributes on the character |
|---|---|
| points | `character_points` (shared pool) |
| practice | `practices` (shared pool) |
| use | `skill_xp_<name>` (per skill) |
| idle | `sp_<name>`, `training_queue`, `training_since` |

**Invariant that keeps the check path fast:** whatever the model, it
writes the plain `skill_<name>` level when a threshold is crossed.
`skill_level()` stays a dumb attribute read
([checks.py:54](realm/core/checks.py#L54)), so every ruleset, softcode
`skill()` binding, and score screen works unchanged across all four
models. XP and SP are *bookkeeping behind* the level, never a second thing
the resolver must know about.

## The seams to build

**1. A use hook on `check()`.** One call at the end of
[`check()`](realm/core/checks.py#L203):

```python
system.on_skill_used(obj, result)   # default: no-op
```

That is the whole learn-by-use mechanism — `check()` is the single funnel
every skill roll passes through. **Constraint:** `check()` is
*synchronous*, so this must be a sync callback, not an action dispatch —
learn-by-use cannot be an `ON_<EVENT>` hook. For a data-driven route, mirror
`resolve_rule` with a `progress_rule` softcode expression, so a builder can
author the award curve in-game the way they already author resolution.

SMAUG's hybrid is the default worth shipping: practice carries a skill to a
floor (~20% of cap), learn-by-use takes it from there, +1-2% per success,
with a celebration award at mastery. Award the specialization *and* the
parent (parent at a fraction) so mastery tracks and broad skill rise
together.

**2. Idle training needs no ticks.** Store `training_since` (a timestamp)
and compute accrued SP lazily on read — at login, on `score`/`skills`, on
any check of that skill, and on a coarse reaper sweep for
"training complete" notifications. This is **offline-correct by
construction** and costs nothing while the player is away — a much better
fit than adding a per-second timer to
[the heartbeat](docs/design/time-and-beats.md). EVE's rate shape
(`primary_attr + secondary_attr/2` SP per minute, skill `rank` as a cost
multiplier, five levels on an exponential curve) is worth copying whole;
`requires` (Axis 2) is already the prerequisite graph.

**3. Caps.** Point-buy is self-limiting (CP are scarce); use and idle are
not. A per-system `skill_cap(actor, skill)` covering the three shapes the
references use: a hard cap (Melvor 99), a class/level cap (SMAUG's percent
of class max), and a chargen pyramid (FS3). Diminishing XP returns near the
cap is the gentler variant.

**4. The idle-action loop (Melvor's actual grind).** A repeating timed
action: while active, every N beats -> roll a check -> award XP -> roll a
drop table -> consume a consumable. This is a **behavior**, not engine —
it is SWR's `make*` shape and CoffeeMud's `CommonSkill` shape, and REALM
already has beats, behaviors, and timed actions to build it from.
Policy knob to decide per game: whether an interrupted/logged-out player
banks offline action progress (RuneScape idlers do, capped at N hours) or
whether only *training* is offline-eligible. Default: training accrues
offline, actions do not.

## The reference game, concretely

GURPS adaptability + Melvor grind, as one config:

- **Chassis**: GURPS — 3d6 roll-under (`resolve_rule` already expresses
  it), attribute defaults, `@parent` defaulting for untrained specs.
- **Craft & gather skills** (`progression = use`): the Melvor loop. Spine
  skill levels broadly; each node/recipe is a specialization that levels as
  its own mastery track and unlocks better yields at thresholds.
- **Study skills** — lore, languages, theory (`progression = idle`): the
  EVE queue. Breadth accrues while you are away; depth requires showing up.
  This is the right split for a small-population MUD: presence is rewarded,
  absence isn't punished.
- **Combat & social** (`progression = points`): CP from kills and quests,
  spent with `improve` — so the sharp end of the game stays a deliberate
  build choice, not a grind.
- **Curve mapping**: a use/idle skill's XP curve must land on the *game's*
  scale, not RuneScape's — under a GURPS chassis, skill 14 is an expert and
  20 is world-class, so the curve is steep and short. `xp_curve` belongs on
  the system (overridable per `skill_def`), never assumed by the engine.

The point is not this specific recipe. It is that the recipe is **four
`progression` values on data objects** — no engine fork, which is the
whole library thesis.

---

# Master list — the fantasy/adventure pack

The spine, skinned fantasy. Specialization seeds are *future* content;
only the top-level skill ships first. Governing stats shown merc-flavored
(str/dex/int/wis/cha/con); each game system maps its own.

### Combat

| Skill | Tags | Stat | Specialization seeds |
|---|---|---|---|
| melee | combat, weapon | str | blades, axes, bludgeons, polearms, exotic |
| archery | combat, weapon | dex | bow, crossbow, sling |
| thrown | combat, weapon | dex | knives, axes, spears, nets |
| brawling | combat, weapon | str | boxing, wrestling, dirty fighting |
| shields | combat, defense, passive | str | bucklers, tower shields |
| dodge | combat, defense, passive | dex | — |
| dual wielding | combat | dex | — |
| tactics | combat, lore | int | terrain families (forest, urban, cave...) |
| siegecraft | combat, craft | int | engines, fortification |

### Rogue

| Skill | Tags | Stat | Specialization seeds |
|---|---|---|---|
| stealth | stealth | dex | urban shadows, wilderness, crowds |
| larceny | larceny, stealth | dex | pickpocketing, burglary, mugging |
| lockpicking | larceny | dex | padlocks, safes, ward-locks |
| traps | larceny, perception | int | detection, disarming, setting |
| disguise | deception | cha | impersonation, costuming |
| forgery | deception, craft | int | documents, seals, coinage |
| poisoncraft | larceny, craft | int | venoms, antidotes, blade oils |
| escape artistry | movement, larceny | dex | ropes, manacles, grapples |
| shadowing | stealth, perception | int | tailing, losing a tail |

### Perception

| Skill | Tags | Stat | Specialization seeds |
|---|---|---|---|
| observation | perception, passive | int | ambush-sense, detail recall |
| eavesdropping | perception, stealth | int | whispers, through doors, lipreading |
| investigation | perception | int | searching, evidence, interrogatories |
| tracking | perception, survival | wis | beasts, people, aged trails |
| scouting | perception | wis | ranging (see into adjacent rooms), overwatch |

### Social

| Skill | Tags | Stat | Specialization seeds |
|---|---|---|---|
| persuasion | social | cha | diplomacy, fast-talk, oratory |
| intimidation | social, combat | str | menace, torture (dark games) |
| deception | social, deception | cha | acting, cons, false identity |
| etiquette | social, lore | cha | court, street, guild, clergy (per context) |
| leadership | social | cha | rallying, command, delegation |
| interrogation | social | int | questioning, reading lies |
| streetwise | social, lore | int | rumors, contacts, underworld doors |
| teaching | social | int | (lets players train others — fee economy) |
| haggling | social, trade | cha | — |
| performance | performance, social | cha | instrument, singing, dance, storytelling |
| gambling | social, deception | int | dice, cards, cheating |

### Craft (artisan)

| Skill | Tags | Stat | Specialization seeds |
|---|---|---|---|
| smithing | craft | str | weapons, armor, tools, **unobtainium-work** |
| carpentry | craft | str | furniture, wagons, boats |
| masonry | craft | str | walls, monuments, keeps |
| leatherworking | craft | dex | armor, saddlery, bookbinding |
| tailoring | craft | dex | clothing, costumes, sails |
| jewelcraft | craft, trade | dex | gemcutting, settings, engraving |
| pottery | craft | dex | vessels, tiles, kilnwork |
| glassblowing | craft | dex | vessels, lenses, stained glass |
| fletching | craft | dex | arrows, bolts, bows |
| cooking | craft, survival | int | baking, curing, feasts |
| brewing | craft | int | ale, wine, spirits |
| alchemy | craft, magic | int | potions, acids, incendiaries |
| herbalism | craft, medicine | wis | remedies, poultices, drugs |
| scribing | craft, lore | int | calligraphy, illumination, secret writing |
| cartography | craft, lore | int | local, sea charts, treasure maps |
| engineering | craft, lore | int | mechanisms, locks, siege engines |

### Gather

| Skill | Tags | Stat | Specialization seeds |
|---|---|---|---|
| mining | gather | str | stone, ore, gems, **unobtainium** |
| logging | gather | str | hardwoods, resins |
| farming | gather | con | grains, orchards, livestock feed |
| fishing | gather, survival | wis | line, nets, trawling, deep-sea |
| foraging | gather, survival | wis | food, herbs, mushrooms |
| hunting | gather, survival | dex | small game, big game, trapping |
| butchery | gather, craft | dex | skinning, meat-cutting, trophies |
| salvaging | gather, larceny | int | wrecks, ruins, scrap |

### Animal

| Skill | Tags | Stat | Specialization seeds |
|---|---|---|---|
| animal handling | animal | wis | taming, training, husbandry |
| riding | animal, movement | dex | horses, exotics, war-mounts |

### Survival & medicine

| Skill | Tags | Stat | Specialization seeds |
|---|---|---|---|
| survival | survival | wis | forest, desert, mountain, underground |
| navigation | survival, lore | int | land, sea, stars |
| medicine | medicine | int | first aid, surgery, diseases |
| swimming | movement, survival | con | diving, currents |
| climbing | movement | str | cliffs, walls, rigging |
| athletics | movement | con | running, jumping, acrobatics |

### Lore & language

| Skill | Tags | Stat | Specialization seeds |
|---|---|---|---|
| lore | lore | int | history, arcana, religion, law, nature |
| research | lore | int | libraries, archives, cross-reference |
| appraisal | trade, lore | int | gems, art, antiquities, fakes |
| trading | trade, social | int | brokering, speculation, caravans |
| tongues | language | int | one spec per language (garble by min of speaker/listener, per SMAUG) |
| meditation | magic | wis | (system-specific: focus, mana recovery) |
| spellcraft | magic, lore | int | (system-specific: identify, counter, design) |

**Count: 62 top-level skills.** Compare: user's SF GURPS data ~100 (flat),
CoffeeMud ~400 (flat, all tiers). 62 tops with 3-5 specs each lands at a
comparable 200-300 total once specialization content ships — and an idler
exposing only the spine sees ~35 grind tracks over that same tree.

## The fun list

Schemes and flavor the references proved players love — each maps to a
skill above plus a small system:

| Fun thing | Skill it hangs on | Reference proof |
|---|---|---|
| Stealing from NPCs/players | larceny | exists (StealBehavior); CoffeeMud Steal/Mug/Embezzle |
| Overhearing whispers | eavesdropping | showcase gap G2 already filed; CoffeeMud Evesdrop |
| Fencing stolen goods | streetwise + trading | CoffeeMud FenceLoot/BlackMarketeering — closes the theft economy loop |
| Treasure maps | cartography + investigation | CoffeeMud TreasureMap/BuriedTreasure/Digsite |
| Street urchin network | streetwise | CoffeeMud urchin suite — recruit kids as spies/pickpockets |
| Fortune telling cons | deception + performance | CoffeeMud Tarot/Palm/Tasseography |
| Secret/coded writing | scribing | CoffeeMud MorseCode/EncryptedWriting — covert player mail |
| Turf graffiti | streetwise | CoffeeMud Graffiti/TagTurf — territory written on rooms |
| Gambling dens | gambling | CoffeeMud; SWR notably has none (gap they regretted) |
| Bounty hunting | tracking + investigation | SWR player-bounty escrow economy; CoffeeMud Arrest/CollectBounty; ties into REALM's crime system |
| Slice-and-cook | butchery + cooking | SMAUG's two-skill corpse-to-meal loop |
| Trophies & body art | butchery (taxidermy), jewelcraft (tattoos) | CoffeeMud — status items |
| Teaching for fees | teaching | player-to-player training economy |
| Tavern flourishes | performance | CoffeeMud SmokeRings — trainable pure flavor |
| Sustained/channelled skills | (mechanic) | tbaMUD whirlwind — re-fires until the check fails |
| Misdirection on failed track | tracking | tbaMUD — a failed roll points you the WRONG way |
| An offline training queue | (mechanic) | EVE — the only progression that respects a player's absence |
| Per-node mastery | any gather/craft spec | Melvor/RuneScape — the same ore, mastered, yields more |

## Reference appendix (what each source is FOR)

- **CoffeeMud** — breadth (the artisan/thief catalogs above are distilled
  from it) and both specialization models. Steal: expertise data format,
  Master-tier gating, the fun list.
- **SMAUG** — the learning economy: practice sessions carry a skill only
  to 20% of class cap, then learn-by-use takes over; +1-2% per successful
  use, a celebration XP bonus at mastery. Also: tongues garbling by
  `min(speaker%, listener%)`, fighting stances as skills, secret skills,
  and 18 combat maneuvers as pure data (validates REALM's skills-as-data).
- **tbaMUD** — the floor (11 skills). Steal: track's wrong-way-on-failure,
  whirlwind's channelled pattern, the INT-as-exchange-rate practice math.
- **SWR** — 8 parallel career XP classes (using smuggling skills levels
  your smuggler career, not a monolithic level); the `make*` crafting
  pattern (roll -> multi-round timer -> consume components -> quality
  scales with skill); hijacking; planet influence via smalltalk.
- **FS3/Ares** — taxonomy discipline: a small ruled action list + freeform
  background skills ("unknown name = background skill"); linked
  attributes; chargen pyramid caps; specialties as labels.
- **AwakeMUD** — the modern/social vocabulary: etiquette-per-context
  (corporate/street/tribal...), negotiation vs intimidation vs
  interrogation as distinct skills, per-chassis pilot+repair pairs, and
  attribute defaulting chains for untrained rolls.
- **GoMud** — emergent profession titles (skill combos score into
  displayed titles: brawling+dual-wield -> "journeyman warrior") and
  level-gated subcommand unlocks (skill level N enables `command:subverb`).
- **DikuMUD3/VME** — the best Diku craft/gather set (forage, herbs, dowse,
  skin, butcher, cook, resize, fashion weapon); a real weapon skill tree
  with leaf->category defaulting; per-profession skill *pricing* instead
  of gating.
- **Solar Frontiers (GURPS)** — the user's own ~100-skill list; its flat
  `survival_forest` / `hidden_lore_demons` pattern is what the `@parent`
  chain plus `requires` formalizes.
- **EVE Online** *(added in refinement)* — real-time queue training: one
  skill trains at a time, offline, at `primary + secondary/2` SP per
  minute; skills carry a `rank` cost multiplier and five levels on an
  exponential curve; a prerequisite graph gates what you may train. The
  proof that a progression model can respect a player's absence, and the
  source of `requires`.
- **Melvor Idle / RuneScape** *(added in refinement)* — per-skill levels
  earned purely by use, plus **mastery per action target** (each ore, each
  fish levels independently inside its skill). The proof that a
  specialization tree and a mastery grid are the same data structure, and
  the model for the idle-action loop.

## Engine notes (what this needs from REALM)

**Already there:** `skill_def` objects (name, stat, penalty) merged over
system builtins ([definitions.py](realm/systems/definitions.py)); the
`@parent` attribute-inheritance chain; native object tags for grouping;
`skill_<name>` attrs; the checks engine with pluggable resolver and
condition modifiers; `resolve_rule` softcode resolution; content packs;
point-buy `improve`/CP; merc `practices` (unspendable); per-object skill
overrides (`db.lock_skill`, `db.check_skill`).

**To build** (filed in BACKLOG, in dependency order):

1. **Skill roles** — the six-entry role table, `GameSystem.skill_roles()`,
   and converting the five hardcoded call sites to `check_role`. Small,
   fully backward-compatible, and it unblocks non-fantasy packs.
   1b. **Failed attempts propagate** — the gated-event helper fires the
   action on the "no" branch too, unapplied, carrying the `CheckResult`;
   `ON_<VERB>_FAIL` hooks hear it. Convert `pick`, then sneak / search /
   persuade. (Same change-site as step 1: these commands are being edited
   anyway.)
2. **Specialization** — `@parent` on `skill_def` + `requires` prereqs +
   parent-chain fallback in `skill_level` + hidden-until-unlocked
   visibility.
3. **`skills` command** grouped by tag, showing spec trees and lock state
   (the tags and the tree are why).
4. **Progression seam** — `on_skill_used` sync hook on `check()`,
   `progression` attr on `skill_def`, `default_progression` on GameSystem,
   `skill_cap`, and an optional `progress_rule` softcode route. Ship the
   SMAUG hybrid (practice to a floor, use past it) as the first
   non-point-buy model, plus the missing `practice` command.
5. **Idle training** — `training_queue` / `training_since`, lazy accrual on
   read, prerequisite checks via `requires`, completion notices on the
   coarse reaper. No new timer.
6. **Content packs** — seed the fantasy pack (this list) and re-skin the
   spine for `gurps-scifi`.
7. **The idle-action loop** — timed repeating gather/craft behavior with a
   drop table (behaviors + softcode, not engine).
