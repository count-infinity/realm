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
| `realm/cli.py` | `realm init` / `realm start` |
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
| `realm/std/rules/system.py` | `GameSystem`, the swappable rules package; `GAME_SYSTEM` names one |
| `realm/games/<name>/` | The built-in game systems (GURPS/D20/Merc): `system.py`, `ruleset.py` (combat), `feature.py` |
| `realm/scripting/` | Sandboxed softcode: `$commands`, `^listens`, `ON_<EVENT>` |
| `realm/scripting/registry.py` | The softcode function registry: `softfn` / `softcode_function` with `group`, `readonly`, `harm` flags |
| `realm/scripting/namespace.py` | `build_namespace(profile, ...)`: the one builder for script, check, inline, lock, detail and rule contexts |
| `realm/scripting/lib/` | The kernel's softcode functions, one module per area (a feature's own are in `realm/std/<feature>/softcode.py`, declared by its `feature.py`); `functions.py` holds the per-run `ScriptFrame` |
| `realm/packs/` | Content packs (worldio JSON bundles) |
| `realm/persistence/worldio.py` | Export/import with ref remapping |
| `realm/persistence/store.py` | `Store` protocol: what engine code may call on a store (`PersistenceManager`, `MemoryStore`) |

## Where code joins a world

Everything optional is a **feature** (`realm/features.py`): a named set of
declarations (`feature.command`, `.behavior`, `.function`/`.softfn`,
`.observer`, `.ruleset`, `.dest_resolver`, `.reaper`, `.queue_kind`,
`.check_modifier`, `.name_resolver`, `.speech_renderer`, `.group_formatter`,
`.fallback`, `.traversal_gate`, `.after_traverse`, `.sight_rule`, `.marker`,
`.input_interceptor`, `.login`, `.protocol`, `.setting`,
`.on_install`/`.on_boot`/`.on_close`; `.command(token=)` for `:pose`-style
prefixes). A built-in feature is a package `realm/std/<name>/`: `feature.py`
declares it; `actions.py` (its action-type enum), `verbs.py`, `softcode.py`
and the rest are its parts, importable without loading the feature. The
kernel's `ActionType` holds only kernel events; `world.rules` (the game
system) is set by the `rules` feature and the kernel never calls it. The dispatcher and `core/movement.py` know no command, token,
direction, exit or follower by name.
Built-ins are declared in `realm/std/<feature>/feature.py` and `realm/games/<system>/feature.py`;
a game declares its own in `game.py`; `FEATURES` in config lists them
(default `realm.std.CLASSIC`). Do not register at import time
(`@BehaviorRegistry.register`, `dispatcher.register`) in engine code: declare on a
feature. Collisions raise `FeatureError`. Guide: `docs/guides/features.md`.

`tests/test_boundaries.py` is the rule for where code goes: the kernel
(`realm/core`, `scripting`, `commands`, `permissions`, `persistence`,
`gateway`, `server`, `config`, `packs`, `realm/features.py`) imports nothing
from `realm/std` or `realm/games`; a feature imports another feature's parts
only when it `requires` it (otherwise it asks for that feature's service,
`world.services.get("look")`, and copes with None). Details:
`docs/development/contributing.md`.

Engine code reaches the running world through `realm.core.world`
(`get_world()`, or `find_world()` where no world is legitimate) and reads
config with `setting("KEY")`. Do not add module-global setters
(`set_x()` / `get_x()` pairs wired at boot): put the value on `World`, its
`services`, or a `Settings` key. Tests start with no world; they take the
`world` / `classic_world` fixtures (`tests/conftest.py`) or a `Simulator`.

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
