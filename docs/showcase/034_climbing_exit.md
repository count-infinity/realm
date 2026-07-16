# 034. Climbing Exit

> Checklist item 34 — now — *skill-gated wards, damage(), ON_FAIL*

**What you'll build:** A rock chimney from the gully floor to an
eagle's ledge: traversing it rolls your Climbing skill, failure drops
you back down for 1d6 falling damage, and the descent is its own —
easier — roll.

**Concepts:** the engine's built-in skill-gated exits (`check_skill`,
`check_difficulty`, `check_fail_msg`), `ON_FAIL` on the exit as the
consequence hook, `damage()` under proximity authority, and asymmetric
difficulty per face.

## How it works

**The roll is stock.** You don't script the check: any exit with a
`check_skill` attribute rolls it (at `-check_difficulty`) for every
traversal, refuses on failure with your `check_fail_msg`, and tells the
room `<name> tries to go rock chimney and fails.` The game system
resolves the skill — under GURPS rules, Climbing defaults to DX-5, so
an unskilled scrambler *can* get lucky, which is exactly what a cliff
should feel like.

**Consequences hang on `ON_FAIL`.** Every thwarted move fires
`event:on_fail` with the exit as target, so the exit itself can carry
the price of falling: `damage(enactor, roll('1d6'))` plus a landing
line. Two authority notes make this legal and safe: `damage()` is
*proximity* authority — the chimney can hurt the climber because they
are in its room — and the failed mover never relocated, so they're
guaranteed to still be standing there when the trigger runs. One
honesty note: an `ON_FAIL` script can't read *why* the move failed
(locked? closed? skill?), so hang damage on exits whose only failure
mode is the roll — true here, and noted below for the day you build a
cliff with a locked gate on it.

**Each face is its own exit** — so each face is its own climb. Going
up is a hard scramble (`check_difficulty = 2`); coming down the same
chimney is a controlled slither (`check_difficulty = 0`) with its own
fail line and its own tumble. Same pair of rooms, two different rolls:
the mirror-image of [025](025_lockable_door.md)'s "one door, two
faces" — here the faces are *supposed* to disagree.

## Build it

The gully and the ledge, joined by a paired exit — then make the
upward face a climb:

```text
@dig Gully Floor
@teleport me = Gully Floor
@dig Eagle Ledge = rock chimney, rock chimney
@set rock chimney/check_skill = climbing
@set rock chimney/check_difficulty = 2
@set rock chimney/check_fail_msg = Halfway up, a hold crumbles under your fingers.
@set rock chimney/on_fail = damage(enactor, roll('1d6')); pemit(enactor, 'You land hard in the scree at the bottom.')
```

The descent face — `@teleport` up rather than climb (the builder gets
no special grip; a failed roll costs *you* 1d6 like anyone), and
configure the way down as an easier roll:

```text
@teleport me = Eagle Ledge
@set rock chimney/check_skill = climbing
@set rock chimney/check_difficulty = 0
@set rock chimney/check_fail_msg = Your boot skids on the polished rock.
@set rock chimney/on_fail = damage(enactor, roll('1d6')); pemit(enactor, 'You bounce down the last body-length and land in a heap.')
@teleport me = Gully Floor
```

## Try it

As a skilled climber (Climbing 14 or so):

```text
rock chimney        -> most days: you're on Eagle Ledge
rock chimney        -> the descent at full skill: down safely
```

As a deskbound scholar:

```text
rock chimney        -> Halfway up, a hold crumbles under your fingers.
                       You land hard in the scree at the bottom.   (-1d6 HP)
```

— and the gully hears `Scholar tries to go rock chimney and fails.`
Check your HP; the mountain keeps score. Failure leaves you exactly
where you started (the engine refuses the move *before* relocation),
so there's no half-way ledge state to clean up.

## Engine gaps

- `ON_FAIL` softcode can't see the failure reason (the action carries
  `reason` — 'skill', 'closed', 'locked' — but action data isn't bound
  into trigger namespaces). On an exit that is also lockable or
  closable, fall damage would fire for bounced-off-the-locked-gate
  too. Workaround here: the chimney's only failure mode is the roll.
  Noted for the integrator alongside the same gap in items 28/30.

## Going further

- **Fall INTO somewhere** — the walked-into exit's `ON_FAIL` is the
  one witnessed event allowed to relocate its enactor (the portal
  pattern): add `teleport_obj(enactor, 'Scree Gully')` and a failed
  climb drops you into a different room than you left.
- **Gear helps** — sell pitons: the fail script can soften the landing
  for anyone carrying them
  (`damage(enactor, roll('1d6')) if not get('pitons') else damage(enactor, 1)`
  — `get` resolves against the enactor's inventory too).
- **Exhaustion, not just injury** — swap the `damage()` for
  `apply_effect(enactor, 'modifier_effect', kind='winded', ...)`; the
  next attempt is genuinely harder.
- **A rope changes the game** — a `$tie rope:` command that simply
  deletes `check_skill` from the face (`del_attr`): skill-gates are
  attributes, so removing the gate *is* content.
