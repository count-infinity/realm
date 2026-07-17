# 072. NPC reaction emotes

> Checklist item 72 — [now] — *^listen keyword reactions, ON_EMOTE, ON_WIELD, now() cooldowns*

**What you'll build:** Nerissa, keeper of the Anchor Taproom, who
misses nothing: greet the room and she answers, talk of fighting and
she warns you off, *pose* anything and she marks you with a raised
eyebrow, draw a weapon and she is already telling you to put it away —
with a cooldown so she doesn't turn into a metronome.
**Concepts:** the three reaction surfaces an NPC has — `^listen`
(speech content), `ON_EMOTE` (someone posed), `ON_WIELD` (someone drew
steel) — plus the `now()` cooldown-attr idiom and a disposition
consequence.

## How it works

An NPC reacts to the world through the same event fabric everything
else uses; the craft is knowing which surface hears what:

1. **Speech content → `^listen`.** `listen_*` attributes fire on
   overheard *says* (and shouts and emits), with the full line
   available to the pattern — so reactions can key on *what was said*
   (`^*evening*`, `^*fight*`). Multiple patterns may fire on one
   line; she can't overhear herself.
2. **Poses → `ON_EMOTE`.** A pose propagates as `event:emote`, and
   `ON_<EVENT>` matching is by suffix — so an `ON_EMOTE` attribute on
   any bystander fires whenever someone in the room emotes. The hook
   knows *who* (`enactor`) but not *what*: the pose text isn't passed
   into witnessed event scripts (see Engine gaps). React to the
   gesture, not its content — an eyebrow, not a critique.
3. **Weapon draws → `ON_WIELD`.** `wield` fires `item:on_wield` (a
   gated event — cursed blades can refuse, item 59's family), and
   every witness with an `ON_WIELD` attribute hears it. `enactor` is
   the one drawing. Nerissa's reaction pairs the line with
   `adjust_disposition(me, enactor, -1)` — bare steel has a social
   price her prices and patience will remember (items 31/62/68 all
   read that number).

**The cooldown idiom** (one attr, no timers): store `now()` on
success, gate on `now() - get_attr(me, '<attr>', 0) > <secs>`. A
roomful of poseurs gets one eyebrow per fifteen seconds, not a
facial tic. The same guard protects any reaction that can be
spammed — it's item 71's one-alarm-per-brawl, miniaturized.

## Build it

The taproom and its keeper (from your workroom):

```
@dig The Anchor Taproom = taproom, out
taproom
@create Nerissa
@tag Nerissa = npc
drop Nerissa
@desc Nerissa = The Anchor's keeper. Nothing in this room escapes her.
```

Two content-keyed listens for speech:

```
@set Nerissa/listen_greet = ^*evening*:say Evening yourself. First one's full price, same as always.
@set Nerissa/listen_trouble = ^*fight*:say Take that talk to the alley or lose your tab.
```

The pose reaction, cooled down to one glance per fifteen seconds:

```
@set Nerissa/on_emote = (pose('glances up, marking ' + name(enactor) + ' with one raised eyebrow.'), set_attr(me, 'noticed', now())) if now() - get_attr(me, 'noticed', 0) > 15 else None
```

And the weapon-draw reaction — words now, prices later:

```
@set Nerissa/on_wield = (say('Steel away in my taproom, ' + name(enactor) + '. I will not ask twice.'), adjust_disposition(me, enactor, -1)) if not has_tag(enactor, 'town_watch') else None
```

(The `town_watch` exemption is the same filter item 71's master uses —
the law drawing a blade is not a scene.)

## Try it

```
say good evening, all      → "Evening yourself. First one's full price..."
say I hear there was a fight
                           → "Take that talk to the alley or lose your tab."
pose stretches and cracks his knuckles.
                           → Nerissa glances up, marking you with one
                             raised eyebrow.
pose whistles innocently.  → nothing — the cooldown attr holds
                             (wait fifteen seconds and pose again: eyebrow)
```

Now give her something worth noticing:

```
@create rusty cutlass      (lands in your hands)
wield rusty cutlass        → "Steel away in my taproom, <you>. I will
                             not ask twice."
consider Nerissa           → cooler than she was — the -1 stuck
```

## Engine gaps

Two precise limits, both in `realm/scripting/engine.py`:

- **`^listen` never hears poses.** `LISTENABLE_ACTIONS` is
  `{speech, shout, ooc, emit}`; a pose propagates as `event:emote`,
  so listen patterns cannot match emote *wording* (`pose draws his
  dagger slowly` triggers no `^*dagger*`).
- **Witnessed `ON_<EVENT>` scripts receive no action payload.** The
  trigger runs with `enactor` bound but captures empty and no access
  to the action's extras — `ON_EMOTE` can't read the pose text, and
  `ON_WIELD` can't tell a butter knife from a greatsword (an
  `adata()`-style accessor exists only in `on_check` wards). Content-
  keyed emote/wield reactions are blocked until an event-payload
  surface exists.

## Going further

- **Escalation:** track `set_attr(me, 'warned_' + enactor.id, 1)` in
  `ON_WIELD` and have a second offense `force()` a bouncer (item 71's
  dispatch, one room deep).
- **A whole mood:** key reactions on `disposition(me, enactor)` — the
  eyebrow becomes a smile for regulars she likes, a glare for the
  fasttalker whose lie wore off (item 31).
- **Unwield too:** an `ON_UNWIELD` thanking them for good sense —
  gated events come in pairs.
- **Semiposes:** `;'s dog growls` propagates `event:semipose` — an
  `ON_SEMIPOSE` attribute catches those separately if your house
  style uses them.
