# 209. Lever combination

> Checklist item 209 ([now]): *shared pattern state on a controller object, softcode pull verbs, cross-object unsealing*

**What you'll build:** A vault hall with four wall levers. Pull them in the
right order and the sealed vault gate grinds open; pull them in the wrong
order and a buzzer throws the whole attempt away so you start over. This
opens the Puzzles & Mechanisms chapter (items 209 to 218 of the
[checklist](checklist.md)), and the shape under it, *many input objects
feeding one shared state machine that unseals a third object*, recurs in
every puzzle that follows.

**Concepts:** the [combination safe](016_combination_safe.md)'s dial state
machine, but with the digits arriving from several objects instead of one;
a controller that owns the progress attribute so the puzzle is shared and
persistent; the [airlock](032_airlock.md)'s cross-object wiring, where one
object writes another under their common owner's authority; and a `closed`
plus `locked` exit as the prize.

## How it works

The finished machine has three parts: four levers that are pure props, one
`lock mechanism` that holds both the secret combination and the running
progress, and a vault gate that the mechanism unseals by hand. Every pull
in the hall runs the same script on the mechanism, which appends one colour
to the attempt and, the moment the attempt is as long as the combination,
judges the whole thing at once. This section answers the three questions a
builder hits in order: where the `pull` verb comes from, where the progress
lives, and how the gate stays shut against everything but the mechanism.

### Where does the `pull` verb come from?

