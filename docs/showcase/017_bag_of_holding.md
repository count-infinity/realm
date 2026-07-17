# 017. Bag of Holding

> Checklist item 17 — [now] — *overriding a softcode weight convention cleanly*

**What you'll build:** A plain leather bag that hangs two pounds on
your belt no matter what you cram inside it — proven on a freight
scale, and honored by a weight-limited satchel that refuses everything
else the anvil touches.

**Concepts:** how weight *aggregates* when the engine has no weight
kernel — a recursive fold over `contents()` — and the clean override
point: one data attribute (`carry_weight`) that any container can
declare to replace its aggregate. Plus the one-liner trick for
recursion in softcode: a lambda that takes itself as its first
argument.

## How it works

**The convention, restated.** The [basic container](014_basic_container.md)
established it: items carry a `weight` attribute, and *anything that
cares sums them*. That was one level deep. The moment bags go inside
bags you need the full rule, and this build writes it down once:

> the carried weight of a thing is its `carry_weight` attribute if it
> has one; otherwise its own `weight` plus the carried weight of
> everything inside it.

That first clause is the whole magic item. A container declaring
`carry_weight = 2` tells every scale, satchel ward, and encumbrance
script in the game: *whatever is inside me, I hang two pounds on my
holder.* No weights are falsified on the contents — take the anvil
back out and it's 12 lbs again, because nothing ever wrote to it. The
wrong way is zeroing `weight` on entry and restoring it on exit; the
first script that moves an item out some other way leaves the books
corrupted forever.

**Recursion on one line.** Softcode attributes are one-liners, and a
top-level name can't see itself from inside a lambda — so the fold
passes itself along: `w = lambda w, o: ...w(w, c)...` and every call
site says `w(w, thing)`. Ugly for a heartbeat, then it reads fine.
Because the rule is pure reads (`get_attr`, `has_attr`, `contents`),
the *same line* works in a `$`-command and in an `on_check` ward — the
decision pass allows reads only, and this needs nothing else.

## Build it

A freight scale, so the numbers are visible before anything enforces
them. `$weigh <thing>` runs the fold and reports:

```text
@create cargo scale
drop cargo scale
@desc cargo scale = A freight scale with a brass needle the size of a sword blade.
@set cargo scale/cmd_weigh = $weigh *: w = lambda w, o: get_attr(o, 'carry_weight') if has_attr(o, 'carry_weight') else get_attr(o, 'weight', 0) + sum([w(w, c) for c in contents(o)]); it = get(trim(arg0)); pemit(enactor, f'The needle settles at {w(w, it)} lbs.') if it else pemit(enactor, 'Nothing by that name to weigh.')
```

The enforcer: a porter's satchel with a 10 lb limit, warded exactly
like the canvas sack in [014](014_basic_container.md) — except its
ward weighs *aggregates*, not raw attributes. Note `load = w(w, me)`:
the cheapest way to weigh your own contents is to weigh yourself (the
satchel has no `weight` of its own, so the fold returns pure load):

```text
@create porter's satchel
@set porter's satchel/container = true
drop porter's satchel
@set porter's satchel/weight_limit = 10
@set porter's satchel/on_check = mine = atype == 'item:on_put' and target is me; w = lambda w, o: get_attr(o, 'carry_weight') if has_attr(o, 'carry_weight') else get_attr(o, 'weight', 0) + sum([w(w, c) for c in contents(o)]); adding = w(w, adata('item')) if mine else 0; load = w(w, me) if mine else 0; limit = V('weight_limit', 10); block(f'At {adding} lbs that would overload the {name(me)} ({load} of {limit} lbs used).') if mine and load + adding > limit else None
```

The test mass, an honest container for contrast, and the bag itself —
whose entire enchantment is one attribute:

```text
@create iron anvil
@set iron anvil/weight = 12
@create canvas duffel
@set canvas duffel/container = true
@create bag of holding
@set bag of holding/container = true
@set bag of holding/carry_weight = 2
@desc bag of holding = Plain oiled leather, far too light in the hand. [[n = len(contents(me)); result = 'It holds ' + str(n) + ' item' + ('' if n == 1 else 's') + ' and hangs like an empty purse regardless.']]
```

## Try it

First the honest duffel — aggregation with no override:

```text
weigh iron anvil               -> The needle settles at 12 lbs.
put iron anvil in canvas duffel
weigh canvas duffel            -> The needle settles at 12 lbs.
put canvas duffel in porter's satchel
                               -> At 12 lbs that would overload the porter's satchel (0 of 10 lbs used).
```

Now launder the same anvil through the enchantment:

```text
get iron anvil from canvas duffel
put iron anvil in bag of holding
weigh bag of holding           -> The needle settles at 2 lbs.
look bag of holding            -> It holds 1 item and hangs like an empty purse regardless.
put bag of holding in porter's satchel   -> accepted
weigh porter's satchel         -> The needle settles at 2 lbs.
```

Same anvil, same satchel, same ward — the only thing that changed is
which fold clause the bag triggers. The description still counts the
cargo honestly; the secret is in the weighing, not the holding.

## Going further

- **A computed shell:** `carry_weight` is a flat number here, but the
  general form is an `eval_attr` function attribute (e.g. half the
  contents' total, for a mundane compression sack). Note the boundary:
  `eval_attr` is not available on the check pass, so wards can only
  honor *data* overrides — keep `carry_weight` a number if satchels
  must respect it.
- **Keep an inner limit.** Weightless outside doesn't mean infinite
  inside — bolt on 014's count/weight ward with a big `weight_limit`
  so the bag can't swallow a warehouse.
- **Encumbrance:** the same fold over `contents(enactor)` is a
  carry-limit ward on a *player* — one `w(w, ...)` call away.
- **The classic disaster:** a ward on the bag that
  `block('The fabric of space complains.')`s any incoming item with
  `carry_weight` — put a bag of holding in a bag of holding and find
  out why.
