# 120. Combat replay log

> Checklist item 120 ([now]): *recorder objects, event-appended log attrs, $replay*

**What you'll build:** A brass chronicle automaton that records every fight
in its room, the swings, the wounds, the taunts and the finish, into a capped
log that anyone standing there can `replay` afterwards with each line dated by
how long ago it happened.

**Concepts:**
[`ON_ATTACK`/`ON_DAMAGE`/`ON_DEATH`](../reference/softcode.md#lifecycle-hooks)
witnesses that read each event's own
[payload](../reference/softcode.md#event-data-namespace) (`target`,
`adata('damage')`, `adata('weapon')`), a `^*` listen trigger for fight talk,
the capped-list-attribute idiom (`(old + [row])[-30:]`),
[`now()`](../reference/softcode.md#fn-now) timestamps replayed as an age in
seconds, [`eval_attr()`](../reference/softcode.md#fn-eval_attr) subroutines,
and an owner-locked `$wipe`.

## How it works

The finished device is a single object that stands in the ring and does one
thing: it writes. Combat propagates a real action for every swing, every wound
and the kill, and the chronicle reacts to each by appending one row to a `log`
list on itself. A `replay` command reads that log back and a `wipe` command
clears it. This section answers four questions: how the chronicle hears each
moment of a fight, what a single row records, why it needs no `target` guard,
and what it can honestly say about who landed the killing blow.

### How the chronicle hears each moment of a fight

Combat propagates a real action for every swing (`combat:on_attack`), every
wound that lands (`combat:on_damage`) and the kill (`combat:on_death`), and
each fires the matching [`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks)
attribute on the objects standing in the room, with the acting fighter bound as
`enactor` (see the [propagation model](../architecture/events.md)). The
chronicle carries all three hooks, so it reacts to a fight the way the
[security camera](054_security_camera.md) reacts to movement. Fight talk comes
in through a separate `^*` listen trigger, the microphone of the
[voice recorder](007_voice_recorder.md), which fires when a fighter speaks
where the chronicle stands.

Every one of those inputs calls a single `scribe` subroutine through
[`eval_attr()`](../reference/softcode.md#fn-eval_attr). `scribe` appends
`[now(), text]` to the `log` list and re-slices to the newest thirty rows. The
cap matters: an unbounded list on a hot attribute is the classic way a busy
room leaks the database, so the slice is not decoration.

### What a single row records

Each hook reads its own event straight off the action's
[payload](../reference/softcode.md#event-data-namespace). `target` is the
fighter on the receiving end, `adata('damage')` is what the wound cost, and
`adata('weapon')` is the object swung (or empty for a barehanded blow). A row
therefore records what happened in plain words rather than leaving the reader
to reconstruct it later. The engine delivers combat narration directly to the
fighters and the room rather than as speech, and only say-class actions feed
`^` listens, so the chronicle writes its own prose from each event's facts
instead of transcribing the room's messages.

Alongside the prose, a `tally` subroutine snapshots every `in_combat` fighter's
HP into the row, a scoreboard set beside the play. The attack and damage hooks
fire while the action is still in flight, before the wound is applied to HP, so
a row's bracket is the board going into that blow and the row's own damage
number is what the blow then took off. The two together are the whole fight
with no subtraction required.

### Why the hooks need no `target` guard

Most [`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hooks fire on
every object in the room, not only the one the action targeted, so a hook that
reacts to its own business must open with `if target is me:` (see
[Guard on `target`](../reference/softcode.md#guard-on-target)). The chronicle
is the deliberate exception, because it is a witness of the whole room and
means to record everyone. Its hooks take no `target` guard, exactly like the
[arena](115_arena_spectators.md) relay and the security camera. The only filter
is `if enactor` on the listen trigger, which skips a sourceless line. Confirmed
with a second chronicle set in the same room: each one records every blow of an
Ace-versus-Bruce fight once, in the same order, with neither doubling nor
crossing the other's log.

### What the chronicle can honestly say about a kill

`target` is always reliable, since it is the fighter who went down. The killer
is best-effort. A swing binds the attacker as `enactor`, and a poison applied
with `apply_effect` binds whoever applied it, because the effect records its
source. A softcode `damage()` kill binds the scripted object that dealt the
blow (a grenade, a trap) rather than whoever set it, and a death with no
attributable source binds nothing, leaving `enactor` empty. That is why
`on_death` checks the name before writing it: a row that reads "FINISH --  ends
Bruce" is worse than one that admits it does not know who landed the last blow.
The [bounty board](114_bounty_board.md) meets the same question when it has to
decide whom to pay.

## Build it

Dig the ring, step in, and build the automaton. The description tells a reader
which two commands the chronicle answers:

```text
@dig The Fight Cage = cage, out
cage
@create match chronicle
drop match chronicle
@desc match chronicle = A brass automaton hunched over a ledger, pen scratching by itself. REPLAY reads the record back; the owner may WIPE LEDGER.
```

`scribe` is the one place the log grows. It appends a dated row with
[`set_attr`](../reference/softcode.md#fn-set_attr) and caps the list so it
never runs away:

```text
@set match chronicle/scribe = '''
rows = (V('log') or []) + [[now(), str(arg0)]]
set_attr(me, 'log', rows[-30:])   # keep only the newest 30 rows
'''
```

`tally` is the scoreboard. It walks the room's
[`contents`](../reference/softcode.md#fn-contents) with
[`loc(me)`](../reference/softcode.md#fn-loc), keeps the fighters still tagged
`in_combat` with [`has_tag`](../reference/softcode.md#fn-has_tag), and reads
each one's HP with [`get_attr`](../reference/softcode.md#fn-get_attr):

```text
@set match chronicle/tally = result = ' / '.join([f'{name(o)} {get_attr(o, "hp", 0)}:{get_attr(o, "max_hp", 0)}' for o in contents(loc(me)) if has_tag(o, 'in_combat')])
```

The attack hook names the swing. `adata('weapon')` is the object swung, so the
row names the knife as readily as the fist:

```text
@set match chronicle/on_attack = '''
w = adata('weapon')   # empty for a barehanded swing
row = name(enactor) + ' presses the attack on ' + name(target) + (' with ' + name(w) if w else ' barehanded') + '. [' + eval_attr(me, 'tally') + ']'
eval_attr(me, 'scribe', row)
'''
```

The damage hook records the number the wound cost, read straight from
`adata('damage')`, and the same bracketed scoreboard:

```text
@set match chronicle/on_damage = eval_attr(me, 'scribe', name(enactor) + ' lands ' + str(adata('damage', 0)) + ' on ' + name(target) + '. [' + eval_attr(me, 'tally') + ']')
```

The death hook writes the finish, and checks the killer's name before using it
so an unattributed kill still reads honestly:

```text
@set match chronicle/on_death = '''
k = name(enactor)   # empty string when the death path had no one to blame
if k:
    eval_attr(me, 'scribe', 'FINISH -- ' + k + ' ends ' + name(target) + '.')
else:
    eval_attr(me, 'scribe', 'FINISH -- ' + name(target) + ' dies with no hand on record.')
'''
```

The listen trigger catches fight talk. Player text is passed through
[`escape`](../reference/softcode.md#fn-escape), so a taunt is treated as text
rather than color markup:

```text
@set match chronicle/listen_words = ^*: eval_attr(me, 'scribe', name(enactor) + ' shouts: ' + escape(arg0)) if enactor else None
```

`replay` walks the rows and sends each privately with
[`pemit`](../reference/softcode.md#fn-pemit), stamping the age of each line as
`now()` minus its saved time:

```text
@set match chronicle/cmd_replay = '''
$replay:
rows = V('log') or []
if not rows:
    pemit(enactor, 'The ledger is blank.')
else:
    for r in rows:
        pemit(enactor, f'[{now() - r[0]}s ago] {r[1]}')
'''
```

`wipe ledger` clears the log with [`del_attr`](../reference/softcode.md#fn-del_attr),
gated so only the chronicle's [`owner`](../reference/softcode.md#fn-owner) may
start the record over:

```text
@set match chronicle/cmd_wipe = '''
$wipe ledger:
if enactor == owner(me):
    del_attr(me, 'log')
    pemit(enactor, 'You tear out the used pages. The automaton dips its pen.')
else:
    pemit(enactor, 'The automaton clutches its ledger jealously.')
'''
```

## Try it

Run a fight in the cage, a few beats, a taunt, a finish. Then, from anyone
standing there (a fighter limping back in, a judge, the loser's second):

```text
replay
[42s ago] Ace presses the attack on Bruce barehanded. [Ace 30:30 / Bruce 20:20]
[42s ago] Ace lands 3 on Bruce. [Ace 30:30 / Bruce 20:20]
[27s ago] Bruce shouts: is that ALL
[27s ago] Ace presses the attack on Bruce barehanded. [Ace 30:30 / Bruce 17:20]
...
[3s ago] FINISH -- Ace ends Bruce.
```

Read it like a scorekeeper's sheet: each row's bracket is the board going into
that blow, and the damage on the row is what came off it, so Bruce's 20 down to
17 is written twice, once as a number and once as the next row's bracket. The
`wipe ledger` command from anyone but the owner earns the jealous clutch; from
the owner, a blank page for the next bout:

```text
wipe ledger
The automaton clutches its ledger jealously.
(as the owner)
wipe ledger
You tear out the used pages. The automaton dips its pen.
replay
The ledger is blank.
```

## Going further

- **Per-fight takes:** have `scribe` write into a `take_<n>` attribute and step
  `n` on each `on_death`, so `replay 3` plays back one specific bout, the tape
  labels of the [voice recorder](007_voice_recorder.md).
- **Round markers:** the per-fighter beat prompts reach each fighter privately,
  so the chronicle cannot see them; instead count `on_attack` clusters, or
  scribe a divider row whenever the tally's names change.
- **Broadcast the replay:** a `$replay to stands` that
  [`remit`](../reference/softcode.md#fn-remit)s each row into the
  [arena](115_arena_spectators.md)'s stands, a slow rebroadcast for the crowd.
- **Stat lines:** on `on_death`, add each fighter's rows into a `record_<name>`
  attribute (fights, finishes), and a `$record *` command reads career totals,
  the running-balance arithmetic of the [bank accounts](087_bank_accounts.md)
  pointed at fight data.
