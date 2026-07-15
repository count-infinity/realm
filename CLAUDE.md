# REALM Project

Real-time Event-Action Layered MUD framework in Python.

## Core Design Philosophy

**REALM is a library, not an application to fork.**

Users should:
```bash
pip install realm
realm init mygame
cd mygame
realm start
```

Users should NOT need to modify REALM's source code. Everything should be extensible through:
- **Configuration files** (YAML/TOML)
- **Python entry points** (for protocols, commands, behaviors)
- **Subclassing** (GameServer, Session, etc.)
- **Plugin registration** (decorators, register functions)

### Extension Points (Design Goals)

| Feature | How Users Extend |
|---------|------------------|
| Protocols | Register via config or entry points, not by editing realm/gateway/ |
| Commands | Decorators in user's game code |
| Behaviors | Attach to objects, loaded from user's game |
| Events | Subscribe from user code |
| Welcome screen | data/welcome.txt in user's game directory (WELCOME_FILE setting) |
| Database | Config setting for SQLite path or PostgreSQL URL |

### Anti-Patterns to Avoid

- Hardcoding paths that assume REALM is the working directory
- Requiring users to subclass when configuration would suffice
- Putting game-specific logic in the realm package
- Protocols that can only be added by modifying realm/gateway/

## Target User Workflow

```bash
# Install REALM as a dependency
pip install realm

# Create a new game project
realm init spacegame
cd spacegame

# Project structure created:
# spacegame/
# ├── config.py              # Python-based config (callbacks, ports, db)
# ├── data/
# │   ├── welcome.txt        # Connection screen
# │   └── game.db            # SQLite database (created on start)
# └── (future: commands/, behaviors/, world/)

# Start the server
realm start
```

## Development Environment (REALM Contributors)

**Always activate the virtual environment before running Python:**
```bash
source venv/bin/activate
```

The venv is located at `./venv` in the realm project directory.

### Running the Server
```bash
source venv/bin/activate
python -m realm.cli start   # or: realm start
```

### Running Tests
```bash
source venv/bin/activate
pytest
```

### Building Documentation
```bash
source venv/bin/activate
pip install -e ".[docs]"

# Python 3.14 workaround: markupsafe C extension has issues
# Force pure Python build if you get SystemError with _escape_inner
pip uninstall -y markupsafe && pip install --no-binary :all: markupsafe

mkdocs serve -a 0.0.0.0:8000   # Live preview
mkdocs build                   # Build static site to site/
```

## Documentation Discipline (permanent)

**Every change that adds or alters a feature, softcode function, event hook,
command, or kernel primitive MUST update its documentation in the same
change.** Features that aren't written down get lost — treat docs as part of
"done" (code + tests + docs), not an afterthought. Concretely:

- **Softcode functions & `ON_<EVENT>` hooks are auto-generated.** After
  touching `ScriptFunctions` or `STANDARD_EVENTS` (`realm/scripting/triggers.py`,
  the single source of truth for event hooks), run
  `python scripts/gen_softcode_docs.py` to regenerate
  `docs/reference/softcode.md`. New hooks/functions then self-document.
- **Design docs** (`docs/design/`): update the relevant one, and keep
  `features-roadmap.md` + `reference-synthesis.md` honest — mark shipped
  features shipped, keep gap lists current. New design docs go in the
  `mkdocs.yml` nav.
- **Guides/reference**: if the change touches a builder-facing workflow,
  update the matching `docs/guides/*` or `docs/reference/*`.
- **Memory**: record notable shipped features in the project memory so they
  survive across sessions.

## Reference Implementations (Outside the Repo)

Reference MU* codebases are siblings of this repo in the home directory. They are not part of REALM itself.
```
~/CoffeeMud/     # Java MUD - combat, economy, crafting
~/evennia/       # Python MUD - Django-based, modern
~/pennmush/      # C MUSH - softcode, permissions
~/tinymux/  ~/tbamud/  ~/SmaugFUSS/  ~/SWRFUSS/  ~/SWFOTEFUSS/
~/ldmud/  ~/aresmush/  ~/lambdamoo/  ~/GoMud/  ~/DikuMUD3/  ~/AwakeMUD/
```

**Do not modify files in these directories.** These are read-only study material.

When working in these reference framework folders, you may be a subagent focused on extracting patterns from that codebase.

## Notes for Subagents

**IMPORTANT**: When designing any feature, remember REALM is a library. Users install it via pip and extend it through configuration and their own code. They should never need to modify REALM source.

### If working in ~/CoffeeMud/
Focus: combat formulas, area/mob templates, economy systems, event-driven behavior system
CoffeeMud is verbose Java. Look for patterns, not code to copy.

### If working in ~/evennia/
Focus: command parsing, typeclass system, how they handle inheritance, Portal/Server split architecture
Note what works well and what's over-engineered.
**Key insight**: Evennia uses entry points and settings.py for extensibility - study this pattern.

### If working in ~/pennmush/
Focus: permission systems, softcode concepts, flag-based attributes, lock system
The C is old but the design concepts are battle-tested.

## Key Files Reference

| File | Purpose |
|------|---------|
| `realm/cli.py` | CLI entry point (`realm init`, `realm start`) |
| `realm/server/game.py` | GameServer class - orchestrates all components |
| `realm/config/loader.py` | Settings loader from config.py |
| `realm/gateway/telnet.py` | Telnet protocol (asyncio.Protocol) |
| `realm/gateway/session.py` | Session and SessionManager |
| `realm/core/objects.py` | GameObject hierarchy |
| `realm/persistence/manager.py` | SQLite persistence |
| `realm/templates/` | Project scaffolding templates |
| `BACKLOG.md` | Prioritized task list |
| `ARCHITECTURE_IMPORT_EXPORT.md` | Import/export system design (future feature) |

## Architecture Notes

### Telnet Protocol Flow
1. Client connects → `TelnetProtocol.connection_made()`
2. Creates task for `_setup_session()` which sends negotiation then creates Session
3. Session gets writer callback passed at creation (for immediate flush)
4. Welcome screen sent and flushed immediately
5. `data_received()` processes bytes, triggers on CR (byte 13), ignores LF
6. Complete lines pushed to session and `on_command` callback invoked

### run_forever Loop
The `GameServer.run_forever()` uses `asyncio.sleep(1)` - this is not CPU intensive. The `await` suspends the coroutine and the event loop handles other tasks. Under the hood, asyncio uses OS-level `select`/`epoll`/`kqueue` which blocks efficiently at kernel level.
