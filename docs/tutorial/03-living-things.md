# Part 3 — Living Things

## Your first NPC

In the Cellar:

```text
@create harbor rat
@tag harbor rat = npc
@set harbor rat/hp = 3
@set harbor rat/max_hp = 3
drop harbor rat
```

It stands there. Attach a **behavior** — a reusable brain from the
engine's kit:

```text
@behavior harbor rat = wandering, pause:3
```

Wait a few beats and it skitters off through an open exit (locks and
closed doors apply to it like anyone). `@behavior/list` shows every
brain in the kit; `@behavior harbor rat` shows what's attached.

## Clone it

One rat is ambience. Three is a cellar:

```text
@clone harbor rat
@clone harbor rat
```

`@clone` copies attributes, tags, *and behaviors* — the copies wander
independently.

## Someone to talk to

On the Steps, the keeper's ghost — visible only to some:

```text
up
@create the keeper
@tag the keeper = npc
@set the keeper/description = He is thin as fog, and the lamp's ghost-light shines through him.
drop the keeper
```

Size him up: `consider the keeper` rolls his first impression of you —
and it *sticks*. NPCs remember. `persuade` and `fasttalk` move that
opinion (fast-talk wears off; getting caught costs you).

!!! info "Learn more"
    The behavior kit includes `watchful` (challenges arrivals, spots
    sneaks), `patrol`, `aggressive`, `shopkeeper`, spawners with
    respawn timers, and timed effects. Behaviors are also writable in
    softcode — next part.
