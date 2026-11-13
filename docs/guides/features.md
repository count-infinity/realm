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
| `feature.command(name, handler, aliases=, permission=, category=, help_text=, usage=, parse_equals=)` | a command (decorator when `handler` is omitted) |
| `feature.behavior(cls)` | a behavior class, by its `behavior_id` (class decorator) |
| `feature.function(fn, name=, group=, readonly=, harm=)` | a native softcode function |
| `feature.softfn(fn, ...)` | a softcode function whose first parameter is the run's frame |
| `feature.observer(fn)` | an `async (action)` propagation observer |
| `feature.ruleset(name, cls, aliases=)` | a combat ruleset (used when `combat` is installed) |
| `feature.dest_resolver(name, fn, shared_destination=)` | a deferred exit destination |
| `feature.reaper(fn)` | an `async (store)` sweep on the reap cadence |
| `feature.queue_kind(kind, handler)` | a world op softcode queues for the event loop |
| `feature.check_modifier(fn)` | a `(obj, skill) -> int` modifier folded into every check |
| `feature.protocol(name, cls, **kwargs)` | a protocol server (see [Adding a Protocol](../protocols/adding-protocol.md)) |
| `feature.setting(key, default, doc)` | a `config.py` key; read it with `world.setting(key)` |
| `feature.on_install(fn)` | `(world)`, run while the world is wired |
| `feature.on_boot(fn)` | `async (world)`, after the world is loaded and wired |
| `feature.on_close(fn)` | `(world)`, when the world closes |

Behaviors, rulesets, destination resolvers and softcode functions are
installed **before the world loads**, so a saved behavior always finds its
class, with no import in `config.py`.

Read the built-in features in `realm/std/` for worked examples: `combat.py`
creates its manager in `on_install`, scrubs stale fight state in `on_boot`
and declares two queue kinds.

## Collisions

A name can belong to one feature. Two features declaring the same command
(or alias), behavior id, softcode function, ruleset, destination resolver,
queue kind or config key raise `FeatureError` at load, naming both:

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
