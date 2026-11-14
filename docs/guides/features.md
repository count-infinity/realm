# Features

A REALM game is a list of **features**. A feature is a named bundle of
declarations: commands, behaviors, softcode functions, propagation
observers, combat rulesets, settings and a few more. The built-in ones
(talk, combat, economy, ...) are declared with exactly the same API your
game uses, so anything they do, your game can do, and anything your game
leaves out simply does not exist in its world.

## Choosing features

`config.py` lists them:

```python
from realm.std import CLASSIC
FEATURES = [*CLASSIC, "game"]          # every built-in, plus your game.py
```

`FEATURES` unset means `CLASSIC`. A name is either a built-in feature or a
module path on `sys.path` (your game directory is on it, so `"game"` is
`game.py`). The built-in features:

| Feature | Gives you | Requires |
|---|---|---|
| `basics` | help, commands, who, quit, logout, color, think, time, uptime, recall | |
| `talk` | say, pose, semipose, emit, ooc, shout, whisper | |
| `movement` | go and the directions, in, out | |
| `look` | look, examine | |
| `items` | get, drop, give, put, inventory, open, close, lock, unlock, use, wear, remove, wield, unwield | |
| `building` | every `@` command, quell, unquell | |
| `rules` | points, improve; softcode `skill_check`, `check_roll`, `contest`, `skill`, `check`; gear changes reach the game system | |
| `stealth` | hide, search, pick; loud actions break stealth | rules, items |
| `combat` | attack, queue, defend, flee, combat, pace, combatdefault, wimpy, showrolls, firstaid; the combat manager; combat AI behaviors; softcode `damage`, `heal`, `start_combat`; settings `COMBAT_RULESET`, `COMBAT_BEAT_*`, `SHOW_ROLLS` | rules, items |
| `effects` | timed effect behaviors; softcode `apply_effect`, `remove_effect` | rules |
| `abilities` | cast, spells; the caster behavior; softcode `cast`, `use_ability` | rules |
| `economy` | buy, sell, list, pay, credits; shopkeepers; softcode `credits`, `adjust_credits`, `transfer_credits` | items |
| `social` | consider, persuade, fasttalk, follow, unfollow, party; softcode `disposition`, `adjust_disposition`, `reaction_roll` | rules |
| `crime` | wanted flags for assaulting players, peacekeeper guards, thieves | combat, economy |
| `npc` | watchful, patrol, scavenger, wandering, guard, decay behaviors | |
| `spawning` | spawner, restock, population, zone_reset behaviors | |
| `instances` | instanced copies of template areas; softcode `enter_instance` | |
| `wilderness` | procedural wilderness cells; softcode `enter_wilderness` | spawning |
| `gurps`, `d20`, `merc` | the combat ruleset of each rules system | rules |

The kernel is always there: the script engine and every other softcode
function, `script_ticker`, `behavior_def` behaviors, expiry reaping, the
game system's check resolution.

A smaller game lists what it wants. This social game has no combat and no
money; `attack`, `buy` and `damage()` are unknown there, and no NPC turns
aggressive:

```python
FEATURES = ["basics", "talk", "movement", "look", "items", "building", "game"]
```

## Writing a feature

`realm init` writes `game.py` with one commented example of each common
declaration. A feature module exposes a `feature` attribute:

```python
# game.py
from realm.core.behaviors import Behavior
from realm.features import Feature

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
| `feature.fallback(fn)` | an `async (ctx) -> bool` tried when no command matches, before softcode `$`-commands (`movement` walks a typed exit name) |
| `feature.traversal_gate(fn, reason=, attrs=)` | an `async (actor, exit_obj, direction) -> str \| None` asked before a walk through an exit; a string refuses with that line and fires `event:on_fail` with `reason`. `attrs` are the exit attributes it reads (`@examine` warns about them in a world without the feature) |
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
| `feature.name_resolver(fn)` | `(obj, looker, current) -> name`: who an object appears to be (recognition, disguise) |
| `feature.speech_renderer(fn)` | `(body, action, looker) -> body`: a spoken line per listener (languages, slurring) |
| `feature.group_formatter(fn, replace=)` | `(obj, count) -> str`: how a grouped contents line reads (one per game) |
| `feature.protocol(name, cls, **kwargs)` | a protocol server (see [Adding a Protocol](../protocols/adding-protocol.md)) |
| `feature.setting(key, default, doc)` | a `config.py` key; read it with `world.setting(key)` |
| `feature.script_verb(name, aliases=, token=, sugar=, doc=)` | a script command line (decorator) |
| `feature.event(action_type, hook=, doc=, payload=, target_lock=, tool_lock=, speech=)` | an action type and its `ON_<HOOK>` |
| `feature.lock_type(name, default=, doc=)` | a lock type with a default expression |
| `feature.entitlement(name, doc)` | an entitlement name |
| `feature.audience(name)` | a message audience (decorator on its resolver) |
| `feature.def_kind(name, tag, parse=)` | an in-world definition kind |
| `feature.on_install(fn)` | `(world)`, run while the world is wired |
| `feature.on_boot(fn)` | `async (world)`, after the world is loaded and wired |
| `feature.on_close(fn)` | `(world)`, when the world closes |

Behaviors, rulesets, destination resolvers and softcode functions are
installed **before the world loads**, so a saved behavior always finds its
class, with no import in `config.py`.

Read the built-in features in `realm/std/` for worked examples: `combat.py`
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
# from realm.core.defs import all_defs, find_def; find_def("recipe", "stew")
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

## Requirements

`Feature("crime", requires=["combat", "economy"])` means crime needs both in
`FEATURES`. A missing requirement raises `FeatureError` at load (`feature
'crime' requires 'combat', which is not in FEATURES`). Requirements are
never added for you: the list in `config.py` is the whole game.

## In tests

`Simulator(features=[...])` builds the same world a server would from that
list (default `CLASSIC`). Feature `on_boot` hooks run when the test awaits
`sim.boot()`.
