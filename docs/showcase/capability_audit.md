# Showcase Capability Audit

An honest audit of the 250-item showcase checklist (see
[`checklist.md`](checklist.md)) against REALM's **actual** engine surface as
of 2026-07-17 — every classification below was checked against source
(`realm/scripting/functions.py`, `triggers.py`, `realm/behaviors/`,
`realm/combat/`, `realm/commands/`, `realm/core/`), not the README.

The checklist originated as an Evennia/Solar Frontiers tutorial plan
(Python typeclasses). REALM's version must be **softcode-first**: every
`[now]` item is buildable live, in-game, with `@dig`/`@create`/`@set`,
`$`-commands, `^listen`, `ON_<EVENT>` triggers, behaviors, and the
sandboxed-Python function library — no server restart.

## Classification summary

| Class | Meaning | Count |
|---|---|---|
| **SOFTCODE-NOW** | expressible today, live in-game | **223** |
| **ENGINE-SMALL — shipped 2026-07-17** | the seam is now in the engine; needs a deploy-time native binding + softcode (items 79/84/85/133/134/139) | **6** |
| **ENGINE-SMALL — open** | needs one modest engine addition (named per row) | **14** |
| **ENGINE-MAJOR** | needs a subsystem REALM lacks (named per row) | **7** |
| | | **250** |

Recurring patterns the `[now]` rows lean on (all verified to exist):

- **Triggers**: `$pattern:code` commands, `^pattern:code` listens,
  `ON_<EVENT>` (30 standard events, any suffix via `act()`), `on_tick`
  (script_ticker behavior), `on_check` wards (`block()` by action tag).
- **Wizards**: softcode `prompt(target, text, callback[, persistent])`
  for menus, codes, dialogues, multi-step flows.
- **Timing**: `wait()`/`cancel_wait()` (in-memory), `expire()`/`ON_EXPIRE`
  (persistent), `now()` timestamp arithmetic, behaviors on the world tick.
- **World-zone master**: tag rooms `zone:world`, crown one master —
  global `$`-commands, global `ON_CONNECT`/`ON_DEATH`/`ON_ATTACK`
  witnesses, global policy. (The classic Zone Master Room; the engine's
  dedicated Master Room is still a TODO, but the zone route works today.)
- **Admin-owned masters**: softcode runs with its *owner's* authority
  (`controls()`), so an admin-owned quest/effect master may write player
  sheets; a builder-owned one deliberately may not.
- **Behaviors**: spawner, decay, zone_reset, shopkeeper, wandering,
  patrol, guard, watchful, aggressive/defensive/fleeing/healer,
  script_ticker, timed_effect / damage_over_time / modifier_effect /
  regeneration / disposition_boost.
- **Data**: skills/classes as `skill_def`/`class_def` objects, content
  packs (`@pack`, `realm pack import`), areas as files
  (`@export`/`@import` plan→apply), `@parent` inheritance, `@clone`,
  `@find`/`@foreach`/`search_world`.

Known engine truths that bound the audit (checked in source):

- Builtin commands dispatch **before** softcode `$`-triggers — softcode
  cannot shadow `say`/`whisper`/`who`; anything needing to *transform*
  builtin speech or presence output is an engine gap.
- `wait()` timers are in-memory (MUSH-style); `expire()` persists.
- GMCP is live (telnet option 201 + websocket parity + `oob()`).
- Combat: beat-driven encounters, maneuvers incl. aim/cover/range bands,
  strategies, `ON_HITPRCNT`, corpses + loot, players fall unconscious.
- No weight/capacity kernel — weight is an attribute convention, gated
  by `on_check` wards (that is the tutorial, not a gap).
- No game calendar — but `now()` arithmetic builds one in softcode.

---

## Per-item classification

Class key: **now** = SOFTCODE-NOW · **small** = ENGINE-SMALL (gap named)
· **major** = ENGINE-MAJOR (subsystem named). Gap IDs (G1–G13) refer to
the ranked gap list below.

### 1. Interactive Objects & Gadgets (1–13)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 1 | Slot machine | now | `$pull` cmd-trigger; `rand()`+`switch()` payout table; `transfer_credits()`; `ON_PAYMENT` |
| 2 | Vending machine | now | `pay` → `ON_PAYMENT`; `create_obj()` from prototype attrs (spawner vocabulary) |
| 3 | Jukebox | now | `$play` + `prompt()` menu; `wait()` chains for timed lyrics; `remit()` |
| 4 | ATM / bank terminal | now | one bank object holding `db.accounts`; terminals call it via `eval_attr()`; `transfer_credits()` |
| 5 | Magic 8-ball | now | `$shake: say switch(rand(1,8), …)` — the hello-world |
| 6 | Flashlight | now | `light` tag toggle (`add_tag`/`remove_tag`); `on_tick` battery drain; engine dark-room perception |
| 7 | Voice recorder | now | `^*:` listen appends `db.transcript`; `$play` reads back |
| 8 | Camera | now | `$snap: create_obj()` photo; desc built from `name(here)` + `contents(here)` loop |
| 9 | Music box | now | `$wind` sets turns attr; `wait()` chain emotes until it runs down |
| 10 | Typewriter & paper | now | `prompt()` page wizard; per-page attrs; `$read`/`$sign`; OLC attribute editor |
| 11 | Mirror | now | `ON_LOOK: pemit(enactor, …)` their description + worn-tag contents scan |
| 12 | Gift box | now | container + `set_lock()` per recipient; `ON_OPEN` fanfare |
| 13 | Fortune teller booth | now | `ON_PAYMENT` + `create_obj()` fortune card, `rand()` text |

