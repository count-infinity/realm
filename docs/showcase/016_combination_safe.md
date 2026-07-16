# 016. Combination Safe

> Checklist item 16 — now — *prompt() input, secret attr flag*

**What you'll build:** A wall safe opened by dialing a numeric code one
number at a time; the owner (and only the owner) can reset the code
through a `prompt()` wizard. Part of the [Heist arc](arc_heist.md) —
builds on the rooms from [item 27](027_secret_door.md) and digs the
vault itself.

**Concepts:** composing the engine's container + closed + locked
conventions on one object, a multi-step state machine in a `$`-command,
`prompt()` for out-of-band input, the `secret` attribute flag, and
`owner()` as a social rule.

## How it works

The safe is one object wearing three hats, all engine conventions:

| Piece | How |
|---|---|
| holds the loot | `container = true`, `closed` tag — `open`/`close`/`get ... from` just work |
| refuses to open | `locked = true` + `locked_msg` — the same fields every door uses |
| stays pickable | `lock_skill` / `lock_difficulty` — the built-in `pick` command remains a legitimate alternate route |

The interesting part is the **dial**. There is no modal input state:
each `dial <number>` is an ordinary `$`-command that appends to an
`entered` list stored in a plain attribute. Because the progress lives
on the *safe*, it survives reboots and is shared — two thieves can take
turns at the dial. When as many numbers are in as the code holds, the
sequence is compared:

- **match** — the safe sets `locked = False` (the exact field `open`
  checks) and announces the clunk;
- **mismatch** — progress resets, and the dialer learns only that the
  *sequence* was wrong, never which digit. No brute-forcing one tumbler
  at a time.

Resetting the code uses **`prompt()`** — the softcode wizard primitive.
`setcode` doesn't take the new code as an argument (arguments end up in
command history and over shoulders); it asks, and the player's *next
line* runs the safe's `on_new_code` attribute with the answer bound as
`arg0`.

Finally, the code itself. REALM attributes are **readable by default**
— deliberately, so traps can read hp and shops can read prices. That
means any stranger's gadget could `get_attr(safe, 'code')`. The `@attr`
command closes exactly that hole: an attribute flagged `secret` is
readable only by the safe's controllers, while the safe's own scripts
(which run as the safe) keep working.

## Build it

Dig the vault behind the antechamber and walk in (`@dig` makes the
`vault door` exit here and an `antechamber` exit back):

```text
@dig Nexagen Vault = vault door, antechamber
@tag vault door = closed
open vault door
vault door
```

The safe, loaded then sealed — load the loot *before* you close and
lock, in the order a real person would:

```text
@create wall safe
@set wall safe/container = true
drop wall safe
@create prototype schematics
put prototype schematics in wall safe
close wall safe
@set wall safe/locked = true
@set wall safe/locked_msg = The safe door doesn't budge. Engraved under the dial: DIAL <NUMBER>.
@set wall safe/lock_skill = lockpicking
@set wall safe/lock_difficulty = 4
```

The code, kept honest:

```text
@set wall safe/code = 17 4 33
@attr wall safe/code = secret
```

The dial — one `$`-command, one state machine. `arg0` is the wildcard
capture; `trim()` guards against stray spaces; the two `set_attr` paths
either bank progress or reset it:

```text
@set wall safe/cmd_dial = $dial *: seq = (get_attr(me, 'entered') or []) + [trim(arg0)]; code = str(get_attr(me, 'code')).split(); done = len(seq) >= len(code); set_attr(me, 'entered', [] if done else seq); (set_attr(me, 'locked', False), pemit(enactor, 'CLUNK. The last tumbler drops -- the wall safe unlocks.')) if done and seq == code else pemit(enactor, 'Clunk. The dial spins back to zero.' if done else 'Click.')
```

The reset wizard. Two social rules in two guards: `enactor != owner(me)`
(only the owner resets — an object comparison, not a name check), and
the safe must be open (you can't reprogram a safe through its own locked
door). Passing both, `prompt()` captures the player's next line into
`on_new_code`:

```text
@set wall safe/cmd_setcode = $setcode: pemit(enactor, 'Only the owner may reset the dial.') if enactor != owner(me) else (pemit(enactor, 'Open the safe first -- the reset switch is inside the door.') if has_tag(me, 'closed') else prompt(enactor, 'New combination (numbers separated by spaces):', 'on_new_code'))
@set wall safe/on_new_code = (set_attr(me, 'code', trim(arg0)), pemit(enactor, 'The tumblers reseat. New combination: ' + trim(arg0))) if trim(arg0) and trim(arg0).replace(' ', '').isdigit() else pemit(enactor, 'Numbers separated by spaces, nothing else. The dial is unchanged.')
```

Arc flavor — leave the combination lying around where a burglar can
case it:

```text
@teleport me = The Security Office
@create crumpled note
drop crumpled note
@desc crumpled note = Hurried handwriting: '17 - 4 - 33. Do NOT write this down.'
```

## Try it

As a thief in the vault:

```text
open wall safe       -> "The safe door doesn't budge. Engraved under the dial: DIAL <NUMBER>."
dial 1               -> Click.
dial 2               -> Click.
dial 3               -> Clunk. The dial spins back to zero.
dial 17              -> Click.
dial 4               -> Click.
dial 33              -> CLUNK. The last tumbler drops -- the wall safe unlocks.
open wall safe
get prototype schematics from wall safe
```

The safecracker's route (carry a `lockpicks`-tagged kit or eat -5 for
improvising): `pick wall safe` — lockpicking 14 with tools beats -4.

As the owner, with the safe open:

```text
setcode              -> New combination (numbers separated by spaces):
5 25 45              -> The tumblers reseat. New combination: 5 25 45
```

And the secret flag at work — as anyone else:

```text
@eval result = get_attr(get('wall safe'), 'code')     -> => None
```

(The owner gets `=> '5 25 45'` — controllers still read it.)

## Going further

- **Audible tumblers** — in the `Click.` branch, give dialers with
  Lockpicking a `skill_check` hint about whether that number is in the
  code — the classic safecracker's ear.
- **Time lock** — store `now()` on each full-sequence miss and refuse
  dialing for five minutes after three misses.
- **Trapped dial** — the mismatch branch already knows a wrong sequence
  finished; wire it to [item 49](049_landmine.md)'s `boom` pattern.
- **Keypad variant** — one `$enter *` command that splits digits; the
  state machine doesn't change.
