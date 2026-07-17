# 85. Rich emote parser

> Checklist item 85 — [small] — *targeted emotes whose `/name` references
> are named correctly for each viewer*

**What you'll build:** nothing — that's the point. `pose` already parses
`/name` references and renders each one *per viewer*: the person you
reference reads **"you"**, everyone else reads the name **they** know that
person by. You just type the emote.

**Concepts:** the rich-emote **reference sigil** (`/`, the config value
`EMOTE_SIGIL`), per-viewer rendering through the same **identity seam**
that powers short-descs and disguises ([133](133_short_descs.md)), and the
rule that keeps ordinary prose (`3/4`, `and/or`) safe.

## How it works

A plain pose bakes one string and ships it to the whole room. A *rich*
emote is different: before the line goes out, `pose` scans it for
references — a sigil (`/` by default) glued to a name — and resolves each
to someone in the room. `pose slides the datapad to /Bob` doesn't send the
literal text "Bob"; it sends a line with a **marker** where Bob goes, and
the marker is filled in separately for every reader.

That per-reader fill is the whole trick, and it runs through
`get_display_name(looker)` — the exact seam [133](133_short_descs.md) uses
for the room list and speech attribution. So a reference composes with
everything already registered there:

- **The referenced person reads "you".** Bob, and only Bob, sees *"Ada
  slides the datapad to you."*
- **Everyone else reads the name they know.** A viewer who has been
  introduced to a masked actor reads her real name; a stranger reads her
  sdesc; someone fooled by a disguise reads the fake name — all in the
  same emote, at the same instant, each correct for its reader.

Two things make it safe to use in normal writing:

- **An unmatched `/word` is left exactly as typed.** `/4` in `3/4`, `/or`
  in `and/or`, a bare slash — none of them resolve to a person in the
  room, so they survive untouched. References are opt-in by coincidence of
  spelling, never by mangling your prose.
- **Player text can't smuggle in tokens.** The body still rides the
  engine's `{speech}` slot, so typing `{actor}` in your pose prints the
  literal braces — it is not a substitution hook a player can reach.

There is **no Python and no registration** for this item. Rich emotes are
a builtin; the identity behavior they compose with is registered once by
the game (see 133/134), but the emote parser needs nothing of its own.

## Build it

Nothing to build. Rich emotes ship enabled for every player — there is no
verb to `@create`, no attribute to `@set`, no resolver to register. The
only prerequisite is a scene: **two or more people in the same room.**

For the walkthrough below the cast is **Ada** (the poser), **Bob**, and
**Cara**, all standing in the Plaza. Substitute your own players; any two
onlookers will do. If you want to *see* the per-viewer effect yourself,
you need two connected characters — one to reference, one to watch — since
each reads a different line.

## Try it

Ada references Bob. Watch the two readers diverge:

```text
(Ada)  pose slides the datapad to /Bob.
(Bob reads)   Ada slides the datapad to you.
(Cara reads)  Ada slides the datapad to Bob.
```

Bob is named "you" because Bob *is* the reference; Cara reads the name she
knows. Reference two people in one line and each reader gets themselves as
"you" and the others by name:

```text
(Ada)  pose looks from /Bob to /Cara.
(Cara reads)  Ada looks from Bob to you.
```

Now prove it stays out of the way. A slash that matches no one in the room
is never touched, so fractions and either/or read literally:

```text
(Ada)  pose eats 3/4 of the pie and/or leaves.
(Bob reads)   Ada eats 3/4 of the pie and/or leaves.
```

A plain pose with no references behaves exactly as it always did:

```text
(Ada)  pose waves hello.
(Bob reads)   Ada waves hello.
```

A reference resolves the name and leaves the grammar you glued to it
alone, so possessives just work:

```text
(Ada)  pose takes /Bob's hand.
(Cara reads)  Ada takes Bob's hand.
```

Everything above works through the `:` shortcut too — `:` is `pose` — so
`:waves at /Bob.` is the same rich emote.

**It composes with disguise.** Because references render through
`get_display_name`, the moment a game registers a disguise or recognition
resolver ([133](133_short_descs.md), [134](134_disguises.md)) emotes obey
it for free. If Ada is wearing a disguise Cara can't see through, the same
emote reaches Cara with the actor masked and the reference still named the
way Cara knows Bob:

```text
(Ada, disguised)  pose beckons to /Bob.
(Cara reads)      a hooded figure beckons to Bob.
```

You register nothing extra here; pointing an emote at the identity seam is
automatic.

## Going further

- **Change the sigil.** `EMOTE_SIGIL` in your game config sets the
  reference character (`/` by default). Set it to `@` and emotes read
  `pose waves at @Bob` while a stray `/` becomes ordinary punctuation
  again. It accepts 1–16 non-alphanumeric, non-space characters, and a
  bad value is rejected at boot rather than mid-emote — so a game whose
  prose is full of slashes can move the sigil out of the way.
- **Reference things, not just people.** The parser resolves any object in
  the room, so `pose sets the mug beside /lantern.` names the lantern the
  way each viewer perceives it — the same seam, aimed at scenery.
- **Point it at recognition.** With the [133](133_short_descs.md) resolver
  registered, `pose nods to /stranger` reads as the real name for those
  who've been introduced and as the sdesc for everyone else, in one line.
- **Layer voice on top.** A `voice_as` disguise ([84](084_voice_disguise.md))
  reskins the *attribution* while references still name their targets
  normally — so *"a distorted voice"* can still gesture at *Bob*.
