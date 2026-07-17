# 031. Guarded Exit

> Checklist item 31 — now — *guard behavior, disposition, persuade/fasttalk, wards*

**What you'll build:** Bruk, a halberdier planted in front of the feast
hall archway. He passes anyone on the guest list, anyone he's come to
like — and nobody else. Players talk, charm, or con their way past him
with the built-in social commands, and if Bruk ever leaves his post,
the archway stands open.

**Concepts:** a movement ward that consults **live NPC state** (guest
list, `disposition()`, presence, consciousness), the built-in social
layer (`consider`, `persuade`, `fasttalk`) writing the state the ward
reads, `ON_FAIL` as the guard's audible reaction — and when the stock
`guard` *behavior* is the better tool.

## How it works

**The ward reads the guard; the guard never blocks anything.** The
engine ships a `guard` behavior (`@behavior Bruk = guard, ...`) that
vetoes movement — but it guards the whole *room*, every direction. For
one archway among several exits you want the softcode ward instead: it
sits on the room (movement's gating action targets the room — an
`on_check` on the exit itself never fires for traversal), keys itself
to the archway via `adata('exit')`, and interrogates Bruk like any
other object:

- `loc(g) == me` and `not has_tag(g, 'unconscious')` — no guard, no
  gate. Lure him away or lay him out and the archway is just an arch.
  This is the difference between a lock and a *guard*: the obstacle is
  a creature with state.
- the **guest list** is an attribute on Bruk (`guest_list`, a
  comma-separated string) — reprintable at runtime with one `@set`.
- `disposition(g, actor) >= 2` — the engine's NPC-attitude scale
  (-5..+5). You don't write the diplomacy system; it ships.

**The social commands do the writing.** `persuade Bruk` is an honest
contest (persuasion vs will) worth a *permanent* +1; `fasttalk Bruk`
is fast_talk vs detect_lies for +2 that **wears off** (and a permanent
-1 if he sees through you); `consider Bruk` rolls and shows the first
impression. All of them mutate the same disposition score the ward
reads — build the gate, and the whole con-artist playbook works
against it for free.

**Wards are quiet; `ON_FAIL` is loud.** A `block()` reason is shown
only to the blocked walker. But every thwarted move also fires
`event:on_fail`, which bystanders witness — so Bruk carries an
`ON_FAIL` that *says* his line out loud, and the whole gatehouse hears
him turn someone away. Decision in the ward, theater in the reaction.

## Build it

The gatehouse, the hall, and Bruk himself — with weak social defenses
(a door greeter, not an interrogator) and a short guest list:

```text
@dig Gatehouse
@teleport me = Gatehouse
@dig Feast Hall = archway, archway
@create Bruk
@tag Bruk = npc
drop Bruk
@set Bruk/will = 8
@set Bruk/skill_detect_lies = 8
@set Bruk/guest_list = Lady Vex, Raven
@set Bruk/on_fail = say(f'The list is the list. Walk away, {name(enactor)}.')
```

The ward on the gatehouse — one long condition, read left to right:
*is this a walk, through the archway, with Bruk on post and conscious,
by someone neither listed nor liked?*

```text
@set here/on_check = g = get('Bruk'); vip = g and name(actor) in [t.strip() for t in str(get_attr(g, 'guest_list', '')).split(',')]; block('Bruk plants his halberd across the archway. "Not on the list, not inside."') if has_atag('movement') and adata('exit') == get('archway') and g and loc(g) == me and not has_tag(g, 'unconscious') and not vip and disposition(g, actor) < 2 else None
```

## Try it

As a nobody:

```text
archway             -> Bruk plants his halberd across the archway.
                       "Not on the list, not inside."
                       (and the room hears: Bruk says, "The list is the
                       list. Walk away, Mook.")
consider Bruk       -> Bruk regards you neutrally.   (your baseline)
persuade Bruk       -> maybe: Bruk nods along -- you've won some goodwill.
fasttalk Bruk       -> maybe: Bruk buys every word -- for now.
archway             -> at disposition +2, the halberd stays up: you're in
```

`persuade` sticks; `fasttalk` decays in a couple of minutes — walk in
now, because Bruk's opinion of a fast-talker reverts (and if he catches
the lie, it *drops*, permanently). A guest — anyone named on the list —
walks straight through. And the guard is a creature, not a lock:

```text
(lure Bruk off his post somehow...)
archway             -> nobody bars the way
```

## Going further

- **The whole wing off-limits** — when the answer is "nobody passes
  anywhere," skip the ward: `@behavior Bruk = guard,
  challenge_message:Halt!` blocks all movement past him, honors
  disposition, and takes `allow_tags` for uniforms.
- **Bribes** — give Bruk an `ON_PAYMENT` that bumps
  `adjust_disposition(me, enactor, 1)` per 10 credits: the
  [toll gate](030_toll_gate.md)'s machinery pointed at a heart.
- **Passphrase** — a `^*ravenfeather*:` listen trigger on Bruk that
  `adjust_disposition(me, enactor, 2)` turns the guest list into a
  secret knock.
- **Shift changes** — Bruk already wanders off duty if you move him;
  attach an [NPC schedule](068_npc_schedule.md) and the archway is only
  guarded when he's standing at it, with no changes to the ward at all.
