# 159. Group travel

> Checklist item 159 — now — *the native follow/party system, follower cascade, loop safety, an NPC escort via softcode*

**What you'll build:** Nothing, almost — because REALM already ships
group travel. This is the tour: `follow` someone and you walk exits
after them; `party` shows your band; chains cascade so a whole column
moves as one; and an NPC guide agrees to fall in with a single
`$`-command. The only thing you *build* is Wend, a scout who joins your
party when asked.

**Concepts:** the built-in `follow` / `unfollow` / `party` commands; the
**follower cascade** and its **loop safety**; the one-attribute follow
model (`db.following`) that lets *anything* — a pet, a mount, an NPC —
opt into your party from softcode.

## How it works

**Following is one attribute.** A follower carries `db.following = <the
leader's id>`. When the leader walks an exit, everything in the room
whose `following` names them walks after — and the scan is *room-local*,
so chains cascade (A leads B leads C, all move) and cycles can't loop
forever (A follows B follows A resolves in one pass: the mover has
already left the room being scanned). Blocked, unconscious, or
mid-combat followers stay behind — each takes the exit on their *own*
merits, so a locked gate or a guard judges them individually.

**Players use verbs; anything else writes the attribute.** `follow
Alice` sets your `following`; `party` reads the connected follow-chains
in your room; `unfollow` clears it. An NPC can't be *told* to follow by
a stranger — but it can *decide* to, by setting its own `following` in a
`$`-command it chooses to answer. That's the whole escort quest: a
prisoner, a hireling, a guide who says "lead on" and falls in. It runs
as the NPC, mutating only itself, so it's never a way to hijack someone
else's followers.

## Build it

A short road, and Wend the guide standing at the Camp:

```text
@dig The Camp
@teleport me = The Camp
@dig The Old Bridge = north, south
@teleport me = The Camp
@create Wend the guide
@tag Wend the guide = npc
@desc Wend the guide = A weathered scout who knows the passes. ESCORT to have her fall in behind you; HALT WEND to send her to wait.
drop Wend the guide
@set Wend the guide/cmd_escort = $escort: (set_attr(me, 'following', enactor.id), pose('shoulders her pack and falls in behind ' + name(enactor) + '.'))
@set Wend the guide/cmd_halt = $halt wend: (del_attr(me, 'following'), pose('plants her staff and waits.')) if get_attr(me, 'following') == enactor.id else pemit(enactor, 'Wend is not yours to command.')
```

That's it — the rest is the engine's.

## Try it

Bring a friend to the Camp. They follow you, Wend joins, and the whole
band crosses the bridge in one step:

```text
(Bob)   follow Alice     -> You fall in behind Alice.
(Alice) escort           -> Wend shoulders her pack and falls in behind Alice.
(Alice) party            -> Your party:
                              Alice (you)
                              Bob — following Alice
                              Wend the guide — following Alice
(Alice) north            -> Alice crosses; Bob and Wend cross right after.
```

Everyone lands on The Old Bridge together. `halt wend` on the far side
and she stops travelling with you (and only *you* can — she checks who's
leading her). Have Bob `follow Wend` while Wend follows Alice: a
three-deep column that still moves in one `north`, and a mischievous
`follow` back up the chain just resolves — the cascade is loop-proof by
construction.

## Going further

- **A caravan master:** an NPC with a `$caravan` that walks its room and
  sets `following` on every `npc`-tagged creature present — muster a
  whole train with one word (the bulk pattern from
  [tutorial 149](149_maintenance_sweeper.md)).
- **Escort quests:** Wend's `ON_ARRIVE` can check `name(here)` and pay
  out when she reaches the destination — deliver-the-NPC as content
  ([tutorial 094](094_job_board.md) for the board that offers it).
- **Leashed pets and mounts:** the [pet](065_pet.md) and
  [mount](158_mounts.md) both ride this same `following` attribute — they
  already show up in `party`, because a party is just the follow graph.
- **Break on danger:** fleeing combat drops you from the column (you
  escape alone); lean into it with a rule that scatters a party when its
  leader is ambushed.
