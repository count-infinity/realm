# AresMUSH vs REALM

A reference comparison against **AresMUSH** (the modern Ruby MUSH platform,
~1500 `.rb` files: `engine/aresmush/` = the kernel — dispatcher, plugin
loader, Ohm/Redis models, Sinatra API server; `plugins/` = ~35 first-party
plugins including the FS3 combat system, scenes, jobs, forum, chargen,
website/wiki). Read from the actual source, not the marketing. It maps what
AresMUSH does onto what REALM does, and flags what's worth stealing.

AresMUSH is the odd sibling in REALM's reference set. CoffeeMud, PennMUSH,
LambdaMOO, and Evennia are all *engines a builder lives inside*. AresMUSH is
a **headless game service with a web app bolted on the front** — the thing a
player actually touches is usually a browser, not a telnet client. That
makes it the sharpest mirror for one specific REALM question: how far should
the game logic be decoupled from the telnet stream and exposed as an API?

## The one deep difference

**AresMUSH's game lives in compiled host-language modules behind a web API;
REALM's game lives as sandboxed data + softcode inside the world DB, driven
through a telnet-first propagation kernel.** This is one axis, not two:
*where the game logic physically lives, and who is allowed to change it.*

To add a feature to AresMUSH you write **Ruby** — a plugin is a plain module
with class-method hooks (`get_cmd_handler`, `get_event_handler`,
`get_web_request_handler`) that the loader discovers by `respond_to?`
(`engine/aresmush/commands/dispatcher.rb:91-99`,
`plugin/plugin_manager.rb:19-67`), plus command classes that mix in
`CommandHandler` (`plugin/command_handler.rb`) — and you **restart the
server** to load it. There is no in-world programming surface at all: no
softcode, no `@dig`, no builders typing code into objects. Content authors
are Ruby developers with filesystem and git access. The "no coding
experience" promise in the README is about *running a game from YAML config*,
not extending one.

To add a feature to REALM you ship **data** (`class_def`/`skill_def`/action
packs) and **sandboxed softcode** (`$`-commands, `^listen`, `ON_<EVENT>`,
`on_tick`) that lives in object attributes in SQLite and runs live, by
in-game builders, with no code deploy — the two-tier-trust model, with
`@softcode_function` native bindings as the escape hatch. AresMUSH has
exactly *one* trust tier: you either commit Ruby to the server or you don't
play.

The second half of the axis is the client. AresMUSH's engine is a **JSON API
first** and a MUSH second: a Sinatra server (`web/engine_api_server.rb:30`)
runs on the same EventMachine reactor as the telnet listener, every plugin
exposes web request handlers (267 of them across the tree), and the canonical
UI is a **separate Ember SPA** (not in this repo — it talks to the engine
over `POST /request` with `{cmd, args, api_key, auth}`,
`web_request.rb:5-11`). Telnet and web are peers: they coexist in one
`@clients` list distinguished only by `is_web_client?`
(`client/client_monitor.rb:39-45`). REALM inverts this: the two-pass action
propagation stream *is* the engine, telnet is the primary surface, and
GMCP/WebSocket is an OOB sidecar on top of it. Nearly every row below flows
from this one axis.

## 1. Architecture & dispatch

| | AresMUSH | REALM |
|---|---|---|
| Kernel language | Ruby on EventMachine reactor (single-threaded, `next_tick` command queue, `dispatcher.rb:21-26`) | Python on asyncio + one global tick heartbeat |
| Game logic lives in | Ruby files on the server install (`plugins/*/`) | data packs + sandboxed softcode in the SQLite DB |
| Command dispatch | crack `root/switch args` (`commands/command.rb`), then **linear scan** of sorted plugins calling `get_cmd_handler` until one returns a class (`dispatcher.rb:91-102`) | command table + `$`-commands on objects + verb cores |
| Command definition | a class mixing in `CommandHandler`; template method `on_command → parse_args → error_check → handle` (`plugin/command_handler.rb:15-98`) | Python `Command` classes + in-DB `$`-commands |
| Event model | `queue_event` → linear scan of plugins calling `get_event_handler(name)`; **every** subscriber runs (`dispatcher.rb:113-134`) | two-pass propagation stream + `ON_<EVENT>`/`^listen` triggers |
| Extensibility unit | a plugin = Ruby module + command/event/web/config/locale/help files, discovered by folder (`plugin_manager.rb:31-67`) | a data pack + softcode, loaded into the world |
| Service access | `Global` service-locator module (`global.rb:28`: dispatcher, config_reader, plugin_manager, client_monitor, locale, notifier…) | core singletons + `controls()` authority |
| Deploy a change | edit Ruby, restart server | edit data/softcode in-world, live |

