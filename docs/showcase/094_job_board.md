# 094. Job board

> Checklist item 94 — [now] — *posting attrs, ON_RECEIVE validation, payouts*

**What you'll build:** a hiring hall: Foreman Dray posts paid delivery
jobs onto a board on his own heartbeat, workers sign for them, and
handing the goods to the foreman verifies the claim and pays out —
automatically, no GM in the loop.

**Concepts:** postings as ledger attributes (`job_<n>` dicts) on a board
object; an NPC whose `script_ticker`/`on_tick` *authors content* (the
posting faucet); claim = one attribute write; verification riding
`give` + `ON_RECEIVE` (the hand-in *is* the proof); wages paid by
`transfer_credits` from the NPC's own funded purse; the push-back
pattern for wrong deliveries.

## How it works

**First, the honest architecture note:** REALM has no native quest
subsystem — the engine's own adventure-coverage matrix
(`docs/design/adventure_coverage.md`) grades quest tracking as softcode
territory ("quest XP = softcode `set_attr`"). So a job board is what
quests *are* in a softcode-first world: **rows in an attribute ledger,
plus hooks that verify and pay.** No engine seam is missing; this is
the intended shape.

Two objects share the work:

- **The job board** holds the ledger: `job_<n> = {'want': <exact item
  name>, 'reward': <credits>, 'text': <posting>, 'taken': <player id>,
  'taken_name': ...}` plus a `next_job` counter — the auction house's
  lot bookkeeping, reused. `jobs` renders it; `accept job <n>` writes
  the claim (one row, one writer, first-come-first-served).
- **Foreman Dray** is the employer. His `on_tick` calls a `post`
  routine: while fewer than two jobs are open, pick a template from his
  `templates` data attribute at random, stamp it onto the board (he's
  admin-owned, like the board — masters may write masters), and post
  it to the room with `remit`. NPCs *posting* content on a heartbeat is
  the same muscle as the shopkeeper restocking shelves (063) — the world
  authors itself. (Note the `remit`, not `say`: `post` is invoked
  through `eval_attr`, and a routine run that way has its *output lines*
  — `say`/`pose`/`emit` — discarded; only the queued emitters
  `remit`/`pemit` survive back to the caller. Reach for the emitter,
  not the speech verb, inside anything you call with `eval_attr`.)

**Verification is the hand-in.** The engine's `give` accepts NPC
recipients and fires the recipient's `ON_RECEIVE` *after* the item
lands. (`adata('item')`/`adata('giver')` now name the delivery directly
— this build predates the event namespace.) It doesn't need one anyway:
the foreman keeps nothing, so whatever is in his hands *is* the
delivery. The script finds the giver's claimed job on
the board, checks the delivered item's name against the job's `want`,
and on a match: pays `transfer_credits(me, enactor, reward)` out of the
foreman's funded purse (fund him up front — wages that can bounce are a
lie), consumes the goods with `destroy_obj`, and deletes the row. On a
miss, the item goes straight back via `teleport_obj` with an explanation
— an interface that silently kept wrong deliveries would be a theft
bug.

Note what the claim check buys: you can only be paid for a job **you
signed for** — handing in pelts without accepting the posting gets them
pushed back. That's the "claimed and verified" contract of the checklist
in two attribute reads.

## Build it

The hall, the board, and the employer (funded — he pays real wages):

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

His job templates as data — `[exact item name, reward, posting text]`:

```text
@set Foreman Dray/templates = [["a rat pelt", 15, "Cull the dock rats: bring me a rat pelt."], ["a salvage crystal", 40, "Recover a salvage crystal from the mud flats."]]
```

The posting routine and its heartbeat — post while fewer than two jobs
are open:

