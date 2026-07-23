# REALM Showcase Conventions

Rules for implementing items from [checklist.md](checklist.md) (250 showcase
tutorials; per-item feasibility in [capability_audit.md](capability_audit.md)).
Multiple sessions may work on this repo concurrently, so the file boundaries
below keep implementers from colliding.

## The philosophy: softcode-first

A showcase tutorial is a **sequence of in-game commands a builder types live**
(`@dig`, `@create`, `@behavior`, `@set obj/on_tick = ...`, `[[...]]` inline
expressions, wards, wizards, masters). REALM's thesis is that games are built
from inside the game, and every tutorial proves it. **No Python appears in the
tutorial path.**

If you hit an engine gap (a primitive the audit promised is missing, or a small
addition would be needed), do **not** edit engine source. Note the gap precisely
in your report and in an "Engine gaps" line in the tutorial, and the integrator
files BACKLOG entries. Wave-1 items are all classified `[now]`, so gaps should
be rare.

## Hard file boundaries

You may **create or edit files ONLY here**:

- `docs/showcase/NNN_<item_slug>.md`, one tutorial per checklist item
  (zero-padded number, for example `048_gas_bomb.md`); arc implementers also
  write `arc_<name>.md`
- `tests/showcase/test_<slug>.py`, your verification tests, one file, yours
  alone

**Never** edit: `realm/` source, `BACKLOG.md`, `mkdocs.yml`, `docs/` outside
`docs/showcase/`, `examples/`, `checklist.md`, `capability_audit.md`, this file,
other implementers' files, or anything in the reference repos (`~/CoffeeMud`,
`~/evennia`, `~/pennmush`, `~/solar_frontiers`, and so on). Do not create or
edit `tests/showcase/__init__.py`, which already exists.

## Required reading, in order

1. This file, then your items' rows in [capability_audit.md](capability_audit.md).
   The audit names the exact primitives per item, so follow them.
2. `docs/reference/softcode.md` (auto-generated: every softcode function and
   `ON_<EVENT>` hook), plus the relevant `docs/guides/*` and `docs/tutorial/*`.
3. Harness references for tests: `tests/test_builtin_commands.py`,
   `tests/test_olc.py`, `tests/test_packs.py`, `tests/test_infiltration.py`.

## Load-bearing engine facts (from the audit, verified against source)

- Builtins dispatch **before** `$`-triggers, so softcode cannot shadow `say`,
  `whisper`, `who`, and the like.
- `wait()` is in-memory and dies on restart, while `expire()` persists, so use
  `expire()` for anything that must survive a reboot.
- Global `$`-commands: there is no Master Room yet, so the workaround is a
  **world-zone master** (an object in a `zone:world`-tagged room). Say so
  whenever you use it.
- `on_check` wards gate actions; admin-owned masters may write other players'
  sheets under owner authority; sandboxed Python `[[...]]` allows loops.
- GMCP is live (telnet option 201 and websocket) through `oob()`.
- **Keep `[[...]]` inline blocks cheap and local.** They run per look, per
  viewer, on the look's own call stack, and the sandbox recursion cap is
  currently absolute (filed defect), so deep blocks (remote `get_attr('<name>',
  ...)` chains) can fail closed depending on dispatch depth. The robust idiom is
  **push-on-change**: tickers on the worker stack compute and stamp state onto
  the object, and the description block does one shallow `get_attr(me, ...)`
  read. See 036_weather_system.md.
- Instances, wilderness, zone-reset, shopkeeper, combat (cover and range bands),
  `ON_HITPRCNT`, prompt wizards, packs, and `@import` plan-apply all exist.

### Guarding an `ON_<EVENT>` hook

An `ON_<EVENT>` hook fires on **every object in the room**, not only on the one
the action targeted, so a hook that reacts to its own business must say so. The
guard is an `if` statement wrapping the whole body:

```text
@set shopkeeper/on_receive = '''
if target is me:
    it = adata('item')
    pemit(enactor, 'Thanks.')
'''
```

Three rules go with it:

- **The guard wraps the whole body.** `if target is me:` is the first line and
  the reaction is indented beneath it. (A one-liner guard,
  `if target is me: it = adata('item'); pemit(...)`, only works when the body is
  a single line of simple statements; a multi-line block sidesteps that limit,
  which is one reason blocks are now the norm.)
- **There is no `return`.** Scripts run at module scope, where a bare `return`
  is invalid. Note that `@set` does **not** currently warn about this, so a
  stray `return` fails only when the hook fires. Wrap the body in the guard
  instead.
- **Write `target is me`, not `target == me`.** It is an identity check.

