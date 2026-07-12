# The Data-Driven Rules Kernel

**Status:** Stages A–D shipped (2026-07). The data-driven rules kernel is
complete: skills/classes are data, resolution composes from primitives,
actions reach across rooms, and content ships as importable packs.

REALM's north star for rules is a **microkernel**: the Python core is a
small set of *abstract mechanics* (the "physics engine"), and the entire
*game* — GURPS, D20, skills, classes, actions, whole rulesets — is data
and softcode composed on top. Privileged users edit the game; the kernel
stays fixed. This is the Godot analogy taken all the way: you don't
rewrite the physics solver, but almost everything you *build* is data.

## The kernel / game boundary

The valuable question is what's genuinely irreducible. It's a short list.

| **Kernel — stays Python (abstract mechanics)** | **Game — data / softcode** |
|---|---|
| Propagation: two-pass check/react traversal, per-looker delivery, veto | **Game system**: dice + resolution rule + advancement + derived stats |
| Targeting vocabulary: self / room / contents / holder / remote / zone | **Actions/verbs**: trigger, targeting, check, effect, messages |
| Expression eval (`safe_eval`) + RNG + dice-expression eval | **Skills** (`skill_def`), **classes** (`class_def`) |
| Persistence, sessions, protocols, permissions, scheduler | **Items, rooms, NPCs, areas, behaviors** |

The kernel staying code is the point, not a limitation: it's what keeps
the data safe (sandboxed formulas, a fixed traversal a bad definition
can't break) and fast. The discipline is keeping the kernel *small and
abstract* so the game surface stays *large*.

## Bindings, not a mega-descriptor

Resolution is **not** a monolithic `resolve(mode, dice, direction, bands,
target, …)` descriptor — that's the late-90s "struct of flags" smell. It
is a handful of small **bound primitives** (fast Python) that softcode
*composes*. REALM already has this layer: the softcode sandbox is a
binding layer (~90 Python functions scripts call). A game system's
resolution rule becomes a one-liner:

```
GURPS      resolve = margin_under(roll("3d6"), effective_skill)
D20        resolve = margin_over(roll("d20") + mod, dc)
Shadowrun  resolve = net_successes(pool, tn)         # pool of d6, count ≥ tn
PbtA       resolve = band(roll("2d6") + stat, 7, 10) # miss / 7-9 / 10+
Blades     resolve = highest(roll("{pool}d6"))       # 6 / 4-5 / 1-3
FATE       resolve = roll("4dF") + skill - difficulty
```

No mode enum, no giant signature; each primitive has its own small,
natural signature. Simple systems are one line; a bespoke system is a
longer expression. Complexity only appears when a game needs it.

### Two tiers of extension (the trust boundary)

| Tier | What | Who | Safety |
|---|---|---|---|
| **Softcode** | sandboxed expressions composing bound primitives | any builder, live in-game | safe — restricted, permission-gated |
| **Bindings** | native Python functions exposed to softcode | operator / pack author, at deploy time | **full power — arbitrary code** |

A binding is the Python↔C escape hatch — register a native function
(via a decorator, loaded from `config.py`) and softcode/OLC can call it
by name. Firm rule: registering a binding is a **deploy-time act by a
trusted operator**, never something a builder types at a prompt (native
Python is unsandboxed). Operators extend the vocabulary; builders
compose it. It's also self-healing on performance: a resolution rule
that's too slow or hairy in softcode simply *becomes a binding* — simple
stays softcode, hot/complex goes native, you never hit a wall.

## Five design decisions (from surveying real rulesets)

Pressure-tested against CoffeeMud (d100, breadth) and AwakeMUD/Shadowrun
(dice pools) source, plus the tabletop field. The findings, baked in:

1. **Resolution returns a *graded outcome*, not a bool.** Shadowrun net
   successes, GURPS margin, PbtA bands, Blades tiers all unify as a
   *degree*. Actions branch on it. (AwakeMUD's `success_test` returns a
   count, never a bool; binary is an ad-hoc `< 1` threshold.)
2. **Dice-pool success-counting is a distinct mode**, not a special case
   of threshold rolls — a bound primitive (`net_successes`), not a schema
   field.
3. **The resolver is entity-agnostic** — formula variables bind *by name*
   from entity data, not `mob.strength`. This is the big one: CoffeeMud's
   MOB-typed resolver forced a whole parallel *siege engine* for ships;
   AwakeMUD's vehicle combat reuses `success_test` with a different stat
   source. Bind by name and one resolver drives characters, ships, cars.
4. **Health is a data-described *track*, not hardcoded HP** — GURPS HP,
   Shadowrun's wound monitor (with TN feedback), a ship's hull/shields,
   Blades stress are all "a track with thresholds + optional feedback."
5. **Effects need four hooks, not just a per-tick formula** — and the
   critical one is `on_event(action) → allow | modify` (resistance,
   armor-reduces-damage, wards, counters). CoffeeMud proves a pure-formula
   effect model can't express these. The others: `recompute` (stat delta),
   `on_tick` (DoT), `on_apply`/`on_expire` (purge/cleanup).
   **✅ The `allow | modify` hook is built:** an object's `on_check`
   softcode runs in the propagation check pass with `block()` / `mod()` /
   `set_adata()` on the in-flight action — data-driven wards, immunity, and
   armor (see [Interception](../guides/interception.md)). It's the softcode
   surface on the *existing* two-pass mechanism (Python behaviors already
   had `on_check` block/modify), and it's decision-only (no side effects in
   the veto pass). `recompute`/`on_tick`/`on_apply` already exist as the
   effect behaviors; only the interception hook was missing.

