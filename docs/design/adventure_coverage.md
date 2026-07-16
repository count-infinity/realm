# Adventure Coverage Matrix: can REALM run the classics?

Status: LIVING DOCUMENT (2026-07-15). Nine published TTRPG one-shots /
starter modules, distilled to their load-bearing mechanics, each graded
against the engine as it stands. Sourced from module knowledge, not a
web crawl — mechanics are the famous ones, paraphrased.

Grades:
- **YES** — engine mechanism exists; the row names it.
- **SOFT** — no dedicated mechanism, but honestly buildable today in
  softcode/behaviors without engine changes (this is a *pass* — the
  whole thesis is that games are softcode).
- **PARTIAL** — buildable but with a real seam missing; gap named.
- **NO** — engine change required; gap named.

Summary (88 rows): originally **38 YES / 30 SOFT / 17 PARTIAL / 9 NO**;
after the 2026-07-04 modifier pipeline: **42 YES / 29 SOFT / 14 PARTIAL / 9 NO**;
after dispositions (same day): **44 YES / 29 SOFT / 12 PARTIAL / 9 NO**;
after ranged combat (2026-07-05): **46 YES / 29 SOFT / 12 PARTIAL / 7 NO**;
after the economy kit (same day): **50 YES / 28 SOFT / 9 PARTIAL / 7 NO**;
after followers/party (same day): **51 YES / 28 SOFT / 9 PARTIAL / 6 NO**;
after @force/possession (2026-07-05): **53 YES / 28 SOFT / 8 PARTIAL / 5 NO**;
current tables (2026-07-15 audit): **61 YES / 19 SOFT / 6 PARTIAL / 1 NO**
(+1 YES/SOFT) — the progression figures above were tallied against a
pre-commit draft and do not sum against the committed tables.
Wilderness cells + instanced areas (realm/core/wilderness.py,
realm/core/instances.py) shipped since: no grade changes — they strengthen
existing YES rows, addressing no open gap.
2026-07-16: tutorial Act III (Saltmarsh) exercises the social kit
end-to-end (NPC-piloted vehicle sequences, disposition-priced shops,
skill_def rules-data, cast/ward mind magic, prompt()-driven quest
gates) — plus two small seams closed: `give` now accepts NPC
recipients (ON_RECEIVE was already recipient-agnostic; quest hand-ins
and shop stocking work as typed), and `disposition_boost` joined the
softcode `apply_effect` allowlist (charm effects that wear off are
one line). No grade changes; several SOFT rows (bribes, gifts, court
audiences) got easier to build honestly.
Gap clusters at the bottom feed BACKLOG.md.

---

## 1. AD&D — B2 The Keep on the Borderlands (Caves of Chaos)

| Mechanic | Covered? | How / gap |
|---|---|---|
| Home-base keep with shops, inn, banker | YES | Economy kit (2026-07-05): db.credits + ShopkeeperBehavior (stock = inventory, disposition-priced) + list/buy/sell/pay commands. |
| Wandering monsters (random encounter checks) | YES | SpawnerBehavior + WanderingBehavior with zone confinement; encounter chance = wander_chance. |
| Tribal caves with organized defenders | YES | zone: tags, GuardBehavior, PatrolBehavior, spawners per cave. |
| Guards call for reinforcements when alarm raised | SOFT | `^listen` on guards + `trigger`/`teleport_obj` chains; no dedicated alert-zone system (Story 3 backlog). |
| Morale — monsters flee when losing | YES | Strategy rules (`!me.hp_percent < 30 → flee`) — wimpy IS morale. |
| Reaction rolls (parley with kobolds) | YES | reaction_roll() — 3d6 high-good, MEMOIZED per (npc, character); `consider` command; softcode reaction_roll(). (2026-07-04) |
| Secret doors found by searching | YES | `hidden` tag + search command + Observation checks. |
| Pit traps, spiked | YES | Proven live: room ON_ENTER `damage(enactor, N)` through the death path. |
| Poison (save or suffer) | YES | skill/HT check + DamageOverTimeBehavior. |
| Ogre bribed with treasure | YES | `pay 25 to ogre` propagates event:payment → ON_PAYMENT softcode judges the bribe and drops `hostile` (tested). |
| Prisoners to rescue (escort them out) | YES | `db.following` + room-local cascade in move_through_exit; NPC escorts agree via softcode `set_attr(me,'following','%#')` — tested end-to-end. (2026-07-05) |
| Torch/lantern light in dark caves | YES | Carried `light`-tagged object lights the room (perception.py). |
| Torches burn out over time | SOFT | script_ticker/TimedEffect on the torch removes its `light` tag. |
| Treasure + XP for recovering it | YES/SOFT | Loot from corpses yes; quest XP = softcode `set_attr` on character_points. |

