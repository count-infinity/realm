# 104. Scavenger Hunt

> Checklist item 104 — [now] — *ON_GET/ON_ARRIVE detection, registry attrs*

**What you'll build:** A hunt board with a staff-set list of finds:
players scour the world for tagged items, bring them back, `claim`
their card, and climb a leaderboard; the first full sets are announced
as champions.

**Concepts:** staff truth via tags (only controllers can `@tag`, so
finds can't be forged), a registry attribute as the hunt definition,
a `$claim` verb that verifies *carried* items, a leaderboard dict, and
a champions list that records finish order.

## How it works

**A find is a name on the list AND a tag on the item.** The board's
`finds` attribute names the trophies; each real trophy carries the
`hunt` tag. `$claim` intersects the two: of the things you're carrying
that bear the tag, how many are on the list? A player can name an
object anything — `@create a brass gear` costs nothing — but tags are
mutations, gated by `controls()`, so only staff can mint a *true* find.
The tag is the anti-forgery device; the name is just the shopping list.

**Progress is a high-water mark.** The leaderboard maps player name →
best claim so far, only ever rising — drop a trophy after claiming and
your stamp stands. A full set appends you to `champions` (once), in
finish order, with a room-wide announcement: finish order *is* the
prize structure.

**Why a verb and not automatic?** `ON_GET` on each trophy could tick
progress the instant it's picked up — see Going further — but a claim
verb makes the hunt end where it began (return to the board), lets
players claim partial sets, and keeps all bookkeeping on one object you
can `@examine`.

## Build it

The board and the official list:

```text
@create the Hunt Board
drop the Hunt Board
@desc the Hunt Board = A corkboard headed THE GREAT HUNT, three photographs pinned beneath. [[lb = V('leaderboard', {}); result = str(len(lb)) + ' hunters on the board.']]
@set the Hunt Board/finds = ["a shard of driftglass", "a brass gear", "a violet feather"]
```

The trophies — tagged, then scattered (here they're dropped at the
board; in a live game you'd hide them across three zones):

```text
@create a shard of driftglass
@tag a shard of driftglass = hunt
drop a shard of driftglass
@create a brass gear
@tag a brass gear = hunt
drop a brass gear
@create a violet feather
@tag a violet feather = hunt
drop a violet feather
```

The claim — carried ∩ tagged ∩ listed, then the ledger writes:

```text
@set the Hunt Board/cmd_claim = $claim: want = V('finds', []); carried = [name(o) for o in contents(enactor) if has_tag(o, 'hunt')]; got = [nm for nm in want if nm in carried]; lb = V('leaderboard', {}); best = lb.get(name(enactor), 0); [(lb.update({name(enactor): len(got)}), set_attr(me, 'leaderboard', lb)) for g in [len(got) > best] if g]; pemit(enactor, f'The board stamps your card: {len(got)} of {len(want)} finds.'); [(set_attr(me, 'champions', V('champions', []) + [name(enactor)]), remit(here, name(enactor) + ' has found everything on the hunt!')) for g in [len(got) == len(want) and name(enactor) not in V('champions', [])] if g]
```

The leaderboard:

```text
@set the Hunt Board/cmd_hunters = $hunters: lb = V('leaderboard', {}); ch = V('champions', []); pemit(enactor, 'THE GREAT HUNT -- standings:'); [pemit(enactor, f'  {nm} -- {k} finds' + (f' [CHAMPION #{ch.index(nm) + 1}]' if nm in ch else '')) for nm, k in sorted(lb.items(), key=lambda kv: -kv[1])]; pemit(enactor, '  (nobody yet)') if not lb else None
```

## Try it

```text
get a shard of driftglass
get a brass gear
claim                     -> "The board stamps your card: 2 of 3 finds."
hunters                   -> "Kess -- 2 finds"
get a violet feather
claim                     -> "3 of 3" and, room-wide:
                             "Kess has found everything on the hunt!"
hunters                   -> "Kess -- 3 finds [CHAMPION #1]"
```

And the forgery test — a look-alike without the tag counts for
nothing:

```text
@create a brass gear          (an untagged fake, from anyone)
claim                         -> still counts only the tagged one
```

## Going further

- **Auto-detection:** put `ON_GET` on each trophy —
  `set_attr(get('the Hunt Board'), 'seen_' + enactor.id, ...)` — and
  the board knows the moment a find is lifted; `ON_ARRIVE` on a trophy
  tells you when it's carried into the trophy hall. The claim verb
  then becomes pure ceremony.
- **Turn-ins:** have `$claim` *take* the trophies (`move_to(o, me)`)
  and pay a bounty per new find — the board becomes a collection
  quest with the [shopkeeper](063_shopkeeper.md)'s economics.
- **Namespaced hunts:** tag trophies `hunt:spring` and check
  `tag_value(o, 'hunt')` against the board's own hunt id — many
  seasonal hunts, zero crosstalk.
- **Timed seasons:** stamp `opened = now()` and have `$claim` refuse
  after `opened + 86400` — leaderboard freezes at the bell.
