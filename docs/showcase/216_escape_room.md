# 216. Escape room

> Checklist item 216 — now — *composition capstone: instanced suite + countdown + chained puzzles, resettable*

**What you'll build:** A one-room escape room, private to each group.
Walk in and a flood countdown starts; **search** the cell to find a code
scratched under the bench; **punch** that code into the keypad; the hatch
unbolts and you're out — if you beat the clock. Every party gets its own
fresh copy, so "reset" is free: the next group walks in on an untouched
cell.

**Concepts:** this is the chapter's **composition capstone**. It stacks
[instancing](044_instanced_room.md) (item 44) for per-group privacy and
reset, the [self-destruct countdown](056_self_destruct.md) (item 56) for
time pressure, [hidden-object search](217_hidden_object_search.md) (item
217) for the first puzzle, and the [keypad](210_keypad_code.md) (item
210) for the second — and it teaches the one rule that makes puzzles work
*inside* an instance: **look things up locally.**

## How it works

Everything here is a pattern you've already built. The capstone is in
wiring them together correctly.

1. **The cell is a template, entered by walking.** The `Holding Cell` is
   an `instance_template` + `instance_entry` room ([item 44](044_instanced_room.md));
   a `cell door` exit in the lobby carries `dest_resolver = instance`, so
   walking it materializes a *private copy* and drops you in. A second
   party walks the same door into a *different* copy. That is the whole
   reset story: you never reset the cell, you get a new one.

2. **Look things up locally, never by global name.** The template and
   every live copy all contain an object named `escape hatch`. A
   `get('escape hatch')` from inside a copy might resolve the *wrong*
   one. So the keypad finds its hatch by scanning **its own room** —
   `[o for o in contents(loc(me)) if ... name(o) == 'escape hatch']`.
   This is the golden rule for instanced puzzles: reference `loc(me)` and
   `here`, not global names.

3. **The countdown belongs to the room copy.** The entry room's
   `ON_ENTER` starts the item-56 `wait()` chain — but guarded with
   `enactor != owner(me)` so it fires for *arriving players*, not for the
   builder walking the template during construction (whose entry would
   otherwise trip the `started` flag and poison every copy). Each copy
   keeps its own `count`, so two groups' clocks run independently.

4. **The puzzles chain.** `search` reveals the code (perception, [item
   217](217_hidden_object_search.md)); the code opens the keypad ([item
   210](210_keypad_code.md)); the keypad unbolts the hatch; the hatch's
   *static* destination — the real lobby — copies as-is into every
   instance, so escaping lands everyone back in the same shared world.

## Build it

The real lobby, then the template cell dug off on its own zone:

```text
@dig Escape Lobby = lobby, out
lobby
@dig Holding Cell
@teleport me = Holding Cell
@zone here = cell
@tag here = instance_template
@tag here = instance_entry
@desc here = A bare cell, one bench, a heavy hatch. A countdown clock ticks on the wall.
@set here/limit = 3
@set here/beat = 60
```

The countdown — owner-guarded so building it doesn't start it:

```text
@set here/on_enter = (set_attr(me, 'started', 1), set_attr(me, 'count', V('limit', 3)), remit(me, 'A klaxon wails: ' + str(V('limit', 3)) + ' minutes until the cell floods. Find the way out!'), set_attr(me, 'pending', wait(V('beat', 60), 'trigger me/tick'))) if has_tag(enactor, 'player') and enactor != owner(me) and not V('started') else None
@set here/tick = n = V('count', 0) - 1; (remit(me, 'TIME UP. Water roars in through the vents.') if n <= 0 else (set_attr(me, 'count', n), remit(me, str(n) + ' minutes remain...'), set_attr(me, 'pending', wait(V('beat', 60), 'trigger me/tick'))))
```

Puzzle one — the hidden code (revealed by `search`, item 217):

```text
@create scratched plate
drop scratched plate
@set scratched plate/conceal_difficulty = 2
@set scratched plate/reveal_msg = Scratched under the bench, tiny numbers: 7291.
@tag scratched plate = invisible
```

Puzzle two — the keypad. Note `check` finds the hatch **in its own
room**, the instance-local lookup:

```text
@create cell keypad
drop cell keypad
@desc cell keypad = A keypad wired to the hatch bolts. PUNCH to enter a code.
@set cell keypad/code = 7291
@attr cell keypad/code = secret
@set cell keypad/cmd_punch = $punch: prompt(enactor, 'Enter the code you found:', 'check')
@set cell keypad/check = hs = [o for o in contents(loc(me)) if has_tag(o, 'exit') and name(o) == 'escape hatch']; (remove_tag(hs[0], 'closed'), remit(loc(me), 'The keypad flashes green -- the escape hatch unbolts!')) if hs and trim(arg0) == str(V('code')) else pemit(enactor, 'The keypad flashes red. Nothing happens.')
```

The hatch — a static exit back to the real lobby, sealed until the keypad
opens it:

```text
@open escape hatch = Escape Lobby
@tag escape hatch = closed
@tag escape hatch = locked
@set escape hatch/locked_msg = The escape hatch is bolted from a keypad beside it.
```

Finally, back in the lobby, the door that instances the cell:

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

From the lobby, walk in — the clock starts:

```text
cell door            -> the Holding Cell
                        A klaxon wails: 3 minutes until the cell floods. Find the way out!
```

Solve the chain before it runs down:

```text
search               -> Scratched under the bench, tiny numbers: 7291.
punch                -> Enter the code you found:
7291                 -> The keypad flashes green -- the escape hatch unbolts!
escape hatch         -> back in the Escape Lobby
```

Have a friend walk `cell door`: they land in their *own* Holding Cell —
their klaxon, their scratched plate, their locked hatch, none of it
touched by your run. Leave a copy empty past its TTL and the reaper
removes it; the next entry is freshly built. **That** is puzzle reset by
construction — no `$reset` needed, because nobody ever plays the same
copy twice.

## Going further

- **Shared teams** — `@set cell door/instance_mode = shared` and have a
  party `follow` the leader in; one cell, whole team, one clock (item 44).
- **Real failure** — at `TIME UP`, `teleport_obj` the occupants to a
  "You Drowned" debrief room instead of just narrating (grant the room
  authority over its occupants, or fire it from an admin-owned master).
- **More rooms** — the template can be a *suite* (dig several rooms, zone
  them together); the whole zone copies per group, so a three-room escape
  sequence instances exactly like this one.
- **Leaderboard** — on escape, `remit` the elapsed time (`limit - count`)
  and post it to a board object in the lobby (item 228).
- **Single-copy variant** — if you'd rather *not* instance (one shared
  cell for everyone), [item 218](218_puzzle_reset.md) shows the `$reset`
  and `ON_RESET` lifecycle that makes a persistent room safely repeatable.