A global witness (a zone master, a chronicle, a scoreboard) is the deliberate
exception and takes no guard, because it is watching everyone. See
[Guard on `target`](../reference/softcode.md#guard-on-target).

## Tutorial format

Each `NNN_<item_slug>.md`:

```markdown
# NNN. Title

> Checklist item NNN ([now|small|major]): *concept tags from checklist.md*

**What you'll build:** one or two sentences.
**Concepts:** the REALM primitives this teaches.

## How it works       <- the model first, then which primitives and why
## Build it           <- the exact command transcript, explained in chunks
## Try it             <- an annotated transcript of commands and responses
## Going further      <- 2 to 4 short variation ideas
```

**`## Build it` is machine-executed.** The test harness's `build_lines()` reads
every non-blank line from the ```` ```text ```` fenced blocks under the literal
heading `## Build it`, up to the next `##` heading, and runs them through the
dispatcher. So:

- Put **only** commands a builder types in those fenced blocks. No prose, no
  `>` prompts, no expected output.
- Keep the heading exactly `## Build it`.
- Illustrative snippets that are not meant to run belong under a different
  heading, such as `## How it works`.

### Multi-line scripts use `'''` heredoc blocks

Any script attribute with more than a couple of statements, or any control
flow, is written as a multi-line block, not a semicolon-and-ternary one-liner.
End the `@set` line with a trailing `'''`, write the body as ordinary indented
softcode (real `if`/`else`/`for`), and close with a line of just `'''`.
[001 (slot machine)](001_slot_machine.md) is the reference example, and
[World Management](../guides/world-management.md#multi-line-input-heredocs)
documents the input mechanism.

- **Split `## Build it` into narrated steps.** The shell (`@create` / `drop` /
  `@desc`) comes first, then one fenced block per attribute or tight group, each
  preceded by a sentence saying what it does. Never one 40-line block.
- **Comment the gotchas, not every line.** A curated few inline `#` comments may
  point at what a newcomer would miss (the `target` guard, a non-obvious
  argument, a per-player key). Showcase code is dense, so let the prose carry the
  explanation and reserve comments for genuine surprises. Comments persist in the
  stored attribute, so keep them terse and true.
- **No blank lines inside a body.** The extractor drops blank lines, so a blank
  inside a heredoc body will not survive into the stored script.
- **Tests drive the real input path.** Heredocs accumulate in
  `Session.submit_input`, so the build helper feeds each line through
  `sim.submit_line`, not `sim.do`. When you convert the first tutorial in a test
  file, point that file's `build` helper at `submit_line` (see
  `tests/showcase/test_first_builds.py`); it runs one-liners identically, so the
  switch is always safe.

`## Try it` is not parsed, so its blocks should show an annotated session with
`>` prompts and the responses underneath, which lets a reader check each step
as they go rather than reading a paragraph and mapping it back onto commands.
Where output depends on a die roll, pin one representative outcome and say
plainly which lines vary.

## Writing style

Write for a builder at a live prompt, and explain *why* each primitive is used,
not merely what it does.

**Punctuation.** Do not use em dashes or double hyphens as punctuation. Use
commas, colons, semicolons, parentheses, or a second sentence. (ASCII art in
game text, such as a `[ ---- : ---- : ---- ]` reel line, is content and stays
as written.)

**Flow.** Write in complete, connected sentences. Avoid strings of noun
fragments standing in for sentences ("The cabinet." / "The lever." / "Finally,
the float."), and avoid stacking parenthetical asides. Join related ideas with
connectives such as "because", "since", "once", and "which means", so the
reader is carried from one step to the next instead of reassembling the thread.

**Never narrate history.** REALM has never been released, so there is no "old
way". Do not write "this used to", "older builds", "the ledger idiom", or
"before X existed". Describe only what is true now. (The word "ledger" is fine
when it names a real in-game data structure, such as a lottery's ledger of
ticket ids.)

**Plain words.** Avoid jargon a newcomer would have to decode, such as "seam",
"beats" (outside a ticker context), or "the float". Name the thing directly, and
define a domain term on first use if you need it ("its credit balance, which
slot-machine people call the hopper").

**Link every primitive to the reference.** The first mention of a softcode
function or concept links to its anchor in the auto-generated reference:

| What | Anchor |
|---|---|
| any function | `../reference/softcode.md#fn-<name>`, for example `#fn-pemit` |
| the event data namespace | `../reference/softcode.md#event-data-namespace` |
| the `target` guard | `../reference/softcode.md#guard-on-target` |
| the `ON_<EVENT>` hook list | `../reference/softcode.md#lifecycle-hooks` |

For the propagation model itself, link `../architecture/events.md`, and for a
guided tour of the event system link [245_event_bus_tour.md](245_event_bus_tour.md).

### Teaching structure

These follow established findings on how adults learn technical material, and
they matter most in `## How it works`.

1. **Open with the whole before the parts** (an advance organizer). Begin the
   section with a short paragraph describing the finished shape, then say what
   the section will answer. A reader who holds a scaffold absorbs detail far
   better than one accumulating it bottom-up.
2. **Title subsections as questions the builder would ask.** Adults are
   problem-centred and want the reason before the mechanism, so prefer "How the
   machine knows the payment was for it" over "Guarding the hook".
3. **Explain a helper where it is first used, not earlier.** Introducing a
   function far from the code that uses it forces the reader to hold it in
   working memory for nothing. Keep the explanation next to its example.
4. **Name a block's steps before showing it.** Softcode blocks get long, so
   precede a dense multi-line script with a sentence naming its steps in order.
   The reader then parses the block against a structure they already hold. (Write
   multi-statement scripts as `'''` heredoc blocks, not `;` one-liners; see
   "Multi-line scripts" above.)
5. **Close the loop in `## Try it`.** Show the command and its response
   together so the learner gets immediate feedback, and call out the one or two
   results worth confirming deliberately.

The Solar Frontiers showcase (`~/solar_frontiers/world/showcase/`,
`~/solar_frontiers/docs/guides/showcase/`) is a **concept reference only**, with
the same item numbers, worked mechanics, and tutorial voice. Never port its
Python; re-derive each build in idiomatic softcode.

## Verification, required

- `tests/showcase/test_<slug>.py`, pytest, driving a **real in-process world
  through the dispatcher** with the tutorial's exact command lines (raw input
  in, session output out), asserting outcomes. Every command line in "Build it"
  must be exercised. For patterns, see the harness references above.
- Run: `cd /home/evennia/realm && source venv/bin/activate && pytest tests/showcase/test_<slug>.py`
  and get all green before you are done. Do NOT run the full suite, start
  servers, or bind ports.

## Report back (agents)

Per item: number, status, files, primitives used; any engine gaps found
(precise: the missing function, hook, or flag, plus what it blocks); test
command and pass count. Do not check items off checklist.md, since a single
integrator does that.
