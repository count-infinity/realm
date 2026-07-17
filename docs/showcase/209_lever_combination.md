# 209. Lever combination

> Checklist item 209 — now — *multi-object shared puzzle state, ON_PUSH-style verbs, cross-object controller*

**What you'll build:** A vault hall with four wall levers. Pull them in
the right order and the sealed vault gate grinds open; pull them in the
wrong order and every lever springs back to neutral. This is the first
of the [Puzzles & Mechanisms](index.md) chapter, and the pattern under
it — *many input objects, one shared state machine, a third object as
the prize* — recurs in every puzzle that follows.

**Concepts:** the [combination-safe dial](016_combination_safe.md) state
machine (item 16) **distributed across several objects**; a controller
that owns the progress attribute; the airlock's
[cross-object wiring](032_airlock.md) (item 32) where one object reads and
writes another; and a `closed`+`locked` exit as a prize that no `open`
command can shortcut.

## How it works

REALM has no built-in `push`/`pull` verb — pushing a button is just a
`$`-command you supply. That freedom is the point: the *verb* and the
*state* can live on different objects.

1. **The levers are dumb props.** Each is a real object tagged `lever`,
   so it shows up in the room, can be looked at, and can be validated by
   name — but it holds no logic. All four are interchangeable inputs.

2. **One controller owns the sequence.** A `lock mechanism` object
   carries the secret `code` (a space-separated colour list) and the
   running `entered` list. Its single `$pull *` command captures whichever
   lever you named, appends that lever's colour to `entered`, and — the
   moment enough numbers are in — compares the whole sequence at once.
   This is exactly the safe's `$dial` from item 16, only the digits
   arrive from four separate objects instead of one dial. Progress lives
   on the controller, so it survives reboots and is shared: two players
   can take turns at the wall.

   - **match** — the controller strips the `closed` tag off the vault
     gate (a raw write, running with the builder's authority because the
     mechanism and gate share an owner — the [item 32](032_airlock.md)
     cross-object move);
   - **mismatch** — `entered` resets, and the puller learns only that the
     *sequence* was wrong, never which lever was right. No pulling one
     tumbler at a time.

3. **The prize can't be cheated.** The vault gate is an ordinary exit
   wearing two hats: the `closed` tag blocks traversal, and `locked =
   true` makes the built-in `open` command refuse it (with `locked_msg`).
   A player can't just `open vault gate` to skip the puzzle — only the
   mechanism's raw `remove_tag` moves it, because raw writes bypass the
   `open` verb entirely. (Traversal keys on the `closed` tag, so once the
   tag is gone the gate is walkable even though `locked` is still set —
   the two flags guard different doors.)

## Build it

Dig the hall and the vault behind it. `@dig`'s second exit (`hall`) is
the way back, so the gate only ever needs configuring from the hall
side:

```text
@dig Reliquary Hall = hall, out
hall
@dig Inner Vault = vault gate, hall
@desc Inner Vault = A bare stone cell. Whatever the reliquary was guarding sits on a plinth in the centre.
```

Seal the gate — `closed` blocks the walk, `locked` blocks the `open`
verb, and `locked_msg` tells the player where the real switch is:

```text
@tag vault gate = closed
@set vault gate/locked = true
@set vault gate/locked_msg = The vault gate has no handle -- only the levers move it.
```

The four levers. Their names carry their colours; `amber` is a decoy
that appears in no valid sequence:

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

The controller. `code` is the winning order; keep it `secret` so a
stranger's gadget can't read the answer off it (the same flag the safe
uses in [item 16](016_combination_safe.md)):

```text
@create lock mechanism
drop lock mechanism
@desc lock mechanism = A brass reader plate wired to the levers. Engraved above it: PULL THE LEVERS IN THE ORDER OF THE DAWN.
@set lock mechanism/code = crimson azure emerald
@attr lock mechanism/code = secret
```

And the state machine — one `$pull *` command, the item-16 dial redrawn
for many inputs. `arg0` is the lever you named; the walrus assignments
keep it to one line, and the final `[-1]` returns the branch's value so
nothing leaks to the caller:

```text
@set lock mechanism/cmd_pull = $pull *: lev = get(trim(arg0)); (pemit(enactor, 'There is no such lever to pull here.') if not (lev and has_tag(lev, 'lever') and loc(lev) == loc(me)) else (color := replace(name(lev), ' lever', ''), seq := (get_attr(me, 'entered') or []) + [color], code := str(get_attr(me, 'code')).split(), full := len(seq) >= len(code), (set_attr(me, 'entered', []), (remit(loc(me), 'Tumblers slam home deep in the wall -- the vault gate grinds open!'), remove_tag(get('vault gate'), 'closed')) if seq == code else remit(loc(me), 'A brazen buzzer blares. Every lever springs back to neutral.')) if full else (set_attr(me, 'entered', seq), remit(loc(me), 'The ' + color + ' lever thunks down. Something heavy shifts behind the wall.')))[-1])
```

## Try it

Stand in the Reliquary Hall. The gate resists the obvious approach:

```text
open vault gate          -> The vault gate has no handle -- only the levers move it.
```

Wrong order buzzes and resets:

```text
pull crimson lever       -> The crimson lever thunks down...
pull emerald lever       -> The crimson lever thunks down...    (still building)
pull azure lever         -> A brazen buzzer blares. Every lever springs back to neutral.
```

Right order — crimson, azure, emerald — opens it:

```text
pull crimson lever       -> The crimson lever thunks down...
pull azure lever         -> The crimson lever thunks down...
pull emerald lever       -> Tumblers slam home deep in the wall -- the vault gate grinds open!
vault gate               -> the Inner Vault
```

The decoy `amber` lever counts as a wrong entry the instant it fills the
sequence — pulling it is never safe.

## Going further

- **Audible feedback** — in the reset branch, give pullers with a
  Lockpicking or Perception skill a `skill_check` hint about how many of
  their first entries were correct — the safecracker's ear from
  [item 16](016_combination_safe.md).
- **Timed lockout** — stamp `now()` on each full-sequence miss and refuse
  further pulls for a minute after three misses (item 55's clock).
- **Trapped levers** — the decoy could do more than fail: wire the amber
  lever's own `$pull amber` to spring the [landmine](049_landmine.md)
  `boom` on whoever touched it.
- **Reset it** — this puzzle stays solved once opened. To make it
  repeatable — re-seal the gate, clear `entered` — see
  [item 218](218_puzzle_reset.md), which resets exactly this mechanism.
