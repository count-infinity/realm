# The REALM Showcase

250 tutorial-sized builds — slot machines, gas bombs, auction houses, guard
posts, player-scriptable gadgets — each one a **pure softcode tutorial**: a
sequence of commands a builder types at a live prompt, verified end-to-end by
tests that drive those exact lines through the dispatcher.

The showcase serves three purposes:

1. **Teaching** — every tutorial explains *why* each primitive is used, building
   a shared vocabulary (triggers → wards → wizards → behaviors → zone masters).
2. **Proof** — it demonstrates REALM's thesis that whole game systems are built
   from inside the game. Per the [capability audit](capability_audit.md), 223 of
   250 items need no engine changes at all.
3. **Feature-driver** — engine gaps discovered while building are filed to
   `BACKLOG.md`, so the showcase pulls the engine forward.

**Progress: see the [checklist](checklist.md).**

## Start here: the five arcs

| Arc | Items | What it teaches |
|---|---|---|
| [First Builds](arc_first_builds.md) | 5, 1, 2, 14, 25 | The hello-world path: triggers, payments, prototypes, wards, paired doors |
| [The Heist](arc_heist.md) | 27, 16, 49, 54, 48, 160 | A playable break-in: concealment, state machines, traps, surveillance, AoE, stealth |
| [Living NPCs](arc_living_npcs.md) | 60, 64, 67, 68, 71 | Behaviors, listen patterns, dialogue wizards, schedules, zone masters |
| [Working Economy](arc_economy.md) | 86, 63, 87, 89, 92 | Currency, vendors, ledgers, escrow, market simulation |
| [Softcode for Builders](arc_softcode.md) | 243, 240, 241, 242, 250 | REALM's native extension model, from one verb to safe player-authored content |

## For implementers

- [Checklist](checklist.md) — all 250 items with feasibility marks
- [Capability audit](capability_audit.md) — per-item primitives and the ranked engine-gap list
- [Conventions](CONVENTIONS.md) — file boundaries, tutorial format, verification rules

Individual tutorials are numbered `NNN_<name>.md` in this directory and linked
from their arc pages and the checklist. Verification tests live in
`tests/showcase/`.

*A parallel implementation of the same checklist exists in the Solar Frontiers
Evennia game (Python typeclasses) as a concept reference; the REALM showcase is
re-derived in softcode, never ported.*
