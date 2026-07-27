# 124. Salvage & Disassembly

> Checklist item 124 ([now]): *reverse recipes, component tables by tag*

**What you'll build:** A breaker bench that takes things *apart*.
`salvage med-scanner` looks up what a gadget is made of by its **tag**,
rolls your salvage skill, destroys the item, and spills its component table
onto the bench. A good roll recovers all of it; a bad roll recovers only a
mangled fraction.

**Concepts:** reverse recipes keyed by item tags (one `parts_<tag>` table per
kind of thing, since the item itself carries no manifest); component tables as
data (`[[name, count, tags], ...]` rows a balance pass can `@set`); a skill
roll that grades *recovery* rather than success or failure; and the skill
itself added as data (a `skill_def` object plus `@reload`, the
[dart trap](052_poison_dart_trap.md)'s trick).

## How it works

The finished bench holds one component table per kind of item and reads nothing
off the item itself. When you `salvage` something, the bench finds the table
that matches one of the item's tags, rolls your salvage skill to grade how much
survives, destroys the item, and mints its components on the floor. This
section answers three questions: where the disassembly table lives and why, how
the bench finds the right one, and what the roll actually decides.

### Where does the disassembly table live?

The table lives on the bench, keyed by tag. A `gadget`-tagged item, from any
builder, breaks down according to the bench's `parts_gadget` attribute, and the
item never lists its own guts. The bench is the authority on disassembly, the
same way the [shopkeeper](063_shopkeeper.md) is the authority on price. That
means one `@set` re-balances every gadget ever made, and a bench in the
scrapyard can pay out differently than the licensed one in town.

### How does the bench find the right table?

The lookup runs [`tags`](../reference/softcode.md#fn-tags)`(item)` against the
bench's `parts_*` attributes. The script walks the target's tags asking
[`has_attr`](../reference/softcode.md#fn-has_attr)`(me, 'parts_' + tag)`, and
the first of the item's tags that this bench has a table for wins. An item with
no tabled tag gets a clean refusal (`nothing recoverable`), not a die roll. Note
what this composes with: [122](122_recipe_crafting.md)'s failed crafts leave
`scrap`-tagged lumps, so a `parts_scrap` table here turns botched work back into
feedstock.

### What does the roll decide?

The roll grades recovery.
[`skill_check`](../reference/softcode.md#fn-skill_check)`(enactor, 'salvage')`
returns a plain pass or fail, and salvage is a skill we define as data: a
`skill_def` object whose `stat` is `intelligence` and whose `penalty` is -2, so
an untrained salvager defaults to intelligence minus 2. Because the check runs
through the engine's real check pipeline, its defaults and any condition
modifiers (fear, darkness, a meal buff) all apply. Success recovers the full
table; failure recovers only its first row, so the sturdy bits survive a clumsy
teardown while the delicate ones do not. Either way the item is gone, because
pulling things apart is not reversible, which is what makes the roll worth
sweating.

## Build it

The salvage skill is data, not code. Create a `skill_def` object, tag it, give
it a governing attribute and an untrained penalty, then `@reload` so the check
tables pick it up (the [dart trap](052_poison_dart_trap.md) adds a skill the
same way):

```text
@create salvage
@tag salvage = skill_def
@set salvage/stat = intelligence
@set salvage/penalty = -2
@reload
```

Now the bench and its component tables. Each `parts_<tag>` attribute is a list
of `[name, count, tags]` rows: what the row mints, how many copies, and the tags
each copy is born with. A `gadget` breaks into wire and a microcell, while the
`scrap` table pays ore, which is what turns [122](122_recipe_crafting.md)'s
botched-craft lumps back into feedstock:

```text
@create breaker bench
drop breaker bench
@desc breaker bench = A waist-high teardown bench: magnetic bit rack, spudgers, a parts tray scarred by ten thousand screws.
@set breaker bench/parts_gadget = [["a coil of copper wire", 2, ["thing", "wire"]], ["an intact microcell", 1, ["thing", "cell"]]]
@set breaker bench/parts_scrap = [["a chunk of balthite ore", 1, ["thing", "ore"]]]
```

The `salvage` verb is a `$`-command, so it fires only on the bench and only for
the player who typed it, which means it needs no `target` guard. Read its steps
in order: match the named item in the salvager's hands, find the first tag this
bench tables, roll the skill, then destroy the item and mint whatever the roll
let you keep. It reads the item's tags with
[`tags`](../reference/softcode.md#fn-tags), destroys with
[`destroy_obj`](../reference/softcode.md#fn-destroy_obj) (the bench owns the
item, so it may), and mints each component with
[`create_obj`](../reference/softcode.md#fn-create_obj):

```text
@set breaker bench/cmd_salvage = '''
$salvage *:
q = trim(arg0).lower()
held = [o for o in contents(enactor) if q in name(o).lower()]
tgt = held[0] if held else None
tabs = [t for t in tags(tgt) if has_attr(me, 'parts_' + t)] if tgt else []
if not tgt:
    pemit(enactor, 'You carry nothing called ' + q + '.')
elif not tabs:
    pemit(enactor, 'The scanner shrugs: nothing recoverable in ' + name(tgt) + '.')
else:
    ok = skill_check(enactor, 'salvage')      # graded recovery, not a gate on the verb
    table = V('parts_' + tabs[0], [])         # first tabled tag wins
    keep = table if ok else table[:1]         # a botch keeps only the sturdy first row
    label = name(tgt)                         # read the name before destroying the item
    destroy_obj(tgt)
    for row in keep:
        for i in range(row[1]):
            create_obj(row[0], row[2], here)
    summary = ', '.join(str(row[1]) + 'x ' + row[0] for row in keep)
    tail = '' if ok else ' (clumsy teardown -- the delicate parts are mangled)'
    remit(here, name(enactor) + ' strips ' + label + ' down to: ' + summary + '.' + tail)
'''
```

And a gadget to tear down: a busted med-scanner, tagged `gadget` so the bench's
`parts_gadget` table claims it:

```text
@create busted med-scanner
@tag busted med-scanner = gadget
drop busted med-scanner
```

## Try it

Pick the scanner up and break it down:

```text
> get busted med-scanner
> salvage med-scanner
... strips busted med-scanner down to: 2x a coil of copper wire, 1x an intact microcell.
```

On a made roll the room hears the full line above and the parts land at your
feet, tagged `wire` and `cell`, ready to be recipe ingredients. On a missed roll
only the wire survives, and the message says why:

```text
> salvage med-scanner
... strips busted med-scanner down to: 2x a coil of copper wire. (clumsy teardown -- the delicate parts are mangled)
```

Either way the scanner is gone. The guards never gamble: an absent item is
refused before any dice, and salvaging something untabled (pick up one of the
copper wires you just recovered and try it) is refused too:

```text
> salvage teapot
You carry nothing called teapot.
> get coil of copper wire
> salvage copper wire
The scanner shrugs: nothing recoverable in a coil of copper wire.
```

## Going further

- **Close the loop:** the `parts_scrap` table already pays ore for
  [122](122_recipe_crafting.md)'s botched-craft scrap, so mine, craft, fail,
  salvage, smelt, and try again. Economies are loops, not lines.
- **Margin-graded recovery:** swap `skill_check` for
  [`check_roll`](../reference/softcode.md#fn-check_roll)`(enactor, 'salvage')`
  and keep `1 + r.margin // 2` rows, which points the
  [gathering node](121_gathering_nodes.md)'s yield arithmetic at teardown and
  folds in condition modifiers the raw roll would miss.
- **Tag priority:** give special items a rare `mil_spec` tag with its own richer
  table. Because [`tags`](../reference/softcode.md#fn-tags) returns an object's
  tags sorted alphabetically, the first tabled tag wins by name order, not by
  the order you added them, so to force a rare table ahead of `gadget` have the
  script check a preferred-tag list before falling back to the sorted scan.
- **Destructive analysis:** on a critical margin, also add the item's recipe to
  the salvager's `known_recipes` list (see [126](126_blueprints.md)), so
  reverse-engineering becomes gameplay.
```
