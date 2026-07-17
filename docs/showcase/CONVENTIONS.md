# REALM Showcase Conventions

Rules for implementing items from [checklist.md](checklist.md) (250 showcase
tutorials; per-item feasibility in [capability_audit.md](capability_audit.md)).
Multiple sessions may work on this repo concurrently — the file boundaries below
keep implementers from colliding.

## The philosophy: softcode-first

A showcase tutorial is a **sequence of in-game commands a builder types live**
(`@dig`, `@create`, `@behavior`, `@set obj/on_tick = ...`, `[[...]]` inline
expressions, wards, wizards, masters). REALM's thesis is that games are built
from inside the game — every tutorial proves it. **No Python appears in the
tutorial path.**

If you hit an engine gap (a primitive the audit promised is missing, or a small
addition would be needed): do **not** edit engine source. Note the gap precisely
in your report and in a "Engine gaps" line in the tutorial; the integrator files
BACKLOG entries. Wave-1 items are all classified `[now]`, so gaps should be rare.

## Hard file boundaries

You may **create or edit files ONLY here**:

- `docs/showcase/NNN_<item_slug>.md` — one tutorial per checklist item (zero-padded
  number, e.g. `048_gas_bomb.md`); arc implementers also write `arc_<name>.md`
- `tests/showcase/test_<slug>.py` — your verification tests, one file, yours alone

**Never** edit: `realm/` source, `BACKLOG.md`, `mkdocs.yml`, `docs/` outside
`docs/showcase/`, `examples/`, `checklist.md`/`capability_audit.md`/this file,
other implementers' files, or anything in the reference repos (`~/CoffeeMud`,
`~/evennia`, `~/pennmush`, `~/solar_frontiers`, …). Do not create or edit
`tests/showcase/__init__.py` (it already exists).

## Required reading, in order

1. This file, then your items' rows in [capability_audit.md](capability_audit.md)
   — the audit names the exact primitives per item; follow them.
2. `docs/reference/softcode.md` (auto-generated: every softcode function and
   `ON_<EVENT>` hook), plus the relevant `docs/guides/*` and `docs/tutorial/*`.
3. Harness references for tests: `tests/test_builtin_commands.py`,
   `tests/test_olc.py`, `tests/test_packs.py`, `tests/test_infiltration.py`.

## Load-bearing engine facts (from the audit — verified against source)

- Builtins dispatch **before** `$`-triggers: softcode cannot shadow `say`,
  `whisper`, `who`, etc.
- `wait()` is in-memory (dies on restart); `expire()` persists — use it for
  anything that must survive.
- Global `$`-commands: no Master Room yet — the workaround is a **world-zone
  master** (object in a `zone:world`-tagged room). Say so when you use it.
- `on_check` wards gate actions; admin-owned masters may write other players'
  sheets (owner authority); sandboxed Python `[[...]]` allows loops.
- GMCP is live (telnet option 201 + websocket): `oob()`.
- **Keep `[[...]]` inline blocks cheap and local** — they run per look, per
  viewer, on the look's own call stack, and the sandbox recursion cap is
  currently absolute (filed defect), so deep blocks (remote `get_attr('<name>',
  …)` chains) can fail closed depending on dispatch depth. The robust idiom is
  **push-on-change**: tickers (worker-stack) compute and stamp state onto the
  object; the desc block does one shallow `get_attr(me, …)` read. See
  036_weather_system.md.
- Instances, wilderness, zone-reset, shopkeeper, combat (cover + range bands),
  `ON_HITPRCNT`, prompt wizards, packs, and `@import` plan-apply all exist.

## Tutorial format

Each `NNN_<item_slug>.md`:

```markdown
# NNN. Title

> Checklist item NNN — [now|small|major] — *concept tags from checklist.md*

**What you'll build:** one or two sentences.
**Concepts:** the REALM primitives this teaches.

## How it works       <- which primitives/hooks and why
## Build it           <- the exact command transcript, explained in chunks
## Try it             <- what to type to see it work, expected output
## Going further      <- 2-4 short variation ideas
```

Write for a builder at a live prompt — explain *why* each primitive is used.
The Solar Frontiers showcase (`~/solar_frontiers/world/showcase/`,
`~/solar_frontiers/docs/guides/showcase/`) is a **concept reference only** —
same item numbers, worked mechanics, tutorial voice. Never port its Python;
re-derive each build in idiomatic softcode.

## Verification — required

- `tests/showcase/test_<slug>.py`, pytest, driving a **real in-process world
  through the dispatcher** with the tutorial's exact command lines (raw input
  in → session output out), asserting outcomes. Every command line in "Build
  it" must be exercised. Patterns: see the harness references above.
- Run: `cd /home/evennia/realm && source venv/bin/activate && pytest tests/showcase/test_<slug>.py`
  — all green before you're done. Do NOT run the full suite, start servers, or
  bind ports.

## Report back (agents)

Per item — number, status, files, primitives used; any engine gaps found
(precise: missing function/hook/flag + what it blocks); test command + pass
count. Do not check items off checklist.md — a single integrator does that.
