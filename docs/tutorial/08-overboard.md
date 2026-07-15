# Part 8 — Overboard

You've been strolling on the Gullwater like it's cobblestone. Time to
fix that. Some engines hardcode water: CoffeeMud gives every room an
*atmosphere*, every creature a list of what it can *breathe*, and a
tick of unblockable damage when the two disagree. REALM's kernel has
never heard of water — so you'll teach the sea to drown people
yourself, from the table, in one line.

## The undertow

The provider has one more attribute: `cell_populate` spawns things
into a cell the moment it materializes. Spawn a hazard into every
cell of the sea (one line — mind the quotes):

```text
@set gullwater/cell_populate = undertow = {'name': 'the undertow', 'tags': ['hazard'], 'attrs': {'on_tick': "[(damage(p, 2), pemit(p, 'You slip under, choking on brine!')) if not skill_check(p, 'swimming') else pemit(p, 'You fight the swell and tread water.') for p in contents(here) if has_tag(p, 'player')]"}, 'behaviors': [{'behavior_id': 'script_ticker', 'params': {'interval': 8}}]}; result = [undertow]
```

Read it inside-out: every fresh cell gets an invisible **undertow**
carrying a `script_ticker`. Every few beats, its `on_tick` sweeps the
players *directly in the water* — each one rolls `swimming` or takes
2 damage. That's drowning: a spawner, a ticker, a skill check, and
`damage()`. No engine change.

Two details do the heavy lifting:

- **The boat is your waterworthiness.** Aboard the ferry you're
  inside *her*, not in the cell — `contents(here)` never sees you.
  Disembark mid-sea and you're a swimmer.
- **The undertow dies with its cell.** Populate-spawns are born
  transient; when an empty cell reaps, its hazards go with it, and
  the next visitor gets a fresh one.

## Test it (carefully)

```text
board
row sea
row north
ashore
```

Wait a few beats — tread or choke. `board` before it gets serious.
Untrained swimmers fare badly; `improve swimming` (part 5's character
points) is suddenly worth the coin.

## Checkpoint

Standing in open water hurts every few beats; standing on the ferry's
deck never does; the Jetty is dry land and always safe.

!!! info "Learn more"
    CoffeeMud's full shape is worth stealing as you grow this:
    *sinking* (a failed tread walks you down to an underwater room)
    separate from *drowning*, a held-breath grace (an expiring
    `apply_effect` counter), and water-breathing races — here, one
    tag: end the sweep with `... if has_tag(p, 'player') and not
    has_tag(p, 'gills')`. The undertow respects it instantly.
