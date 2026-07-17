# 210. Keypad code

> Checklist item 210 — now — *prompt() code entry, secret attr flag, knowledge-gating*

**What you'll build:** A cleanroom sealed behind a numeric keypad. The
code isn't sold, dropped, or dialed by brute force — it's written on a
maintenance log in a *different* room. Find the log, read the code, punch
it in. The door is gated by **knowledge**, not by an item or a skill.

**Concepts:** `prompt()` for out-of-band input (the answer never appears
in command history), the `secret` attribute flag from
[item 16](016_combination_safe.md), and the design idea of a lock whose
"key" is information seeded elsewhere in the world.

## How it works

The keypad is the [combination safe](016_combination_safe.md)'s reset
wizard turned into the lock itself:

1. **`enter code` asks; it doesn't take an argument.** `$enter code`
   calls `prompt(enactor, ..., 'check_code')`, which captures the
   player's *next line* into the keypad's `check_code` callback with the
   answer bound as `arg0`. Typing the code as an argument
   (`enter code 4815`) would leave it in scrollback and command history;
   the prompt keeps it a one-shot secret.

2. **`check_code` compares against a `secret` attribute.** The callback
   runs *as the keypad*, so it can read the keypad's own `code` even
   though the `@attr ... = secret` flag hides that attribute from every
   stranger's `get_attr`. Match strips the `closed` tag off the gate;
   mismatch just buzzes.

3. **The code lives in the world, not on the keypad's face.** A
   maintenance log two rooms away carries the number in its description.
   Nothing links the log to the door mechanically — the connection is in
   the player's head. That's the whole tutorial: a *knowledge* gate is
   just a secret compared against player-supplied input, with the hint
   placed somewhere a player has to go and look.

As in [item 209](209_lever_combination.md), the gate is `closed` (blocks
the walk) and `locked = true` (blocks the `open` verb), so the keypad is
the only way through.

## Build it

The lab, and the cleanroom behind the gate:

```text
@dig Fabrication Lab = lab, out
lab
@dig The Cleanroom = clean gate, lab
@desc The Cleanroom = A white cell under harsh light. The prototype hums on its cradle.
@tag clean gate = closed
@set clean gate/locked = true
@set clean gate/locked_msg = A keypad blinks beside the clean gate. ENTER CODE to proceed.
```

The keypad, with its code kept honest by the `secret` flag:

```text
@create keypad
drop keypad
@desc keypad = A backlit numeric keypad, twelve keys worn shiny. A label reads: AUTHORIZED PERSONNEL. ENTER CODE.
@set keypad/code = 4815
@attr keypad/code = secret
@set keypad/cmd_enter = $enter code: prompt(enactor, 'Enter access code:', 'check_code')
@set keypad/check_code = (remove_tag(get('clean gate'), 'closed'), remit(loc(me), 'The keypad chirps green. The clean gate slides open.')) if trim(arg0) == str(get_attr(me, 'code')) else pemit(enactor, 'The keypad buzzes red. ACCESS DENIED.')
```

Now seed the code somewhere a player must find it — a maintenance log
back out in the corridor:

```text
out
@dig Maintenance Corridor = corridor, lab
corridor
@create maintenance log
drop maintenance log
@desc maintenance log = A greasy clipboard. Halfway down: "Cleanroom access reset to 4815 -- update your badges."
```

## Try it

From the lab, the gate won't budge on its own:

```text
open clean gate      -> A keypad blinks beside the clean gate. ENTER CODE to proceed.
```

Guess blind and you're stuck:

```text
enter code           -> Enter access code:
0000                 -> The keypad buzzes red. ACCESS DENIED.
```

Go read the log (`out`, `corridor`, `look maintenance log`), come back,
and punch it in:

```text
enter code           -> Enter access code:
4815                 -> The keypad chirps green. The clean gate slides open.
clean gate           -> the Cleanroom
```

And the code stays hidden from prying gadgets — as anyone but the
keypad's owner:

```text
@eval result = get_attr(get('keypad'), 'code')     -> => None
```

## Going further

- **Lockout on failures** — count wrong tries in an attribute and, past
  three, refuse `enter code` for five minutes (`now()` arithmetic) or
  page the owner like the [tripwire](050_tripwire_alarm.md).
- **Per-player badges** — instead of one shared code, store a dict of
  `{player_id: code}` and check the enactor's own — the ATM ledger shape
  from [item 4](004_atm_terminal.md).
- **Rotating code** — an `on_tick` that rerolls `code` nightly and
  rewrites the maintenance log's description to match, so yesterday's
  intel goes stale (item 145's scheduled events).
- **Combine gates** — stack a [keycard ward](026_keycard_door.md) on the
  same gate: the card gets you to the keypad, the code gets you through.
