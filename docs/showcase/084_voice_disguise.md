# 84. Voice disguise

> Checklist item 84 ([small]): *speech-attribution override via the `db.voice_as` convention*

**What you'll build:** a signal booth with a voice modulator. Step up,
`modulate` your voice, and the room hears **"a distorted voice says,"**,
yet a `look` still shows your real face and name. It is the exact inverse
of a [disguise](134_disguises.md): that build hides the face and lets the
voice carry it, while this one hides the voice and leaves the face plain.
Together they are the two halves of concealment.

**Concepts:** the **`db.voice_as` convention**. There is no seam to
register and no native half at all. An actor carrying a `voice_as`
attribute is *attributed* by that name in speech (and only in speech), for
every listener but themselves. On top of that sits an admin-owned
modulator with `$modulate` and `$clear` verbs that set and clear the
attribute.

## How it works

The finished device is one admin-owned object standing in a booth. A
player who runs its `modulate` verb picks up a `voice_as` attribute, and
from then on the room hears an alias whenever that player speaks, while
every other engine surface (the occupant list, `look`, `@examine`) still
reads the true name. This section answers two questions: where the engine
reads `voice_as`, and why setting it on the player needs an admin-owned
object.

### Where the engine reads the alias

REALM already routes the spoken body of a `say`, `pose`, `whisper`, or
`shout` per listener, which is the pathway that languages and slurring
ride on (see [architecture/events.md](../architecture/events.md)). Voice
disguise uses a narrower door in that same pathway. When the engine
formats the `{actor}` of a **speech** action, it checks the speaker for a
`voice_as` attribute, and if one is present it substitutes that string as
the speaker's name for every recipient except the speaker. The speaker
always hears their own true attribution.

That is the whole mechanism, and it needs **no Python**, because
`voice_as` is a plain attribute the engine looks for. This is the
deliberate contrast with a [disguise](134_disguises.md), which changes
`get_display_name` *everywhere* and so needs a registered name resolver.
`voice_as` touches only the `{actor}` token of a speech line:

```
Dex.db.voice_as = "a distorted voice"
Dex: say who goes there
  Edda hears:  a distorted voice says, "who goes there"
  Dex hears:   You say, "who goes there"
  Edda's look still lists:  Dex          # the face is untouched
```

So a modulator hides a voice while the face stays known, and a mask hides
the face while the voice gives you away. Pick the door the fiction needs.
The two compose cleanly: wear both and speech shows the `voice_as` alias
while `look` shows the disguise, two independent concealments a watcher
must break separately.

### Why setting another player's attribute needs authority

`$modulate` writes `voice_as` onto the person who used the booth, and
softcode may write a player sheet only through an object whose owner
controls that sheet. An admin owner controls every sheet, so the modulator
is `@create`d by an admin, the same steward pattern as
[133](133_short_descs.md) and [134](134_disguises.md). The verbs here are
`$`-command verbs, dispatched only to the object whose pattern matched the
typed line, so they are not room-wide `ON_<EVENT>` hooks and need no
`if target is me` guard.

## Build it

Start with the booth and the modulator. `@teleport` positions the builder,
and the two commands below create the master and drop it so its verbs are
reachable from the room:

```text
@dig The Signal Booth
@teleport The Signal Booth
@create voice modulator
drop voice modulator
```

`$modulate` takes the alias voice as `arg0`. When the caller names one, it
stamps `voice_as` on them with
[`set_attr`](../reference/softcode.md#fn-set_attr) and confirms with
[`pemit`](../reference/softcode.md#fn-pemit); when they name nothing, it
prompts. Note what it does not touch: no disguise, no name resolver,
nothing `look` reads.

```text
@set voice modulator/cmd_modulate = '''
$modulate *:
if not arg0:
    pemit(enactor, 'Modulate to what voice? Name it.')
else:
    set_attr(enactor, 'voice_as', arg0)  # admin-owned booth writes the user's own sheet under owner authority
    pemit(enactor, 'The modulator hums. You are HEARD as ' + arg0 + ' now, though your face is unchanged.')
'''
```

`$clear` removes the attribute with
[`del_attr`](../reference/softcode.md#fn-del_attr), which drops the alias
so the next spoken line carries the real name again:

```text
@set voice modulator/cmd_clear = '''
$clear:
del_attr(enactor, 'voice_as')  # does not touch look or the room list; those never read voice_as
pemit(enactor, 'The modulator powers down. Your own voice again.')
'''
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

Now the point of the whole item: the face is untouched. Edda looks and
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
(Dex)  say It is me.
(Edda hears)  Dex says, "It is me."
```

## Going further

- **A personal, wielded gadget.** Instead of a booth, make the modulator a
  small device the character owns and carries. Because an owned object acts
  with its owner's authority, a player-owned gadget can set its owner's
  `voice_as` with no admin in sight, so `$modulate` works only for the
  person holding their own device.
- **Both halves at once.** Wear a [disguise](134_disguises.md) *and*
  modulate. The room sees a masked courier and hears a distorted voice, two
  independent concealments a watcher must break separately.
- **Voice on a timer.** Set `voice_as` for a scene, then
  [`expire()`](../reference/softcode.md#fn-expire) it so the modulation
  drops after N seconds, a battery that runs down mid-conversation.
- **Give it away in a whisper.** `voice_as` covers whispers and shouts too,
  so a leaked fragment overheard by a bystander (item 80) still arrives
  under the false name. The modulation follows the voice wherever it
  carries.
