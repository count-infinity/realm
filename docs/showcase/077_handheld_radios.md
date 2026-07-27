# 077. Handheld radios

> Checklist item 77 ([now]): *device-gated comms, search_world by attr, pemit to holders, ^listen VOX*

**What you'll build:** Field radios you can carry anywhere. `tune <frequency>`
sets the dial, `radio <message>` transmits, and every powered radio on the same
frequency hears it: into its holder's ear if the set is carried, out loud if it
sits on a table. A VOX mode adds an open microphone, so a radio set down with the
voice trigger on rebroadcasts everything said in the room.

**Concepts:** device-gated communication (no radio in hand, no signal),
[`search_world(tag=..., attr=..., value=...)`](../reference/softcode.md#fn-search_world)
as a live registry where the frequency itself is the subscriber list,
[`pemit()`](../reference/softcode.md#fn-pemit) versus
[`remit()`](../reference/softcode.md#fn-remit) chosen by where the receiver sits,
one `xmit` subroutine behind two entry points, and the engine's honest `^listen`
boundary, where a pocketed object overhears nothing.

## How it works

The finished device is a self-contained object that carries every radio command
and needs no master. Transmitting runs one world query to find its peers, then
delivers a line to each by looking at where that peer stands. This section
answers four questions: where the subscriber list lives, how one line reaches the
right radio, why you can talk from your pocket but cannot eavesdrop from it, and
whether the voice trigger needs a guard.

### Where does the subscriber list live?

Nowhere, because it is a query rather than a stored list. No master object tracks
who is tuned where. Transmitting runs
[`search_world(tag='radio', attr='freq', value=<my freq>)`](../reference/softcode.md#fn-search_world),
so the world itself is the registry and retuning a dial re-files the radio
instantly. Compare the [custom channel](074_custom_channel.md), where a
subscription is a row on a master object that the builder must add and remove:
channels are memberships, whereas radios are physics.

### How does one line reach the right radio?

For each matching radio, [`loc(r)`](../reference/softcode.md#fn-loc) is either a
player (the set is carried) or a room (the set is put down). A carried radio gets
[`pemit(loc(r), line)`](../reference/softcode.md#fn-pemit), which delivers
privately to the holder wherever the holder stands. A radio on the ground gets
[`remit(loc(r), ...)`](../reference/softcode.md#fn-remit), so everyone near it
hears the set crackle. The two cases are told apart with
[`has_tag(loc(r), 'player')`](../reference/softcode.md#fn-has_tag), since a player
carries the `player` tag and a room does not.

Both `pemit` and `remit` are plain delivered text, not speech, so incoming
traffic can never re-trigger another radio's listen trigger. That is what makes
the open microphone safe from feedback: a radio that rebroadcasts room speech
uses `remit`, and `remit` does not itself count as room speech, so no loop can
form. The [voice recorder](007_voice_recorder.md) relies on the same rule for its
playback.

### Why can I talk from my pocket but not eavesdrop from it?

Because `$`-commands and `^`-listen triggers search different sets of objects.
The `$radio <message>` command is found on objects in your inventory as well as
your room, so `radio ...` works from your pocket anywhere in the world. A
`^`-listen trigger, though, scans only the room's own contents, never anyone's
inventory (the [voice recorder](007_voice_recorder.md)'s rule: a wiretap must be
planted, not carried). So push-to-talk is the carried interface, and the open
microphone only exists for a radio put down in a room. The build gates both ends
honestly: [`loc(me) is not enactor`](../reference/softcode.md#fn-loc) refuses the
send key and the dial unless you actually hold the set.

One placement note follows from the search order. The `$`-trigger search reads
the room's contents before your inventory and stops at the first match, so a
radio lying on the floor of your room answers `radio ...` before the one in your
pocket does. Because that grounded set is not in your hand, its own gate refuses
you with "Pick the radio up first", so the set you are holding never gets a turn.
Two radios in one place is a scene to stage-manage, not a bug: pick up the loose
one or step away from it before you key your own mic.

### Does the voice trigger need a guard?

No, and the reason is worth stating because a reactive
[`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook would. An
`ON_<EVENT>` hook fires on every object in the room, so one that reacts to its own
business must open with `if target is me:` (see
[Guard on `target`](../reference/softcode.md#guard-on-target)). This build has no
such hook. Its only reactive tap is a `^`-listen trigger, and listen dispatch
already excludes the speaker and scopes each trigger to its own object through
`me`, so the voice trigger reads its own `vox` and `power` flags and needs no
`target` guard. Confirmed with two VOX radios put down in one room: each relays
the line once through plain `remit`, so the room hears a double transmission but
no infinite loop forms, because delivered text is not speech.

## Build it

Start with two rooms and step onto the Warehouse Floor. `@dig` builds the room
and both exits at once:

```text
@dig The Warehouse Floor = floor, out
floor
@dig The Rooftop = roof, floor
```

Create the first radio (it lands in your hands), describe it with a live dial
readout, tag it so the transmitter query can find it, and set its starting
frequency and power:

```text
@create field radio
@desc field radio = A brick of olive plastic with a stubby antenna and a worn send key. [[result = f"The dial is set to {V('freq', 'static')}"]].
@tag field radio = radio
@set field radio/freq = alpha
@set field radio/power = 1
```

The `xmit` subroutine is the shared transmitter. It reads its own frequency, then
walks every powered radio on that frequency (skipping itself and any set with no
location), and delivers by placement: privately to a holder, or out loud to a
room:

```text
@set field radio/xmit = '''
f = str(V('freq', ''))
for r in search_world(tag='radio', attr='freq', value=V('freq', '')):
    if r is not me and get_attr(r, 'power', 1) and loc(r):
        line = f'[{f}] {arg0}'
        if has_tag(loc(r), 'player'):  # loc is a player: the set is carried
            pemit(loc(r), line)
        else:  # loc is a room: the set is put down, so everyone near it hears
            remit(loc(r), f'{name(r)} crackles: {line}')
'''
```

Push-to-talk keys the mic. It refuses unless the set is in your hand, otherwise it
echoes your own transmission and hands the line to `xmit`:

```text
@set field radio/cmd_radio = '''
$radio *:
if loc(me) is not enactor:  # a grounded set has no holder to key its mic
    pemit(enactor, 'Pick the radio up first; the send key is on the grip.')
else:
    pemit(enactor, f"You key the mic: [{V('freq', '')}] {name(enactor)}: {escape(arg0)}")
    eval_attr(me, 'xmit', f'{name(enactor)}: {escape(arg0)}')
'''
```

The dial demands the set in hand too, and writes the new frequency with
[`set_attr`](../reference/softcode.md#fn-set_attr), which re-files the radio in
the frequency query on the spot:

```text
@set field radio/cmd_tune = '''
$tune *:
if loc(me) is not enactor:
    pemit(enactor, 'Hold the radio to work the dial.')
else:
    set_attr(me, 'freq', trim(arg0))
    pemit(enactor, f'You click the dial over to [{trim(arg0)}].')
'''
```

VOX is the open microphone. Start it off, and let a `$vox on` / `$vox off`
command toggle it:

```text
@set field radio/vox = 0
@set field radio/cmd_vox = '''
$vox *:
on = trim(arg0).lower() == 'on'
set_attr(me, 'vox', 1 if on else 0)
pemit(enactor, f'You flip the VOX toggle {trim(arg0).lower()}. It only matters while the set is put down somewhere.')
'''
```

The voice trigger is a `^`-listen that fires on room speech. While VOX and power
are both up it feeds the line straight to `xmit`, so a set left in a room becomes
a bug. It takes no `target` guard because listen dispatch already skips the
speaker and scopes the trigger to `me`:

```text
@set field radio/listen_vox = '''
^*:
if enactor and V('vox', 0) and V('power', 1):
    eval_attr(me, 'xmit', f'{name(enactor)} (open mic): {escape(arg0)}')
'''
```

A second set for your partner. `@clone` copies attributes, tags, and triggers
wholesale, and the clone lands in the room at your feet:

```text
@clone field radio = spare radio
```

## Try it

Hand off the spare (`get spare radio`, then `give spare radio to Zeke`), send Zeke
to the rooftop, and keep your own set in hand on the floor. Both dials read
`alpha`:

```text
radio moving in, two minutes
   -> (you)          You key the mic: [alpha] Bilda: moving in, two minutes
   -> (Zeke, roof)   [alpha] Bilda: moving in, two minutes
```

Zeke retunes with `tune beta`, and your next call finds nobody; retune back and
the net is up again. Comms are severed the moment the dials disagree, which is the
query doing the bookkeeping rather than any stored membership. Now leave a set
behind as a bug:

```text
(Zeke, roof)  vox on
(Zeke, roof)  drop spare radio
(Zeke walks down to the floor)
(anyone left on the roof) say the coast is clear
   -> (your carried radio) [alpha] Watch (open mic): the coast is clear
```

A set lying in a room also plays ordinary traffic out loud, so anyone standing
near the dropped spare hears `spare radio crackles: [alpha] ...` whenever you
transmit. Try `radio hello` right after dropping your own set: the grip is out of
reach, and the send key refuses with "Pick the radio up first".

## Going further

- **Power switch:** a `$power *` toggling the `power` attr. The `xmit` query
  already skips dark sets, so a dead radio is silent both ways.
- **Encryption:** frequencies are just strings, so `tune 7742-scram` is a shared
  secret. Add a `scramble` attr and garble lines for radios missing the matching
  key.
- **Range:** filter the fan-out by zone, keeping
  [`zones_of(loc(r)) == zones_of(loc(me))`](../reference/softcode.md#fn-zones_of)
  so traffic stays on-station, and let a repeater object re-`xmit` across zones.
- **Direction finding:** stamp `last_heard = name(loc(loc(r)))` on receivers with
  every transmission, and a `$triangulate` verb turns three radios into a plot
  device.
