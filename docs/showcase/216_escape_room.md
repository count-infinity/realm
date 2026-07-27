# 216. Escape room

> Checklist item 216 ([now]): *instanced suite, countdown, chained puzzles, reset as a fresh instance*

**What you'll build:** A one-room escape cell that each party enters a
private copy of. Walking in starts a flood countdown, `search` turns up a
code scratched under the bench, `punch` feeds that code to the keypad,
and the keypad unbolts the hatch so you can be out before the water
arrives.

**Concepts:** this is the chapter's composition capstone, so it stacks
patterns you have already built. It uses
[instancing](044_instanced_room.md) for the private copy, the
[self-destruct](056_self_destruct.md) `wait()` chain for time pressure,
[hidden-object search](217_hidden_object_search.md) for the first puzzle,
and the [keypad](210_keypad_code.md) for the second, and it teaches the
one rule that keeps a puzzle working inside a copy: look things up in
your own room.

## How it works

The finished build is one template cell that nobody visits directly, one
doorway in a public lobby that hands each walker a private copy of that
cell, and three props inside it wired in a chain: a concealed plate
carrying a number, a keypad that compares a typed number against its own
secret attribute, and a bolted hatch leading back to the lobby. This
section answers four questions: what makes a party's cell theirs alone,
why the puzzle scripts scan their own room instead of naming objects,
how the clock stays off while you are still building, and how the two
puzzles chain into the hatch.

### What makes a party's cell theirs alone

`Holding Cell` is an ordinary room in a zone of its own (`@zone here =
cell`) carrying the two opt-in tags from
[item 44](044_instanced_room.md): `instance_template` marks the zone as
copyable, and `instance_entry` marks the room arrivals land in. The
`cell door` object in the lobby is a real exit whose destination is
deferred, because it carries `dest_resolver = instance` plus
`instance_template = cell` instead of a fixed destination. Walking it is
an ordinary traversal, so locks, wards, and the `ON_ENTER` hook all run
as usual, while the room on the far side is materialized on the way
through. With `instance_mode = solo`, everyone who walks the door on
their own is handed their own copy, so two parties walking the same
doorway land in two different cells, each with its own plate, keypad,
hatch, and clock.

A copy is keyed to the player who caused it, and the resolver reuses that
copy on the next walk rather than building a second one, which matters
for a puzzle: escape through the hatch, walk back in through the door,
and you arrive in the cell you already solved. What clears it is the
reaper. Every cloned room and prop is tagged `ephemeral`, and once a copy
has sat empty longer than the portal's `instance_ttl` (600 seconds here),
the housekeeping pass destroys it, so the next walk builds a fresh cell.
Reset is therefore a consequence of the lifetime rules rather than a
command you write, which is the whole reason a capstone puzzle is worth
instancing. For a single shared room that is reset deliberately instead,
[item 218](218_puzzle_reset.md) shows the `$reset` and `ON_RESET`
lifecycle.

### Why the puzzle scripts scan their own room

