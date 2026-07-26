# 034. Climbing Exit

> Checklist item 34 ([now]): *skill-gated wards, damage(), ON_FAIL*

**What you'll build:** A rock chimney from the gully floor up to an eagle's
ledge. Traversing it rolls your Climbing skill; a failed roll drops you back
down for 1d6 falling damage, and the descent is its own, easier roll.

**Concepts:** the engine's built-in skill-gated exits (`check_skill`,
`check_difficulty`, `check_fail_msg`),
[`ON_FAIL`](../reference/softcode.md#lifecycle-hooks) on the exit as the
consequence hook, [`damage()`](../reference/softcode.md#fn-damage) under
proximity authority, and asymmetric difficulty per face.

## How it works

A climb here is two rooms joined by two exits, and almost none of it is
scripted. The engine already knows how to roll a skill against an exit and
refuse the move when the roll fails, so your job is only to name the skill,
set the difficulty, and decide what a fall costs. This section answers three
questions: where the roll comes from, where the fall damage hangs, and why
each direction is its own climb.

### Where does the roll come from?

You do not script the check. Any exit with a `check_skill` attribute rolls
that skill on every traversal, at a penalty of `check_difficulty`, and on a
failure it refuses the move, shows your `check_fail_msg` to the climber, and
prints `<name> tries to go rock chimney and fails.` to everyone else in the
room. The active game system resolves the skill: under GURPS, the reference
ruleset, Climbing defaults to DX-5, so even an untrained scrambler can get
lucky, which is exactly what a cliff should feel like. The refusal happens
before the move, so a failed climber never leaves the room and there is no
half-way ledge state to clean up.

### Where does the fall come from?

Refusing the move is the engine's half; charging for the fall is yours. Every
thwarted move fires
[`event:on_fail`](../reference/softcode.md#lifecycle-hooks) with the exit as
its target, so the exit carries an `ON_FAIL` script that hurts the climber and
prints a landing line. [`damage(enactor, roll('1d6'))`](../reference/softcode.md#fn-damage)
is legal here for two reasons. First, `damage()` runs on *proximity*
authority: the chimney may hurt the climber because the climber stands in the
chimney's room, not because it owns them. Second, the failed climber never
relocated, since the roll refused the move before it happened, so they are
guaranteed to still be in the room when the script runs.
[`roll('1d6')`](../reference/softcode.md#fn-roll) returns 1 to 6, which
`damage` subtracts straight from the climber's `hp`.

### Why the hook still needs a target guard

An `ON_FAIL` script, like every
[`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook, fires on
*every* object in the room, not only on the exit that was refused. Open it
with [`if target is me:`](../reference/softcode.md#guard-on-target) so the
chimney charges for a fall only when the chimney is the exit that failed. Add
a second failable exit to this room later and, unguarded, a climber who
bounces off *that* one would still take the chimney's 1d6.

The action also carries *why* it failed.
[`adata('reason')`](../reference/softcode.md#event-data-namespace) returns
`'skill'`, `'closed'`, `'locked'`, `'no_destination'`, and friends, so an exit
that can fail more than one way can price each kind of refusal differently.
This chimney has no lock and no `closed` tag, so it can fail exactly one way:
`adata('reason')` is always `'skill'` here, and gating on it would be dead
code. Reach for it the day you bolt a gate across the chimney, when an
unguarded fall would otherwise charge a climber 1d6 for rattling a locked
door.

### Why each direction is its own climb

A two-way `@dig` makes two exits, one in each room, that happen to share a
name, and because they are separate objects they can carry separate
difficulties. Going up is a hard scramble (`check_difficulty = 2`) and coming
down the same shaft is a controlled slither (`check_difficulty = 0`), each
with its own fail line and its own tumble. It is the same two-faces idea as
the [lockable door](025_lockable_door.md), except that here the two faces are
meant to disagree.

## Build it

Dig the gully and the ledge, joined by a paired exit, and stand on the gully
floor so the next commands configure the upward face:

```text
@dig Gully Floor
@teleport me = Gully Floor
@dig Eagle Ledge = rock chimney, rock chimney
```

Name the skill the upward face rolls, the penalty it rolls at, and the line a
climber reads when a hold gives way:

```text
@set rock chimney/check_skill = climbing
@set rock chimney/check_difficulty = 2
@set rock chimney/check_fail_msg = Halfway up, a hold crumbles under your fingers.
```

Now the fall. The `ON_FAIL` hurts the climber and prints the landing, guarded
so it fires only for the chimney's own failure:

```text
@set rock chimney/on_fail = if target is me: damage(enactor, roll('1d6')); pemit(enactor, 'You land hard in the scree at the bottom.')  # guard: ON_FAIL fires on every object in the room
```

Cross to the ledge to configure the downward face. Teleport up rather than
climb, since a builder gets no special grip and a failed roll would cost you
1d6 like anyone else. The descent is the easier roll (`check_difficulty = 0`)
with its own fail line and its own tumble, and the last teleport walks you
home:

```text
@teleport me = Eagle Ledge
@set rock chimney/check_skill = climbing
@set rock chimney/check_difficulty = 0
@set rock chimney/check_fail_msg = Your boot skids on the polished rock.
@set rock chimney/on_fail = if target is me: damage(enactor, roll('1d6')); pemit(enactor, 'You bounce down the last body-length and land in a heap.')
@teleport me = Gully Floor
```

## Try it

As a skilled climber (Climbing 14 or so), the odds are with you both ways:

```text
> rock chimney
You leave rock chimney.
(Eagle Ledge, most days: skill 14 against difficulty 2 clears a 3d6 roll about three times in four)

> rock chimney
You leave rock chimney.
(and back down at full skill, difficulty 0: almost always)
```

As a deskbound scholar (Climbing 8), the mountain collects:

```text
> rock chimney
Halfway up, a hold crumbles under your fingers.
You land hard in the scree at the bottom.
```

Only the roll decides which of those you get. On the failed climb the gully
also hears `Scholar tries to go rock chimney and fails.`, your HP drops by 1
to 6, and you stay exactly where you started, because the engine refuses the
move before any relocation. Check your HP afterward; the mountain keeps score.

## Going further

- **Fall somewhere new.** The `ON_FAIL` on the exit a walker actually chose is
  the one witnessed event the engine lets relocate its enactor, so
  [`move_to(enactor, 'Scree Gully')`](../reference/softcode.md#fn-move_to) in
  the fail script drops a failed climber into a different room than the one
  they left. It is `move_to` and not a forced teleport because the move rides
  the climber's own consent to the exit they walked, not authority over them.
- **Gear helps.** Sell pitons and let the fall read the climber's own pack:
  `damage(enactor, 1 if any(name(o) == 'pitons' for o in contents(enactor)) else roll('1d6'))`
  softens the landing for anyone carrying them.
  [`contents(enactor)`](../reference/softcode.md#fn-contents) is the climber's
  inventory; `get('pitons')` would be wrong, because
  [`get`](../reference/softcode.md#fn-get) searches the exit's own room and
  then the whole world, not the climber.
- **Exhaustion, not injury.** Swap the `damage()` for
  [`apply_effect(enactor, 'modifier_effect', kind='winded', duration=30, check_mods={'climbing': -2})`](../reference/softcode.md#fn-apply_effect),
  and the next attempt is genuinely harder.
- **A rope changes the game.** A `$tie rope:` command that runs
  [`del_attr(me, 'check_skill')`](../reference/softcode.md#fn-del_attr) on the
  face removes the gate outright, because the roll only happens while
  `check_skill` is set. The gate is an attribute, so deleting it is content.
