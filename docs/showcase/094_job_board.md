# 094. Job board

> Checklist item 94 ([now]): *posting attrs, ON_RECEIVE validation, payouts*

**What you'll build:** a hiring hall where Foreman Dray posts paid delivery
jobs onto a board on his own heartbeat, workers sign for them, and handing the
goods to the foreman verifies the claim and pays out automatically, with no GM
in the loop.

**Concepts:** postings as ledger attributes (`job_<n>` dicts) on a board
object; an NPC whose `on_tick` authors content (the posting faucet); claim as
one attribute write; verification riding `give` plus `ON_RECEIVE` (the hand-in
is the proof); wages paid by
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits) from the
foreman's funded purse; the push-back pattern for wrong deliveries.

## How it works

A job board in REALM is not an engine subsystem, because there is no native
quest framework: the engine's own coverage matrix
(`docs/design/adventure_coverage.md`) grades quest tracking as softcode
territory, "quest XP = softcode `set_attr`". So a job board is what quests
*are* in a softcode-first world, namely rows in an attribute ledger plus hooks
that verify and pay. This section walks the two objects that share the work and
says why each takes the shape it does.

### Where the postings live

The job board holds the ledger. Each posting is one attribute,
`job_<n>`, whose value is a dict:
`{'want': <exact item name>, 'reward': <credits>, 'text': <posting>, 'taken':
<player id>, 'taken_name': <name>}`. A `next_job` counter names the next slot,
so a posting is one
[`set_attr`](../reference/softcode.md#fn-set_attr) on its own numbered key and
never a rewrite of a shared list. This is the same per-object ledger the
[bulletin boards](076_bulletin_boards.md) use for notices and the
[bank](087_bank_accounts.md) uses for accounts. A `$jobs` command renders the
open rows, and an `$accept job <n>` command writes the claim, so each row has
one writer and jobs go first come, first served.

### The foreman authors the work

Foreman Dray is the employer, and his `on_tick` calls a `post` routine through
[`eval_attr`](../reference/softcode.md#fn-eval_attr). While fewer than two jobs
are open, `post` picks a template from his `templates` data attribute at random,
stamps it onto the board, and announces it to the room. Dray is admin-owned,
like the board, so a master may write another master's attributes under owner
authority. An NPC posting content on a heartbeat is the same muscle as the
[shopkeeper](063_shopkeeper.md) restocking shelves, which means the world keeps
itself supplied with work.

One detail decides which emitter `post` uses. Because `post` runs through
`eval_attr`, its `say`/`pose` output lines are discarded, while the queued
emitters [`remit`](../reference/softcode.md#fn-remit) and
[`pemit`](../reference/softcode.md#fn-pemit) survive back to the caller. So a
routine you invoke with `eval_attr` reaches the room with `remit`, not a speech
verb.

### Verification is the hand-in

The engine's `give` accepts NPC recipients and fires the recipient's
`ON_RECEIVE` after the item lands, and the hook's payload names the delivery
outright: [`adata('item')`](../reference/softcode.md#event-data-namespace) is
the thing that just arrived, and `adata('giver')` is the person who handed it
over (the same object as `enactor` on this hook, so the build uses the shorter
name). Reading `it = adata('item')` is worth pausing on, because the obvious
alternative is a trap. You could infer the arrival from `contents(me)[0]` on
the theory that the foreman keeps nothing, so whatever he holds must be the
delivery. That works right up until he is holding anything else, one dropped
prop or one reward he has not handed over yet, and then it grades the wrong
object. The payload does not infer; it knows.

`ON_RECEIVE` is a reactive hook, and it fires on *every* object in the room,
not only the one the give targeted (see
[Guard on `target`](../reference/softcode.md#guard-on-target)). So the whole
body sits under `if target is me:`, an identity check, so Dray only grades
goods pressed into his own hands. The script then finds the giver's claimed job,
checks the delivered item's name against the job's `want`, and on a match pays
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits)`(me, enactor,
reward)` out of Dray's purse (fund him up front, because wages that can bounce
are a lie), consumes the goods with
[`destroy_obj`](../reference/softcode.md#fn-destroy_obj), and deletes the row.
On a miss the item goes straight back with
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj) and an explanation,
because an interface that silently kept wrong deliveries would be a theft bug.

Note what the claim check buys: you can only be paid for a job you signed for,
so handing in goods without accepting the posting first pushes them back. That
is the "claimed and verified" contract of the checklist, in two attribute reads.

## Build it

The hall, the board, and the employer. Fund Dray up front, since he pays real
wages from his own purse:

```text
@dig The Hiring Hall
@teleport The Hiring Hall
@create the job board
drop the job board
@create Foreman Dray
@tag Foreman Dray = npc
drop Foreman Dray
@eval adjust_credits(get('Foreman Dray'), 500)
```

His job templates as data, each row `[exact item name, reward, posting text]`.
`@set` parses JSON, so this stores a real list of lists:

```text
@set Foreman Dray/templates = [["a rat pelt", 15, "Cull the dock rats: bring me a rat pelt."], ["a salvage crystal", 40, "Recover a salvage crystal from the mud flats."]]
```

The posting routine reads the board, counts the open jobs, and while fewer than
two are open picks a template at random, stamps it onto the next slot, and
announces it. It reaches the room with `remit` because `say` would be discarded
when `on_tick` calls it through `eval_attr`:

```text
@set Foreman Dray/post = '''
board = get('the job board')
open_jobs = [i for i in range(1, get_attr(board, 'next_job', 1)) if get_attr(board, 'job_' + str(i))]
rows = V('templates', [])
if len(open_jobs) < 2 and rows:
    p = rows[rand(0, len(rows) - 1)]
    n = get_attr(board, 'next_job', 1)
    set_attr(board, 'job_' + str(n), {'want': p[0], 'reward': p[1], 'text': p[2], 'taken': '', 'taken_name': ''})
    set_attr(board, 'next_job', n + 1)
    remit(here, f'Foreman Dray chalks a notice. Work posted: {p[2]} Pays {p[1]} credits.')  # remit survives eval_attr; say would be dropped
'''
```

Give him the heartbeat that drives it. The `script_ticker` behavior runs
`on_tick` on a cadence, and `on_tick` is a single call into the routine, so it
stays one line:

```text
@behavior Foreman Dray = script_ticker, interval:45
@set Foreman Dray/on_tick = eval_attr(me, 'post')
```

The board's reading face. `$jobs` walks the numbered slots and prints each open
posting, marking whether it is still OPEN or already taken:

```text
@set the job board/cmd_jobs = '''
$jobs:
pemit(enactor, 'The job board:')
for i in range(1, V('next_job', 1)):
    j = V('job_' + str(i))
    if j:
        pemit(enactor, f"  #{i} {j['text']} Pays {j['reward']}. " + (f"Taken by {j['taken_name']}" if j['taken'] else 'OPEN'))
'''
```

The claim verb. `$accept job <n>` writes the worker's id and name into the row
if the job exists and is not yet taken, which is the one write that makes the
claim exclusive:

```text
@set the job board/cmd_accept = '''
$accept job *:
n = arg0.strip()
j = V('job_' + n)
if j and not j['taken']:
    set_attr(me, 'job_' + n, dict(j, taken=enactor.id, taken_name=name(enactor)))  # claim: one row, one writer
    pemit(enactor, f"You sign for job #{n}: {j['text']}")
else:
    pemit(enactor, 'No such job, or it is already taken.')
'''
```

The verifier, Dray's receive hook. The whole body sits under the `target is me`
guard because `ON_RECEIVE` is heard room-wide. It matches the delivery against
the giver's claimed jobs, pays and closes the row on a hit, and pushes the item
back on a miss:

```text
@set Foreman Dray/on_receive = '''
if target is me:  # ON_RECEIVE fires on every object in the room, so gate on the target
    it = adata('item')  # the payload names the delivery; do not infer it from contents(me)
    board = get('the job board')
    hits = [[i, j] for i in range(1, get_attr(board, 'next_job', 1)) for j in [get_attr(board, 'job_' + str(i))] if j and j['taken'] == enactor.id and name(it) == j['want']]
    if hits and transfer_credits(me, enactor, hits[0][1]['reward']):
        i, j = hits[0]
        del_attr(board, 'job_' + str(i))
        destroy_obj(it)
        say(f"Good work, {name(enactor)}. {j['reward']} credits, as posted.")
    else:
        teleport_obj(it, enactor)
        say('That is not what any job of yours calls for.')
'''
```

## Try it

Trigger a posting (or wait for the tick). `@tr` fires the `on_tick` hook
directly, and the room reads the notice:

```text
@tr Foreman Dray/on_tick
    -> Foreman Dray chalks a notice. Work posted: Cull the dock rats: bring me a rat pelt. Pays 15 credits.
```

Then, as Bob, read the board and sign for the job:

```text
jobs                            -> #1 Cull the dock rats... Pays 15. OPEN
accept job 1                    -> You sign for job #1: Cull the dock rats...
jobs                            -> #1 ... Taken by Bob
```

Get a rat pelt (however the world coughs one up) and hand it over:

```text
give a rat pelt to Foreman Dray
    -> Foreman Dray says, "Good work, Bob. 15 credits, as posted."
```

Bob is fifteen credits richer, the pelt is consumed, and `jobs` shows the
posting gone, while the next tick posts fresh work. Hand Dray something wrong
(or something right without signing first) and he pushes it back: "That is not
what any job of yours calls for."

## Going further

- **Kill jobs.** Post a `want` of `head of <boss>` and have the boss's
  `ON_DEATH` mint the trophy, so delivery verification covers bounties the
  moment corpses drop proof.
- **Deadlines.** Stamp `expires` into each row and let the board run a ticker
  that voids stale claims, grafting the auction sweep onto the job ledger.
- **Reputation wages.** On payout, call
  [`adjust_disposition`](../reference/softcode.md#fn-adjust_disposition)`(me,
  enactor, 1)`, so regulars get warmer prices at every shop that reads
  disposition ([063](063_shopkeeper.md)), one line to connect two economies.
- **Player-posted bounties.** An `$offer bounty * for *` verb that escrows the
  poster's reward on the board with `transfer_credits` before the posting is
  public (money in the house before the promise), then writes the row, and the
  same verifier pays it out.
```
