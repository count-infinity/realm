# 210. Keypad code

> Checklist item 210 ([now]): *prompt() code entry, secret attrs, hint placement*

**What you'll build:** A cleanroom sealed behind a numeric keypad. The code
is never sold, dropped, or dialed by brute force, because it is written on a
maintenance log in a *different* room: find the log, read the code, punch it
in. The door is gated by **knowledge** rather than by an item or a skill.

**Concepts:** [`prompt()`](../reference/softcode.md#fn-prompt) for
out-of-band input (the answer never lands in scrollback as a command), the
`secret` attribute flag introduced by the
[combination safe](016_combination_safe.md), and the design idea of a lock
whose "key" is information seeded elsewhere in the world.

## How it works

The finished puzzle is three rooms, one exit, and two props. The exit wears the
`closed` and `locked` tags so that neither walking nor `open` gets you
through, a keypad standing in front of it holds one flagged attribute and
two short scripts, and a clipboard in a third room carries the number in its
description. Nothing in the database ties the clipboard to the gate, since
the only link is the one the player makes. This section answers three
questions: why the keypad *asks* for the code instead of accepting it as an
argument, how a script reads an attribute it hides from everybody else, and
what each of the gate's two tags is actually doing.

### Why the keypad asks instead of taking an argument

The keypad's trigger is `$enter code`, a pattern with no wildcard in it, so
it matches that line and nothing else: typing `enter code 4815` matches no
trigger at all and the digits never reach the keypad. (Matching is
case-insensitive, so `ENTER CODE` works as well.) What `enter code` runs is a
single call to [`prompt()`](../reference/softcode.md#fn-prompt), which
installs a one-shot capture on the player's session, so their **next line**
is delivered to the keypad's `check_code` attribute with the answer bound as
`arg0` instead of being parsed as a command. That keeps the code out of
command history and out of anything watching the command stream, which is the
whole reason to ask rather than to read an argument.

Two consequences are worth knowing before you pick a code. A line whose first
word is `help`, `quit`, or `exit` is passed through to the ordinary command
and the prompt stays waiting, so keep codes numeric. And a
[heredoc](../guides/world-management.md#multi-line-input-heredocs) never
opens while a prompt is capturing, so a builder answering a keypad is
answering it, not starting a block.

### How the callback reads a code it hides from everyone else

`prompt()` runs the callback **as the object that asked**, which here is the
keypad, while `enactor` stays the player who answered. That matters because
of how the `secret` flag works: `@attr keypad/code = secret` makes
[`get_attr`](../reference/softcode.md#fn-get_attr) hand back the default
instead of the value unless the reader controls the object. The keypad
controls itself, so [`V('code')`](../reference/softcode.md#fn-v) inside
`check_code` reads `4815` normally. Its owner (the builder who created it)
and any admin control it too. Everybody else reads the default: a player, a
gadget owned by another player, and even a second builder who does not own
the keypad, since builder authority covers unowned world objects and this one
has an owner.

REALM's default is the opposite of Penn's, meaning attributes are readable
unless flagged, because the mechanics layer depends on reading (a trap reads
hp, a shop reads a price). The `secret` flag is how you opt one attribute out
of that, and it is the only thing standing between a curious script and the
combination.

### What the gate's two tags each do

The two tags divide the work, exactly as they do for the
[lever combination](209_lever_combination.md). `closed` is the physical door
state that blocks traversal, so walking into the gate prints its
`closed_msg`. `locked` is a **tag**, not a `locked = true` attribute, and the
built-in `open` verb refuses while it is present, printing the gate's
`locked_msg`, which is where the keypad advertises itself. A correct code
strips only `closed` with
[`remove_tag`](../reference/softcode.md#fn-remove_tag), so the gate becomes
walkable while `open` still refuses it. The keypad stays the only way to
work the door.

### Where the knowledge lives

The maintenance log is an ordinary object with an ordinary description that
happens to contain the number. It has no script, no tag, and no relationship
to the keypad. A player who never walks down the corridor has no route in,
and one who reads the clipboard needs nothing else. That is the entire
lesson: a knowledge gate is a secret compared against player-supplied input,
with the hint placed somewhere a player has to go and look.

## Build it

Start with the lab and the cleanroom behind it. The gate is sealed with both
tags, and `locked_msg` is what a player sees when they try the obvious thing,
so it names the keypad:

```text
@dig Fabrication Lab = lab, out
lab
@dig The Cleanroom = clean gate, lab
@desc The Cleanroom = A white cell under harsh light. The prototype hums on its cradle.
@tag clean gate = closed
@tag clean gate = locked
@set clean gate/locked_msg = A keypad blinks beside the clean gate. ENTER CODE to proceed.
```

Now the keypad itself, standing in the lab. The combination goes in a plain
attribute, and the very next line flags it `secret` so only the keypad and
its owner read it back:

```text
@create keypad
drop keypad
@desc keypad = A backlit numeric keypad, twelve keys worn shiny. A label reads: AUTHORIZED PERSONNEL. ENTER CODE.
@set keypad/code = 4815
@attr keypad/code = secret
```

The entry command is one statement, so it stays a one-liner. It takes no
argument: all it does is ask, naming `check_code` as the attribute that will
receive the answer:

```text
@set keypad/cmd_enter = $enter code: prompt(enactor, 'Enter access code:', 'check_code')
```

`check_code` is where the answer arrives. It compares, and on a match it
opens the gate for the room and announces it with
[`remit`](../reference/softcode.md#fn-remit); on a miss it buzzes at the one
player with [`pemit`](../reference/softcode.md#fn-pemit). Because that is a
branch, it is written as a
[multi-line block](../guides/world-management.md#multi-line-input-heredocs):

```text
@set keypad/check_code = '''
# arg0 is the player's whole next line and the code is stored as a number,
# so compare the trimmed answer against str(V('code')).
if trim(arg0) == str(V('code')):
    remove_tag(get('clean gate'), 'closed')
    remit(loc(me), 'The keypad chirps green. The clean gate slides open.')
else:
    pemit(enactor, 'The keypad buzzes red. ACCESS DENIED.')
'''
```

[`trim`](../reference/softcode.md#fn-trim) matters because `arg0` is the raw
line, padding and all, and [`loc(me)`](../reference/softcode.md#fn-loc) is
the lab rather than the answerer's room, which is the right place to
announce a door that just slid open.

Finally, seed the code where a player has to walk to find it. The corridor
hangs off the lab, so `corridor` takes you there and `lab` brings you back:

```text
@dig Maintenance Corridor = corridor, lab
corridor
@create maintenance log
drop maintenance log
@desc maintenance log = A greasy clipboard. Halfway down: "Cleanroom access reset to 4815 -- update your badges."
lab
```

## Try it

Standing in the lab, neither of the two obvious approaches moves the gate,
and each refusal comes from a different tag:

```text
> open clean gate
A keypad blinks beside the clean gate. ENTER CODE to proceed.
> clean gate
The clean gate is closed.
```

Guessing blind gets you a red light, and the gate stays shut:

```text
> enter code
Enter access code:
> 0000
The keypad buzzes red. ACCESS DENIED.
```

Go read the log, walk back, and punch the real number in. Notice that `4815`
is typed on its own line as an answer, never as part of a command:

```text
> corridor
Maintenance Corridor
> look maintenance log
maintenance log
A greasy clipboard. Halfway down: "Cleanroom access reset to 4815 -- update your badges."
> lab
Fabrication Lab
> enter code
Enter access code:
> 4815
The keypad chirps green. The clean gate slides open.
> clean gate
The Cleanroom
A white cell under harsh light. The prototype hums on its cradle.
```

The one result worth confirming deliberately is the `secret` flag, and the
clearest way to see it is to ask for the attribute with a default. Run as a
builder who does not own the keypad, the read is refused and the default
comes back instead:

```text
> @eval result = get_attr(get('keypad'), 'code', 'no reading')
=> 'no reading'
```

Run as the keypad's owner, the same line returns `=> 4815`, because
controllers are exempt from the flag. Softcode running with a player's
authority gets `'no reading'` as well, which is what keeps a snooping gadget
from lifting the combination.

## Engine gaps

- The `secret` flag is enforced on softcode reads only. Both `examine` (the
  player command, `cmd_examine` in `realm/commands/builtin/look.py`) and
  `@examine` (`cmd_examine_full` in `realm/commands/olc/admin.py`) print
  `db.all()` without consulting `readable_attr()`, so `examine keypad` shows
  `code: 4815` to anyone who types it. The puzzle holds against scripts and
  gadgets today; it holds against a curious player once those two listings
  filter on the flag. Reported for the integrator.

## Going further

- **Lockout on failures.** Count wrong tries in an attribute and, past three,
  refuse `enter code` for five minutes using
  [`now()`](../reference/softcode.md#fn-now) arithmetic, or page the owner
  the way the [tripwire](050_tripwire_alarm.md) does.
- **Per-player badges.** Instead of one shared code, keep a dict of
  `{player_id: code}` and check the enactor's own entry, which is the ledger
  shape from the [ATM terminal](004_atm_terminal.md). Keep that dict on a
  single-line `@set`, since a `'''` block stores its body as raw text and a
  dict has to stay a dict for `.get()` to work.
- **Rotating code.** An `on_tick` that rerolls `code` nightly and rewrites
  the maintenance log's description to match, so yesterday's intelligence
  goes stale. See [scheduled events](145_scheduled_events.md).
- **Combine gates.** Stack a [keycard ward](026_keycard_door.md) on the same
  gate, so the card gets you as far as the keypad and the code gets you
  through it.
