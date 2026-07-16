# 021. Ammo Pouch

> Checklist item 21 — [now] — *tag-filtered on_check ward*

**What you'll build:** A belt pouch that physically cannot hold
anything but ammunition. Charge cells slot in with a satisfying count;
a dried fig is refused with a reason, and stays in your hand.

**Concepts:** tags as a cheap type system for items, and the
`on_check` ward as a *typed container's* enforcement point — the
[basic container](014_basic_container.md) ward again, filtering on
`has_tag` instead of arithmetic. This is the smallest possible typed
container; every holster, quiver, scroll case, and specimen jar is
this build with a different tag.

## How it works

**The type is a tag.** `@tag <thing> = ammo` is the entire type
declaration. No registry, no subclassing: anything so tagged is
ammunition to every gadget that asks `has_tag(item, 'ammo')`, and a
quartermaster can mint new calibers all day without touching the
pouch. (Namespaced tags — `ammo:cell`, `ammo:bolt` — buy per-caliber
pouches later via `tag_value`; keep the plain tag until a weapon
actually cares.)

**The gate is a ward.** As 014 established, `put` arrives at the check
pass as `atype == 'item:on_put'` with the pouch as `target` and the
item in `adata('item')` — and the ward's `block(reason)` makes the
refusal a law of physics, not a politeness: the same veto meets a
scripted stow or a spawner, because everything that files an
`item:on_put` funnels through the same pass. One line of guard, one
`has_tag` question, and the message says *why* — vague refusals are
how typed containers frustrate players.

**The reaction is a hook.** `ON_PUT` fires as the action is being
gated, before the item lands (014's timing fact), so the friendly
round-count is `contents + 1`.

## Build it

The pouch, its ward, and its counter:

```text
@create ammo pouch
@set ammo pouch/container = true
drop ammo pouch
@desc ammo pouch = Stiff leather, the loops and slots inside sized exactly for charge cells.
@set ammo pouch/on_check = mine = atype == 'item:on_put' and target is me; item = adata('item'); block('The loops inside the ' + name(me) + ' fit ammunition and nothing else - the ' + name(item) + ' stays out.') if mine and not has_tag(item, 'ammo') else None
@set ammo pouch/on_put = pemit(enactor, 'Slotted. The ' + name(me) + ' now carries ' + str(len(contents(me)) + 1) + ' rounds.')
```

Two rounds and one piece of trail lunch:

```text
@create charge cell
@tag charge cell = ammo
@create spare charge cell
@tag spare charge cell = ammo
@create dried fig
```

## Try it

```text
put charge cell in ammo pouch        -> Slotted. The ammo pouch now carries 1 rounds.
put spare charge cell in ammo pouch  -> Slotted. The ammo pouch now carries 2 rounds.
put dried fig in ammo pouch
   -> The loops inside the ammo pouch fit ammunition and nothing else - the dried fig stays out.
```

The fig never moves — a blocked action never happens — and `look ammo
pouch` shows exactly two cells. `get charge cell from ammo pouch`
works as ever; the ward gates only what goes *in*.

## Going further

- **Fix the grammar while you're in there:** `'1 rounds'` earns a
  `('round' if len(contents(me)) + 1 == 1 else 'rounds')` — the same
  pluralization trick 014's description uses.
- **Capacity too:** stack 014's count ward alongside — wards compose;
  each guarded `block()` is its own rule. Thirty rounds to a pouch.
- **Per-caliber:** tag rounds `ammo:cell` / `ammo:bolt` and match
  `tag_value(item, 'ammo')` against the pouch's `caliber` attribute —
  one attribute turns a generic pouch into a typed magazine.
- **A `$load` command:** `$load *: ` that finds the named round in
  `contents(me)` and moves it to a wielded weapon's `chamber` — the
  pouch becomes the reload interface, and the ward means it can trust
  everything inside it is really ammunition.
