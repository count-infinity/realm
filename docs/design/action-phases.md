# Action phases: before / apply / after

Every action in REALM runs as a **trio**: a permission pass that sees the
world *before* the effect, the engine effect itself, and a reaction pass
that sees the world *after*. One sentence carries the whole contract:

> **`on_check` sees the world before, `ON_<EVENT>` sees the world after,
> and the veto is the only thing that stops the middle.**

## The shape

```
propagate(action, apply=<the engine effect>)

  1. permission pass   every leg's on_check: wards/behaviors block(),
                       modify, add_data — PRE-state; never short-circuits,
                       so observers witness blocked attempts
  2. apply(action)     the effect: flip the tag, move the credits,
                       relocate the item — SKIPPED if blocked; may itself
                       refuse via action.block(reason) (an insufficient
                       wallet reads exactly like a ward veto)
  3. reaction pass     messages, trailing actions, behavior reactions —
                       POST-state; ON_<EVENT> softcode fires here (engine
                       observer) and ONLY for actions that applied
```

`action.applied` records whether the effect ran. Pure notifications
(`event:on_fail`, `event:on_receive`) pass no `apply` — the fact already
happened, there is nothing to gate.

## Why a trio and not per-caller ordering

Before this model, each action family picked its own order: `pay` moved
the money *then* propagated (so wards could never veto a payment — the
permission pass ran post-fact into the void), while the `lock`/`open`/
`get` family propagated *then* mutated (so `ON_LOCK` fired with the tag
still unset, observing pre-state from a hook named like an
after-the-fact event). Movement hand-rolled the trio as two actions
because it needed before/after so badly. Three placements, three
different answers to "what state does my hook see", and one silently
disabled capability. The trio replaces all of it with one rule, and the
vocabulary stays put: `on_check` **is** the before hook, `ON_<EVENT>`
**is** the after hook — no `ON_BEFORE_X`/`ON_AFTER_X` proliferation.

Precedents: CoffeeMud's `okMessage`/`executeMsg` is exactly
permission/apply; Evennia's `at_before_*`/`at_after_*` pairs are the
same split with the naming cost this design avoids.

## Consequences worth knowing

- **Payments are vetoable.** A courtroom ward can refuse the bribe
  before a credit moves. `ON_PAYMENT` still sees the moved money, as it
  always did.
- **`ON_LOCK` sees itself locked**, `ON_OPEN` sees itself open, and a
  taken item's `ON_GET` runs with the item already in the taker's
  inventory — which means `loc(me)` inside `ON_GET` is the **taker**,
  not the room. Scripts that announce to the scene use `loc(enactor)`
  (see the [poison dart trap](../showcase/052_poison_dart_trap.md)).
- **Reach includes your carrier.** A carried object can act on the one
  carrying it (a cursed idol biting its taker) — the post-state model
  made this case real, so `_in_reach` covers it.
- **Movement keeps its two-action form** — `event:on_leave` gates and
  announces while the actor still stands in the origin (witnesses of a
  departure should see the departing), relocation happens, then
  `event:on_enter` fires at the destination. Two facts, two locations,
  each internally conforming.

## For builders (the short version)

- Want to **prevent**? `on_check` + `block(reason)` — you see pre-state.
- Want to **react**? `ON_<EVENT>` — you see post-state, and if your hook
  fired, the thing definitely happened.
- Announcing to the room from an item that just moved: `loc(enactor)`.

## See also

- [Action propagation](../architecture/events.md) — chains, messages,
  observers.
- Tests: `tests/test_action_phases.py` pins every guarantee above.