The AresMUSH dispatch model is strikingly simple and worth naming: **there is
no command registry**. `get_cmd_handler` is a hand-written `case cmd.root …
when cmd.switch` statement per plugin (see `fs3combat.rb:17-154` — a 130-line
switch mapping `combat/*` switches to handler classes). Dispatch is O(plugins)
linear scan, first-match-wins, ordered so `Custom` loads last and can
override (`plugin_manager.rb:20-21,185-187`). It's crude but completely
legible — you can read exactly what any input does.

## 2. Extensibility model

| | AresMUSH | REALM |
|---|---|---|
| Who extends | Ruby developers with server + git access | in-game builders (softcode) + pack authors (data) |
| How | write plugin module, drop in `plugins/`, restart | write softcode into objects / load a data pack, live |
| Custom hooks | designated `custom/` plugin (loads last) + per-plugin `custom_hooks.rb` extension points (e.g. `fs3combat/custom_hooks.rb`) | tags + behaviors + `@softcode_function` native bindings |
| Sandbox | **none** — plugin Ruby is trusted host code | `safe_eval` denylist-Python sandbox for softcode |
| Config surface | deep-merge of all `game/config/**/*.yml` (`config/config_reader.rb:67-92`, `hash_ext.rb:11-19`) | data-driven defs + settings |
| Runtime edit | none for logic; config reloadable | softcode and data editable in-world |

AresMUSH's answer to "let users customize without touching core" is **YAML
config + a `custom` plugin**, not a scripting language. A huge amount of game
behavior is data-driven from config: chargen stages (`chargen.yml`),
achievements, NPC stat blocks, FS3 weapons/armor/hit-locations, damage
tables, role permission strings. That is genuinely REALM-adjacent
philosophy — but the moment a game needs *new logic*, AresMUSH requires Ruby
and a restart, where REALM stays in-world.

## 3. Combat — FS3 as a pluggable narrative system

FS3 (`plugins/fs3combat` + `plugins/fs3skills`) is the most valuable single
artifact in the codebase: a complete, opinionated, **narrative** combat
system built as an ordinary plugin.

| | AresMUSH FS3 | REALM |
|---|---|---|
| Dice core | roll N d8, count ≥6 as successes, >half 1s = botch (`fs3skills/helpers/rolls.rb:22-42`) | GameSystem-swappable dice/RNG in CORE |
| Resolution | **opposed roll, net-success margin → narrative outcome** (`fs3combat/helpers/actions_helper.rb:314-368`) | resolution primitives in CORE, rules in GAME |
| Damage | abstracted to 4 wound tiers (GRAZE/FLESH/IMPAIR/INCAP) via config `damage_table`; hit-locations + armor-penetration as bucketed abstractions, **not HP** (`actions_helper.rb:189-259,394-468`) | GAME-defined (GURPS/D20 packs) |
| Action model | each action is a **class** — `AttackAction < CombatAction` with `prepare`(validate)/`resolve`(return message array)/`print_action` (`fs3combat/actions/attack_action.rb`, base `combat_action.rb`) | actions are data + softcode |
| Action dispatch | persisted on the combatant as a `(class_name_string, args_string)` pair, re-instantiated and re-`prepare`d on every access (`combatant.rb:66-84,207-211`) | action defs in packs |
| Turn model | simultaneous-resolution, initiative-ordered, **GM-gated** per turn; one-shot background resolver (`general_helper.rb:186-247`) | tick scheduler + propagation |
| Pose coupling | poses drive an "everyone posed" *gate*, not the mechanics — combat tracks pose-completeness via the scene `PoseEvent` (`events/pose_handler.rb:3-26`) | `^listen`/`ON_<EVENT>` triggers |
| Output | `resolve` returns i18n message *keys*; the turn resolver joins them and emits as GM-narrated prose into the scene log (`general_helper.rb:59-86`) | per-viewer messages on the propagation stream |
| Extras | vehicles (crew-hit shrapnel), mounts (hit-the-mount, fall damage), NPCs with a priority-heuristic AI (`actions_helper.rb:142-175`) | GAME content |

