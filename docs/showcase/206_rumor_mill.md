# 206. Rumor mill

> Checklist item 206 — [now] — *rumor attrs hopping via on_tick, ^listen pickup, decay*

**What you'll build:** a town where gossip travels on its own — seed one
NPC with a rumor and it spreads mouth to mouth on each heartbeat, every
NPC who overhears it becoming a new carrier, until the tale ages out and
is forgotten.

**Concepts:** an NPC's `on_tick` as a **gossip faucet** (speak what you
know), a `^listen` **pickup** that turns overhearers into carriers,
**NPC-to-NPC speech propagation** (a scripted `say` fires other NPCs'
listen triggers), and **decay** keyed on `now()`.

## How it works

A rumor is two attributes on an NPC: `rumor` (the text) and `rumor_at`
(when they learned it). The mill runs on three rules that every gossip NPC
shares:

- **Speak what you know.** Each `on_tick`, if the NPC carries a rumor that
  hasn't gone stale, it `say`s it with a recognizable prefix — `Word is
  <rumor>`. A scripted `say` propagates as real speech, so it reaches every
  *other* NPC's listen triggers (an object never overhears itself), exactly
  as a player's would.
- **Overhearing makes you a carrier.** A `^*word is *` listen trigger
  captures the rumor text (the trailing `*` lands as `arg1`) and — *only if
  the NPC isn't already carrying something* — stores it and stamps
  `rumor_at = now()`. The "not already carrying" guard is what keeps the
  town from thrashing: once you know a tale you keep telling *it*, you don't
  overwrite it with the next thing you hear.
- **Rumors decay.** Before speaking, the tick checks age: if `now() -
  rumor_at` exceeds the NPC's `ttl`, the rumor is *forgotten*
  (`del_attr`) instead of spoken. Old news dies; the mill goes quiet
  unless something fresh is seeded.

Put those together and a single seeded rumor ripples outward one hop per
beat, lives for a while, and fades — organic spread with no central
registry, just NPCs talking. (Keep patterns colon-free: the `:` in a
`^pattern:code` trigger separates pattern from code, so a rumor marker like
`word is` — no colon — is the safe shape.)

## Build it

Two gossips in the square. (Add as many as you like — they all run the same
three attributes.)

```text
@create Gossip Gale
@tag Gossip Gale = npc
drop Gossip Gale
@create Old Pip
@tag Old Pip = npc
drop Old Pip
@set Gossip Gale/ttl = 3
@set Old Pip/ttl = 3
```

The gossip faucet — forget-if-stale, else speak-if-known — on each NPC:

```text
@set Gossip Gale/on_tick = r = V('rumor', 0); (del_attr(me, 'rumor') if r and now() - V('rumor_at', 0) > V('ttl', 3) else (say('Word is ' + r) if r else None))
@set Old Pip/on_tick = r = V('rumor', 0); (del_attr(me, 'rumor') if r and now() - V('rumor_at', 0) > V('ttl', 3) else (say('Word is ' + r) if r else None))
```

The pickup — overhear `Word is …`, become a carrier (unless already
carrying):

```text
@set Gossip Gale/listen_rumor = ^*word is *:(set_attr(me, 'rumor', trim(arg1)), set_attr(me, 'rumor_at', now())) if not V('rumor', 0) else None
@set Old Pip/listen_rumor = ^*word is *:(set_attr(me, 'rumor', trim(arg1)), set_attr(me, 'rumor_at', now())) if not V('rumor', 0) else None
```

Give both NPCs a `script_ticker` (`@behavior Gossip Gale = script_ticker,
interval:20`) on a live server so the mill runs on its own heartbeat. Then
seed one rumor:

```text
@set Gossip Gale/rumor = the docks flood at dawn
@eval set_attr(get('Gossip Gale'), 'rumor_at', now())
```

## Try it

Force a beat instead of waiting on the clock:

```text
@tr Gossip Gale/on_tick     -> Gossip Gale says, "Word is the docks flood at dawn."
```

`@examine Old Pip` now shows `rumor = the docks flood at dawn` — she
overheard and is now a carrier. On her own next tick she'll pass it along,
and the tale walks the room. Age a carrier's copy past its `ttl`
(`@eval set_attr(get('Old Pip'), 'rumor_at', now() - 100)`) and her next
tick *forgets* it rather than repeating it — the rumor decays. Seed Pip
with a *different* rumor first and Gale's gossip won't overwrite it: a
carrier keeps its own tale.

## Going further

- **Chance, not certainty.** Wrap the `say` in `if rand(1, 3) == 1` so
  gossips spill only sometimes — the spread turns lumpy and lifelike
  instead of clockwork.
- **Mutation.** Have the pickup occasionally garble the rumor
  (`replace(arg1, 'dawn', 'midnight')`) — the tale drifts as it travels,
  telephone-game style.
- **Players seed it.** A `^*word is *` on a tavern-keeper NPC lets *players*
  start rumors just by talking near them — the mill picks up organic
  gossip.
- **Rumors with teeth.** Let a guard's listen react to a specific rumor
  (`^*the baron is poisoned*`) by raising the alarm — gossip becomes a plot
  trigger, feeding the [guard response](071_guard_response.md) master.
- **A rumor ledger.** A town crier that logs every distinct rumor it hears
  (the capped-list idiom) gives players a `news` board of what's going
  around.