REALM registers no `push` and no `pull` command, so the verb is entirely
yours: a `$`-command supplies it. (The hook catalogue lists an `ON_PUSH`
entry, but nothing in the engine raises it today; see
[Engine gaps](#engine-gaps) below.) That freedom is exactly what makes this
build possible, because it lets the *verb* and the *state* sit on different
objects.

Only one `$`-command answers a line of input. The engine walks the room's
contents, then the room itself, then your inventory, and stops at the first
object whose pattern matches, which means a single `$pull *` on the
mechanism catches every pull in the hall. The four levers therefore stay
completely inert: they carry a `lever` tag and nothing else. That also
explains why nothing here needs a target guard. Reactive
[`ON_<EVENT>` hooks](../reference/softcode.md#lifecycle-hooks) are the
opposite case, since those fire on *every* object in the room and so must
open with `if target is me:` (identity, not `==`) to react only to their own
business; see [Guard on `target`](../reference/softcode.md#guard-on-target)
and the [event bus tour](245_event_bus_tour.md). This build reaches for no
hooks at all, so it needs no guard.

The one thing the script must check for itself is *which* lever you meant.
[`get`](../reference/softcode.md#fn-get) matches a name in the local room
first and then searches the whole world, so `get('violet lever')` happily
returns a lever standing three rooms away. Comparing
[`loc`](../reference/softcode.md#fn-loc)`(lev)` against `loc(me)` is what
confines the puzzle to the hall, and the
[`has_tag`](../reference/softcode.md#fn-has_tag) test alongside it is what
stops `pull lock mechanism` from entering a phantom colour.

### Who remembers how far you have got?

The mechanism does, in two plain attributes. `code` holds the winning order
as a space-separated colour list, and `entered` holds the attempt so far as
a list. Each pull reads `entered` with
[`V()`](../reference/softcode.md#fn-v), appends the colour it derived from
the lever's name, and compares lengths:

- while the attempt is **shorter** than the code, the new list is written
  back with [`set_attr`](../reference/softcode.md#fn-set_attr) and the room
  hears a thunk;
- once the attempt is **as long** as the code, `entered` is cleared no
  matter what, and then a single equality test decides between the gate
  opening and the buzzer.

Clearing before judging is the whole trick, because it means a wrong
sequence costs the player every entry rather than one, and it means a
solved puzzle leaves no half-state behind. The player learns only that the
*sequence* was wrong, never which lever was right, so there is no picking
off one tumbler at a time.

Because the progress lives on the mechanism rather than on the player, it
persists (`set_attr` queues a save on the object it writes) and it is
shared, so two players can take turns at the wall and still be building one
attempt. Only `code` is flagged `secret`; the running `entered` list stays
readable, which costs nothing, since
[`remit`](../reference/softcode.md#fn-remit) has already announced each
colour to everyone in the room.

### What keeps the gate shut, and what still gets past it

The vault gate is an ordinary exit carrying two independent engine tags.
`closed` is what movement checks, so a closed exit refuses the walk.
`locked` is a **tag, not a `locked = true` attribute**: the built-in `open`
command refuses while `has_tag(gate, 'locked')` holds and prints the gate's
`locked_msg` instead, which is where you point the player at the levers.
The two guard different doors, so when the mechanism strips only `closed`
the gate becomes walkable while still reading as locked, and `open` would
still refuse it.

The mechanism moves the tag with
[`remove_tag`](../reference/softcode.md#fn-remove_tag), which writes the
gate directly rather than going through the `open` verb, so none of the
`open` checks apply. It is allowed to do that because authority follows
ownership: an object acts with its owner's authority, and the builder who
dug the gate also created the mechanism, so the mechanism controls the
gate. That is the same cross-object write the [airlock](032_airlock.md)
panel uses on its two doors, and the same one the
[weight plates](212_weight_plate.md) use on their prize gate.

One honest caveat: `locked` blocks `open`, not lockpicking. The built-in
`pick` command works on anything tagged `locked`, and a successful pick
strips the tag, after which a plain `open` clears the way. That is
deliberate engine behavior and the same alternate route the
[safe](016_combination_safe.md) documents; `lock_difficulty` on the gate is
the dial you turn if you want the levers to be the realistic way in.

## Build it

Dig the hall and the vault behind it. The second exit named in each `@dig`
is the return leg, so `hall` inside the Inner Vault is a separate exit
object with no tags of its own, and sealing the gate can never trap anybody
in the vault:

```text
@dig Reliquary Hall = hall, out
hall
@dig Inner Vault = vault gate, hall
@desc Inner Vault = A bare stone cell. Whatever the reliquary was guarding sits on a plinth in the centre.
```

Seal the gate from the hall side. `closed` blocks the walk, `locked` blocks
the `open` verb, and `locked_msg` is the line `open` prints instead, so use
it to send the player to the levers:

```text
@tag vault gate = closed
@tag vault gate = locked
@set vault gate/locked_msg = The vault gate has no handle. Only the levers move it.
```

Now the four levers. Their names carry their colours, the `lever` tag is
what marks them as valid input, and `amber` is a decoy that belongs to no
winning sequence:

```text
@create crimson lever
drop crimson lever
@tag crimson lever = lever
@create azure lever
drop azure lever
@tag azure lever = lever
@create emerald lever
drop emerald lever
@tag emerald lever = lever
@create amber lever
drop amber lever
@tag amber lever = lever
```

Stand the controller beside them and give it the combination. `code` is a
data attribute, so it stays a single-line `@set`, and `@attr` flags it
`secret` so only the mechanism's controllers may read it, which keeps a
stranger's gadget from lifting the answer straight off the plate (the same
flag the [safe](016_combination_safe.md) uses on its dial code):

```text
@create lock mechanism
drop lock mechanism
@desc lock mechanism = A brass reader plate wired to the levers. Engraved above it: PULL THE LEVERS IN THE ORDER OF THE DAWN.
@set lock mechanism/code = crimson azure emerald
@attr lock mechanism/code = secret
```

The state machine is one `$pull *` command, written as a
[multi-line block](../guides/world-management.md#multi-line-input-heredocs).
It runs in four steps: resolve the named lever and reject anything that is
not one of ours in this room; derive the colour from the lever's name with
[`replace`](../reference/softcode.md#fn-replace) over
[`name`](../reference/softcode.md#fn-name); append it to the attempt and
announce a thunk while the attempt is still short; and, on the entry that
fills the sequence, clear the progress and then either open the gate or
sound the buzzer:

```text
@set lock mechanism/cmd_pull = '''
$pull *:
lev = get(trim(arg0))
if not (lev and has_tag(lev, 'lever') and loc(lev) is loc(me)):
    # get() searches the whole world after the local room, so the location
    # test is what keeps a far-off lever out of the sequence.
    pemit(enactor, 'There is no such lever to pull here.')
else:
    colour = replace(name(lev), ' lever', '')
    seq = (V('entered') or []) + [colour]
    code = V('code', '').split()
    if len(seq) < len(code):
        set_attr(me, 'entered', seq)
        remit(loc(me), f'The {colour} lever thunks down. Something heavy shifts behind the wall.')
    else:
        # A full-length attempt always clears progress, right or wrong.
        set_attr(me, 'entered', [])
        if seq == code:
            remit(loc(me), 'Tumblers slam home deep in the wall. The vault gate grinds open!')
            remove_tag(get('vault gate'), 'closed')
        else:
            remit(loc(me), 'A brazen buzzer blares. Every lever springs back to neutral.')
'''
```

[`trim`](../reference/softcode.md#fn-trim) tidies the captured `arg0`, and
[`pemit`](../reference/softcode.md#fn-pemit) is used for the rejection
because a mistyped lever name is the puller's business alone, while every
real pull goes to the whole room through `remit`.

## Try it

Stand in the Reliquary Hall. The gate turns away the obvious approach and
says where the real switch is:

```text
> open vault gate
The vault gate has no handle. Only the levers move it.
```

A wrong order buzzes on the third pull, not before, because the mechanism
withholds judgement until the attempt is as long as the code:

```text
> pull crimson lever
The crimson lever thunks down. Something heavy shifts behind the wall.

> pull emerald lever
The emerald lever thunks down. Something heavy shifts behind the wall.

> pull azure lever
A brazen buzzer blares. Every lever springs back to neutral.
```

The gate is still tagged `closed` at this point, and `entered` is back to
empty, so the next pull starts a fresh attempt. Crimson, azure, emerald is
the order of the dawn:

```text
> pull crimson lever
The crimson lever thunks down. Something heavy shifts behind the wall.

> pull azure lever
The azure lever thunks down. Something heavy shifts behind the wall.

> pull emerald lever
Tumblers slam home deep in the wall. The vault gate grinds open!

> vault gate
Inner Vault
-----------
A bare stone cell. Whatever the reliquary was guarding sits on a plinth in the centre.

Exits: hall
```

Two results are worth confirming deliberately. First, the decoy: `amber`
never appears in the code, so pulling it poisons the attempt it lands in,
and the buzzer arrives on whichever pull happens to fill the sequence.
Second, a lever that is not here at all is rejected privately, and nothing
is recorded:

```text
> pull amber lever
The amber lever thunks down. Something heavy shifts behind the wall.

> pull ghost lever
There is no such lever to pull here.
```

Reading the answer off the plate fails too, because `code` is flagged
`secret`, so a stranger's softcode gets `None` from
`get_attr(get('lock mechanism'), 'code')` rather than the combination.

## Going further

- **Audible feedback.** In the mismatch branch, give pullers with a
  Lockpicking or Perception skill a
  [`skill_check`](../reference/softcode.md#fn-skill_check) hint about how
  many of their leading entries were right, which is the safecracker's ear
  from the [combination safe](016_combination_safe.md).
- **Timed lockout.** Stamp [`now()`](../reference/softcode.md#fn-now) on
  each full-length miss and refuse further pulls for a minute after three
  of them, the clock the [motion sensor](055_motion_sensor.md) keeps.
- **Trapped decoy.** Make the amber lever hurt rather than merely fail by
  firing the [landmine](049_landmine.md)'s `boom` from inside the
  controller's mismatch branch when `'amber' in seq`. Keep it there rather
  than putting a rival `$pull amber lever` on the lever itself: the first
  matching object wins the input, and the levers sit ahead of the mechanism
  in the room, so a lever-side pattern would swallow the pull and the
  sequence would never see it.
- **Make it repeatable.** As built, the vault stays open once solved. To
  re-seal the gate and clear `entered` for the next group, apply the
  restore-once, trigger-many-ways discipline from
  [puzzle reset engineering](218_puzzle_reset.md), which names this lever
  vault as one of the builds to put back.

## Engine gaps

- `ON_PUSH` is listed in the
  [lifecycle hook catalogue](../reference/softcode.md#lifecycle-hooks) as
  "this object is pushed (button, lever)", but no engine action type maps
  to it, so nothing raises it and an `ON_PUSH` attribute never fires on its
  own. Push and pull verbs are therefore supplied as `$`-commands, as this
  tutorial does. A built-in `push` command propagating an `item:on_push`
  action would close it.
