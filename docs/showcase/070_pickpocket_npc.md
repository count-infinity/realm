# 070. Pickpocket NPC

> Checklist item 70 ([now]): *contest(), skill_def, admin-owned theft authority, act() custom events, crime response*

**What you'll build:** Fenn, a cutpurse who works the Shadow Market on a
timer. Each pass he picks a mark and rolls an opposed check, his pickpocket
against the mark's observation. When he wins, something leaves your pack (or
five credits leave your purse) and all you feel is a tug. When he loses, the
cry goes up as a custom propagated event, and the bazaar's zone master sends a
constable: item 71's crime response, wired to a brand new crime.
**Concepts:** [`contest()`](../reference/softcode.md#fn-contest) opposed rolls,
a **skill_def** that makes "pickpocket" a rollable skill, an admin-owned NPC's
authority to [`teleport_obj`](../reference/softcode.md#fn-teleport_obj) and
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits) against
players, [`act()`](../reference/softcode.md#fn-act) firing a custom
`event:theft`, and zone-master dispatch on the `script_ticker` clock.

## How it works

The finished scene is one NPC on a ticker in a zoned market, plus a watch post
next door whose zone master listens for one made-up event. Every few beats Fenn
rolls a contest against a random bystander: a win quietly moves an item or some
coins into his own hands, and a loss fires a `theft` event that the zone master
answers by teleporting a constable onto the thief. This section answers three
questions: how the roll stays fair to a watchful victim, why the theft needs an
admin-owned thief, and how a crime nobody built into the engine still summons
the law.

### Why the roll is a real contest

[`contest(me, 'pickpocket', m, 'observation')`](../reference/softcode.md#fn-contest)
rolls both sides under the live game system, compares their margins, and returns
True only when the actor (Fenn) wins. Ties and mutual failure go to the
opponent, so the mark, being the defender, keeps the status quo and the wrist
gets caught. Because the victim's own `observation` is the other half of the
roll, a perceptive character is a genuinely harder mark, and theft plugs into
the same skill economy as [sneaking](160_sneaking.md).

"Pickpocket" is not in the built-in skill table, so we add it as data before
anyone can roll it. A **skill_def** object carries a `stat` and a `penalty`, and
one `@reload` merges it into the table, exactly the way the
[poison dart trap](052_poison_dart_trap.md) turns `fortitude` into a rollable
skill. After that the whole engine can roll pickpocket for anyone.

### Why the thief must be admin-owned

Moving an item out of a player's pack with
[`teleport_obj(loot[0], me)`](../reference/softcode.md#fn-teleport_obj) and
taking their coins with
[`transfer_credits(m, me, 5)`](../reference/softcode.md#fn-transfer_credits) are
both mutations against a player, and the executor must control the target to
make them. Fenn is a world NPC, but a script runs with its object's authority
and an owned object also wields its owner's, so an admin-owned Fenn controls
whatever the admin controls, which is everything. That is the same rank the
[trainer NPC](069_trainer_npc.md) needs to write a student's sheet. A
builder-owned Fenn simply fails to steal, because a player's belongings are
neither unowned nor his, so the mutation is refused rather than errored.

### How a crime nobody registered still summons the law

[`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hooks match on the
suffix of an action type, so any object with an `on_theft` attribute reacts the
moment something propagates a matching action. A caught Fenn fires
[`act(here, 'THIEF! ...', targeting='room', action_type='event:theft')`](../reference/softcode.md#fn-act),
inventing the `event:theft` type on the spot with no registration. The bazaar's
zone master witnesses every event in the rooms of its zone, even though it sits
in the watch post rather than the market, so its `on_theft` runs and dispatches
the constable. Crimes are a namespace, not a fixed feature list.

Inside that hook the names bind to the scene of the event, not to the master's
own body: `enactor` is Fenn (whoever fired the act), and `here` is the market
room where the theft happened. The dispatch itself is the same shape as
[item 71's `ON_ATTACK`](071_guard_response.md): a cooldown attribute, a
disposition drop, [`teleport_obj`](../reference/softcode.md#fn-teleport_obj) to
pull the constable in, and two [`force`](../reference/softcode.md#fn-force) lines
for the challenge and the arrest. Queued world changes run after the script in
the order they were added, so the constable lands before he swings.

## Build it

**Work as your admin character**, because Fenn's fingers need the rank (see
above). First make "pickpocket" a rollable skill: a `skill_def` object with its
governing stat and untrained penalty, merged into the table by `@reload`.

```text
@create pickpocket
@tag pickpocket = skill_def
@set pickpocket/stat = dexterity
@set pickpocket/penalty = -5
drop pickpocket
@reload
```

Now dig the market and stand in it, then tag the room into a `bazaar` zone so
the watch's zone master will claim it:

```text
@dig Shadow Market = shadows, out
shadows
@zone here = bazaar
```

Create the cutpurse and give him a face and a body:

```text
@create Fenn
@tag Fenn = npc
drop Fenn
@desc Fenn = Lean, quick-eyed, always somehow just behind your shoulder.
@set Fenn/hp = 8
@set Fenn/max_hp = 8
@set Fenn/skill_pickpocket = 14
@set Fenn/skill_melee = 9
```

His tick is the whole act. It gathers the conscious players in the room, picks
one at random, and rolls the contest. On a win it lifts an item if the mark
carries one and otherwise skims five credits, then whispers the tug to the
victim alone. On a loss it announces the grab to the room and fires the custom
`theft` event that the law is listening for:

```text
@set Fenn/on_tick = '''
marks = [p for p in contents(here) if has_tag(p, 'player') and not has_tag(p, 'unconscious')]
if marks:
    m = marks[rand(0, len(marks) - 1)]
    loot = contents(m)
    if contest(me, 'pickpocket', m, 'observation'):  # ties go to the mark; Fenn needs the better margin
        if loot:
            teleport_obj(loot[0], me)
        else:
            transfer_credits(m, me, 5)
        pemit(m, 'A feather-light tug at your belt. Probably nothing.')
    else:
        remit(here, f"{name(m)} catches a hand in their pouch - Fenn's!")
        act(here, 'THIEF! The cry goes up.', targeting='room', action_type='event:theft')
'''
```

Attach the brain that fires `on_tick`, one pass every few beats:

```text
@behavior Fenn = script_ticker, interval:3
```

Now the law. Dig a watch post that shares the `bazaar` zone, and stand a
constable in it:

```text
@dig The Watch Post = watchpost, shadows
watchpost
@zone here = bazaar
@create Constable Marsh
@tag Constable Marsh = npc
@tag Constable Marsh = town_watch
@set Constable Marsh/hp = 14
@set Constable Marsh/max_hp = 14
@set Constable Marsh/skill_melee = 13
drop Constable Marsh
```

Create the zone master and crown it over the `bazaar` zone. Its `on_theft`
answers the cry: while the cooldown is clear it stamps the time, sours the watch
on the thief, pulls Marsh to the scene, and forces the challenge and the arrest.
The master takes no `target is me` guard, because a zone master is a deliberate
global witness that watches every theft in its rooms:

```text
@create Bazaar Watch
@zone/master Bazaar Watch = bazaar
@set Bazaar Watch/on_theft = '''
fresh = now() - V('last_cry', 0) > 60  # one cry a minute, so a mob of victims summons one constable
if fresh:
    set_attr(me, 'last_cry', now())
    adjust_disposition('Constable Marsh', enactor, -5)
    teleport_obj('Constable Marsh', here)  # here is the market where the theft fired, not the post
    force('Constable Marsh', 'say Hold, cutpurse!')
    force('Constable Marsh', f'attack {name(enactor)}')
'''
drop Bazaar Watch
shadows
```

`enactor` inside `on_theft` is whoever fired the act, which is Fenn, so the
constable arrests the right pair of hands.

## Try it

Carry something worth taking and loiter in the market. Within a tick or two
Fenn makes his pass, and against an untrained eye he wins:

```text
> @create silver locket
> shadows
(a tick or two passes)
A feather-light tug at your belt. Probably nothing.
```

`@examine Fenn` now shows the locket among his contents: it left your pack and
all you felt was the tug. Now become a harder mark and wait for his next pass.
Observation 16 out-margins his pickpocket 14, so this time he is caught:

```text
> @set me/skill_observation = 16
(next tick)
Tam catches a hand in their pouch - Fenn's!
THIEF! The cry goes up.
Constable Marsh says, "Hold, cutpurse!"
```

The `theft` event reached the zone master, which teleported Marsh onto the scene
and set him swinging at Fenn, not at you. `consider Constable Marsh` afterward
shows the watch soured on the thief alone. The `last_cry` cooldown holds the
next dispatch for a minute, so a market full of screaming victims still summons
one constable rather than a stampede.

## Going further

- **Fencing the goods:** give Fenn [item 68's schedule](068_npc_schedule.md) so
  he picks pockets by day and walks to a fence NPC at dusk to `give` the haul
  over, putting stolen property back into the economy.
- **Player pickpockets:** offer the same contest as a `$dip *` command on a
  glove object. With the authority flipped, a mere player's softcode cannot move
  a victim's items, which is exactly the design question
  [sneaking](160_sneaking.md) answers with skill gates.
- **Fenn learns:** on a catch, `set_attr(me, 'burned_' + m.id, 1)` and skip
  burned marks on later passes, so a thief remembers who caught him.
- **Insurance:** put a second `on_theft` on the market room itself, since
  ordinary witnesses react too, and log victims to a claims ledger that a clerk
  NPC pays out. One crime event, many listeners.
