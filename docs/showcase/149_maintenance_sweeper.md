# 149. Maintenance sweeper

> Checklist item 149 ([now]): *on_tick housekeeping, search_world queries, destroy_obj*

**What you'll build:** A janitor bot that clears tagged litter and shows you
what it would remove before it removes anything. `sweep` previews; `sweep
confirm` commits. This is the dry-run-first discipline for any destructive bulk
operation.

**Concepts:** [`search_world()`](../reference/softcode.md#fn-search_world) as a
housekeeping query, [`destroy_obj()`](../reference/softcode.md#fn-destroy_obj)
over a result set, and the **preview/commit** split that keeps a bulk purge
from becoming a bulk mistake. It is the same read-before-write discipline a
builder keeps by running a read-only pass before a destructive one.

## How it works

Maintenance is a query plus an action: find the junk, then remove it. The
finished janitor splits those two halves across two separate commands so the
removal never runs without a look first. This section explains why the split
exists, then how the tag defines what the janitor touches.

**Why run the query twice?** The danger lives in the second half. A search that
is one tag too broad, run straight into `destroy_obj`, quietly eats things you
meant to keep. So the query runs twice, and only the second run destroys.
`sweep` does the `search_world(tag='litter')` and reports the matches, both the
count and the names, changing nothing. You read the list, confirm it is really
junk, and `sweep confirm` runs the same query and reaps it. The preview is the
safety, because you never destroy a set you have not seen.

This mirrors how a builder runs bulk edits from the command line, using
`@foreach tag:litter = @examine %o` to look before `@foreach tag:litter =
@destroy %o` to leap, and how the zone mass-edit in
[tutorial 169](169_zone_mass_edit.md) is dry-run by default. Automating
housekeeping does not mean skipping the look; it means baking the look into the
tool.

**What defines the janitor's reach?** The tag does, not the room.
`search_world` scans the whole world, so `tag='litter'` finds every
`litter`-tagged object anywhere, and everything untagged is invisible to the
janitor. In this build the only litter happens to sit on the promenade, so that
is all the sweep touches. Widen or narrow the reach by changing the one tag in
the query, rather than by hoping the search was specific enough.

## Build it

First the shell: a promenade with two bits of litter (tagged, so the janitor
can find them), one janitor bot that should survive (untagged, so the sweep
passes it by), and the bot's description telling players the two commands:

```text
@dig Promenade = prom, out
prom
@create discarded wrapper
@tag discarded wrapper = litter
drop discarded wrapper
@create broken bottle
@tag broken bottle = litter
drop broken bottle
@create janitor bot
drop janitor bot
@desc janitor bot = A squat cleaning drone, brushes folded. SWEEP to preview a cleanup, SWEEP CONFIRM to run it.
```

The preview command runs the query and reports it, touching nothing. It sends
the count and the names with [`pemit`](../reference/softcode.md#fn-pemit) so
only the person who typed `sweep` sees the report, and
[`name`](../reference/softcode.md#fn-name) renders each match:

```text
@set janitor bot/cmd_sweep = '''
$sweep:
junk = search_world(tag='litter')
if not junk:
    pemit(enactor, 'The promenade is spotless.')
else:
    listing = ', '.join([name(o) for o in junk])
    pemit(enactor, f'DRY RUN -- would remove {len(junk)}: {listing}. Type SWEEP CONFIRM to run it.')
'''
```

The commit command runs the identical query and reaps it. The `$sweep confirm`
pattern is a distinct exact match from `$sweep` (both compile anchored, so one
never triggers the other), which is what lets a single accidental `sweep` stop
at the preview. It counts the set before destroying, since `destroy_obj` is
deferred, then announces to the whole room with
[`remit`](../reference/softcode.md#fn-remit) at
[`loc(me)`](../reference/softcode.md#fn-loc):

```text
@set janitor bot/cmd_sweep_confirm = '''
$sweep confirm:
junk = search_world(tag='litter')
if not junk:
    pemit(enactor, 'Nothing to sweep.')
else:
    for o in junk:
        destroy_obj(o)  # queued: each object is removed after this script ends
    remit(loc(me), f'The janitor bot hums through, collecting {len(junk)} items, and trundles off.')
'''
```

## Try it

```text
sweep
   -> DRY RUN -- would remove 2: discarded wrapper, broken bottle. Type SWEEP CONFIRM to run it.
```

Nothing has changed, so the wrapper and bottle are still on the ground. Look
the list over, then commit:

```text
sweep confirm
   -> The janitor bot hums through, collecting 2 items, and trundles off.
sweep
   -> The promenade is spotless.
```

The litter is gone, and anything you did not tag was never in danger. Preview,
confirm, commit: the same three steps every safe purge should have.

## Going further

- **Orphan hunting:** point the query at real cruft, such as
  `search_world(attr='expires_at')` for stuck timers, for a world-audit
  janitor. [Tutorial 172](172_world_audit.md) builds that audit report.
- **Scheduled with a preview log:** put the dry run on an `on_tick` that pages
  the owner a report, and leave the confirm manual, so the eyes are automated
  but a human hand is on the trigger.
- **Age-gated sweeps:** reap only litter older than an hour by stamping
  `dropped_at = now()` on drop and filtering `now() - dropped_at > 3600` in the
  query, which grants a grace period before the broom using
  [`now()`](../reference/softcode.md#fn-now) arithmetic.
- **Undo insurance:** `@export` the area before a big `sweep confirm`, and the
  file is your snapshot if the purge went one tag too wide.
