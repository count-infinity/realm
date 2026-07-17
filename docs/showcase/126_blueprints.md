# 126. Blueprint Items

> Checklist item 126 — [now] — *ON_USE unlocks, known-list attrs*

**What you'll build:** A single-use data-slate: `study schematic` (or
plain `use coil schematic`) writes the `vector_coil` pattern into
*your* `known_recipes` list and wipes itself — and a fabricator that
refuses to run any pattern you haven't studied.

**Concepts:** knowledge as a **list attribute on the player**
(`known_recipes`), two triggers sharing one payload via `eval_attr()`
(`$study` + `ON_USE`, the [dart trap](052_poison_dart_trap.md)'s
shape), recipe-gated crafting, and — the load-bearing part — **who is
allowed to write on a player's sheet**, decided out loud.

## How it works

**The authority question first.** `set_attr()` mutates only what the
executor *controls*. A blueprint is an object; when you study it, its
script runs with **its owner's** authority, and its owner does not
normally control *you*. The engine offers no enactor-consent path for
attribute writes (consent exists for movement — `move_to` will move a
willing enactor — but not for `set_attr`; a "self-service" blueprint
that signs its reader's own sheet is not currently writable). That
leaves two honest designs:

1. **Admin-owned master** (chosen here): the slate is built by an
   admin, so it controls every player and may append to their
   `known_recipes`. This is the [ATM](004_atm_terminal.md)'s exact
   precedent — bank terminals debit depositors for the same reason.
   The write surface stays tiny and auditable: one list attribute,
   append-only, by admin-issued items.
2. **Ledger on the bench**: never write the player at all — keep
   `known_<player.id>` rows on the fabricator, the
   [vending machine](002_vending_machine.md)'s credit idiom. Works
   with mortal-owned gear, but the knowledge is per-bench, not
   portable with the character.

We take (1) because recipe knowledge *belongs on the character* — it
should follow them to every bench in the world. The script still
checks its own authority honestly: a mortal-built copy of this slate
gets a refusal message, not a silent no-op.

**Two doors, one payload.** The teaching code lives in a `teach`
attribute; `$study schematic` and the engine's `ON_USE` hook (fired
by the built-in `use` command) are both one-line `eval_attr(me,
'teach')` callers. Fix the lesson once, both doors teach it.

**The gate at the bench.** The fabricator's `$fab *` checks `sel in
known_recipes` before it looks at materials — an unlicensed pattern
fails with a pointer to the fix (`Study its schematic first.`), a
licensed one falls through to ordinary
[recipe crafting](122_recipe_crafting.md).

## Build it

**As an admin** (that's the design decision above — a builder-owned
slate will refuse to sign sheets), the schematic:

```text
@create coil schematic
drop coil schematic
@desc coil schematic = A mil-spec data-slate, screen crawling with exploded diagrams of a field coil. STUDY it -- once.
@set coil schematic/recipe = vector_coil
@set coil schematic/teach = r = V('recipe'); k = get_attr(enactor, 'known_recipes', []); pemit(enactor, 'You already hold the ' + r + ' pattern.') if r in k else (pemit(enactor, 'The slate flickers: WRITE REFUSED. Only a licensed slate may sign your pattern library.') if not set_attr(enactor, 'known_recipes', k + [r]) else (pemit(enactor, 'The schematic unfolds behind your eyes: the ' + r + ' pattern is yours.'), remit(here, 'The slate chirps once, wipes itself, and crumbles into grey flakes.'), destroy_obj(me)))
@set coil schematic/cmd_study = $study schematic: eval_attr(me, 'teach')
@set coil schematic/ON_USE = eval_attr(me, 'teach')
```

The pattern-locked fabricator:

```text
@create coil fabricator
drop coil fabricator
@desc coil fabricator = A sealed lathe-printer. Its status ring idles amber: AWAITING LICENSED PATTERN.
@set coil fabricator/cmd_fab = $fab *: sel = trim(arg0).lower(); known = get_attr(enactor, 'known_recipes', []); comps = [o for o in contents(enactor) if has_tag(o, 'component')]; pemit(enactor, 'The fabricator blinks: UNLICENSED PATTERN ' + sel + '. Study its schematic first.') if sel not in known else (pemit(enactor, 'The ' + sel + ' pattern calls for 1x component; you carry 0.') if not comps else (destroy_obj(comps[0]), create_obj('a humming vector coil', ['thing', 'coil'], here), remit(here, 'The fabricator sings through the ' + sel + ' pattern; a vector coil rolls into the tray.')))
```

## Try it

As any player, with a `component`-tagged part in hand (the
[parts mill](123_refining_chain.md) makes them):

```text
fab vector_coil
study schematic
fab vector_coil
```

The first `fab` is refused — `UNLICENSED PATTERN vector_coil. Study
its schematic first.` — the machine won't even count your materials.
`study schematic` answers `The schematic unfolds behind your eyes:
the vector_coil pattern is yours.`, the room watches the slate crumble,
and the knowledge is now an attribute on *you* (`@examine me` shows
`known_recipes: ['vector_coil']`) — it works at every licensed bench
you'll ever visit. The second `fab` consumes your component and rolls
a humming vector coil into the tray. Studying a second slate of the
same pattern would answer `You already hold the vector_coil pattern.`
And on a *builder*-built copy of the slate, `study` answers `WRITE
REFUSED` — the authority rule made visible instead of a mystery.

## Going further

- **Skill-gated studying:** require `skill_check(enactor,
  'engineering')` before the write — failed studies could even burn
  the slate for stakes.
- **Recipe books:** a multi-pattern slate: `recipes = [...]` and
  teach them all in one comprehension; or a librarian NPC who teaches
  via the same admin-owned pattern for a fee (`ON_PAYMENT`).
- **The ledger variant:** design (2) above — swap
  `get_attr(enactor, 'known_recipes', [])` for a
  `known_<enactor.id>` attr on the bench when admin-issued slates
  don't fit your fiction.
- **Chemistry pathways:** item [131](131_chemistry_poisons.md) reuses
  this exact pattern for restricted formulas — knowledge gates are how
  you make dangerous crafting *earned*.
