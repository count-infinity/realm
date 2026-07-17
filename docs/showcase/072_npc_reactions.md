# 072. NPC reaction emotes

> Checklist item 72 — [now] — *^listen keyword reactions, ON_EMOTE, ON_WIELD, now() cooldowns*

**What you'll build:** Nerissa, keeper of the Anchor Taproom, who
misses nothing: greet the room and she answers, talk of fighting and
she warns you off, *pose* anything and she marks you with a raised
eyebrow — but pose a *blade* and she reads the wording and says so —
and draw real steel and she is already naming it and telling you to put
it away, with a cooldown so she doesn't turn into a metronome.
**Concepts:** the three reaction surfaces an NPC has — `^listen`
(speech content), `ON_EMOTE` (someone posed, and *what* they posed via
`adata('pose')`), `ON_WIELD` (someone drew steel, and *which* steel via
`target`) — plus the `now()` cooldown-attr idiom and a disposition
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
   `ON_<EVENT>` matching is by the *action type's* suffix — so an
   `ON_EMOTE` attribute on any bystander fires whenever someone in the
   room emotes. The hook knows *who* (`enactor`) and, since the event
   namespace landed, also *what*: `adata('pose')` is the pose text.
   Nerissa uses both. Talk of blades — even in the *telling* — gets a
   word from her; anything else gets the eyebrow. That first branch is
   the interesting one, because it is the only way to read pose
   wording at all (see Engine gaps: `^listen` cannot).
3. **Weapon draws → `ON_WIELD`.** `wield` fires `item:on_wield` (a
   gated event — cursed blades can refuse, item 59's family), and
   every witness with an `ON_WIELD` attribute hears it. `enactor` is
   the one drawing and **`target` is the weapon itself** — so she can
   name what you drew rather than saying "steel" and hoping. (Note the
   shape: where an event's subject *is* the thing, it arrives as
   `target`, not in `adata` — same as `get`/`drop`. `adata` carries the
   extras a target can't express, like a pose's text.) Nerissa's
   reaction pairs the line with `adjust_disposition(me, enactor, -1)` —
   bare steel has a social price her prices and patience will remember
   (items 31/62/68 all read that number).

**The cooldown idiom** (one attr, no timers): store `now()` on
success, gate on `now() - V('<attr>', 0) > <secs>`. A
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

The pose reaction. Two branches: `adata('pose')` is the pose text, so
blade-talk gets answered on its *content*; everything else falls
through to the eyebrow, cooled down to one glance per fifteen seconds:

```
@set Nerissa/on_emote = p = adata('pose', ''); (say(f'Keep it in the story and out of my taproom, {name(enactor)}.') if 'dagger' in p or 'blade' in p or 'knife' in p else ((pose(f'glances up, marking {name(enactor)} with one raised eyebrow.'), set_attr(me, 'noticed', now())) if now() - V('noticed', 0) > 15 else None))
```

The cooldown guards only the eyebrow — the branch that would otherwise
fire on *every* pose. The blade line is rare by nature and needs no
governor.

And the weapon-draw reaction — `target` is the blade, so she names it;
words now, prices later:

```
@set Nerissa/on_wield = (say(f'That {name(target)} goes away in my taproom, {name(enactor)}. I will not ask twice.'), adjust_disposition(me, enactor, -1)) if not has_tag(enactor, 'town_watch') else None
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
pose draws his dagger slowly.
                           → "Keep it in the story and out of my
                             taproom, <you>."
```

That last one is the whole point of `adata('pose')`: she answered the
*wording*, not the gesture — and no cooldown suppressed it, because
the blade branch never went near one. Note that `^*dagger*` would
never have caught it (Engine gaps, below).

Now give her something worth noticing:

```
@create rusty cutlass      (lands in your hands)
wield rusty cutlass        → "That rusty cutlass goes away in my
                             taproom, <you>. I will not ask twice."
consider Nerissa           → cooler than she was — the -1 stuck
```

She named the blade because `target` *is* the blade. Draw a butter
knife and she says so.

## Engine gaps

One standing limit, and one that is gone — both in
`realm/scripting/engine.py`:

- **`^listen` still never hears poses.** `LISTENABLE_ACTIONS` is
  `{speech, shout, ooc, emit}`; a pose propagates as `event:emote`, so
  listen patterns cannot match emote *wording* — `pose draws his
  dagger slowly` triggers no `^*dagger*`, and no amount of pattern
  writing changes that. **The answer is the hook, not the pattern:**
  `ON_EMOTE` + `adata('pose')` reads exactly that text, which is what
  Nerissa's blade branch does. The gap is real; it is just no longer a
  dead end.
- ~~**Witnessed `ON_<EVENT>` scripts receive no action payload.**~~
  **FIXED 2026-07-17.** Witnessed triggers now get the same event
  namespace wards have: `target`, `atype`, `has_atag()`, and
  `adata(key)`. This build uses both halves — `adata('pose')` for the
  pose text, `target` for the drawn weapon.
  *One correction to the original note:* there is no
  `adata('weapon')` on `item:on_wield` — the event fires with no
  `extra`, and the weapon arrives as **`target`**. The rule of thumb:
  when the event's subject *is* the object (wield, get, drop), it is
  `target`; `adata` carries what a target cannot express (a pose's
  text, a payment's `amount`, a hit's `damage`).

## Going further

- **Escalation:** track `set_attr(me, 'warned_' + enactor.id, 1)` in
  `ON_WIELD` and have a second offense `force()` a bouncer (item 71's
  dispatch, one room deep).
- **Know a butter knife from a greatsword:** `target` is the weapon
  object, so gate the whole reaction on it —
  `if get_attr(target, 'damage', 0) > 2` — and let the harmless draw
  pass without comment. A tavern keeper who can tell a tool from a
  threat.
- **A whole mood:** key reactions on `disposition(me, enactor)` — the
  eyebrow becomes a smile for regulars she likes, a glare for the
  fasttalker whose lie wore off (item 31).
- **Unwield too:** an `ON_UNWIELD` thanking them for good sense —
  gated events come in pairs.
- **Semiposes:** `;'s dog growls` propagates `event:semipose` — an
  `ON_SEMIPOSE` attribute catches those separately if your house
  style uses them.