**Subsystems (races, chases, social conflict) are softcode compositions**
over check + scheduler + propagation, *not* kernel features — confirmed
by both surveys (neither has a "chase" primitive). The one genuine
addition true 3D space combat needs is a small **spatial primitive**
(coordinates / distance / velocity), not a combat engine.

### Coverage

GURPS, D20, Call of Cthulhu (d100), Shadowrun, World of Darkness, PbtA,
Blades, FATE, Savage Worlds, and diceless all express as a bound-primitive
resolution rule + data. Space combat and car races express as data
entities + softcode compositions (with the spatial primitive for true 3D).

## Staged plan

Each stage is independently shippable and keeps the built-ins working
(they ship *as* the default data).

- **Stage A — definitions as data. ✅ SHIPPED.** `skill_def` / `class_def`
  objects; `GurpsSystem`/`D20System` read them, built-ins as the
  merge base / fallback. OLC-editable, `@reload` for cached skills. Proven
  in-game via the [Simulator](../development/testing.md) harness. See
  [Skills & Classes as Data](../guides/data-driven-rules.md).
- **Stage B — system as data (keystone). ✅ SHIPPED.** `realm/core/dice.py`
  holds the genre-neutral primitives (`roll` with pools/explode/keep/Fudge;
  `margin_under`/`margin_over`/`net_successes`/`highest`/`band`), each
  returning a graded `CheckResult`. A `GameSystem` carries an optional
  softcode `resolve_rule` (e.g. `"net_successes(attr('pool'), 4)"`)
  resolved by `checks.resolve_with_rule`, which binds entity data **by
  name** (`skill()`, `attr()`). The built-in `GurpsSystem`/`D20System` own
  their resolvers in the *system* (Python composing the same primitives —
  GURPS crits are policy, so they live in GurpsSystem, not the kernel); a
  Shadowrun-shaped dice pool is a pure `resolve_rule`; and all of them —
  plus a **ship** (`gunnery`/`pool`, no hp/melee) — run through the *same
  entity-agnostic machinery* (proven in `tests/test_rules_kernel.py`). The
  kernel's `default_resolver` is a neutral, policy-free fallback only. The
  primitives are in the softcode namespace, and `@softcode_function`
  (`realm.scripting`)
  registers native bindings — the deploy-time, operator-only escape hatch;
  softcode composes bindings but cannot register them.
- **Stage C — multiroom actions / targeting vocabulary. ✅ SHIPPED.** The
  propagation engine gained a targeting vocabulary — `RemoteStep` (visits
  a *set* of rooms + their occupants; the origin leg is a `RemoteStep` over
  the actor's own room, so a `NO_MAGIC` ward in the caster's room vetoes),
  composed by `remote_chain` — plus a `'remote'` message audience. The softcode `act(target, message,
  targeting='remote'|'zone'|'room')` fires a *propagated* action beyond the
  actor's room: a scry/remote-cast (the target's room) or a zone alarm
  (every room in the zone). Every leg — origin and each destination — gets
  the two-pass, so a ward in the origin *or* any destination can veto, and
  occupants witness/react. Reaching a destination is authority-gated by its
  ``reach`` lock (open by default, like teleport; a room/zone can lock it) —
  the permission gate VISION #4/#5 require, not a hoped-for ward. Proven in
  `tests/test_multiroom.py`.
- **Stage D — packs & à-la-carte. ✅ SHIPPED.** A pack is a directory of
  worldio data files (`realm/packs/<name>/`: `skills.json`, `classes.json`,
  `equipment.json`, a `pack.json` manifest). `realm.packs.import_pack` /
  `import_file`, the `realm pack list|import` CLI, and the in-game `@pack`
  command import a whole pack or one file — the same worldio import that
  loads an area. The built-in **`gurps-scifi`** pack ships the spacegame's
  content (six classes, ship/combat skills, gear) *as data* — proving
  "import the sci-fi pack" and "import one class" are the same operation.
  Generated by `scripts/build_scifi_pack.py`; proven in
  `tests/test_packs.py`.
