# REALM Project

Real-time Event-Action Layered MUD framework in Python. **A game engine,
not a game** — the Godot of MU\*s.

## The five ideas (ELI5)

1. **It's a library, not a fork.** Users `pip install realm`, run
   `realm init mygame`, and extend through config, packs, and their own
   code. If a user ever needs to edit `realm/` source, that's a bug in
   REALM's design.
2. **Tiny kernel; everything with game meaning is data.** The kernel is
   abstract mechanism (propagation, checks, perception, persistence).
   Skills, classes, spells, stealth, verbs — all data + softcode. A
   hardcoded game concept in kernel Python is a defect.
3. **Everything is an action event (push).** Verbs fire actions; a
   two-pass pipeline lets the world veto/modify (check) then react
   (react). Both success *and failure* propagate, carrying the roll — so
   traps hear fumbles.
4. **Questions go through resolver seams (pull).** "Who can see whom?",
   "what's this called?", "what modifies this check?", "how does a check
   resolve?" — the kernel owns one choke point per question; registered
   policy answers it. Never answer a pull question with an if-chain in
   the kernel.
5. **Out of the box, REALM is a social MU\*.** Stealth, light, combat,
   skill lists — all arrive as importable **feature packs**. North star:
   [docs/design/bare-kernel-and-packs.md](docs/design/bare-kernel-and-packs.md).

**The test for any new feature:** *could this ship as a pack using only
public seams?* If not, the kernel is missing a **seam** — add the seam,
not the feature.

## Read before designing

| Doc | What it is |
|---|---|
| `VISION.md` | The invariants. Wins every conflict. |
| `docs/design/bare-kernel-and-packs.md` | Current north star: bare kernel + feature packs plan |
| `docs/design/skills-inventory.md` | Skills model: vocabulary / depth / progression axes |
| `docs/design/features-roadmap.md` | Ledger: what's softcode-today vs needs-a-kernel-bit |
| `BACKLOG.md` | Prioritized tasks + the historical record |
| `docs/showcase/` | 240 numbered worked examples — cite one instead of re-explaining |
| `docs/design/catalog/` | Per-reference-MUD survey findings (14 codebases) |

## Key files

