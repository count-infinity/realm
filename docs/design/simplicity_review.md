# Simplicity Review (2026-07-05)

Three independent review passes (over-abstraction in core/systems/
permissions; duplication in scripting/commands/behaviors; architecture
coherence) against the north star: *the simplest framework that meets
the needs*. Verdict up front: **the bones are right** — layering is
clean, the house style (one attribute + a few functions) is working,
and the recent kits (economy/party/disposition/verbs) are exemplary.
The debt is (a) three real wiring bugs, (b) ~600 lines of dead
speculative surface, and (c) rituals that never got a helper.

## TIER 1 — real bugs (fixed 2026-07-05, same day)

1. **OLC authority hole**: `@teleport`/`@destroy`/`@link`/`@unlink`
   mutated without `require_control`, while every modify.py command and
   the softcode equivalents are gated — builder commands were LOOSER
   than builder scripts. FIXED: all four now require control.
2. **`set_skill_defaults` dropped engine-required skills**: systems
   replace the whole table, but the engine itself rolls `flee`
   (encounter flee checks) — every live server silently degraded
   untrained flee from DX-2 to IQ-5. FIXED: engine floor
   (`ENGINE_SKILL_DEFAULTS`) that systems merge over but can't drop.
3. **`GameSystem.ruleset_name` was never read**: `GAME_SYSTEM = "d20"`
   with `COMBAT_RULESET` unset gave D20 chargen with GURPS combat.
   FIXED: config `COMBAT_RULESET` defaults to None → falls back to the
   system's ruleset; explicit config still wins.
4. **`create_obj` location ungated**: scripts could create objects in
   any resolvable room. FIXED: executor's own location, or one it
   controls.
5. **roles.py rival authority layer**: dead `can_control`/`can_examine`
   DISAGREED with the canonical `locks.controls` — a trap for whoever
   wires flags later. FIXED: deleted (with their tests); roles.py is
   now just Role/get_role/has_permission.

## TIER 2 — dead weight (EXECUTED 2026-07-05 except where noted)

- `permissions/flags.py`: a full PennMUSH flag lexicon with ZERO
  runtime consumers (17 flags, descriptions, predicates). Delete or
  reduce to what a command enforces; tags already provide the
  mechanism. (Supersedes the old "flag namespace bug" item — the
  namespace can't bite if the module is gone.)
- Legacy `set_combat_system`/`get_combat_system` globals: only consumer
  is the unimportable `examples/spacegame/commands.py` (+ the demo's
  game.py setter). Delete together with the spacegame-commands rewrite.
- Softcode `eq/neq/gt/gte/lt/lte`: MUSH-isms in a PYTHON sandbox where
  `a == b` works. (Keep the list helpers — first/extract/setunion serve
  space-separated attr lists and MUSH muscle memory.)
- `ScriptFunctions.output_callback`: stored, never called.
- `disposition.BANDS` table (disposition_band hardcodes thresholds).
- `LockType.PAGE/MAIL/ZONE`: checked nowhere.
- Dispatcher `@command` decorator + `register_commands` + `min_args`:
  zero uses; two registration idioms, one dead.
- `Ruleset.roll_saving_throw/get_attack_range` (+ backlogged
  roll_dice/get_modifier): no callers, deleted. `calculate_healing`
  KEPT — one real caller (combat/system.py healing path).
- TagSet `has_prefix/get_value/get_all_values`: zero callers while the
  one zone-scan that needs them hand-rolls it. Use or delete.
- AttributeProxy per-attribute dirty SET (DONE 2026-07-05, final
  sweep): reduced to the object-level bool that was actually consumed.
- `resolve_attr`: DELETED (with @parent inheritance tests); @parent
  storage remains harmless. Wire real inheritance reads if ever needed.

## TIER 3 — consolidations (PARTIALLY EXECUTED 2026-07-05)

Done: functions.py one-idiom consolidation (_resolve everywhere,
_controlled + _touch helpers, del_attr save, eq/gt comparisons and
output_callback deleted); 53 unreachable ctx.player guards deleted.
ALSO DONE (2026-07-05, second pass): GURPS skill-ladder unification
(get_skill → checks.skill_level via the get_stat-default trick; seed
table trimmed to the engine floor), canonical speech_action/pose_action
in core/verbs.py (cmd_say, engine emitters, and _npc_say all consume
them — say/pose drift is now impossible), GameSystem.death_award hook
(manager consults it), RulesetRegistry (games register custom rulesets
without editing engine source), Behavior.countdown helper (ticker +
wanderer converted), DispositionBoost applied-flag moved to owner.db.
Still pending below (small, cosmetic tier):

- **find-or-complain helper**: `resolve_or_report(ctx, name)` (~32 call
  sites across builtin+OLC, two message idioms). Still unwritten.
- **communication.py ooc/shout one-off shapes**: ACCEPTED-AS-IS per the
  BACKLOG final sweep.
- **locks.py class layers**: DONE 2026-07-05 final sweep —
  LockEvaluator's `_cache` and the throwaway Locks in `check()` removed
  (`eval_bool` direct). Remnant: Lock's `_compiled` stored by
  `validate()`, unused by evaluate.
- **engine.py `_run_script_command`** is a second hand-rolled command
  parser (13 verbs, own conventions) — the long-term fix is the
  backlogged headless-session dispatcher access; until then it's the
  price of the actuator set. Accepted for now.

## VERDICTS — right-sized, leave alone

- **Ambient singletons (10)**: keep the pattern; a service registry
  would be *different, not simpler* (typed accessors, one composition
  root, exemplary teardown). Subtract two members (legacy combat
  global; dissolve set_skill_defaults into GameSystem consultation
  eventually) → 8.
- **encounter `_resolve_action` if-chain**: keep. Flat early-return
  branches with the ruleset hook in the right place. Switch to a
  dispatch table only when maneuvers become registrable data or the
  vocabulary passes ~12.
- **GameSystem vs Ruleset split**: coherent; fix the loose wires
  (done in Tier 1), don't merge.
- **realm/core at 16 modules**: leave it; a mechanics/ split is a
  nicer `ls` for an import-migration tax. Revisit past ~25 modules.
- **Dependency layering**: clean — core imports only core (economy's
  ambient GameSystem read is the one deliberate upward reach; RULE:
  core may read the ambient GameSystem, never import
  combat/scripting/server).
- **Exemplary, per reviewers**: verbs.py, propagation.py, safe_eval.py,
  economy/party/disposition kits, GameSystem seam (now that it's
  wired), ScriptFunctions.to_dict (verified 1:1), queue kinds
  (verified 1:1), OLC modify.py gates (verified uniform).
- **Modifier-provider list with one entry**: reviewer called it
  speculative; KEPT deliberately — it shipped days ago as the
  documented seam for darkness/encumbrance providers and is 8 lines.
