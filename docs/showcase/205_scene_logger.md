# 205. Scene logger

> Checklist item 205 — [now] — *recorder ^listen + ON_EMOTE, consent attrs, $export*

**What you'll build:** an opt-in RP scene recorder — an obelisk that logs
the speech and poses of players who `join scene`, in the order they
happen, and reads the transcript back on `export`. Players who never opt
in are never recorded.

**Concepts:** the **capture idioms** (`^*` listen for speech, `ON_EMOTE`
for poses) pointed at a scene; a **consent roster** (`cast`) so recording
is opt-in and revocable; reading **`adata('pose')`** for the pose text; a
capped log and `$export`.

## How it works

The recorder is a witness, like the [voice recorder](007_voice_recorder.md)
and the [combat chronicle](120_combat_replay.md) — but consent-gated. Two
taps feed one log:

- **Speech** arrives through a `^*` listen trigger: the whole line lands as
  `arg0`, the speaker as `enactor`, `escape()`d because players write it.
- **Poses** arrive through `ON_EMOTE` — the event REALM fires for `pose`/`:`
  — and the pose's text arrives with it, as `adata('pose')`. An
  `ON_<EVENT>` witness reads the action's data, not just who set it off
  ([event bus tour](245_event_bus_tour.md)), so the recorder logs the words
  themselves. `escape()` them for the same reason speech is escaped:
  players wrote them.

Both taps therefore capture verbatim text, and the log needs no second
verb and no cooperation from the poser — `pose bows deeply.` is recorded
as it is typed.

**Consent is a roster, not a global switch.** `join scene` appends your id
to the recorder's `cast` list; `leave scene` removes it. Both taps check
`enactor.id in cast` before logging a thing, so the obelisk records only
those who opted in and stops the instant they opt out — the consent model
the checklist asks for, in one list attribute anyone can inspect
(`@examine scene recorder`).

Each row is `[now(), name, text]`, appended and sliced to the newest 100
(`[-100:]`) — unbounded logs on hot attributes are the classic MUD leak,
so every capture idiom here caps. `export` renders the rows with relative
timestamps, so the transcript reads the same live or a week later.

## Build it

The recorder and its consent verbs:

```text
@create scene recorder
drop scene recorder
@desc scene recorder = A slim obsidian obelisk. JOIN SCENE to consent to recording; LEAVE SCENE to opt out; EXPORT reads the log back.
@set scene recorder/cmd_join = $join scene:(pemit(enactor, 'You are already part of this scene.') if enactor.id in (V('cast') or []) else (set_attr(me, 'cast', (V('cast') or []) + [enactor.id]), remit(here, name(enactor) + ' steps into the scene. (now recording their poses and speech)')))
@set scene recorder/cmd_leave = $leave scene:(set_attr(me, 'cast', [c for c in (V('cast') or []) if c != enactor.id]), pemit(enactor, 'You step out of the scene.'))
```

The two taps — speech from the listen trigger's `arg0`, poses from the
event's `adata('pose')` — both verbatim, both gated on the consent roster:

```text
@set scene recorder/listen_all = ^*:set_attr(me, 'log', ((V('log') or []) + [[now(), name(enactor), 'says, "' + escape(arg0) + '"']])[-100:]) if enactor and enactor.id in (V('cast') or []) else None
@set scene recorder/on_emote = set_attr(me, 'log', ((V('log') or []) + [[now(), name(enactor), escape(adata('pose', ''))]])[-100:]) if enactor and enactor.id in (V('cast') or []) else None
```

Playback, oldest first, with ages computed at read time:

```text
@set scene recorder/cmd_export = $export:rows = V('log') or []; pemit(enactor, 'The scene is blank.') if not rows else [pemit(enactor, '[' + str(r[0] - rows[0][0]) + 's] ' + r[1] + ' ' + r[2]) for r in rows]
```

## Try it

With Ada, Ben, and Cara in the room:

```text
(Ada)  join scene              -> Ada steps into the scene. (now recording...)
(Ben)  join scene
(Ada)  say Well met, friends.
(Ben)  pose bows deeply.
(Cara) say You cannot record me.
(Ada)  say Indeed we are gathered.
(Ada)  export
  [0s] Ada says, "Well met, friends."
  [0s] Ben bows deeply.
  [0s] Ada says, "Indeed we are gathered."
```

Speech and poses alike are captured verbatim, in the order they happened —
but Cara, who never joined, appears nowhere. `leave scene` and your
subsequent lines stop landing on the log. The obelisk keeps recording the
rest of the cast either way.

The transcript is a scene, not a stage direction: nobody had to type a
special verb to be recorded properly, which is the point of an RP recorder
that gets out of the way.

## Going further

- **Separate the channels.** Log speech and poses to two attributes and
  let `export` interleave them by timestamp — the same rows, but a
  poses-only or dialogue-only reading of the same scene.
- **Scene boundaries.** `$scene start` / `$scene end` verbs that stamp
  divider rows and wipe the roster, so each session exports cleanly.
- **Owner-only export.** Gate `export` on `enactor == owner(me)` (or a
  `storyteller` tag) if transcripts are staff-eyes-only; the recording
  still runs for everyone who consented.
- **Persist to a file.** Pair with the [area export](241_yaml_responses.md)
  idiom to write finished scenes out of the game as data — an archive of
  the tale.
