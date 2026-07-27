# 106. Arm Wrestling

> Checklist item 106 ([now]): *contest(), remit spectacle, wagers*

**What you'll build:** A scarred bar table where two players slap down matching
stakes and settle it with one opposed strength contest, called with crowd
play-by-play and paid on the spot.

**Concepts:** [`contest()`](../reference/softcode.md#fn-contest) opposed quick
contests (margin against margin), making a raw stat rollable by defining a
`skill_def` object and running `@reload` (skills as data), an escrowed wager
through [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks), and
[`remit()`](../reference/softcode.md#fn-remit) spectacle, where the crowd is the
product.

## How it works

The finished scene is a bar table that holds two matching stakes in escrow and,
the instant the second one lands, runs a single opposed strength roll and pays
the winner double from the credits it is already holding. This section answers
three questions: how a raw stat becomes something `contest()` can roll, why a
tie keeps the standing champion, and how the table banks both wagers before the
elbows go down.

### Why strength needs a skill name

[`contest(a, skill, b, skill)`](../reference/softcode.md#fn-contest) has both
sides roll 3d6 under their level in a *skill* and compares margins of success.
A level comes from a `skill_<name>` attribute when trained, or, untrained, from
the game system's default table, and that table is data. A `skill_def` object
named `brawn` with `stat = strength` and `penalty = 0` teaches the table one row:
every untrained `brawn` roll resolves against the roller's raw ST. This is the
same skills-as-data bridge the [pickpocket NPC](070_pickpocket_npc.md) uses to
make "pickpocket" rollable and the [poison dart trap](052_poison_dart_trap.md)
uses for "fortitude"; `@reload` re-reads the definitions from the world, and from
then on `contest(a, 'brawn', b, 'brawn')` is the ST-against-ST quick contest, no
engine change and one data object.

There is deliberately no `contest(a, 'strength', ...)` shortcut. The check layer
resolves skill names, so a name the table does not list falls to a neutral floor
(five here), not the roller's actual strength, and the `skill_def` bridge is the
sanctioned way to key a roll off a bare attribute.

### Why a tie keeps the champion

`contest()` returns True only when the actor wins outright; ties and mutual
failure go to the opponent, because the status quo holds. The bout passes the
challenger as the actor and the challenged player as the opponent, so calling
someone out means you must beat them cleanly: an equal-ST pair goes to the
challenged roughly two times in three. It is a house rule the engine enforces
for free.

### How the table holds both stakes

Both players pay the table, which arms an [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks)
hook that reads the stake off the action with
[`adata('amount')`](../reference/softcode.md#event-data-namespace), one of the
names in the event data namespace. Because `pay` moves the credits before the
hook runs (see the [before/apply/after trio](../design/action-phases.md)), the
table is already holding each stake by the time the hook reacts, so a wrong
amount is handed straight back with
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits). There are no
secret choices here, so no prompts: the second matching stake landing runs the
bout at once, and the winner takes double from the table's own balance, which at
that moment holds exactly both stakes.

## Build it

**Work as your admin character** for the skill bridge, then create the table
itself. First the skill-as-data bridge, once per game: a `skill_def` object
carrying its governing stat and untrained penalty, merged into the table by
`@reload`. Each of these is a single statement, so they stay one line apiece:

```text
@create brawn
@tag brawn = skill_def
@set brawn/stat = strength
@set brawn/penalty = 0
@reload
```

Now the table, with a face that reads the current bout live. The `[[...]]` block
runs per viewer at look time, doing one shallow [`V('bout', None)`](../reference/softcode.md#fn-v)
read (shorthand for `get_attr(me, 'bout', None)`) so the description knows whether
a grudge match is forming:

```text
@create the wrestling table
drop the wrestling table
@desc the wrestling table = Elbow-polished oak, ringed by chalk lines and old beer. [[bt = V('bout', None); result = 'A grudge match is forming.' if bt else 'The chair opposite is empty.']]
```

The callout is a `$`-command, so it only ever runs on the table whose name
matched and needs no `target` guard. It validates the opponent and wager, records
the bout as a small escrow record on the table, and announces the terms to the
room with [`remit`](../reference/softcode.md#fn-remit):

```text
@set the wrestling table/cmd_wrestle = '''
$wrestle * for *:
opp = get(trim(arg0))
w = int(trim(arg1))
ok = not V('bout', None) and opp is not None and has_tag(opp, 'player') and loc(opp) is here and opp is not enactor and w > 0
if ok:
    set_attr(me, 'bout', {'a': enactor.id, 'b': opp.id, 'wager': w, 'paid': []})
    remit(here, name(enactor) + ' slaps ' + str(w) + ' credits on the table and calls out ' + name(opp) + '. Both: pay ' + str(w) + ' to the wrestling table.')
else:
    pemit(enactor, 'The table is busy, or that is no valid opponent or wager.')
'''
```

The escrow is the [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks) hook.
Unlike the callout it must open with `if target is me:`, because an `ON_PAYMENT`
fires on every object in the room, and unguarded the table would bank a stake
whenever someone paid the bar next to it (see
[Guard on `target`](../reference/softcode.md#guard-on-target)). It banks a
matching stake from a listed duelist, shrugs a wrong amount back, and, when the
second stake lands, fires the bout through
[`eval_attr`](../reference/softcode.md#fn-eval_attr):

```text
@set the wrestling table/on_payment = '''
if target is me:  # ON_PAYMENT fires on EVERY object in the room, so guard it
    bt = V('bout', None)
    paid = adata('amount', 0)
    ok = bt is not None and enactor.id in [bt['a'], bt['b']] and enactor.id not in bt['paid'] and paid == bt['wager']
    if ok:
        bt['paid'].append(enactor.id)
        set_attr(me, 'bout', bt)  # write the mutated escrow record back
        pemit(enactor, 'Your stake hits the wood.')
        if len(bt['paid']) == 2:  # second stake in: elbows down
            eval_attr(me, 'bout_go')
    elif paid > 0:
        transfer_credits(me, enactor, paid)  # wrong amount or no bout of yours: hand it back
        pemit(enactor, 'The table shrugs your credits back: wrong amount, or no bout of yours.')
'''
```

The bout is a subroutine the escrow calls, so it also needs no guard: `eval_attr`
runs it with the same message queue, and it resolves the pair off their stored
ids. It narrates the lock-up, runs the one contest, pays the winner double, and
clears the escrow with [`del_attr`](../reference/softcode.md#fn-del_attr) so the
chair opposite is empty again:

```text
@set the wrestling table/bout_go = '''
bt = V('bout', {})
a = get('#' + bt['a'])
b = get('#' + bt['b'])
remit(here, name(a) + ' and ' + name(b) + ' lock hands over the scarred tabletop. The crowd leans in.')
win = a if contest(a, 'brawn', b, 'brawn') else b  # ties go to b, the challenged player
lose = b if win is a else a  # identity check: win IS one of these two objects
remit(here, 'Knuckles whiten, the table groans... ' + name(win) + " slams " + name(lose) + "'s arm down! The crowd roars.")
transfer_credits(me, win, bt['wager'] * 2)
remit(here, name(win) + ' scoops the pot: ' + str(bt['wager'] * 2) + ' credits.')
del_attr(me, 'bout')
'''
```

## Try it

Two players, one strong (`@set Kess/strength = 14`) and one less so
(`@set Bob/strength = 8`), each with pocket money. Kess calls Bob out, both match
the stake, and the second payment runs the bout at once:

```text
> wrestle Bob for 10
Kess slaps 10 credits on the table and calls out Bob. Both: pay 10 to the wrestling table.

> pay 10 to the wrestling table
Your stake hits the wood.

(Bob) pay 10 to the wrestling table
Kess and Bob lock hands over the scarred tabletop. The crowd leans in.
Knuckles whiten, the table groans... Kess slams Bob's arm down! The crowd roars.
Kess scoops the pot: 20 credits.
```

Only the winner varies, since the two `remit` slam lines follow the roll. ST 14
against ST 8 takes the bout about five times in six: strong, but not scripted, so
the underdog still steals one now and then. Train `skill_brawn` above your ST
(`improve`, or a coach NPC) and technique starts to beat raw meat.

## Going further

- **Best of three:** loop the contest in `bout_go` and narrate each fall.
  Margins are already graded, so you can call the close ones differently from the
  clean slams.
- **Fatigue:** on each bout, `apply_effect(lose, 'modifier_effect',
  kind='burned_arm', check_mods={'brawn': -2}, duration=300)`, and the
  condition-modifier pipeline folds the penalty into the loser's next contest
  automatically.
- **Side bets:** stand the [bookmaker](105_npc_races.md)'s book next to the
  table. The bout resolves in one event, so the book settles the moment `bout_go`
  names a winner.
- **The house champion:** an NPC with `skill_brawn = 15` and an `ON_PAYMENT` that
  accepts any challenger's stake turns the table into a credit sink with a face.