| File | Purpose |
|---|---|
| `realm/__init__.py` | The public names (`realm.__all__`, loaded on first use via `realm/_exports.py`); feature and game packages publish theirs in their `__init__.py`. Frozen by `tests/test_public_api.py`; docs/reference/public-api.md |
| `realm/testing/` | `Simulator` (`Simulator.from_game(dir)` + `await sim.start()` boot a game directory as `realm start` would; the shared step is `server/world.py::prepare_world`), `build_test_world`, `reconfigure`; `fixtures.py` is the pytest plugin (`world`, `classic_world`, the `features` marker) the suite and a game's tests load |
| `realm/cli.py` | `realm init` (`--features classic\|social\|bare`, `--template`; templates in `realm/templates/`, including the scaffold's README and `tests/test_game.py`), `realm start`, `realm features [--check]`, `realm import-rom` |
| `realm/server/game.py` | GameServer — opens the store, loads the world, runs loops and protocols; input goes session prompt → feature input interceptors → dispatcher (login is the `accounts` feature's) |
| `realm/server/world.py` | `build_world()` — wires the kernel, then the loaded features; the server and the Simulator both call it |
| `realm/core/world.py` | `World`, the one handle to the running world: `get_world().store` / `.engine` / `.scripts` / `.rules` / `.services`, and `setting(key)` for config |
| `realm/features.py` | `Feature`, `FeatureSet`, `load()`: how commands, behaviors, softcode functions and observers join a world |
| `realm/std/` | The built-in features (`CLASSIC` lists them): one package each, `feature.py` declares it, the rest are its parts |
| `realm/config/loader.py` | `Settings` (every config key, its default and doc) and `load_config` |
| `realm/core/objects.py` | GameObject: tags, attrs, `@parent` inheritance, kind predicates |
| `realm/core/propagation.py` | Two-pass check/react action pipeline |
| `realm/core/pools.py` | Pools: bounded numbers on objects (hp, shields, stress); `harm`/`mend`/`spend`, then `settle` fires `ON_POOL`/`ON_SPENT`; combat's `std/combat/vitals.py` turns a spent vital pool into death and a fall through `hitprcnt` into `ON_HITPRCNT` |
| `realm/std/rules/checks.py` | Skill checks, contests; the `rules` feature's `Checks` service (resolver, skill table, modifier providers) |
| `realm/core/perception.py` | Visibility & naming choke points |
| `realm/std/rules/system.py` | `GameSystem`, the swappable rules package (neutral: no advancement economy); `PointBuyMixin` adds character points; `GAME_SYSTEM` names one |
| `realm/games/<name>/` | The built-in game systems (GURPS/D20/Merc): `system.py`, `ruleset.py` (combat), `feature.py` |
| `realm/scripting/` | Sandboxed softcode: `$commands`, `^listens`, `ON_<EVENT>` |
| `realm/scripting/registry.py` | The softcode function registry: `softfn` / `softcode_function` with `group`, `readonly`, `harm` flags |
| `realm/scripting/namespace.py` | `build_namespace(profile, ...)`: the one builder for script, check, inline, lock, detail and rule contexts |
| `realm/scripting/lib/` | The kernel's softcode functions, one module per area (a feature's own are in `realm/std/<feature>/softcode.py`, declared by its `feature.py`); `functions.py` holds the per-run `ScriptFrame` |
| `realm/packs/` | Content packs (worldio JSON bundles) |
| `realm/examples/` | The example games `realm init --template <name>` copies (midgaard, spacegame, wilderness); inside the package so a wheel has them (`tests/test_packaging.py`) |
| `realm/tools/rom_import.py` | ROM `.are` -> worldio converter behind `realm import-rom`. `scripts/` holds developer tools only (doc generators, example builders, `dev/move_modules.py`) |
| `realm/persistence/worldio.py` | Export/import with ref remapping |
| `realm/persistence/store.py` | `Store` protocol: what engine code may call on a store (`PersistenceManager`, `MemoryStore`) |

## Where code joins a world

Everything optional is a **feature** (`realm/features.py`): a named set of
declarations. A game declares its own in `game.py`; the built-ins in
`realm/std/<feature>/feature.py` and `realm/games/<system>/feature.py`;
`FEATURES` in config lists them (default `realm.std.CLASSIC`). Where each
kind of code goes (the table that opens `docs/guides/features.md`, every
row with a running example in `tests/test_where_things_go.py`):

| I want to add | Declare it with |
|---|---|
| a command | `feature.command` |
| a behavior for NPCs and objects | `feature.behavior` |
| a softcode function | `feature.softfn`, `feature.function` |
| a line scripts can emit | `feature.script_verb` |
| an event and its `ON_` hook | `feature.event` |
| a lock type, an entitlement | `feature.lock_type`, `feature.entitlement` |
| a resource on objects | `feature.pool` or a `pools` attribute |
| a kind of data definition | `feature.def_kind` |
| a rules system | `feature.ruleset`, `GameSystem` |
| a network protocol | `feature.protocol` |
| a setting in `config.py` | `feature.setting` |
| a reaction to every action | `feature.observer` |

The rest (`.dest_resolver`, `.reaper`, `.queue_kind`, `.check_modifier`,
`.name_resolver`, `.speech_renderer`, `.group_formatter`, `.fallback`,
`.traversal_gate`, `.after_traverse`, `.sight_rule`, `.marker`,
`.input_interceptor`, `.login`, `.audience`, `.on_install`/`.on_reload`/
`.on_boot`/`.on_close`) is listed in the same guide. A built-in feature is a
package: `feature.py` declares it; `actions.py`, `verbs.py`, `softcode.py`
and the rest are its parts, importable without loading the feature, and
its `__init__.py` lists its public names. The kernel's `ActionType` holds
only kernel events; `world.rules` (the game system) is set by the `rules`
feature and the kernel never calls it. Do not register at import time
(`@BehaviorRegistry.register`, `dispatcher.register`) in engine code:
declare on a feature. Collisions raise `FeatureError`.

Three tests in `tests/test_boundaries.py` are the rule for where code goes:

- `test_kernel_imports_nothing_above_it`: the kernel (`realm/core`,
  `scripting`, `commands`, `permissions`, `persistence`, `gateway`,
  `server`, `config`, `packs`, `realm/features.py`) imports nothing from
  `realm/std` or `realm/games`, and names no module there.
- `test_feature_requires_match_imports`: a feature imports another
  feature's parts only when it `requires` it; otherwise it asks for that
  feature's service (`world.services.get("look")`) and copes with None.
- `test_stock_game_is_only_a_feature_list`: a world of no features loads no
  feature module, and the default world loads exactly `CLASSIC`'s packages.

Details: `docs/development/contributing.md`.

Engine code reaches the running world through `realm.core.world`
(`get_world()`, or `find_world()` where no world is legitimate) and reads
config with `setting("KEY")`. Do not add module-global setters
(`set_x()` / `get_x()` pairs wired at boot): put the value on `World`, its
`services`, or a `Settings` key. Tests start with no world; they take the
`world` / `classic_world` fixtures (the `realm.testing.fixtures` plugin) or a `Simulator`.

## Development environment

Activate the venv first when one exists (`source venv/bin/activate`;
some checkouts — e.g. the Windows laptop — have no venv and plain
`python` works, verify with `python -c "import realm, pytest"`).

```bash
python -m realm.cli start      # run the server (or: realm start)
pytest                         # run tests
mkdocs serve -a 0.0.0.0:8000   # docs preview (needs pip install -e ".[docs]")
mkdocs build
```

Python 3.14 docs-build workaround (markupsafe SystemError):
`pip uninstall -y markupsafe && pip install --no-binary :all: markupsafe`

Deep architecture notes (telnet flow, event loop) live in
`docs/architecture/overview.md`, not here.

## Documentation discipline (permanent)

**Done = code + tests + docs, in the same change.** Features that aren't
written down get lost.

- Touched `ScriptFunctions` or `STANDARD_EVENTS`
  (`realm/scripting/triggers.py`)? Run
  `python scripts/gen_softcode_docs.py` to regenerate
  `docs/reference/softcode.md`.
- Update the matching `docs/design/*` doc; keep `features-roadmap.md`
  honest (mark shipped things shipped). New design docs go in the
  `mkdocs.yml` nav.
- Builder-facing changes update the matching `docs/guides/*` or
  `docs/reference/*`.
- Record notable shipped features and direction decisions in project
  memory so they survive across sessions.

## Reference MU* codebases (read-only study material)

Canonically siblings in the home directory (`~/CoffeeMud`, `~/evennia`,
`~/pennmush`, `~/tinymux`, `~/tbamud`, `~/SmaugFUSS`, `~/SWRFUSS`,
`~/SWFOTEFUSS`, `~/ldmud`, `~/aresmush`, `~/lambdamoo`, `~/GoMud`,
`~/DikuMUD3`, `~/AwakeMUD`). **Never modify them.** Not every machine
has them checked out (this Windows laptop has CoffeeMud, evennia, and
pennmush under `c:\develop\`); when a checkout is absent, the distilled
findings in `docs/design/catalog/*.md` and the `docs/design/*-comparison.md`
docs are the substitute — consult those first regardless.

Subagent focus, when studying one: CoffeeMud = breadth of
skills/crafting/behaviors (patterns, not code). Evennia = extensibility
via entry points/settings, cmdsets (note what's over-engineered).
PennMUSH = softcode, locks, permissions — old C, battle-tested design.

**Reminder for all agents:** REALM is a library. Users install it via
pip and extend it through configuration and their own code — they never
modify REALM source. Judge every design against `VISION.md`.
