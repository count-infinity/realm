# 205. Scene logger

> Checklist item 205 ([now]): *opt-in RP scene recording, recorder `^listen` + `ON_EMOTE`, consent attrs, `$export`*

**What you'll build:** an opt-in roleplay scene recorder. An obelisk logs the
speech and the poses of players who type `join scene`, in the order they
happen, and reads the transcript back on `export`. Players who never opt in are
never recorded.

**Concepts:** the two capture taps (a
[`^pattern:` listen trigger](../reference/softcode.md#triggers-attributes-on-objects)
for overheard lines and [`ON_EMOTE`](../reference/softcode.md#lifecycle-hooks)
for poses) pointed at one room, a consent roster held in a `cast` list
attribute, [`adata('pose')`](../reference/softcode.md#event-data-namespace) for
the pose text, [`escape()`](../reference/softcode.md#fn-escape) over
player-authored words, the capped-log append idiom, and a `$export` playback
command.

## How it works

The finished obelisk is one object carrying five attributes: two capture taps
that append rows to a `log` list, two verbs that add and remove ids from a
`cast` list, and a playback verb that prints the log. Nothing else in the room
has to cooperate, because both taps read text the engine already carries. This
section answers three questions: how each tap hears its half of the scene, how
consent decides what gets written, and why the log has a hard ceiling.

### How the recorder hears speech and poses

REALM carries speech and poses on two different rails, so the recorder needs
one tap for each.

Overheard lines arrive through a **listen trigger**, an attribute named
`listen_*` whose value is `^pattern:` followed by code. The pattern `^*`
matches every line, the whole line arrives as `arg0`, and the speaker is bound
as `enactor`, exactly as on the [voice recorder](007_voice_recorder.md). The
engine feeds a listen trigger four action types and no others: `say`, `shout`,
`ooc`, and `emit`. A `whisper` is deliberately excluded, because a bystander
only ever sees the vague "X whispers something to Y" line, so a script gets no
more than a person would. Combat narration is not on that list either, which is
why the [combat chronicle](120_combat_replay.md) reaches for `ON_ATTACK` and
`ON_DAMAGE` instead of a microphone.

Poses arrive through [`ON_EMOTE`](../reference/softcode.md#lifecycle-hooks),
which is the event that `pose` and its `:` alias propagate, and the pose text
rides along in the action's payload as
[`adata('pose')`](../reference/softcode.md#event-data-namespace). Reading the
payload rather than merely noting who acted is what makes the recorder useful
([event bus tour](245_event_bus_tour.md)): the log keeps the words themselves,
so `pose bows deeply.` is stored as `bows deeply.` with no cooperation from the
poser. Note that the semipose alias `;` propagates `event:semipose` instead and
lands on `ON_SEMIPOSE`, so add that hook too if your players use it.

Both taps run [`escape()`](../reference/softcode.md#fn-escape) over the captured
text, since players author it and their color markup belongs in the transcript
as characters rather than as instructions to the renderer.

### Why neither tap guards on `target`

An [`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook fires on every
object standing in the room, not only the one an action was aimed at, so most
hooks open with `if target is me:` to tell "this happened to me" from "this
happened near me" (see
[Guard on `target`](../reference/softcode.md#guard-on-target)). A scene
recorder is the deliberate exception named there: it *wants* the whole room's
traffic, so a target guard would silence it. Put two recorders in one room and
both log the same line, each against its own roster, which is the behavior a
global witness should have.

The taps do check `if enactor and ...` before reading the roster, because a
sourceless emit reaches a listen trigger with no speaker bound and `enactor` is
`None` there. The three `$`-commands need neither check, since a `$`-command
runs only for the person who typed it, with that person always bound as
`enactor`.

### How consent decides what is written

Consent is a roster rather than a global switch. `join scene` appends your id
to the recorder's `cast` list and `leave scene` filters it back out, so both
taps ask `enactor.id in cast` before writing anything. Recording therefore
starts and stops per person, at the moment they ask, and everyone else in the
room carries on unrecorded. The roster is an ordinary list attribute, so any
player can read it back with `examine scene recorder`, and a builder gets the
same view from `@examine`.

Each row is `[now(), name, text]`, and the append slices the list to its newest
100 with `(old + [row])[-100:]`, which is the whole capped-log idiom: read the
old list, add one row, keep the tail, write it back in a single
[`set_attr`](../reference/softcode.md#fn-set_attr). An unbounded list on a hot
attribute is the classic MUD database leak, so every capture idiom in the
showcase caps the same way the [bank](087_bank_accounts.md) caps its audit log.
Playback subtracts the first row's timestamp from each row, which prints ages
in seconds and makes the transcript read the same live or a week later.

## Build it

Every script below is a `'''` multi-line block: end the `@set` line with a
trailing `'''`, write the body as ordinary indented softcode, and close with a
line of just `'''` (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

Create the obelisk and stand it in the room, with a description that names its
three verbs so a player who walks in knows the terms:

```text
@create scene recorder
drop scene recorder
@desc scene recorder = A slim obsidian obelisk. JOIN SCENE to consent to recording; LEAVE SCENE to opt out; EXPORT reads the log back.
```

Now the consent verbs. `$join scene` reads the roster with
[`V`](../reference/softcode.md#fn-v) (shorthand for
`get_attr(me, 'cast', ...)`), refuses a second helping to someone already on
it, and otherwise appends the joiner's id and tells the room with
[`remit`](../reference/softcode.md#fn-remit), so consent is public rather than
silent:

```text
@set scene recorder/cmd_join = '''
$join scene:
cast = V('cast') or []
if enactor.id in cast:
    pemit(enactor, 'You are already part of this scene.')
else:
    set_attr(me, 'cast', cast + [enactor.id])
    remit(here, name(enactor) + ' steps into the scene. (now recording their poses and speech)')
'''
```

`$leave scene` rebuilds the roster without the leaver, which is one
comprehension and stays correct whether or not they were on it. The
acknowledgement goes back with [`pemit`](../reference/softcode.md#fn-pemit),
since leaving quietly is the point:

```text
@set scene recorder/cmd_leave = '''
$leave scene:
set_attr(me, 'cast', [c for c in (V('cast') or []) if c != enactor.id])
pemit(enactor, 'You step out of the scene.')
'''
```

The speech tap is the listen trigger. `^*` matches every overheard line, the
line itself is `arg0`, [`name`](../reference/softcode.md#fn-name) resolves the
speaker, [`now`](../reference/softcode.md#fn-now) stamps the row, and the
append is immediately sliced to the newest 100. The row template writes every
overheard line as `says, "..."`, so a `shout` or an `ooc` line reads as speech
in the transcript; branch on
[`atype`](../reference/softcode.md#event-data-namespace) inside the tap if you
want them labelled separately:

```text
@set scene recorder/listen_all = '''
^*:
if enactor and enactor.id in (V('cast') or []):
    row = [now(), name(enactor), 'says, "' + escape(arg0) + '"']
    set_attr(me, 'log', ((V('log') or []) + [row])[-100:])
'''
```

The pose tap is the same shape with a different source: `ON_EMOTE` carries the
pose text in its payload, so `adata('pose', '')` is the whole row. There is no
`if target is me:` here on purpose, since this witness records the whole room:

```text
@set scene recorder/on_emote = '''
if enactor and enactor.id in (V('cast') or []):
    # No target guard: a scene recorder wants every pose in the room, not
    # only poses aimed at the obelisk.
    row = [now(), name(enactor), escape(adata('pose', ''))]
    set_attr(me, 'log', ((V('log') or []) + [row])[-100:])
'''
```

Playback runs oldest first and dates each line against the first row, so the
ages are computed at read time rather than baked in when the row was written:

```text
@set scene recorder/cmd_export = '''
$export:
rows = V('log') or []
if not rows:
    pemit(enactor, 'The scene is blank.')
for r in rows:
    pemit(enactor, '[' + str(r[0] - rows[0][0]) + 's] ' + r[1] + ' ' + r[2])
'''
```

## Try it

Stand Ada, Ben, and Cara in the room with the obelisk. Ada and Ben opt in and
Cara never does. Each block below shows what the person typing it sees, so
`say` comes back as "You say" to its own speaker:

```text
(Ada) > join scene
Ada steps into the scene. (now recording their poses and speech)

(Ben) > join scene
Ben steps into the scene. (now recording their poses and speech)

(Ada) > say Well met, friends.
You say, "Well met, friends."

(Ben) > pose bows deeply.
Ben bows deeply.

(Cara) > say You cannot record me.
You say, "You cannot record me."

(Ada) > say Indeed we are gathered.
You say, "Indeed we are gathered."
```

Everyone in the room witnessed all four lines, and only three of them were
written down. Read the transcript back:

```text
(Ada) > export
[0s] Ada says, "Well met, friends."
[0s] Ben bows deeply.
[0s] Ada says, "Indeed we are gathered."
```

Two results are worth confirming deliberately. Cara appears nowhere, because
her id was never on the roster. Ben's pose reads as he typed it, because
`ON_EMOTE` handed the recorder the words rather than just the fact that Ben
posed. The `[0s]` figures are ages relative to the first row, so a scene
replayed an hour later opens at `[0s]` and counts up from there.

Opting out takes effect on the next line:

```text
(Ada) > leave scene
You step out of the scene.

(Ada) > say off the record now.
You say, "off the record now."

(Ada) > export
[0s] Ada says, "Well met, friends."
[0s] Ben bows deeply.
[0s] Ada says, "Indeed we are gathered."
```

Ada's last line is absent while Ben, still on the roster, keeps being recorded.
An empty log answers `The scene is blank.` rather than printing nothing, and
`examine scene recorder` shows the `cast` list to anyone who asks, so a player
can always check whether they are being recorded.

## Going further

- **Separate the channels.** Log speech and poses to two attributes and let
  `export` interleave them by timestamp, which gives you a poses-only or
  dialogue-only reading of the same scene.
- **Scene boundaries.** Add `$scene start` and `$scene end` verbs that stamp
  divider rows and wipe the roster, so each session exports cleanly.
- **Owner-only export.** Gate `export` on `enactor is owner(me)` (or on a
  `storyteller` tag) when transcripts are staff-eyes-only. Recording still runs
  for everyone who consented.
- **One obelisk per room.** A `$`-command runs on the first object in the room
  that matches it, so a second recorder standing beside the first receives no
  `join scene` of its own even though both taps still hear everything. Give the
  spare its own verb names, or keep one recorder per room.
- **Persist to a file.** Pair with the [area export](241_yaml_responses.md)
  idiom to write finished scenes out of the game as data.
