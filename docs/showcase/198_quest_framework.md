# 198. Quest framework

> Checklist item 198 — [now] — *admin-owned quest masters, stage attrs, $quests journal*

**What you'll build:** a Quest Warden — one admin-owned object that holds
every quest's definition, tracks each player's progress as stage
attributes on the player, renders a `quests` journal, and advances
players through completion hooks that any object in the world can fire.

**Concepts:** the honest softcode-first quest shape (there is no native
quest engine — a quest *is* an attribute ledger plus hooks); a **quest
master** as the single source of quest definitions; **stage attributes on
the player** (`q_<slug>`); a generic `advance` completion hook driven from
any `ON_<EVENT>` trigger; owner authority (an admin-owned master may write
a player's sheet).

## How it works

REALM ships no dedicated quest subsystem — the engine's own
adventure-coverage matrix (`docs/design/adventure_coverage.md`) grades
quest tracking as softcode territory ("quest XP = softcode `set_attr`").
The native "adventures" work (commit c69f667) added combat *beats* and a
coverage audit, not a quest object. So a quest framework is what quests
*are* in a softcode-first world: **definitions on a master, progress on
the player, hooks that advance it.** The [job board](094_job_board.md) is
the same muscle pointed at paid deliveries; this is the general form.

Three ideas carry the whole framework:

- **The master owns the definitions.** `Quest Warden/quests` is a data
  attribute — a dict of `{slug: {name, stages, reward}}`. Adding a quest
  is editing one attribute, never code.
- **The player owns the progress.** A quest in flight is a single integer
  attribute on the *player*: `q_cinders = 2` means "on stage 2 of the
  cinders quest". Reads are open, so `quests` renders the journal by
  reading the player's own `q_*` attrs against the master's table. Because
  the master is **admin-owned**, its scripts run with owner authority and
  may write those attrs onto the player — the one authority rule that
  makes staff-run content possible (a player-owned gadget could never do
  this to someone else's sheet).
- **Completion is a hook, not a command.** The `advance` subroutine takes
  a player id and a slug, bumps the stage, and — on the final stage — pays
  the reward. *Anything* can call it: a room's `ON_ENTER`, an item's
  `ON_USE`, a boss's `ON_DEATH`, or the Warden's own `report` verb. That
  is the completion-hook surface the checklist asks for: one routine, many
  triggers.

One softcode wrinkle worth knowing: `eval_attr(obj, 'attr', ...)` runs the
attribute's code but **keeps the caller's executor** (Penn's `u()`), so
inside `advance` the name `me` would be whoever *called* it, not the
Warden. `advance` therefore re-resolves its own home with
`get('Quest Warden')` before reading the quest table — a "method" that
looks itself up. (Names resolve world-wide as a fallback, so a hook in a
far room still finds the master.)

## Build it

Stand in your guild hall. Create the Warden and give it the quest table —
one quest, "The Cinder Road", three stages, a 50-credit reward:

```text
@create Quest Warden
drop Quest Warden
@set Quest Warden/quests = {"cinders": {"name": "The Cinder Road", "stages": ["Search the burned waystation for the toll ledger.", "Return the toll ledger to the Quest Warden.", "Complete."], "reward": 50}}
```

The `advance` completion hook — bump the stage; on the last step, pay out.
It re-resolves the Warden (`wd`) so it works no matter who calls it:

```text
@set Quest Warden/advance = q = get('#' + str(arg0)); slug = str(arg1); wd = get('Quest Warden'); defn = get_attr(wd, 'quests', {}).get(slug); cur = get_attr(q, 'q_' + slug, 0); nxt = cur + 1; last = len(defn['stages']) if defn else 0; [(set_attr(q, 'q_' + slug, nxt), pemit(q, 'Quest updated -- ' + defn['name'] + ': ' + defn['stages'][nxt - 1])) for g in [bool(defn) and 0 < cur < last - 1] if g]; [(set_attr(q, 'q_' + slug, last), adjust_credits(q, defn['reward']), pemit(q, 'Quest complete: ' + defn['name'] + '. Reward: ' + str(defn['reward']) + ' credits.')) for g in [bool(defn) and cur == last - 1] if g]; result = 1
```

The player-facing verbs — accept a quest (writes stage 1 onto the player),
and the journal:

```text
@set Quest Warden/cmd_start = $accept quest *:slug = trim(arg0); defn = V('quests', {}).get(slug); (pemit(enactor, 'No such quest.') if not defn else (pemit(enactor, 'You are already on that quest.') if get_attr(enactor, 'q_' + slug, 0) else (set_attr(enactor, 'q_' + slug, 1), pemit(enactor, 'Quest accepted -- ' + defn['name'] + ': ' + defn['stages'][0]))))
@set Quest Warden/cmd_quests = $quests:defs = V('quests', {}); rows = [(d['name'] + ' [' + str(min(get_attr(enactor, 'q_' + s, 0), len(d['stages']))) + '/' + str(len(d['stages'])) + '] -- ' + d['stages'][min(get_attr(enactor, 'q_' + s, 0), len(d['stages'])) - 1]) for s, d in defs.items() if get_attr(enactor, 'q_' + s, 0)]; pemit(enactor, 'Your journal:' if rows else 'Your journal is empty.'); [pemit(enactor, '  ' + r) for r in rows]
```

The hand-in verb — `report` fires `advance` for any quest sitting on its
*return* stage (the second-to-last):

```text
@set Quest Warden/cmd_report = $report:hits = [s for s, d in V('quests', {}).items() if get_attr(enactor, 'q_' + s, 0) == len(d['stages']) - 1]; [eval_attr(me, 'advance', enactor.id, s) for s in hits]; pemit(enactor, 'You have nothing to report.') if not hits else None
```

Finally, the objective — a toll ledger whose `ON_USE` is a *completion
hook*: pick it up, use it, and the same `advance` routine carries you from
stage 1 to stage 2. (In a real world you'd scatter it in the waystation
room; here it sits alongside the Warden for the demo.)

```text
@create toll ledger
drop toll ledger
@set toll ledger/on_use = w = get('Quest Warden'); [eval_attr(w, 'advance', enactor.id, 'cinders') for g in [w is not None and get_attr(enactor, 'q_cinders', 0) == 1] if g]
```

## Try it

As a player, Raven:

```text
quests                       -> Your journal is empty.
accept quest cinders         -> Quest accepted -- The Cinder Road: Search the burned waystation...
quests                       -> The Cinder Road [1/3] -- Search the burned waystation...
use toll ledger              -> Quest updated -- The Cinder Road: Return the toll ledger to the Quest Warden.
report                       -> Quest complete: The Cinder Road. Reward: 50 credits.
```

`@examine Raven` now shows `q_cinders = 3` in plain attributes — the whole
journal lives on the player and survives reboots. Accept a quest that
doesn't exist and the Warden says "No such quest."; accept the same one
twice and it refuses; `report` with nothing due answers "You have nothing
to report."

## Going further

- **More quests, zero code.** Add a key to the `quests` dict and the
  journal, accept verb, and reward pipeline all cover it automatically —
  the table *is* the content.
- **Any hook advances.** Point a boss's `ON_DEATH` or a room's `ON_ENTER`
  at `eval_attr(get('Quest Warden'), 'advance', enactor.id, '<slug>')` and
  killing the boss or reaching the ruin advances the quest — the delivery
  quest ([199](199_delivery_quest.md)) rides `ON_RECEIVE`, collection
  counters ([200](200_collection_counters.md)) ride `ON_GET`.
- **Prerequisites.** Gate `accept` on another quest's stage
  (`get_attr(enactor, 'q_cinders', 0) >= 3`) to chain quests into a line.
- **Abandon.** A `$abandon *` verb that `del_attr(enactor, 'q_' + slug)`
  clears a quest — the journal drops it on the next read.
- **Per-quest rewards.** Swap `adjust_credits` for `set_attr` on
  `character_points`, an item grant, or a disposition bump — the reward is
  just the last line of `advance`.