The design lesson, not the code: FS3 is **narrative-first** — it exists to
produce *prose describing what happened* that a human then poses around, not
to run a tactical simulation. The whole pipeline (`prepare` validates,
`resolve` mutates state and returns strings, the turn engine narrates) is a
clean template REALM could mirror in data. But note the coupling: FS3 is
welded to the scene system, the pose event, Ohm models, and the web combat
HUD. It is a *reference design*, not a droppable module.

## 4. Community & social systems

This is where AresMUSH is deepest and REALM is thinnest. These are mature,
web-integrated, first-class subsystems — and they are almost entirely **game
content**, not engine.

| System | AresMUSH | REALM |
|---|---|---|
| **Scenes / pose-logging** | signature feature. `Scene` Ohm model with poses, versioned logs, participants/watchers/likers, plots, content tags, web-sharing (`scenes/public/scene.rb:3-56`). `add_to_scene` auto-creates a `ScenePose`, auto-adds the poser as participant, marks unread, pushes **per-viewer** web notifications (`scenes_api.rb:21-62`) | none — `^listen`/events exist, no RP archival |
| Shared logic | `emit_pose` is one module function called by **both** the telnet `pose` command *and* the web pose handler (`scenes/helpers/posing.rb:35-60`, telnet `pose_cmd.rb:44`, web `add_scene_pose_handler.rb:53`) | per-viewer messaging on propagation stream |
| Jobs / tickets | `Job` model: category, status, replies, participants, assigned_to, indexed by category/status (`jobs/public/job.rb`); `JobCategory` has a `roles` set for per-category access. **Central triage hub** — chargen approval, roster claims, *and* abuse reports from scenes/channels/page/mail all funnel into `Jobs.create_job` | none |
| BBS / forum | full bulletin board: boards, posts, replies, read-trackers, prefs (`forum/public/bbs_*.rb`) | none |
| Mail | in-game mail with compositions/messages (`mail/public/mail_*.rb`) | none |
| Channels | `Channel` model, role-gated join/talk, message history, aliases, **Discord webhook bridging** (`channels/public/channel.rb:1-40`) | structured log channels; no player chat |
| Achievements | config-declared, merged per-plugin (`plugin_manager.rb:157-170`, `achievements/achievements.rb:13-15`) | none |
| Chargen | dual-mode (web + telnet, same data), **YAML-defined stages** (`chargen.yml`), `save_char` aggregates every subsystem (`chargen/helpers.rb:67-152`), submit → Job → staff approval → `approved` role (`chargen/helpers.rb:154-202`) | none |
| Roster | claimable off-screen characters (`idle` plugin); claim → app Job or instant welcome (`idle/helpers.rb:71-124`) | none |
| Wiki | `WikiPage` Ohm model, Markdown via Redcarpet + Wikidot compat, 15-min edit locks, versioned, web-CRUD (`website/public/wiki_page.rb`, `wiki_markdown/`) | none |

The pattern under *all* of these: **business logic is a module function**
(`Scenes.emit_pose`, `Jobs.create_job`, `Chargen.approve_char`) that thin
telnet handlers and thin web handlers both call. That decoupling — not the
web framework — is the reusable idea.

## 5. Persistence

| | AresMUSH | REALM |
|---|---|---|
| Datastore | **Redis via Ohm** (Object-Hash-Mapping); *not* MongoDB (`database.rb:5-16`, `Gemfile:15`) | SQLite (WAL) + in-memory store, incremental dirty-sweep |
| Model base | `< Ohm::Model` + `ObjectModel` mixin → DataTypes/Callbacks/Timestamps (`models/object_model.rb:1-52`) | `GameObject` (uuid, tags, attrs, behaviors, locks) |
| Schema | per-model `attribute`/`reference`/`collection`/`set`/`index`; non-scalars JSON-serialized into Redis strings (`models/ohm_data_types.rb:24-40`) | schemaless attrs + tags; class via data defs |
| Cross-cutting fields | **plugins reopen `class Character`** to add their own columns (chargen adds `chargen_stage`; profile adds `profile`; demographics adds `birthdate`) | composition via tags + behaviors + packs, no class reopening |
| Query | Redis index sets; `find(name_upcase: …)`, `FindByName` (`models/find_by_name.rb`) | `search_world` + tag/attr queries |
| Persistence model | live objects *are* Redis-backed; every `update` writes through | incremental sweep of dirty objects |

