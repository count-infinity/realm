# 217. Hidden object search

> Checklist item 217 ([now]): *concealment tags, the search command, seeded secrets*

**What you'll build:** A scholar's study salted with three hidden things, a key
in the dust, a ledger behind a false book spine, and a wall cache flush with the
plaster, each one harder to spot than the last. The built-in `search` command
rolls the seeker's Observation against every hiding place in the room at once,
so sharp eyes turn up the easy finds while only a real expert clears the study.

**Concepts:** the perception engine's `invisible` tag paired with the
`conceal_difficulty` and `reveal_msg` attributes (the concealment kit the
[secret door](027_secret_door.md) and the [landmine](049_landmine.md) also use,
here applied to plain objects rather than an exit or a trap), the built-in
`search` command, and the design of layered secrets that reward a better roll
with a better find.

## How it works

The finished study holds three perfectly ordinary objects that happen to be
invisible, each carrying one number saying how hard it is to spot. There is no
script anywhere in this build, because the engine already owns the whole puzzle:
you type six attribute values and three tags, and `search` supplies the rest.
This section answers what makes a thing hidden, what `search` actually rolls,
why the three difficulties differ, and who a find is true for once it happens.

### What makes a thing hidden?

A single tag. Anything tagged `invisible` drops out of room displays and stops
resolving by name, so the key sits in the study the whole time while `get brass
key` reports that no such thing is here. Two exemptions are worth knowing: a
viewer tagged `see_invisible` (and any admin, who holds the SEE_ALL
entitlement) perceives concealed things normally, and exits are deliberately
left out of the name-resolution half so a concealed exit stays walkable, which
is the rule the [secret door](027_secret_door.md) is built on.

### What does `search` actually roll?

