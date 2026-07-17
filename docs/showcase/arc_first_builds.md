# Arc: First Builds

The "hello world" sequence of the REALM showcase — five small builds
for a builder's first hour at a live prompt. Each tutorial is
deliberately tiny and heavily explained, each one adds exactly one new
idea on top of the last, and **everything is typed in-game**: no
Python files, no restarts. This arc establishes the vocabulary
(`@create`/`@set` → object `$`-commands → event triggers → wards) that
every later tutorial in the showcase reuses without re-explaining.

Work through them in order, standing in any room you may build in
(a fresh `@dig The Workshop` works fine). Every command line in every
tutorial is exercised against a live in-process world by
`tests/showcase/test_first_builds.py` — which reads those lines
*straight out of these markdown files*, so what the tests prove and
what you are told to type cannot drift apart.

## The learning path

**1. [Magic 8-ball](005_magic_8ball.md)** *(checklist 5)* — the
smallest possible interactive object: `@create`, `@desc`, and one
`$shake` command trigger wrapping `say(switch(rand(1, 8), ...))`.
Teaches what a `$`-command *is* — a command that lives on an object,
in scope only for people near it — plus the golden rule that builtins
dispatch before softcode, and the first data-vs-code split (answers in
an attribute, script reading it).

**2. [Slot machine](001_slot_machine.md)** *(checklist 1)* — money.
Scripts can spend their object's credits but never a player's, so the
wager arrives by consent via the built-in `pay` and the machine's
`ON_PAYMENT` hook — introducing the **event namespace** every
`ON_<EVENT>` script gets (`adata('amount')` for the sum paid, plus
`atype`/`target`/`actor`), `transfer_credits()` payouts, a
`rand()`+`switch()` weighted payout table, and the house-edge
arithmetic that makes the machine a currency sink. Also the actor/room
messaging etiquette
(`pemit` you, `oemit` everyone else) and a living `[[...]]`
description that reads the hopper.

**3. [Vending machine](002_vending_machine.md)** *(checklist 2)* —
money again, but now the machine *creates* things: products are
prototype dicts stored in attributes, minted on demand with
`create_obj()` — the spawner vocabulary. Adds wildcard captures
(`$vend *` → `arg0`), a second command on the same object, banked
per-player credit, guard-chain validation with numeric error messages,
and the definitions-vs-state split (one `item_coffee`, one mutable
`stock_coffee`).

**4. [Basic container](014_basic_container.md)** *(checklist 14)* —
the first build that *intercepts* the engine instead of adding to it.
The `container` attribute gets you `put`/`get from`/`open`/`close` for
free; the tutorial adds the missing capacity rule as an **`on_check`
ward** — softcode running in the engine's permission pass, inspecting
the in-flight action (`atype`, `target`, `adata`) and vetoing with
`block(reason)`. Weight is a summed-attribute convention, enforced at
the one choke point every code path shares — the difference between a
rule polite commands follow and a law of physics.

**5. [Lockable door](025_lockable_door.md)** *(checklist 25)* — a
two-sided exit pair that locks and unlocks with a key. The engine
already enforces `closed`/`locked`/`key_id` on each face; the tutorial
solves the classic two-exit problem (a "door" is really two objects)
with the **mirror pattern**: four one-line
`ON_OPEN`/`ON_CLOSE`/`ON_LOCK`/`ON_UNLOCK` hooks that write raw state
onto a `partner` — recursion-proof because raw writes don't propagate.
The pattern reuses everywhere two objects must share state.

## What you'll know afterwards

- `@create` / `@desc` / `@set` / `@tag` / `@dig`, and `@eval` for
  ad-hoc softcode
- `$pattern:code` command triggers, their room-scoped reach, and why
  builtins always win a name collision
- Scripts as one-line sandboxed Python: `;` statements, conditional
  expressions, comprehensions, `me`/`enactor`/`here`, `arg0` captures
- The economy contract: `pay` + `ON_PAYMENT` in, `transfer_credits()`
  out, `adata('amount')` for the sum, and house-edge arithmetic
- Prototype-attributes + `create_obj()` — data that becomes objects
- `[[...]]` living descriptions, `pemit`/`oemit`/`remit` audiences
- `ON_<EVENT>` reactions vs. `on_check` wards — after-the-fact
  narration vs. before-the-fact veto with `block()`; both read the same
  event namespace (`atype`/`target`/`actor`/`adata`), and `block()` is
  what only the ward gets
- Door and container state conventions (`closed`, `locked`, `key_id`,
  `unlocks`, `container`, summed `weight`), and the mirror pattern for
  shared state

## Where next

The gadget items (6–13) iterate on these same object patterns with
timers (`wait`, `script_ticker`) and world state; the container items
(15–24) push the sack's ward vocabulary further; the door items
(26–35) do the same for exits. If you'd rather give your world some
inhabitants first, the NPC arcs pick up `@behavior`, `^listen`
triggers, and `prompt()` wizards from here.
