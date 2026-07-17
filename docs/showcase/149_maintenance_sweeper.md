# 149. Maintenance sweeper

> Checklist item 149 — [now] — *housekeeping over tagged objects, search_world queries, dry-run-first safety*

**What you'll build:** A janitor bot that clears litter from a
promenade — but **shows you what it would remove before it removes
anything**. `sweep` previews; `sweep confirm` commits. The
dry-run-first discipline for any destructive bulk operation.

**Concepts:** `search_world()` as a housekeeping query, `destroy_obj()`
over a result set, and the **preview/commit** split that keeps a bulk
purge from being a bulk mistake — the softcode cousin of `@foreach`'s
echo-first habit.

## How it works

Maintenance is a query plus an action: *find the junk, then remove it.*
The danger is the second half — a search that's one tag too broad, run
straight into `destroy_obj`, quietly eats things you meant to keep.

**So the query runs twice, and only the second one destroys.** `sweep`
does the `search_world(tag='litter')` and **reports** the matches — count
and names — changing nothing. You read the list, confirm it's really
junk, and `sweep confirm` runs the same query and reaps it. The preview
*is* the safety: you never destroy a set you haven't seen.

This mirrors how a builder runs bulk edits from the command line —
`@foreach tag:litter = @examine %o` to look before `@foreach tag:litter =
@destroy %o` to leap — and how zone mass-edits
(tutorial 169) echo first. Automating housekeeping doesn't mean
skipping the look; it means baking the look into the tool.

**Tags scope the sweep.** Only `litter`-tagged objects are in range;
everything else in the world is invisible to the janitor. Widen or narrow
the beat by changing one tag in the query — never by hoping the search
was specific enough.

## Build it

A promenade with two bits of litter (tagged, so the janitor can find
them) and one thing that should survive (untagged):

```text
@dig Promenade = prom, out
prom
@create discarded wrapper
@tag discarded wrapper = litter
drop discarded wrapper
@create broken bottle
@tag broken bottle = litter
drop broken bottle
```

The janitor. `sweep` previews; `sweep confirm` commits — two distinct
exact patterns, so one can never trigger the other:

```text
@create janitor bot
drop janitor bot
@desc janitor bot = A squat cleaning drone, brushes folded. SWEEP to preview a cleanup, SWEEP CONFIRM to run it.
@set janitor bot/cmd_sweep = $sweep: junk = search_world(tag='litter'); pemit(enactor, 'The promenade is spotless.') if not junk else pemit(enactor, 'DRY RUN -- would remove ' + str(len(junk)) + ': ' + ', '.join([name(o) for o in junk]) + '. Type SWEEP CONFIRM to run it.')
@set janitor bot/cmd_sweep_confirm = $sweep confirm: junk = search_world(tag='litter'); (pemit(enactor, 'Nothing to sweep.') if not junk else ([destroy_obj(o) for o in junk], remit(loc(me), 'The janitor bot hums through, collecting ' + str(len(junk)) + ' items, and trundles off.')))
```

## Try it

```text
sweep
   -> DRY RUN -- would remove 2: discarded wrapper, broken bottle. Type SWEEP CONFIRM to run it.
```

Nothing has changed — the wrapper and bottle are still on the ground.
Look the list over, then commit:

```text
sweep confirm
   -> The janitor bot hums through, collecting 2 items, and trundles off.
sweep
   -> The promenade is spotless.
```

The litter is gone; anything you *didn't* tag was never in danger.
Preview, confirm, commit — the same three beats every safe purge should
have.

## Going further

- **Orphan hunting:** point the query at real cruft —
  `search_world(attr='expires_at')` for stuck timers, or objects with no
  `location` — for a world-audit janitor (the shape of tutorial 172's
  audit report).
- **Scheduled with a preview log:** put the *dry run* on an `on_tick` that
  pages the owner a report, and leave the *confirm* manual — automated
  eyes, human hands on the trigger.
- **Age-gated sweeps:** only reap litter older than an hour by stamping
  `dropped_at = now()` on drop and filtering `now() - dropped_at > 3600`
  in the query — grace before the broom, using `now()` arithmetic.
- **Undo insurance:** `@export` the area before a big `sweep confirm`; the
  file is your snapshot if the purge went one tag too wide.