### 2. Containers, Storage & Item Handling (14–24)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 14 | Basic container | now | `container` tag; `on_check` ward `block()`s put over summed weight attrs |
| 15 | Locked chest & key | now | `@lock`, `lock`/`unlock`/`pick` commands, key items, `ON_OPEN`/`ON_UNLOCK` (gated) |
| 16 | Combination safe | now | `prompt(enactor, 'Code?', 'check_code')` vs `secret`-flagged attr |
| 17 | Bag of holding | now | weight is a softcode convention; this bag's weight function returns 0 |
| 18 | Refrigerator | now | decay behavior; `ON_PUT`/`ON_GET` adjust the item's decay-ticks attr |
| 19 | Trash bin / incinerator | now | `ON_RECEIVE` + `expire(item, grace)`; `ON_EXPIRE` destroys; `$rummage` rescues |
| 20 | Bookshelf | now | `$browse`: loop `contents(me)`, list `has_tag('book')` titles |
| 21 | Ammo pouch | now | `on_check` ward: block unless `has_tag(item, 'ammo')` |
| 22 | Coat check | now | `create_obj()` ticket with claim-id attr; `$claim` matches and returns item |
| 23 | Conveyor belt | now | `script_ticker` `on_tick`: `move_to()` each item to the next room |
| 24 | Loot crate | now | `ON_OPEN` one-shot flag; weighted `rand()` table → `create_obj()` |

### 3. Doors, Exits & Access Control (25–35)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 25 | Lockable door | now | `@dig` paired exits; `@lock` both sides; key item; shared state attrs + `trigger` |
| 26 | Keycard door | now | exit `on_check` ward scans `contents(enactor)` for a clearance attr |
| 27 | Secret door | now | concealed exits (perception engine); `search` + `skill_check('observation')` reveal |
| 28 | One-way exit | now | `@open` single exit; `ON_LEAVE`/`ON_ARRIVE` message overrides |
| 29 | Timed door | now | `$push`: open + `wait(30, 'close …')`; `cancel_wait()` for atomicity |
| 30 | Toll gate | now | exit `on_check`: `credits(enactor) >= fee` else `block()`; `transfer_credits`; `ON_PAYMENT` |
| 31 | Guarded exit | now | guard behavior + disposition; `persuade`/`fasttalk`; guest-list attr in the ward |
| 32 | Airlock | now | two doors, `on_check` interlock reading the other door's state; `$cycle` wait sequence |
| 33 | Portal pair | now | `create_obj(tags=['exit'])` + `db.destination` both ends; `ON_ARRIVE` effects |
| 34 | Climbing exit | now | `on_check` `skill_check('climbing')` else `block()` + `damage(enactor, roll('1d6'))`; `ON_FAIL` |
| 35 | Size-restricted crawlspace | now | `on_check` reads enactor stats/carried count; helpful `block()` text |

### 4. Rooms & Environment (36–47)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 36 | Weather system | now | zone master `on_tick` drifts `db.weather`; `remit()` to `zone_rooms()` |
| 37 | Day/night cycle | now | softcode clock from `now()`; `[[…]]` descs branch on hour; visibility via tags |
| 38 | Dark room | now | engine: `dark` tag, `light`-tagged sources, `nightvision` |
| 39 | Underwater room | now | room `on_tick`: per-occupant breath attrs, `skill_check('swimming')`, `damage()` |
| 40 | Zero-G compartment | now | movement ward (`has_atag('movement')` → `block()`) + `$push`/`$drift` verbs; themed `remit()` |
| 41 | Ambient room messages | now | `script_ticker` + `rand()` gate + `remit()` (the docs-tutorial pattern) |
| 42 | Room details | now | `@detail` / `desc_extras` with per-viewer conditions — built in |
| 43 | Hazard room | now | room `on_tick`: `skill_check(occ,'health')` else `damage()`; severity via `zone_property` |
| 44 | Instanced room | now | `enter_instance()` — ephemeral instances are shipped |
| 45 | Procedural wilderness | now | wilderness regions: `cell_name`/`cell_desc`/`cell_exits` map-provider attrs — shipped |
| 46 | Room capacity | now | room `on_check` ENTER ward counting `player`-tagged contents |
| 47 | Falling between rooms | now | ledge check on `ON_ENTER`/ward fail → `teleport_obj()` below + `damage()` |

### 5. Traps, Hazards & Devices (48–59)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 48 | Gas bomb | now | `$arm` + `wait()` fuse; gas objects spread along `exits()` graph; `on_tick` HT `skill_check` + `damage`; `expire()` |
| 49 | Landmine | now | concealed tag; `ON_ENTER` + `contest()` Per-vs-concealment else `damage()` |
| 50 | Tripwire alarm | now | `ON_ENTER: pemit(owner(me), …)` — silent remote alert |
| 51 | Pit trap | now | `ON_ENTER` + skill gate → `teleport_obj(enactor, cell)`; `$climb` escape contest |
| 52 | Poison dart trap | now | `ON_GET`/`ON_USE` on trapped object → `apply_effect('damage_over_time')` |
| 53 | Snare | now | `add_tag('snared')` + movement ward; `$struggle` `contest()` of ST to break free |
| 54 | Security camera & monitor | now | bug object in target room: `^*:` + `ON_ENTER`/`ON_LEAVE` relay via `pemit()` to watchers |
| 55 | Motion sensor log | now | `ON_ENTER`/`ON_LEAVE` append `(name, now())` to a log attr; `$review` |
| 56 | Self-destruct sequence | now | master `wait()` chain of countdown `remit()`s; `$abort` + `cancel_wait(handle)`; `secret` code attr |
| 57 | EMP charge | now | loop `contents(here)` `has_tag('electronic')` → `add_tag('disabled')`; `wait()` restore; gadgets check the tag |
| 58 | Spreading fire | now | fire objects `on_tick` grow + spread via `exits()`; extinguisher `$spray` destroys; damages occupants |
| 59 | Tranquilizer mechanics | now | engine `unconscious` tag (blocks move/attack); `apply_effect` + `wait()` to wake |

