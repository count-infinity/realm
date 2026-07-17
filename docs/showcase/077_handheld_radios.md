# 077. Handheld radios

> Checklist item 77 — [now] — *device-gated comms, search_world by attr, pemit to holders, ^listen VOX*

**What you'll build:** Field radios you can carry anywhere: `tune
<frequency>` sets the dial, `radio <message>` transmits, and every
powered radio on the same frequency hears it — into its holder's ear
if carried, out loud if sitting on a table. Plus a VOX mode: set a
radio down with the voice trigger on and it rebroadcasts everything
said in the room.

**Concepts:** **device-gated communication** (no radio in hand, no
signal), `search_world(tag=..., attr=..., value=...)` as a live
registry — the *frequency itself* is the subscriber list — `pemit()`
vs `remit()` chosen by where the receiver sits, one `xmit` subroutine
behind two entry points, and the engine's honest `^listen` boundary:
pocketed objects overhear nothing.

## How it works

**The registry is a query, not a list.** No master object tracks who
is tuned where. Transmitting runs
`search_world(tag='radio', attr='freq', value=<my freq>)` — the world
*is* the registry, and retuning a dial re-files the radio instantly.
(Compare the [custom channel](074_custom_channel.md), where
subscription is a list on a master: channels are memberships, radios
are physics.)

**Delivery depends on where the receiver sits.** For each matching
radio, `loc(r)` is either a player (carried — `pemit()` the holder
privately) or a room (set down — `remit()` so everyone near it hears
the speaker crackle). Incoming traffic is *delivered text*, not
speech, so it can never re-trigger another radio's listen trigger —
no feedback loops, by construction.

**Transmission is a `$`-command, and that's load-bearing.** `$`-verbs
are found on objects in your *inventory* as well as your room, so
`radio <message>` works from your pocket anywhere in the world. But
`^`-listen triggers scan only the room's contents — a pocketed radio
*overhears nothing* (the [voice recorder](007_voice_recorder.md)'s
rule: wiretaps must be planted). So push-to-talk is the carried
interface, and the open microphone — VOX — only exists for a radio
*set down* in a room. The build gates both honestly: `loc(me) !=
enactor` refuses the send key unless you actually hold the set.

One placement note: `$`-triggers search the room before your
inventory, so a *dropped* radio in your room answers `radio ...`
before the one in your pocket — and transmits on *its* frequency.
Two radios in one place is a scene, not a bug, but know whose mic
is hot.

## Build it

Two rooms and the first radio:

```text
@dig The Warehouse Floor = floor, out
floor
@dig The Rooftop = roof, floor
@create field radio
@desc field radio = A brick of olive plastic with a stubby antenna and a worn send key. [[result = 'The dial is set to ' + str(get_attr(me, 'freq', 'static'))]].
@tag field radio = radio
@set field radio/freq = alpha
@set field radio/power = 1
```

The shared transmitter — find every other powered radio on my
frequency, deliver by receiver placement:

```text
@set field radio/xmit = f = str(get_attr(me, 'freq', '')); [(pemit(loc(r), '[' + f + '] ' + str(arg0)) if has_tag(loc(r), 'player') else remit(loc(r), name(r) + ' crackles: [' + f + '] ' + str(arg0))) for r in search_world(tag='radio', attr='freq', value=get_attr(me, 'freq', '')) if r != me and get_attr(r, 'power', 1) and loc(r)]
```

Push-to-talk and the dial — both demand the set in hand:

```text
@set field radio/cmd_radio = $radio *: (pemit(enactor, 'Pick the radio up first; the send key is on the grip.') if loc(me) != enactor else (pemit(enactor, 'You key the mic: [' + str(get_attr(me, 'freq', '')) + '] ' + name(enactor) + ': ' + escape(arg0)), eval_attr(me, 'xmit', name(enactor) + ': ' + escape(arg0))))
@set field radio/cmd_tune = $tune *: (pemit(enactor, 'Hold the radio to work the dial.') if loc(me) != enactor else (set_attr(me, 'freq', trim(arg0)), pemit(enactor, 'You click the dial over to [' + trim(arg0) + '].')))
```

VOX — the open microphone, alive only when the radio sits in a room:

```text
@set field radio/vox = 0
@set field radio/cmd_vox = $vox *: (set_attr(me, 'vox', 1 if trim(arg0).lower() == 'on' else 0), pemit(enactor, 'You flip the VOX toggle ' + trim(arg0).lower() + '. It only matters while the set is put down somewhere.'))
@set field radio/listen_vox = ^*: eval_attr(me, 'xmit', name(enactor) + ' (open mic): ' + escape(arg0)) if enactor and get_attr(me, 'vox', 0) and get_attr(me, 'power', 1) else None
```

A second set for your partner — `@clone` copies attributes, tags,
and triggers wholesale:

```text
@clone field radio = spare radio
```

## Try it

Hand off the spare (`get spare radio`, then `give spare radio to
Zeke` — the clone lands on the ground at your feet), send Zeke to the
rooftop, keep yours on the floor. Both dials read `alpha`:

```text
radio moving in, two minutes
   -> (you)          You key the mic: [alpha] Bilda: moving in, two minutes
   -> (Zeke, roof)   [alpha] Bilda: moving in, two minutes
```

Zeke retunes — `tune beta` — and your next call finds nobody; tune
back and the net is up again. Comms are severed the moment the dials
disagree: that's the query doing the bookkeeping. Now leave a set
behind as a bug:

```text
(Zeke, roof)  vox on
(Zeke, roof)  drop spare radio
(Zeke walks down to the floor)
(anyone left on the roof) say the coast is clear
   -> (your carried radio) [alpha] Watch (open mic): the coast is clear
```

And a set lying in a room plays traffic out loud — anyone standing
near the dropped spare hears `spare radio crackles: [alpha] ...`
whenever you transmit. Try `radio hello` right after dropping yours:
the grip is out of reach, and the send key refuses.

## Going further

- **Power switch** — a `$power *` toggling the `power` attr; the
  `xmit` query already skips dark sets, so a dead radio is silent
  both ways.
- **Encryption** — frequencies are just strings: `tune 7742-scram`
  is a shared secret. Add a `scramble` attr and garble lines for
  radios missing the matching key.
- **Range** — filter the fan-out by zone: `if zones_of(loc(r)) ==
  zones_of(loc(me))` keeps traffic on-station; a repeater object
  re-`xmit`s across zones.
- **Direction finding** — every transmission could stamp
  `last_heard = name(loc(loc(r)))` on receivers; a `$triangulate`
  verb turns three radios into a plot device.
