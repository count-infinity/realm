# REALM — Vision & Architectural Invariants

This is the **durable yardstick**: the principles every implementation is
measured against. It is deliberately timeless — no dates, no status, no
"shipped." For the living capability tracker see
`docs/design/engine_vision.md`; for the rules layer see
`docs/design/rules-kernel.md`. When those disagree with this file, **this
file wins**.

## Thesis

REALM is a **game engine, not a game** — the Godot of MU\*s. As Godot
hides the complexity of physics, rendering, and scene management while
leaving the game to GDScript and data, REALM hides the complexity of a
MU\* — propagation, persistence, perception, scheduling, movement,
permissions — while leaving the *game* to data and softcode. A specific
game (a GURPS MU\*, a D20 MU\*, a sci-fi one-shot) is a **composition on
the engine**, not a fork of it.

The architecture is a **microkernel**: a small set of abstract Python
mechanics (the kernel), and everything with game meaning built on top as
data and softcode (the game). The kernel is the physics engine you don't
rewrite; the game is what you build.

## The kernel / game boundary

The kernel is the *smallest* set of irreducible mechanisms. Everything
else is game.

**Kernel (Python — mechanism):** action propagation (two-pass
check/react, per-looker delivery, veto); the targeting vocabulary (self /
room / contents / holder / remote / zone); expression evaluation
(sandboxed); RNG and dice-expression evaluation; the resolution
primitive; persistence, identity, sessions, protocols; permissions
(`controls`); the scheduler/heartbeat.

**Game (data / softcode — policy):** game systems (dice + resolution rule
+ advancement + derived stats); skills, classes; actions/verbs (trigger,
targeting, check, effect, messages); items, rooms, NPCs, areas;
behaviors/AI; effects.

The kernel staying code is the *point*: a fixed traversal a bad definition
can't break, sandboxed formulas, one fast path. The discipline is keeping
the kernel small and abstract so the game surface stays large.

## Invariants (the testable yardstick)

1. **Engine, not game (mechanism vs policy).** No kernel code encodes a
   specific game's rules, content, or genre. A hardcoded dict of game
   content in the kernel is a defect, not a convenience.
2. **Minimal kernel.** New Python in the core is *guilty until proven
   irreducible*. If it can be data or softcode, it must be.
3. **Game-meaning is data/softcode.** Skills, classes, actions, rulesets,
   effects — anything with game meaning — is data or script, not Python.
4. **Everything reachable from softcode, with permissions.** Every
   mechanism has a softcode/OLC surface. A feature without its softcode
   surface is half-shipped.
5. **Two-tier trust.** Sandboxed softcode = any builder, live, safe.
   Native bindings = operators/pack-authors, deploy-time, full power.
   Unsandboxed code registration must never reach an in-game prompt.
6. **Compose primitives; don't enumerate configs.** Prefer small
   composable bound primitives over monolithic declarative descriptors
   (no struct-of-flags / Win32 signatures). Simple cases are one-liners;
   complexity appears only when a game needs it.
7. **Entity-agnostic mechanics.** Kernel mechanics bind variables *by
   name* over entity data. They must not assume a character shape (HP,
   melee, humanoid). A ship, a car, and a door run the same mechanics as a
   person — or the abstraction has failed.
8. **Graded, not binary.** Outcomes carry degree/margin/tier; the kernel
   does not collapse to a bool prematurely.
9. **Subsystems are compositions.** Chases, races, crafting, social
   conflict are built from kernel primitives in softcode — not added as
   kernel features. A new kernel subsystem is a defect unless it is a
   genuinely new *primitive* (e.g. spatial coordinates).
10. **One source of truth; small and greppable.** No registry or
    indirection where a direct reference works. No two places that can
    disagree. Fail loudly, never silently fall back. Shared cores, never
    duplicated logic.
11. **Representation to the edge.** Cross-cutting representation (color,
    encoding, per-viewer rendering) travels as data through the pipeline
    and renders once at the protocol boundary. The core stays
    representation-blind.

## Anti-patterns (the smells to hunt)

- **Kernel bloat** — game-meaning creeping into Python "just this once."
- **Character-shape assumptions** — `hp`/`melee`/humanoid baked into a
  mechanic, silently blocking vehicles, ships, objects (the "parallel
  siege engine" tax).
- **Mega-descriptor** — one function/struct taking a flag-bag of modes and
  options instead of composable primitives.
- **Special-case-that-should-be-data** — a hardcoded branch for content
  the data model should carry.
- **Unsandboxed extension creep** — moving the "run arbitrary code" line
  toward untrusted users.
- **Two sources of truth / silent fallback** — config that can desync from
  code; a lookup that quietly returns a default on a typo.
- **Duplicated logic** — two implementations of one behavior that will
  drift.
- **Premature subsystem** — a whole feature added to the kernel that
  should have been a softcode composition.

## How this is used

Every substantial change to the core, the rules layer, or the softcode
surface is judged against these invariants. Alignment is not a matter of
opinion or precedent: "the author prefers it," "we already merged it," and
"it's more convenient" are not defenses. A design that violates an
invariant is wrong even if everyone likes it — and the fix is the
alternative that serves the invariant.