Two honest notes. (1) AresMUSH stores the **entire game in RAM-backed
Redis** — fast, but the working set must fit in memory, and there's no rich
query layer (it's key/value + index sets). (2) The **class-reopening**
pattern for cross-plugin fields is the exact thing REALM's tags+behaviors
composition is designed to avoid — it's convenient in Ruby but means a
character's shape is smeared across a dozen plugin files.

## 6. Client / OOB surface

| | AresMUSH | REALM |
|---|---|---|
| Primary UI | **separate Ember web SPA** over JSON API (not in this repo) | telnet-first |
| Engine shape | headless service: Sinatra API + telnet + em-websocket on one reactor (`web/engine_api_server.rb`, `server.rb`) | propagation engine; telnet + GMCP + WebSocket |
| API shape | `POST /request` `{cmd, args, api_key, auth}` → same dispatcher (`engine_api_server.rb:60-92`) → `get_web_request_handler` (`dispatcher.rb:138-153`) | GMCP/WebSocket OOB payloads |
| Web auth | per-player API key + auth token; `request.enactor` resolves the char (`web_request.rb:13-26`) | session/account auth |
| Push | web clients hold a live WebSocket; `notify_web_clients` / `send_web_notification` push structured events (`client_monitor.rb:25-33`) | GMCP/WebSocket push |
| Localization | **every** user string via `t()` = Ruby I18n; per-plugin locale YAMLs merged; ships en + de (`locale/locale.rb:2-4`, `plugin_manager.rb:69-76`) | pipe-markup at the edge; no i18n layer |

## Capabilities REALM lacks

Concretely, things AresMUSH has that REALM has no analog for:

1. **A first-class RP scene/pose archival system** — automated logging,
   participant tracking, web-published, versioned, likeable scene logs. This
   is AresMUSH's whole reason to exist and REALM has nothing like it.
2. **A staff-workflow spine** — jobs/tickets that *drive* other systems
   (chargen approval, roster claims) rather than existing as a standalone
   feature.
3. **Community comms suite** — BBS, mail, role-gated channels with Discord
   bridging. (PennMUSH/MOO surveys already flagged the comms gap; AresMUSH
   shows the fully-realized version.)
4. **A web-first content platform** — wiki (Markdown, versioned, edit-locks),
   web chargen, web profiles, static-site export.
5. **Mandatory localization discipline** — no bare strings; `t()` everywhere.
6. **A shipped narrative combat system** with vehicles/mounts/NPC-AI as a
   worked reference.
7. **Per-player API keys + a documented JSON request/webhook protocol** for
   third-party integrations.

Almost all of these are **game content or a presentation platform**, not
kernel — which is the whole point of the verdict below.

## A different philosophy

- **Extend by editing the host, not the world.** AresMUSH has no in-world
  programming and no sandbox because it doesn't need one — content authors
  are trusted Ruby developers. This is the *opposite* pole from REALM's
  "Godot of MU*s" thesis. It's simpler (one language, one trust tier, real
  debuggers) and strictly less live (restart to change logic, no builder
  scripting). REALM deliberately took the harder, more powerful road.
- **The game is a service; the MUSH is a view.** REALM's kernel *is* the
  propagation stream. AresMUSH's kernel is a dispatcher + model store, and
  both telnet and web are equal clients of it. AresMUSH proves you can build
  a serious MU* where the telnet stream is not privileged — but it pays for
  it by having no rich in-world spatial/action model (no two-pass
  propagation, no reach, no controls-authority; "rooms" are thin).
- **Config-and-plugins, not data-and-softcode.** Both aim at "customize
  without forking core." AresMUSH gets ~70% there with YAML + a `custom`
  plugin, then falls back to "write Ruby." REALM gets there with data +
  sandboxed softcode and no fallback to editing the engine.
- **Narrative over simulation.** FS3 is engineered to *narrate*, not
  *simulate*. Worth internalizing regardless of what REALM steals.

## Steal-list (ranked)

Distinguishing **engine-mechanism** (could inform CORE) from **game-content**
(belongs in a pack, not the kernel). REALM must stay a data-driven
microkernel, so several tempting items are explicitly flagged as *not kernel*.

