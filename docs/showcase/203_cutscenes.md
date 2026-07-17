# 203. Cutscenes

> Checklist item 203 — [now] — *wait()-paced pemit/remit, $skip via cancel_wait*

**What you'll build:** a holoprojector that plays a paced briefing —
timed lines of text drifting out to everyone in the room one beat at a
time — with a `skip` command that any viewer can type to cut it short.

**Concepts:** a **`wait()`-paced sequence** as a self-scheduling chain
(one wait pending at a time), the **handle-in-an-attribute** so the
sequence is cancellable, `remit` for the whole room (or `pemit` for one),
and `cancel_wait` as the entire `skip`.

## How it works

A cutscene is a chain, not a schedule. The lines live in a `scenes` list;
`scene_step` shows the current line, advances the `step` counter, and
schedules *itself* to run again after a pause — so exactly one `wait()` is
ever pending. That single pending handle, stashed in a `pending`
attribute, is what makes the whole thing skippable: `cancel_wait(pending)`
kills the one wait in flight, and the sequence stops dead. (The
[self-destruct](056_self_destruct.md) countdown is the same
one-wait-at-a-time chain; here the payload is text instead of klaxons.)

Three points:

- **Paced by an attribute, not a magic number.** The pause between lines
  is `get_attr(me, 'pace', 6)` — a knob you can turn per projector (and
  set to `0` for instant playback while testing). `play` kicks the chain
  with `wait(0, ...)` so the first line lands immediately.
- **`remit` reaches the room; `pemit` reaches one.** This projector plays
  to everyone present (`remit(here, ...)`) — a briefing for the whole
  party. Swap `remit(here, ...)` for `pemit(enactor, ...)` and the very
  same chain becomes a private vision only the initiator sees. That's the
  "one or many" of the checklist: the emitter, not the machinery, decides
  the audience.
- **Skip is one line.** Anyone in the room may `skip`: cancel the pending
  wait, clear the state, and announce the cut. Because `wait()` is
  in-memory, a reboot mid-cutscene simply drops it — the correct failure
  mode for a bit of theatre.

## Build it

The projector and its script:

```text
@create holoprojector
drop holoprojector
@set holoprojector/scenes = ["The lights dim. A star map flickers to life.", "A red world turns slowly, ringed with debris.", "A voice whispers: this is Kepler's Rest, your target.", "The map collapses into darkness."]
@set holoprojector/pace = 6
```

`play` starts the chain (refusing to double-start); `scene_step` is the
self-scheduling body that shows a line and books the next:

```text
@set holoprojector/cmd_play = $play briefing:(pemit(enactor, 'The projector is already running. Type skip to cut it short.') if get_attr(me, 'pending') else (set_attr(me, 'step', 0), set_attr(me, 'pending', wait(0, 'trigger me/scene_step'))))
@set holoprojector/scene_step = lines = get_attr(me, 'scenes', []); n = get_attr(me, 'step', 0); (del_attr(me, 'pending') if n >= len(lines) else (remit(here, lines[n]), set_attr(me, 'step', n + 1), set_attr(me, 'pending', wait(get_attr(me, 'pace', 6), 'trigger me/scene_step'))))
```

`skip` — cancel the one pending wait and stop:

```text
@set holoprojector/cmd_skip = $skip:(pemit(enactor, 'Nothing is playing.') if not get_attr(me, 'pending') else (cancel_wait(get_attr(me, 'pending')), del_attr(me, 'pending'), set_attr(me, 'step', 0), remit(here, 'The projection snaps off. (skipped)')))
```

## Try it

With a friend in the room:

```text
play briefing
  The lights dim. A star map flickers to life.
  A red world turns slowly, ringed with debris.        (six seconds later)
  A voice whispers: this is Kepler's Rest, your target.
  The map collapses into darkness.
```

Both of you see every line; the projector goes quiet when the chain runs
out. Start it again and `skip` partway through — `The projection snaps
off. (skipped)` — and the remaining lines never arrive. `skip` with
nothing playing answers "Nothing is playing." (For a snappy demo or a
test, `@set holoprojector/pace = 0` and the whole reel plays as fast as the
clock is pumped.)

## Going further

- **Solo cutscenes.** Swap the `remit(here, ...)` in `scene_step` for
  `pemit(enactor, ...)` — the sequence becomes a private vision. Stash the
  viewer's id in an attr at `play` time so the chain knows who to whisper
  to.
- **Per-line pacing.** Make `scenes` a list of `[text, delay]` pairs and
  read the delay from the current line — slow reveals, quick cuts.
- **Cutscene as a quest beat.** Have the final `scene_step` call the
  [Quest Warden](198_quest_framework.md)'s `advance`, so watching the
  briefing to the end advances the mission.
- **Freeze the room.** Set a `watching` tag on viewers at `play` and have a
  movement ward hold them until the scene ends or they `skip` — a true
  cutscene lock.
- **Klaxon variant.** Point the same chain at `act(me, ..., targeting='zone')`
  and it plays zone-wide, like the self-destruct's all-call.
