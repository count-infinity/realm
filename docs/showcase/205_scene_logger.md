# 205. Scene logger

> Checklist item 205 — [now] — *recorder ^listen + ON_EMOTE, consent attrs, $export*

**What you'll build:** an opt-in RP scene recorder — an obelisk that logs
the speech and poses of players who `join scene`, in the order they
happen, and reads the transcript back on `export`. Players who never opt
in are never recorded.

**Concepts:** the **capture idioms** (`^*` listen for speech, `ON_EMOTE`
for poses) pointed at a scene; a **consent roster** (`cast`) so recording
is opt-in and revocable; **pose-order tracking** via timestamped rows; the
honest **payload limit** on pose text; a capped log and `$export`.

## How it works

The recorder is a witness, like the [voice recorder](007_voice_recorder.md)
and the [combat chronicle](120_combat_replay.md) — but consent-gated. Two
taps feed one log:

- **Speech** arrives through a `^*` listen trigger: the whole line lands as
  `arg0`, the speaker as `enactor`, `escape()`d because players write it.
- **Poses** arrive through `ON_EMOTE` — the event REALM fires for `pose`/`:`.
  This is where the honesty comes in: **an event trigger gets only
  `enactor`, never the pose's text** (the same payload gap the combat
  chronicle documents). So the recorder can log *that* a consenting player
  posed, and exactly *when* in the sequence — preserving pose order — but
  not the words. The row reads `(emotes -- pose text is not exposed to
  witnesses)`; full pose capture needs the workaround in "Going further".

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
@set scene recorder/cmd_join = $join scene:(pemit(enactor, 'You are already part of this scene.') if enactor.id in (get_attr(me, 'cast') or []) else (set_attr(me, 'cast', (get_attr(me, 'cast') or []) + [enactor.id]), remit(here, name(enactor) + ' steps into the scene. (now recording their poses and speech)')))
@set scene recorder/cmd_leave = $leave scene:(set_attr(me, 'cast', [c for c in (get_attr(me, 'cast') or []) if c != enactor.id]), pemit(enactor, 'You step out of the scene.'))
```

The two taps — speech verbatim, poses as ordered markers — both gated on
the consent roster:

```text
@set scene recorder/listen_all = ^*:set_attr(me, 'log', ((get_attr(me, 'log') or []) + [[now(), name(enactor), 'says, "' + escape(arg0) + '"']])[-100:]) if enactor and enactor.id in (get_attr(me, 'cast') or []) else None
@set scene recorder/on_emote = set_attr(me, 'log', ((get_attr(me, 'log') or []) + [[now(), name(enactor), '(emotes -- pose text is not exposed to witnesses)']])[-100:]) if enactor and enactor.id in (get_attr(me, 'cast') or []) else None
```

Playback, oldest first, with ages computed at read time:

```text
@set scene recorder/cmd_export = $export:rows = get_attr(me, 'log') or []; pemit(enactor, 'The scene is blank.') if not rows else [pemit(enactor, '[' + str(r[0] - rows[0][0]) + 's] ' + r[1] + ' ' + r[2]) for r in rows]
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
  [0s] Ben (emotes -- pose text is not exposed to witnesses)
  [0s] Ada says, "Indeed we are gathered."
```

Ada's lines are captured verbatim and Ben's pose holds its place in the
order — but Cara, who never joined, appears nowhere. `leave scene` and
your subsequent lines stop landing on the log. The obelisk keeps recording
the rest of the cast either way.

**Limit, stated once:** poses log their *order* and author but not their
text, because REALM's `ON_<EVENT>` witnesses receive no action payload
(item 120's note). The workaround below captures full pose text at the cost
of a dedicated verb.

## Going further

- **Full-fidelity poses.** Add a `$rp *` verb — `remit(here, name(enactor)
  + ' ' + arg0)` plus the same log append with `arg0` as the text. Players
  who type `rp bows deeply` get their pose *and* a verbatim log entry;
  consent still gates it. This is the honest way to record pose words while
  the payload gap stands.
- **Scene boundaries.** `$scene start` / `$scene end` verbs that stamp
  divider rows and wipe the roster, so each session exports cleanly.
- **Owner-only export.** Gate `export` on `enactor == owner(me)` (or a
  `storyteller` tag) if transcripts are staff-eyes-only; the recording
  still runs for everyone who consented.
- **Persist to a file.** Pair with the [area export](241_yaml_responses.md)
  idiom to write finished scenes out of the game as data — an archive of
  the tale.
