# 133. Short-descs & introductions

> Checklist item 133 ([small]): *per-viewer naming (sdesc/recog) on the `register_name_resolver` seam*

**What you'll build:** a masquerade where a stranger reads as **"a tall
woman"** until she introduces herself, after which you, and only you, see
her name. Everyone in the room can hold a different set of known and
unknown faces at the same time.

**Concepts:** the **name-resolver seam** (`register_name_resolver`), one
short native binding a game registers at deploy time, plus an in-game
`introduce` command and per-character `sdesc` and `recognized_by`
attributes. This is one of the few tutorials with a Python half, because
who counts as recognised is a game's own policy, so it lives in the
game's setup rather than in softcode a player could rewrite.

## How it works

The finished piece has two parts: one native resolver registered when the
game starts, and one admin-owned steward standing in the room that carries
an `introduce` verb. The resolver decides which name each looker sees, and
the verb records who has been introduced to whom. This section answers
three questions: where the engine asks who you appear to be, what that
question deliberately leaves alone, and why introducing yourself needs an
admin-owned object.

### How the engine decides who you appear to be

Every place the engine names a character for a viewer routes through
`get_display_name(looker)`: speech attribution, the room's occupant list,
and `look <person>` all call it. That method runs a chain of **name
resolvers**, so a game can answer "who does this person appear to be?"
without touching the engine. Registering one resolver is the whole native
half.

The resolver is short. A character carries a `sdesc` ("a tall woman") and
a `recognized_by` list of the ids who have been introduced to them. If the
looker is absent from that list, they read the sdesc; otherwise they read
the real name:

```python
# In your game's setup (config.py's on_start, or a bindings module):
from realm.core.perception import register_name_resolver

def strangers_read_by_sdesc(obj, looker, current):
    sdesc = obj.db.get('sdesc')
    if (sdesc and looker is not None and looker is not obj
            and looker.id not in (obj.db.get('recognized_by') or [])):
        return sdesc            # a stranger sees the description
    return current              # you, and those introduced, see the name

register_name_resolver(strangers_read_by_sdesc)
```

That is the whole engine side. A resolver returns the name so far or a
replacement, runs only when the looker can actually see the object, and is
skipped and logged if it raises, so a cosmetic override that breaks never
blanks a name. Everything else lives in-game.

### What the resolver does not touch

The resolver governs engine narration, and two surfaces stay truthful by
design. It does not change softcode's own
[`name(obj)`](../reference/softcode.md#fn-name), which always returns the
real name, because softcode is trusted and authoritative: a builder who
writes `name(x)` into a message wants the true name on purpose. And
`@examine` reads the raw name too. Recognition is a fiction for players,
never a wall against staff or scripts.

### Why introducing yourself needs an admin-owned object

Telling someone your name means writing *your own* `recognized_by` to
include *them*, which is a write to the introducer's own sheet. Softcode
may write a player sheet only through an object whose owner controls that
sheet, and an admin owner controls every sheet, so the steward that
carries the `introduce` verb is `@create`d by an admin. This is the same
steward pattern as [disguises](134_disguises.md) and
[voice disguise](084_voice_disguise.md). Because `introduce` is a
`$`-command verb, dispatched only to the object whose pattern matched the
typed line, it is not a room-wide `ON_<EVENT>` hook and needs no
`if target is me` guard.

## Build it

A room to gather in, and the steward that carries the verb. `@teleport`
positions the builder, and dropping the steward makes its verb reachable
from the room:

```text
@dig The Masquerade
@teleport The Masquerade
@create introductions steward
drop introductions steward
```

`$introduce` takes the person to introduce yourself to as `arg0`. It
resolves that name with [`get`](../reference/softcode.md#fn-get) and
confirms it is a player with
[`has_tag`](../reference/softcode.md#fn-has_tag), then reads the
introducer's current `recognized_by` with
[`get_attr`](../reference/softcode.md#fn-get_attr), adds the target's id
with [`set_attr`](../reference/softcode.md#fn-set_attr) if it is not
already there, and tells both sides with
[`pemit`](../reference/softcode.md#fn-pemit). The control flow makes this a
`'''` multi-line block:

```text
@set introductions steward/cmd_introduce = '''
$introduce *:
who = get(arg0)
if not who or not has_tag(who, 'player'):
    pemit(enactor, 'No one here by that name.')
else:
    rec = get_attr(enactor, 'recognized_by', []) or []   # ids that read enactor by name
    if who.id not in rec:
        set_attr(enactor, 'recognized_by', rec + [who.id])
    pemit(enactor, 'You give your name. ' + name(who) + ' will know you now.')
    pemit(who, name(enactor) + ' introduces themselves to you.')
'''
```

Note the direction of the write: the introducer stamps their *own*
`recognized_by` with the listener's id, so the resolver later reads the
introducer by name for that one listener. `name(who)` and `name(enactor)`
return the true names on purpose, since the whole point of the message is
to hand over a real name.

## Try it

Give two players sdescs (a builder does this here; chargen would normally),
then watch the room from each side:

```text
> @set Ada/sdesc = a tall woman in a domino mask
Attribute set.
> @set Bran/sdesc = a stout man in a feathered hat
Attribute set.
```

Now, as **Bran**, look. Ada is a stranger:

```text
> look
Players here:
  a tall woman in a domino mask
  Bran
```

Ada speaks, and Bran still reads the mask, because speech attribution runs
through the same resolver:

```text
(Ada)  say Care to dance?
(Bran hears)  a tall woman in a domino mask says, "Care to dance?"
```

Ada introduces herself to Bran, and to Bran alone:

```text
(Ada)  introduce Bran
You give your name. Bran will know you now.
(Bran sees)  Ada introduces themselves to you.
```

From now on Bran reads her name, while anyone else in the hall still sees
the mask:

```text
(Bran)  look
Players here:
  Ada
  Bran
(Ada)  say Shall we?
(Bran hears)  Ada says, "Shall we?"
```

Her voice was carried by the same seam the whole time, so introductions
covered her speech with no extra work.

## Going further

- **Recognise, not only introduce.** A `$recognise * as *` verb for staff
  (or for a character with the Acquaintance advantage) writes the name a
  viewer *chooses* to file someone under, the recog half of a full
  rpsystem.
- **Whole-room introduction.** `introduce` with no argument adds everyone
  currently present to your `recognized_by`, so you walk into a tavern and
  announce yourself to the whole room at once.
- **Global desk.** Put the steward in a `zone:world` room and tag it a
  zone master so `introduce` works anywhere, not just this hall.
- **Compose with disguise.** Register the [disguise](134_disguises.md)
  resolver too. Resolvers run in order, so an assumed name overrides a
  known one, which means a friend you have been introduced to still fools
  you while masked.
