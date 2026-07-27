# 85. Rich emote parser

> Checklist item 85 ([small]): *targeted emotes whose `/name` references are named correctly for each viewer*

**What you'll build:** nothing, and that is the point. `pose` already parses
`/name` references and renders each one *per viewer*, so the person you
reference reads **"you"** while everyone else reads the name **they** know that
person by. You just type the emote.

**Concepts:** the rich-emote **reference sigil** (`/`, the config value
`EMOTE_SIGIL`), per-viewer rendering through the same naming path that powers
short-descs and disguises ([133](133_short_descs.md)), and the rule that keeps
ordinary prose (`3/4`, `and/or`) safe.

## How it works

A rich emote diverges for its readers before it ever leaves the room: the same
`pose` line arrives at each person named for *that* reader, so one command
produces as many different lines as there are people watching. This section
explains where the split happens and why it is safe to use in ordinary writing.

### What a reference actually sends

A plain pose bakes one string and ships it to the whole room. A rich emote is
different. Before the line goes out, `pose` scans it for references, where a
reference is the sigil (`/` by default) glued to a name, and resolves each to
someone in the room. `pose slides the datapad to /Bob` does not send the literal
text "Bob". It sends a line with a **marker** where Bob goes, and the marker is
filled in separately for every reader.

### Why each reader sees a different name

That per-reader fill is the whole trick, and it runs through
`get_display_name(looker)`, the exact naming path [133](133_short_descs.md) uses
for the room list and speech attribution. Because a reference resolves through
it, a reference composes with everything already registered there:

- **The referenced person reads "you".** Bob, and only Bob, sees *"Ada slides
  the datapad to you."* The parser compares each reference to the reader by
  identity, so the match is exact.
- **Everyone else reads the name they know.** A viewer who has been introduced
  to a masked actor reads her real name, a stranger reads her sdesc, and someone
  fooled by a disguise reads the fake name, all in the same emote, at the same
  instant, each correct for its reader.

### Why it stays out of ordinary prose

Two rules keep references safe to use in normal writing:

- **An unmatched `/word` is left exactly as typed.** The `/4` in `3/4`, the
  `/or` in `and/or`, a bare slash: none of them resolve to a person in the room,
  so they survive untouched. A reference is opt-in by coincidence of spelling,
  and the parser never mangles prose that only looks like one.
- **Player text can't smuggle in tokens.** The body still rides the engine's
  `{speech}` slot, so typing `{actor}` in your pose prints the literal braces.
  It is not a substitution hook a player can reach.

There is **no Python and no registration** for this item. Rich emotes are a
builtin. The identity behavior they compose with is registered once by the game
(see [133](133_short_descs.md) and [134](134_disguises.md)), but the emote
parser needs nothing of its own.

## Build it

Nothing to build. Rich emotes ship enabled for every player, so there is no verb
to `@create`, no attribute to `@set`, and no resolver to register. The only
prerequisite is a scene, meaning two or more people in the same room.

For the walkthrough below the cast is **Ada** (the poser), **Bob**, and
**Cara**, all standing in the Plaza. Substitute your own players, since any two
onlookers will do. To *see* the per-viewer effect yourself you need two
connected characters, one to reference and one to watch, because each reads a
different line.

## Try it

Ada references Bob, and the two readers diverge:

```text
> pose slides the datapad to /Bob.
Bob reads:   Ada slides the datapad to you.
Cara reads:  Ada slides the datapad to Bob.
```

Bob is named "you" because Bob *is* the reference, while Cara reads the name she
knows. Reference two people in one line and each reader gets themselves as "you"
and the others by name:

```text
> pose looks from /Bob to /Cara.
Cara reads:  Ada looks from Bob to you.
```

Now prove it stays out of the way. A slash that matches no one in the room is
never touched, so fractions and either/or read literally:

```text
> pose eats 3/4 of the pie and/or leaves.
Bob reads:   Ada eats 3/4 of the pie and/or leaves.
```

A plain pose with no references behaves exactly as an ordinary pose does:

```text
> pose waves hello.
Bob reads:   Ada waves hello.
```

A reference resolves the name and leaves the grammar you glued to it alone, so
possessives just work:

```text
> pose takes /Bob's hand.
Cara reads:  Ada takes Bob's hand.
```

Everything above works through the `:` shortcut too, since `:` is `pose`, so
`:waves at /Bob.` is the same rich emote.

**It composes with disguise.** Because references render through
`get_display_name`, the moment a game registers a disguise or recognition
resolver ([133](133_short_descs.md), [134](134_disguises.md)) emotes obey it for
free. If Ada is wearing a disguise Cara cannot see through, the same emote
reaches Cara with the actor masked while the reference is still named the way
Cara knows Bob:

```text
> pose beckons to /Bob.        (Ada is disguised)
Cara reads:  a hooded figure beckons to Bob.
```

You register nothing extra here, because pointing an emote at the naming path is
automatic.

## Going further

- **Change the sigil.** `EMOTE_SIGIL` in your game config sets the reference
  character (`/` by default). Set it to `@` and emotes read `pose waves at @Bob`
  while a stray `/` becomes ordinary punctuation again. It accepts
  1–16 non-alphanumeric, non-space characters, and a bad value is rejected at
  boot rather than mid-emote, so a game whose prose is full of slashes can move
  the sigil out of the way.
- **Reference things, not just people.** The parser resolves any object in the
  room, so `pose sets the mug beside /lantern.` names the lantern the way each
  viewer perceives it, the same naming path aimed at scenery.
- **Point it at recognition.** With the [133](133_short_descs.md) resolver
  registered, `pose nods to /stranger` reads as the real name for those who have
  been introduced and as the sdesc for everyone else, in one line.
- **Layer voice on top.** A `voice_as` disguise ([84](084_voice_disguise.md))
  reskins the *attribution* while references still name their targets normally,
  so *"a distorted voice"* can still gesture at *Bob*.
