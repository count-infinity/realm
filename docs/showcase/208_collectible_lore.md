# 208. Collectible lore

> Checklist item 208 ([now]): *ON_GET/ON_USE unlocks, $codex rendering*

**What you'll build:** scattered lore, a data log you pick up and a mural you
study, that quietly unlocks entries in a codex. The Archive terminal reads your
recovered lore back, printing found entries in full and the rest as `[LOCKED]`,
tracked per player.

**Concepts:** [`ON_GET`](../reference/softcode.md#lifecycle-hooks) and
[`ON_USE`](../reference/softcode.md#lifecycle-hooks) hooks that stamp an unlock
flag on the finder with [`set_attr`](../reference/softcode.md#fn-set_attr), the
[`target` guard](../reference/softcode.md#guard-on-target) that keeps one
fragment from answering for another, a codex master holding the entry text in a
single dictionary attribute, and a
[`$codex` trigger](../reference/softcode.md#triggers-attributes-on-objects) that
renders found entries with [`pemit`](../reference/softcode.md#fn-pemit) while
locking the rest.

## How it works

The finished system is two halves that never need to know each other's
internals: fragments scattered through the world, each of which sets a single
flag on whoever finds it, and a terminal that reads those flags back against a
table of entry text. Adding lore later is adding a key to the table and
dropping an object whose hook sets the matching flag, since nothing connects
the two beyond a shared slug. This section answers where an unlock is recorded,
how a fragment knows the find was its own, how the terminal reads a flag it
does not own, and why the entry table stays on one line while the scripts
become multi-line blocks.

### Where does an unlock get recorded?

On the finder. Both fragments run the same line of consequence,
[`set_attr(enactor, 'lore_<slug>', 1)`](../reference/softcode.md#fn-set_attr),
where `enactor` is the player who picked the log up or studied the mural.
Because the flag lives on the player rather than on the item or the terminal,
the collection is per character and persistent without any extra bookkeeping,
and it is inspectable: `@examine Sol` lists `lore_beacon` and `lore_mutiny`
among Sol's attributes.

Writing to a player's sheet takes authority. A script runs with its object's
authority, and an object [controls](../reference/softcode.md#fn-controls)
whatever its owner controls, so a fragment owned by an admin may write any
player's attributes. Build these objects as an admin for that reason: owned by
a plain builder, the same `set_attr` call returns `False`, the flag never
lands, and the finder sees only the pickup message.

### How does a fragment know the find was its own?

An `ON_<EVENT>` hook fires on **every** object in the room, not only the one
the action targeted, so a second data log lying next to the first would unlock
its own entry every time you picked up either of them. The fix is the
[`target` guard](../reference/softcode.md#guard-on-target): `item:on_get` and
`item:on_use` make the object acted on the `target`, so `if target is me:`
wrapping the whole body is exactly the test for "this happened to me" as
opposed to "this happened near me". Write it with `is`, because it is an
identity check against this object.

The two fragments differ only in which hook they hang on. `ON_GET` fires when
the data log is picked up, and `ON_USE` fires when the mural is used, which is
what `use faded mural` propagates. Everything below the guard is the same in
both.

### How does the terminal read a flag it does not own?

Attribute reads are open in REALM unless an attribute is flagged `secret`, so
[`get_attr(enactor, 'lore_' + slug, 0)`](../reference/softcode.md#fn-get_attr)
from the terminal reads the reader's own flags with no special authority. The
`$codex` trigger runs as the terminal, with `enactor` bound to whoever typed
the word, which is what makes the tally per player: Sol sees Sol's count and a
newcomer standing beside them sees `0/2`.

A `$` command carries no action behind it, so `target` is `None` inside it and
there is nothing to guard against; the guard belongs on the reactive hooks
only.

### Why the entry table stays on one line

`entries` is data rather than code, a dictionary of `{slug: {title, text}}`
that the reader walks. A `'''` block stores its body as a raw string, so the
table is written as a single `@set` line to come back as a real dictionary that
[`V('entries', {})`](../reference/softcode.md#fn-v) can iterate and index. The
two hooks and the reader go the other way: they carry control flow, so they are
written as `'''` blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

## Build it

**The furniture.** Create the terminal and the two fragments, and drop them
where players will meet them. In a real world you would scatter the log and the
mural across different rooms; here they sit by the terminal so the whole loop
is one room wide.

```text
@create archive terminal
drop archive terminal
@desc archive terminal = A humming data pedestal. CODEX lists the lore you have recovered.
@create data log
drop data log
@desc data log = A cracked datapad, its screen still faintly lit.
@create faded mural
drop faded mural
@desc faded mural = Flaking pigment across a wall-sized painting of a burning ship.
```

**The codex text.** The `entries` table is the only content in the build, and
every other piece keys off its slugs. Two entries are enough to show the
pattern, and this stays one line so it is stored as a dictionary:

```text
@set archive terminal/entries = {"beacon": {"title": "The Silent Beacon", "text": "Colony ship Meridian went dark here in 2189; its beacon still pulses on a dead channel."}, "mutiny": {"title": "The Long Mutiny", "text": "The crew that survived did not do so kindly. Three names were struck from the log."}}
```

**The first find.** The log's `ON_GET` checks that this log is the object being
taken, stamps the `beacon` flag on the taker, and tells them something changed:

```text
@set data log/on_get = '''
if target is me:  # ON_GET reaches every object in the room; react only to this log's own pickup
    set_attr(enactor, 'lore_beacon', 1)
    pemit(enactor, 'You recovered a data log. A codex entry was unlocked.')
'''
```

**The second find.** The mural is scenery rather than loot, so it unlocks on
`ON_USE` instead, which `use faded mural` fires. The shape is identical down to
the guard:

```text
@set faded mural/on_use = '''
if target is me:
    set_attr(enactor, 'lore_mutiny', 1)
    pemit(enactor, 'You study the faded mural. A codex entry was unlocked.')
'''
```

**The reader.** `$codex` reads the table, counts how many of its slugs the
typist has flagged, prints that count as a completion target, then walks the
table in order and prints each entry either in full or as a locked slot:

```text
@set archive terminal/cmd_codex = '''
$codex:
defs = V('entries', {})
found = [s for s in defs if get_attr(enactor, 'lore_' + s, 0)]
pemit(enactor, f'Codex ({len(found)}/{len(defs)} entries recovered):')
for slug, entry in defs.items():
    if slug in found:
        pemit(enactor, f'  [{entry["title"]}] {entry["text"]}')
    else:
        pemit(enactor, '  [LOCKED] ???')
'''
```

Walking `defs.items()` rather than `found` keeps the locked slots in their
table positions, so a collector can see how much is still out there and where
it falls in the sequence.

## Try it

As Sol, standing in the room with the terminal:

```text
> codex
Codex (0/2 entries recovered):
  [LOCKED] ???
  [LOCKED] ???

> get data log
You recovered a data log. A codex entry was unlocked.
You pick up a data log.

> codex
Codex (1/2 entries recovered):
  [The Silent Beacon] Colony ship Meridian went dark here in 2189; its beacon still pulses on a dead channel.
  [LOCKED] ???

> use faded mural
You study the faded mural. A codex entry was unlocked.
You use the faded mural.

> codex
Codex (2/2 entries recovered):
  [The Silent Beacon] Colony ship Meridian went dark here in 2189; its beacon still pulses on a dead channel.
  [The Long Mutiny] The crew that survived did not do so kindly. Three names were struck from the log.
```

The two results worth confirming deliberately are the count line climbing from
`0/2` to `2/2` as you find lore, and the fact that the unlocks are flags on
*you*: `@examine Sol` now lists `lore_beacon` and `lore_mutiny`, while another
player who typed `codex` in the same room without touching anything still reads
`0/2` and two locked slots.

## Going further

- **Read in place.** Give each fragment an
  [`ON_LOOK`](../reference/softcode.md#lifecycle-hooks) hook or a `[[...]]`
  block in its description so studying it shows the flavor text on the spot,
  leaving the codex as the permanent record.
- **Rewards for completion.** Have `$codex` compare `len(found)` with
  `len(defs)` and, the first time they match, grant a title, credits, or a
  [quest](198_quest_framework.md) advance.
- **Categories.** Namespace the slugs (`lore_ship_beacon`, `lore_crew_mutiny`)
  and add a second trigger, `$codex *:`, that filters the table by the
  wildcard capture in `arg0`, giving the codex tabs.
- **Hidden entries.** Mark some entries `secret` in the table and omit them
  from the `[LOCKED]` list until they are found, the way the hidden badges work
  in [achievements](207_achievements.md), so a collector meets them only by
  stumbling on them.
- **One-shot logs.** Add [`destroy_obj(me)`](../reference/softcode.md#fn-destroy_obj)
  to a log's `ON_GET` so it crumbles as it is read, since the lore now lives in
  the codex rather than in a pack.
