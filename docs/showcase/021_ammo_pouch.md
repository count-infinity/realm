# 021. Ammo Pouch

> Checklist item 21 ([now]): *tag-filtered on_check ward*

**What you'll build:** A belt pouch that physically cannot hold anything but
ammunition. Charge cells slot in with a satisfying count, a dried fig is
refused with a reason, and the fig stays in your hand.

**Concepts:** tags as a cheap type system for items, and the `on_check` ward
as a typed container's enforcement point. It is the
[basic container](014_basic_container.md) ward again, filtering on
[`has_tag`](../reference/softcode.md#fn-has_tag) instead of arithmetic. This
is the smallest possible typed container: every holster, quiver, scroll case,
and specimen jar is this build with a different tag.

## How it works

The finished pouch is one tag, one ward, and one reaction. The `container`
tag switches on the stock storage verbs, the ward vetoes any `put` that is not
ammunition, and the reaction reports the running round-count. This section
answers where an item's "type" lives, how the ward says no to the engine
itself, and why the counter can trust a plain count.

**The type is a tag.** `@tag <thing> = ammo` is the entire type declaration.
There is no registry and no subclassing: anything so tagged is ammunition to
every gadget that asks `has_tag(item, 'ammo')`, and a quartermaster can mint
new calibers all day without touching the pouch. (Namespaced tags such as
`ammo:cell` and `ammo:bolt` buy per-caliber pouches later via
[`tag_value`](../reference/softcode.md#fn-tag_value); keep the plain tag until
a weapon actually cares.)

**The gate is a ward.** As [014](014_basic_container.md) established, a `put`
arrives at the check pass as `atype == 'item:on_put'` with the pouch as
`target` and the item in
[`adata`](../reference/softcode.md#event-data-namespace)`('item')`. The ward's
[`block(reason)`](../reference/softcode.md#event-data-namespace) makes the
refusal a law of physics rather than a politeness, because the same veto meets
a scripted stow or a spawner: everything that files an `item:on_put` funnels
through the same permission pass. One line of guard and one `has_tag` question
are enough, and the message says why, since vague refusals are how typed
containers frustrate players.

**The reaction is a hook.**
[`ON_PUT`](../reference/softcode.md#lifecycle-hooks) fires after the item
lands, so by the [action-phases trio](../design/action-phases.md) a reaction
sees post-state, and the friendly round-count is simply
[`contents`](../reference/softcode.md#fn-contents)`(me)` measured with `len()`.
It opens with `if target is me:` because the hook fires on every object in the
room (see [the guard on `target`](../reference/softcode.md#guard-on-target)).

## Build it

The two scripts are `'''` multi-line blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs));
everything else is one plain command each.

**The pouch.** Create it, switch on the stock storage verbs with the
`container` tag, drop it so it is here to test, and give it a face:

```text
@create ammo pouch
@tag ammo pouch = container
drop ammo pouch
@desc ammo pouch = Stiff leather, the loops and slots inside sized exactly for charge cells.
```

**The ward.** Its steps in order: filter to "someone is putting something into
*me*", read the incoming item with
[`adata`](../reference/softcode.md#event-data-namespace), then block the put
unless the item is tagged `ammo`.
[`name(me)`](../reference/softcode.md#fn-name) keeps the refusal honest on a
renamed pouch:

```text
@set ammo pouch/on_check = '''
if atype == 'item:on_put' and target is me:  # the ward hears every action the pouch is part of, so filter to puts aimed at it
    item = adata('item')
    if not has_tag(item, 'ammo'):
        block(f'The loops inside the {name(me)} fit ammunition and nothing else - the {name(item)} stays out.')
'''
```

That first line earns its length. The ward fires for every action the pouch
takes part in (picking the pouch up arrives as `item:on_get`), so without the
`atype` filter a loaded pouch would refuse to be carried, and without
`target is me` it would answer for puts aimed elsewhere. Write `is`, not `==`,
because it is an identity check.

**The running count.** An `ON_PUT` reaction tells the putter where they stand
through [`pemit`](../reference/softcode.md#fn-pemit). It needs the same guard,
and because a reaction sees post-state the round it reports is already inside,
so `contents(me)` counts it with no adjustment:

```text
@set ammo pouch/on_put = '''
if target is me:  # ON_PUT fires on every object in the room, so guard it
    pemit(enactor, f'Slotted. The {name(me)} now carries {len(contents(me))} rounds.')
'''
```

**Two rounds and one piece of trail lunch.** The cells carry the `ammo` tag;
the fig deliberately does not, so it is what the ward turns away:

```text
@create charge cell
@tag charge cell = ammo
@create spare charge cell
@tag spare charge cell = ammo
@create dried fig
```

## Try it

`@create` leaves the props in your inventory, so put them straight in. The
count line arrives from the `ON_PUT` hook, and the "You put" line from the
command itself:

```text
> put charge cell in ammo pouch
Slotted. The ammo pouch now carries 1 rounds.
You put a charge cell in the ammo pouch.

> put spare charge cell in ammo pouch
Slotted. The ammo pouch now carries 2 rounds.
You put a spare charge cell in the ammo pouch.

> put dried fig in ammo pouch
The loops inside the ammo pouch fit ammunition and nothing else - the dried fig stays out.

> get charge cell from ammo pouch
You pick up a charge cell.
```

The fig never moves, because a blocked action never happens, so the pouch
still holds exactly two cells and the fig stays in your hand. Getting a round
back out is not gated at all, since the ward inspects only what goes in.

## Going further

- **Fix the grammar while you are in there:** `'1 rounds'` earns a
  `('round' if len(contents(me)) == 1 else 'rounds')`, the same pluralization
  trick [014](014_basic_container.md)'s description uses.
- **Capacity too:** stack [014](014_basic_container.md)'s count ward
  alongside, because wards compose: each guarded `block()` is its own rule.
  Thirty rounds to a pouch.
- **Per-caliber:** tag rounds `ammo:cell` or `ammo:bolt` and match
  `tag_value(item, 'ammo')` against the pouch's `caliber` attribute, so one
  attribute turns a generic pouch into a typed magazine.
- **A `$load` command:** a `$load *:` that finds the named round in
  `contents(me)` and moves it to a wielded weapon's `chamber`, so the pouch
  becomes the reload interface, and the ward means it can trust that
  everything inside really is ammunition.
