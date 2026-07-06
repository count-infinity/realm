# Part 5 — The Banshee

The lamp room. Something kept the keeper from coming down.

## Fear itself

```text
up
@create the banshee
@tag the banshee = npc
@set the banshee/hp = 8
@set the banshee/max_hp = 8
@set the banshee/points = 60
drop the banshee
@behavior the banshee = script_ticker, interval:6
@set the banshee/on_tick = [apply_effect(p, 'modifier_effect', kind='fear', duration=8, check_mods={'all': -2}, apply_msg='A keening wail freezes your blood!') for p in contents(here) if has_tag(p, 'player')]
```

Every few beats, her wail applies **fear** to everyone present: a
real, expiring condition that penalizes *every* skill roll -2 — combat,
climbing, fast-talk — automatically, until it wears off.

## Teeth

```text
@behavior the banshee = aggressive, taunt:You should not have climbed, little light.
```

Now she attacks players on sight. Combat runs on **beats** — you queue
an action each round (`attack`, `defend`, `flee`; `queue shoot` if
you've `wield`ed something ranged). Frightened characters fight worse.
Killing her pays character points (her `points` worth, split across
your party) — spend them with `improve <skill>`. Her corpse is
lootable.

## The ferryman (economy + a bribe)

Back at the Jetty, an ending:

```text
@create the ferryman
@tag the ferryman = npc
drop the ferryman
@set the ferryman/on_payment = say('Aye. I saw nothing, I row nothing.') if get_attr(me, 'credits', 0) >= 10 else say('Not for coppers, friend.')
```

`pay 10 to the ferryman` moves real money AND fires his `ON_PAYMENT`
script. Give him a shop too if you like — `@behavior the ferryman =
shopkeeper` sells whatever he's carrying, priced by `db.value` and
his *disposition* toward the buyer.

## Opening night

That's a complete one-shot: a mystery on the steps, a hidden key, a
dark cellar with teeth, a ghost who talks, a monster that frightens
and fights, treasure, and a morally flexible exit. Everything you
built persists across restarts, and none of it needed a line of
world code.

!!! info "Where to go from here"
    - **Players can't find things?** `help` is category-grouped and
      searchable (`help fear`).
    - **Bigger worlds**: spawners with respawn timers, patrols, zones —
      see the behavior kit and `examples/spacegame/nexagen.py`.
    - **Your own rules**: GameSystems swap chargen/skills/combat
      (GURPS and D20 ship in-box) — docs/design/engine_vision.md.
    - **Modern clients**: the engine speaks GMCP (room info, vitals,
      and `oob()` from softcode for custom UI panels).