`search` walks the room's contents once and treats two kinds of concealment
differently. A concealed *object* has no Stealth of its own, so it gets a flat
Observation check at `-conceal_difficulty`. A *hidden character*, someone who
typed `hide`, opposes with their own Stealth in a quick
[`contest`](../reference/softcode.md#fn-contest), where a tie leaves them
hidden because the status quo holds. This tutorial is about the object half,
but the same sweep covers both, so a thief lurking in your study is spotted by
the same command.

On a success against an object the engine strips its `invisible` tag, delivers
the object's `reveal_msg` to **everyone in the room** rather than to the
searcher alone, and then reports the sweep back to the searcher as `Your search
turns up: brass key, leather ledger.` A sweep that beats nothing answers `You
find nothing unusual.`

One condition is easy to miss: `search` considers an invisible object only once
it also carries a `conceal_difficulty`. An object tagged `invisible` with no
such attribute stays permanently unfindable this way, which is how the engine
separates "concealed, go find it" from "invisible as a lasting special effect".

### Why three difficulties instead of one?

`conceal_difficulty` is subtracted straight from the searcher's Observation, so
it is a penalty measured in skill points. The default resolver rolls 3d6 under
the effective skill, which means every point of difficulty bites hard: a
searcher at Observation 13 clears difficulty 1 on a 12 or less, difficulty 3 on
a 10 or less, and difficulty 5 on an 8 or less. Reading those as design dials, 1
is barely tucked away, 3 takes real looking, and 5 is master work, so the same
command produces three different stories depending on who types it. The search
*is* the skill check.

Give your test characters a trained Observation before you try this, since an
untrained searcher falls back to whatever the installed game system defaults
Observation to. Under the GURPS reference ruleset that is Intelligence minus 5,
which lands at 5 for a character with no Intelligence set, low enough to find
nothing at any difficulty.

### Who is the find true for?

Revealing strips a tag the object carries once for the whole world, so the
moment anybody finds the cache it is open for everyone who walks in afterwards.
That is usually right for a physical hiding place, because a cache that springs
open should stay open. When you want the opposite, a secret that stays hidden in
everyone else's view, the tools are per-viewer description machinery rather than
tags, and both variants are in Going further.

Once revealed, a hidden object is an ordinary thing again. You `look` it, `get`
it, and carry it off, because concealment was only ever a tag.

## Build it

Dig the study, walk in, and describe it. The `out` exit is the way back to where
you started:

```text
@dig The Study = study, out
study
@desc The Study = A scholar's study gone to dust: a great desk, sagging shelves, a cracked oil painting.
```

Create the three finds as plain objects and drop them where they will be hidden.
Nothing is secret yet, so a `look` at this point lists all three in the room:

```text
@create brass key
drop brass key
@desc brass key = A small brass key, filmed with dust.
@create leather ledger
drop leather ledger
@desc leather ledger = A slim ledger of cramped figures.
@create wall cache
drop wall cache
@desc wall cache = A palm-sized cavity behind the painting, lined with felt.
```

Now conceal each one, easiest first. The pattern is three lines every time:
the difficulty, the line `search` prints on a success, and the tag that takes
the object out of sight. The brass key is the gift, findable by almost anyone
who bothers to look:

```text
# search reveals an invisible object only once it also carries a conceal_difficulty
@set brass key/conceal_difficulty = 1
@set brass key/reveal_msg = Something glints behind the desk leg -- a brass key in the dust!
@tag brass key = invisible
```

The ledger is a step up at difficulty 3, which a middling searcher finds about
half the time:

```text
@set leather ledger/conceal_difficulty = 3
@set leather ledger/reveal_msg = One book spine is false -- a leather ledger slides out from behind it.
@tag leather ledger = invisible
```

The wall cache is the master-concealed one at difficulty 5, so it is the find
that separates a keen eye from an ordinary one:

```text
@set wall cache/conceal_difficulty = 5
@set wall cache/reveal_msg = Your fingertips catch a seam in the plaster -- a wall cache springs open!
@tag wall cache = invisible
```

That is the entire build, since `search` does the rest.

## Try it

Prime a test character with a real Observation first. Writing another player's
sheet takes admin authority, so this line is one you type as staff rather than
as a plain builder:

```text
> @set Scout/skill_observation = 13
Set Scout/skill_observation = 13
```

Now play Scout, standing in the study. The room looks empty of anything
interesting, because all three finds are tagged out of the display:

```text
> look

The Study
---------
A scholar's study gone to dust: a great desk, sagging shelves, a cracked oil painting.

Exits: out
```

One sweep turns up what Scout's eyes are good for. The two reveal lines are the
objects' own `reveal_msg` values and the last line is the command's summary:

```text
> search
Something glints behind the desk leg -- a brass key in the dust!
One book spine is false -- a leather ledger slides out from behind it.
Your search turns up: brass key, leather ledger.
```

Those are the lines that vary. Scout needs a 12 or less for the key (near
certain), a 10 or less for the ledger (a coin flip), and an 8 or less for the
cache (about one sweep in four), so on an unlucky roll the ledger line is
missing and on a lucky one the cache line appears early. Anyone else standing in
the study reads the two reveal lines as well, though only Scout gets the
summary.

The finds are now real objects in the room, and they behave like any other
prop:

```text
> look

The Study
---------
A scholar's study gone to dust: a great desk, sagging shelves, a cracked oil painting.

You see:
  a brass key
  a leather ledger

Exits: out

> look brass key

brass key
A small brass key, filmed with dust.

> get leather ledger
You pick up a leather ledger.
```

Sweeping again with only the hard cache left is the outcome worth confirming
deliberately, because it is what a player who is out of their depth actually
sees:

```text
> search
You find nothing unusual.
```

An expert at Observation 16 needs only an 11 or less for the cache, so she
clears the room where Scout stalled, and the find is hers to carry:

```text
> search
Your fingertips catch a seam in the plaster -- a wall cache springs open!
Your search turns up: wall cache.

> get wall cache
You pick up a wall cache.
```

Because the reveal is world state, the next player through the door walks in on
a study whose cache is already open.

## Going further

- **A passive glance.** Mirror the [secret door](027_secret_door.md) by giving
  the room an [`ON_ENTER`](../reference/softcode.md#lifecycle-hooks) that rolls
  [`skill_check`](../reference/softcode.md#fn-skill_check)`(enactor,
  'observation', -1)` and
  [`remove_tag`](../reference/softcode.md#fn-remove_tag)s the easiest find, so
  the obvious one costs no deliberate `search`. Hang it on the room rather than
  on a prop: `ON_ENTER` reaches every object in the room and binds `target` to
  the *location* for all of them, which means a prop-mounted copy fires on
  arrivals too and has no `target is me` distinction to guard itself with (see
  [Guard on `target`](../reference/softcode.md#guard-on-target)).
- **Per-viewer finds.** For a secret that stays hidden in everyone else's view,
  skip the tag entirely and hang a conditional line on the room with `@detail
  here = check('observation', -5) -> Your fingertips catch a seam in the
  plaster.`, which [room details](042_room_details.md) covers. The condition is
  evaluated per looker on every `look`, with `viewer`, `skill(name)`,
  `check(name, mod)`, and `has_tag(tag)` in scope. To make one player's find
  stick instead of rerolling it, put the state in a `[[...]]` description block
  that keys off the looker,
  [`set_attr`](../reference/softcode.md#fn-set_attr)`(me, 'found_' + viewer.id,
  1)` on a success and reading it back with
  [`get_attr`](../reference/softcode.md#fn-get_attr) on later looks.
- **Search costs noise.** Builtins dispatch ahead of `$`-triggers, so a trigger
  named `$search` would never fire and the builtin keeps the word. Add a
  `$ransack` command on the room instead, one that reveals
  the finds and also [`remit`](../reference/softcode.md#fn-remit)s "drawers bang
  and papers fly", and a [tripwire](050_tripwire_alarm.md) or a posted guard
  hears the thief tossing the room.
- **Tools help.** In that custom verb, read
  [`contents`](../reference/softcode.md#fn-contents)`(enactor)` and pass a
  positive modifier to `skill_check` when the searcher is carrying a magnifier
  or a lit [flashlight](006_flashlight.md), which turns equipment into a real
  edge without touching the hiding places.
- **Re-hide for the next explorer.** Restoring the puzzle is just re-adding the
  `invisible` tags, which is exactly the restore routine
  [puzzle reset](218_puzzle_reset.md) generalises across triggers. The
  [escape room](216_escape_room.md) gets the same effect for free by handing
  every party its own instance of the room.
