# 203. Cutscenes

> Checklist item 203 ([now]): *wait()-paced pemit/remit, $skip via cancel_wait*

**What you'll build:** a holoprojector that plays a paced briefing, sending
timed lines of text to everyone in the room one at a time, with a `skip`
command any viewer may type to cut it short.

**Concepts:** a [`wait()`](../reference/softcode.md#fn-wait)-paced sequence
written as a self-scheduling chain (one wait pending at a time), the handle
that `wait()` hands back stored in an attribute so the sequence stays
cancellable, [`remit`](../reference/softcode.md#fn-remit) for a whole room
beside [`pemit`](../reference/softcode.md#fn-pemit) for one player, and
[`cancel_wait`](../reference/softcode.md#fn-cancel_wait) as the entire
`skip`.

## How it works

The finished projector holds a list of four lines and answers to `play
briefing`. The first line reaches the room at once, another arrives every
few seconds after that, and when the list runs out the projector falls
silent. At any point anyone standing there may type `skip` and the rest of
the briefing is dropped. Three attributes carry all of the state: the
`scenes` list, a `step` counter, and a `pending` handle. This section
answers how the pacing stays a single timer, who hears each line, what
`skip` actually cancels, and what a reboot does to a scene in progress.

### How the pacing stays a single timer

The sequence is a chain rather than a schedule. `scene_step` emits the line
at `step`, bumps the counter with [`incr`](../reference/softcode.md#fn-incr),
and schedules *itself* to run again after a pause, so exactly one `wait()`
is pending at any moment and there is only ever one thing to call off. The
scheduled command is `trigger me/scene_step`, which runs the plain
`scene_step` attribute directly. No player input is involved, which is the
same shape the [self-destruct](056_self_destruct.md) countdown uses to
re-arm its stages; here the payload is text instead of klaxons.

The pause is read from an attribute, `V('pace', 6)`, rather than baked into
the script, so each projector paces to taste and a builder checking the
sequence sets `pace` to `0` to watch the whole thing land at once.

`play` opens the chain with `wait(0, 'trigger me/scene_step')` instead of
running the first step inline, and that choice earns its keep twice. A
zero-second wait still returns a handle and still goes through the
scheduler, so the first line arrives the moment the `play` command finishes,
and a `skip` typed in that instant cancels the briefing before a single line
has landed. One code path then covers the first line and every later one.

### Who hears a line: the room or one player

`scene_step` calls `remit(here, ...)`, which delivers to everyone in the
projector's room, so the briefing plays to the whole party.
[`pemit`](../reference/softcode.md#fn-pemit) is the one-player counterpart,
and `cmd_play` and `cmd_skip` both use it for the replies that belong to the
person typing ("The projector is already running", "Nothing is playing").
The audience is a choice of emitter, so the same machinery serves a
room-wide briefing and a private vision.

Aiming the chain at a single viewer takes one extra attribute, because a
step fired by `wait()` runs with the **object itself** as `enactor`: the
engine runs `trigger me/scene_step` as the projector, so inside `scene_step`
the name `enactor` is the holoprojector and never the player who typed
`play`. A solo cutscene therefore records the viewer while it still has one,
during the `$`-command, with `set_attr(me, 'viewer', enactor.id)`, and each
step emits with `pemit(get('#' + str(V('viewer'))), ...)`. Inside a
`$`-command such as `cmd_play` the name `enactor` is the player, which is
why the refusal message reaches them directly.

### What `skip` actually cancels

`skip` is a plain [`$`-command](../reference/softcode.md#triggers-attributes-on-objects)
on the projector, gated only by the object's `use` lock, which is open by
default, so any viewer in the room may cut the scene short. It reads the one
stored handle, passes it to `cancel_wait`, clears `pending` and `step`, and
announces the cut to the room. The handle is authority as well as identity,
since `cancel_wait` requires the caller to control the object that scheduled
the wait, and here the projector cancels its own timer.

Because the chain is one wait deep, the cancellation is complete: there is
no queue of later lines to hunt down, and the scene stops on the line it had
reached. A player standing in a different room reaches neither `play` nor
`skip`, since `$`-command matching searches the typist's own room.

Pick verbs no builtin already claims. Builtins dispatch before
`$`-triggers, so a projector answering to `$go` would never be reached,
while `play` and `skip` are free.

### What a reboot does to a scene in progress

`wait()` lives in memory, so a restart during a briefing drops the pending
timer while the `pending` attribute persists on the object. The projector
then reports itself busy until someone types `skip`, which clears the stale
state and leaves it ready to play again; cancelling an unknown handle is a
harmless no-op, and the rest of the branch still runs. For
a piece of theatre that is the right trade, and where a timer must survive a
restart the tool is [`expire()`](../reference/softcode.md#fn-expire), as the
[EMP charge](057_emp_charge.md) uses it.

## Build it

Create the projector, drop it where the audience will stand, and describe
it:

```text
@create holoprojector
drop holoprojector
@desc holoprojector = A squat drum of lenses and cooling fins, dark until someone starts a briefing.
```

The script of the cutscene is data rather than code, so it stays a
single-line `@set`: a list stored as a literal comes back as a real list
that `scene_step` indexes by number, and `pace` is the seconds between
lines.

```text
@set holoprojector/scenes = ["The lights dim. A star map flickers to life.", "A red world turns slowly, ringed with debris.", "A voice whispers: this is Kepler's Rest, your target.", "The map collapses into darkness."]
@set holoprojector/pace = 6
```

`play briefing` refuses to start a second chain over a running one, and
otherwise rewinds the counter and lights the first wait, keeping the handle
it gets back. It is the first multi-line script here, so it is typed as a
`'''` block, the input form
[World Management](../guides/world-management.md#multi-line-input-heredocs)
documents: end the `@set` line with `'''`, type the body, and close with a
line of just `'''`.

```text
@set holoprojector/cmd_play = '''
$play briefing:
if V('pending'):
    pemit(enactor, 'The projector is already running. Type skip to cut it short.')
else:
    set_attr(me, 'step', 0)
    # a zero-second wait still returns a handle, so skip works before line one
    set_attr(me, 'pending', wait(0, 'trigger me/scene_step'))
'''
```

`scene_step` is the body of the chain. It reads the line at `step`, emits it
to the room, advances the counter, and books its own next run; once the
counter passes the last line it clears `pending` instead and the chain ends:

```text
@set holoprojector/scene_step = '''
lines = V('scenes', [])
n = V('step', 0)
if n >= len(lines):
    del_attr(me, 'pending')  # past the last line: nothing is scheduled now
else:
    remit(here, lines[n])
    incr('step')
    # schedule the next line; exactly one wait is pending at a time
    set_attr(me, 'pending', wait(V('pace', 6), 'trigger me/scene_step'))
'''
```

`skip` cancels that one pending wait, resets the state, and tells the room
the projection was cut:

```text
@set holoprojector/cmd_skip = '''
$skip:
if not V('pending'):
    pemit(enactor, 'Nothing is playing.')
else:
    cancel_wait(V('pending'))
    del_attr(me, 'pending')
    set_attr(me, 'step', 0)
    remit(here, 'The projection snaps off. (skipped)')
'''
```

## Try it

Stand in the room with a friend and start the briefing. The `play` command
has no reply of its own, because the first thing you see is the opening line
of the sequence:

```text
> play briefing
The lights dim. A star map flickers to life.
A red world turns slowly, ringed with debris.
A voice whispers: this is Kepler's Rest, your target.
The map collapses into darkness.
```

Six seconds separate each line from the next, and your friend sees all four
at the same moments you do, because `remit` addresses the room. Start it
again and cut it short:

```text
> play briefing
The lights dim. A star map flickers to life.

> skip
The projection snaps off. (skipped)
```

The remaining lines never arrive, and the announcement reaches the whole
room rather than only the person who typed it. Two more results are worth
confirming deliberately. Typing `play briefing` while a briefing is running
answers `The projector is already running. Type skip to cut it short.`
instead of starting a second chain, and `skip` with nothing playing answers
`Nothing is playing.`

For a fast demo, set the pace to zero and all four lines arrive in one
breath:

```text
> @set holoprojector/pace = 0
Set holoprojector/pace = 0
```

## Going further

- **Solo cutscenes.** Record the viewer during `cmd_play` with
  `set_attr(me, 'viewer', enactor.id)`, then emit each step with
  `pemit(get('#' + str(V('viewer'))), lines[n])`. The chain becomes a
  private vision, and the stored id is what carries the viewer across the
  waits, since `enactor` inside a wait-fired step is the projector.
- **Per-line pacing.** Make `scenes` a list of `[text, delay]` pairs and
  read the delay out of the current entry, which buys slow reveals and quick
  cuts in one briefing.
- **Cutscene as a quest step.** Have the last `scene_step` call the
  [Quest Warden](198_quest_framework.md)'s `advance` for the viewer you
  stored, so watching the briefing to the end moves the mission along.
- **Freeze the room.** [`add_tag`](../reference/softcode.md#fn-add_tag) a
  `watching` tag onto viewers at `play` and have a movement `on_check` ward
  hold them until the scene ends or they `skip`, which turns the briefing
  into a true cutscene lock.
- **Klaxon variant.** Point the chain at
  [`act(me, ..., targeting='zone')`](../reference/softcode.md#fn-act) and it
  plays to every room of the projector's zone, like the self-destruct's
  all-call. Zone targeting reads the zone tags of the room the projector
  stands in, so tag that room (`@zone here = station`) or the announcement
  reaches nobody.
