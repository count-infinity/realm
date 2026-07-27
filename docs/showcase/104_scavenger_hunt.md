# 104. Scavenger Hunt

> Checklist item 104 ([now]): *ON_GET/ON_ARRIVE detection, registry attrs*

**What you'll build:** a hunt board with a staff-set list of finds. Players
scour the world for tagged items, carry them back, `claim` their card, and climb
a leaderboard, and the first full sets are announced as champions.

**Concepts:** staff truth through tags (only builders can `@tag`, so finds
cannot be forged), a registry attribute as the hunt definition, a `$claim` verb
that verifies
*carried* items, a leaderboard dict, and a champions list that records finish
order.

## How it works

The finished board is a single object carrying three attributes: `finds` (the
official shopping list), `leaderboard` (a name-to-best-score dict), and
`champions` (the finish order). Two `$`-commands do all the work, `claim` and
`hunters`, and every write lands on that one object. This section answers three
questions: what counts as a real find, how a claim scores you, and why the hunt
runs through a verb rather than tripping automatically.

### What makes a find real, and not a fake

A find is a name on the list AND a tag on the item. The board's `finds`
attribute names the trophies, and each genuine trophy carries the `hunt` tag.
`claim` intersects the two: of the things you are carrying that bear the tag,
how many are on the list? The name alone proves nothing, because two objects can
share a name, so the tag is the truth signal.
`@tag` is a builder command that also requires control of the object, so a
mortal cannot mint a `hunt` item, and a look-alike a player picks up counts for
nothing until staff have blessed it.
Inside the verb the test is [`has_tag`](../reference/softcode.md#fn-has_tag)`(o,
'hunt')`, run over [`contents`](../reference/softcode.md#fn-contents)`(enactor)`,
the caller's own inventory.

### How a claim scores you

Progress is a high-water mark. The `leaderboard` dict maps each player's
[`name`](../reference/softcode.md#fn-name) to their best claim so far, and it
only ever rises, so dropping a trophy after claiming leaves your stamp standing.
The verb reads the current best with `lb.get(name(enactor), 0)` and rewrites the
entry with [`set_attr`](../reference/softcode.md#fn-set_attr) only when this
claim beats it. A full set appends you to `champions` once, in finish order,
with a room-wide [`remit`](../reference/softcode.md#fn-remit), because finish
order is the prize structure.

### Why a verb, and not automatic detection

An [`ON_GET`](../reference/softcode.md#lifecycle-hooks) hook on each trophy could
tick progress the instant it is lifted (see Going further), but a claim verb
earns its place three ways: it makes the hunt end where it began, at the board;
it lets players claim partial sets and watch the count climb; and it keeps every
write on one object you can `@examine`. Nothing here reacts to another
object's event, so nothing here needs a
[`target` guard](../reference/softcode.md#guard-on-target): a `$`-command fires
on the board only when a player types it, so it always knows the deed is its own.
The [job board](094_job_board.md) is the contrasting case, where verification
rides an `ON_RECEIVE` hook and must screen on `target`.

## Build it

First the board and the official list. The description carries an inline block
that counts how many hunters have registered so far, and `finds` is a plain JSON
list that `@set` parses into a real list:

```text
@create the Hunt Board
drop the Hunt Board
@desc the Hunt Board = A corkboard headed THE GREAT HUNT, three photographs pinned beneath. [[lb = V('leaderboard', {}); result = str(len(lb)) + ' hunters on the board.']]
@set the Hunt Board/finds = ["a shard of driftglass", "a brass gear", "a violet feather"]
```

Then the trophies. Each is created, stamped with the `hunt` tag, and dropped.
Here they land at the board, but in a live game you would scatter them across
three zones. The tag is what the verb trusts, so a trophy without it is just a
prop:

```text
@create a shard of driftglass
@tag a shard of driftglass = hunt
drop a shard of driftglass
@create a brass gear
@tag a brass gear = hunt
drop a brass gear
@create a violet feather
@tag a violet feather = hunt
drop a violet feather
```

The claim verb is the heart of the build. It reads the list, gathers the tagged
trophies in your inventory, counts how many are on the list, raises your
leaderboard entry only if this beats your best, stamps your card, and on a full
set enrolls you as a champion. The two `if` blocks are the whole point: the
first keeps the score a high-water mark, the second admits a champion exactly
once:

```text
@set the Hunt Board/cmd_claim = '''
$claim:
want = V('finds', [])
carried = [name(o) for o in contents(enactor) if has_tag(o, 'hunt')]  # only tagged trophies count; the name alone is not proof
got = [nm for nm in want if nm in carried]
lb = V('leaderboard', {})
if len(got) > lb.get(name(enactor), 0):  # high-water mark: your best only ever rises
    lb[name(enactor)] = len(got)
    set_attr(me, 'leaderboard', lb)
pemit(enactor, f'The board stamps your card: {len(got)} of {len(want)} finds.')
champs = V('champions', [])
if len(got) == len(want) and name(enactor) not in champs:  # enroll a champion once, in finish order
    set_attr(me, 'champions', champs + [name(enactor)])
    remit(here, name(enactor) + ' has found everything on the hunt!')
'''
```

Finally the leaderboard reader. `hunters` prints the standings sorted by score,
tagging anyone who has finished with their champion number, and says so plainly
when nobody has scored yet:

```text
@set the Hunt Board/cmd_hunters = '''
$hunters:
lb = V('leaderboard', {})
ch = V('champions', [])
pemit(enactor, 'THE GREAT HUNT -- standings:')
if not lb:
    pemit(enactor, '  (nobody yet)')
for nm, k in sorted(lb.items(), key=lambda kv: -kv[1]):
    badge = f' [CHAMPION #{ch.index(nm) + 1}]' if nm in ch else ''
    pemit(enactor, f'  {nm} -- {k} finds' + badge)
'''
```

## Try it

Pick up two of the three trophies and claim a partial card, then read the board:

```text
get a shard of driftglass
get a brass gear
claim                     -> "The board stamps your card: 2 of 3 finds."
hunters                   -> "Kess -- 2 finds"
get a violet feather
claim                     -> "3 of 3" and, room-wide:
                             "Kess has found everything on the hunt!"