## 2. AD&D — S1 Tomb of Horrors

| Mechanic | Covered? | How / gap |
|---|---|---|
| Instant-death traps (sphere of annihilation) | YES | `damage(enactor, 999)` → handle_death; players fall unconscious (engine default) — perma-death is a game-policy knob a system could set. |
| Riddle-based progression (Acererak's poem) | YES | `$`-command / `^listen` triggers on speaking answers; proven pattern. |
| Secret/concealed doors everywhere | YES | hidden exits + conceal_difficulty search checks (wall safe pattern). |
| One-way teleporters, misdirection | YES | ON_ENTER + `teleport_obj(enactor, dest)` — teleport lock consulted. |
| False floors / collapsing corridors | SOFT | ON_ENTER script: skill check → damage + teleport to pit room. |
| Cursed items (drain when touched) | SOFT | ON_GET trigger: `damage`/`set_attr` — the item bites when picked up. |
| Gaze attack — save or die (Acererak) | SOFT | contest/check on look... LOOK fires ON_LOOK triggers; script damages on failed check. |
| Gargoyle guardian animates when approached | YES | AggressiveBehavior or ON_ENTER `start_combat(me, enactor)`. |
| Item destruction (gems crumble, weapons dissolve) | YES | `destroy_obj` from scripts. |
| Character drained of levels/attributes | SOFT | `set_attr` on strength/skills — no resistance framework, straight softcode. |
| Party mapping/careful exploration rewarded | YES | Room/exit model, hidden exits, examine — the medium is the mechanic. |

## 3. D&D 5e — Death House (Curse of Strahd intro)

| Mechanic | Covered? | How / gap |
|---|---|---|
| Ghost children NPCs with dialogue | YES | `$ask *`/`^listen` softcode dialogue; per-looker visibility for ghosts (`invisible`/`see_invisible`). |
| Possession (ghost controls a PC) | YES | @force / softcode force() through the real dispatcher; possession is OPT-IN via the victim's control lock (`@lock/control me = caller.has_tag('ghost')`). (2026-07-05) |
| Creepy mood escalation on a timer | YES | script_ticker on rooms + `wait` chains for staged emits. |
| House refuses exit (doors seal) | YES | Scripted `set_lock`/`closed` tags — proven live (script-sealed coin). |
| Animated armor / mimic furniture | YES | Innocuous object + ON_GET/ON_ENTER `start_combat`; spawner prototype. |
| Cult ritual demands a sacrifice | SOFT | Room ON_EVENT scripts + counters in room.db. |
| Shambling mound boss fight | YES | Beat combat, strategies, HealerBehavior-style adds. |
| Fear/madness effects (disadvantage) | YES | ModifierEffectBehavior + check_mods → condition_modifier auto-applies to every roll (2026-07-04). |
| Smoke/haze obscuring vision | PARTIAL | Observation penalties via check_mods; @detail gives per-viewer conditional text; graded render concealment still missing. |
| Child corpses reveal backstory items | YES | Containers, examine, hidden objects. |

## 4. D&D 5e — A Wild Sheep Chase

| Mechanic | Covered? | How / gap |
|---|---|---|
| Polymorphed wizard (sheep is a person) | SOFT | Name/description swap via set_attr + get_display_name; no transformation framework. |
| Item that lets the sheep talk (scroll) | SOFT | ON_USE grants a tag; `$`-commands on the sheep gated by `use` lock. |
| Chase through town streets | PARTIAL | Movement + contests can fake it; no chase subsystem (opposed movement over rounds). GAP if chases matter. |
| Wizard tower with animated furniture | YES | Spawners + aggressive prototypes. |
| Shapeshifted villain reveal | YES | Disguise via get_display_name hook + reveal by tag flip (Story 2 will formalize). |
| Comedic reaction tables | SOFT | rand() + pemit tables in softcode. |

## 5. GURPS — Caravan to Ein Arris

| Mechanic | Covered? | How / gap |
|---|---|---|
| Hired as caravan guards (job + pay) | YES | Wages = softcode `transfer_credits`/`adjust_credits`; balances via `credits` command. |
| Long journey in stages with events | YES | Zone rooms + tram-pattern transit + staged ON_ENTER events. |
| Bandit ambush at a ford | YES | Spawners + hostile auto-combat + terrain room. |
| Night watch rotations (who's awake?) | SOFT | wait/on_tick schedules; no sleep system. |
| Fast-talk past city guards | YES | `fasttalk` command: contest → DispositionBoostBehavior (+2, WEARS OFF, caught = -1 permanent); GuardBehavior waves through disposition >= 2. (2026-07-04) |
| Disguise to infiltrate the villa | PARTIAL | get_display_name seam exists; Watchful-consults-disguise is Story 2. |
| Fright checks | YES | check vs will; failure applies ModifierEffectBehavior (fear, -N all) — aftermath is automatic now. |
| Fatigue from forced march | YES | ticker writes db.check_mods['fatigue'] (or a permanent ModifierEffect); auto-applied to all checks. |
| Betrayal by an NPC mid-journey | YES | Tag flip hostile + start_combat from a triggered script. |
| Climactic duel (single combat, honor rules) | YES | Beat combat + maneuvers (AoA/AoD/Feint are literally implemented). |
| First aid after fights | YES | firstaid command + HealerBehavior + heal(). |

## 6. GURPS — Harkwood

| Mechanic | Covered? | How / gap |
|---|---|---|
| Tournament — jousting/melee with rules | PARTIAL | Combat yes; formal non-lethal victory conditions (yield, points) need a softcode referee — doable, fiddly. |
| Social standing / knightly reputation | PARTIAL | Per-NPC dispositions + default_disposition DONE; herald-style faction/status propagation remains. |
| Kidnapping plot investigation | YES | Clue objects, hidden things, $ask dialogue, Observation checks. |
| Bandits in the forest (hex crawl-ish) | YES | Zone wander + spawners; wilderness regions now give true coordinate hex-crawl cells with cell_populate spawning. |
| Baron's court audience (etiquette rolls) | SOFT | check('savoir_faire') via $-command scene. |
| Archery contest | YES | shoot/aim maneuvers + range bands (2026-07-05); contest scoring = softcode referee. |

## 7. Call of Cthulhu — The Haunting

| Mechanic | Covered? | How / gap |
|---|---|---|
| Library/newspaper research phase | YES | Rooms as archives, hidden clue objects, and @detail skill-gated description reveals (`check('library_use') -> ...`). |
| Sanity meter eroded by scares | SOFT | sanity attr + softcode fright events; thresholds trigger effects. |
| Phobia/temporary madness effects | YES | check_mods auto-penalties + force() for compelled actions. |
| Haunted-house room-by-room dread | YES | ON_ENTER emits, script_ticker whispers, per-viewer perception. |
| Poltergeist throws objects | YES | Scripted `teleport_obj` + damage + emits. |
| The bed that attacks | YES | ON_EVENT start_combat from furniture. |
| Corbitt's journal (multi-clue chain) | YES | Readable items (description/examine), containers, locked chest + key. |
| Boarded attic needing STR to open | YES | Forceable = check_skill on the exit... actually `check_skill` gates exits by skill; STR check = attribute default. |
| Final banishment ritual (specific steps in order) | SOFT | Room db counters + $-command sequence — classic MUSH puzzle code. |

## 8. Traveller — Death Station

| Mechanic | Covered? | How / gap |
|---|---|---|
| Derelict lab ship, airlocks and vacc suits | YES | `grants_tags` suit + rooms lethal without tag (ticker damage) — nightvision-goggles pattern generalizes. |
| Ship computer terminals with logs | YES | ON_USE softcode terminals (power panel pattern). |
| Medical horror — infected crew attack | YES | Spawners + AggressiveBehavior; infection = ON_DAMAGE trigger (STANDARD_EVENTS includes DAMAGE; combat propagates combat:on_damage) applying DamageOverTimeBehavior. |
| Zero-G sections (skill checks to move) | SOFT | check_skill exits with freefall skill. |
| Locked labs with keycards | YES | key_id items + electronic lock_skill. |
| Ship systems to repair (engineering checks) | SOFT | $repair softcode + attr state machines. |
| Air running out (global timer) | YES | wait chains / zone ticker escalating damage. |
| Loot: salvage value | YES | db.value on items + `sell` to any ShopkeeperBehavior NPC. |

## 9. Shadowrun — Food Fight (Stuffer Shack)

| Mechanic | Covered? | How / gap |
|---|---|---|
| Firefight in a convenience store | YES | shoot/aim/cover/close/withdraw + range bands + wielded guns (2026-07-05). Bursts/ammo tracking remain softcode attrs. |
| Innocent bystanders as complications | SOFT | Non-combatant NPCs with flee strategies; collateral = proximity damage. |
| Grenade — area damage | SOFT | Script: damage every `player`/`npc` in room — proximity authority is literally room-scoped. |
| Matrix/decking minigame | NO | Would be a bespoke softcode subgame; no engine support and none planned — softcode CAN express it as rooms-as-hosts. |
| Street cred / faction reputation | PARTIAL | Per-NPC dispositions DONE; faction-wide reputation (one deed moves a whole gang) still needs faction propagation. |
| Ammo tracking | SOFT | attrs + softcode decrement; no dedicated system. |
| Contacts & legwork phase | YES | NPC dialogue triggers + locked info behind checks. |

## 10. Mothership — The Haunting of Ypsilon 14

| Mechanic | Covered? | How / gap |
|---|---|---|
| Invisible stalking monster | YES | `invisible` tag + see_invisible counters + stealth contests + hostile ambush. |
| Panic/stress mechanic | YES | stress thresholds apply ModifierEffects; penalties aggregate automatically. |
| Crew NPCs with schedules & secrets | YES | script_ticker routines + PatrolBehavior + dialogue triggers. |
| Airlock murder option (vent the monster) | YES | ON_USE lever: teleport_obj target → space room → lethal ticker. |
| Countdown to self-destruct finale | YES | wait chains + zone-wide emits (proven pattern). |
| Hiding from the creature | YES | hide/search stealth contests, Watchful spotting. |

---

## Gap clusters (ranked by how many rows they block)

1. ~~**Check-modifier providers**~~ **DONE 2026-07-04**: `check()`
   folds `condition_modifier(obj, skill)` (provider chain; built-in
   provider reads `db.check_mods` — softcode-writable) upstream of the
   resolver, so every ruleset inherits it. Any TimedEffectBehavior can
   carry `check_mods`; `ModifierEffectBehavior` is the pure-debuff
   shape; softcode gets `apply_effect`/`remove_effect` (proximity
   authority). The banshee wail is one line of softcode now.
2. ~~**Ranged combat**~~ **DONE 2026-07-05**: range bands on the
   encounter (0 = engaged, 1 = at range; int field, more bands later),
   base maneuvers shoot/aim/close/withdraw/cover (engine vocabulary —
   D20 archery gets them free), wielded weapons (`wield`/`unwield`,
   `wielded` tag; melee refuses to club with a rifle), aim = +Acc
   stacking to Acc+2 consumed by the shot, cover objects (-2 vs
   ranged), close-quarters -2, weapon skill_type honored
   (skill_guns). NPC snipers = `[["", "shoot"]]` strategy. Remaining
   flavor: ammo/reload, bursts, cross-room sniping (encounters are
   per-room by design).
3. ~~**Disposition/reaction states**~~ **MOSTLY DONE 2026-07-04**:
   `realm/core/disposition.py` (db.dispositions per NPC, GURPS bands,
   memoized reaction_roll), consider/persuade/fasttalk commands,
   DispositionBoostBehavior (fast-talk wears off), Guard/Aggressive
   consult it, softcode disposition()/adjust_disposition()/
   reaction_roll(). Remaining from Story 2: disguise consulted by
   Watchful, faction-wide reputation propagation.
4. ~~**Economy kit**~~ **DONE 2026-07-05**: `db.credits` +
   `realm/core/economy.py` (never-negative, transfer), ShopkeeperBehavior
   (stock = inventory, prices from db.value × markup × DISPOSITION
   factor — persuade the merchant, get a discount), list/buy/sell/pay/
   credits commands, `event:payment` → ON_PAYMENT softcode (bribes),
   GameSystem names the currency (credits vs gold), softcode
   credits/adjust_credits/transfer_credits (authority-gated).
5. ~~**Followers/party**~~ **DONE 2026-07-05**: `db.following` (one
   attr, softcode-settable), follow/unfollow/party commands, room-local
   follower cascade in move_through_exit (chains cascade, cycles
   self-resolve, locks judge each follower separately, fleeing breaks
   the chain), party = connected follow component in the room, CP
   awards split across party members present.
6. ~~**@force / possession**~~ **DONE 2026-07-05**: PuppetSession +
   force_command through the REAL dispatcher (target's own permissions
   apply — NPCs are player-level citizens, never builder+); authority =
   controls(); player possession is opt-in via control lock; softcode
   force() queued; puppet chains depth-capped. Bonus: closed a
   controls() hole (builders no longer control unowned players).
7. **Chase subsystem** (1-2 rows): opposed movement contest over
   rounds; genuinely optional — contests approximate it.

Everything else the classics need, the engine already speaks —
mostly through the softcode surface, which is the point.