### 6. NPCs & AI Behaviors (60–73)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 60 | Wandering NPC | now | `wandering` behavior (built in); zone confinement params |
| 61 | Patrolling guard | now | `patrol` behavior (built in); waypoint params; `ON_OPEN` reactions |
| 62 | Aggressive mob | now | `aggressive` behavior + disposition thresholds; `start_combat()` |
| 63 | Shopkeeper | now | `shopkeeper` behavior + `list`/`buy`/`sell`/`pay`; `spawner` restock |
| 64 | Bartender | now | `^listen` keyword patterns; `create_obj()` drinks; rumor attrs |
| 65 | Pet | now | `db.following`; `$`-command whitelist on the pet; ownership |
| 66 | Puppet | now | opt-in control lock (`@lock/control`) + `@force`; puppet output forwarded to the forcer |
| 67 | Dialogue-tree NPC | now | `prompt()` callback chains; per-player memory dict attr keyed by enactor id |
| 68 | NPC daily schedule | now | `on_tick` + softcode clock; `attach_behavior`/`detach_behavior` by hour; walk home |
| 69 | Trainer NPC | now | CP economy (`points`/`improve`) built in; `$train` wrapper with fees/prereqs (admin-owned NPC writes the sheet) |
| 70 | Pickpocket NPC | now | `contest('pickpocket','observation')`; admin-owned NPC `move_to()` the item; disposition fallout |
| 71 | Guard response | now | zone master `ON_ATTACK` witness → summon guards (`teleport_obj`/`force`); disposition drop |
| 72 | NPC reaction emotes | now | `^listen` + `ON_WIELD`/`ON_*`; cooldown attr with `now()` |
| 73 | Boss with phases | now | `ON_HITPRCNT` (`db.hitprcnt`) + combat strategies; swap behaviors per phase |

