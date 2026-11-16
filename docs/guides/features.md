# Features

A REALM game is a list of **features**. A feature is a named bundle of
declarations: commands, behaviors, softcode functions, propagation
observers, combat rulesets, settings and a few more. The built-in ones
(talk, combat, economy, ...) are declared with exactly the same API your
game uses, so anything they do, your game can do, and anything your game
leaves out simply does not exist in its world.

## Where things go

Everything your game adds is declared on its feature, in `game.py`
(`feature = Feature("mygame")`). Each row links to a short example.

| I want to add | Declare it with |
|---|---|
| [a command](#add-a-command) | `feature.command` |
| [a behavior for NPCs and objects](#add-a-behavior) | `feature.behavior` |
| [a softcode function](#add-a-softcode-function) | `feature.softfn`, `feature.function` |
| [a line scripts can emit](#add-a-script-verb) | `feature.script_verb` |
| [an event and its `ON_` hook](#add-an-event) | `feature.event` |
| [a lock type, an entitlement](#add-a-lock-type-or-an-entitlement) | `feature.lock_type`, `feature.entitlement` |
| [a resource on objects](#add-a-resource-pool) | `feature.pool` or a `pools` attribute |
| [a kind of data definition](#add-a-definition-kind) | `feature.def_kind` |
| [a rules system](#add-a-rules-system) | `feature.ruleset`, `GameSystem` |
| [a network protocol](#add-a-protocol) | `feature.protocol` |
| [a setting in `config.py`](#add-a-setting) | `feature.setting` |
| [a reaction to every action](#add-an-observer) | `feature.observer` |

The [full list of declarations](#writing-a-feature) is below.

## Choosing features

`config.py` lists them:

```python
from realm import CLASSIC
FEATURES = [*CLASSIC, "game"]          # every built-in, plus your game.py
```

`FEATURES` unset means `CLASSIC`. A name is, in this order, a built-in
feature, a feature an installed package provides
([Add-on packages](#add-on-packages)), or a module path on `sys.path` (your
game directory is on it, so `"game"` is `game.py`). `realm features` lists
everything available. The built-in features:

| Feature | Gives you | Requires |
|---|---|---|
| `accounts` | accounts with several characters: the welcome screen (`connect`, `create`, `who`, `quit`), the character menu (`play`, `new`, `delete`, `password`), `characters`, `password`, `@account`, `@sitelock`; character creation from the game system's chargen steps; softcode `account_attr`, `set_account_attr`, `incr_account_attr`, `account_characters`; settings `MAX_CHARACTERS`, `ACCOUNT_MULTIPLAY` ([Accounts](accounts.md)) | |
| `mail` | mail to characters, kept on their accounts; `mail`; setting `MAIL_LIMIT`; softcode `send_mail` | accounts |
| `achievements` | `achievement_def` data, `achievements`; softcode `grant_achievement`, `has_achievement`; the `ACHIEVEMENT` hook | accounts |
| `basics` | help, commands, who, quit, logout, color, think, uptime, recall, prompt (and `time`, the server clock, when there is no `clock`); the default prompt (setting `PROMPT`, [The Character Sheet](character-sheet.md#the-prompt)) | |
| `talk` | say, pose, semipose, emit, ooc, shout, whisper; socials as data (`social_def`), `socials`, the `SOCIAL` hook ([Communication](communication.md)) | |
| `channels` | tell, reply, ignore, unignore, afk; channels as data (`channel_def`), `channels`, `channel`; the `TELL` and `CHANNEL` hooks; softcode `cemit`, `channel_members` | |
| `movement` | go and the directions, in, out | |
| `look` | look, examine | |
| `clock` | game time and calendar (`time`, softcode `game_time`, `time_of_day`), the `HOUR`, `DAWN`, `DAY`, `DUSK` and `NIGHT` hooks, `outdoor` rooms dark at night, weather per zone (`weather`, softcode `weather`); settings `GAME_TIME_RATIO`, `HOURS_PER_DAY`, `DAYS_PER_MONTH`, `MONTH_NAMES`, `DAY_NAMES` ([Time and Weather](time-and-weather.md)) | |
| `sight` | darkness and light (`dark`, `light`, `nightvision`; another feature's darkness tests, `add_darkness_test`), invisibility (`invisible`, `see_invisible`), the `glowing`, `magic` and `invisible` markers | |
| `items` | get, drop, give, put, inventory, equipment, open, close, lock, unlock, use, wear, remove, wield, unwield, eat, drink | |
| `building` | every `@` command, quell, unquell | look |
| `rules` | points, skills, improve, practice, train, study; the `trainer` behavior; progression ([Progression](progression.md)); setting `IDLE_TRAINING_MAX_HOURS`; softcode `skill_check`, `check_roll`, `contest`, `skill`, `check`; gear changes reach the game system | |
| `stealth` | hide, search, pick; loud actions break stealth; the watchful behavior | rules, items |
| `combat` | attack, queue, defend, flee, combat, pace, combatdefault, wimpy, showrolls, firstaid; the combat manager; death, coming round and respawn; combat AI behaviors; softcode `damage`, `heal`, `start_combat`; settings `COMBAT_RULESET`, `COMBAT_BEAT_*`, `SHOW_ROLLS`, `PLAYER_DEATH`, `CORPSE_LOCK_SECONDS` | rules, items |
| `effects` | timed effect behaviors; softcode `apply_effect`, `remove_effect`; `services["effects"].clear(obj)` | rules |
| `vitals` | regeneration out of combat; rest, sleep, stand (wake); a sleeper sees, hears and does nothing; settings `REGEN_INTERVAL`, `REST_REGEN`, `SLEEP_REGEN` ([Life and Death](life-and-death.md)) | |
| `abilities` | cast, spells, quaff, recite, zap (brandish); the caster behavior; softcode `cast`, `use_ability` | rules, combat |
| `economy` | buy, sell, list, pay, credits; shopkeepers; softcode `credits`, `adjust_credits`, `transfer_credits` | items |
| `social` | consider, persuade, fasttalk, follow, unfollow, party; the disposition boost; softcode `disposition`, `adjust_disposition`, `reaction_roll` | rules, effects |
| `crime` | wanted flags for assaulting players, peacekeeper guards, thieves | rules, combat, economy, effects |
| `npc` | patrol, scavenger, wandering, guard, decay behaviors | |
| `spawning` | spawner, restock, population, zone_reset behaviors | |
| `instances` | instanced copies of template areas; softcode `enter_instance` | |
| `wilderness` | procedural wilderness cells; softcode `enter_wilderness` | spawning |
| `tasks` | timed actions: stop; softcode `start_task`, `task_of`, `stop_task`; the `(busy)` marker | |
| `gurps`, `d20`, `merc` | the combat ruleset of each rules system; `merc` also charges movement points for walking | rules, combat |

The kernel is always there: the script engine and every other softcode
function, `script_ticker`, `behavior_def` behaviors, expiry reaping. Its
sight knows only that you see yourself and that admins see everything;
darkness and invisibility are the `sight` feature's, and without it the
`dark` and `invisible` tags are just tags. The
game system (`GAME_SYSTEM`) and its check resolution are the `rules`
feature's; without it, checks roll a neutral 3d6 roll-under.

A smaller game lists what it wants. This social game has no combat and no
money; `attack`, `buy` and `damage()` are unknown there, and no NPC turns
aggressive:

```python
FEATURES = ["accounts", "basics", "talk", "movement", "look", "items", "building", "game"]
```

## Writing a feature

`realm init` writes `game.py` with one commented example of each common
declaration. A feature module exposes a `feature` attribute:

```python
# game.py
from realm import Behavior, Feature

feature = Feature("mygame", requires=["rules"])


@feature.command("wave", category="social", help_text="Wave hello")
async def cmd_wave(ctx):
    await ctx.session.send("You wave.")


@feature.behavior
class Chime(Behavior):
    behavior_id = "mygame_chime"


@feature.function(readonly=True)
def double(n):
    return 2 * n
```

Everything a feature can declare:

| Declaration | What it adds |
|---|---|
| `feature.command(name, handler, aliases=, permission=, category=, help_text=, usage=, parse_equals=, token=)` | a command (decorator when `handler` is omitted); `token=":"` makes `:text` run it |
| `feature.login(fn)` | the `async (ctx)` that handles input from a session with no player (one per game; `accounts` declares it). Without one the server answers "This world has no login feature installed." |
| `feature.input_interceptor(fn, order=)` | an `async (world, session, line) -> bool` that sees input before the dispatcher, lowest `order` first; True consumes the line (`accounts` routes chargen) |
| `feature.fallback(fn)` | an `async (ctx) -> bool` tried when no command matches, before softcode `$`-commands (`movement` walks a typed exit name) |
| `feature.traversal_gate(fn, reason=, attrs=)` | an `async (actor, exit_obj, direction, *, fleeing) -> str \| None` asked before a walk (`exit_obj` may be None; `combat` holds a fighter who is not fleeing); a string refuses with that line and fires `event:on_fail` with `reason`. `attrs` are the exit attributes it reads (`@examine` warns about them in a world without the feature) |
| `feature.after_traverse(fn)` | an `async (actor, origin, destination, exit_obj, *, fleeing)` run after a walk (`social` brings followers) |
| `feature.behavior(cls)` | a behavior class, by its `behavior_id` (class decorator) |
| `feature.function(fn, name=, group=, readonly=, harm=)` | a native softcode function |
| `feature.softfn(fn, ...)` | a softcode function whose first parameter is the run's frame |
| `feature.observer(fn)` | an `async (action)` propagation observer |
| `feature.ruleset(name, cls, aliases=)` | a combat ruleset (used when `combat` is installed) |
| `feature.dest_resolver(name, fn, shared_destination=)` | a deferred exit destination |
| `feature.reaper(fn)` | an `async (store)` sweep on the reap cadence |
| `feature.queue_kind(kind, handler)` | a world op softcode queues for the event loop |
| `feature.check_modifier(fn)` | a `(obj, skill) -> int` modifier folded into every check |
| `feature.sight_rule(fn)` | `(viewer, obj) -> bool \| None`: after the kernel's sight (invisibility, darkness), False hides (`stealth` hides a `hidden` character) |
| `feature.deaf_rule(fn)` | `(recipient, action) -> bool`: True keeps that action's queued messages from that recipient (`vitals`: a sleeper hears nothing it is not party to) |
| `feature.marker(fn)` | `(obj, looker) -> str \| None`: a parenthetical marker on a listed name (`a key (hidden)`) |
| `feature.name_resolver(fn)` | `(obj, looker, current) -> name`: who an object appears to be (recognition, disguise) |
| `feature.speech_renderer(fn)` | `(body, action, looker) -> body`: a spoken line per listener (languages, slurring) |
| `feature.prompt(fn, replace=)` | `(player) -> str \| None`: the prompt after each batch of output, one per game (`basics` declares the default; see [The Character Sheet](character-sheet.md#your-own-prompt)) |
| `feature.group_formatter(fn, replace=)` | `(obj, count) -> str`: how a grouped contents line reads (one per game) |
| `feature.protocol(name, cls, **kwargs)` | a protocol server (see [Adding a Protocol](../protocols/adding-protocol.md)) |
| `feature.pool(Pool(...), replace=)` | a world-default pool definition (`realm.core.pools`): how `shields` or `hull` behaves on any object without its own (see [Pools](pools.md)) |
| `feature.setting(key, default, doc)` | a `config.py` key; read it with `world.setting(key)` |
| `feature.script_verb(name, aliases=, token=, sugar=, doc=)` | a script command line (decorator) |
| `feature.event(action_type, hook=, doc=, payload=, target_lock=, tool_lock=, speech=, listen=)` | an action type and its `ON_<HOOK>`; `listen=True` lets `^listen` triggers overhear its message |
| `feature.lock_type(name, default=, doc=)` | a lock type with a default expression |
| `feature.entitlement(name, doc)` | an entitlement name |
| `feature.audience(name)` | a message audience (decorator on its resolver) |
| `feature.def_kind(name, tag, parse=)` | an in-world definition kind |
| `feature.on_install(fn)` | `(world)`, run while the world is wired |
| `feature.on_reload(fn)` | `(world)`, when a builder reloads the world's data (`@reload`, an area or pack import) |
| `feature.on_boot(fn)` | `async (world)`, after the world is loaded and wired |
| `feature.on_close(fn)` | `(world)`, when the world closes |

Behaviors, rulesets, destination resolvers and softcode functions are
installed **before the world loads**, so a saved behavior always finds its
class, with no import in `config.py`.

## Where things go: examples

Each example goes in `game.py`, after this preamble. They all run in
`tests/test_where_things_go.py`.

```python
from realm import Behavior, Feature, Pool

feature = Feature("mygame")
```

### Add a command

```python
@feature.command("wave", help_text="Wave hello")
async def cmd_wave(ctx):
    await ctx.session.send("You wave.")
```

### Add a behavior

```python
@feature.behavior
class Chime(Behavior):
    behavior_id = "mygame_chime"          # attach with @behavior obj = mygame_chime

    async def tick(self, obj, delta):
        obj.location.msg_contents("Ding.")
```

### Add a softcode function

```python
@feature.function(readonly=True)          # double(4) in softcode
def double(n):
    return 2 * n

@feature.softfn(readonly=True)            # gets the run's frame first
def whoami(frame):
    return frame.executor.name
```

### Add a script verb

```python
@feature.script_verb("chant")             # a script line: chant Om
async def chant(engine, executor, text):
    if executor.location is not None:
        executor.location.msg_contents(f"{executor.name} chants: {text}")
```

### Add an event

```python
feature.event("weather:on_rain", hook="RAIN", doc="rain falls here",
              payload={"strength": "how hard it rains"})
# fire it: await fire_event(None, room, "weather:on_rain", extra={"strength": 3})
# react:   @set room/on_rain = remit(here, 'Puddles form.')
```

### Add a lock type or an entitlement

```python
feature.lock_type("ride", doc="who may ride this mount")   # @lock horse/ride = ...
feature.entitlement("summon_storms", "may call the weather down")
# check them: check_lock(horse, rider, "ride"); has_entitlement(caller, "summon_storms")
```

### Add a resource pool

```python
feature.pool(Pool("shields", overflow="hull"))   # how shields behave on any object
# or one object at a time: @set ship/pools = {"shields": {"overflow": "hull"}}
```

See [Pools](pools.md).

### Add a definition kind

```python
feature.def_kind("recipe", "recipe_def", parse=lambda obj: obj.db.get("needs"))
# objects tagged recipe_def are data: realm.defs.find_def("recipe", "stew")
```

### Add a rules system

```python
from realm.std.combat import Ruleset

class PercentileRuleset(Ruleset):         # roll_attack, roll_damage, apply_damage, ...
    name = "Percentile"

feature.ruleset("percentile", PercentileRuleset)
# and the game system in rules.py: class PercentileSystem(GameSystem), ruleset_name = "percentile"
```

[Creating your own system](creating-your-own-system.md) builds both.

### Add a protocol

```python
# doctest: skip
from mygame.protocols import GodotServer   # an asyncio server you write

feature.protocol("godot", GodotServer, port=4002)
```

[Adding a protocol](../protocols/adding-protocol.md) writes the server.

### Add a setting

```python
feature.setting("WEATHER_SEED", 1, "Seed for the weather.")
# config.py: WEATHER_SEED = 7       read it: get_world().setting("WEATHER_SEED")
```

### Add an observer

```python
@feature.observer                         # runs after every propagated action
async def count_actions(action):
    if action.actor is not None and not action.blocked:
        action.actor.db.actions = (action.actor.db.actions or 0) + 1
```

Read the built-in features in `realm/std/` for worked examples (each is a
package; `feature.py` holds its declarations): `combat/feature.py`
creates its manager in `on_install`, scrubs stale fight state in `on_boot`
and declares two queue kinds.

## Open vocabularies

Six lists the engine used to hard-code are declarations too, so a game
extends them the same way.

**Script verbs** — the lines a one-line script or `cmd()` may emit:

```python
@feature.script_verb("ping", sugar=True, doc="ping <text>")
async def ping(engine, executor, rest):
    executor.db.set("pinged", rest)
# @set bell/cmd_ring = $ring:ping hello      (and ping("x") inside Python)
```

**Events** — an action type, its `ON_<HOOK>`, its `adata()` payload and lock:

```python
feature.event("heist:on_crack", hook="CRACK", doc="a safe is cracked",
              payload={"tool": "the drill"},
              target_lock=("crack", "{name} holds."))
# @set safe/ON_CRACK = say Somebody's drilling me!     (@events lists it)
```

**Lock types** — any lowercase name works once a builder sets it; declare one
to give it a default (`"True"` is open) and a doc. A near miss of a known type
(`@lock/baisc`) is set with a "did you mean `basic`?" warning:

```python
feature.lock_type("crack", default="False", doc="who may drill this safe")
```

**Entitlements** — a `role_def` may grant a game's own name and softcode
checks it; declare it to document it. A near miss of a registered name
(`LOCK_BYPAS`) is reported by `@reload` and not granted:

```python
feature.entitlement("SMUGGLE", doc="carry contraband past customs")
# softcode: if has_entitlement(enactor, 'SMUGGLE'): ...
```

**Audiences** — who receives `action.add_message(name, ...)`:

```python
@feature.audience("zone")
def zone_players(action):
    return [p for p in action.actor.location.contents if p.is_player]
```

**Definition kinds** — objects tagged `tag` become data, cached and live:

```python
feature.def_kind("recipe", "recipe_def", parse=lambda obj: obj.db.get("needs"))
# from realm import defs; defs.find_def("recipe", "stew"); defs.all_defs("recipe")
```

**Global softcode commands** need no feature: an admin tags an object
`global_commands` and its `$`-commands work from every room (a room's own
command of the same pattern wins).

## Collisions

A name can belong to one feature. Two features declaring the same command
(or alias, or token), behavior id, softcode function, ruleset, destination resolver,
queue kind, config key, script verb (or token), event (or hook), lock type,
audience, definition kind or group formatter raise `FeatureError` at load, naming both:

```text
FeatureError: command 'wave' is declared by both 'mygame' and 'emotes'.
Rename one, leave one feature out, or pass replace=True on the declaration
that should win.
```

To replace a built-in on purpose, say so: `feature.ruleset("gurps", MyGurps,
replace=True)`, `@feature.command("look", replace=True)`.

## Services: using a feature you don't require

A feature that only *enhances* another (a shop that reads dispositions, a
walk that shows the room) asks for that feature's service instead of
importing it, and does without it when it is absent:

```python
look = get_world().services.get("look")      # None in a world without look
if look is not None:
    await ctx.session.send(look.render_room(room, player))
```

The built-ins offer `look` (`render_room`), `economy` (`get_credits`,
`transfer_credits`, `currency_name`), `social` (`get_disposition`,
`adjust_disposition`, `party_members`), `talk` (`npc_say`), `damage`
(`apply_resisted`, `deal_damage`) and `combat` (the manager). A feature
offers one from `on_install`: `world.services["mine"] = ...`. Importing
another feature's code is allowed only when you `requires` it
(`tests/test_boundaries.py` checks).

## Requirements

`Feature("crime", requires=["combat", "economy"])` means crime needs both in
`FEATURES`. A missing requirement raises `FeatureError` at load (`feature
'crime' requires 'combat', which is not in FEATURES`). Requirements are
never added for you: the list in `config.py` is the whole game.

## Add-on packages

A feature can be published as an ordinary Python package. The package
declares it in the entry-point group `realm.features`:

```toml
# pyproject.toml of the realm-weather package
[project.entry-points."realm.features"]
weather = "realm_weather:feature"
```

```python
# realm_weather/__init__.py
from realm import Feature

feature = Feature("weather", requires=["talk"], doc="Rain and shine.")
```

After `pip install realm-weather`, a game enables it by name:

```python
FEATURES = [*CLASSIC, "weather", "game"]
```

Installing a package makes a feature **available, not enabled**: nothing
in it runs, or is even imported, until a game lists it. Its requirements
are checked like a built-in's.

The rules, each a `FeatureError` at load:

- The entry-point name is the feature's name: `weather` must load
  `Feature("weather")`, and must load a `Feature`.
- A package may not claim a built-in's name. This fails every load, not
  only one that lists the name, so a package that shadows `combat` is
  found at once.
- Two installed packages may not claim the same name.

### `realm features`

Run in a game directory, `realm features` lists every available feature:
the built-ins, each installed package's (with the package and version) and
the game directory's own (the module paths in `FEATURES`), with what each
requires and how many commands, behaviors, softcode functions and other
declarations it makes. A `*` marks the ones `FEATURES` lists.

```text
$ realm features
combat   * built-in; requires rules, items; 10 commands, 6 behaviors, 3 softcode functions, ...
weather    installed: realm-weather 1.0; requires talk; 1 command, 1 setting
mygame   * game directory (game); requires talk; 2 commands
```

`realm features --check` loads `FEATURES` the way `realm start` would, and
reports a missing requirement or a collision without starting the server:

```text
$ realm features --check
FEATURES does not load: command 'forecast' is declared by both 'weather' and 'mygame'. ...
```

## In tests

`Simulator(features=[...])` builds the same world a server would from that
list (default `CLASSIC`). Feature `on_boot` hooks run when the test awaits
`sim.boot()`.