Once a copy exists, the world holds two objects named `escape hatch` (the
template's and the copy's), and a third for every further party. That
makes name lookup the interesting question.
[`get('escape hatch')`](../reference/softcode.md#fn-get) matches by name
executor-locally first, meaning the executor's own room and inventory,
and only then across the whole world, taking the first match either way.
From a keypad standing inside a copy that resolves the copy's own hatch,
so the short form is not wrong here. It is fragile, because the
fall-through is world-wide: if the local match ever misses, the same call
quietly returns the *template's* hatch, and unbolting a template leaves
every copy built afterwards already open. A
[`search_world`](../reference/softcode.md#fn-search_world) scan has no
local pass at all and sees the template plus every live copy at once.

Writing the scan out puts the scope in the code, where a reader sees it:

```text
hatches = [o for o in contents(loc(me)) if has_tag(o, 'exit') and name(o) == 'escape hatch']
```

That reads [`loc(me)`](../reference/softcode.md#fn-loc), the room the
keypad itself is standing in, which inside a copy is the copy.
[`contents()`](../reference/softcode.md#fn-contents) returns exits
alongside items and players, so the `exit` tag plus the
[`name()`](../reference/softcode.md#fn-name) match is what narrows it to
the hatch. The same rule governs the countdown, which lives on the room
object and therefore copies with it, so each cell counts down on its own
attributes.

### How the clock stays off while you build

The countdown is the [item 56](056_self_destruct.md) chain: exactly one
[`wait()`](../reference/softcode.md#fn-wait) is pending at a time, and
each stage announces, decrements `count`, and schedules the next stage
with `trigger me/tick`. Since `wait()` is in-memory and dies with a
reboot, a restart mid-run leaves the cell quiet, which is the right
failure mode for a copy that a restart deletes anyway; where a timer must
outlive a reboot, use [`expire()`](../reference/softcode.md#fn-expire)
instead.

What starts it is the room's `ON_ENTER`
[lifecycle hook](../reference/softcode.md#lifecycle-hooks), and its guard
is the load-bearing line:

```text
if has_tag(enactor, 'player') and enactor is not owner(me) and not V('started'):
```

Each of the three filters earns its place. You walk into the template
yourself while building it, and without the owner filter that entry sets
`started` on the template, every copy inherits the flag, and no party's
clock ever runs. The `player` filter keeps a wandering NPC from arming
the cell, and `not V('started')` keeps a second arrival from restarting a
clock that is already running. Note that
[`owner()`](../reference/softcode.md#fn-owner) returns an object, so the
comparison is the identity form `is not`, matching the
[`target` guard](../reference/softcode.md#guard-on-target) convention. A
reactive hook is heard by the whole room, so the guard wraps the entire
body rather than sitting inside it. This hook needs no separate same-room
test, because `me` is always the room the `enactor` just walked into.

### How the two puzzles chain

`search` is a built-in command ([item 217](217_hidden_object_search.md)):
it rolls the searcher's Observation against the `conceal_difficulty` of
every `invisible` object in the room, and each one it beats loses the tag
and prints its `reveal_msg`, which is where the player reads the number.
Because the plate the searcher revealed is the copy's plate, the
template's stays concealed and the next party still has to search.

The number then goes to the keypad ([item 210](210_keypad_code.md)).
`punch` takes no argument: it calls
[`prompt()`](../reference/softcode.md#fn-prompt), which captures the
player's *next* line into the keypad's `check` attribute as `arg0`, so
the code never lands in scrollback. `check` runs as the keypad, which is
why it can read its own `code` attribute even though `@attr ... = secret`
hides that attribute from every other reader.

A match strips the `closed` tag from the hatch, and that single tag is
the lock: a `closed` exit refuses the walk, while the `locked` tag it
keeps refuses only a bare-handed `open`, answering with `locked_msg`. The
hatch's destination is a static one, the real lobby, and a destination
outside the copied zone resolves against the live world in every copy, so
everyone who escapes lands back in the same shared room.

## Build it

Start with the public lobby, then dig the template cell and put it in a
zone of its own with the two instancing tags. The cell is deliberately
unlinked from the street, so the only way in is the doorway built at the
end:

```text
@dig Escape Lobby = lobby, out
lobby
@dig Holding Cell
@teleport me = Holding Cell
@zone here = cell
@tag here = instance_template
@tag here = instance_entry
@desc here = A bare cell, one bench, a heavy hatch. A countdown clock ticks on the wall.
```

The clock runs on two plain numbers, so they stay one-line `@set` values:
`limit` is how many stages the countdown has, and `beat` is the seconds
between them.

```text
@set here/limit = 3
@set here/beat = 60
```

Arrival arms the clock. The hook stamps `started` so it arms once, copies
`limit` into the working counter, sounds the klaxon to everyone in the
room, and lights the first wait:

```text
@set here/on_enter = '''
if has_tag(enactor, 'player') and enactor is not owner(me) and not V('started'):  # your own entries while building leave the template unarmed
    set_attr(me, 'started', 1)
    set_attr(me, 'count', V('limit', 3))
    remit(me, f"A klaxon wails: {V('limit', 3)} minutes until the cell floods. Find the way out!")
    set_attr(me, 'pending', wait(V('beat', 60), 'trigger me/tick'))  # stash the handle so a variation can cancel_wait() it
'''
```

Each stage decrements the counter and re-arms the single pending wait,
until the last one floods the cell instead. `trigger me/tick` runs the
plain `tick` attribute directly, so it is never player input and needs no
`$` pattern:

```text
@set here/tick = '''
n = V('count', 0) - 1
if n <= 0:
    remit(me, 'TIME UP. Water roars in through the vents.')
else:
    set_attr(me, 'count', n)
    remit(me, f'{n} minutes remain...')
    set_attr(me, 'pending', wait(V('beat', 60), 'trigger me/tick'))
'''
```

Puzzle one is pure configuration: an `invisible` prop with a difficulty
and the line a successful `search` prints.

```text
@create scratched plate
drop scratched plate
@set scratched plate/conceal_difficulty = 2
@set scratched plate/reveal_msg = Scratched under the bench, tiny numbers: 7291.
@tag scratched plate = invisible
```

Puzzle two is the keypad. Its code is a data value, flagged `secret` so
only a controller reads it back, and `punch` is a single expression, so
it stays a one-liner:

```text
@create cell keypad
drop cell keypad
@desc cell keypad = A keypad wired to the hatch bolts. PUNCH to enter a code.
@set cell keypad/code = 7291
@attr cell keypad/code = secret
@set cell keypad/cmd_punch = $punch: prompt(enactor, 'Enter the code you found:', 'check')
```

The callback finds the hatch by scanning its own room, compares the
captured line against the secret code, and unbolts on a match. This is
the instance-local lookup the whole build turns on:

```text
@set cell keypad/check = '''
hatches = [o for o in contents(loc(me)) if has_tag(o, 'exit') and name(o) == 'escape hatch']  # this room's hatch, never another copy's
if hatches and trim(arg0) == str(V('code')):  # arg0 is the line the player typed at the prompt
    remove_tag(hatches[0], 'closed')
    remit(loc(me), 'The keypad flashes green -- the escape hatch unbolts!')
else:
    pemit(enactor, 'The keypad flashes red. Nothing happens.')
'''
```

The hatch is a static exit back to the real lobby. `closed` is what
refuses the walk, and `locked` with its message is what refuses a player
who tries to lever it open by hand:

```text
@open escape hatch = Escape Lobby
@tag escape hatch = closed
@tag escape hatch = locked
@set escape hatch/locked_msg = The escape hatch is bolted from a keypad beside it.
```

Finally, back in the lobby, the doorway that hands out copies. It is an
ordinary object tagged `exit` and dropped in the room, and the four
attributes are what make it a portal into a private copy:

```text
@teleport me = Escape Lobby
@create cell door
@tag cell door = exit
drop cell door
@set cell door/dest_resolver = instance
@set cell door/instance_template = cell
@set cell door/instance_mode = solo
@set cell door/instance_ttl = 600
```

## Try it

Walk the door from the lobby. The copy is built on the way through and
the klaxon is the first thing you hear, before the room description:

```text
> cell door
You leave cell door.
A klaxon wails: 3 minutes until the cell floods. Find the way out!

Holding Cell
------------
A bare cell, one bench, a heavy hatch. A countdown clock ticks on the wall.

You see:
  a cell keypad

Exits: escape hatch
```

The plate is missing from that list because it is still `invisible`.
Search turns it up, printing its `reveal_msg` first and then the standard
find line:

```text
> search
Scratched under the bench, tiny numbers: 7291.
Your search turns up: scratched plate.
```

Now the keypad. `punch` asks, your next line answers, and a wrong number
only buzzes at you:

```text
> punch
Enter the code you found:
> 0000
The keypad flashes red. Nothing happens.
> punch
Enter the code you found:
> 7291
The keypad flashes green -- the escape hatch unbolts!
> escape hatch
Escape Lobby
------------

Exits: out, cell door
```

Leave the clock running instead and the chain plays out to the flood,
one line per beat:

```text
2 minutes remain...
1 minutes remain...
TIME UP. Water roars in through the vents.
```

Two results are worth confirming deliberately. First, have a friend walk
`cell door` while you are inside: they land in a different Holding Cell
with their own klaxon, their own concealed plate, and a hatch that is
still bolted, none of it touched by your run. Second, walk back in
through `cell door` yourself after escaping: you arrive in *your* copy,
plate revealed and hatch open, because the resolver reuses the copy you
already own. Stay out until the copy has been empty past its 600-second
TTL and the reaper destroys it, and the next walk builds a cell that is
fresh again.

## Going further

- **Shared teams.** Set `@set cell door/instance_mode = shared` and have
  a party `follow` the leader in, which routes the followers into the
  leader's copy: one cell, one clock, whole team (see
  [item 44](044_instanced_room.md)).
- **Real failure.** At `TIME UP`, move the occupants with
  [`teleport_obj`](../reference/softcode.md#fn-teleport_obj) to a
  "You Drowned" debrief room rather than only narrating. That needs
  authority over the occupants, so fire it from an admin-owned object.
- **Stop the clock on escape.** The room stashes its wait handle in
  `pending`, so a script that notices the hatch opening can call
  [`cancel_wait`](../reference/softcode.md#fn-cancel_wait) on it and end
  the countdown the moment the party is out, exactly as the
  [self-destruct](056_self_destruct.md)'s `abort` does.
- **More rooms.** The template can be a whole suite, since digging
  several rooms into the `cell` zone copies the entire zone per party, so
  a three-room escape sequence instances exactly like this one.
- **Leaderboard.** On escape, `remit` the elapsed time (`limit - count`)
  and post it to a board object in the lobby
  ([item 228](228_leaderboards.md)).
