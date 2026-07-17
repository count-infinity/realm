# 204. GM possession tools

> Checklist item 204 — [now] — *@force, control locks, puppet forwarding*

**What you'll build:** the staff toolkit for running a live scene through
an NPC — speak and act as Baron Haldor with `@force`, see through his eyes
via forwarded output, and hand a trusted player a signet ring that lets
*them* drive the Baron without staff powers.

**Concepts:** `@force` through the **real dispatcher** (seamless
attribution — the room sees the NPC, not you), **output forwarding** back
to the puppeteer, the **player-level ceiling** on a forced body, and a
softcode `force()` **relay** gated by a `use` lock for handing possession
to trusted players.

## How it works

`@force <target> = <command>` runs a command **as** the target through the
same dispatcher a player types into — real parsing, real permission
checks, real propagation. That's what makes it a GM tool rather than a
narration trick, and it's the same machinery the [puppet](066_puppet.md)
tutorial dissects; this one is about *using* it to run a scene.

Two properties matter at the table:

- **Attribution is seamless.** `@force Baron Haldor = say Kneel.` produces
  `Baron Haldor says, "Kneel."` in the room — the players hear the *Baron*,
  never the GM behind him. And what the body perceives is forwarded back to
  you, prefixed with its name: `@force Baron Haldor = look` prints
  `[Baron Haldor] The Throne Room ...` to your screen. You see through his
  eyes without ever standing in the room.
- **A forced body has its own hands.** The dispatcher checks the *Baron's*
  permissions, and an NPC rates as a PLAYER — so `@force Baron Haldor =
  @dig ...` is refused. Possession never escalates privilege; you can only
  ever do *less* through a body than a builder can do directly. (This is
  why GMing through NPCs is safe to hand out: the NPC can't build, ban, or
  teleport the world.)

**Handing the reins to a player** uses the softcode twin, `force()`, with
its authority resolved by `controls()`. A signet ring, admin-owned, runs
`force('Baron Haldor', arg0)` — so whoever passes the ring's `use` lock
types `act <command>` and the Baron obeys, driven by a player who has no
staff powers of their own. The `use` lock (`caller.has_tag('steward')`) is
the entire permission surface: tag your co-GM a steward and the ring works
in their hands; untag them and it goes inert.

## Build it

The NPC you'll wear as a body:

```text
@create Baron Haldor
@tag Baron Haldor = npc
drop Baron Haldor
@desc Baron Haldor = A stout man in a fur-trimmed robe, eyes flicking to the door.
```

That's all `@force` needs — possession is authority, not machinery. Now
the delegation tool: a signet ring that relays commands to the Baron,
gated to stewards:

```text
@create signet ring
@set signet ring/cmd_act = $act *:force('Baron Haldor', arg0)
@lock/use signet ring = caller.has_tag('steward')
drop signet ring
```

## Try it

As staff, run the Baron live:

```text
@force Baron Haldor = say Kneel before your Baron.
                                -> Baron Haldor says, "Kneel before your Baron."
                                   (the room hears the Baron, not you)
@force Baron Haldor = look      -> [Baron Haldor] The Throne Room
                                   [Baron Haldor] A stout man in a fur-trimmed robe...
@force Baron Haldor = @dig Vault
                                -> [Baron Haldor] Permission denied.
                                   (a body has player-level hands)
```

Now hand a co-GM the ring. Tag them `@tag Wren = steward`, and from then on
`act say The court is in session.` makes the Baron speak — the ring drives
him with the player's authority delegated through its admin owner, but only
because the `use` lock admits a steward. Untag them and `act` goes silent.

## Going further

- **A whole cast.** One GM can `@force` any NPC in the scene, switching
  bodies line by line — Baron, herald, guard — without ever appearing as
  themselves. Keep a `$speak <npc> = <line>` verb on a GM wand that
  `force(get(arg0), 'say ' + arg1)` to make cast-switching one command.
- **Possess a player, with consent.** `@force` on a *player* only works if
  they set a control lock (`@lock/control me = caller.has_tag('mesmerist')`)
  — possession of a PC is opt-in and revocable by its owner (the
  [puppet](066_puppet.md) consent model).
- **Emote, not just speak.** `@force Baron Haldor = pose steeples his
  fingers.` drives body language too — everything the dispatcher accepts,
  the body can do.
- **Sensory-only.** A `$peer` verb that `force(me, 'look')` from a scrying
  bowl gives staff remote eyes on a room without a body in it (the
  [security camera](054_security_camera.md) with GM authority).
