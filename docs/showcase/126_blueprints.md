# 126. Blueprint Items

> Checklist item 126 ([now]): *ON_USE unlocks, known-list attrs*

**What you'll build:** A single-use data-slate. `study schematic` (or
the plain `use coil schematic`) writes the `vector_coil` pattern into
*your* `known_recipes` list and then wipes itself, and a fabricator
that refuses to run any pattern you have not studied.

**Concepts:** knowledge as a **list attribute on the player**
(`known_recipes`), two triggers sharing one payload through
[`eval_attr()`](../reference/softcode.md#fn-eval_attr) (a `$study`
command plus an [`ON_USE`](../reference/softcode.md#lifecycle-hooks)
hook, the [poison dart trap](052_poison_dart_trap.md)'s shape),
recipe-gated crafting, and the load-bearing part: **who is allowed to
write on a player's sheet**, decided out loud.

## How it works

A blueprint is an object that carries a pattern name as data, and
studying it copies that name onto the reader's own list of known
recipes. A fabricator then reads that same list before it will build
anything. This section answers three questions in order: who is
allowed to sign your sheet, how one lesson serves two commands, and
how the bench enforces the license.

### Who is allowed to write on a player's sheet

[`set_attr()`](../reference/softcode.md#fn-set_attr) mutates only what
the executor *controls*. A blueprint is an object, so when you study
it its script runs with **its owner's** authority, and its owner does
not normally control *you*. The consent you give by invoking an object
grants relocation (the movement functions honor it), but not attribute
writes: `set_attr()` always requires the executor to control its
target. That leaves two honest designs:

1. **Admin-owned master** (chosen here): the slate is built by an
   admin, so it controls every player and may append to their
   `known_recipes`. This is the [ATM](004_atm_terminal.md)'s exact
   precedent, since bank terminals debit depositors for the same
   reason. The write surface stays tiny and auditable: one list
   attribute, append-only, by admin-issued items.
2. **Ledger on the bench**: never write the player at all, but keep
   `known_<player.id>` rows on the fabricator, the
   [vending machine](002_vending_machine.md)'s per-player credit idiom.
   That works with mortal-owned gear, yet the knowledge lives per
   bench and does not travel with the character.

We take (1) because recipe knowledge *belongs on the character*, so it
should follow them to every bench in the world. The script still
checks its own authority honestly: a mortal-built copy of this slate
returns a refusal message rather than a silent no-op, because
`set_attr()` reports False when it is refused.

### One lesson, two commands

The teaching code lives in a single `teach` attribute, and both doors
call it through `eval_attr(me, 'teach')`, which runs the attribute as a
subroutine with `me` still the slate and `enactor` still the reader.
The first door is `$study schematic`, a `$`-command the player types at
the slate. The second is the engine's `ON_USE` hook, fired by the
built-in `use` command. Fix the lesson once and both doors teach it.

The two doors need different framing, though. A `$`-command has no
action behind it, so `target` is unbound and it needs no guard. `ON_USE`
is a reactive hook that fires on **every** object in the room when
anything is used, so the slate's hook must first check
[`target is me`](../reference/softcode.md#guard-on-target) (an identity
check, written `is`, not `==`) before it delegates to `teach`. Without
that guard, using any unrelated object in the room would sign your
sheet and crumble the slate.

### How the bench enforces the license

The fabricator's `$fab *` reads
[`get_attr(enactor, 'known_recipes', [])`](../reference/softcode.md#fn-get_attr)
and checks membership before it looks at materials. An unlicensed
pattern fails with a pointer to the fix (`Study its schematic first.`),
while a licensed one falls through to ordinary
[recipe crafting](122_recipe_crafting.md): consume a tagged component
and mint the coil.

## Build it

**Build as an admin.** That is the design decision above, since a
builder-owned slate refuses to sign sheets. Create the slate, drop it
so a reader can reach it, and store the pattern name as plain data.

```text
@create coil schematic
drop coil schematic
@desc coil schematic = A mil-spec data-slate, its screen crawling with exploded diagrams of a field coil. STUDY it once.
@set coil schematic/recipe = vector_coil
```

The `teach` payload is the whole lesson: read the pattern name and the
reader's current list, then branch three ways. If they already hold the
pattern, say so. If the write is refused (a slate without authority),
report `WRITE REFUSED`. Otherwise the append succeeded, so confirm it,
announce the slate crumbling to the room, and destroy the slate.

```text
@set coil schematic/teach = '''
r = V('recipe')
k = get_attr(enactor, 'known_recipes', [])
if r in k:
    pemit(enactor, 'You already hold the ' + r + ' pattern.')
elif not set_attr(enactor, 'known_recipes', k + [r]):
    # set_attr returns False when the slate lacks authority over the reader
    pemit(enactor, 'The slate flickers: WRITE REFUSED. Only a licensed slate may sign your pattern library.')
else:
    pemit(enactor, 'The schematic unfolds behind your eyes: the ' + r + ' pattern is yours.')
    remit(here, 'The slate chirps once, wipes itself, and crumbles into grey flakes.')
    destroy_obj(me)
'''
```

The `$study` door is one statement, so it stays a one-liner that hands
straight off to the shared payload:

```text
@set coil schematic/cmd_study = $study schematic: eval_attr(me, 'teach')
```

The `ON_USE` door needs the guard, because the hook fires on every
object present whenever anything is used, so it confirms the slate is
the thing being used before teaching:

```text
@set coil schematic/ON_USE = '''
if target is me:  # ON_USE fires on every object in the room, so guard on the target
    eval_attr(me, 'teach')
'''
```

The fabricator checks the license first, then the material, then
builds. An unstudied pattern is refused before materials are even
counted; an empty-handed crafter is told the shortfall; otherwise the
component burns and a coil drops into the room that serves as the tray.

```text
@create coil fabricator
drop coil fabricator
@desc coil fabricator = A sealed lathe-printer. Its status ring idles amber: AWAITING LICENSED PATTERN.
@set coil fabricator/cmd_fab = '''
$fab *:
sel = trim(arg0).lower()
known = get_attr(enactor, 'known_recipes', [])
comps = [o for o in contents(enactor) if has_tag(o, 'component')]
if sel not in known:
    pemit(enactor, 'The fabricator blinks: UNLICENSED PATTERN ' + sel + '. Study its schematic first.')
elif not comps:
    pemit(enactor, 'The ' + sel + ' pattern calls for 1x component; you carry 0.')
else:
    destroy_obj(comps[0])
    create_obj('a humming vector coil', ['thing', 'coil'], here)
    remit(here, 'The fabricator sings through the ' + sel + ' pattern; a vector coil rolls into the tray.')
'''
```

## Try it

As any player, with a `component`-tagged part in hand (the
[parts mill](123_refining_chain.md) makes them):

```text
> fab vector_coil
  The fabricator blinks: UNLICENSED PATTERN vector_coil. Study its schematic first.
> study schematic
  The schematic unfolds behind your eyes: the vector_coil pattern is yours.
  The slate chirps once, wipes itself, and crumbles into grey flakes.
> @examine me
  known_recipes: ['vector_coil']
> fab vector_coil
  The fabricator sings through the vector_coil pattern; a vector coil rolls into the tray.
```

The first `fab` is refused before the machine counts your materials.
`study schematic` writes the pattern onto *you*, so `@examine me` shows
`known_recipes: ['vector_coil']`, and the license now works at every
bench you visit. The second `fab` consumes your component and rolls a
humming vector coil into the tray. Studying a second slate of the same
pattern answers `You already hold the vector_coil pattern.`, and
`use coil schematic` teaches through the same payload as `study`. On a
*builder*-built copy of the slate, `study` answers `WRITE REFUSED`,
which makes the authority rule visible instead of a mystery.

## Going further

- **Skill-gated studying:** require `skill_check(enactor,
  'engineering')` before the write, and a failed study could even burn
  the slate for stakes.
- **Recipe books:** a multi-pattern slate stores `recipes = [...]` and
  teaches them all in one loop, or a librarian NPC teaches through the
  same admin-owned pattern for a fee (`ON_PAYMENT`).
- **The ledger variant:** design (2) above swaps
  `get_attr(enactor, 'known_recipes', [])` for a `known_<enactor.id>`
  attribute on the bench, for when admin-issued slates do not fit your
  fiction.
- **Chemistry pathways:** item [131](131_chemistry_poisons.md) reuses
  this exact pattern for restricted formulas, since knowledge gates are
  how you make dangerous crafting earned.
