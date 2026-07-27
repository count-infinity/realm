# 159. Group travel

> Checklist item 159 ([now]): *follow/lead so parties move as one, follower cascade*

**What you'll build:** Almost nothing, because REALM already ships group travel.
This is the tour: `follow` someone and you walk exits after them, `party` shows
your band, chains cascade so a whole column moves as one, and an NPC guide falls
in with a single `$`-command. The one thing you *build* is Wend, a scout who
joins your party when asked.

**Concepts:** the built-in `follow` / `unfollow` / `party` commands, the
follower cascade and its loop safety, and the one-attribute follow model
(`db.following`) that lets a pet, a mount, or an NPC opt into your party from
softcode by writing a single attribute with
[`set_attr`](../reference/softcode.md#fn-set_attr).

## How it works

Group travel is a graph problem the engine already solves. Every follower stores
one attribute naming its leader, and when the leader walks an exit the engine
scans the room they left and sends the followers after them. That single scan,
applied at each step of a cascade, gives you columns, branching bands, and cycle
safety for free. This section answers two questions: what state a party actually
is, and why an NPC may join a party but a stranger may not drag it around.

### What is a party, really?

A follower carries `db.following = <the leader's id>`. When the leader walks an
exit, everything in the room whose `following` names them walks after, and the
scan is *room-local*: it looks only at the room the leader just left. That one
rule buys two behaviors at once. Chains cascade, because moving a follower is
itself a walk that triggers its own scan, so A leads B leads C and all three
move in one step. Cycles resolve in a single pass, because the mover has already
left the room being scanned, so A follows B follows A settles instead of
recursing forever. Blocked, unconscious, or mid-combat followers stay behind:
each one takes the exit on its *own* merits, so a locked gate or a guard judges
them individually.

A `party` is just the connected piece of that follow graph inside your room.
There is no party object and no invitations. `follow Alice` sets your
`following`, `party` reads the connected follow chains among everyone present,
and `unfollow` clears your `following`. Because the state is one ordinary
attribute, anything that writes it joins the graph, which is exactly how the
[pet](065_pet.md) walks with you.

### How the guide joins without being hijacked

A stranger has no way to *make* an NPC follow, but the NPC may *decide* to, by
setting its own `following` inside a `$`-command it chooses to answer (see
[triggers](../reference/softcode.md#triggers-attributes-on-objects)). That is
the whole escort quest: a prisoner, a hireling, or a guide who says "lead on"
and falls in. The command runs *as the NPC*, so `set_attr(me, 'following', ...)`
mutates only itself, which means it is never a way to seize someone else's
followers. The halt half of the pair checks who is leading the NPC before it
lets anyone stand her down, so only her current leader may send her to wait.

## Build it

This is a world-zone build in the sense that the road and the guide live in
ordinary rooms; there is no master object involved. Dig a short road and stand
Wend at the Camp:

```text
@dig The Camp
@teleport me = The Camp
@dig The Old Bridge = north, south
@create Wend the guide
@tag Wend the guide = npc
@desc Wend the guide = A weathered scout who knows the passes. ESCORT to have her fall in behind you; HALT WEND to send her to wait.
drop Wend the guide
```

The escort command is Wend agreeing to be led. It writes her own `following` to
name whoever spoke, then poses with that leader's
[`name`](../reference/softcode.md#fn-name), so from that step on the engine
walks her after that leader:

```text
@set Wend the guide/cmd_escort = '''
$escort:
set_attr(me, 'following', enactor.id)  # me is Wend: she only ever writes her own following
pose(f'shoulders her pack and falls in behind {name(enactor)}.')
'''
```

Halt is the inverse, gated on ownership. It compares her stored `following`
against the speaker with [`V`](../reference/softcode.md#fn-v), and only her
current leader clears it with
[`del_attr`](../reference/softcode.md#fn-del_attr); anyone else is turned away
with [`pemit`](../reference/softcode.md#fn-pemit):

```text
@set Wend the guide/cmd_halt = '''
$halt wend:
if V('following') == enactor.id:   # only the leader she is actually following may stand her down
    del_attr(me, 'following')
    pose('plants her staff and waits.')
else:
    pemit(enactor, 'Wend is not yours to command.')
'''
```

That is the entire build; the following, the cascade, and the party listing are
the engine's.

## Try it

Bring a friend to the Camp. They follow you, Wend joins, and the whole band
crosses the bridge in one step:

```text
follow Alice     (as Bob)   -> You fall in behind Alice.
escort           (as Alice) -> Wend shoulders her pack and falls in behind Alice.
party            (as Alice) -> Your party:
                                 Alice (you)
                                 Bob following Alice
                                 Wend the guide following Alice
north            (as Alice) -> Alice crosses; Bob and Wend cross right after.
```

Everyone lands on The Old Bridge together. Type `halt wend` on the far side and
she stops travelling with you, and only *you* may stop her, because she checks
who is leading her first. Have Bob `follow Wend` while Wend follows Alice for a
three-deep column that still moves in one `north`, and a mischievous `follow`
back up the chain simply resolves, because the cascade is loop-proof by
construction.

## Going further

- **A caravan master:** an NPC with a `$caravan` command that walks its room and
  sets `following` on every `npc`-tagged creature present, mustering a whole
  train with one word (the bulk pattern from
  [tutorial 149](149_maintenance_sweeper.md)).
- **Escort quests:** Wend's [`ON_ARRIVE`](../reference/softcode.md#lifecycle-hooks)
  hook can check `name(here)` and pay out when she reaches the destination,
  making deliver-the-NPC into content (see
  [tutorial 094](094_job_board.md) for the board that offers it).
- **A led pet or mount:** the [pet](065_pet.md) rides this same `following`
  attribute, so it shows up in `party` because a party is just the follow graph;
  a [mount](158_mounts.md) instead carries you by containment, and its led-mount
  variation opts a pack animal into `following` the very way Wend does here.
- **Break on danger:** fleeing combat drops you from the column, since a flee
  breaks the cascade and you escape alone; lean into it with a rule that
  scatters a party when its leader is ambushed.
