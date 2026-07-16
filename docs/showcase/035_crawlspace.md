# 035. Size-Restricted Crawlspace

> Checklist item 35 — now — *stat-reading wards, helpful block() text*

**What you'll build:** A crawlspace between the cellar and a smugglers'
nook that only admits the lightly-burdened: the ward weighs everything
you carry, and if you don't fit it tells you **exactly by how much** —
in both directions, so hauling loot *out* is the real puzzle.

**Concepts:** an `on_check` ward computing over the actor's inventory
(`sum` across `contents(actor)`), attribute conventions as physics
(`weight` on items, `max_load` on the exit), numeric refusal text as
game design, and the same ward stanza deployed on both faces.

## How it works

**Encumbrance is a convention, not an engine.** REALM ships no weight
system — deliberately. An item's `weight` is just an attribute; the
crawlspace is the first thing that *cares*, and the ward defines the
rule locally: `sum(int(get_attr(o, 'weight', 1)) for o in
contents(actor))`. The default of 1 makes every unmarked trinket count
a little; mark the heavy props explicitly. Ten different chokepoints
could weigh the world ten different ways, and none of them needs a
framework — reads are open, and wards may compute.

**The limit is data on the exit.** `max_load` lives on the crawlspace
object itself, so `@set narrow crawlspace/max_load = 8` re-bores the
tunnel without touching the ward. The ward reads it fresh at every
crossing.

**Squeeze both ways, one stanza.** Movement wards live on the rooms
(the walk's gating actions target rooms, with the exit in the payload
— an `on_check` on the exit itself never fires for traversal). Both
faces share the name `narrow crawlspace`, and `get()` resolves locally
first — so the *identical* `@set here/on_check = ...` line works in
the cellar and in the nook, each keying on its own local face via
`adata('exit')`. Same trick as 025's two-sided configuration: name
your faces alike and your scripts stop caring which side they're on.

**Fail loud, fail useful.** `block()` text is the player's only
feedback, so make it arithmetic: *"12 lbs of bulk against a 5 lb
squeeze"* turns a refusal into a plan (drop 7 lbs). Vague failure text
is a bug in disguise.

## Build it

The cellar, the nook, the paired crawlspace, and the load limit:

```text
@dig Dusty Cellar
@teleport me = Dusty Cellar
@dig Smugglers' Nook = narrow crawlspace, narrow crawlspace
@set narrow crawlspace/max_load = 5
```

The ward, cellar side — weigh the walker, compare against the local
face's limit, quote both numbers:

```text
@set here/on_check = load = sum([int(get_attr(o, 'weight', 1)) for o in contents(actor)]); gap = get('narrow crawlspace'); block('You wedge fast: ' + str(load) + ' lbs of bulk against a ' + str(get_attr(gap, 'max_load', 5)) + ' lb squeeze. Shed some kit.') if has_atag('movement') and adata('exit') == gap and load > int(get_attr(gap, 'max_load', 5)) else None
```

Crawl through (empty pockets fit fine) and give the nook the very same
lines — `get('narrow crawlspace')` now resolves to *this* side's face:

```text
narrow crawlspace
@set narrow crawlspace/max_load = 5
@set here/on_check = load = sum([int(get_attr(o, 'weight', 1)) for o in contents(actor)]); gap = get('narrow crawlspace'); block('You wedge fast: ' + str(load) + ' lbs of bulk against a ' + str(get_attr(gap, 'max_load', 5)) + ' lb squeeze. Shed some kit.') if has_atag('movement') and adata('exit') == gap and load > int(get_attr(gap, 'max_load', 5)) else None
narrow crawlspace
```

(The second `max_load` line technically re-sets the same value — kept
so each side's config is complete and copy-paste safe.)

Stock the nook with something worth the trouble — a strongbox too big
to leave with:

```text
@eval box = create_obj('strongbox', tags=['thing'], location=get("Smugglers' Nook")); set_attr(box, 'weight', 9); result = 'stashed'
```

## Try it

Carrying two 3-lb crates:

```text
narrow crawlspace   -> You wedge fast: 6 lbs of bulk against a 5 lb
                       squeeze. Shed some kit.
drop crate
narrow crawlspace   -> through! (3 lbs slides fine)
get strongbox
narrow crawlspace   -> You wedge fast: 12 lbs of bulk against a 5 lb
                       squeeze. Shed some kit.
```

That last refusal is the design: the way in is easy when you travel
light, and the 9-lb prize doesn't fit through a 5-lb hole. Smuggling
becomes a logistics problem — open the strongbox and ferry the
contents? Find the *other* entrance? The ward doesn't care; it just
does the arithmetic, every crossing, both directions.

## Going further

- **Small races fit better** — add the body to the sum:
  `load + int(get_attr(actor, 'girth', 0))`, and set `girth` in
  chargen; a halfling's 0 against an ogre's 6 makes the crawlspace a
  species filter with no extra machinery.
- **Grease the squeeze** — a `$grease crawlspace:` command that bumps
  `max_load` by 3 for a minute (`set_attr` + a [timed-door](029_timed_door.md)
  ticket to revert): consumables versus geometry.
- **Escaping wriggle-check** — replace the flat limit with
  `skill_check(actor, 'escape_artist', 5 - load)` inside the ward —
  wards may roll dice; margins make near-fits chancy instead of binary.
- **Weigh-station variant** — same ward on a cargo gate, but reading
  `credits(actor)`: an excise gate that taxes by the pound is this
  tutorial plus the [toll gate](030_toll_gate.md).