hunters                   -> "Kess -- 3 finds [CHAMPION #1]"
```

Now drop a trophy and claim again. The count you would score is lower, so the
high-water mark holds and the board still reads three finds:

```text
drop a violet feather
claim                     -> "2 of 3 finds." but your standing stays 3
hunters                   -> "Kess -- 3 finds [CHAMPION #1]"
```

And the forgery test. A look-alike without the tag counts for nothing, so
someone handed a bare, untagged "a brass gear" claims zero:

```text
claim                     -> "The board stamps your card: 0 of 3 finds."
```

## Going further

- **Auto-detection:** put [`ON_GET`](../reference/softcode.md#lifecycle-hooks) on
  each trophy so the board learns the moment a find is lifted:
  `if target is me: set_attr(get('the Hunt Board'), 'seen_' + enactor.id, 1)`.
  The `if target is me` guard is not optional here, because a lifecycle hook
  fires on every object in the room (see
  [`target` guard](../reference/softcode.md#guard-on-target)), and a trophy is
  the [`target`](../reference/softcode.md#event-data-namespace) only when it is
  the one being lifted. Drop the guard and picking up any object marks every
  trophy found. `ON_ARRIVE` on a trophy tells you when it is carried into the
  trophy hall, and the claim verb then becomes pure ceremony.
- **Turn-ins:** have `$claim` take the trophies with
  [`move_to`](../reference/softcode.md#fn-move_to)`(o, me)` and pay a bounty per
  new find, so the board becomes a collection quest with the
  [shopkeeper](063_shopkeeper.md)'s economics.
- **Namespaced hunts:** tag trophies `hunt:spring` and check
  [`tag_value`](../reference/softcode.md#fn-tag_value)`(o, 'hunt')` against the
  board's own hunt id, so many seasonal hunts run with zero crosstalk.
- **Timed seasons:** stamp `opened = now()` and have `$claim` refuse after
  `opened + 86400`, so the leaderboard freezes when the bell rings. See
  [`now`](../reference/softcode.md#fn-now).
</content>
</invoke>