### 7. Communication Systems (74–85)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 74 | Custom channel | now | world-master `$chat`: subscriber-list attr, `pemit()` fan-out, history attr, mute attrs |
| 75 | In-game mail | now | post-office object stores mail dict + escrow items; `$send`/`$read`; `ON_CONNECT` "you have mail" |
| 76 | Bulletin boards | now | board object: posts as attrs with timestamps; `on_tick` expiry sweep |
| 77 | Handheld radios | now | radio `^*:` relays via `search_world(attr='freq', value=…)` + `pemit()` to holders |
| 78 | Station PA system | now | `for r in zone_rooms('station'): remit(r, msg)` |
| 79 | Languages | ~~small~~ **SHIPPED 2026-07-17** (`register_speech_renderer` garbles the `{speech}` body per listener; tutorial [079_languages](079_languages.md)) | **G2 speech pipeline**: per-listener transform hook to garble by listener skill (builtins can't be shadowed) |
| 80 | Overheard whispers | **small** | **G2 speech pipeline**: per-bystander Per leak roll on `whisper` (engine emits a fixed vague line today) |
| 81 | Graffiti | now | room-owned `$scrawl` appends a `desc_extras` detail (`set_attr(me,…)` runs as the room) |
| 82 | Newspaper | now | issue compiled into attrs; kiosk `ON_PAYMENT` dispenses `create_obj()` copy; `on_tick` release |
| 83 | Message in a bottle | now | bottle logged on an ocean master; `on_tick` random delay → deliver via mail pattern / `pemit` |
| 84 | Voice disguise | ~~small~~ **SHIPPED 2026-07-17** (`db.voice_as` reskins the speech `{actor}` only; face/room-list unaffected; tutorial [084_voice_disguise](084_voice_disguise.md)) | **G2 speech pipeline**: speaker-attribution override (say's name line is engine-fixed) |
| 85 | Rich emote parser | ~~small~~ **SHIPPED 2026-07-17** (native `pose /name` command; per-viewer rendering, configurable EMOTE_SIGIL) | **G3 identity layer**: per-viewer name substitution in emotes (perceived_name has no sdesc hook) |

### 8. Economy & Commerce (86–97)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 86 | Multi-denomination currency | now | canonical `credits()` + coin items; `$exchange` change-making arithmetic |
| 87 | Bank accounts | now | bank-object ledger attrs; `transfer_credits()`; `on_tick` interest; audit-log attr |
| 88 | Player-run shop stalls | now | stall objects with owner pricing attrs; shopkeeper behavior or `$`-commands; `on_tick` rent |
| 89 | Auction house | now | auction master: listing/bid/expiry attrs; escrow in its inventory; `on_tick` settlement |
| 90 | Pawn shop | now | `$pawn` pays a percentage of `db.value`; buyback window via attr + `expire()` |
| 91 | Lottery | now | numbered ticket items; master `on_tick` drawing; pot via `transfer_credits()` |
| 92 | Commodity market | now | price attrs drift `on_tick` + `rand()` events; `$market` renders the table |
| 93 | Housing rent | now | `on_tick` billing + warning `pemit()`s; `set_lock()` evicts; grace attrs |
| 94 | Job board | now | posting attrs; `ON_GIVE`/`ON_PAYMENT` verification; payout `transfer_credits()` |
| 95 | Item durability & repair | now | durability attrs; zone-master `ON_ATTACK`/`ON_DAMAGE` wear bookkeeping; `$repair` money sink |
| 96 | Secure player trade | now | escrow object; both sides `prompt()` confirm; swap executes in one script |
| 97 | Barter NPC | now | want-list attr; `ON_RECEIVE`/`give` matching; item-for-item swap |

### 9. Games & Recreation (98–108)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 98 | Dice roller | now | `roll('3d6')`, `margin_under()` vs skill; `$roll`; `@rolls` debug echo |
| 99 | Card deck | now | deck as list attr, `rand()` shuffle; per-player hand attrs; `pemit()` private views |
| 100 | Poker table | now | sandboxed-Python state machine on the table; `prompt()` betting rounds; hidden info via `pemit` *(advanced)* |
| 101 | Chess board | now | board attr; `eval_attr()` render helper; move validation in sandboxed Python *(advanced)* |
| 102 | Trivia host NPC | now | question data in attrs/pack; `prompt()` answer windows; score attrs |
| 103 | Rock-paper-scissors | now | simultaneous secrets via `prompt()` to both; escrowed wager; reveal `remit()` |
| 104 | Scavenger hunt | now | hunt-master registry; `ON_GET`/`ON_ARRIVE` detection; leaderboard attr |
| 105 | NPC races & betting | now | `on_tick` race sim; odds attrs; betting-book object; payouts |
| 106 | Arm wrestling | now | `contest(a,'strength',b,'strength')`; `remit()` play-by-play; wager |
| 107 | Dart board | now | `$throw` `skill_check()` margins → score; CP practice award via admin-owned master |
| 108 | Casino floor | now | composition: chips exchange vs house-bank object + prior builds |

### 10. Combat & Conflict Extensions (109–120)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 109 | Cover system | now | engine `cover` maneuver + `cover`-tagged fixtures — tour + tagging |
| 110 | Ammunition & reloading | **small** | **G8 ammo/reload**: ruleset must consume weapon `db.ammo` on ranged attacks + a `reload` maneuver |
| 111 | Grenades | now | `$throw` + `wait()` fuse; loop `damage()` over occupants; `rand()` scatter to an `exits()` neighbor |
| 112 | Non-lethal takedowns | now | players already fall unconscious; NPC surrender via `ON_HITPRCNT` behavior swap; `restrained` tag + ward |
| 113 | Dueling system | now | `$duel` consent `prompt()`s both sides; `start_combat()`; stakes escrow; referee logic |
| 114 | Bounty board | now | board attrs; world/zone `ON_DEATH` verifies killer; escrow payout |
| 115 | Arena with spectators | now | recorder in the pit relays `ON_ATTACK`/`ON_DAMAGE` via `remit()` to the stands room |
| 116 | Called shots | **small** | **G9 hit locations**: GURPS ruleset needs a hit-location maneuver + penalty/effect table |
| 117 | Armor degradation | now | admin-owned master `ON_DAMAGE` decrements armor durability attr → adjusts DR attr; `$repair` |
| 118 | Bleeding & first aid | now | `damage_over_time` behavior + `firstaid` command — both built in |
| 119 | NPC morale | now | `ON_HITPRCNT` → detach `aggressive`, attach `fleeing`; surrender via disposition |
| 120 | Combat replay log | now | recorder object `ON_ATTACK`/`ON_DAMAGE`/`ON_DEATH` appends a log attr; `$replay` `pemit()`s it |

### 11. Crafting & Resources (121–131)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 121 | Gathering nodes | now | node attrs deplete on `$mine`; `on_tick` respawn; yield via `margin_under()` |
| 122 | Recipe crafting | now | `$craft`: validate ingredients in `contents()`, `destroy_obj()` inputs, `create_obj()` output; margin = quality |
| 123 | Refining chain | now | staged stations with tag-gated recipes |
| 124 | Salvage & disassembly | now | `$salvage`: component table per item tag; destroy + create parts |
| 125 | Quality tiers | now | `margin_under()` margin → fine/good/shoddy attrs on the output |
| 126 | Blueprint items | now | `$study`/`ON_USE` adds the recipe to the crafter's known-list attr |
| 127 | Crafting stations | now | recipe requires a `forge`-tagged object in `contents(here)` |
| 128 | Hydroponics farming | now | plant objects with `on_tick` growth stages; desc swaps per stage; harvest `create_obj()` |
| 129 | Cooking with buffs | now | meals `apply_effect('modifier_effect', duration)`; `decay` behavior spoilage |
| 130 | Fishing | now | `$cast` + `wait(rand())` + `prompt()` hook window; catch table; skill margin |
| 131 | Chemistry & poisons | now | recipes with risk: failure margins → `damage()`/`apply_effect` on the crafter; skill prereqs |

### 12. Character Systems (132–143)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 132 | Chargen walkthrough | now | GameSystem ChargenSteps (`rules.py`) *or* an admin-owned clerk `prompt()` wizard writing the sheet live |
| 133 | Short-descs & introductions | ~~small~~ **SHIPPED 2026-07-17** (`register_name_resolver` sdesc/recog seam; tutorial [133_short_descs](133_short_descs.md)) | **G3 identity layer**: per-viewer naming (sdesc/recog) hook in `perceived_name` |
| 134 | Disguises | ~~small~~ **SHIPPED 2026-07-17** (disguise resolver + `check_roll` see-through check; tutorial [134_disguises](134_disguises.md)) | **G3 identity layer**: apparent-name override + softcode rename (no `set_name()` today) |
| 135 | Injury & treatment | now | `modifier_effect` conditions; `firstaid`; `regeneration` behavior; recovery timers |
| 136 | Encumbrance effects | now | weight-sum softcode on `ON_GET`/`ON_DROP` → `modifier_effect` DX penalty (effects are proximity-gated) |
| 137 | Hunger & thirst | now | `on_tick` meter attrs; consumable `ON_USE` resets; toggle via zone policy |
| 138 | Sleep & rest | now | `$rest`/`$sleep` tags; `regeneration` boost; vulnerability via ward/lockout |
| 139 | Intoxication | ~~small~~ **SHIPPED 2026-07-17** (`modifier_effect` penalty + `register_speech_renderer` slur, both scaling with a drink counter; tutorial [139_intoxication](139_intoxication.md)) | stacking `modifier_effect`s work today; slurring now has its seam — `register_speech_renderer` |
| 140 | Death & cloning | now | `ON_DEATH` + engine unconsciousness/corpses; clone-bay `teleport_obj()` + fees |
| 141 | Character sheet display | now | `stats` built in; custom `$sheet` via `eval_attr()` layout functions |
| 142 | Traits in play | now | `class_def`/`skill_def` data + triggers/effects (phobia = `ON_*` + ward; reflexes = modifier) |
| 143 | XP spending | now | CP economy (`points`/`improve`) built in; training-time limits via `now()` attrs |

### 13. Time, Scheduling & Automation (144–153)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 144 | Game calendar & clock | now | softcode clock: `now()` arithmetic + month-name tables in attrs; `$time` |
| 145 | Scheduled world events | now | master `on_tick` cron-checks against the clock; event-registry attrs |
| 146 | Item decay | now | `decay` behavior + `expire()`/`ON_EXPIRE` built in; batch sweeps via `@foreach` |
| 147 | Zone repop | now | `zone_reset` behavior — player-aware, `reset_spec`, `ON_RESET` — built in |
| 148 | Delayed actions | now | `wait()`/`cancel_wait()` idioms; teach the persistence caveat (waits are in-memory) |
| 149 | Maintenance sweeper | now | `on_tick` + `search_world()` orphan queries + `destroy_obj()`; `@foreach` manually |
| 150 | Global countdown events | now | `wait()` chain + `remit()` loop over `search_world(tag='room')` |
| 151 | Business hours | now | clock + `on_tick` attach/detach `shopkeeper`; closed-state desc via `[[…]]` |
| 152 | Reboot-surviving timers | now | the pattern itself: db timestamps + `on_tick` compare, `expire()` (persists) vs `wait()` (doesn't) |
| 153 | Time scaling | now | your softcode clock's own factor; beat/`pace` discussion for combat tempo |

### 14. Movement & Transportation (154–164)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 154 | Elevator | now | `$press` relinks exits via `set_attr(exit, 'destination', …)`; door-state attrs |
| 155 | Drivable vehicle | now | vehicle = container-room; `$drive` makes the vehicle traverse an exit, riders inside; `[[…]]` outside view |
| 156 | Scheduled shuttle | now | `on_tick` timetable moves the vehicle along its route; boarding-window attrs |
| 157 | Teleporter pads | now | `$tp` + destination-registry attr; `teleport_obj()`; arrival `remit()` effects |
| 158 | Mounts | now | enter the mount (containment) or `db.following`; `$ride`/`$dismount` |
| 159 | Group travel | now | follow/party built in (`follow`, `party`, follower cascade) — tour |
| 160 | Sneaking | now | `hide` + Stealth contests + concealment built in; quiet movement via ward + `contest()` |
| 161 | Travel time | now | exit ward blocks + `wait()` progress `pemit()`s + `teleport_obj()` on arrival *(advanced)* |
| 162 | Tracking | now | `ON_LEAVE` drops footprint objects with `expire()`; `$track` `skill_check()` reads them |
| 163 | Vehicle fuel | now | fuel attr consumed per `$drive`; refuel stations + `transfer_credits()` |
| 164 | Small spaceship | now | capstone composition: multi-room vehicle + airlock interlock + docking = exit relinking |

### 15. Building & World Tools (165–175)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 165 | Prototype library | now | spawner prototype dicts + `@parent` inheritance + `@clone` + pack data |
| 166 | Batchcode areas | now | `@export`/`@import` area files (plan → apply) + `@foreach` bulk edits |
| 167 | Random dungeon generator | now | softcode carves rooms/exits (`create_obj` + tags + destinations) or instance templates *(advanced)* |
| 168 | Room templates | now | `@clone`/`@parent` template rooms; `$stamp` wizard |
| 169 | Zone mass-edit | now | `@find` + `@foreach` over `zone_rooms()`; echo-first as dry run |
| 170 | Builder wizard | now | `prompt()` chain creating rooms/exits without `@`-syntax |
| 171 | Dynamic descriptions | now | `[[…]]` inline per-viewer evaluation — REALM's flagship |
| 172 | World audit report | now | `@eval` + `search_world()`: orphans (no location), dangling `db.destination`, oversized attrs |
| 173 | CSV world import | now | reframed to REALM's format: area files via `@import` (stable-id sync) / `realm import` CLI |
| 174 | Auto-map generator | now | BFS over `exits()` graph, coordinate layout, ASCII render in sandboxed Python *(advanced)* |
| 175 | Player housing customization | now | `@chown` room to player; control lock; room-owned `$redecorate` sets its own desc; `safe` attr flags as guardrails |

### 16. Admin, Moderation & Staff Tools (176–186)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 176 | Staff dashboard | now | `@stats` (tick load, waits, combat) + `who` + `@eval` queries |
| 177 | Jail system | now | `$jail`: `teleport_obj()` + exit lock + `wait()` auto-release + log attr |
| 178 | Ban & sitelock manager | **small** | **G12 ban registry**: account/IP bans with expiry in AuthService (login-attempt lockout exists) |
| 179 | Character approval queue | now | `unapproved` tag gates the start-room exit ward; staff `$approve`; `pemit()` on decision |
| 180 | Staff invisibility | **small** | `invisible` tag + admin sight + `quell` exist; **G4 presence surface**: `who` must respect perception |
| 181 | Announcement system | now | `remit()` loop over all rooms (or world-master emit); history attr; opt-out attr filter |
| 182 | Object snapshot/restore | now | `@clone` as backup + `@export` area files; attr dump via `@eval` into a vault attr |
| 183 | Permission tiers in practice | now | roles (god/admin/builder/player/guest) + locks + `controls()` + `quell` — all built in; tour |
| 184 | New-player onboarding | now | world-master `ON_CONNECT` + first-login attr → starter kit `create_obj()`, greeting, mentor ping |
| 185 | Rate limiting | **small** | **G13 flood throttle**: per-session command-rate limiter (sandbox CPU limits + login lockout exist) |
| 186 | Watchlist & alerts | now | world-master `ON_CONNECT` + `watched` tag → `pemit()` staff |

### 17. Information & UI (187–197)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 187 | Status prompt | **small** | **G10 prompt line**: per-player prompt template appended after output (GMCP vitals via `oob()` work today) |
| 188 | Custom who list | **small** | **G4 presence surface**: expose sessions to softcode (`online_players()`, idle) so `$who` can be built |
| 189 | In-room minimap | now | room `ON_LOOK` `pemit()`s a mini-map from an `exits()` BFS; exploration-memory attr *(advanced)* |
| 190 | Score screen | now | `$score` via `eval_attr()` layout over stats/effects attrs |
| 191 | Help system extensions | now | help *is* auto-generated from command registrations (category/usage/help_text) — tour |
| 192 | Clickable links | **small** | **G11 MXP**: link markup rendered at the telnet edge (markup pipeline is extension-ready) |
| 193 | GMCP/OOB data | now | GMCP live on telnet (option 201) + websocket parity + `oob()` softcode — tour |
| 194 | Screenreader mode | **small** | **G7 render options**: per-session accessibility flags beyond `color on/off` |
| 195 | Color themes | **small** | **G7 render options**: per-player palette remap at the protocol edge (no-color fallback exists) |
| 196 | Personal aliases (nicks) | now | carried alias gadget: inventory `$`-commands run multi-line script bodies |
| 197 | Idle & AFK states | **small** | `who` shows idle; **G4 presence surface**: idle exposed to softcode + auto-AFK hook |

### 18. Quests & Storytelling (198–208)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 198 | Quest framework | now | admin-owned quest master; stage attrs on players; `$quests` journal; `ON_*` completion hooks |
| 199 | Delivery quest | now | `ON_GIVE` verification at the recipient; `wait()`/timestamp deadline; failure states |
| 200 | Collection counters | now | zone/world master `ON_GET` counts tagged items; auto-completes |
| 201 | Branching quest | now | `prompt()` choices set branch attrs; endings gated on them |
| 202 | World event: invasion | now | zone master phases: spawner waves + `remit()`s + cleanup (`destroy_obj`/`ON_RESET`) |
| 203 | Cutscenes | now | `wait()`-paced `pemit()`/`remit()` sequences; `$skip` via `cancel_wait()` |
| 204 | GM possession tools | now | `@force` + control locks + puppet output forwarding — built in |
| 205 | Scene logger | now | recorder `^*` + `ON_POSE` (any-suffix events) appends a log attr; consent attr; `$export` |
| 206 | Rumor mill | now | rumor attrs hop between NPCs via `on_tick` + `^listen`; decay by `now()` |
| 207 | Achievements | now | badge attrs awarded by `ON_*` watchers; hidden tiers via `secret` attr flag; `$badges` |
| 208 | Collectible lore | now | `ON_GET`/`ON_USE` unlocks codex attrs; `$codex` renders found entries |

### 19. Puzzles & Mechanisms (209–218)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 209 | Lever combination | now | levers `ON_PUSH` append to a shared pattern attr on the controller; right order opens the vault |
| 210 | Keypad code | now | `prompt()` code entry vs a `secret`-flagged attr; hints placed elsewhere |
| 211 | Riddle door | now | `prompt()` free-text; normalize via `trim`/`lcfirst` + contains-matching |
| 212 | Weight-plate puzzle | now | plate `ON_RECEIVE`/`ON_PUT` checks contents weights/tags; unlock when all pass |
| 213 | Power routing puzzle | now | junction attrs as graph state; `$route` toggles; win-check as an `eval_attr()` function |
| 214 | Simon sequence | now | `wait()`-chained signal `remit()`s; `prompt()` echo-back; growing pattern attr |
| 215 | Shifting maze | now | `on_tick` relinks exit `db.destination` among the room set |
| 216 | Escape room | now | `enter_instance()` template suite + countdown; reset = a fresh instance per group |
| 217 | Hidden object search | now | concealed tags + `search` (Observation) built in; seeded secrets |
| 218 | Puzzle reset engineering | now | `ON_RESET`/`zone_reset`, instance teardown, or `$reset` scripts restoring attrs |

### 20. Social & Player Systems (219–229)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 219 | Friends list | now | world-master `ON_CONNECT`/`ON_DISCONNECT` + consent attrs → `pemit()` friends |
| 220 | Titles & badges | now | title attrs rendered in look/`$finger` via `desc_extras` (builtin `who` columns are fixed — see G4) |
| 221 | Player organizations | now | org master: rank attrs, invite `$`-commands, roster attr; lock expressions by tag/rank |
| 222 | Org treasury & storage | now | org credits on the master; rank-gated `$withdraw`; lockers with lock expressions |
| 223 | Elections | now | ballot attrs; `$vote` dedupes by id; `on_tick` tally at close |
| 224 | Petition/ticket system | now | ticket-queue attrs on a desk object; staff `$claim`/`$resolve`; `pemit()` notifications |
| 225 | Player-to-player notes | now | notes dict attrs; `secret` flag for staff-only layers, `visual` for public profile |
| 226 | Mentor program | now | mentor tag + pairing attrs; `ON_CONNECT` nudges |
| 227 | Event calendar & RSVP | now | event attrs + `$rsvp`; `on_tick` reminders `pemit()` attendees |
| 228 | Leaderboards | now | `on_tick` aggregation via `search_world()` over stat attrs; cached board attr |
| 229 | Login streak rewards | now | `ON_CONNECT` date math vs last-login attr; grace window; perks via `create_obj`/`adjust_credits` |

### 21. Web & External Integration (230–239)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 230 | Web character profiles | **major** | **G1 web layer**: HTTP site serving world data |
| 231 | REST API endpoints | **major** | **G1 web layer**: API endpoints + auth + serialization |
| 232 | Discord bridge | **major** | **G5 external bridges**: bidirectional chat-bridge service |
| 233 | Webhooks on events | **small** | **G6 HTTP connectors**: config-declared event→webhook POST sink |
| 234 | Website who widget | **major** | **G1 web layer** (depends on the site existing) |
| 235 | JSON content packs | now | `@pack` / `realm pack import` — packs are a shipped feature; tour + authoring |
| 236 | Email notifications | **major** | **G5 external bridges**: SMTP delivery + digest batching |
| 237 | Web-based build forms | **major** | **G1 web layer**: web → game content pipeline |
| 238 | In-game news from RSS | **small** | **G6 HTTP connectors**: allowlisted feed-fetch behavior filling attrs; rendering is softcode |
| 239 | Character export | **major** | **G1 web layer**: player-facing downloads (staff-side `realm export` CLI exists) |

### 22. Scripting & Extensibility (240–250)

| # | Item | Class | Primitives / gap |
|---|---|---|---|
| 240 | Builder trigger system | now | *the* feature: `$`-commands, `^listen`, `ON_<EVENT>`, `on_tick` — flagship tutorial |
| 241 | Response scripting in data | now | packs/area files carry `listen_*`/`cmd_*` attrs; import installs NPC responses |
| 242 | Inline functions in text | now | `[[…]]` inline evaluation with `viewer` binding (`rand`/`now`/conditionals in descs) |
| 243 | Object-verb pattern | now | `$`-commands on objects, gated by the `use` lock — Penn-style, native |
| 244 | Player macros | now | personal gadget `$`-commands running multi-line script bodies; sandbox limits are the safeguard |
| 245 | Event bus tour | now | two-pass propagation, `ON_<EVENT>` suffix matching, `act()` custom events, action-category tags |
| 246 | Hot-reload workflow | now | reframed: softcode is always live; `@reload` re-reads data rules; only engine code needs restart |
| 247 | Testing your game | now | `realm.testing` Simulator harness + pytest; scripted sessions, virtual-clock waits |
| 248 | Custom input handling | now | `session.prompt()/choose()/confirm()` (hardcode) + softcode `prompt()` with `persistent=True` |
| 249 | Writing a contrib | now | content packs (`pack.json`) + area files as reusable, versioned modules |
| 250 | Restricted player scripting | now | the sandbox *is* this: AST validation, CPU/call/output limits, `controls()` authority — capstone tour |

---

## Ranked engine gaps

Deduped from the rows above. Size: S = a day-ish, M = a week-ish,
L = a real subsystem.

| Rank | Gap | What it is | Unblocks | Count | Size |
|---|---|---|---|---|---|
| G1 | **Web layer** | HTTP site + REST API over the live world (views, auth, serialization, submission pipeline) | 230, 231, 234, 237, 239 | 5 | L |
| G2 | **Speech pipeline hooks** — ~~gap~~ **MOSTLY SHIPPED 2026-07-17**: `register_speech_renderer(fn)` transforms the spoken `{speech}` body per listener (lands **79 languages**, **139 intoxication**), and `db.voice_as` overrides the speech `{actor}` attribution (lands **84 voice disguise**). Still open: **80 overheard whispers** needs the whisper ROOM line to carry a body it currently lacks. | per-listener transform + speaker-attribution override + leak rolls in `do_say`/`do_whisper` delivery (builtins dispatch before softcode, so speech can't be intercepted today) | 80 | 1 | S |
| G3 | **Identity layer** — ~~gap~~ **SHIPPED 2026-07-17**: `register_name_resolver(fn)` is the per-viewer naming (sdesc/recog/disguise) seam in `perceived_name`, and `pose /name` renders emote references per viewer. Lands **85, 133, 134**. (A softcode `set_name()` was not needed — the resolver chain covers apparent-name.) | per-viewer naming (sdesc/recog) hook in `perceived_name` + a softcode `set_name()`/apparent-name | — | 0 | done |
| G4 | **Presence & session surface** | `online_players()`/`idle_seconds()` softcode functions, perception-aware `who`, auto-AFK hook | 180, 188, 197 | 3 | S |
| G5 | **External bridges** | Discord relay + SMTP email digests (long-lived external-service connectors) | 232, 236 | 2 | L |
| G6 | **HTTP connector primitives** | config-declared event→webhook POST sink; allowlisted feed-fetch behavior | 233, 238 | 2 | M |
| G7 | **Per-session render options** | screenreader flag + per-player color-palette remap at the protocol edge (beyond `color on/off`) | 194, 195 | 2 | S |
| G8 | **Ammo & reload** | ranged attacks consume weapon `db.ammo`; `reload` maneuver in the ruleset vocabulary | 110 | 1 | S |
| G9 | **Hit locations** | called-shot maneuver + penalty/effect table in the GURPS ruleset | 116 | 1 | S |
| G10 | **Status prompt line** | per-player prompt template appended after command output | 187 | 1 | S |
| G11 | **MXP links** | MXP link markup rendered at the telnet edge | 192 | 1 | S |
| G12 | **Ban/sitelock registry** | account/IP bans with expiry + audit in AuthService | 178 | 1 | S |
| G13 | **Command flood throttle** | per-session rate limiter with backoff | 185 | 1 | S |

Worth noting (not blocking any item, but recurring): a dedicated
**Master Room** (global `$`-command search is a `TODO` in
`get_search_objects`) would replace the tag-every-room `zone:world`
workaround that ~10 `[now]` items lean on; and **persistent `wait()`**
would simplify (not enable — patterns exist) items 29, 56, 148, 152.

## Arc readiness

**All five arcs are 100% SOFTCODE-NOW — each can run end-to-end,
in-game, today.**

| Arc | Items | Verdict |
|---|---|---|
| First builds | 5 → 1 → 2 → 14 → 25 | ✅ all now — oracle/slots/vending/container/door on `$`-commands, `ON_PAYMENT`, wards, locks |
| The heist | 27 → 16 → 49 → 54 → 48 → 160 | ✅ all now — perception, `prompt()` codes, `ON_ENTER` traps, listen-relays, gas spread, stealth contests |
| Living NPCs | 60 → 64 → 67 → 68 → 71 | ✅ all now — stock behaviors, `^listen`, `prompt()` dialogue, clock-driven behavior swaps, zone-master witnesses |
| A working economy | 86 → 63 → 87 → 89 → 92 | ✅ all now — credits kernel, shopkeeper behavior, ledger objects, `on_tick` settlement/drift |
| Softcode for builders | 243 → 240 → 241 → 242 → 250 | ✅ all now — this arc is a tour of REALM's native feature set |

## Recommended implementation waves

Honoring dependencies: arcs first (zero gaps), then all-`[now]`
categories, then gap-gated items grouped so each engine gap ships once
and unlocks its whole cluster.

1. **Wave 1 — The five arcs (26 tutorials).** All `[now]`. Proves the
   softcode-first thesis end-to-end and produces the teaching
   vocabulary (triggers → wards → wizards → behaviors → masters) every
   later tutorial reuses.
2. **Wave 2 — Foundations (categories 1–5, items 1–59).** All `[now]`.
   Gadgets, containers, doors, rooms, traps — one small build each,
   ordered easy → hard within each category.
3. **Wave 3 — Living systems (categories 6, 8, 9, 11, 13, 14, 19).**
   All `[now]` (NPCs, economy, games, crafting, time, movement,
   puzzles). These compose Wave 2 primitives into systems.
4. **Wave 4 — Characters, quests, social, building, staff, UI
   (remaining `[now]` items in categories 7, 10, 12, 15, 16, 17, 18,
   20, 22 + item 235).** Includes the capstones (108 casino, 164
   spaceship, 216 escape room, 250 sandbox tour).
5. **Wave 5 — Small-gap unlocks.** ~~G2 (→ 79, 84, 139)~~ and ~~G3 (→ 85,
   133, 134)~~ shipped 2026-07-17. Remaining, in bang-for-buck order:
   G4 (→ 180, 188, 197), the last of G2 (→ 80 overheard whispers),
   G7 (→ 194, 195), then the singletons G8–G13 (→ 110, 116, 187, 192,
   178, 185) and G6 (→ 233, 238). Each gap's tutorial lands with the
   engine change (docs discipline: same change).
6. **Wave 6 — Web & external (G1, G5).** 230, 231, 234, 237, 239, 232,
   236. A deliberate, design-first subsystem effort; everything else in
   the showcase is independent of it.
