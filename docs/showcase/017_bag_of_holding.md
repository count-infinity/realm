# 017. Bag of Holding

> Checklist item 17 ([now]): *overriding a softcode weight convention cleanly*

**What you'll build:** A plain leather bag that hangs two pounds on your belt
no matter what you cram inside it, proven on a freight scale and honored by a
weight-limited satchel that refuses everything else the anvil touches.

**Concepts:** how weight aggregates when the engine has no weight kernel (a
recursive fold over an object's
[`contents`](../reference/softcode.md#fn-contents)), and the clean override
point: one data attribute (`carry_weight`) that any container can declare to
replace its computed total. Plus recursion in a single line, a lambda that
calls itself by name.

## How it works

**The convention, restated.** The [basic container](014_basic_container.md)
established it: items carry a `weight` attribute, and anything that cares sums
them. That rule was only one level deep. The moment bags go inside bags you
need its full form, and this build writes it down once:

> the carried weight of a thing is its `carry_weight` attribute if it has one,
> otherwise its own `weight` plus the carried weight of everything inside it.

That first clause is the whole magic item. A container declaring
`carry_weight = 2` tells every scale, satchel ward, and encumbrance script in
the game the same thing: whatever is inside me, I hang two pounds on my holder.
Nothing on the contents is falsified, so taking the anvil back out reads 12 lbs
again, because no script ever wrote to it. The tempting wrong turn is to zero an
item's `weight` on the way in and restore it on the way out, but the first
script that moves that item some other way leaves the totals wrong for good.

**Recursion in one line.** A softcode script runs in a single namespace, like
module scope, so a name the script has bound is visible everywhere below it, a
lambda body included. Writing `w = lambda o: ... w(c) ...` is therefore just
recursion: by the time anything calls `w`, the name `w` already resolves to the
lambda. Because the rule is pure reads
([`get_attr`](../reference/softcode.md#fn-get_attr),
[`has_attr`](../reference/softcode.md#fn-has_attr), and `contents`), the same
fold works unchanged in a `$`-command and in an `on_check` ward: the ward runs
in the engine's [permission pass](../design/action-phases.md), which reads the
world freely and can veto but never writes to it, and the fold only ever reads.

## Build it

The two scripts here, the scale's `weigh` command and the satchel's ward, are
`'''` multi-line blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs));
everything else is plain data.

First a freight scale, so the numbers are visible before anything enforces them.
Give it a face and drop it where anyone can read it:

```text
@create cargo scale
drop cargo scale
@desc cargo scale = A freight scale with a brass needle the size of a sword blade.
```

`$weigh <thing>` runs the fold and reports it with
[`pemit`](../reference/softcode.md#fn-pemit). The lambda `w` is the rule from
"How it works" in one line: `carry_weight` if the thing declares one, otherwise
its own `weight` plus the folded weight of its contents.
[`get`](../reference/softcode.md#fn-get) turns the typed name into an object,
after [`trim`](../reference/softcode.md#fn-trim) cleans the wildcard capture:

```text
@set cargo scale/cmd_weigh = '''
$weigh *:
w = lambda o: get_attr(o, 'carry_weight') if has_attr(o, 'carry_weight') else get_attr(o, 'weight', 0) + sum(w(c) for c in contents(o))  # carry_weight override wins; else own weight plus folded contents
it = get(trim(arg0))
if it:
    pemit(enactor, f'The needle settles at {w(it)} lbs.')
else:
    pemit(enactor, 'Nothing by that name to weigh.')
'''
```

Now the enforcer: a porter's satchel with a 10 lb limit, warded like the canvas
sack in [basic container](014_basic_container.md) except that its ward weighs
aggregates, not raw attributes. The `container` tag switches on the stock
`put`/`get` verbs, and `weight_limit` is plain data the ward will read:

```text
@create porter's satchel
@tag porter's satchel = container
drop porter's satchel
@set porter's satchel/weight_limit = 10
```

The ward filters to `put` actions aimed at this satchel with
[`target is me`](../reference/softcode.md#guard-on-target), weighs both the
satchel's current load and the incoming item with the same fold, reads its
ceiling with [`V`](../reference/softcode.md#fn-v) (shorthand for
`get_attr(me, 'weight_limit')`), and
[`block`](../reference/softcode.md#event-data-namespace)s the put when the sum
would break it. [`name(me)`](../reference/softcode.md#fn-name) keeps the refusal
honest on a renamed satchel:

```text
@set porter's satchel/on_check = '''
if atype == 'item:on_put' and target is me:  # only puts aimed at THIS satchel; is, not ==
    w = lambda o: get_attr(o, 'carry_weight') if has_attr(o, 'carry_weight') else get_attr(o, 'weight', 0) + sum(w(c) for c in contents(o))
    limit = V('weight_limit', 10)
    load = w(me)  # the satchel has no weight of its own, so this is pure contents load
    adding = w(adata('item'))
    if load + adding > limit:
        block(f'At {adding} lbs that would overload the {name(me)} ({load} of {limit} lbs used).')
'''
```

The test mass and an honest container for contrast: the anvil carries a plain
12 lb `weight`, and the duffel is a container with no override, so it weighs
exactly what it holds.

```text
@create iron anvil
@set iron anvil/weight = 12
@create canvas duffel
@tag canvas duffel = container
```

Finally the bag itself, whose entire enchantment is the one `carry_weight`
attribute. Its living description still counts the real cargo with
`contents(me)` on every look, so nothing about the contents is hidden except
their weight:

```text
@create bag of holding
@tag bag of holding = container
@set bag of holding/carry_weight = 2
@desc bag of holding = Plain oiled leather, far too light in the hand. [[n = len(contents(me)); result = 'It holds ' + str(n) + ' item' + ('' if n == 1 else 's') + ' and hangs like an empty purse regardless.']]
```

## Try it

First the honest duffel, aggregation with no override:

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
put bag of holding in porter's satchel   -> You put a bag of holding in the porter's satchel.
weigh porter's satchel         -> The needle settles at 2 lbs.
```

Same anvil, same satchel, same ward: the only thing that changed is which fold
clause the bag triggers. The description still counts the cargo honestly, so the
secret is in the weighing, not the holding.

## Going further

- **A computed shell.** Here `carry_weight` is a flat number, but the general
  form is an [`eval_attr`](../reference/softcode.md#fn-eval_attr) function
  attribute (say, half the contents' total, for a mundane compression sack).
  Mind the boundary: `eval_attr` is not bound on the check pass, so a ward can
  only honor a plain data override. Keep `carry_weight` a number if satchels
  must respect it, and let the scale, which runs with the full namespace, do
  the computing.
- **Keep an inner limit.** Weightless on the outside does not mean bottomless
  within, so bolt on the [basic container](014_basic_container.md) count and
  weight ward with a generous `weight_limit` and the bag still cannot swallow a
  warehouse.
- **Encumbrance.** The same fold over `contents(enactor)` becomes a carry-limit
  ward on a player, one `w(...)` call away.
- **The bag-in-a-bag rule.** A ward on the bag that calls
  `block('The fabric of space complains.')` on any incoming item that itself
  declares `carry_weight` keeps players from nesting one bag of holding inside
  another, which many settings forbid for good reason.
