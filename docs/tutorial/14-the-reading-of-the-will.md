# Part 14 — The Reading of the Will

Why cross at all? Because the keeper — Aldous Grey, to the law — died
owning an island, and Saltmarsh keeps its paper. The finale is a
**multi-step interaction**: a notary who wants three things before
he'll read, a witness you must win honestly, and a question you
answer *at a prompt*, like a person, not a menu.

## The Counting House

```text
@dig The Counting House = counting house, market
counting house
@tag here = zone:saltmarsh
@desc here = Ledgers to the rafters. Dust with a filing system. A brass scale weighs the light itself.
@create Master Quill
@tag Master Quill = npc
@set Master Quill/description = Ink on every finger and no opinion he was not paid for.
drop Master Quill
@create the keeper's deed
@set the keeper's deed/description = Gullwing Isle, the tower, and the light — conveyed to whoever this parchment is handed.
give the keeper's deed to Master Quill
@create the sea-chest
@set the sea-chest/credits = 900
give the sea-chest to Master Quill
```

The estate's money lives *in the chest*, not in Quill's purse — his
own balance stays zero, which his fee gate is about to rely on.

## Three things the law wants

The chart, by hand (`ON_RECEIVE` fires when he's *given* something —
he checks what he's now holding). The fee, by `pay` (`ON_PAYMENT`).
The witness, by presence — checked live when you ask him to read:

```text
@set Master Quill/ON_RECEIVE = c = [o for o in contents(me) if 'chart' in name(o)]; (set_attr(me, 'chart_' + enactor.id, 1), say('The Gullwater chart. So she gave up her dead after all.')) if c else say('I have no use for this.')
@set Master Quill/on_payment = (set_attr(me, 'fee_' + enactor.id, 1), say('The clerks thank you.')) if credits(me) >= 25 else say('The probate fee is twenty-five. Not a penny less.')
@set Master Quill/cmd_probate = $probate:w = [o for o in contents(here) if has_tag(o, 'witness') and disposition(o, enactor) >= 1]; missing = 'the chart' if not get_attr(me, 'chart_' + enactor.id) else ('the fee' if not get_attr(me, 'fee_' + enactor.id) else ('a witness of standing' if not w else '')); prompt(enactor, 'Who claims the estate of Aldous Grey, keeper of the Gullwing light? Speak plainly, for the record.', 'on_claim') if not missing else say('The law wants ' + missing + '. The law will have it.')
```

Each check keys state by `enactor.id` — part 4's caching trick grown
into a quest ledger, one attribute per claimant, `@examine`-able any
time. The chart itself is in the wreck if you handed yours to the
ferryman; the sea prints another for anyone who dives (part 9 warned
you the greedy would notice).

## The witness

The harbormaster from part 10 stands for the dead — if you stand well
with him:

```text
@tag the harbormaster = witness
@set the harbormaster/on_check = block('a mind like a ledger') if has_atag('mind') else None
@set the harbormaster/cmd_witness = $bear witness:(say('For the keeper? Aye. I will stand for that.'), force(me, 'follow ' + name(enactor))) if disposition(me, enactor) >= 1 else say('I stand witness for those I trust. You are not yet one of them.')
```

Note the ward: he's iron-minded like the watchman, so the pendant is
no shortcut. `persuade` him (permanent, but one honest pitch each) —
or if that pitch already failed, `fasttalk` buys a +2 that *wears
off*: get him to the reading before it does. Then, on the quay,
`bear witness` — he falls in behind you, and part 10's follow
machinery walks him wherever you go.

## The reading

`prompt()` is the last new primitive: it hands the player's *next
typed line* to a named script, as `arg0`. The answer and the bequest:

```text
@set Master Quill/on_claim = say('Let the record show: ' + escape(arg0) + '.'); set_attr(me, 'claimant', enactor.id); wait(3, 'trigger bequest')
@set Master Quill/bequest = p = get('#' + get_attr(me, 'claimant')); say('To the hand that relit the Gullwing light: the tower, the island, and the sea-chest. Nine hundred, by my count.'); cmd('give deed = ' + name(p)); transfer_credits('the sea-chest', p, 900); force('the harbormaster', 'unfollow')
```

Now claim it, end to end:

```text
quay
persuade the harbormaster
bear witness
market
counting house
give the keeper's chart to Master Quill
pay 25 to master quill
probate
Keeper of the Gullwing
```

That last line isn't a command — it's your *answer*. Quill records
it (through `escape()`, because players will absolutely try color
codes in a legal document), pauses a beat, and the deed crosses the
desk. `credits`: nine hundred richer. `i`: you own a lighthouse.

## Curtain

Count the whole act: a scripted crossing, a market that prices its
opinions, a skill added to the rules as data, a spell with saves and
wards, and a notary running a quest with a prompt and six attributes.
The engine gained nothing new — you composed it all at the table,
inside the game, which was the thesis of part 1 and is now yours to
abuse.

!!! info "Where to go from here"
    - **Harden it**: per-payer fee ledgers (`'fee_' + enactor.id` on
      ON_PAYMENT is honest bookkeeping; the amount-blind gate is
      village accounting), a lock on the stocks, a respawning chart.
    - **Chain prompts**: `on_claim` may `prompt()` again — dialogue
      trees are just callbacks naming callbacks.
    - **The deeper docs**: docs/design/engine_vision.md for the
      authority model this act leaned on, and the adventure coverage
      matrix for what the classics still demand.
