# 050. Tripwire Alarm

> Checklist item 50 — [now] — *ON_ENTER, pemit(owner(me)), remote notification*

**What you'll build:** A hair-thin wire across a stockroom doorway that
sends its owner a silent, cross-room alert every time someone crosses
the room — the intruder never knows. A `search` finds the wire; a found
wire is stepped over.

**Concepts:** witnessed `ON_ENTER` as a proximity trigger, `pemit()` as
cross-room delivery (no shared room required), `owner(me)` as a standing
return address, the `invisible` + `conceal_difficulty` concealment kit,
and a counter attribute as trap memory.

## How it works

Three engine seams, one line of consequence each:

1. **The wire hears arrivals for free.** When anything moves into a
   room, the arrival propagates as `event:on_enter` and *every object in
   the room witnesses it* — the mover bound as `enactor`. An object
   lying on the floor with an `on_enter` attribute is a sensor; no
   polling, no code on the room. This is the same witnessed-trigger
   shape as the landmine (item 49) — but where the mine answers an
   arrival with a bang, the wire answers with a whisper.

2. **The alert is a `pemit()`.** `pemit()` delivers to a named target
   *anywhere in the world* — it is the cross-room primitive (the camera
   in item 54 is built on the same fact). And the target writes itself:
   `owner(me)` is whoever built the wire, looked up fresh on every trip,
   so the alarm keeps reporting to you even if you move, and reports to
   the buyer if you ever give the wire away.

3. **Silence is just the absence of a message.** Softcode only says
   what you tell it to say. The intruder's branch of the script does
   nothing at all — they walk through a perfectly ordinary room. That
   asymmetry (you know, they don't) is the entire value of a tripwire.

The concealment kit (`invisible` tag + `conceal_difficulty`) is the same
one the secret door and the landmine use, so the built-in `search`
command finds tripwires with no extra wiring. The script's first branch
honors the reveal: a *visible* wire is stepped over, and steps that are
seen send no alert — knowledge is safety, on both sides of the wire.

The owner-exemption (`enactor != owner(me)`) matters for the same reason
it does on the mine: triggers fire for *everyone*, including you while
you decorate. A burglar alarm that pages you about yourself trains you
to ignore it.

## Build it

Two rooms — your shop, and the stockroom worth guarding:

```text
@dig The Curio Shop = shop, out
shop
@dig The Stockroom = stockroom, shop
```

The wire goes in the stockroom. Ordinary attributes hold its state:
`armed` is the master switch, `trips` the running count.

```text
stockroom
@create tripwire
drop tripwire
@desc tripwire = A hair-fine wire at ankle height, easy to miss.
@set tripwire/armed = 1
@set tripwire/conceal_difficulty = 2
@set tripwire/reveal_msg = A glint at ankle height -- a wire, stretched taut across the doorway!
```

The trigger. Branches, in order: ignore non-characters, the disarmed
state, and the owner; step politely over a wire that has been found;
otherwise count the crossing and page the owner — and say nothing to
the walker:

```text
@set tripwire/on_enter = x = enactor; (None if not (V('armed', 0) and (has_tag(x, 'player') or has_tag(x, 'npc')) and x != owner(me)) else (pemit(x, 'You step over the exposed tripwire.') if not has_tag(me, 'invisible') else (incr('trips'), pemit(owner(me), f'[tripwire] {name(x)} crossed {name(loc(me))}.'))))
```

Hide it last, so you can see it while you work, and go mind the shop:

```text
@tag tripwire = invisible
shop
```

## Try it

Stand in the Curio Shop and have someone else walk into the stockroom:

```text
(they type: stockroom)
you see:              [tripwire] Zeke crossed The Stockroom.
they see:             (the ordinary room, nothing else)
```

Every crossing pages you, wherever you are — `pemit()` does not care
about distance. The intruder's screen stays clean. Their way out:

```text
(they type: search)   -> A glint at ankle height -- a wire, stretched taut across the doorway!
(they leave and re-enter)
they see:             You step over the exposed tripwire.
you see:              (nothing -- a seen wire reports nothing)
```

Back home, `@examine tripwire` shows `trips` ticking up — the wire
remembers even when you were asleep for the page.

## Going further

- **A bell instead of a page** — swap the `pemit()` for
  `remit(get('The Curio Shop'), 'A tiny bell over the counter jumps.')`
  and the alarm becomes diegetic: anyone minding the shop hears it,
  not just you.
- **Subscriber list** — replace `owner(me)` with a `watchers` list
  attribute and a `$subscribe` command, exactly like the security
  monitor's opt-in list in item 54: a whole guild on one wire.
- **Direction sense** — add a matching `on_leave` that pages
  `f'... left {name(loc(me))}'`; enter-without-leave means they are
  still inside. (Item 55 builds a full log on this.)
- **Re-hiding** — a `$reset wire` command for the owner:
  `add_tag(me, 'invisible')` and the stepped-over wire is a trap again.
