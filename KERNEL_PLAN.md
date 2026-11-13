# REALM Kernel Plan

A staged plan to turn REALM from "an engine with the game baked in" into a
kernel that games grow from. It implements the recommendations of the
architecture review of 2026-11-11 and is measured against `VISION.md`.

Execute the steps **in order**. Tick boxes as work lands. Every step ships on
its own and leaves the suite green.

| # | Step | Size | Status |
|---|------|------|--------|
| 1 | Fix the defects, delete the dead code | S | [ ] |
| 2 | One composition root, one source of defaults | S–M | [ ] |
| 3 | One softcode function registry, one namespace builder | M | [ ] |
| 4 | Features: built-ins use the front door | M–L | [ ] |
| 5 | One service function per world operation | M | [ ] |
| 6 | One softcode dialect, open vocabularies | M | [ ] |
| 7 | Move the files, replace the global setters, add boundary tests | L | [ ] |
| 8 | Pools: entity-agnostic health and resources | M–L | [ ] |
| 9 | A public face: imports, add-ons, packaging, scaffold | S–M | [ ] |

Steps 6 and 7 are swapped relative to the review's list. The file moves need
the registries of step 6 to exist, otherwise kernel modules would still have
to import feature modules.

---

## How to work this plan

**Baseline when this plan was written**

- Commit `edce4d3` (2026-07-31). `pytest -q` reports **2319 passed**.
  `ruff check realm/` reports 19 findings; do not add new ones.
- Line numbers in this document refer to that commit. Once earlier steps have
  moved code, find things by function name.

**Rules for whoever executes a step**

1. One step at a time. Start with a clean tree and a green suite
   (`source venv/bin/activate && pytest -q`).
2. Run the suite after every task. Never tick a box on a red suite.
3. Test first when behavior changes: write the test that pins the new
   behavior, watch it fail, then make it pass.
4. No compatibility shims. There are no outside users. When a name moves,
   fix every import in `realm/`, `tests/`, `docs/`, `examples/`, `scripts/`.
   Do not leave a re-export behind.
5. Fail loudly (VISION invariant 10). A collision or an unknown name raises,
   or logs at WARNING with the fix in the message. No silent fallback.
6. Docs are part of done (`CLAUDE.md`, Documentation Discipline). Each step
   lists the docs it touches. After changing softcode functions or events run
   `python scripts/gen_softcode_docs.py`. Close the `BACKLOG.md` entries
   named under **Closes**.
7. The maintainer commits. Do not commit. End each task with a suggested
   commit message.
8. When the code disagrees with this plan, stop and write the deviation in
   the **Decision log** at the bottom before continuing. Do not quietly
   build a different design.
9. Tasks marked **Decision** need the maintainer's answer. The plan states a
   default; use it if nobody answers.

**Lab results behind this plan.** Four of the riskier changes were tried in a
scratch clone before being written down:

- The shared destroy path of task 1.1 passed all 2319 tests with no test
  edits and fixed all four destroy defects.
- Removing the `+` rewrite (1.2), setting the heartbeat default to 0.1 (1.3)
  and fixing the `@set` validator (1.4) broke exactly one test, the one that
  pins the `+` rewrite itself.
- Wiring the Simulator with the same observers and combat manager as the live
  server (step 2) broke exactly one test,
  `tests/test_spells.py::TestCasting::test_fire_immune_target_takes_nothing`.
  That failure is a real bug in live GURPS and D20 games, fixed by task 1.8.

**Vocabulary**

- **Kernel**: mechanism that every MU* needs and no game replaces. After
  step 7 it is `realm/core`, `scripting`, `commands`, `permissions`,
  `persistence`, `gateway`, `server`, `config`, `features.py`.
- **Feature**: an optional unit that registers commands, behaviors, softcode
  functions, observers, events and settings through one API. Built-in
  features live in `realm/std/`.
