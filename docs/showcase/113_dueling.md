# 113. Dueling system

> Checklist item 113 ([now]): *consent prompt()s, start_combat, stakes escrow*

**What you'll build:** a sanctioned dueling ring. A challenge is issued at a
stone, the challenged party consents by typing a word, stakes escrow into the
stone, [`start_combat()`](../reference/softcode.md#fn-start_combat) throws both
duelists into an encounter, and the stone referees the fight and pays the pot to
whoever is left standing. A ward on the room makes the ring the only place a
swing can land.

**Concepts:** consent through a typed [`prompt()`](../reference/softcode.md#fn-prompt)
answer, scoped PvP with a room [`on_check`](../design/action-phases.md) ward over
`combat:on_attack`, escrow by owner authority (an admin-owned stone), a queued
`start_combat()`, and `ON_DEATH` as the referee's whistle.

## How it works

The finished ring has three moving parts: a ward on the room that decides whose
swings may land, a stone that runs the challenge and accept handshake and holds
the stakes, and an `ON_DEATH` reaction on that same stone that settles the bet
when someone drops. This section answers four questions: why PvP is a ward and
not a switch, why consent has to be a word the player types, why the stone can
seize other players' credits, and how the stone knows which death was its duel.

### Why PvP is a ward, not a switch

REALM has no global PvP flag, because policy is data. The ring carries a room
[`on_check`](../design/action-phases.md) that blocks any `combat:on_attack`
unless both parties carry the `duelist` tag. The `attack` command still enrolls
people in an encounter, but the ward stops the swing itself, every beat, with
the house rules as the block reason, so unsanctioned violence in the ring is all
wind-up and no contact. Outside the ring this ward does not exist, and a
consent-only game would ward its whole world the same way, with one zone-master
`on_check`. This is the [guarded exit](031_guarded_exit.md)'s idea of policy as a
readable ward, aimed at swings instead of movement.

### Why consent is a typed word

`duel <name>` stamps the pair onto the stone and
[`prompt()`](../reference/softcode.md#fn-prompt)s the challenged player. The
prompt captures that player's next line and runs the stone's `answer` attribute
with the line bound as `arg0` and the answerer bound as `enactor`. Acceptance is
therefore something the player deliberately typed, which is the point of the
consent model: a passive trigger grants nothing, only a typed answer does.
Anything other than `accept` declines and returns the gauntlet.

### Why the stone can take another player's credits

On acceptance the stone pulls the stake from both players with
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits)`(player, me,
stake)` and tags them `duelist`. Moving other players' credits and tags is
exactly what the rule "an admin-owned master may write other players' sheets"
covers, so **this build must be done by an admin character**: the stone acts
with its admin owner's authority. A mortal-owned stone could not seize the
stakes, and would instead have to make each duelist `pay` it, which is how item
114's [bounty board](114_bounty_board.md) escrows its money. The stakes ride the
same real-escrow idea as the [secure trade](096_secure_trade.md) broker: once
they are in the stone, neither duelist can touch them.

### How the stone knows which death was its duel

`start_combat(a, b)` opens the encounter, again under admin authority, because
you are throwing two players you do not own into a fight they consented to. When
a duelist drops, the engine propagates `combat:on_death` with the winner bound
as `enactor`, and the stone, standing in the room, hears it on its `ON_DEATH`
attribute
([an `ON_<EVENT>` lifecycle hook](../reference/softcode.md#lifecycle-hooks)): it
pays the pot, strips both tags, and announces the result. The loser is a player
at 0 HP, so the native defeat rule applies, which means they fall unconscious in
place rather than dying, and `firstaid` brings them back.

That `ON_DEATH` is a reactive hook, so it needs a guard, but not the usual
[`target is me`](../reference/softcode.md#guard-on-target) one. A death's target
is the fallen player, never the stone, so `target is me` would never be true
here. Instead the stone guards on its own stored duel: it fires only when the
winner (`enactor`) is one of the two ids it stamped and still carries the
`duelist` tag. Two stones in one room stay independent, because a stone with no
duel pending resolves its stored ids to nothing and stands down, exactly as the
[secure trade](096_secure_trade.md) broker keys its witnessed hooks on the
parties it is actually holding.

## Build it

Do this as an **admin**, because the stone will seize stakes and throw players
into combat, both of which need its owner's authority. First dig the ring and
step inside:

```text
@dig The Ring = ring, out
ring
```

The ring's law is one ward. It blocks a `combat:on_attack` whenever the swing is
not between two `duelist`-tagged parties, so an ordinary `attack` here enrolls
the encounter but never lands a blow:

```text
@set here/on_check = if atype == 'combat:on_attack' and not (has_tag(actor, 'duelist') and has_tag(target, 'duelist')): block('The Ring hosts sanctioned duels only -- DUEL <name> to issue a challenge.')
```

Now the stone itself, dropped in the ring, with a default stake:

```text
@create dueling stone
drop dueling stone
@desc dueling stone = A waist-high basalt block, its top hollowed into a coin bowl. DUEL <name> to put money on your grievance.
@set dueling stone/stake = 25
```

The challenge command. It is a `$`-command, so it needs no `target` guard. It
refuses a second duel while one is pending, refuses a target who is not a player
standing here, and refuses a challenge neither side can cover, then stamps the
pair and prompts the challenged player, whose next typed line runs the `answer`
attribute below:

```text
@set dueling stone/cmd_duel = $duel *:'''
t = get(trim(arg0))
s = V('stake', 25)
if V('challenged'):
    pemit(enactor, 'A duel is already in the making. Wait for it to settle.')
elif not (t and has_tag(t, 'player') and loc(t) is here and t is not enactor):
    pemit(enactor, 'They are not here to face you.')
elif credits(enactor) < s or credits(t) < s:
    pemit(enactor, 'One of you cannot cover the ' + str(s) + '-credit stake.')
else:
    set_attr(me, 'challenger', enactor.id)
    set_attr(me, 'challenged', t.id)
    remit(here, name(enactor) + ' lays a gauntlet on the dueling stone before ' + name(t) + '.')
    # prompt captures the challenged player's next line and runs 'answer'
    prompt(t, name(enactor) + ' challenges you to a duel for ' + str(s) + ' credits. Type ACCEPT to fight -- anything else declines.', 'answer')
'''
```

The `answer` attribute is a plain callback the prompt fires, so `enactor` is the
answerer and `arg0` is what they typed. Only the challenged player can settle it
(`enactor is b`). Anything but `accept` returns the gauntlet, while `accept`
escrows both stakes, tags both duelists, and starts the fight. The two
`transfer_credits` calls pull from the players by the stone's admin authority:

```text
@set dueling stone/answer = '''
a = get('#' + str(V('challenger', '')))
b = get('#' + str(V('challenged', '')))
s = V('stake', 25)
# only the challenged player's typed answer settles the duel
if a and b and enactor is b:
    if trim(arg0).lower() != 'accept':
        del_attr(me, 'challenger')
        del_attr(me, 'challenged')
        remit(here, name(b) + ' declines the duel. The gauntlet is returned.')
    else:
        transfer_credits(a, me, s)
        transfer_credits(b, me, s)
        add_tag(a, 'duelist')
        add_tag(b, 'duelist')
        remit(here, 'The stakes -- ' + str(2 * s) + ' credits -- rattle into the stone. FIGHT!')
        start_combat(a, b)
'''
```

Finally the referee. `ON_DEATH` fires on every witness in the room, so the stone
matches the winner (`enactor`) against the duel it stored rather than against
`target`, which is the fallen player. When the winner is one of its two tagged
duelists, it pays the pot, strips the tags, and clears the pending duel:

```text
@set dueling stone/on_death = '''
a = get('#' + str(V('challenger', '')))
b = get('#' + str(V('challenged', '')))
s = V('stake', 25)
w = enactor
# guard on the stored duel: the death targets the loser, never the stone
if a and b and w and (w is a or w is b) and has_tag(w, 'duelist'):
    transfer_credits(me, w, 2 * s)
    remove_tag(a, 'duelist')
    remove_tag(b, 'duelist')
    del_attr(me, 'challenger')
    del_attr(me, 'challenged')
    remit(here, name(w) + ' stands over a fallen rival. The stone pays out ' + str(2 * s) + ' credits.')
'''
```

## Try it

Unsanctioned first: walk two characters into the ring and have one type `attack`
on the other. The fight starts (beats tick, actions queue) but every swing
bounces off the ward:

```text
The Ring hosts sanctioned duels only -- DUEL <name> to issue a challenge.
```

Now the real thing. Ace challenges Bruce, and Bruce accepts by typing a word:

```text
duel Bruce            -> (room) Ace lays a gauntlet on the dueling stone before Bruce.
                         (Bruce) Ace challenges you to a duel for 25 credits. Type ACCEPT ...
(Bruce types) accept  -> The stakes -- 50 credits -- rattle into the stone. FIGHT!
```

Both are now `duelist`-tagged, the ward yields, and the encounter runs on the
ordinary beat, so `queue`, `defend`, and `pace` all work. When one falls: "...
stands over a fallen rival. The stone pays out 50 credits." The winner is 25 up,
the loser is 25 down and unconscious until someone `firstaid`s them, and the
tags are gone, so the very next punch is unsanctioned again. Declining (`no`, or
anything else) returns the gauntlet and moves no money.

**Design note (not a gap):** if a duelist flees the ring, nobody dies, so the
stone never pays out and the stakes sit in escrow until a duel concludes. Treat
fleeing as forfeit with the `ON_LEAVE` variation below.

## Going further

- **Forfeit on flight.** Add an `ON_LEAVE` to the ring room: if the leaver is a
  `duelist`, pay the pot to the other duelist and clean up, so cowardice is a
  settled bet.
- **Named stakes.** Parse `duel bruce = 100` (a second wildcard) and store the
  stake per challenge instead of on the stone.
- **First-blood rules.** Referee on `ON_DAMAGE` instead of `ON_DEATH`, so the
  first hit that lands settles the bet before anyone is carried out.
- **A betting book for the crowd.** Combine with item 115's
  [arena](115_arena_spectators.md): spectators `pay` the stone on a fighter's
  name before the first beat, and `ON_DEATH` splits the losing pool among the
  winners.
