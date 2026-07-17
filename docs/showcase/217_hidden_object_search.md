# 217. Hidden object search

> Checklist item 217 — now — *concealed tags, the search command, Observation vs conceal_difficulty*

**What you'll build:** A study salted with hidden things — a key in the
dust, a ledger behind a false book, a wall cache flush with the plaster —
each harder to spot than the last. `search` rolls the seeker's
Observation against each hiding place; sharp eyes turn up the easy finds,
a real expert turns up everything.

**Concepts:** the perception engine's `invisible` tag and
`conceal_difficulty` (the same machinery the [secret door](027_secret_door.md)
and [landmine](049_landmine.md) use, here applied to *objects*), the
built-in `search` command, and the design of layered secrets that reward
a better roll with a better find.

## How it works

This build is almost entirely *configuration of an existing engine
feature* — the point of the tutorial is to show how little softcode a
search puzzle needs:

1. **Hiding is a tag.** Anything tagged `invisible` drops out of the
   room's contents display and can't be targeted by name. Put it on a
   thing and the thing is concealed.

2. **`search` is built in.** It rolls the searcher's Observation at
   `-conceal_difficulty` against **every** concealed object in the room.
   Each one it beats loses its `invisible` tag and prints its
   `reveal_msg`. One command, any number of hiding places, no softcode at
   all — the difficulty per object is just an attribute.

3. **Difficulty layers the finds.** `conceal_difficulty` is the penalty
   on the roll: 1 is "barely tucked away", 5 is "master-concealed". A
   searcher with middling Observation turns up the easy caches and walks
   right past the hard one; only a keen-eyed expert clears the room. Same
   command, different outcomes — the search *is* the skill check.

4. **Found is found (world state).** Revealing strips a shared tag, so
   once anyone finds the cache it's visible to everyone. That's usually
   what you want for a physical hiding place; a per-character variant (the
   secret stays hidden except in *your* view) is in Going further, lifted
   straight from [item 27](027_secret_door.md).

Once revealed, a hidden object is an ordinary thing — `look` it, `get`
it, read it — because concealment was only ever a tag.

## Build it

Dig the study:

```text
@dig The Study = study, out
study
@desc The Study = A scholar's study gone to dust: a great desk, sagging shelves, a cracked oil painting.
```

Three finds of rising difficulty. Each is a real object; the pattern is
identical — set `conceal_difficulty`, write the `reveal_msg`, tag it
`invisible`:

```text
@create brass key
drop brass key
@desc brass key = A small brass key, filmed with dust.
@set brass key/conceal_difficulty = 1
@set brass key/reveal_msg = Something glints behind the desk leg -- a brass key in the dust!
@tag brass key = invisible
@create leather ledger
drop leather ledger
@desc leather ledger = A slim ledger of cramped figures.
@set leather ledger/conceal_difficulty = 3
@set leather ledger/reveal_msg = One book spine is false -- a leather ledger slides out from behind it.
@tag leather ledger = invisible
@create wall cache
drop wall cache
@desc wall cache = A palm-sized cavity behind the painting, lined with felt.
@set wall cache/conceal_difficulty = 5
@set wall cache/reveal_msg = Your fingertips catch a seam in the plaster -- a wall cache springs open!
@tag wall cache = invisible
```

That's the whole build — the `search` command does the rest.

## Try it

As a searcher of middling skill (Observation around 13), the easy and
medium caches turn up but the wall cache stays hidden:

```text
look                 -> the desk and shelves, but nothing hidden shows
search               -> Something glints behind the desk leg -- a brass key in the dust!
                        One book spine is false -- a leather ledger slides out...
look                 -> You see: a brass key, a leather ledger
```

The wall cache needs a sharper eye — an expert (Observation 16) clears it
in one sweep:

```text
search               -> ...a wall cache springs open!
get wall cache       -> now it's a thing like any other
```

Each revealed object is fully real — `look brass key`, `get leather
ledger`. And because reveal is world state, once one player finds the
cache, the next walks in and sees it already open.

## Going further

- **A passive glance** — mirror [item 27](027_secret_door.md): a room
  `ON_ENTER` that rolls `skill_check(enactor, 'observation', -N)` and
  reveals the *easiest* cache on a sharp enough look, so the obvious find
  doesn't even need a deliberate `search`.
- **Per-character finds** — instead of stripping the tag, cache the find
  per player (`set_attr(me, 'found_' + enactor.id, 1)`) and gate a
  `[[...]]` line in the room description on it; the object stays
  `invisible` to everyone else. Item 27's memoization trick.
- **Search costs time or noise** — wrap `search` behind a `$ransack`
  command that also `remit`s "drawers bang and papers fly" so a
  [tripwire](050_tripwire_alarm.md) or guard can hear a thief tossing the
  room.
- **Tools help** — grant a bonus if the searcher carries a `magnifier` or
  `flashlight` (item 6): read `contents(enactor)` in a custom search verb
  and pass the modifier to `skill_check`.
- **Reset** — to re-hide everything for the next explorer, see
  [item 218](218_puzzle_reset.md)'s attribute-restore lifecycle.
