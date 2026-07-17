# 84. Voice disguise

> Checklist item 84 — [small] — *speech-attribution override via the `db.voice_as` convention*

**What you'll build:** a signal booth with a voice modulator. Step up,
`modulate` your voice, and the room hears **"a distorted voice says,"** —
but a `look` still shows your real face and name. It is the exact inverse
of a [disguise](134_disguises.md): that hides the face and lets the voice
carry it; this hides the voice and leaves the face plain. Together they're
the two halves of concealment.

**Concepts:** the **`db.voice_as` convention** — no seam to register, no
native half at all. An actor carrying a `voice_as` attribute is
*attributed* by that name in speech (and only speech), for every listener
but themselves. Plus an admin-owned modulator with `$modulate` / `$clear`
verbs that set and clear it.

## How it works

REALM already routes the spoken body of a `say`/`pose`/`whisper`/`shout`
per listener — that's the seam languages and slurring ride on (see
[architecture/events.md](../architecture/events.md)). Voice disguise uses
a narrower door in the same pathway: when the engine formats the `{actor}`
of a **speech** action, it checks the speaker for a `voice_as` attribute
and, if present, substitutes that string as the speaker's name — for
every recipient except the speaker, who always hears their own true
attribution.

That's the whole mechanism, and it needs **no Python** — `voice_as` is a
plain attribute the engine looks for. This is the deliberate contrast with
a [disguise](134_disguises.md), which changes `get_display_name`
*everywhere* and so needs a registered name resolver. `voice_as` touches
only the `{actor}` of a speech line:

```
Dex.db.voice_as = "a distorted voice"
Dex: say who goes there
  Edda hears:  a distorted voice says, "who goes there"
  Dex hears:   You say, "who goes there"
  Edda's look still lists:  Dex          # the face is untouched
```

So a modulator hides a voice while the face stays known; a mask hides the
face while the voice gives you away. Pick the door the fiction needs.

**Setting another player's attribute needs authority.** `$modulate`
writes `voice_as` onto the person who used the booth, and softcode may
write a player sheet only through an admin-owned object — so the modulator
is `@create`d by an admin, the same steward pattern as
[133](133_short_descs.md) and [134](134_disguises.md).

## Build it

A booth and the modulator master:

```text
@dig The Signal Booth
@teleport The Signal Booth
@create voice modulator
drop voice modulator
```

`$modulate` sets the alias voice; `$clear` removes it. Note what these
verbs *don't* touch — no `disguise`, no name resolver, nothing that
`look` reads:

```text
@set voice modulator/cmd_modulate = $modulate *: (pemit(enactor, 'Modulate to what voice? Name it.') if not arg0 else (set_attr(enactor, 'voice_as', arg0), pemit(enactor, 'The modulator hums. You are HEARD as ' + arg0 + ' now, though your face is unchanged.')))
@set voice modulator/cmd_clear = $clear: (del_attr(enactor, 'voice_as'), pemit(enactor, 'The modulator powers down. Your own voice again.'))
```

## Try it

As **Dex**, modulate, then speak:

```text
modulate a distorted voice
    The modulator hums. You are HEARD as a distorted voice now, though your face is unchanged.
say Identify yourself.
```

Everyone else in the booth hears the alias, but you hear your own words as
your own:

```text
(Edda hears)  a distorted voice says, "Identify yourself."
(Dex hears)   You say, "Identify yourself."
```

Now the point of the whole item — the face is untouched. Edda looks and
still sees Dex by name, right there in the room:

```text
(Edda)  look
    Players here:
      Dex
      Edda
```

Power it down and your voice is yours again:

```text
(Dex)  clear
    The modulator powers down. Your own voice again.
(Dex)  say It's me.
(Edda hears)  Dex says, "It's me."
```

## Going further

- **A personal, wielded gadget.** Instead of a booth, make the modulator a
  small device the character owns and carries. Because an owned object
  acts with its owner's authority, a player-owned gadget can set its
  owner's `voice_as` with no admin in sight — `$modulate` works only for
  the person holding their own device.
- **Both halves at once.** Wear a [disguise](134_disguises.md) *and*
  modulate — the room sees a masked courier and hears a distorted voice,
  two independent concealments a watcher must break separately.
- **Voice on a timer.** Set `voice_as` for a scene, then `expire()` it so
  the modulation drops after N seconds — a battery that runs down mid-
  conversation.
- **Give it away in a whisper.** `voice_as` covers whispers and shouts
  too, so a leaked fragment overheard by a bystander (item 80) still
  arrives under the false name — the modulation follows the voice wherever
  it carries.
