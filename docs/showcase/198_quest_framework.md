# 198. Quest framework

> Checklist item 198 ([now]): *admin-owned quest masters, stage attrs, $quests journal*

**What you'll build:** a Quest Warden, one admin-owned object that holds every
quest's definition, tracks each player's progress as a stage attribute on that
player, renders a `quests` journal on demand, and advances players through a
single routine that any object in the world may fire.

**Concepts:** a **quest master** as the one source of quest definitions; **stage
attributes on the player** (`q_<slug>`); a shared `advance` routine reachable
from any [`ON_<EVENT>` hook](../reference/softcode.md#lifecycle-hooks);
[owner authority](../reference/softcode.md#fn-set_attr), which is what lets an
admin-owned master write a player's sheet; and the
[`target` guard](../reference/softcode.md#guard-on-target) that keeps a reactive
hook from firing on a neighbour's business.

## How it works

The finished machine is three parts that never touch each other's data. The
Warden holds a table of quest definitions, each *player* holds one small integer
per quest in flight, and one routine on the Warden is the only code that moves a
player from one stage to the next. Every trigger in the world, a used relic
today and a slain boss tomorrow, ends up calling that same routine. This section
answers four questions in turn: what a quest even *is* when the engine has no
quest system, who is allowed to write progress onto a player, how a routine
stored on one object figures out where it lives, and why the relic that fires it
has to check who the event was aimed at.

### What is a quest, when the engine ships no quest system?

REALM has no quest subsystem, and that is deliberate: the engine's own coverage
matrix (`docs/design/adventure_coverage.md`) grades quest tracking as softcode
territory, "quest XP = softcode `set_attr`". So a quest here is exactly what the
[job board](094_job_board.md) makes of a paid delivery, only generalised:
definitions on a master, progress on the player, hooks that advance it.

The definitions live in one data attribute, `Quest Warden/quests`, whose value is
a dict of `{slug: {'name': ..., 'stages': [...], 'reward': ...}}`. Adding a
second quest is editing that one attribute, never editing code, which is why it
stays a plain single-line `@set` rather than a
[`'''` block](../guides/world-management.md#multi-line-input-heredocs): a
heredoc stores its body as a raw string, and
`V('quests', {}).get(slug)` needs a real dict to read.

Progress lives on the player as a single integer attribute per quest,
`q_<slug>`, so `q_cinders = 2` reads as "on stage 2 of the cinders quest". That
choice pays off twice over, because a player's whole journal is already on the
player (it survives reboots and shows up in `@examine` with no extra
bookkeeping), and because rendering the journal is a read of the player's own
attributes against the master's table. Reads are open in REALM unless an
attribute is flagged `secret`, so the `$quests` command needs no special
authority to look at a player's stages.

### Who is allowed to write progress onto a player?

Writes are a different matter. [`set_attr`](../reference/softcode.md#fn-set_attr)
succeeds only when the executor *controls* the target, and a player object is
controlled by that player, by an admin, or by anything acting with an admin's
authority. That last clause is the one that makes staff-run content possible:
an object's scripts run with its owner's authority, so a Warden owned by an
admin may stamp `q_cinders` onto Raven's sheet, while a gadget owned by an
ordinary player is refused when it reaches for someone else's attributes. Build
the Warden as staff and the quest line works; build it as a player and it
quietly writes nothing.

### How does a shared routine find its own home?

The `advance` routine is stored on the Warden but called from elsewhere, and
[`eval_attr`](../reference/softcode.md#fn-eval_attr) runs an attribute **as the
caller**: the executor is unchanged, so inside `advance` the name `me` is
whichever object called it, and `V()` would read that caller's attributes. (This
is the reverse of PennMUSH's `u()`, which swaps the executor to the attribute's
owner and can therefore escalate; REALM's version stays at the caller's
authority, which is why it needs no power to gate it.) The practical
consequence is one line of ceremony at the top of the routine: `advance`
re-resolves its own home with [`get('Quest Warden')`](../reference/softcode.md#fn-get)
before reading the quest table. Names resolve locally first and then world-wide,
so a hook in a distant room still finds the master. If you would rather the
routine run *as* the Warden, with `me` and `V()` pointing at it,
[`call`](../reference/softcode.md#fn-call) is the method-invocation form, gated
on the caller controlling the target.

### Why the relic guards on `target`

The toll ledger reacts to being used, and `ON_USE`, like every
[`ON_<EVENT>` hook](../reference/softcode.md#lifecycle-hooks), fires on the room
and on **every object in it**, not only on the object the action named. Without
`if target is me:` the ledger advances the quest when a player uses the Warden,
a chair, or a second ledger standing beside it. The guard is an identity check,
`is` rather than `==`, and it wraps the entire body. See
[Guard on `target`](../reference/softcode.md#guard-on-target) and, for the
propagation model behind it, [Action Propagation](../architecture/events.md).

## Build it

Stand in your guild hall as staff. Create the Warden, drop it so it is part of
the room, and give it the quest table: one quest, "The Cinder Road", three
stages, a 50-credit reward. The table is data, so it stays a single-line `@set`
and `.get()` keeps working on it.

```text
@create Quest Warden
drop Quest Warden
@set Quest Warden/quests = {"cinders": {"name": "The Cinder Road", "stages": ["Search the burned waystation for the toll ledger.", "Return the toll ledger to the Quest Warden.", "Complete."], "reward": 50}}
```

Now the routine everything else calls. It takes a player id and a quest slug,
re-resolves the Warden so it can read the table no matter who called it, reads
the player's current stage, and then does one of two things: bump the stage and
report the new objective, or, when the player is already on the last step before
the end, close the quest out and pay the reward.

```text
@set Quest Warden/advance = '''
q = get('#' + str(arg0))
slug = str(arg1)
wd = get('Quest Warden')  # eval_attr keeps the CALLER as executor, so me is not the Warden here
defn = get_attr(wd, 'quests', {}).get(slug)
cur = get_attr(q, 'q_' + slug, 0)
last = len(defn['stages']) if defn else 0
if defn and 0 < cur < last - 1:
    set_attr(q, 'q_' + slug, cur + 1)
    pemit(q, f"Quest updated -- {defn['name']}: {defn['stages'][cur]}")
elif defn and cur == last - 1:
    set_attr(q, 'q_' + slug, last)
    adjust_credits(q, defn['reward'])
    pemit(q, f"Quest complete: {defn['name']}. Reward: {defn['reward']} credits.")
'''
```

A player takes a quest with `accept quest <slug>`. The command refuses an
unknown slug, refuses a quest already in flight, and otherwise writes stage 1
onto the player and reads them the first objective. This is the write that needs
the Warden's admin owner behind it.

```text
@set Quest Warden/cmd_start = '''
$accept quest *:
slug = trim(arg0)
defn = V('quests', {}).get(slug)
if not defn:
    pemit(enactor, 'No such quest.')
elif get_attr(enactor, 'q_' + slug, 0):
    pemit(enactor, 'You are already on that quest.')
else:
    set_attr(enactor, 'q_' + slug, 1)
    pemit(enactor, f"Quest accepted -- {defn['name']}: {defn['stages'][0]}")
'''
```

The journal walks the master's table, keeps only the quests this player has a
stage on, and prints the stage text for each. Clamping the stage with `min`
keeps the last line readable once a quest is finished, since a completed quest
sits at `stage == len(stages)`.

```text
@set Quest Warden/cmd_quests = '''
$quests:
rows = []
for slug, d in V('quests', {}).items():
    stage = get_attr(enactor, 'q_' + slug, 0)
    if stage:
        shown = min(stage, len(d['stages']))
        rows.append(f"{d['name']} [{shown}/{len(d['stages'])}] -- {d['stages'][shown - 1]}")
if rows:
    pemit(enactor, 'Your journal:')
    for row in rows:
        pemit(enactor, '  ' + row)
else:
    pemit(enactor, 'Your journal is empty.')
'''
```

Handing in is the second caller of `advance`. `report` collects every quest the
player is holding at its return stage, which is the one before the end, and
fires the routine for each.

```text
@set Quest Warden/cmd_report = '''
$report:
due = [slug for slug, d in V('quests', {}).items() if get_attr(enactor, 'q_' + slug, 0) == len(d['stages']) - 1]
for slug in due:
    eval_attr(me, 'advance', enactor.id, slug)
if not due:
    pemit(enactor, 'You have nothing to report.')
'''
```

Finally the objective itself, a toll ledger whose `ON_USE` is the first caller
of `advance`: pick it up, use it, and the same routine carries a player from
stage 1 to stage 2. In a full world you would scatter it in the waystation room;
here it sits alongside the Warden so the demo runs in one place.

```text
@create toll ledger
drop toll ledger
@set toll ledger/on_use = '''
if target is me:  # ON_USE fires on EVERY object in the room, so guard it
    wd = get('Quest Warden')
    if wd is not None and get_attr(enactor, 'q_cinders', 0) == 1:
        eval_attr(wd, 'advance', enactor.id, 'cinders')
'''
```

## Try it

Play a round as Raven, standing in the room with the Warden and the ledger:

```text
> quests
Your journal is empty.

> accept quest cinders
Quest accepted -- The Cinder Road: Search the burned waystation for the toll ledger.

> quests
Your journal:
  The Cinder Road [1/3] -- Search the burned waystation for the toll ledger.

> use toll ledger
Quest updated -- The Cinder Road: Return the toll ledger to the Quest Warden.
You use the toll ledger.

> report
Quest complete: The Cinder Road. Reward: 50 credits.

> quests
Your journal:
  The Cinder Road [3/3] -- Complete.
```

Two results are worth confirming deliberately. The first is that the progress
really is on the player, which `@examine` shows as a plain attribute:

```text
> @examine Raven
Attributes:
  credits: 50
  q_cinders: 3
```

The second is that the ledger reacts only to its own use. Drop any other object
beside it and use *that*, and the quest stays where it was, because the
`if target is me:` guard rejects the neighbour's event:

```text
> @create spare ledger
Created: spare ledger (#3e26579b)      <- the id differs on every run

> drop spare ledger
You drop a spare ledger.

> use spare ledger
You use the spare ledger.
```

The refusals are worth a look too. `accept quest dragons` answers "No such
quest.", accepting a quest already in flight answers "You are already on that
quest.", and `report` with nothing due answers "You have nothing to report."

## Going further

- **More quests, no new code.** Add a key to the `quests` dict and the journal,
  the accept verb, and the reward payout all cover it, because the table is the
  content.
- **Any hook advances.** Point a boss's `ON_DEATH` or a room's `ON_ENTER` at
  `eval_attr(get('Quest Warden'), 'advance', enactor.id, '<slug>')` and killing
  the boss or reaching the ruin moves the stage. On `ON_DEATH`, read the killer
  from `actor` rather than trusting `enactor` to be the right object, and expect
  the hook from every death route, since a boss felled by a trap fires it just
  as a boss felled by a blade does
  ([245](245_event_bus_tour.md)). The delivery quest
  ([199](199_delivery_quest.md)) rides `ON_RECEIVE` and collection counters
  ([200](200_collection_counters.md)) ride `ON_GET`, both of which need the same
  `target` guard.
- **Prerequisites.** Gate `accept` on another quest's stage
  (`get_attr(enactor, 'q_cinders', 0) >= 3`) to chain quests into a line.
- **Abandon.** A `$abandon *` verb calling
  [`del_attr`](../reference/softcode.md#fn-del_attr) on `'q_' + slug` clears a
  quest, and the journal drops it on the next read.
- **Other rewards.** Swap
  [`adjust_credits`](../reference/softcode.md#fn-adjust_credits) for a
  `set_attr` on `character_points`, an item grant, or a disposition bump, since
  the reward is only the last line of `advance`.
