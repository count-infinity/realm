# 133. Short-descs & introductions

> Checklist item 133 — [small] — *per-viewer naming (sdesc/recog) on the `register_name_resolver` seam*

**What you'll build:** a masquerade where a stranger reads as **"a tall
woman"** until she introduces herself — after which you, and only you,
see her name. Everyone in the room can be a different set of "known" and
"unknown" faces at the same time.

**Concepts:** the **name-resolver seam** (`register_name_resolver`) — one
short native binding a game registers at deploy time — plus an in-game
`introduce` command and per-character `sdesc` / `recognized_by`
attributes. This is one of the few tutorials with a Python half: *who
counts as recognised* is a game's own policy, so it lives in the game's
setup, not in softcode a player could rewrite.

## How it works

Every place the engine names a character for a viewer — speech
attribution, the room's "Players here" list, `look <person>` — goes
through `get_display_name(looker)`. That function runs a chain of
**name resolvers**, so a game can decide "who does this person appear to
be?" without touching the engine.

The resolver is eight lines. A character carries a `sdesc` ("a tall
woman") and a `recognized_by` list of the ids who've been introduced to
them. If the looker isn't on that list, they read the sdesc; otherwise
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

That's the whole engine side. Everything else is in-game.

**Two honest boundaries.** The resolver governs *engine* narration; it
does **not** touch softcode's own `name(obj)`, which always returns the
true name — softcode is trusted and authoritative, so a builder who
writes `name(x)` into a message gets the real name on purpose. And
`@examine` shows the truth too. Recognition is a fiction for players, not
a wall against staff or scripts.

**Introductions are an admin-owned command.** Telling someone your name
means writing *your* `recognized_by` to include *them* — a write to the
introducer's own sheet, which softcode may do only through an admin-owned
object's authority. So the steward that carries the `$introduce` verb is
`@create`d by an admin.

## Build it

The room, and characters with descriptions the unacquainted will see:

```text
@dig The Masquerade
@teleport The Masquerade
@create introductions steward
@tag introductions steward = npc
drop introductions steward
@set introductions steward/cmd_introduce = $introduce *: who = get(arg0); rec = V('_') and [] or (get_attr(enactor, 'recognized_by', []) or []); (pemit(enactor, 'No one here by that name.') if not who or not has_tag(who, 'player') else (set_attr(enactor, 'recognized_by', rec + [who.id]) if who.id not in rec else None, pemit(enactor, 'You give your name. ' + name(who) + ' will know you now.'), pemit(who, name(enactor) + ' introduces themselves to you.')))
```

The steward is `npc`-tagged only so `get('introductions steward')` and
friends resolve it cleanly; its authority comes from its admin owner. The
`V('_') and [] or ...` is the one-line way to bind `rec` before the
guard chain uses it.

## Try it

Give two players sdescs (a builder does this; chargen would normally),
then watch the room from each side:

```text
@set Ada/sdesc = a tall woman in a domino mask
@set Bran/sdesc = a stout man in a feathered hat
```

Now, as **Bran**, look — Ada is a stranger:

```text
look
    Players here:
      a tall woman in a domino mask
      Bran
```

Ada speaks; Bran still doesn't know her:

```text
(Ada)  say Care to dance?
(Bran hears)  a tall woman in a domino mask says, "Care to dance?"
```

Ada introduces herself to Bran — and only Bran:

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

Her voice was covered by the same seam the whole time — attribution runs
through `get_display_name`, so introductions cover speech for free.

## Going further

- **Recognise, don't just introduce.** A `$recognise * as *` verb for
  staff (or for a character with the Acquaintance advantage) writes the
  name a viewer *chooses* to file someone under — the recog half of a
  full rpsystem.
- **Whole-room introduction.** `introduce` with no argument adds everyone
  currently present to your `recognized_by` — walking into a tavern and
  announcing yourself.
- **Global desk.** Put the steward in a `zone:world` room and tag it a
  zone master so `introduce` works anywhere, not just this hall.
- **Compose with disguise.** Register the [disguise](134_disguises.md)
  resolver too; resolvers run in order, so an assumed name overrides a
  known one — a friend you've been introduced to still fools you while
  masked.