```text
@set Foreman Dray/post = board = get('the job board'); open_jobs = [i for i in range(1, get_attr(board, 'next_job', 1)) if get_attr(board, 'job_' + str(i))]; rows = V('templates', []); pick = rows[rand(0, len(rows) - 1)] if rows else None; [(set_attr(brd, 'job_' + str(n), {'want': p[0], 'reward': p[1], 'text': p[2], 'taken': '', 'taken_name': ''}), set_attr(brd, 'next_job', n + 1), remit(here, f'Foreman Dray chalks a notice. Work posted: {p[2]} Pays {p[1]} credits.')) for g, p, brd in [[len(open_jobs) < 2 and pick is not None, pick, board]] if g for n in [get_attr(brd, 'next_job', 1)]]; result = 1
@behavior Foreman Dray = script_ticker, interval:45
@set Foreman Dray/on_tick = eval_attr(me, 'post')
```

The board's reading face and the claim verb:

```text
@set the job board/cmd_jobs = $jobs:pemit(enactor, 'The job board:'); [pemit(enactor, f"  #{i} {j['text']} Pays {j['reward']}. " + (f"Taken by {j['taken_name']}" if j['taken'] else 'OPEN')) for i in range(1, V('next_job', 1)) for j in [V('job_' + str(i))] if j]
@set the job board/cmd_accept = $accept job *:j = V('job_' + arg0.strip()); ok = bool(j) and not j['taken']; [(set_attr(me, 'job_' + arg0.strip(), dict(x, taken=enactor.id, taken_name=name(enactor))), pemit(enactor, f"You sign for job #{arg0.strip()}: {x['text']}")) for g, x in [[ok, j]] if g]; pemit(enactor, 'No such job, or it is already taken.') if not ok else None
```

And the verifier — the foreman's receive hook. Match the delivery
against the giver's claimed jobs; pay and close on a hit, push back on
a miss:

```text
@set Foreman Dray/on_receive = board = get('the job board'); stuff = [o for o in contents(me)]; it = stuff[0] if stuff else None; hits = [[i, j] for brd, itx in [[board, it]] for i in range(1, get_attr(brd, 'next_job', 1)) for j in [get_attr(brd, 'job_' + str(i))] if j and j['taken'] == enactor.id and itx is not None and name(itx) == j['want']]; paid = bool(hits) and transfer_credits(me, enactor, hits[0][1]['reward']); [(del_attr(brd, 'job_' + str(i)), destroy_obj(x), say(f"Good work, {name(enactor)}. {j['reward']} credits, as posted.")) for g, row, x, brd in [[paid, hits[0] if hits else None, it, board]] if g for i, j in [row]]; (teleport_obj(it, enactor), say('That is not what any job of yours calls for.')) if it is not None and not paid else None
```

## Try it

Trigger a posting (or wait for the tick): `@tr Foreman Dray/on_tick` —
the room reads "Foreman Dray chalks a notice. Work posted: Cull the
dock rats: bring me a rat pelt. Pays 15 credits." Then, as Bob:

```text
jobs                            -> #1 ... Pays 15. OPEN
accept job 1                    -> "You sign for job #1: ..."
jobs                            -> #1 ... Taken by Bob
```

Get a rat pelt (however the world coughs one up) and hand it over:

```text
give a rat pelt to Foreman Dray
    -> Foreman Dray says, "Good work, Bob. 15 credits, as posted."
```

Fifteen credits richer; the pelt is consumed; `jobs` shows the posting
gone — and the next tick posts fresh work. Hand Dray something wrong
(or something right *without* signing first) and he pushes it back:
"That is not what any job of yours calls for."

## Going further

- **Kill jobs.** Post a `want` of `head of <boss>` and have the boss's
  `ON_DEATH` mint the trophy — delivery-verification covers bounties the
  moment corpses drop proof.
- **Deadlines.** Stamp `expires` into each row and let the *board* run a
  ticker that voids stale claims — grafting the auction sweep onto the
  job ledger.
- **Reputation wages.** On payout, `adjust_disposition(me, enactor, 1)`
  — regulars get warmer prices at every shop that reads disposition
  (063), one line to connect two economies.
- **Player-posted bounties.** An `$offer bounty * for *` verb that
  escrows the poster's reward on the board (the auction escrow rule:
  money in the house before the promise is public) and writes the row —
  the same verifier pays it out.
