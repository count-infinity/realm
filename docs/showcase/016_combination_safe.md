# 016. Combination Safe

> Checklist item 16 ([now]): *prompt() input, secret attr flag*

**What you'll build:** A wall safe opened by dialing a numeric code one
number at a time, where the owner (and only the owner) can reset the code
through a [`prompt()`](../reference/softcode.md#fn-prompt) wizard. It is
part of the [Heist arc](arc_heist.md): it reuses the rooms from
[the secret door](027_secret_door.md) and digs the vault itself.

**Concepts:** composing the engine's `container`, `closed`, and `locked`
tags on one object, a multi-step state machine in a `$`-command,
[`prompt()`](../reference/softcode.md#fn-prompt) for out-of-band input,
the `secret` attribute flag, and
[`owner()`](../reference/softcode.md#fn-owner) as a social rule.

## How it works

The finished safe is one object that behaves like a strongbox by reusing
three engine tags, then adds two small pieces of softcode: a dial that is
really a tiny state machine living in a `$`-command, and a reset that
*asks* for the new code instead of taking it as an argument. The code
itself is hidden with one attribute flag. This section walks through each
piece and why it takes that shape.

### Three engine tags, no new mechanics

The safe wears three tags, each one a convention the builtins already
honor, so `open`, `close`, and `get ... from` work on it with no scripting
at all:

| Tag | What it buys |
|---|---|
| `container` | it can hold the loot, and `close` / `open` / `get ... from` operate on it |
| `closed` | it starts shut, so its contents are sealed away |
| `locked` | `open` refuses while the tag is present, printing the safe's `locked_msg` |

`locked` is a tag, not a `locked = true` attribute:
[`open` checks `has_tag(safe, 'locked')`](../reference/softcode.md#fn-has_tag),
so the only way to open the safe is to make that tag go away. Two plain
attributes ride alongside the lock. `locked_msg` is the line `open` shows
while it is barred, and `lock_skill` with `lock_difficulty` let the
built-in `pick` command stay a legitimate alternate route (a lockpicking
check against the safe), so the dial is never the *only* way in.

### How the dial remembers progress

There is no modal "you are now dialing" state. Each `dial <number>` is an
ordinary `$`-command that appends the number to an `entered` list stored
on the safe with [`set_attr`](../reference/softcode.md#fn-set_attr).
Because the progress lives on the *safe* rather than on the player, it
survives reboots and is shared, so two thieves can take turns at the dial.
Once the list is as long as the code, the two are compared:

- on a **match**, the safe drops its `locked` tag with
  [`remove_tag`](../reference/softcode.md#fn-remove_tag), which is exactly
  the tag `open` checks, and announces the clunk;
- on a **mismatch**, the progress resets, and the dialer learns only that
  the whole *sequence* was wrong, never which single digit, so there is no
  brute-forcing one tumbler at a time.

### Why the reset asks instead of taking an argument

Resetting the code uses [`prompt()`](../reference/softcode.md#fn-prompt),
the softcode wizard primitive (see the
[wizards guide](../guides/wizards.md)). `setcode` deliberately does not
take the new code as an argument, because a typed argument lands in the
command history and in plain sight over a shoulder. Instead it asks, and
the player's *next line* runs the safe's `on_new_code` attribute with the
answer bound as `arg0`. That callback runs as the safe, so it can write
the safe's own `code` attribute, and while the prompt is pending the words
`help`, `quit`, and `exit` still reach the game, so a half-typed answer
never traps anyone. The same one-question wizard, chained so its callback
prompts again, is what the [typewriter](010_typewriter.md) and the
[dialogue-tree NPC](067_dialogue_tree_npc.md) grow into.

### Why the code is readable by nobody but the owner

REALM attributes are readable by default, and on purpose: traps read a
victim's hp and shops read an item's price, so a blanket "attributes are
private" rule would break the mechanics layer. The plain consequence is
that any stranger's gadget could call
[`get_attr(safe, 'code')`](../reference/softcode.md#fn-get_attr) and read
the combination straight off. The `secret` attribute flag closes exactly
that hole. Flagging `code` secret marks it readable only by the safe's
controllers, so the owner and the safe's own scripts (which run as the
safe) still read it, while everyone else reads the default of `None`.

## Build it

First dig the vault behind the antechamber and step inside. The `@dig`
names a `vault door` exit leading in and an `antechamber` exit back, and
tagging the door `closed` means you have to open it to pass:

```text
@dig Nexagen Vault = vault door, antechamber
@tag vault door = closed
open vault door
vault door
```

Now build the safe and load it in the order a real person would, putting
the loot in *before* the door is closed and locked. The `container` tag is
what lets you `close` it, and the `locked` tag is what `open` will later
refuse:

```text
@create wall safe
@tag wall safe = container
drop wall safe
@create prototype schematics
put prototype schematics in wall safe
close wall safe
@tag wall safe = locked
```

Give the lock its three plain attributes: the message `open` prints while
the safe is barred, and the skill and penalty the built-in `pick` command
contests, so a lockpicker keeps a fair alternate route:

```text
@set wall safe/locked_msg = The safe door doesn't budge. Engraved under the dial: DIAL <NUMBER>.
@set wall safe/lock_skill = lockpicking
@set wall safe/lock_difficulty = 4
```

Set the combination, then flag it `secret` with `@attr` so only the safe's
controllers can read it back:

```text
@set wall safe/code = 17 4 33
@attr wall safe/code = secret
```

The dial is one `$`-command holding the whole state machine, written as a
[multi-line block](../guides/world-management.md#multi-line-input-heredocs).
It reads the running `entered` list with
[`V()`](../reference/softcode.md#fn-v), appends this
[`trim`](../reference/softcode.md#fn-trim)med number, splits the stored
code into its own list, and once both are the same length either drops the
`locked` tag on an exact match (announcing with
[`pemit`](../reference/softcode.md#fn-pemit)) or resets the progress and
spins back to zero on a miss:

```text
@set wall safe/cmd_dial = '''
$dial *:
seq = (V('entered') or []) + [trim(arg0)]
code = str(V('code')).split()
done = len(seq) >= len(code)
set_attr(me, 'entered', [] if done else seq)  # a full row clears entered either way, so a wrong code just starts over
if done and seq == code:
    remove_tag(me, 'locked')
    pemit(enactor, 'CLUNK. The last tumbler drops -- the wall safe unlocks.')
elif done:
    pemit(enactor, 'Clunk. The dial spins back to zero.')
else:
    pemit(enactor, 'Click.')
'''
```

The reset is gated twice before it will ask anything. `enactor != owner(me)`
keeps everyone but the owner out (an object comparison through
[`owner()`](../reference/softcode.md#fn-owner), not a name check), and
`has_tag(me, 'closed')` refuses while the door is shut, since the reset
switch is inside. Passing both, `prompt()` captures the player's next line
into `on_new_code`:

```text
@set wall safe/cmd_setcode = $setcode: pemit(enactor, 'Only the owner may reset the dial.') if enactor != owner(me) else (pemit(enactor, 'Open the safe first -- the reset switch is inside the door.') if has_tag(me, 'closed') else prompt(enactor, 'New combination (numbers separated by spaces):', 'on_new_code'))
```

`on_new_code` is where that next line arrives as `arg0`. It accepts the
answer only if it is digits and spaces, writes it to `code`, and otherwise
leaves the dial unchanged:

```text
@set wall safe/on_new_code = (set_attr(me, 'code', trim(arg0)), pemit(enactor, f'The tumblers reseat. New combination: {trim(arg0)}')) if trim(arg0) and trim(arg0).replace(' ', '').isdigit() else pemit(enactor, 'Numbers separated by spaces, nothing else. The dial is unchanged.')
```

Finally, a little arc flavor: leave the combination lying around in the
security office where a burglar can case it:

```text
@teleport me = The Security Office
@create crumpled note
drop crumpled note
@desc crumpled note = Hurried handwriting: '17 - 4 - 33. Do NOT write this down.'
```

## Try it

As a thief standing in the vault, a wrong full sequence tells you nothing
about which digit was off, and only the exact code drops the lock:

```text
> open wall safe
The safe door doesn't budge. Engraved under the dial: DIAL <NUMBER>.
> dial 1
Click.
> dial 2
Click.
> dial 3
Clunk. The dial spins back to zero.
> dial 17
Click.
> dial 4
Click.
> dial 33
CLUNK. The last tumbler drops -- the wall safe unlocks.
> open wall safe
You open the wall safe.
> get prototype schematics from wall safe
You pick up a prototype schematics.
```

The lockpicker's route is the built-in `pick` (carry a `lockpicks`-tagged
kit, or take the -5 for improvising): `pick wall safe` runs a lockpicking
check at -4, so tools turn a skill of 14 into exactly the 10 it needs to
beat the lock, while improvising bare-handed falls to 5 and fails.

As the owner, with the safe open, `setcode` asks for the new code and your
next line becomes it:

```text
> setcode
New combination (numbers separated by spaces):
> 5 25 45
The tumblers reseat. New combination: 5 25 45
```

The `secret` flag shows at work when a stranger's softcode tries to read
the code and gets nothing:

```text
> @eval result = get_attr(get('wall safe'), 'code')
=> None
```

Run as the owner, that same line returns `=> '5 25 45'`, because
controllers are exempt from the flag.

## Going further

- **Audible tumblers:** in the `Click.` branch, give a dialer with
  Lockpicking a [`skill_check`](../reference/softcode.md#fn-skill_check)
  hint about whether that number belongs in the code, the classic
  safecracker's ear.
- **Time lock:** store [`now()`](../reference/softcode.md#fn-now) on each
  full-sequence miss and refuse dialing for five minutes after three
  misses.
- **Trapped dial:** the mismatch branch already knows a wrong sequence
  just finished, so wire it to the [landmine](049_landmine.md)'s `boom`
  pattern.
- **Keypad variant:** one `$enter *` command that splits the digits
  itself, and the state machine does not change.
