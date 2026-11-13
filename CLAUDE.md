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
| `realm/server/game.py` | GameServer — opens the store, loads the world, runs loops and protocols |
| `realm/server/world.py` | `build_world()` — wires the engine; the server and the Simulator both call it |
| `realm/config/loader.py` | `Settings` (every config key, its default and doc) and `load_config` |
| `realm/core/objects.py` | GameObject: tags, attrs, `@parent` inheritance, kind predicates |
| `realm/core/propagation.py` | Two-pass check/react action pipeline |
| `realm/core/checks.py` | Skill checks, contests, modifier providers, pluggable resolver |
| `realm/core/perception.py` | Visibility & naming choke points |
| `realm/systems/` | Swappable GameSystem rules packages (GURPS/D20/Merc) |
| `realm/scripting/` | Sandboxed softcode: `$commands`, `^listens`, `ON_<EVENT>` |
| `realm/packs/` | Content packs (worldio JSON bundles) |
| `realm/persistence/worldio.py` | Export/import with ref remapping |
| `realm/persistence/store.py` | `Store` protocol: what engine code may call on a store (`PersistenceManager`, `MemoryStore`) |

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
