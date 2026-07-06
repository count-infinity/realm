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
- `Ruleset.roll_saving_throw/calculate_healing/get_attack_range`
  (+ backlogged roll_dice/get_modifier): no callers; shrink the
  contract implementers must read.
- TagSet `has_prefix/get_value/get_all_values`: zero callers while the
  one zone-scan that needs them hand-rolls it. Use or delete.
- AttributeProxy per-attribute dirty SET (NOT YET DONE): only an
  object-level bool is consumed. Simplify.
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

- **functions.py**: one resolution idiom (`_resolve` everywhere — 12
  older methods hand-roll it), one mutate helper (`_controlled` +
  `_touch`) replacing the ritual copied ~10×; `del_attr` is the one
  mutator missing its save-queue. Move `_resolve` next to `get`.
- **78 dead `if not ctx.player` guards**: the dispatcher guarantees a
  player before any handler runs. Delete guards + unused `has_player`.
- **find-or-complain helper**: `resolve_or_report(ctx, name)` (~32 call
  sites across builtin+OLC, two message idioms).
- **communication.py**: six structurally identical commands → one
  `_emit_room_action` helper, unified with `gate_action`'s veto idiom.
- **Speech-shape drift**: engine `_emit_speech/_emit_pose/_emit_whisper`
  + `_npc_say` hand-mirror cmd_say/pose/whisper Action shapes (3 copies
  each). Shared action builders.
- **Behavior.countdown(obj, key, reset)**: five behaviors hand-roll the
  same db-counter dance with different off-by-one conventions.
- **DispositionBoostBehavior 'applied' state lives in params**: against
  the declared behaviors-are-stateless rule; move to owner.db (the
  `_state_key` machinery exists).
- **locks.py class layers**: Lock's `_compiled` cache is never used by
  evaluate (safe_eval's lru_cache does the work); LockEvaluator's
  `_cache` never read; `check()` builds throwaway Locks. Module
  functions suffice.
- **GURPS skill ladder unification**: `GURPSRuleset.get_skill` flat-10
  fallbacks should fall through to `checks.skill_level()` so combat
  sees attribute-based defaults (untrained DX-13 attacks at DX-4, not
  10). Also `checks.SKILL_DEFAULTS` seed table drifted from
  GurpsSystem's — after Tier 1's engine-floor fix, trim the seed to
  the floor.
- **RulesetRegistry** (or `GameSystem.create_ruleset()`): the hardcoded
  ruleset_map closes the swappable-rules story the registries elsewhere
  open.
- **`GameSystem.death_award(victim)`**: CP formula/party split in
  CombatManager is game policy; one overridable method.
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
