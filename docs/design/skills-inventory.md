# Skills: Reference Inventory & Master List

A survey of every reference architecture's skill system (2026-08-02),
synthesized into a tagged master list of **top-level skills** for REALM,
plus the specialization model that lets a skill deepen with mastery
(Mining -> Mining Unobtainium).

**Sources surveyed:** CoffeeMud (~170 artisan + ~190 thief + fighter/general
skills; the motherlode), SMAUG (86 skills + 7 weapon groups + 11 tongues),
tbaMUD (11 — the Diku floor), SWR (space/technical/crafting + 8 career
classes), AresMUSH FS3 (taxonomy + specialties), AwakeMUD (~155 Shadowrun
skills — the modern/social vocabulary), GoMud (15 tags + emergent
professions), DikuMUD3/VME (75 skills + a 72-entry weapon tree with
category defaulting), and Solar Frontiers' own GURPS data (~100 skills).
Per-source highlights are in the appendix.

## The progression model

Every reference solves "get better -> get more specific" one of three ways:

1. **Vertical tiers as separate skills** — CoffeeMud's `Mining ->
   MasterMining -> Legendary*` (subclass with better yield/speed, gated by
   level); VME's weapon tree (leaf weapons default to their category
   parent); SMAUG's second/third/fourth attack chain.
2. **Horizontal expertises on one skill** — CoffeeMud's data-driven ladders
   (`Stealthy I-X`: one text line = ten stages, each with stat/level gates
   and costs, modifying one declared axis: power, speed, cost, range, or a
   skill-defined effect).
3. **Specialty labels on one rating** — FS3 (Medicine -> Surgeon):
   qualification markers, mechanically inert by design.

**REALM's model (proposed): vertical, as data.** A specialization is just
another `skill_def` with two new attrs:

```text
@create skill_def "mining unobtainium"
  stat = strength          # governing attribute (already exists)
  penalty = -80            # untrained default (already exists)
  parent = mining          # NEW: the top-level skill this deepens
  unlocks_at = 60          # NEW: parent level at which it becomes trainable
```

- **Top-level skills train normally** — this whole document ships only
  top-level skills at first.
- At `unlocks_at`, the specialization appears (trainable, visible in
  `score`). Until then it is hidden — SMAUG's `SF_SECRETSKILL` pattern,
  which also gives quest-taught skills for free (a def with no parent and
  a `hidden` tag that a quest reveals).
- **Checks default upward**: rolling an untrained specialization falls
  back to `parent + penalty` (the GURPS default idiom; AwakeMUD's
  `DEFAULT_TO` chain; VME's leaf->category weapon defaulting). Knowing
  `mining` 70 means attempting unobtainium at, say, 70-40 — hard, not
  impossible.
- `skill_def`s are ordinary objects, so **grouping tags cost nothing** —
  they are literally object tags: `tags = [skill_def, gather]`.

Rejected for now: expertise ladders (CoffeeMud model 2) — powerful but a
second currency; revisit if vertical specs feel flat. FS3 labels can ride
along later as pure flavor.

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

## Master list — top-level skills

Specialization seeds are *future* content; only the top-level skill ships
first. Governing stats shown merc-flavored (str/dex/int/wis/cha/con);
each game system maps its own.

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
comparable 200-300 total once specialization content ships.

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
  `survival_forest` / `hidden_lore_demons` pattern is what `parent` +
  `unlocks_at` formalizes.

## Engine notes (what this needs from REALM)

Already there: `skill_def` objects (name, stat, penalty) merged over
system builtins; native object tags for grouping; `skill_<name>` attrs on
characters; the checks engine; `improve` (CP) and practices (merc).

To build (filed in BACKLOG):

1. `parent` + `unlocks_at` on skill_def; untrained-spec checks default to
   parent at penalty; specs hidden until unlocked.
2. A `skills` command grouping by tag (the tags are why).
3. Learn-by-use option per system (SMAUG hybrid: practice to a floor,
   use past it) — merc currently improves by practice/CP only.
4. Gather/craft verb pattern: one generic timed-action core (SWR's
   make*/CoffeeMud's CommonSkill shape) that skill defs parameterize —
   candidates for behaviors + softcode rather than engine code.
