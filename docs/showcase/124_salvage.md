# 124. Salvage & Disassembly

> Checklist item 124 — [now] — *reverse recipes, component tables by tag*

**What you'll build:** A breaker bench that takes things *apart*:
`salvage med-scanner` looks up what a gadget is made of by its **tag**,
rolls your salvage skill, destroys the item, and spills its component
table onto the bench — all of it on a good roll, a mangled fraction on
a bad one.

**Concepts:** **reverse recipes keyed by item tags** (one
`parts_<tag>` table per kind of thing — the item itself carries no
manifest), **component tables as data** (`[[name, count, tags], ...]`
rows a balance pass can `@set`), a skill roll that grades *recovery*
rather than success/failure, and the skill itself added as data
(`skill_def` + `@reload`, the [dart trap](052_poison_dart_trap.md)'s
trick).

## How it works

**The table lives on the bench, keyed by tag.** A `gadget`-tagged
item — any gadget, from any builder — breaks down according to the
bench's `parts_gadget` attribute. The item never lists its own guts;
the bench is the authority on disassembly, the same way the
[shopkeeper](063_shopkeeper.md) is the authority on price. That means
one `@set` re-balances every gadget ever made, and a bench in the
scrapyard can pay out differently than the licensed one in town.

**Lookup is `tags(item)` against `parts_*`.** The script walks the
target's tags asking `has_attr(me, 'parts_' + tag)` — the first tag
with a table wins. An item with no tabled tag gets a clean refusal
(`nothing recoverable`), not a die roll. Note what this composes with:
[122's](122_recipe_crafting.md) failed crafts leave `scrap`-tagged
lumps, so a `parts_scrap` table here turns botched work back into
feedstock.

**The roll grades recovery.** `skill_check(enactor, 'salvage')` — a
skill we define as data (`skill_def`: IQ-based, untrained default
IQ-2) so the engine's checks, defaults, and condition modifiers all
apply. Success recovers the full table; failure recovers only its
first row (the sturdy bits survive a clumsy teardown; the delicate
ones don't). Either way the item is gone — pulling things apart is
not reversible, which is what makes the roll worth sweating.

## Build it

The skill, as data — then the bench and its tables:

```text
@create salvage
@tag salvage = skill_def
@set salvage/stat = intelligence
@set salvage/penalty = -2
@reload
@create breaker bench
drop breaker bench
@desc breaker bench = A waist-high teardown bench: magnetic bit rack, spudgers, a parts tray scarred by ten thousand screws.
@set breaker bench/parts_gadget = [["a coil of copper wire", 2, ["thing", "wire"]], ["an intact microcell", 1, ["thing", "cell"]]]
@set breaker bench/parts_scrap = [["a chunk of balthite ore", 1, ["thing", "ore"]]]
```

The verb — find the named item in your hands, find its table, roll,
and commit the teardown:

```text
@set breaker bench/cmd_salvage = $salvage *: q = trim(arg0).lower(); tgt = ([o for o in contents(enactor) if q in name(o).lower()] + [None])[0]; tabs = [t for t in tags(tgt) if has_attr(me, 'parts_' + t)] if tgt else []; pemit(enactor, 'You carry nothing called ' + q + '.') if not tgt else None; pemit(enactor, 'The scanner shrugs: nothing recoverable in ' + name(tgt) + '.') if tgt and not tabs else None; ok = skill_check(enactor, 'salvage') if tabs else False; tab = get_attr(me, 'parts_' + tabs[0], []) if tabs else []; keep = tab if ok else tab[:1]; (destroy_obj(tgt), [create_obj(row[0], row[2], here) for row in keep for i in range(row[1])], remit(here, name(enactor) + ' strips ' + name(tgt) + ' down to: ' + ', '.join(str(row[1]) + 'x ' + row[0] for row in keep) + '.' + ('' if ok else ' (clumsy teardown -- the delicate parts are mangled)'))) if tabs else None
```

Something to break:

```text
@create busted med-scanner
@tag busted med-scanner = gadget
drop busted med-scanner
```

## Try it

```text
get busted med-scanner
salvage med-scanner
```

On a made roll the room hears `... strips busted med-scanner down to:
2x a coil of copper wire, 1x an intact microcell.` and the parts land
at your feet, tagged `wire` and `cell` — ready to be recipe
ingredients. On a missed roll only the wire survives, and the message
says why: `(clumsy teardown -- the delicate parts are mangled)`.
Either way the scanner is gone. The guards never gamble:
`salvage teapot` answers `You carry nothing called teapot.`, and
salvaging something untabled (pick up and try one of the copper wires
you just recovered) gets `The scanner shrugs: nothing recoverable in
a coil of copper wire.`

## Going further

- **Close the loop:** the `parts_scrap` table already pays ore for
  [122's](122_recipe_crafting.md) botched-craft scrap — mine, craft,
  fail, salvage, smelt, try again. Economies are loops, not lines.
- **Margin-graded recovery:** swap `skill_check` for
  `margin_under(roll('3d6'), ...)` and keep `1 + margin // 2` rows —
  the [gathering node](121_gathering_nodes.md)'s yield arithmetic
  pointed at teardown.
- **Tag priority:** a rare `mil_spec` tag with its own richer table,
  set *before* `gadget` on special items — first-table-wins makes tag
  order a rarity system.
- **Destructive analysis:** on a critical margin, also teach the
  salvager the item's recipe (`known_recipes` — see
  [126](126_blueprints.md)): reverse-engineering as gameplay.