**Engine-mechanism — genuinely worth considering for CORE:**

1. **The "one business-logic function, two thin adapters" discipline.** This
   is the single most transferable idea in the codebase: `Scenes.emit_pose`
   is called identically by the telnet command and the web handler
   (`posing.rb:35`, `pose_cmd.rb:44`, `add_scene_pose_handler.rb:53`). REALM
   already has a propagation core; the lesson is to make sure the **GMCP/OOB
   surface calls the same action primitives the telnet parser does**, never a
   parallel path. Pure discipline, zero kernel bloat. Adopt.
2. **A documented, authenticated request/webhook protocol for the OOB
   surface.** AresMUSH's `{cmd, args, api_key, auth}` + per-player API key +
   `enactor` resolution (`web_request.rb`, `engine_api_server.rb:81-92`) is a
   clean, small contract. REALM's WebSocket/GMCP layer would benefit from the
   same explicit shape (request → same dispatcher → structured response) plus
   per-account API keys for third-party tools. Small, kernel-appropriate.
3. **Per-viewer structured push as a core primitive.** `notify_web_clients`
   with a predicate block that decides *who* gets the event
   (`client_monitor.rb:25-33`) maps directly onto REALM's per-viewer
   messaging — formalize "push a structured OOB event to the subset of
   sessions matching predicate P" as a CORE call. Kernel-appropriate.
4. **A minute-granular cron event as a scheduling idiom.** AresMUSH fires one
   `CronEvent` per minute and lets subscribers match a `{day, hour, minute,
   day_of_week}` spec (`cron.rb:5-23`). REALM has `on_tick`/`wait`; a
   *calendar* cron spec (as softcode-visible data) is a cheap, useful
   addition to the tick scheduler. Consider — but keep it data, not code.
5. **Mandatory localization at the emit boundary.** Not i18n itself (that's a
   lot of kernel), but the *discipline* that user-facing strings resolve
   through one indirection. REALM's pipe-markup edge is the natural hook. Low
   priority, but architecturally cheap to reserve the seam now.

**Game-content — steal the *design*, build it as a pack, keep it OUT of the
kernel:**

6. **A scene/pose RP-logging system.** The highest-value *feature* AresMUSH
   has, and REALM's `^listen`/`ON_<EVENT>` + per-viewer messaging are the
   right substrate to build it on. But a `Scene` with poses/participants/logs
   is **game content** — it belongs in a pack (models as GameObjects + tags +
   softcode), never in CORE. If building it tempts you to add scene concepts
   to the kernel, stop.
7. **The FS3 combat template — `prepare`/`resolve`/`narrate`.** Steal the
   *shape* (validate → mutate → return narrative strings → engine emits) for
   REALM's data-driven action packs. Do **not** port the Ruby; do **not** let
   "narrative combat" pull HP/wound-tier/hit-location concepts into CORE.
   It's a GameSystem pack.
8. **Jobs-as-workflow-spine.** The pattern of a generic ticket system that
   *other* systems hang off — chargen → job → approval, roster claims, and
   every abuse-report path in the game (`Scenes.report_scene`,
   `Channels.report_channel_abuse`, page/mail) all create jobs in a
   `trouble_category`. One triage hub, many producers. Good content pattern.
   Pure game content — a pack.
9. **YAML-defined multi-stage chargen.** Config-driven stages
   (`chargen.yml`) is philosophically on-brand for REALM (data-driven), but
   it's a GAME concern — implement as a data pack + softcode flow, not a
   kernel feature.
10. **BBS / mail / channels / achievements / wiki.** All real gaps, all
    **content**. Build the comms ones on a future channel/mail primitive if
    one is ever corified, but the features themselves are packs.

**Explicitly do NOT steal:** the class-reopening pattern for cross-cutting
fields (REALM's tags+behaviors composition is the deliberate alternative);
the linear O(plugins) `case`-statement dispatch (legible but doesn't scale to
REALM's in-world command surface); Redis-only persistence (REALM's
incremental SQLite is the right call for a world that may exceed RAM); and
the "extend only by writing host-language code" model, which is the exact
thing REALM exists to avoid.

---

*Status: reference comparison, no decisions taken — captured for evaluation.
See also [LambdaMOO Comparison](moo-comparison.md) and the
[PennMUSH Inventory](pennmush-inventory.md).*
</content>
</invoke>