- **Game**: a rules system and its content (`realm/games/gurps`, `d20`,
  `merc`, or a game's own directory).
- **World**: the object returned by `build_world()`. It holds the store, the
  propagation engine, the dispatcher, the script engine, the rules and the
  services features add.
- **Op**: a service function for one world operation (create, destroy, tag).
  Commands and softcode both call it. Authority is checked inside it.
- **Profile**: a named softcode evaluation context (script, check, inline,
  lock, detail, rule).

**The one rule behind every step**

> Built-ins use the front door. Combat, economy, the rules systems and the
> stock verbs install themselves through the same registration call an
> outside package uses, and the kernel boots and passes its own tests with
> none of them present.

---

## Step 1 — Fix the defects, delete the dead code

**Goal.** Remove the reproduced defects and the code nothing uses, so later
steps refactor a smaller and correct codebase. No design decisions beyond the
ones marked.

**Depends on.** Nothing.

### 1.1 One destroy path (data loss)

Today `@destroy` on a room deletes the player characters inside it
(`commands/olc/admin.py:145`, `_destroy_recursive`). The softcode path
(`ScriptEngine._deliver_queued`, `'destroy'` branch) evacuates players but
ignores the `safe` tag, skips exit unpairing and leaves contents pointing at
a deleted container. A third policy, the correct one, already exists in
`core/teardown.py` (`release_contents`, the R9 contract).

Create `realm/core/lifecycle.py`:

```python
class DestroyRefused(Exception):
    """Raised when an object may not be destroyed. `.reason` is shown to the actor."""
    def __init__(self, reason: str): ...

def check_destroy(obj, *, allow_player: bool = False) -> None:
    """Raise DestroyRefused for a player (unless allow_player) or a `safe`-tagged object."""

async def destroy_object(obj, store, *, allow_player: bool = False,
                         contents: str = "release") -> int:
    """Destroy obj. Returns how many contained objects were destroyed with it."""
```

Semantics of `destroy_object`:

1. `check_destroy(obj, allow_player=allow_player)`.
2. If `obj` is an exit: `core.pairing.dissolve_pairing(obj)` and save the
   former partner.
3. `contents="release"` (default): `await release_contents(obj, store)`.
   Players anywhere in the subtree are evacuated (home, else the start room).
   Player-owned property goes to its owner's refuge. Everything else inside
   is destroyed, recursively.
4. `contents="destroy"`: pass the ids of every non-player object in the
   subtree as `doomed_ids` to `release_contents` (players are still
   evacuated), then delete those objects deepest first.
5. `obj.location = None`, then `await store.delete(obj)`.
6. Return the count of destroyed contents. Make `teardown._release` return
   that count instead of `None`.

- [x] Write `tests/test_lifecycle.py` first (use `Simulator`, plus one case on
      a real `PersistenceManager` with a temp SQLite file):
  - [x] `@destroy` of a room with a player inside: the player still exists and
        stands in the start room. On SQLite the player's row still exists.
  - [x] A player-owned item in the destroyed room is at its owner's refuge. An
        unowned NPC in the room is gone.
  - [x] `@destroy` and softcode `destroy_obj()` both refuse a `safe`-tagged
        object. `destroy_obj()` returns `False` and the object still exists.
  - [x] Softcode `destroy_obj(container)` leaves no object whose `location` is
        a deleted object.
  - [x] Softcode destroy of a paired exit clears the partner's pairing.
  - [x] `@nuke` removes the player and their inventory.
- [x] Add `realm/core/lifecycle.py` as specified.
- [x] `cmd_destroy` (`commands/olc/admin.py`): keep parsing, target
      resolution, `require_control` and "You can't destroy yourself!". Replace
      the player check, the `safe` check, the pairing block and the recursive
      call with `destroy_object(target, ctx.persistence)`. On `DestroyRefused`
      send `refused.reason`.
- [x] `cmd_nuke`: `destroy_object(target, ctx.persistence, allow_player=True,
      contents="destroy")`. Delete `_destroy_recursive`.
- [x] `ScriptEngine._deliver_queued`, `'destroy'` branch: replace the body
      with `destroy_object(obj, self._persistence)` and swallow
      `DestroyRefused`.
- [x] `ScriptFunctions.destroy_obj` (`scripting/functions.py:503`): call
      `check_destroy(target)` and return `False` on refusal.
- [x] `core/events.py::reap_expired` and the final `else` branch of
      `GameServer._reconcile_orphaned_players`: call `destroy_object`. Leave
      `instances.destroy_instance` and the wilderness cell teardown alone;
      they are batch teardowns with their own doomed sets.

### 1.2 Commands that start with `+`

`CommandDispatcher._parse_command` rewrites `+x y` to a `channel` command
that does not exist, so a Python command registered as `+finger` never runs.
Softcode `$+pub` works only because softcode matches the raw input.

- [x] Delete the block "Step 2: Check for channel prefix (+)" in
      `commands/dispatcher.py`.
- [x] Delete `tests/test_dispatcher.py::TestCommandDispatcher::test_channel_prefix`.
- [x] Add tests: a Python command registered as `+finger` receives its
      arguments. Showcase 074 (`$+pub`, `$+p`) still passes.

### 1.3 Heartbeat default

A fresh scaffold runs `tick_interval = 4.0` because `config/defaults.py:38`
wins, while `Settings`, `GameServer` and `docs/design/time-and-beats.md` say
0.1.

- [x] Set `TICK_INTERVAL = 0.1` in `config/defaults.py` (step 2 deletes the
      file).
- [x] Test in `tests/test_config.py`: a `config.py` that sets only `GAME_NAME`
      loads with `tick_interval == Settings().tick_interval == 0.1`.

### 1.4 The false "will not run" warning

`cmd_set` (`commands/olc/modify.py`, about line 249) validates every script
attribute as Python, so every command-line script (`say ...`, `pose ...`,
`trigger ...`) prints "will not run" and then runs. The README's parrot
example hits this.

- [x] Add `validate_script(code: str) -> list[str]` next to `script_code_of`
      in `scripting/triggers.py`. It returns `[]` when
      `SimpleScriptRunner.is_simple_script(code)` is true and
      `validate_code(code)` otherwise.
- [x] `cmd_set` calls `validate_script`.
- [x] Tests: `@set x/on_tick = say hi`, `@set x/cmd_a = $a:pose waves` and
      `@set x/ON_RESET = trigger me/reseal` print no warning.
      `@set x/on_tick = if (` still warns.

### 1.5 Native bindings inside resolution rules

`docs/guides/resolution-and-bindings.md:65` shows
`resolve_rule = "exploding_pool(attr('pool'), 4)"`. It raises NameError
because `core/checks.py::resolve_with_rule` builds its namespace without the
registered bindings. Wards, locks and `@detail` have the same gap and are
fixed in step 3.

- [x] In `resolve_with_rule`, start the namespace from
      `registered_bindings()` and then apply the built-in names so built-ins
      win a collision.
- [x] Test: the guide's `exploding_pool` example, as written.

### 1.6 Ruleset registration

`RulesetRegistry._ensure_builtins` (`combat/system.py:104`) runs only when
`'gurps'` is missing, so a game that registers its own `gurps` first loses
`d20` and `merc`. `register` silently replaces.

- [x] Replace the `'gurps' not in` test with a `_builtins_loaded` class flag.
      Keep `setdefault` per name so an earlier registration by a game wins.
- [x] `RulesetRegistry.register(name, cls, *, replace=False)` raises
      `ValueError` when the name is taken by a different class and `replace`
      is false.
- [x] Tests for both.

### 1.7 Missing behaviors and unknown entitlements are reported

A saved behavior whose class is not registered loads as an inert
`ScriptedBehavior` with no log line, and gains a `def_name` key in its saved
parameters. An unknown entitlement in a `role_def` is dropped with a server
log warning only; the builder sees nothing.

- [x] `behaviors/scripted.py`: add `report_unresolved(objects) -> list[str]`.
      For each `ScriptedBehavior` whose definition is missing, log one WARNING
      per behavior id: "behavior 'x' on N object(s) has no registered class
      and no behavior_def; it will do nothing. If it is a Python behavior,
      import its module before the world loads."
- [x] Call it at the end of `GameServer._load_world`, and at the end of
      `worldio.import_objects` and `worldio.apply_plan`.
- [x] Keep `def_name` out of saved parameters: store the definition name in
      its own slot on `ScriptedBehavior`, and override `to_dict` to emit
      `{'behavior_id': <def name>, 'params': <the original params>}`.
      Test: loading and re-saving an unknown id leaves `params` unchanged.
- [x] `permissions/entitlements.py::reload_role_defs` returns the list of
      problems it found. `cmd_reload` (`commands/olc/debug.py`) prints them.
      Test.

### 1.8 One schema for `resistances`

Merc and the ability system read `resistances` as a dict of multipliers
(`apply_type_resistance`). `Combatant.get_resistance` reads it as a list of
type names, with separate `immunities` and `vulnerabilities` lists, and only
D20 calls it. GURPS consults neither. Result: in a live GURPS or D20 game a
fire-immune target takes full damage from a fireball. The existing test
passes only because the Simulator has no combat manager and falls back to
`apply_resisted`. All shipped data (134 objects in `midgaard.json`) uses the
dict form.

- [x] Add `Ruleset.scale_resistances(self, target: Combatant, damage:
      DamageResult) -> None` to `combat/ruleset.py`. It applies
      `apply_type_resistance(damage.damage_by_type, <resistances dict>,
      magical=damage.magical)` and records `damage.resisted`.
- [x] Call it first in `apply_damage` of `rulesets/gurps.py`,
      `rulesets/d20.py` and `rulesets/merc.py` (Merc's inline copy is replaced
      by the call).
- [x] Delete `Combatant.get_resistance` and the list-form `immunities` and
      `vulnerabilities`. Rewrite `tests/test_combat.py:108-118` to the dict
      form.
- [x] Parametrize `test_fire_immune_target_takes_nothing` over the three
      rulesets with a `CombatManager` installed.

### 1.9 Delete what nothing uses

Confirm each item with `git grep -n "<name>"` before deleting.

**A. Compatibility code with no users**

- [ ] `realm/server/dispatcher.py` (re-export shim). Rewrite the 16 test files
      that import `realm.server.dispatcher` to `realm.commands.dispatcher`.
      Remove `CommandDispatcher` from `realm/server/__init__.py`.
- [ ] The `realm_config.py` fallback in `config/loader.py` (about lines
      209-221).
- [ ] The legacy `data/welcome.txt` fallback in
      `GameServer._get_welcome_screen` (`server/game.py`, about line 745).
- [ ] **Decision (default: delete).** The plaintext-password branch in
      `server/auth.py` (`verify_password`, `needs_rehash`) and its tests at
      `tests/test_systems.py:143` and `:193`. Any local database older than
      2026-07-04 must be recreated.

**B. Hooks nothing can reach**

- [ ] `GameObject.at_action_check`, `at_action_react`, `at_observe_check`,
      `at_observe_react` and their four call lines in `visit_*`
      (`core/objects.py`). Nothing overrides them, and
      `PersistenceManager._row_to_object` always builds a plain `GameObject`,
      so a subclass can never be loaded. Keep the `visit_*` methods.
- [ ] Remove the docstrings that describe subclass overrides
      (`core/propagation.py` lines 11-14, the comment block above `visit_check`).

**C. Accepted and ignored**

- [ ] `min_args` in `CommandDispatcher.register`, the matching line in the
      `Command` docstring, and `# TODO: Argument validation`.
- [ ] The stale `# TODO: Check locks on exit` at `commands/dispatcher.py:442`
      (`move_through_exit` already checks them).
- [ ] **Decision (default: delete).** The player-alias step in
      `_parse_command`, `set_player_alias`, `remove_player_alias`,
      `_player_aliases` and their three tests. No command sets an alias.
- [ ] Make `DEBUG` work instead of deleting it: in `cli.py::cmd_start`, load
      the config before `logging.basicConfig` and use DEBUG level when
      `args.debug or settings.debug`.

**D. Unreferenced anywhere (engine, tests, docs)**

- [ ] `gateway/session.py`: `SessionMessage`, `Session.account_name`,
      `get_heredoc_sigils`.
- [ ] `combat/combatant.py`: `modify_stat`, `get_weapon`, `get_armor`,
      `is_in_combat`. `combat/system.py`: `CombatRound.next_turn`.
- [ ] `permissions/locks.py::list_locks`,
      `scripting/triggers.py::TriggerManager.invalidate_cache`,
      `server/game.py::GameServer.is_running`.

**E. Used only by tests and documented nowhere: delete with their tests**

- [ ] `CombatSystem.end_combat`, `CombatSystem.get_combatants`,
      `locks.get_lock`, `EventTrigger.matches_event`, `TagSet.from_list`,
      `CommandContext.has_player`, `ScriptSandbox._has_loop`,
      `GameObject.get_behavior`, `Session.push_input`.
- [ ] **Decision (default: keep).** `roles.role_conferred_by_tag` has six test
      uses and no engine caller.

**F. Keep. Recorded so nobody flags them again**

- Documented API with no engine caller: `Session.confirm`, `get_data`,
  `set_data`, `connected_time`, `push_input_nowait`, `receive_nowait`;
  `SessionManager.get_session`, `get_sessions_by_address`,
  `broadcast_to_room`; `BehaviorRegistry.describe_all`;
  `Simulator.submit_line`.
- `add_modifier_provider` and `remove_modifier_provider`: an intended seam.
  Step 4 gives it a feature-level entry point.
- The flat spell fields (`mana`, `damage_dice`, `heal_dice`, `save`) are
  **not** legacy. All 23 shipped spells, the ROM importer and
  `docs/guides/spells.md` use them. Reword the comments in
  `systems/abilities.py` from "legacy" to "shorthand".
- `clear_combatant_cache`, `clear_name_resolvers`, `clear_speech_renderers`,
  `get_emote_sigil`: test teardown for global state. They go in step 7.

**G. Lists and comments that have drifted**

- [ ] `realm.combat.__all__` and `realm.combat.rulesets.__all__`: add
      `MercRuleset` and `RulesetRegistry`. `realm.commands.builtin.__all__`:
      add `register_magic_commands`.
- [ ] `core/checks.py` module docstring calls the default resolver
      GURPS-shaped; the function's docstring calls it neutral. Make the module
      docstring say neutral.
- [ ] `combat/damage.py` module docstring says every source of damage goes
      through `deal_damage`. State the truth: softcode `damage()` and the
      timed effects write directly until step 8.
- [ ] Add a dated note at the top of `docs/design/simplicity_review.md`
      pointing here. Its thresholds (core past 25 modules, 10 singletons,
      "core imports only core") have been crossed.

### 1.10 Kind predicates

`has_tag('player')` appears 47 times in engine Python and `.is_player` twice.

- [ ] Add `is_npc` beside `is_room`, `is_player`, `is_exit`, `is_thing` on
      `GameObject`.
- [ ] Replace `x.has_tag('player' | 'room' | 'exit' | 'npc')` with the
      predicate across `realm/` (engine Python only; softcode keeps
      `has_tag(obj, 'player')`).

### Acceptance

- [ ] Every new test above passes. The suite is green.
- [ ] `git grep -n "_destroy_recursive\|realm.server.dispatcher\|realm_config\|at_action_check\|min_args"`
      returns nothing under `realm/` and `tests/`.
- [ ] `ruff check realm/` reports no more findings than before.

### Docs

- [ ] `docs/guides/world-management.md`: what `@destroy` does with players,
      owned property and other contents; `@nuke`.
- [ ] `docs/reference/softcode.md` regenerated (`destroy_obj` docstring).
- [ ] `docs/architecture/commands.md`: drop `min_args`.
- [ ] `BACKLOG.md`: add a dated FIXED entry listing 1.1 to 1.8.

---

## Step 2 — One composition root, one source of defaults

**Goal.** The live server and the test Simulator build the world with the
same function, so a test cannot pass on wiring the live game lacks. Every
config key is declared in exactly one place.

**Depends on.** Step 1 (task 1.8 fixes the one test this step would break).

### 2.1 `Settings` is the only source of defaults

Today a default lives in `config/defaults.py`, the `Settings` dataclass,
`load_config`'s `.get(key, default)` calls, `GameServer.__init__`'s 30
keyword defaults and `from_settings`'s `getattr(settings, name, default)`
calls. `KNOWN_CONFIG_KEYS` and the scaffold template are two more lists.

Design (`realm/config/loader.py`, or a new `realm/config/settings.py`):

```python
def setting(default, key: str, doc: str, *, path: bool = False):
    """A dataclass field that is also a config.py key."""
    return field(default=default, metadata={"key": key, "doc": doc, "path": path})

@dataclass
class Settings:
    game_name: str = setting("REALM", "GAME_NAME", "Name shown on the welcome screen and in logs")
    tick_interval: float = setting(0.1, "TICK_INTERVAL", "Seconds between server pulses (0 disables)")
    db_path: Path = setting(Path("data/game.db"), "DB_PATH", "SQLite file, relative to the game directory", path=True)
    ...  # every existing field, same names, same defaults as the dataclass has today
    # callbacks stay plain fields: init_world, on_start, on_stop, register_commands, register_protocols

KNOWN_CONFIG_KEYS = frozenset(f.metadata["key"] for f in fields(Settings) if "key" in f.metadata)
```

- `load_config` loops over `fields(Settings)`: when the key is present in
  `config.py` it is used, otherwise the dataclass default applies. Path
  fields are resolved against the game directory. The near-miss warning
  stays.
- `GameServer.__init__(self, settings: Settings | None = None, **overrides)`
  stores `self.settings = dataclasses.replace(settings or Settings(), **overrides)`.
  Existing calls such as `GameServer(db_path=":memory:", enable_telnet=False)`
  keep working. The copied attributes (`self.tick_interval`, ...) become
  reads of `self.settings`.

Tasks:

- [ ] Convert every `Settings` field to `setting(...)` with its key and a
      one-line doc. Keep the current dataclass defaults; they are the intended
      ones.
- [ ] Rewrite `load_config` as the loop described. Derive
      `KNOWN_CONFIG_KEYS`.
- [ ] Delete `realm/config/defaults.py` and the `DEFAULT_SETTINGS` export.
- [ ] Change `GameServer.__init__` as described. Delete
      `GameServer.from_settings`; `cli.py::cmd_start` calls
      `GameServer(settings)`. Keep the wiring of the `on_start` and `on_stop`
      config callbacks, now in `__init__`.
- [ ] Extend `tests/test_config.py`:
  - [ ] every key assigned in `realm/templates/config.py.template`, active or
        commented out, is in `KNOWN_CONFIG_KEYS`;
  - [ ] every active value in the template equals the `Settings` default,
        except `GAME_NAME` and `GAME_SYSTEM`;
  - [ ] `git grep -n "getattr(settings"` finds nothing in `realm/`.
- [ ] Add `scripts/gen_config_docs.py`, modelled on
      `scripts/gen_softcode_docs.py`. It writes `docs/reference/config.md`
      from the field metadata. Add the page to `mkdocs.yml` under Reference.

### 2.2 `build_world()`

Create `realm/server/world.py`:

```python
@dataclass
class World:
    settings: Settings
    store: Any                       # satisfies the Store protocol of 2.3
    engine: PropagationEngine
    dispatcher: CommandDispatcher
    rules: GameSystem
    scripts: ScriptEngine | None
    sessions: SessionManager | None
    services: dict[str, Any]         # "combat" -> CombatManager; features add theirs in step 4
    _closers: list[Callable[[], None]]

    def close(self) -> None:
        """Undo every ambient registration, newest first."""

def build_world(store, settings: Settings | None = None, *,
                sessions: SessionManager | None = None,
                defer_timers: bool = False) -> World:
```

`build_world` performs, in this order, what `GameServer.__init__` (lines
148-163) and `GameServer.start` (lines 351-433) do today. Each action pushes
its undo onto `_closers`.

1. Syntax settings: `set_inline_delimiters`, `set_trigger_sigils`,
   `set_markup_marker`, `set_emote_sigil`, `set_keyid_sigil`,
   `set_heredoc_sigils`, `set_interpreter_recursion_limit`.
2. `set_active_manager(store)`.
3. `CommandDispatcher()`, with `.persistence` and `.session_manager` set.
4. If `settings.enable_scripting`: `ScriptEngine`, its propagation observer,
   `set_script_engine`, `set_check_hook`, `engine.dispatcher`,
   `engine.session_manager`, `engine.defer_waits = defer_timers`, and the
   dispatcher's unknown handler.
5. `stealth_observer`.
6. Rules: `resolve_game_system`, `set_game_system`, `equipment_observer`,
   `set_skill_defaults`, `set_check_resolver`.
7. Combat: `create_combat_system(settings.combat_ruleset or rules.ruleset_name)`,
   `CombatManager(...)`, `set_combat_manager`, `set_show_rolls_default`, the
   hostile observer.
8. `crime_observer`.
9. `set_world_tick(settings.world_beat)`.
10. `register_all_commands(dispatcher)`.

Tasks:

- [ ] Write `tests/test_world_parity.py` first. Build a
      `GameServer(db_path=":memory:", enable_telnet=False)`, start it, and
      build a `Simulator()`. Assert both have: the same command names, the
      same propagation observers by qualified name, a combat manager with the
      same ruleset class, and the same softcode namespace keys. It fails
      today.
- [ ] Add `realm/server/world.py` as specified.
- [ ] `GameServer.start`: keep the order it has today. Open the store, call
      `set_active_manager`, create `AuthService`, load the world, run
      `init_world`, reload role defs, ensure the startup room, reconcile
      orphans, scrub combat state. Then `self.world = build_world(
      self.persistence, self.settings, sessions=self.session_manager)`. Then
      the login handler, the "Huh?" wrapper, the tick and reap loops, the
      config callbacks, the protocols.
- [ ] `GameServer.dispatcher`, `.script_engine`, `.combat_manager` and
      `.game_system` become properties that read `self.world`.
- [ ] `GameServer.stop`: replace the manual teardown of observers and
      setters with `self.world.close()`.
- [ ] `Simulator.__init__`: `self.world = build_world(self.store,
      Settings(game_system=game_system, enable_scripting=scripting),
      defer_timers=True)`. Keep the attributes tests use (`dispatcher`,
      `engine`, `game_system`, `store`). `Simulator.close` calls
      `self.world.close()` and `reset_engine()`.
- [ ] The parity test passes. Expected fallout, verified in the lab: no other
      test changes once task 1.8 is in.

### 2.3 A store protocol, one memory store

Three stores exist with different method sets: `PersistenceManager`,
`persistence/repository.py::GameObjectRepository` and
`testing/simulator.py::_Store`.

- [ ] Add `realm/persistence/store.py` with `class Store(Protocol)`. Its
      members are the methods engine code calls on a store today:
      `get_cached(id)`, `all_cached()`, `find_cached(*, tag=None, name=None)`,
      `async save(obj)`, `async delete(obj)`, `keyid_holder(keyid)`,
      `claim_keyid(obj, keyid)`, `release_keyid(obj)`. Check the single
      callers of `save_deferred` and `load`; either add them or change the
      caller to `save` / `get_cached`.
- [ ] Move `_Store` to `realm/persistence/memory.py` as public `MemoryStore`.
      The Simulator imports it.
- [ ] Delete `persistence/repository.py`. Port `tests/test_spacegame.py` (four
      uses) to `MemoryStore`. Change the type hints in
      `examples/spacegame/ships.py` and `scripts/spacegame_world/world.py` to
      `Store`.
- [ ] Test: `PersistenceManager` and `MemoryStore` both provide every member
      of `Store`.

### Acceptance

- [ ] `tests/test_world_parity.py` passes.
- [ ] `realm/config/defaults.py` and `persistence/repository.py` are gone.
- [ ] A config key is added by editing one line in `Settings`. The template
      test and the generated reference pick it up.

### Docs

- [ ] `docs/reference/config.md` (new, generated) and `mkdocs.yml`.
- [ ] `docs/development/testing.md`: the Simulator is wired like the server.
- [ ] `docs/architecture/overview.md`: `build_world` and `World`.
- [ ] `CLAUDE.md` Key Files table: `realm/server/world.py`,
      `realm/persistence/store.py`.

### Closes

- BACKLOG "Config drift" follow-ups. BACKLOG "Persistence follow-ups:
  `repository.py` interface incompatible with `manager.py`".

---

## Step 3 — One softcode function registry, one namespace builder

**Goal.** A softcode function is declared once, with its flags. Every
evaluation context is built by one function, so a name means the same thing
everywhere and a third-party function is visible wherever its flags allow.

**Depends on.** Step 2.

Today a function is a method on `ScriptFunctions` (94 public methods, 2055
lines) plus an entry in four hand-kept lists: the dict in `to_dict()`
(`functions.py:1891`), `_READONLY` (`:1860`), `_HARM_GATED` (`:2029`) and
`CATEGORIES` in `scripts/gen_softcode_docs.py`. Third-party functions use a
different registry (`scripting/bindings.py`) and reach only the full script
namespace and inline blocks. Seven contexts build their own namespaces:

| Context | Built at | Today |
|---|---|---|
| script (`$`, `^`, `ON_`, `on_tick`, `@tr`, `@eval`) | `engine.py:552`, `:721`, `functions.py:1280`, `:1342` | `to_dict()` plus event names |
| check pass (`on_check`, behavior_def `on_check`, wilderness provider) | `engine.py:310`, `core/wilderness.py:185` | `readonly_dict()` plus `block`, `mod`, `set_adata`, `is_blocked` |
| inline `[[...]]` | `scripting/inline.py:146` | `to_dict()` plus `viewer`, an override of `check_roll`, and `skill` |
| lock | `permissions/locks.py:158`, `:208` | `caller`, `target`, `owner` only |
| `@detail` condition | `core/describe.py:63` | `viewer`, `skill(name)`, `check(name, mod)`, a one-argument `has_tag(tag)` |
| resolution rule | `core/checks.py:108` | dice reducers, `skill`, `attr`, `mod`, `skill_name` |
| combat strategy | `combat/strategy.py` | `me`, `target`, `enemies`, `round`, `chance` |

### 3.1 The registry

Create `realm/scripting/registry.py`:

```python
@dataclass(frozen=True)
class SoftFn:
    name: str
    fn: Callable
    group: str            # section in the reference, e.g. "Money"
    readonly: bool        # safe in check, lock, detail and rule profiles
    harm: bool            # removed for executors without the HARM entitlement
    takes_frame: bool     # True: called as fn(frame, *args); False: a plain native function
    subject: bool = False # True: the context's subject is passed implicitly (see 3.3)

def softfn(name=None, *, group, readonly=False, harm=False, subject=False):
    """Decorator for engine functions whose first parameter is the frame."""

def softcode_function(name=None, *, group="Game", readonly=False, harm=False, replace=False):
    """Public decorator for plain native functions. Same registry."""

def registered() -> Mapping[str, SoftFn]: ...
def unregister(name: str) -> None: ...          # tests
```

Registering a name that is already bound to a different callable raises
`ValueError` unless `replace=True`. A game that really wants to replace
`controls` has to say so.

- [ ] Add the registry. `scripting/bindings.py` becomes a thin re-export of
      `softcode_function`, then is deleted once imports are fixed
      (`realm.scripting.softcode_function` stays the public path).

### 3.2 Derive the lists (no file moves yet)

- [ ] Write `tests/test_softcode_registry.py` first. It hardcodes today's
      three sets, copied from the current code: the keys of `to_dict()`, the
      `_READONLY` names, the `_HARM_GATED` names. It asserts the registry
      produces the same three sets.
- [ ] Decorate each public method of `ScriptFunctions` with
      `@softfn(group=..., readonly=..., harm=...)`. Take `group` from
      `CATEGORIES`, `readonly` from `_READONLY`, `harm` from `_HARM_GATED`.
      Appendix A lists every function with its values.
- [ ] Register the dice primitives from `core/dice.py` (`roll`,
      `margin_under`, `margin_over`, `net_successes`, `highest`, `band`) with
      `softcode_function(group="Dice & skill checks", readonly=True)`.
- [ ] `to_dict()` and `readonly_dict()` are generated from the registry.
      Delete the hand-written dict, `_READONLY` and `_HARM_GATED`.
- [ ] `scripts/gen_softcode_docs.py` reads groups from the registry. Delete
      `CATEGORIES`; keep only an ordered list of group names. Regenerate.
      `git diff docs/reference/softcode.md` must be empty.

### 3.3 One namespace builder

Create `realm/scripting/namespace.py`:

```python
def build_namespace(profile: str, *, executor, enactor=None, location=None,
                    store=None, action=None, params=None, subject=None,
                    enactor_consent=False) -> tuple[Mapping[str, Any], ScriptFunctions]:
```

| Profile | Functions | Extra names | Subject |
|---|---|---|---|
| `script` | all, minus harm-flagged ones when the executor lacks HARM | `me`, `here`, `enactor`; `atype`, `actor`, `target`, `has_atag`, `adata` (always bound); `param` when `params` is given | enactor |
| `check` | read-only only | script extras plus `block`, `mod`, `set_adata`, `is_blocked` | enactor |
| `inline` | same as `script` | `viewer` | viewer |
| `lock` | read-only only | `caller`, `target`, `owner` (executor is the locked object, enactor the caller) | caller |
| `detail` | read-only only | `viewer` | viewer |
| `rule` | read-only only | `skill(name=<this skill>)`, `attr(name)`, `mod`, `skill_name` | the roller |

The combat strategy namespace is left as it is. Record that in the Decision
log.

Subject helpers are defined once and exist in every profile: `skill(name)`
is the subject's skill level and `check(name, mod=0)` is a bool roll by the
subject. They are registered with `subject=True`.

Two signature conflicts go away:

- `inline` no longer overrides `check_roll`. In every profile `check_roll(obj,
  skill, mod=0)` returns a `CheckResult`. One line of content changes:
  `docs/tutorial/04-softcode.md:68` uses the one-argument inline form;
  change it to `check('observation')`.
- `@detail` loses its one-argument `has_tag(tag)`. No shipped content uses it
  (`grep -rn "@detail .*has_tag('" docs tests examples` is empty). The
  two-argument `has_tag(viewer, 'x')` and `viewer.has_tag('x')` both work.

Locks and `@detail` conditions are evaluated on hot paths. Do not build 60
closures per evaluation. `core/safe_eval.py::eval_expression` passes the
namespace as the `locals` mapping, which may be any mapping: implement
`ExprNamespace(Mapping)` that holds the few direct names and resolves
registry functions on first lookup. Measure `check_lock` with
`python -m timeit` before and after; a slowdown above 20% goes in the
Decision log and is fixed before the step closes.

- [ ] Write the context test first, `tests/test_namespace_profiles.py`: a
      native function registered with `readonly=True` is callable in a
      script, an `on_check` ward, a lock, a `@detail` condition, an inline
      block and a resolution rule. A native function without the flag is
      callable only in `script` and `inline`.
- [ ] Add `build_namespace` and `ExprNamespace`.
- [ ] Rewire every site in the table above to call it. Delete
      `ScriptEngine._check_namespace` and `_event_namespace` once nothing else
      uses them.
- [ ] Move `PROTECTED_ATTRS` from `scripting/functions.py:31` to
      `core/attrflags.py`. `scripting/handle.py` then no longer imports
      `functions`.
- [ ] `ScriptEngine._ward_failed`: when the cause is a NameError for a
      registered function that lacks `readonly`, say so in the log line.
- [ ] Change the one tutorial line. Run the tutorial and showcase tests.

### 3.4 Split the class by owner

Mechanical, and only after 3.2 and 3.3 are green.

- [ ] Rename `ScriptFunctions` to `ScriptFrame`. It keeps the per-run state
      (`executor`, `enactor`, `location`, the store, `command_queue`,
      `enactor_consent`) and the helpers (`_resolve`, `_controlled`,
      `_may_mutate`, `_may_relocate`, `_touch`, `_in_reach`, `_may_harm`),
      made public by dropping the underscore.
- [ ] Move each function out of the class into a module under
      `realm/scripting/lib/` as `def name(frame, ...)`, using the owner column
      of Appendix A: `objects.py`, `attrs.py`, `tags.py`, `locks.py`,
      `messaging.py`, `scheduling.py`, `text.py`, `mathx.py`, `lists.py`,
      `behaviors.py`, `checks.py`, `economy.py`, `social.py`, `combat.py`,
      `effects.py`, `abilities.py`, `travel.py`. Step 7 moves the
      feature-owned modules next to their features.
- [ ] `scripting/functions.py` ends below 400 lines.

### 3.5 The missing softcode half of abilities

The `cast` command runs a spell definition with its costs. Softcode `cast()`
only fires `event:on_cast`. Softcode cannot run an ability definition.

- [ ] Add `use_ability(name, target=None)` (group "Combat & effects",
      `harm=True`). It checks `abilities.can_invoke`, queues an `'ability'`
      delivery, and the engine calls `abilities.invoke_ability(executor, adef,
      target)` on the loop.
- [ ] Reword the `cast` docstring: it fires the ward and reaction event only.
- [ ] Tests, and regenerate the reference.

### Acceptance

- [ ] `git grep -n "_READONLY\|_HARM_GATED\|CATEGORIES" realm scripts` is
      empty.
- [ ] Both new test files pass. The suite is green.
- [ ] The regenerated reference lists the same functions as before plus
      `use_ability`.

### Docs

- [ ] `docs/reference/softcode.md`: regenerate. Replace the "Context names"
      section with one table of profiles (generated from the builder).
- [ ] `docs/guides/resolution-and-bindings.md`: the `readonly` and `harm`
      flags and where a binding is visible.
- [ ] `docs/guides/interception.md`: what is callable inside `on_check`.
- [ ] `docs/tutorial/04-softcode.md:68`.

---

## Step 4 — Features: built-ins use the front door

**Goal.** A game is a list of features. Built-in code registers through the
same API as a game or an add-on. A game can leave features out, and what it
leaves out is not registered, not listed in `help`, not callable from
softcode and not observing actions. Collisions raise.

**Depends on.** Steps 2 and 3.

Today `build_world` hardwires the script engine, the stealth, equipment and
crime observers, the combat manager and all 115 commands. Code registers
through eight different idioms (`@BehaviorRegistry.register`,
`RulesetRegistry.register`, `@softcode_function`, three `register_*`
functions in `core`, `add_observer`, `dispatcher.register` inside a config
callback, `server.register_protocol` inside another, the `GAME_SYSTEM`
path). A behavior written in a game directory must be imported at the top of
`config.py`, or its saved attachments go inert.

### 4.1 The Feature API

Create `realm/features.py`:

```python
class FeatureError(Exception): ...

class Feature:
    def __init__(self, name: str, *, requires: Sequence[str] = (), doc: str = ""): ...

    # Each call records a declaration. Nothing global changes until the feature is installed.
    def command(self, name, handler=None, *, aliases=(), permission="player",
                category=None, help_text="", usage="", parse_equals=False): ...   # decorator when handler is None
    def behavior(self, cls): ...                       # uses cls.behavior_id; usable as a class decorator
    def function(self, fn=None, *, name=None, group=None, readonly=False, harm=False): ...  # plain native softcode function
    def softfn(self, fn=None, *, name=None, group=None, readonly=False, harm=False, subject=False): ...  # takes the frame
    def observer(self, fn): ...                        # async (action) -> None on the propagation engine
    def ruleset(self, name, cls, *, aliases=()): ...
    def dest_resolver(self, name, fn, *, shared_destination=True): ...
    def reaper(self, fn): ...                          # async (store) -> None on the reap cadence
    def queue_kind(self, kind, handler): ...           # async (engine, frame, obj, payload) for softcode-queued world ops
    def check_modifier(self, fn): ...                  # (obj, skill) -> int, replaces add_modifier_provider
    def protocol(self, name, cls, **kwargs): ...
    def setting(self, key, default, doc=""): ...       # a config.py key owned by this feature
    def on_boot(self, fn): ...                         # async (world) -> None, after the world is loaded and wired
    def on_close(self, fn): ...                        # (world) -> None

class FeatureSet:
    features: list[Feature]                            # in dependency order
    def install_registries(self) -> None: ...          # before the world loads
    def install_runtime(self, world) -> None: ...      # commands, observers, queue kinds, reapers
    async def boot(self, world) -> None: ...           # on_boot hooks
    def close(self, world) -> None: ...

def load(names: Sequence[str]) -> FeatureSet: ...
```

Rules:

- A feature name resolves through the built-in table `realm.std.BUILTIN`
  (`"talk" -> "realm.std.talk"`). Anything else is a dotted module path; the
  game directory is already on `sys.path`. The module must expose a
  `feature` attribute. A missing module, a missing attribute or a missing
  requirement raises `FeatureError` naming the feature and who requires it.
- Registries hold declarations, and installing activates exactly the
  declarations of the loaded set. Only one world is live per process (the
  same assumption the global setters make today). `install_registries`
  resets `BehaviorRegistry`, `RulesetRegistry`, the softcode function
  registry and the destination resolvers to the loaded set.
  `World.close()` clears them. Import-time registration stops:
  `@BehaviorRegistry.register` on engine classes is replaced by
  `feature.behavior(...)`. `BehaviorRegistry.register` stays as the low-level
  call for tests.
- Two different objects declared under one name raise `FeatureError` naming
  both features. Every declaration accepts `replace=True` for a deliberate
  override.
- The softcode registry of step 3 gains an `owner` on each `SoftFn`.
  `registered()` returns only functions whose owner is installed. Kernel
  functions are always installed.
- Feature settings: `KNOWN_CONFIG_KEYS` is the kernel keys plus the keys the
  loaded features declare. `world.setting(key)` returns the value from
  `config.py` or the declared default. The config reference generator loads
  `CLASSIC` so feature keys appear in it.

Config: add `FEATURES` to `Settings` (default `None`, meaning
`realm.std.CLASSIC`).

```python
# mygame/config.py
from realm.std import CLASSIC
FEATURES = [*CLASSIC, "game"]                       # everything, plus the game's own code
# FEATURES = ["basics", "talk", "movement", "look", "items", "building", "game"]   # a social game
```

### 4.2 Boot order

`GameServer.start` becomes:

1. `features = realm.features.load(settings.features or CLASSIC)`.
2. `features.install_registries()`.
3. Open the store, load the world, call `report_unresolved`.
4. `init_world` on first boot, role defs, startup room, orphan reconcile.
5. `world = build_world(store, settings, sessions=..., features=features)`.
   `build_world` keeps only kernel wiring (syntax settings, store,
   dispatcher, script engine, rules resolution, world tick) and then calls
   `features.install_runtime(world)`.
6. `await features.boot(world)`.
7. Login handler, loops, config callbacks, protocols.

Behaviors are registered in step 2 of this list, before the world loads in
step 3. That removes the ordering trap for game-side behaviors.

`Simulator(features=None)` uses the same sequence without a file store.

### 4.3 Built-in features

Create the package `realm/std/` with one **declaration module** per feature.
In this step a declaration module only imports handlers and classes from
where they live today and declares them. Step 7 moves the code in.
`realm/std/__init__.py` exports `BUILTIN` and `CLASSIC`. The three rules
systems get declaration modules under `realm/games/`.

| Feature | Commands | Other declarations | Requires |
|---|---|---|---|
| `basics` | help, commands, who, quit, logout, color, think, time, uptime, recall | | |
| `talk` | say, pose, semipose, emit, ooc, shout, whisper | | |
| `movement` | go and the 12 directions, in, out | | |
| `look` | look, examine | | |
| `items` | get, drop, give, put, inventory, open, close, lock, unlock, use, wear, remove, wield, unwield | | |
| `building` | every `@` command in `commands/olc/*`, quell, unquell | | |
| `rules` | points, improve | `equipment_observer`; softcode `skill_check`, `check_roll`, `contest`, `skill`, `check` | |
| `stealth` | hide, search, pick | `stealth_observer` | rules, items |
| `combat` | attack, queue, defend, flee, combat, pace, combatdefault, wimpy, showrolls, firstaid | `on_boot`: create `CombatManager`, store it in `world.services["combat"]`, add the hostile observer, scrub stale combat state. Behaviors aggressive, defensive, fleeing, healer, combatant, venomous. Softcode `damage`, `heal`, `start_combat`. Queue kinds `death_check`, `combat`. Settings `COMBAT_RULESET`, `COMBAT_BEAT_MIN`, `COMBAT_BEAT_MAX`, `COMBAT_BEAT_DEFAULT`, `SHOW_ROLLS` | rules, items |
| `effects` | | Behaviors damage_over_time, modifier_effect, regeneration. Softcode `apply_effect`, `remove_effect` | rules |
| `abilities` | cast, spells | Behavior caster. Softcode `cast`, `use_ability`. Queue kinds `cast`, `ability` | rules |
| `economy` | buy, sell, list, pay, credits | Behavior shopkeeper. Softcode `credits`, `adjust_credits`, `transfer_credits` | items |
| `social` | consider, persuade, fasttalk, follow, unfollow, party | Behavior disposition_boost. Softcode `disposition`, `adjust_disposition`, `reaction_roll` | rules |
| `crime` | | `crime_observer`. Behaviors wanted, peacekeeper, steal | combat, economy |
| `npc` | | Behaviors watchful, patrol, scavenger, wandering, guard, decay | |
| `spawning` | | Behaviors spawner, restock, population, zone_reset | |
| `instances` | | Destination resolver, reaper, softcode `enter_instance`, queue kind | |
| `wilderness` | | Destination resolver, reaper, softcode `enter_wilderness`, queue kind | spawning |
| `gurps`, `d20`, `merc` | | `feature.ruleset(...)` with today's aliases (`3d6`, `dnd`, `diku`) | rules |

`script_ticker` and the scripted-behavior fallback belong to the kernel's
scripting runtime and are always installed. `reap_expired` is kernel.

A ruleset declaration is consumed only when `combat` is installed, so a
rules system does not require combat. When `combat` is absent,
`GameSystem.ruleset_name` is ignored and no manager exists.

Tasks:

- [ ] Write `tests/test_features.py` first:
  - [ ] **Default equals today.** With `CLASSIC`, the command names, the
        softcode namespace keys, the propagation observers and the registered
        behavior ids equal lists frozen in the test from the state after
        step 3.
  - [ ] **Subtract.** `Simulator(features=["basics", "talk", "movement",
        "look", "items", "building"])`: `attack`, `buy`, `cast`, `wimpy` and
        `improve` are unknown commands and absent from `help`. Softcode
        `credits`, `damage` and `start_combat` raise NameError. The engine's
        only observer is the script engine. `world.services` has no
        `"combat"`. An `act()` tagged hostile between two players starts
        nothing. `BehaviorRegistry.get("aggressive")` is `None`.
  - [ ] **A game feature.** A module written to `tmp_path` declares one
        behavior, one command and one softcode function. Listed in
        `FEATURES`, all three work. Attach the behavior, save to SQLite,
        boot a second server on the same file: the behavior still ticks,
        with no import in `config.py`.
  - [ ] **Collisions.** Two features declaring the same behavior id, command
        name, softcode function or ruleset name raise `FeatureError` that
        names both.
  - [ ] **Requirements.** A feature list with `combat` but without `rules`
        raises `FeatureError`.
- [ ] Add `realm/features.py`.
- [ ] Add `realm/std/` and `realm/games/` declaration modules per the table.
      Move the content of each `register_*_commands` function into the
      matching declarations. Delete `register_all_commands`, the 16
      `register_*_commands` functions, and the side-effect imports at
      `server/game.py:26-27` and in `realm/behaviors/__init__.py`.
- [ ] Replace the 26 `@BehaviorRegistry.register` decorators with
      `feature.behavior(...)` declarations.
- [ ] Move the feature-specific queue kinds out of
      `ScriptEngine._deliver_queued` into `feature.queue_kind` handlers:
      `death_check`, `combat`, `cast`, `enter_instance`, `wilderness`. The
      kernel keeps `pemit`, `remit`, `oemit`, `oob`, `save`, `destroy`,
      `wait`, `cancel_wait`, `prompt`, `force`, `act`, `move_to`.
- [ ] Move `GameServer._reap`'s instance and wilderness calls to
      `feature.reaper`. Move `_scrub_stale_combat_state` into the combat
      feature's `on_boot`.
- [ ] Reduce `build_world` to kernel wiring plus `install_runtime`. Change
      `GameServer.start` to the boot order of 4.2.
- [ ] Tests that call `register_all_commands` or a `register_*_commands`
      function (17 uses in 6 files) switch to `Simulator` or to
      `realm.features.load(CLASSIC).install_runtime(world)`.
- [ ] Delete the `register_commands` and `register_protocols` config
      callbacks. A game declares commands and protocols in its feature
      module. Keep `init_world`, `on_start`, `on_stop`.
- [ ] Scaffold: `realm init` writes `game.py` with
      `feature = Feature("<game id>")` and one commented example each of a
      command, a behavior and a softcode function. `config.py.template` gets
      `FEATURES = [*CLASSIC, "game"]` and loses the two callback examples.
      Add a test that uncomments the three examples and boots the scaffold.

### Acceptance

- [ ] `tests/test_features.py` passes. The suite is green.
- [ ] `git grep -n "crime\|stealth_observer\|CombatManager\|equipment_observer" realm/server/`
      is empty.
- [ ] `git grep -n "@BehaviorRegistry.register\|def register_.*_commands" realm/`
      is empty.

### Docs

- [ ] New guide `docs/guides/features.md`: choosing features, writing one,
      collisions, requirements. Add it to `mkdocs.yml`.
- [ ] `docs/getting-started/first-game.md`: `game.py` and `FEATURES`.
- [ ] `docs/architecture/commands.md`: registration through `feature.command`.
- [ ] `docs/protocols/adding-protocol.md`: rewrite around `feature.protocol`.
      Remove the `config/settings.yaml` section; that mechanism never existed.
- [ ] `docs/guides/creating-your-own-system.md`: ruleset declaration.
- [ ] `README.md` and `CLAUDE.md`: the extension table.

### Closes

- BACKLOG Priority 0 "Command Registration" and "Protocol Registration
  System" (config-based loading is superseded by features).

---

## Step 5 — One service function per world operation

**Goal.** Each world operation has one implementation. A command parses and
prints. A softcode function resolves and returns a bool. Both call the same
op, and the op checks authority. This removes the class of defect fixed in
task 1.1 and answers the BACKLOG question "Command authorization belongs at
the service layer".

**Depends on.** Step 4.

### 5.1 The shape of an op

Create `realm/core/ops.py` (make it a package if it passes about 500 lines):

```python
class OpError(Exception):
    """An op refused. `.reason` is a sentence fit to show the actor."""
class NotAllowed(OpError): ...     # the actor lacks authority
class Refused(OpError): ...        # the target refuses (safe tag, system attribute, ...)
class Invalid(OpError): ...        # bad argument

@dataclass
class OpResult:
    value: Any = None
    touched: list[GameObject] = field(default_factory=list)   # objects the caller must persist
    warnings: list[str] = field(default_factory=list)
```

Rules:

- An op takes `actor` first. It never parses command strings and never sends
  output.
- A synchronous op mutates in memory and returns `OpResult`. An op that
  needs the store or propagation is `async`.
- Every op has a sibling `check_<op>(actor, ...)` that raises the same
  errors without mutating. Softcode needs it because scripts run in a worker
  thread: the function calls `check_<op>` to return `True` or `False` at
  once, then queues the op to run on the loop.
- Command wrapper: parse, resolve, `try: result = op(...)`, save
  `result.touched`, print. On `OpError` print `.reason`.
- Softcode wrapper: resolve, `try: op(...)` or `check` plus queue,
  `frame.touch(obj)` for each touched object, return `True`; on `OpError`
  return `False`.

### 5.2 The operations

| Op | Command today | Softcode today | Differences today | Unified rule |
|---|---|---|---|---|
| `destroy` | `cmd_destroy`, `cmd_nuke` | `destroy_obj` | Fixed in 1.1 | Move `lifecycle.destroy_object` here unchanged |
| `create` | `cmd_create` (`olc/create.py:15`): in the caller's inventory, owner is the caller, tags `['thing']`, optional parent | `create_obj` (`functions.py:451`): in the executor's room or a location it controls, owner is the executor's owner or the executor, tags, description and attrs accepted | Two constructors. Only softcode filters protected attributes | `create(actor, name, *, location, description="", tags=("thing",), attrs=None, parent=None)`. The actor must control `location` unless it is the actor or the actor's room. Owner is `actor.owner or actor`. Attributes go through the same gate as `set_attr` |
| `clone` | `cmd_clone` | none | No softcode half | `clone(actor, original, *, name=None, location)`. Add softcode `clone_obj` |
| `set_attr`, `del_attr` | `cmd_set`, `cmd_wipe` | `set_attr`, `del_attr`, `incr`, `decr` | The command refuses `keyid` and checks `writable_attr`. Softcode refuses `PROTECTED_ATTRS` and checks `writable_attr` | Control, then protected names (`password`, `keyid`), then `writable_attr`. Script validation warnings are returned in `OpResult.warnings` |
| `tag`, `untag` | `cmd_tag`, `cmd_untag` | `add_tag`, `remove_tag` | The command lowercases the tag; softcode does not | Lowercase. Control, then `may_change_role_tag` |
| `set_lock`, `clear_lock` | `cmd_lock`, `cmd_unlock` | `set_lock`, `clear_lock` | Already share `locks.set_lock` | Control check and type validation inside the op |
| `attach_behavior`, `detach_behavior` | `cmd_behavior` (178 lines) | `attach_behavior`, `detach_behavior` | The command is builder tier. Softcode needs only control | **Decision (default):** control, and the actor or its owner chain holds the new `BUILD` entitlement |
| `rename`, `describe` | `cmd_name`, `cmd_desc` | none | Softcode cannot set a description; filed in BACKLOG as a showcase gap | Add softcode `set_name`, `set_desc` |
| `relocate` | `cmd_teleport` | `move_to`, `teleport_obj` | Already share `core.movement.move_to` | The op wraps `move_to`. `cmd_teleport` drops its own `may_relocate` pre-check |
| `chown` | `cmd_chown` | none | No control check beyond the admin tier | Requires `CONTROL_ALL`. Keeps the halt of scripted objects |
| `dig`, `open_exit`, `link`, `unlink`, `pair` | `olc/create.py` | none | Commands only | Move the bodies into ops. Softcode surface is optional and can follow later |
| `boot` | `cmd_boot` | none | Acts inline | `boot(actor, player)` requires a new `MODERATE` entitlement, granted to admin |

`force` (`server/puppet.py::force_command`) and the money functions
(`core/economy.py`) already have one implementation. Leave them.

New entitlements `BUILD` (builder and above) and `MODERATE` (admin and
above) go in `permissions/entitlements.py` and the role table in
`permissions/roles.py`. The ladder-equivalence test in
`tests/test_permissions.py` must still pass.

`Command.permission` tiers stay as they are in this step. The op layer adds
the real check underneath. Opening builder commands to custom roles is task
5.4, and it is optional.

Tasks, one op family per commit:

- [ ] `tests/test_ops.py` first. For each op, a parametrized matrix of actor
      (player, owner, builder, admin) by target (own, someone else's,
      unowned, protected) asserts that the command and the softcode function
      produce the same outcome and the same refusals.
- [ ] Add `realm/core/ops.py` with the errors and `OpResult`. Move
      `destroy_object` in.
- [ ] `create`, `clone` and an `inflate(spec)` helper (see 5.3).
- [ ] `set_attr`, `del_attr`. `cmd_wipe` loops over the op.
- [ ] `tag`, `untag`.
- [ ] `set_lock`, `clear_lock`.
- [ ] `attach_behavior`, `detach_behavior`. `cmd_behavior` keeps its listing
      and `/info` output and calls the op to mutate.
- [ ] `rename`, `describe`, with the two new softcode functions.
- [ ] `relocate`, `chown`, `boot`.
- [ ] `dig`, `open_exit`, `link`, `unlink`, `pair`.

### 5.3 One way to build an object from data

Eight places inflate a `GameObject` from a dict by hand:
`worldio.import_objects`, `worldio._apply_entry`,
`PersistenceManager._row_to_object`, `spawner.spawn_from_prototype`,
wilderness cell materialization, `create_obj`, `Simulator._make`,
`cmd_create`. They disagree about unknown behaviors: the spawner warns, the
rest drop them without a message.

- [ ] Add `realm/core/inflate.py::inflate(spec: dict, *, obj_id=None,
      strict_behaviors=False) -> GameObject`. The spec keys are `name`,
      `description`, `tags`, `attrs`, `locks`, `behaviors`. Unknown behavior
      ids are collected and reported once.
- [ ] Replace the eight loops.

### 5.4 Optional: let custom roles run gated commands

- [ ] **Decision (default: skip for now).** Add `Command.requires: str | None`,
      an entitlement name. The dispatcher admits the caller when the tier
      check passes or when the caller holds that entitlement. Set
      `requires="TELEPORT_ANY"` on `@teleport` and `requires="MODERATE"` on
      `@boot`. A `role_def` granting `TELEPORT_ANY` can then run `@teleport`.

### Acceptance

- [ ] `tests/test_ops.py` passes. The suite is green.
- [ ] Command modules no longer mutate targets directly. This grep returns
      only lines inside `realm/core/ops.py`, `realm/core/inflate.py` and
      listing code:
      `git grep -n "\.add_tag(\|\.remove_tag(\|\.db\.set(\|persistence\.delete(" realm/commands/olc`

### Docs

- [ ] `docs/architecture/commands.md`: commands are thin wrappers over ops.
- [ ] `docs/design/engine_vision.md`: the authority section names ops as the
      one gate; add `BUILD` and `MODERATE`.
- [ ] Regenerate the softcode reference (`clone_obj`, `set_name`, `set_desc`).

### Closes

- BACKLOG "Command authorization belongs at the service layer". Record what
  5.4 leaves open.
- BACKLOG showcase gap "no softcode description slot".


---

## Step 6 — One softcode dialect, open vocabularies

**Goal.** A script line means the same thing wherever it is written, and the
set of lines a script can emit is a registry. Every closed list in the kernel
that a game might extend becomes open: script verbs, event hooks, lock
types, entitlements, message audiences, definition kinds and the trigger
search path. Adding to any of them is one declaration on a `Feature`.

**Depends on.** Steps 3, 4 and 5.

**Why this comes before the file moves.** `permissions/locks.py`,
`scripting/triggers.py` and `core/action_types.py` hold tables that name
speech, item, combat and magic events. While those tables exist the kernel
cannot be separated from the features. This step empties them.

What is closed today:

| Vocabulary | Where | Size | To add one today |
|---|---|---|---|
| Script verbs | `SimpleScriptRunner.SIMPLE_COMMAND_PREFIXES` (`sandbox.py:606`), the if-chain in `ScriptEngine._run_script_command` (`engine.py:753`), sandbox sugar (`sandbox.py:498-505`), `validate_script` (task 1.4) | 16 prefixes, 3 tokens | Edit four places in two kernel files |
| Event hooks | `STANDARD_EVENTS` (`triggers.py:219`), `ActionType` (`core/action_types.py`), the payload table in `docs/reference/softcode.md` | 32 hooks, 39 action types | Edit the enum, the dict and the doc |
| Lock on an action | `TARGET_ACTION_LOCKS`, `TOOL_ACTION_LOCKS` (`locks.py:438,454`) | 10 rows | Edit the kernel table |
| Lock types | `LockType` enum, `DEFAULT_LOCKS` (`locks.py:44,62`) | 12 | Edit the enum |
| Entitlements | `ALL_ENTITLEMENTS` (`entitlements.py:65`) | 7 | Edit the frozenset. A game's own name is logged and dropped |
| Audiences | `deliver_messages` (`propagation.py:671`) | 4 | Not possible. Other audiences are ignored |
| Definition kinds | six loaders in four modules | 6 | Write a seventh loader |
| Trigger search path | `get_search_objects` (`triggers.py:460`) | 4 sources, 1 TODO | Not possible |

### 6.1 Script verbs: one dialect

A softcode attribute is either one command line (`say Hello, %n!`) or Python
that emits command lines (`say(f"Hello")`, `cmd("drop key")`). Both end in
`_run_script_command`. The line format stays. What changes is that one
registry decides which lines exist, for the classifier, the executor, the
validator and the Python sugar at once.

Create `realm/scripting/verbs.py`:

```python
ScriptVerbHandler = Callable[["World", GameObject, str], Awaitable[None]]

@dataclass(frozen=True)
class ScriptVerb:
    name: str                       # "say"
    handler: ScriptVerbHandler      # (world, executor, rest_of_line)
    aliases: tuple[str, ...] = ()   # ("take",) for get
    token: str | None = None        # one leading character: ":" for pose
    sugar: bool = False             # also expose name(text) inside Python scripts
    owner: str = "kernel"
    doc: str = ""

class ScriptVerbs:
    def register(self, verb: ScriptVerb, *, replace: bool = False) -> None: ...
    def match(self, line: str) -> tuple[ScriptVerb, str] | None: ...
    def is_command_line(self, code: str) -> bool: ...
    def names(self) -> list[str]: ...
```

Rules:

- `match` compares the first word case-insensitively against names and
  aliases, then the first character against tokens. A verb with no
  arguments matches a bare word (`look`), which the prefix list could not
  express.
- `is_command_line` is true for a single non-empty line that `match`
  accepts. It replaces `SimpleScriptRunner.is_simple_script`.
- `register` raises `FeatureError` on a duplicate name, alias or token
  unless `replace=True`.
- The registry lives on the script engine (`world.scripts.verbs`). It is
  built from the loaded features, so a world without `items` has no `get`
  verb and `validate_script` says so when a builder writes one.
- Add `Feature.script_verb(name, *, aliases=(), token=None, sugar=False,
  doc="")` as a decorator.

Owners:

| Verb | Aliases, token | Owner | Handler body today |
|---|---|---|---|
| `wait` | | kernel | `schedule_wait` branch |
| `trigger` | `@tr` | kernel | `_scripted_trigger` |
| `say` | | talk | `_emit_speech` |
| `pose` | token `:` | talk | `_emit_pose` |
| `emit` | `@emit`, token `\` | talk | `_emit_raw` |
| `whisper` | | talk | `_emit_whisper` |
| `move` | `go` | movement | `_scripted_move` |
| `get` | `take` | items | `_scripted_verb` |
| `drop`, `give`, `open`, `close` | | items | `_scripted_verb` |

The `;` token is in `SIMPLE_COMMAND_TOKENS` but `_run_script_command` has no
branch for it, so a `;` script is classified as a command line and then
dropped with a warning. Register it as the semipose verb in `talk`.
`cmd_semipose` (`communication.py:72`) builds its action inline, so extract
a `do_semipose(actor, text, *, scripted=False)` core next to `do_pose` in
`core/verbs.py` and call it from both.

Tasks:

- [ ] Write `tests/test_script_verbs.py` first:
  - [ ] Each row of the table still runs from a one-line attribute and from
        `cmd("...")`, with the results the current tests expect.
  - [ ] A feature registers `script_verb("ping")`. A one-line attribute
        `ping hello` runs it. `validate_script("ping hello")` returns no
        warnings.
  - [ ] With `features=["basics", "talk", "movement", "look", "building"]`,
        `validate_script("get key")` returns a warning naming the missing
        verb, and running it logs one WARNING.
  - [ ] `;waves.` as a one-line attribute produces a semipose.
  - [ ] Two features registering the same verb or token raise.
- [ ] Add `realm/scripting/verbs.py` and `Feature.script_verb`.
- [ ] Move each handler body to its owner per the table. The handlers call
      the cores in `core/verbs.py` exactly as today.
- [ ] Reduce `_run_script_command` to: strip, `match`, call the handler, or
      log the unsupported line at WARNING with the list of known verbs.
- [ ] Delete `SIMPLE_COMMAND_PREFIXES`, `SIMPLE_COMMAND_TOKENS` and
      `is_simple_script`. `SimpleScriptRunner` keeps `expand_simple` only;
      rename it to a module function `expand_substitutions`.
- [ ] Sandbox sugar: build `say`, `pose`, `move`, `trigger` from the verbs
      flagged `sugar=True` instead of the four hardcoded lambdas. Keep `cmd`
      and `output`. `cmd(line)` raises `ScriptError` when `match(line)` is
      `None`, so a typo fails at the call instead of in the log.
- [ ] `validate_script` (task 1.4) asks `is_command_line`.

**Out of scope.** Sending script lines through the full command dispatcher,
so that any player command works from a script. That needs a permission
model for scripted objects running admin commands and is a separate design.
Record it in `BACKLOG.md` under engine design.

### 6.2 Events: one declaration per action type

An action type today is spread over an enum member, an optional hook name
derived by `_event_suffix`, a description in `STANDARD_EVENTS`, an optional
lock row and a hand-written payload row in the docs.

Create `realm/core/eventdefs.py`:

```python
@dataclass(frozen=True)
class EventDef:
    action_type: str                      # "item:on_get"
    hook: str | None = None               # "GET": the ON_GET softcode attribute
    doc: str = ""                         # one line for the generated reference
    payload: dict[str, str] = field(default_factory=dict)   # extra key -> meaning
    target_lock: tuple[str, str] | None = None   # (lock type, failure template)
    tool_lock: tuple[str, str] | None = None
    speech: bool = False                  # {actor} is a voice (see voice_as)
    owner: str = "kernel"

class EventRegistry:
    def register(self, event: EventDef, *, replace: bool = False) -> None: ...
    def get(self, action_type: str) -> EventDef | None: ...
    def hook_for(self, action_type: str) -> str | None: ...
    def hooks(self) -> dict[str, EventDef]: ...     # by hook name
```

Rules:

- Add `Feature.event(action_type, *, hook=None, doc="", payload=None,
  target_lock=None, tool_lock=None, speech=False)`.
- `hook_for` replaces `ScriptEngine._event_suffix`. An action type with no
  `EventDef` gets the derived suffix as before, so softcode `act()` with a
  made-up type still fires `ON_<SUFFIX>`.
- Hooks with no action type stay declarable: `ARRIVE`, `PUSH` and `TICK` are
  registered with `action_type=None` by the code that fires them.
- `enforce_lock_on_action` reads `target_lock` and `tool_lock` from the
  registry. Delete `TARGET_ACTION_LOCKS` and `TOOL_ACTION_LOCKS`.
- `Action.format_message` reads `speech` from the registry. Delete
  `_SPEECH_ACTIONS` (`propagation.py:41`).
- `ActionType` stays as a module of string constants for now. Step 7 splits
  it so each feature owns its own constants.

Owners:

| Owner | Action types |
|---|---|
| kernel | `ON_ENTER`, `ON_LEAVE`, `PRE_ENTER`, `LOOK`, `CONNECT`, `DISCONNECT`, `ON_FAIL`, `ACT`, `ON_RECEIVE`, `ON_RESET`, `ON_LOAD`, `ON_EXPIRE`; hooks `ARRIVE`, `TICK` |
| talk | `SPEECH`, `SHOUT`, `OOC`, `WHISPER`, `EMOTE`, `SEMIPOSE`, `EMIT`, each with `speech=True` where `_SPEECH_ACTIONS` lists it and the speech lock rows |
| items | the thirteen `item:*` types with the `ON_GET`, `ON_DROP`, `ON_PUT` and `ON_GIVE` lock rows; hook `PUSH` |
| combat | `ON_ATTACK`, `ON_DAMAGE`, `ON_DEATH`, `NARRATE`, `ON_HITPRCNT` |
| economy | `PAYMENT` |
| abilities | `ON_CAST` |

Tasks:

- [ ] Write `tests/test_event_registry.py` first:
  - [ ] The set of hook names from the registry under `CLASSIC` equals the
        keys of today's `STANDARD_EVENTS`, frozen in the test.
  - [ ] The lock rows from the registry equal today's two tables, frozen in
        the test.
  - [ ] A feature declares `event("heist:on_crack", hook="CRACK",
        payload={"tool": "the drill"}, target_lock=("crack", "{name} holds."))`.
        An `ON_CRACK` attribute fires, the lock blocks with the message, and
        `@events` lists it.
- [ ] Add the registry and `Feature.event`. Move every row to its owner.
- [ ] Delete `STANDARD_EVENTS`. `scripts/gen_softcode_docs.py` reads the
      registry of a `CLASSIC` world and generates both the hook table and
      the payload table.
- [ ] Rewrite `tests/test_payload_docs_match_engine.py`: keep its AST scan of
      what the engine really sends, and compare it with `EventDef.payload`
      instead of the hand-written doc table. The doc is generated, so it
      cannot drift from the declarations, and the test keeps the
      declarations honest.
- [ ] Add an `@events` command to `building` that lists hooks with owner and
      doc.

### 6.3 Lock types are open

- [ ] Replace `class LockType(str, Enum)` with string constants in the same
      module (`BASIC = "basic"` and so on) and a registry:
      `register_lock_type(name, *, default="True", doc="")`. The twelve
      current types register with their `DEFAULT_LOCKS` expression. Add
      `Feature.lock_type(...)`.
- [ ] `check_lock`, `get_lock`, `set_lock` and `parse_lock` take a `str`.
      Remove every `.value` access on a lock type (`lock_failure_message`
      builds `lock_fail_<type>` from it).
- [ ] `set_lock` on an unregistered type: accept it when it matches
      `^[a-z][a-z0-9_]*$`, and return a warning through `OpResult.warnings`
      when `difflib.get_close_matches` finds a registered name within 0.8.
      `@lock door/baisc = ...` prints "Set. Did you mean `basic`?". An
      unregistered type with no near match is a game's own lock and is
      silent.
- [ ] `check_lock` on a type with no lock set and no registered default
      passes. Today an unknown type falls to `"False"`
      (`locks.py:204`). **Decision (default: pass).** A game-defined lock
      that nobody set should not block.
- [ ] Tests: softcode `test_lock(obj, "crack", who)` on a game-defined type
      works with and without a registered default.

### 6.4 Entitlements are open

- [ ] `ALL_ENTITLEMENTS` becomes a registry:
      `register_entitlement(name, doc="")`. The seven current names plus
      `BUILD` and `MODERATE` from step 5 register in the kernel. Add
      `Feature.entitlement(name, doc="")`.
- [ ] `read_role_defs` keeps unregistered names instead of dropping them.
      A name within 0.8 of a registered one is reported as a problem by
      `reload_role_defs` (task 1.7), so `@reload` shows
      "role_def 'smuggler': unknown entitlement 'LOCK_BYPAS', did you mean
      'LOCK_BYPASS'?" and that one name is not granted.
- [ ] `has_entitlement(obj, name)` works for any string. Softcode
      `has_entitlement` is the way a game checks its own.
- [ ] Tests: a `role_def` granting `SMUGGLE` (unregistered, no near match)
      makes `has_entitlement(player, "SMUGGLE")` true; the near-miss case
      above is reported and not granted.

### 6.5 Audiences are open

- [ ] In `core/propagation.py` add
      `register_audience(name, resolver)` where
      `resolver(action) -> Iterable[GameObject]`. Register the four current
      audiences through it: `actor`, `target`, `room` (everyone in the
      delivery room except actor and target) and `remote` (the rooms in
      `extra['remote_rooms']`).
- [ ] `deliver_messages` loops over the audiences that have queued messages
      and asks the resolver for recipients. A message queued for an
      unregistered audience logs one WARNING per action type with the fix.
- [ ] Add `Feature.audience(name)` as a decorator.
- [ ] Tests: a feature registers `zone` (every player in rooms sharing the
      actor's zone). An action with `add_message("zone", ...)` reaches a
      player two rooms away and formats `{actor}` per recipient.

### 6.6 One definition loader

Six loaders scan every cached object for a tag and parse attributes:
`read_skill_defs`, `read_class_defs` (`systems/definitions.py`),
`read_role_defs` (`permissions/entitlements.py`), `find_behavior_def` and
`list_behavior_defs` (`behaviors/scripted.py`), `find_spell_def` and
`list_spell_defs` (`systems/spells.py`), `find_ability_def` and
`list_ability_defs` (`systems/abilities.py`). Each has its own cache policy
and its own name matching.

Create `realm/core/defs.py`:

```python
@dataclass(frozen=True)
class DefKind:
    name: str                              # "skill"
    tag: str                               # "skill_def"
    parse: Callable[[GameObject], Any] | None = None   # None returns the object
    key: Callable[[GameObject], str] = lambda obj: obj.name.lower()
    owner: str = "kernel"

def register_def_kind(kind: DefKind, *, replace: bool = False) -> None: ...
def all_defs(kind: str) -> dict[str, Any]: ...      # key -> parsed value
def find_def(kind: str, name: str) -> Any | None:   # exact key, then unique prefix
def invalidate(kind: str | None = None) -> None: ...
```

Rules:

- `all_defs` caches per kind. The cache is dropped when an object carrying
  the kind's tag is saved, tagged, untagged or destroyed. Hook this into the
  ops of step 5 (`tag`, `untag`, `set_attr`, `destroy`, `create`) through
  one `defs.touched(obj)` call, and into `Store.save`.
- Add a tag index to the `Store` protocol of task 2.3:
  `find_cached(tag=...)` reads `dict[str, set[str]]` maintained on save and
  delete instead of scanning the cache. Both stores implement it.
- A `parse` that raises is logged at WARNING with the object id and that
  definition is skipped. It never raises into the caller.
- Add `Feature.def_kind(name, tag, parse=None)`.

Tasks:

- [ ] Tests first: `tests/test_defs.py` covers caching, invalidation on
      `@set` and `@tag`, prefix matching, a failing parser, and a
      game-defined kind (`recipe_def`).
- [ ] Add the tag index to `PersistenceManager` and `MemoryStore`.
- [ ] Add `realm/core/defs.py`.
- [ ] Convert the six loaders to `DefKind` registrations owned by `rules`
      (skill, class), kernel (role, behavior) and `abilities` (ability,
      spell). Keep each public function as a one-line call into `defs` only
      where more than five call sites use it; otherwise change the callers.
- [ ] `@reload` calls `defs.invalidate()` and reports per-kind counts.

### 6.7 Global softcode commands

`get_search_objects` (`triggers.py:460`) searches room contents, the room,
the inventory and zone masters. Step 5 of its docstring, the Master Room, is
a TODO, so a game cannot add a softcode command that works everywhere.

- [ ] Objects tagged `global_commands` are searched last. Read them through
      `store.find_cached(tag="global_commands")`, which the tag index of 6.6
      makes cheap.
- [ ] Protect the tag. Generalize `may_change_role_tag`
      (`permissions/roles.py:194`) into
      `register_protected_tag(tag, required_tier)` and register
      `global_commands` at admin. The `tag` op of step 5 already calls the
      gate.
- [ ] Tests: a `$+finger *` attribute on a `global_commands` object fires
      from any room; a room-local `$+finger *` wins over it; a builder
      cannot add the tag.
- [ ] Remove the TODO lines at `triggers.py:469` and `:505`.

### Acceptance

- [ ] `git grep -n "SIMPLE_COMMAND_PREFIXES\|STANDARD_EVENTS\|TARGET_ACTION_LOCKS\|TOOL_ACTION_LOCKS\|_SPEECH_ACTIONS\|class LockType" realm/`
      returns nothing.
- [ ] `permissions/locks.py`, `scripting/triggers.py`,
      `scripting/sandbox.py` and `core/propagation.py` name no speech, item,
      combat, economy or magic action type.
- [ ] The feature tests of step 4 still pass, and the "subtract" test gains:
      without `items`, `ON_GET` is not a known hook and `get` is not a
      script verb.
- [ ] The suite is green.

### Docs

- [ ] `docs/reference/softcode.md` is regenerated; the hook and payload
      tables are now generated sections.
- [ ] `docs/guides/features.md` (written in step 4): one short section per
      vocabulary with a five-line example.
- [ ] `docs/architecture/events.md`: an action type is declared once, with
      its hook, payload and lock.
- [ ] `docs/design/engine_vision.md`, authority section: open lock types and
      entitlements, the near-miss guard.
- [ ] `docs/tutorial/04-softcode.md`: the list of script verbs comes from
      the registry; show `@events`.

### Closes

- BACKLOG "**Master Room** for global `$`-commands is a live TODO".
- The review findings "two softcode dialects", "a game-defined entitlement
  is dropped" and "audiences other than four are ignored".

---

## Step 7 — Move the files, replace the global setters, add boundary tests

**Goal.** The directory layout states the architecture, and three tests keep
it true. `realm/core`, `scripting`, `commands`, `permissions`, `persistence`,
`gateway`, `server` and `config` import nothing from `realm/std` or
`realm/games`. A world built with no features boots and passes the kernel's
own tests. The seventeen module-global setters are gone; one `World` handle
replaces them.

**Depends on.** Steps 1 to 6. Do not start while any of them has open boxes.

**This step changes no behavior.** Every task is a move, a rename or an
inversion. If a test needs a new assertion to pass, stop and log it.

**Non-goals.**

- Import cycles inside the kernel (403 deferred imports today). They shrink
  as a side effect; removing the rest is not part of this plan.
- Renaming `realm/core` to `realm/kernel`. The name stays. It costs 500
  import edits and buys nothing.

### 7.1 Target layout

```
realm/
  __init__.py          public facade (step 9)
  features.py          Feature, FeatureSet, load
  core/                objects, tags, attrflags, propagation, events, movement,
                       search, query, zones, beats, behaviors, dice, markup,
                       safe_eval, language, teardown, perception, ops, inflate,
                       defs, eventdefs, pools (step 8), world, action_types
  scripting/           sandbox, engine, triggers, verbs, registry, namespace,
                       handle, inline, bindings, scripted_behavior, ticker,
                       lib/ (kernel softcode functions only)
  commands/            base, dispatcher
  permissions/         locks, roles, entitlements
  persistence/         manager, memory, keyid, worldio
  gateway/             session, telnet, websocket
  server/              game, world (build_world), auth, puppet
  config/              loader
  packs/               content-pack loader
  testing/             Simulator
  std/                 one package per built-in feature
    accounts/ basics/ talk/ movement/ look/ items/ building/ rules/
    stealth/ combat/ effects/ abilities/ economy/ social/ crime/ npc/
    spawning/ instances/ wilderness/
  games/
    gurps/ d20/ merc/
```

Inside a feature package: `__init__.py` holds the `feature = Feature(...)`
declarations written in step 4, `commands.py` the command handlers,
`softcode.py` the softcode functions, `behaviors.py` the behaviors,
`actions.py` the action-type constants, and other modules as needed.
Appendix B maps every file.

### 7.2 One `World` handle instead of seventeen setters

Today a module that needs the store, the engine or a setting reads a module
global that some other module set at boot. Tests set and reset these by hand
(`set_active_manager` 49 times, `set_check_resolver` 56,
`set_combat_manager` 36, `reset_engine` 41, `set_game_system` 24). A test
that forgets one leaks state into the next.

Move the `World` dataclass of task 2.2 from `realm/server/world.py` to
`realm/core/world.py`. `build_world` stays in `realm/server/world.py`. Add:

```python
# realm/core/world.py
_current: World | None = None

def get_world() -> World:
    """The running world. Raises RuntimeError when none is installed."""
def find_world() -> World | None:
    """The running world or None. For code that legitimately runs without one."""
def set_world(world: World | None) -> World | None:
    """Install a world, return the previous one. build_world and tests call it."""
def setting(name: str):
    """The current world's setting, or the Settings class default when no
    world is installed. Pure helpers (markup, inline) stay usable in a unit
    test that builds nothing."""

@contextmanager
def use_world(world: World): ...     # set, yield, restore
```

`_current` is the only mutable module global left in the kernel after this
step. Two worlds in one process (a test that boots a second server on the
same file) use `use_world`.

Replacement table. Appendix C repeats it with call-site counts.

| Today | After |
|---|---|
| `get_engine()`, `reset_engine()` | `get_world().engine`; a new world has a new engine |
| `get_active_manager()`, `set_active_manager()` | `get_world().store` |
| `get_script_engine()`, `set_script_engine()` | `get_world().scripts` |
| `get_game_system()`, `set_game_system()` | `get_world().rules` |
| `get_combat_manager()`, `set_combat_manager()` | `get_world().services.get("combat")` |
| `set_check_resolver()`, `set_skill_defaults()` | fields of the `rules` feature's service, `get_world().services["checks"]` |
| `set_check_hook()` (`core/objects.py:154`) | `GameObject.visit_check` asks `find_world()` for `scripts` and calls `run_check_hook` |
| `set_group_formatter()` | `Feature.group_formatter`, stored on the `look` feature's service |
| `register_speech_renderer()`, `register_name_resolver()`, `register_dest_resolver()` | lists on `World`, filled by `Feature` declarations; the module functions are deleted |
| `set_emote_sigil()`, `set_markup_marker()`, `set_heredoc_sigils()`, `set_inline_delimiters()`, `set_keyid_sigil()`, `set_trigger_sigils()`, `set_interpreter_recursion_limit()`, `set_world_tick()`, `set_show_rolls_default()` | the use site calls `setting("EMOTE_SIGIL")` and so on; no push at boot |

Tasks, in three passes so the suite is green after each:

- [ ] **Pass 1, delegate.** Add `realm/core/world.py`. `build_world` calls
      `set_world`. Rewrite the body of every getter and setter in the table
      to read or write the current world. No call site changes. Suite green.
- [ ] Add to `tests/conftest.py`:
  - [ ] an autouse fixture that restores `set_world(None)` after every test;
  - [ ] `world`: a fixture returning
        `build_world(MemoryStore(), features=realm.features.load([]))`,
        installed;
  - [ ] `classic_world`: the same with `load(CLASSIC)`.
- [ ] **Pass 2, migrate.** One row of the table at a time: change every call
      site in `realm/` to the new form, then every test. A test that
      hand-wires services takes the `world` or `classic_world` fixture, or a
      `Simulator`, and sets the field on it. Suite green after each row.
- [ ] **Pass 3, delete.** Remove the getter and setter functions and their
      module globals. `git grep -n "^_[a-z_]* *\(: [^=]*\)\?= None$" realm/`
      should list `_current` and nothing else that is assigned by a setter.
- [ ] `GameServer.start` ends by logging the settings that differ from the
      defaults at INFO (one line each), replacing the block of `set_*` calls
      at `server/game.py:154-162` as the place a maintainer sees them.

### 7.3 Invert the kernel's imports of features

Every edge from a kernel module to a feature module, and its fix:

| Edge today | Fix |
|---|---|
| `commands/dispatcher.py:424` imports `core.render.render_room` in `_handle_exit` | `_handle_exit` moves to the `movement` feature as the dispatcher's **fallback resolver**: `Feature.fallback(fn)` registers `async fn(ctx) -> bool`, tried in order when no command matches. `movement` registers the exit matcher, the script engine registers `$`-command matching. The dispatcher no longer knows about exits |
| `core/movement.py:385` imports `core.checks.check` for skill-gated exits | `register_traversal_gate(fn)` with `async fn(actor, exit_obj, direction) -> str | None`; a string blocks with that message. The `rules` feature registers the `check_skill` gate through `Feature.traversal_gate` |
| `core/movement.py:486` imports `core.party.bring_followers` | `register_after_traverse(fn)` with `async fn(actor, origin, destination, exit_obj, *, fleeing)`. The `social` feature registers followers |
| `core/events.py:69` imports `core.teardown.release_contents` | `teardown` is kernel. No change |
| `core/propagation.py:206`, `core/search.py:74` import `core.language` | `language` is kernel. No change |
| `scripting/inline.py:150` imports `core.checks` | Already removed by task 3.3 |
| `commands/base.py:108,180` import `perception.can_see` | `perception` stays kernel after the split of 7.4 |
| `core/objects.py:445` imports `perception.perceived_name` | Same |
| `scripting/handle.py:53,223` import `functions.PROTECTED_ATTRS` | Already moved to `core/attrflags.py` by task 3.3 |
| `server/game.py` imports `combat`, `systems.crime`, `core.checks`, `core.render`, `core.verbs`, `core.instances`, `core.wilderness`, `behaviors` | Removed by step 4, except login and chargen, see 7.4 |
| `permissions/locks.py`, `core/events.py`, `core/movement.py`, `core/propagation.py` import all of `ActionType` | 7.4 |

Tasks:

- [ ] `Feature.fallback`, `Feature.traversal_gate`, `Feature.after_traverse`
      with tests in `tests/test_features.py`: without `movement`, typing an
      exit name is an unknown command; without `rules`, an exit with
      `check_skill` set is passable and `@examine` shows a warning that the
      attribute has no effect; without `social`, nobody follows.
- [ ] Move `_handle_exit`, `_find_exit` and their helpers. Today
      `CommandDispatcher._execute` tries direct match, alias, unique prefix,
      exit name, then the unknown handler (`$`-commands), then "Huh?". The
      fallback order under `CLASSIC` must keep that; pin it with a test
      before moving.
- [ ] `DIRECTION_ALIASES` (`dispatcher.py`, parse step 6) is movement
      vocabulary in the kernel parser. Delete it and declare `n`, `s`, `e`
      and the rest as aliases on the direction commands in `movement`.
- [ ] `TOKEN_MAP` (`dispatcher.py:91`) maps `"`, `'`, `:`, `;` and `\` to
      talk commands. Delete it and add `token=` to `Feature.command`
      (`feature.command("pose", cmd_pose, token=":")`). The dispatcher keeps
      the mechanism, a registry of one-character prefixes, and no entries.
      A duplicate token raises `FeatureError`.
- [ ] `dispatcher.set_login_handler` and `set_unknown_handler` stay as the
      kernel slots; 7.4 fills the first from a feature.

### 7.4 Split the mixed files

**`core/action_types.py`.** Keep `ActionType` in the kernel with the twelve
kernel members listed in 6.2. Each owning feature gets an `actions.py` with
its own `StrEnum`:

| New enum | Module | Members |
|---|---|---|
| `TalkAction` | `std/talk/actions.py` | `SPEECH`, `SHOUT`, `OOC`, `WHISPER`, `EMOTE`, `SEMIPOSE`, `EMIT` |
| `ItemAction` | `std/items/actions.py` | the thirteen `item:*` members |
| `CombatAction` | `std/combat/actions.py` | `ON_ATTACK`, `ON_DAMAGE`, `ON_DEATH`, `NARRATE`, `ON_HITPRCNT` |
| `EconomyAction` | `std/economy/actions.py` | `PAYMENT` |
| `AbilityAction` | `std/abilities/actions.py` | `ON_CAST` |

String values do not change, so saved worlds and softcode are unaffected.

- [ ] Split the enum. 27 engine files and 1 test file reference
      `ActionType.<MEMBER>`; rewrite each reference to its new enum.
- [ ] `tests/test_payload_docs_match_engine.py::_action_type_value` resolves
      `ActionType.X` by name. Teach it the five new enums.

**`core/perception.py`.** The kernel keeps sight as a mechanism: `can_see`,
`can_see_room`, `room_is_lit`, `display_markers`, `perceived_name`, the name
resolvers, invisibility and darkness. Stealth leaves.

- [ ] Add `register_sight_rule(fn)` with `fn(viewer, obj) -> bool | None`.
      `False` hides, `None` has no opinion. `can_see` runs the rules after
      its own checks.
- [ ] Move to `std/stealth/`: the `HIDDEN_TAG` branch of `can_see` (as a
      sight rule), the `hidden` marker of `display_markers` (as a marker
      rule on the same pattern), `break_stealth`, `stealth_observer` and the
      loud-action set at `perception.py:42`. Move `cmd_hide`, `cmd_search`
      and `cmd_pick` from `commands/builtin/manipulation.py`.

**`core/verbs.py`.** No kernel code remains in it.

- [ ] `do_say`, `do_pose`, `do_semipose`, `do_emit`, `do_whisper`, the
      `*_action` builders, `_speak` and the emote-reference parser move to
      `std/talk/verbs.py`.
- [ ] `gate_item_action`, `do_get`, `do_drop`, `do_give`, `do_open`,
      `do_close` move to `std/items/verbs.py`.
- [ ] Delete `core/verbs.py`.

**`scripting/engine.py`.** Steps 4 and 6 already moved the queue kinds and
the verb handlers out. What is left is kernel.

- [ ] Move the wait scheduler (`schedule_wait`, `cancel_wait`, `_wait_timer`,
      `_deliver_wait`, `tick_waits`, `shutdown_waits`) to
      `scripting/waits.py` as a `WaitScheduler` owned by the engine.
- [ ] Confirm the module imports nothing from `realm.std` or `realm.games`.

**`scripting/functions.py`.** Task 3.4 split it into `scripting/lib/*.py`
by owner. Now move each feature's file next to the feature
(`std/combat/softcode.py`, `std/economy/softcode.py`, and so on). The kernel
keeps objects and attributes, tags and zones, locks and permissions,
messaging and prompts, dice, movement, events, time and scheduling, text,
math and logic. Appendix A lists the owner of every function.

**`server/game.py`.** The server keeps sockets, sessions, the tick loop, the
reaper loop, start and stop. Login, character creation and `who` are policy.

- [ ] Add an **input interceptor** list to the server:
      `Feature.input_interceptor(fn, *, order=0)` with
      `async fn(world, session, line) -> bool`. `_on_command` runs: the
      session's own `input_handler`, then interceptors in order, then the
      dispatcher. The chargen branch at `server/game.py:800` becomes an
      interceptor.
- [ ] Add `Feature.login(fn)` with `async fn(ctx) -> None`. It fills the
      dispatcher's existing login slot (`set_login_handler`), which receives
      input from a session with no player. Exactly one may be registered.
- [ ] Create the feature `accounts` in `std/accounts/` and move
      `_handle_login`, `_do_connect`, `_do_create`, `_handle_chargen`,
      `_enter_world`, `_announce_connect`, `_do_who`, `_get_welcome_screen`
      and `_default_welcome_screen` into it. `accounts` requires nothing;
      it reads `world.rules` for chargen steps when a rules system exists.
- [ ] Add `accounts` to `CLASSIC`. With no login handler registered the
      server prints one line, "This world has no login feature installed."
- [ ] `GameSystem`, `ChargenStep`, `ChoiceStep`, `resolve_game_system`,
      `equipment_observer` and `reload_rules` move from `systems/base.py` to
      `std/rules/system.py`. `World.rules` is typed `Any | None`; the
      kernel never calls a method on it.
- [ ] `behaviors/scripted.py` and `behaviors/ticker.py` are kernel: move
      them to `scripting/scripted_behavior.py` and `scripting/ticker.py`.

### 7.5 Move the files

Mechanics:

- [ ] Write `scripts/dev/move_modules.py`. Input: a JSON map of old dotted
      module path to new dotted module path. It runs `git mv`, creates
      missing `__init__.py` files, and rewrites `from X import`, `import X`,
      `import X as`, string literals that are dotted paths (`GAME_SYSTEM`
      values, `patch("realm....")` targets in tests) and backticked module
      paths in `docs/**/*.md`, across `realm/`, `tests/`, `docs/`,
      `examples/`, `scripts/` and `realm/templates/`. It prints every file it
      changed and every occurrence of an old path it could not rewrite.
- [ ] After each batch: `ruff check realm/ tests/`, `pytest -q`, then
      `git grep` for each old path. No shim modules, no re-exports.

Batches, smallest blast radius first. Counts are import statements in
engine code plus tests.

| Batch | Moves | Import sites |
|---|---|---|
| A | `systems/{gurps,d20,merc}.py`, `combat/rulesets/*` to `games/*` | part of 33 + 31 |
| B | `core/instances.py`, `core/wilderness.py`, `systems/crime.py`, `behaviors/{npc,decay,spawner,zone_reset,shop,caster,effects}.py` | part of 22 + 32 |
| C | `core/{economy,disposition,party,describe,pairing,render}.py` | 36 + 34 |
| D | `core/checks.py`, `systems/{base,definitions,abilities,spells}.py` | 25 + 44 and the rest of `systems` |
| E | `combat/*` to `std/combat/` | 60 + 87 |
| F | `commands/builtin/*`, `commands/olc/*` | 21 + 79 |
| G | the splits of 7.4 | |

- [ ] Batch A. `GAME_SYSTEM` values become `realm.games.gurps.GurpsSystem`,
      `realm.games.d20.D20System`, `realm.games.merc.MercSystem`. Update
      `realm/config/loader.py`'s default, the templates, the examples and
      the docs. Short names (`"gurps"`) resolve through the `ruleset` and
      feature registries, not through a hardcoded dict.
- [ ] Batch B.
- [ ] Batch C.
- [ ] Batch D.
- [ ] Batch E.
- [ ] Batch F. Delete the empty `realm/commands/builtin/`,
      `realm/commands/olc/`, `realm/behaviors/`, `realm/systems/` and
      `realm/combat/` packages.
- [ ] Batch G.
- [ ] Remove every import that has become unused, and every deferred import
      that no longer needs deferring (ruff `F401`, then a manual pass over
      function-level imports in the moved files).

### 7.6 Boundary tests

Create `tests/test_boundaries.py`. These three tests are the definition of
"kernel" from here on.

- [ ] `test_kernel_imports_nothing_above_it`. Parse every `.py` file under
      `realm/core`, `scripting`, `commands`, `permissions`, `persistence`,
      `gateway`, `server`, `config`, `packs` and `realm/features.py` with
      `ast`. Collect every `Import` and `ImportFrom`, including those inside
      functions and under `TYPE_CHECKING`. Fail on any module path starting
      with `realm.std` or `realm.games`. One allowed exception, named in the
      test: `realm/config/loader.py` may name `realm.std.CLASSIC` as the
      default value of `FEATURES`, as a string.
- [ ] `test_std_features_do_not_import_games`. The same scan over
      `realm/std`: no import of `realm.games`.
- [ ] `test_feature_requires_match_imports`. For each feature package,
      every import of another `realm.std.<x>` package must be listed in that
      feature's `requires`.
- [ ] `test_bare_kernel_boots`. `Simulator(features=[])`: create two
      objects and a room through ops, set an attribute, run a softcode
      attribute that calls `pemit`, propagate a custom `act()` and observe
      an `ON_<HOOK>` fire, save to SQLite and load in a second world. No
      command other than the dispatcher's unknown-command reply exists.
- [ ] `test_stock_game_is_only_a_feature_list`. `sys.modules` after
      `Simulator(features=[])` contains no `realm.std.*` and no
      `realm.games.*` module. After `Simulator()` with defaults it contains
      exactly the packages named by `CLASSIC` and the configured game.
- [ ] Name the file in `docs/development/contributing.md` as the rule for
      where new code goes. The repository has no CI workflow; the tests run
      with the suite.

### Acceptance

- [ ] `tests/test_boundaries.py` passes.
- [ ] `realm/commands/` contains `base.py` and `dispatcher.py` only.
      `realm/core/` contains no module named in the right column of
      Appendix B.
- [ ] `git grep -n "def set_[a-z_]*(" realm/core realm/scripting realm/persistence realm/gateway`
      lists only object-level operations (`set_lock`, `set_attr_flags`) and
      `set_world`.
- [ ] Record `wc -l` over the kernel packages in the Decision log. Before
      the plan the kernel was about 10,500 lines plus about 4,800 in the
      five mixed files. Expect 11,000 to 13,000. A larger number means
      feature code stayed behind; find it before ticking this box.
- [ ] The suite is green with the same test count as at the end of step 6
      plus the boundary tests.

### Docs

- [ ] `docs/architecture/overview.md`: rewrite around the three rings with
      the layout of 7.1.
- [ ] `CLAUDE.md` and `README.md`: the module map and "where does new code
      go".
- [ ] `docs/development/contributing.md`: the boundary tests.
- [ ] `docs/development/testing.md`: the `world` and `classic_world`
      fixtures replace hand-wiring.
- [ ] `docs/api/*.md`: module paths.
- [ ] `VISION.md`: mark the microkernel thesis as enforced by test, with the
      test names.

### Closes

- The review findings "12 of 30 `core` modules are features", "91 of 119
  modules load for any world", "17 module-global setters" and "two
  composition roots".

---

## Step 8 — Pools: entity-agnostic health and resources

**Goal.** Nothing in the engine writes `hp` by name. Damage, healing and
costs go through one small kernel module that understands "a bounded number
on an object". A ship with shields and a hull, a door with structure points
and a character with a harm clock all work with stock combat, stock effects
and stock abilities, and a game states which pool takes damage in data.

**Depends on.** Steps 4, 5 and 7. Task 1.8 must be done.

This implements VISION invariant 7, entity-agnostic mechanics.

Today `hp` is written at 16 sites in 11 modules, and the sites disagree.
`Combatant.take_damage` and the damage-over-time effect clamp at zero;
`apply_resisted`, the Merc ruleset and softcode `damage()` do not. Softcode
`damage()` queues a death check; the effect and the ruleset rely on their
callers. A missing `hp` means "immune" in three places and zero in two.
`is_defeated` is `hp <= 0` in all three rulesets. `ON_HITPRCNT` fires only on
the swing path (`combat/system.py:300`), so a poison tick never triggers it.
Ability costs already read any attribute as a pool
(`systems/abilities.py::_pay_cost`), with a fourth set of rules.

### 8.1 The pool module

Create `realm/core/pools.py`. It is kernel: numbers on objects, no dice, no
rules.

```python
@dataclass(frozen=True)
class Pool:
    name: str                          # "hp"
    attr: str | None = None            # storage attribute, default: name
    max_attr: str | None = None        # default: "max_" + name; a missing value means unbounded
    direction: Literal["down", "up"] = "down"
                                       # down: harm lowers it, spent at <= spent_at
                                       # up:   harm raises it, spent at >= max (stress, harm clocks)
    floor: int | None = 0              # lowest stored value for a down pool; None allows negatives
    spent_at: int = 0                  # a down pool is spent at or below this
    overflow: str | None = None        # harm this pool could not absorb goes to the named pool
    soak_attr: str | None = None       # flat reduction read from this attribute before harm lands
    owner: str = "kernel"

@dataclass
class PoolChange:
    obj: GameObject
    pool: str
    old: int
    new: int
    requested: int                     # amount asked for, always positive
    applied: int                       # amount this pool took
    soaked: int = 0
    spilled: "PoolChange | None" = None   # the change made to the overflow pool
    @property
    def became_spent(self) -> bool: ...   # crossed into spent on this change
    @property
    def total_applied(self) -> int: ...   # applied plus everything spilled

def pool_def(obj, name) -> Pool | None
def pool_get(obj, name) -> int | None          # None: the object has no such pool
def pool_max(obj, name) -> int | None
def has_pool(obj, name) -> bool
def is_spent(obj, name) -> bool
def damage_pool(obj) -> str | None             # where harm lands first
def vital_pool(obj) -> str | None              # end of the overflow chain from damage_pool

def harm(obj, name, amount, *, soak=False) -> PoolChange       # sync, in memory
def mend(obj, name, amount) -> PoolChange                      # sync, in memory
def spend(obj, name, amount) -> PoolChange | None              # all or nothing; None when short
def set_pool(obj, name, value, *, max=None) -> None            # initialize or resize (chargen, level gain)

async def settle(change: PoolChange, *, source: GameObject | None = None) -> None
```

Rules:

- **Storage does not change.** A pool named `hp` is the attributes `hp` and
  `max_hp`, exactly as saved today. Softcode and content that read
  `get_attr(obj, "hp")` keep working. No migration.
- **Where a definition comes from**, first match wins:
  1. the object's own `pools` attribute, a dict of name to partial spec:
     `@set ship/pools = {"shields": {"overflow": "hull"}, "hull": {"soak_attr": "armor"}}`;
  2. the same attribute on the object's `parent`;
  3. a world default registered by the active rules system
     (`GameSystem.pools() -> list[Pool]`) or by a feature
     (`Feature.pool(Pool(...))`);
  4. implicit: any attribute holding a number is a pool with default
     settings. This is what makes `{"pool": "mana", "n": 15}` costs work
     today and it stays.
- `damage_pool(obj)` is `obj.db.damage_pool`, else the setting `DAMAGE_POOL`
  (default `"hp"`), and `None` when the object has no such pool. An object
  with no damage pool cannot be harmed; callers treat it as "immune", as the
  `hp is None` branches do today.
- `harm` and `mend` are synchronous and touch memory only, so the softcode
  worker thread can call them. They fire nothing.
- `settle` is the async half. It propagates `pool:on_change` (hook `POOL`,
  payload `pool`, `old`, `new`, `applied`, `source`) and, when
  `became_spent`, `pool:on_spent` (hook `SPENT`, same payload). It walks
  `spilled` and settles each link. Softcode queues a `pool_settle` queue
  kind, which replaces `death_check`.
- Measure before optimizing: `settle` adds one propagation per change. If a
  profile of the combat tests shows it matters, skip `pool:on_change` when
  no observer and no witness has an `ON_POOL` hook. Do not add that
  speculatively.

Softcode, kernel-owned: `pool(obj, name)`, `pool_max(obj, name)`,
`has_pool(obj, name)`, `spent(obj, name)` are read-only. `harm_pool(obj,
name, n)` is harm-gated. `mend_pool(obj, name, n)` and `spend_pool(name, n)`
(on the executor) are not.

Tasks:

- [ ] Write `tests/test_pools.py` first, in a bare world (`features=[]`):
  - [ ] `harm` clamps a down pool at `floor`; with `floor=None` it goes
        negative; `mend` caps at max and is unbounded without one.
  - [ ] An up pool: `harm` raises it and caps at max; it is spent at max;
        `mend` lowers it and stops at zero.
  - [ ] Overflow: 10 harm into shields holding 4 leaves shields at 0 and
        puts 6 into the hull; `total_applied` is 10; the hull's `soak_attr`
        of 2 makes it 4 when `soak=True`.
  - [ ] Definition lookup order 1 to 4, including a parent.
  - [ ] `spend` returns `None` and changes nothing when short.
  - [ ] An object with no pool: `pool_get` is `None`, `harm` returns a
        change with `applied == 0`.
  - [ ] `settle` fires `ON_POOL` then `ON_SPENT`, once each, and `ON_SPENT`
        only on the crossing.
  - [ ] An overflow cycle (`a -> b -> a`) raises `ValueError` naming both.
- [ ] Add `realm/core/pools.py`, `Feature.pool`, the two events through
      `eventdefs`, the softcode functions and the `pool_settle` queue kind.

### 8.2 Convert the write sites

Every site becomes `pools.harm`, `pools.mend` or `pools.spend` followed by
`settle` where the context is async.

| Site | Today | After |
|---|---|---|
| `combat/combatant.py:181` (`hp` setter), `:211` (`take_damage`), `:232` (`heal`) | writes `hp` via `set_stat` | `Combatant.take_damage` and `heal` call `harm` and `mend` on `damage_pool(obj)` and return `PoolChange.total_applied`. Delete the `hp` setter. `hp`, `max_hp` and `hp_percent` become read-only views of the vital pool, renamed `vital`, `vital_max`, `vital_percent` |
| `combat/damage.py:116` (`apply_resisted`) | `target.db.hp = hp - dealt` | `harm(target, damage_pool(target), dealt, soak=True)` |
| `combat/rulesets/merc.py:141` | `apply_damage` writes `hp` through `set_stat` | `Ruleset.write_damage(target, amount)` in the base class does the `harm`. GURPS and D20 reach the same helper through `Combatant.take_damage` |
| `systems/gurps.py:163`, `systems/d20.py:100`, `systems/merc.py:155` | chargen sets `hp` and `max_hp` | `set_pool(player, "hp", value, max=value)` |
| `systems/merc.py:287` | level gain raises `max_hp` and `hp` | `set_pool(player, "hp", hp + gain, max=max_hp + gain)` |
| `combat/behaviors.py:235` | the healer behavior | `mend` then `settle` |
| `behaviors/effects.py:212`, `:362` | damage over time, regeneration | `harm` or `mend`, then `settle` |
| `commands/builtin/combat.py:322` | `firstaid` | `mend` then `settle` |
| `scripting/functions.py:831`, `:848` | softcode `damage`, `heal` | `harm` or `mend` on the damage pool; queue `pool_settle` |
| `systems/abilities.py:381` | an ability's heal effect | `mend` then `settle` |
| `systems/abilities.py::_pay_cost` | reads and writes any attribute | `spend(actor, pool, n)`; `None` blocks with the same messages |

`deal_damage` (`combat/damage.py:34`) stays the one interceptable entry for
hostile damage: it fires the damage event so wards and armor can change the
amount, then calls the ruleset, which calls `write_damage`. Softcode
`damage()` stays the deliberate bypass of interception, as documented today.

Tasks:

- [ ] Before touching a site, add a characterization test for any site the
      suite does not already pin. To find out, change that line to `raise`
      and run the suite; a green suite means the site is unpinned.
- [ ] Add `Ruleset.write_damage` and convert the three rulesets.
- [ ] Convert the remaining rows, one commit per row.
- [ ] `Ruleset.is_defeated` gets a default in the base class:
      `is_spent(obj, vital_pool(obj))`. Delete the three identical
      overrides. A ruleset may still override (a GURPS death check).
- [ ] Readers: `combat/manager.py:39`, `combat/encounter.py:561`,
      `combat/system.py:276,306,365,466`, `combat/strategy.py::CombatView`,
      `commands/builtin/combat.py:190,308,327`, `systems/abilities.py:412`
      read through `pool_get`, `pool_max` or the `vital*` views.
      `CombatView.hp` and `hp_percent` keep their names; they are the public
      strategy API and now report the vital pool.

### 8.3 One death observer, one threshold observer

- [ ] In the combat feature, register an observer for `pool:on_spent`: when
      the pool is the object's vital pool, call
      `CombatManager.handle_death(obj, killer=source)`. Delete the
      `death_check` queue kind (`engine.py:1119`) and every direct
      `is_defeated` then `handle_death` pair outside the encounter loop.
- [ ] Move the `ON_HITPRCNT` check from `combat/system.py:300` to an
      observer on `pool:on_change` for the vital pool. It now fires for
      poison, traps and softcode damage too. Add a test for a poison tick.
      This is a deliberate behavior change; note it in the changelog section
      of `docs/design/combat.md`.
- [ ] `handle_death` tags a player `unconscious` and turns an NPC into a
      corpse. Make the branch data-driven: `obj.db.on_spent` may be
      `"unconscious"`, `"corpse"`, `"destroy"` or `"none"`; the default is
      today's rule by kind. A ship sets `"none"` and handles `ON_SPENT` in
      softcode.

### 8.4 A neutral `GameSystem` base

`GameSystem` (`std/rules/system.py` after step 7) carries point-buy defaults:
`improve_cost`, `death_award`, `grant_award` banking `character_points`, and
`score_lines` printing them. A level-based or diceless game inherits a
character-point economy it has to switch off.

- [ ] `GameSystem` keeps the interface with neutral defaults:
      `improve_cost` returns `None` (the `improve` command then says the
      game has no skill purchase), `death_award` returns 0, `grant_award`
      does nothing, `score_lines` lists the object's pools, `pools()`
      returns `[Pool("hp")]`.
- [ ] Add `PointBuyMixin` with today's defaults. `GurpsSystem` uses it.
      `D20System` and `MercSystem` already override what they need; verify
      each override still applies and drop the ones that now equal the
      neutral default.
- [ ] `MercSystem.pools()` returns `hp`, `mana` and `move`.

### 8.5 Proof

Create `tests/test_pools_in_play.py`. No test in this file may define a
`hp` attribute on the non-character entity.

- [ ] **A ship.** An object with `pools` as in 8.1, `shields=20`,
      `max_shields=20`, `hull=30`, `max_hull=30`, `armor=2`,
      `damage_pool="shields"`, `on_spent="none"` and an `ON_SPENT` attribute.
      A player attacks it with the stock `attack` command under each of the
      three rulesets. Shields fall first, then the hull less soak, the
      `ON_SPENT` hook fires once when the hull is spent, and no `hp`
      attribute appears on the ship.
- [ ] **A harm clock.** A character with
      `pools={"harm": {"direction": "up"}}`, `harm=0`, `max_harm=6`,
      `damage_pool="harm"`. Softcode `damage(target, 2)` three times: harm
      reads 2, 4, 6, and the death path runs on the third.
- [ ] **A door.** A `structure` pool on an exit, damaged by an ability
      effect, destroyed on spent through `on_spent="destroy"`.
- [ ] **Costs.** An ability with `{"pool": "heat", "n": 3}` on a ship with an
      up pool `heat`: `spend` raises heat and blocks at max.
- [ ] **Unchanged play.** The existing combat, effects, spells and
      abilities tests pass with no change to their `hp` assertions.

### Acceptance

- [ ] `git grep -nE "db\.hp *[-+]?=[^=]|db\.set\(['\"]hp['\"]|set_stat\(['\"]hp['\"]" realm/`
      returns nothing.
- [ ] `git grep -n "'hp'\|\"hp\"" realm/` lists only `Pool("hp")` defaults,
      the `DAMAGE_POOL` setting and content templates.
- [ ] `tests/test_pools.py` and `tests/test_pools_in_play.py` pass. The
      suite is green.
- [ ] `tests/test_boundaries.py` still passes: `realm/core/pools.py` imports
      nothing from `realm.std`.

### Docs

- [ ] New guide `docs/guides/pools.md`: the ship, the harm clock and the
      door as worked examples. Add it to `mkdocs.yml`.
- [ ] `docs/design/combat.md`: damage lands in a pool; death is an observer.
- [ ] `docs/guides/creating-your-own-system.md`: `pools()`, the neutral
      base, `PointBuyMixin`.
- [ ] `docs/guides/abilities.md` and `docs/guides/spells.md`: costs use
      pools, including up pools.
- [ ] `docs/guides/interception.md`: where soak sits relative to wards and
      resistances.
- [ ] Regenerate the softcode reference and the config reference.
- [ ] `VISION.md`: invariant 7 cites the pool module as its first full
      instance.

### Closes

- The review findings "`hp` written at 16 sites in 11 modules" and "the
  `GameSystem` base assumes point-buy".
- The BACKLOG design note under the HARM entry, "taking damage is
  entity-agnostic (people/mobs/ships/doors), must not be attach-or-forget".
  Pools are that mechanism.

---

## Step 9 — A public face: imports, add-ons, packaging, scaffold

**Goal.** A game author installs REALM with `pip`, runs `realm init`, and
has a game directory with one obvious place for code, a passing test and one
page of documentation that says where everything goes. A third party can
publish a feature as a package. The names a game may import are listed and
frozen by a test.

**Depends on.** Steps 4 and 7. Step 8 for `Pool` in the public names.

Today `realm/__init__.py` exports `__version__` only, so every example
imports from deep module paths that steps 3 to 7 just moved. `realm init
--template` reads `Path(__file__).parent.parent / "examples"`
(`cli.py:31`), which does not exist in an installed wheel
(`pyproject.toml` packages `realm` only). The ROM importer lives in
`scripts/`, also outside the wheel.

### 9.1 The public names

- [ ] `realm/__init__.py` exports, with an explicit `__all__`:

      | Name | From |
      |---|---|
      | `Feature`, `FeatureError` | `realm.features` |
      | `CLASSIC` | `realm.std` |
      | `GameObject` | `realm.core.objects` |
      | `Action`, `propagate`, `fire_event` | `realm.core.propagation`, `realm.core.events` |
      | `ActionType` | `realm.core.action_types` |
      | `Behavior` | `realm.core.behaviors` |
      | `CommandContext` | `realm.commands.dispatcher` |
      | `Pool`, `pools` | `realm.core.pools` |
      | `ops`, `OpError` | `realm.core.ops` |
      | `World`, `get_world` | `realm.core.world` |
      | `check_lock`, `controls`, `has_entitlement` | `realm.permissions` |
      | `Settings` | `realm.config.loader` |
      | `softcode_function` | `realm.scripting.registry` |

- [ ] Rules and combat types are not in the root, because a bare world must
      not load them. Their public homes are `realm.std.rules`
      (`GameSystem`, `PointBuyMixin`, `ChargenStep`, `ChoiceStep`, `check`)
      and `realm.std.combat` (`Ruleset`, `Combatant`, `deal_damage`,
      `CombatView`). Each feature package's `__init__.py` gets an `__all__`.
- [ ] `realm.testing` exports `Simulator` and the `world` fixtures as a
      pytest plugin (`pytest_plugins = ["realm.testing.fixtures"]`), so a
      game's tests get them with one line.
- [ ] Importing `realm` must not import `realm.std.<feature>` modules. Use a
      module-level `__getattr__` for `CLASSIC` if needed. The boundary test
      `test_stock_game_is_only_a_feature_list` already checks this.
- [ ] State the rule in `docs/reference/public-api.md`: public means
      `realm.__all__`, `realm.features`, `realm.testing` and each
      `realm.std.<feature>.__all__`. Everything else may move without notice.
- [ ] `tests/test_public_api.py`:
  - [ ] `realm.__all__` equals a list frozen in the test. Changing the
        public surface is then a deliberate edit.
  - [ ] Every fenced `python` block in `docs/**/*.md`, `README.md` and the
        templates is parsed with `ast`; every `import realm...` and
        `from realm... import name` in it resolves. A block that is
        intentionally partial opts out with a first line `# doctest: skip`.
- [ ] Rewrite imports in `examples/`, `realm/templates/` and the guides to
      use the public names.

### 9.2 Add-on features as installable packages

- [ ] `realm.features.load` resolves a name in this order: the built-in
      table, the entry-point group `realm.features`, a dotted module path.
      A third-party package declares:

      ```toml
      [project.entry-points."realm.features"]
      weather = "realm_weather:feature"
      ```

- [ ] An installed feature is **available**, not enabled. It runs only when
      a game lists it in `FEATURES`. Nothing is activated by installation.
- [ ] A name defined by both an entry point and the built-in table raises
      `FeatureError` at load.
- [ ] Add `realm features` to the CLI. With no argument it prints every
      available feature with its source (built-in, installed package, game
      directory), its requirements and counts of what it declares. With
      `--check` it loads the game's `FEATURES` and reports collisions and
      missing requirements without starting the server.
- [ ] Test with a fake distribution: write a `*.dist-info/entry_points.txt`
      under `tmp_path`, put it on `sys.path`, and load the feature by name.

### 9.3 Everything the CLI needs is inside the wheel

- [ ] `git mv examples realm/examples`. Resolve it with
      `importlib.resources.files("realm.examples")`. Fix the six test
      references and the docs.
- [ ] Move `scripts/rom_import.py` and `scripts/rom_import_batch.py` to
      `realm/tools/rom_import.py` and add `realm import-rom <area files>
      [--out pack.json]`. Update `docs/development/rom-import.md`.
- [ ] `scripts/` keeps developer tools only: the doc generators, the
      example builders and `scripts/dev/move_modules.py`.
- [ ] `tests/test_packaging.py`: copy the `realm/` package directory alone
      to `tmp_path`, set `PYTHONPATH` to it, and in a subprocess run
      `python -m realm.cli init demo --template spacegame` from a different
      working directory, then `python -m realm.cli features`. Both succeed.
      This proves nothing reads a sibling of the package.
- [ ] `pyproject.toml`: `requires-python` says 3.12 while the classifiers,
      ruff and mypy say 3.11. Make all four agree on 3.12. Add the
      `realm.features` entry-point group documentation URL to `[project.urls]`.

### 9.4 The scaffold

`realm init mygame` writes:

```
mygame/
  config.py          settings and FEATURES
  game.py            feature = Feature("mygame"), with three commented examples
  rules.py           the game's GameSystem subclass
  data/welcome.txt
  tests/test_game.py a Simulator smoke test
  README.md          start, connect, where code goes, how to test
```

- [ ] Add `tests/test_game.py` to the scaffold: boot a `Simulator` from the
      game's own `config.py`, connect a player, `look`, and assert the
      startup room renders.
- [ ] Add `--features classic|social|bare` to `realm init`. `classic` is the
      default. `social` writes `FEATURES = ["accounts", "basics", "talk",
      "movement", "look", "items", "building", "game"]` and omits
      `rules.py`. `bare` writes `["accounts", "building", "game"]`.
- [ ] Extend `tests/test_init_scaffold.py`: for each preset, scaffold into
      `tmp_path` and run the scaffold's own tests in a subprocess.
- [ ] The scaffold `README.md` is ten lines and links to one page,
      `docs/getting-started/first-game.md`.

### 9.5 One page that says where things go

- [ ] `docs/guides/features.md` opens with this table, each row linking to
      a five-line example further down:

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

- [ ] `README.md`: the first screen is install, `realm init`, `realm start`
      and that table's link. Move the architecture description below it.
- [ ] `docs/index.md` and the `mkdocs.yml` nav: "Getting Started" then
      "Build your game" (features, pools, rules, content packs) then
      "Softcode" then "Reference" then "Design notes".
- [ ] `CLAUDE.md`: replace the extension-point list with the same table and
      the three boundary tests.
- [ ] Add `CHANGELOG.md` with one entry for this plan: the module moves of
      Appendix B, the removed config callbacks, the `GAME_SYSTEM` paths, the
      `ON_HITPRCNT` change. State what did not change: saved worlds, action
      type strings, softcode function names, content packs.
- [ ] Bump `__version__` and `pyproject.toml` to `0.2.0`.

### Acceptance

- [ ] `tests/test_public_api.py`, `tests/test_packaging.py` and the scaffold
      tests pass. The suite is green.
- [ ] From an empty directory with only the package on the path:
      `realm init demo && cd demo && pytest -q && realm features --check`
      succeeds.
- [ ] A game file in the scaffold imports from `realm`, `realm.std.<x>` and
      `realm.testing` only.

### Closes

- The review findings "`realm/__init__.py` exports only `__version__`" and
  "templates and importers are outside the wheel".
- BACKLOG entries about the scaffold and first-run experience; list them in
  the Decision log as they are closed.

---

## Appendix A — Softcode functions and their owners

Generated from `scripts/gen_softcode_docs.py::CATEGORIES`, `_READONLY` and
`_HARM_GATED` at the baseline commit. 98 functions: 81 kernel, 17 owned by
seven features. Step 3 turns the three right-hand columns into decorator
arguments; this table is the expected result of the parity test in task 3.2.
`me`, `here` and `enactor` are context names, not functions.

| Group | Function | Read-only | Harm-gated | Owner |
|---|---|---|---|---|
| Objects & attributes | `get` | yes |  | kernel |
| Objects & attributes | `get_attr` | yes |  | kernel |
| Objects & attributes | `set_attr` |  |  | kernel |
| Objects & attributes | `has_attr` | yes |  | kernel |
| Objects & attributes | `del_attr` |  |  | kernel |
| Objects & attributes | `V` | yes |  | kernel |
| Objects & attributes | `incr` |  |  | kernel |
| Objects & attributes | `decr` |  |  | kernel |
| Objects & attributes | `name` | yes |  | kernel |
| Objects & attributes | `loc` | yes |  | kernel |
| Objects & attributes | `owner` | yes |  | kernel |
| Objects & attributes | `contents` | yes |  | kernel |
| Objects & attributes | `exits` | yes |  | kernel |
| Objects & attributes | `create_obj` |  |  | kernel |
| Objects & attributes | `destroy_obj` |  |  | kernel |
| Objects & attributes | `teleport_obj` |  |  | kernel |
| Objects & attributes | `controls` | yes |  | kernel |
| Objects & attributes | `eval_attr` |  |  | kernel |
| Objects & attributes | `call` |  |  | kernel |
| Objects & attributes | `search_world` | yes |  | kernel |
| Tags & zones | `add_tag` |  |  | kernel |
| Tags & zones | `remove_tag` |  |  | kernel |
| Tags & zones | `has_tag` | yes |  | kernel |
| Tags & zones | `tags` | yes |  | kernel |
| Tags & zones | `tag_value` | yes |  | kernel |
| Tags & zones | `tag_values` | yes |  | kernel |
| Tags & zones | `zones_of` | yes |  | kernel |
| Tags & zones | `zone_rooms` | yes |  | kernel |
| Locks & permissions | `set_lock` |  |  | kernel |
| Locks & permissions | `clear_lock` |  |  | kernel |
| Locks & permissions | `test_lock` | yes |  | kernel |
| Locks & permissions | `has_entitlement` | yes |  | kernel |
| Money | `credits` | yes |  | economy |
| Money | `adjust_credits` |  | yes | economy |
| Money | `transfer_credits` |  |  | economy |
| Messaging & prompts | `pemit` |  |  | kernel |
| Messaging & prompts | `oemit` |  |  | kernel |
| Messaging & prompts | `remit` |  |  | kernel |
| Messaging & prompts | `oob` |  |  | kernel |
| Messaging & prompts | `ansi` | yes |  | kernel |
| Messaging & prompts | `escape` | yes |  | kernel |
| Messaging & prompts | `prompt` |  |  | kernel |
| Dice & skill checks | `rand` | yes |  | kernel |
| Dice & skill checks | `dice` | yes |  | kernel |
| Dice & skill checks | `roll` | yes |  | kernel |
| Dice & skill checks | `skill_check` | yes |  | rules |
| Dice & skill checks | `check_roll` | yes |  | rules |
| Dice & skill checks | `contest` | yes |  | rules |
| Dice & skill checks | `band` | yes |  | kernel |
| Dice & skill checks | `highest` | yes |  | kernel |
| Dice & skill checks | `margin_over` | yes |  | kernel |
| Dice & skill checks | `margin_under` | yes |  | kernel |
| Dice & skill checks | `net_successes` | yes |  | kernel |
| Combat & effects | `damage` |  | yes | combat |
| Combat & effects | `heal` |  |  | combat |
| Combat & effects | `apply_effect` |  | yes | effects |
| Combat & effects | `remove_effect` |  | yes | effects |
| Combat & effects | `start_combat` |  |  | combat |
| Combat & effects | `cast` |  |  | abilities |
| NPCs & behaviors | `disposition` | yes |  | social |
| NPCs & behaviors | `adjust_disposition` |  |  | social |
| NPCs & behaviors | `reaction_roll` |  |  | social |
| NPCs & behaviors | `force` |  |  | kernel |
| NPCs & behaviors | `behaviors` |  |  | kernel |
| NPCs & behaviors | `attach_behavior` |  |  | kernel |
| NPCs & behaviors | `detach_behavior` |  |  | kernel |
| Movement & travel | `move_to` |  |  | kernel |
| Movement & travel | `enter_instance` |  |  | instances |
| Movement & travel | `enter_wilderness` |  |  | wilderness |
| Firing your own events | `act` |  |  | kernel |
| Time & scheduling | `now` | yes |  | kernel |
| Time & scheduling | `wait` |  |  | kernel |
| Time & scheduling | `cancel_wait` |  |  | kernel |
| Time & scheduling | `expire` |  |  | kernel |
| Text | `capstr` | yes |  | kernel |
| Text | `lcfirst` | yes |  | kernel |
| Text | `ucfirst` | yes |  | kernel |
| Text | `left` | yes |  | kernel |
| Text | `right` | yes |  | kernel |
| Text | `mid` | yes |  | kernel |
| Text | `strlen` | yes |  | kernel |
| Text | `repeat` | yes |  | kernel |
| Text | `replace` | yes |  | kernel |
| Text | `trim` | yes |  | kernel |
| Text | `words` | yes |  | kernel |
| Text | `extract` | yes |  | kernel |
| Text | `first` | yes |  | kernel |
| Text | `last` | yes |  | kernel |
| Text | `rest` | yes |  | kernel |
| Text | `member` | yes |  | kernel |
| Text | `setdiff` | yes |  | kernel |
| Text | `setinter` | yes |  | kernel |
| Text | `setunion` | yes |  | kernel |
| Math & logic | `ceil` | yes |  | kernel |
| Math & logic | `floor` | yes |  | kernel |
| Math & logic | `clamp` | yes |  | kernel |
| Math & logic | `if_else` | yes |  | kernel |
| Math & logic | `switch` | yes |  | kernel |

Functions this plan adds:

| Step | Function | Read-only | Harm-gated | Owner |
|---|---|---|---|---|
| 3.3 | `skill`, `check` (subject helpers) | yes | | rules |
| 3.5 | `use_ability` | | | abilities |
| 5.2 | `clone_obj`, `set_name`, `set_desc` | | | kernel |
| 8.1 | `pool`, `pool_max`, `has_pool`, `spent` | yes | | kernel |
| 8.1 | `harm_pool` | | yes | kernel |
| 8.1 | `mend_pool`, `spend_pool` | | | kernel |

---

## Appendix B — Where every module goes

Kernel modules that do not move are not listed. Line counts are at the
baseline commit.

| Module today | Lines | Destination | Batch |
|---|---|---|---|
| `systems/gurps.py` | 176 | `games/gurps/system.py` | A |
| `systems/d20.py` | 108 | `games/d20/system.py` | A |
| `systems/merc.py` | 300 | `games/merc/system.py` | A |
| `combat/rulesets/gurps.py`, `d20.py`, `merc.py` | 470, 266, 157 | `games/<name>/ruleset.py` | A |
| `combat/rulesets/__init__.py` | 12 | deleted; registration is `feature.ruleset` | A |
| `core/instances.py` | 354 | `std/instances/instances.py` | B |
| `core/wilderness.py` | 566 | `std/wilderness/wilderness.py` | B |
| `systems/crime.py` | 103 | `std/crime/crime.py` | B |
| `behaviors/npc.py` | 309 | `std/npc/behaviors.py` | B |
| `behaviors/decay.py` | 66 | `std/npc/decay.py` | B |
| `behaviors/spawner.py` | 380 | `std/spawning/spawner.py` | B |
| `behaviors/zone_reset.py` | 110 | `std/spawning/zone_reset.py` | B |
| `behaviors/shop.py` | 87 | `std/economy/shop.py` | B |
| `behaviors/caster.py` | 78 | `std/abilities/caster.py` | B |
| `behaviors/effects.py` | 400 | `std/effects/behaviors.py` | B |
| `core/economy.py` | 63 | `std/economy/credits.py` | C |
| `core/disposition.py` | 129 | `std/social/disposition.py` | C |
| `core/party.py` | 125 | `std/social/party.py` | C |
| `core/describe.py` | 81 | `std/look/describe.py` | C |
| `core/render.py` | 179 | `std/look/render.py` | C |
| `core/pairing.py` | 66 | `std/building/pairing.py` | C |
| `core/checks.py` | 253 | `std/rules/checks.py` | D |
| `systems/base.py` | 348 | `std/rules/system.py` | D |
| `systems/definitions.py` | 127 | `std/rules/definitions.py` | D |
| `systems/abilities.py` | 425 | `std/abilities/abilities.py` | D |
| `systems/spells.py` | 69 | `std/abilities/spells.py` | D |
| `combat/system.py` | 498 | `std/combat/system.py` | E |
| `combat/ruleset.py` | 513 | `std/combat/ruleset.py` | E |
| `combat/encounter.py` | 589 | `std/combat/encounter.py` | E |
| `combat/manager.py` | 298 | `std/combat/manager.py` | E |
| `combat/combatant.py` | 315 | `std/combat/combatant.py` | E |
| `combat/behaviors.py` | 439 | `std/combat/behaviors.py` | E |
| `combat/strategy.py` | 151 | `std/combat/strategy.py` | E |
| `combat/maneuver.py` | 114 | `std/combat/maneuver.py` | E |
| `combat/damage.py` | 117 | `std/combat/damage.py` | E |
| `commands/builtin/combat.py` | 526 | `std/combat/commands.py`; `points`, `improve` to `std/rules/commands.py` | F |
| `commands/builtin/communication.py` | 294 | `std/talk/commands.py` | F |
| `commands/builtin/movement.py` | 116 | `std/movement/commands.py` | F |
| `commands/builtin/look.py` | 274 | `std/look/commands.py` | F |
| `commands/builtin/inventory.py` | 387 | `std/items/inventory.py` | F |
| `commands/builtin/manipulation.py` | 505 | `std/items/commands.py`; `hide`, `search`, `pick` to `std/stealth/commands.py` | F |
| `commands/builtin/utility.py` | 388 | `std/basics/commands.py` | F |
| `commands/builtin/social.py` | 258 | `std/social/commands.py` | F |
| `commands/builtin/economy.py` | 229 | `std/economy/commands.py` | F |
| `commands/builtin/magic.py` | 109 | `std/abilities/commands.py` | F |
| `commands/olc/admin.py`, `area.py`, `create.py`, `debug.py`, `modify.py`, `softcode.py` | 2698 | `std/building/<same name>.py` | F |
| `core/verbs.py` | 401 | split: `std/talk/verbs.py`, `std/items/verbs.py` | G |
| `core/perception.py` (stealth parts) | | `std/stealth/stealth.py` | G |
| `core/action_types.py` (feature members) | | `std/<feature>/actions.py` | G |
| `scripting/lib/<feature>.py` (from task 3.4) | | `std/<feature>/softcode.py` | G |
| `server/game.py` (login, chargen, who, welcome) | about 280 | `std/accounts/` | G |
| `behaviors/scripted.py` | 208 | `scripting/scripted_behavior.py` (kernel) | G |
| `behaviors/ticker.py` | 69 | `scripting/ticker.py` (kernel) | G |
| `server/dispatcher.py`, `persistence/repository.py`, `config/defaults.py` | | deleted in steps 1 and 2 | |

Stays in `realm/core` although the review listed it as a feature:
`language.py` (articles and plurals, used by propagation and search) and
`teardown.py` (used by the destroy op).

---

## Appendix C — The module-global setters

Call sites at the baseline commit, in engine code and in tests. All are
removed by task 7.2.

| Function | Module | Engine | Tests | Replaced by |
|---|---|---|---|---|
| `reset_engine` | `core/propagation.py` | 2 | 41 | a new `World` |
| `get_engine` | `core/propagation.py` | 3 | 24 | `get_world().engine` |
| `set_active_manager` | `persistence/manager.py` | 10 | 49 | `World.store` |
| `get_active_manager` | `persistence/manager.py` | 22 | 2 | `get_world().store` |
| `set_script_engine` | `scripting/engine.py` | 4 | 10 | `World.scripts` |
| `get_script_engine` | `scripting/engine.py` | 11 | 1 | `get_world().scripts` |
| `set_game_system` | `systems/base.py` | 4 | 24 | `World.rules` |
| `get_game_system` | `systems/base.py` | 9 | 0 | `get_world().rules` |
| `set_combat_manager` | `combat/manager.py` | 2 | 36 | `World.services["combat"]` |
| `get_combat_manager` | `combat/manager.py` | 13 | 0 | `get_world().services.get("combat")` |
| `set_check_resolver` | `core/checks.py` | 4 | 56 | `World.services["checks"]` |
| `set_skill_defaults` | `core/checks.py` | 3 | 11 | `World.services["checks"]` |
| `set_check_hook` | `core/objects.py` | 4 | 0 | `find_world().scripts` |
| `set_group_formatter` | `core/render.py` | 0 | 3 | `Feature.group_formatter` |
| `set_show_rolls_default` | `combat/system.py` | 1 | 4 | `setting("SHOW_ROLLS")` |
| `set_world_tick` | `core/behaviors.py` | 1 | 0 | `setting("WORLD_BEAT")` |
| `set_emote_sigil` | `core/verbs.py` | 1 | 9 | `setting(...)` |
| `set_markup_marker` | `core/markup.py` | 1 | 7 | `setting(...)` |
| `set_heredoc_sigils` | `gateway/session.py` | 1 | 5 | `setting(...)` |
| `set_inline_delimiters` | `scripting/inline.py` | 1 | 6 | `setting(...)` |
| `set_keyid_sigil` | `scripting/functions.py` | 1 | 5 | `setting(...)` |
| `set_trigger_sigils` | `scripting/triggers.py` | 1 | 11 | `setting(...)` |
| `set_interpreter_recursion_limit` | `scripting/sandbox.py` | 1 | 5 | `setting(...)` |
| `register_speech_renderer` | `core/propagation.py` | 0 | 11 | `Feature.speech_renderer` |
| `register_name_resolver` | `core/perception.py` | 0 | 18 | `Feature.name_resolver` |
| `register_dest_resolver` | `core/movement.py` | 2 | 1 | `Feature.dest_resolver` |

The exact setting key for each sigil is the `key` given to its `setting(...)`
field in task 2.1.

---

## Appendix D — The Feature API when the plan is done

| Declaration | Added in | Installs into |
|---|---|---|
| `command(name, handler, *, aliases, token, permission, ...)` | 4.1, `token` in 7.3 | dispatcher |
| `behavior(cls)` | 4.1 | `BehaviorRegistry` |
| `function(fn)`, `softfn(fn)` | 4.1 | softcode function registry |
| `observer(fn)` | 4.1 | propagation engine |
| `ruleset(name, cls, *, aliases)` | 4.1 | `RulesetRegistry` |
| `dest_resolver(name, fn)` | 4.1 | movement |
| `reaper(fn)` | 4.1 | server reap loop |
| `queue_kind(kind, handler)` | 4.1 | script engine queue |
| `check_modifier(fn)` | 4.1 | checks service |
| `protocol(name, cls)` | 4.1 | server |
| `setting(key, default, doc)` | 4.1 | `Settings` |
| `on_boot(fn)`, `on_close(fn)` | 4.1 | world lifecycle |
| `script_verb(name, *, aliases, token, sugar)` | 6.1 | script verb registry |
| `event(action_type, *, hook, doc, payload, target_lock, tool_lock, speech)` | 6.2 | event registry |
| `lock_type(name, *, default, doc)` | 6.3 | lock registry |
| `entitlement(name, doc)` | 6.4 | entitlement registry |
| `audience(name)` | 6.5 | message delivery |
| `def_kind(name, tag, parse)` | 6.6 | definition loader |
| `fallback(fn)` | 7.3 | dispatcher, after command lookup |
| `traversal_gate(fn)`, `after_traverse(fn)` | 7.3 | movement |
| `sight_rule(fn)`, `name_resolver(fn)`, `speech_renderer(fn)`, `group_formatter(fn)` | 7.2, 7.4 | perception and rendering |
| `input_interceptor(fn, *, order)`, `login(fn)` | 7.4 | server input path |
| `pool(Pool(...))` | 8.1 | pool defaults |

Every declaration raises `FeatureError` on a name collision and accepts
`replace=True`. Every declaration is undone by `World.close()`.

---

## Decision log

Record here, with the date and the step, every place where the work departed
from this plan, every **Decision** task and its answer, and every BACKLOG
entry closed.

| Date | Step | Decision or deviation | Why |
|---|---|---|---|
| 2026-11-12 | 1.1 | `reap_expired`: a player or `safe` object with a past `expires_at` is not destroyed. `destroy_object` refuses it; the reaper logs a WARNING and clears `expires_at`. | The plan routes the reaper through `destroy_object` but does not say what to do on refusal. Clearing the lease stops the warning repeating every tick. |
| 2026-11-12 | 1.1 | `_reconcile_orphaned_players`: a dangling non-player object that is `safe` is moved to the start room with a WARNING instead of being deleted. | Same gap. Leaving it at `location=None` would be the silent limbo the sweep exists to prevent. |
| 2026-11-12 | 1.1 | `DestroyRefused` carries `# noqa: N818`. | The plan names the class; ruff wants an `Error` suffix. Keeps the finding count at 19. |
| 2026-11-12 | 1.1 | Not fixed: exits *inside* a destroyed room are deleted by `release_contents` without dissolving their pairing, so a neighbouring room's exit can keep a `partner` pointing at a deleted exit. | Outside the 1.1 spec (it dissolves only the destroyed object itself). Candidate for step 5's destroy op. |
| 2026-11-13 | 1.7 | `ScriptedBehavior` does not override `to_dict`. The def name moved to a `_def_name` slot and `behavior_id` reads it, so the inherited `to_dict` already emits `{'behavior_id': <def name>, 'params': <original params>}`. | Same result as the plan with less code. |
| 2026-11-13 | 1.7 | `ScriptedBehavior.__init__(self, def_name, /, **params)`: the name is positional-only. | A database saved before this change has `def_name` inside `params`; a keyword parameter would make those rows raise `TypeError` at load. Positional-only lets the stale key load as an ordinary (ignored) param with no compatibility code. |
| 2026-11-13 | 1.7 | `read_role_defs` also reports a `role_def` whose `entitlements` is not a list (it used to be skipped silently). | Same failure mode as an unknown name: the role grants nothing and the builder was not told. |
| 2026-11-13 | 1.8 | Also converted `tests/test_combat.py::TestD20Ruleset::test_apply_damage_with_resistance` to the dict form. `scale_resistances` logs a WARNING for a non-dict `resistances` value and ignores it. | The plan named only lines 108-118. A stale list would otherwise stop working without a word. |
