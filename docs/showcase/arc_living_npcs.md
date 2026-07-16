# Arc: Living NPCs — from dumb wanderer to a town that reacts

Five tutorials that build, one layer at a time, a town whose NPCs move,
trade, remember, keep hours, and enforce the law — **all typed at a live
builder prompt, zero Python files**. Each item stands alone, but read in
order they assemble one town (dubbed *Emberwick* below) and demonstrate
the full NPC toolkit REALM ships with: stock behaviors, listen triggers,
`prompt()` conversation wizards, softcode clocks driving
`attach_behavior`/`detach_behavior`, and zone-master event witnesses.

Tutorials: items 60 → 64 → 67 → 68 → 71.
Tests: `tests/showcase/test_living_npcs.py` (drives every Build-it line
through the real dispatcher).

## The progression

| # | Tutorial | The NPC learns to... | Key REALM machinery |
|---|----------|----------------------|---------------------|
| 60 | [Wandering NPC](060_wandering_npc.md) | move on its own, within limits | built-in `wandering` behavior, `zone:` tags as a leash, `no_wander` room tags |
| 64 | [Bartender](064_bartender.md) | talk business and gossip | `^listen` keyword triggers, `ON_PAYMENT`, `create_obj()` consumables, rumor attrs |
| 67 | [Dialogue-tree NPC](067_dialogue_tree_npc.md) | hold a real conversation and remember you | `prompt()` callback chains, `eval_attr()` menus, per-player memory attrs |
| 68 | [NPC daily schedule](068_npc_schedule.md) | keep hours — work by day, sleep by night | `script_ticker` + a softcode clock, `attach_behavior`/`detach_behavior` by hour, scripted `move` |
| 71 | [Guard response](071_guard_response.md) | react to what others do | zone-master `ON_ATTACK` witnesses, `teleport_obj`/`force` responders, disposition drop |

Two axes move at once:

- **From body to mind.** Item 60 is pure locomotion. 64 adds
  transactional speech. 67 adds branching conversation *with state* —
  the NPC now knows who you are. 68 gives the NPC a life that runs
  whether or not players watch. 71 closes the loop: NPCs reacting to
  events caused by *other* participants in the world.
- **From one trigger to many.** The wanderer consumes ticks. The
  bartender overhears speech (`^listen`) and takes payments
  (`ON_PAYMENT`). Moss captures your next line (`prompt()`). Verity
  reads a clock another object maintains. The Town Watch master hears
  an `ON_ATTACK` from any room in its zone and *dispatches* — one event
  fanning out into teleports, forced commands, and attitude shifts.

## Shared foundations

Everything here rides four engine rails (see
[softcode reference](../reference/softcode.md)):

- **Behaviors** — reusable brains from the engine kit
  (`@behavior/list`): `wandering` and `shopkeeper` are used as-is;
  `script_ticker` is the escape hatch that turns any `on_tick`
  attribute into a builder-authored behavior.
- **Triggers on attributes** — `$pattern:` commands, `^pattern:`
  listens, and `ON_<EVENT>` hooks make objects programmable with
  `@set`. A key habit this arc drills: **witnessed events fire on every
  bystander** with the hook, so scripts confirm the event was theirs
  (the bartender checks her own till's balance delta before serving).
- **Authority** — scripts run as their object with its owner's power.
  NPCs mutate *their own* attrs freely, never a player's sheet; money
  moves via the real `pay` command; the zone master commands the guard
  because the same builder owns both.
- **Zones** — a `zone:town` tag on rooms plus one master object. The
  wanderer's leash (60) and the watch's ears (71) are the same tag.

## The demo town

```
                 The Loft
                    |  (upstairs/downstairs)
The Gates —— The Square —— Market Street
   (no zone)     |    \______ Guard Post
                 |     \_____ The Rusty Flagon
          Lamplight Lane
                 |
            Back Alley  (no_wander)
```

- **The scamp** (60) roams the streets but never the Back Alley — and
  never out The Gates, because the world beyond isn't zoned `town`.
- **Mira** (64) keeps The Rusty Flagon: menu on a listen trigger, ale
  served on `ON_PAYMENT`, rumors for paying patrons only.
- **Old Moss** (67) has the Flagon's corner table; `talk` to him, and
  buy him a drink before pressing the hard questions. He remembers.
- **Verity** (68) trades on Market Street from nine to nine and sleeps
  in the loft — the `shopkeeper` behavior itself is attached at opening
  and detached at closing.
- **Watchman Bren & Nettie** (71) — swing a fist on Market Street in
  front of Nettie and see how fast the watch arrives.

Every mechanism is exercised end-to-end by
`tests/showcase/test_living_npcs.py`; if that file is green, every
typed line in these five tutorials works.
