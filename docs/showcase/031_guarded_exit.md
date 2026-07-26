# 031. Guarded Exit

> Checklist item 31 ([now]): *guard behavior, disposition, persuade/fasttalk, wards*

**What you'll build:** Bruk, a halberdier planted in front of the feast hall
archway. He passes anyone on the guest list and anyone he has come to like, and
turns away everyone else. Players talk, charm, or con their way past him with
the built-in social commands, and if Bruk ever leaves his post the archway
stands open.

**Concepts:** a movement ward that consults live NPC state (the guest list,
[`disposition()`](../reference/softcode.md#fn-disposition), presence, and
consciousness), the built-in social layer (`consider`, `persuade`, `fasttalk`)
writing the state the ward reads,
[`ON_FAIL`](../reference/softcode.md#lifecycle-hooks) as the guard's audible
reaction, and knowing when the stock `guard` behavior is the better tool.

## How it works

An NPC stands at an archway; a ward on the room decides who may walk through by
reading that NPC's live state; three social commands rewrite the state; and a
refused attempt fires an audible reaction. This section answers four questions:
why the ward lives on the room, what makes the NPC an obstacle rather than a
lock, how a walker's standing gets high enough to pass, and why the refusal is
private while the guard's line is heard by the room.

### Why the ward lives on the room, not the exit

Movement gates on the room. When someone walks an exit, the engine fires an
`event:on_leave` action whose target is the room they are leaving, tagged
`movement` and carrying the exit in its
[action data](../reference/softcode.md#event-data-namespace). An
[`on_check`](../design/action-phases.md) ward set on the exit itself never fires
for traversal, so the ward sits on the room, reads `adata('exit')` to see which
way the walker is headed, and calls
[`block()`](../design/action-phases.md) only when that exit is the archway. The
engine also ships a `guard` behavior (`@behavior Bruk = guard, ...`) that vetoes
movement, but it guards the whole room, in every direction. For one archway
among several exits the room ward is the right tool, because it keys itself to a
single exit through `adata('exit')`.

### What makes Bruk an obstacle and not a lock

The ward interrogates Bruk like any other object. It resolves him with
[`get('Bruk')`](../reference/softcode.md#fn-get), checks that he is standing
here ([`loc(g)`](../reference/softcode.md#fn-loc) `== me`) and conscious
(`not` [`has_tag(g, 'unconscious')`](../reference/softcode.md#fn-has_tag)), then
consults two pieces of his state: his `guest_list` attribute, a comma-separated
string editable at runtime with one `@set`, and his disposition toward the
walker. Because presence and consciousness are part of the test, luring Bruk
away or knocking him out turns the archway back into an ordinary arch. That is
the difference between a lock and a guard: the obstacle is a creature with
state, so it can be moved, downed, or won over.

### How a walker's standing gets high enough to pass

[`disposition(g, actor)`](../reference/softcode.md#fn-disposition) returns how
Bruk feels about the walker on the engine's attitude scale, which runs from -5
to +5 centered on 0. The ward passes anyone he rates +2 or higher, the same
threshold the stock guard behavior uses. Three built-in commands move that
number, and none of them is code you write:

- `consider Bruk` rolls his first impression, a memoized 3d6 reaction, and names
  the attitude it lands on.
- `persuade Bruk` is an honest contest, persuasion against his `will`, worth a
  permanent +1 on success and a slight hardening on failure.
- `fasttalk Bruk` is fast_talk against his `skill_detect_lies` for +2, but that
  boost is a timed effect that wears off and reverses; if he sees through the
  lie it costs a permanent -1.

Build the gate and the whole social layer works against it for free, because
every one of those commands writes the same disposition the ward reads. The same
score drives any disposition-aware NPC, such as the
[dialogue-tree regular](067_dialogue_tree_npc.md) who clams up for people he
dislikes.

### Why the refusal is private but the guard is loud

A `block()` reason is delivered only to the walker who was stopped. But every
thwarted move also fires `event:on_fail`, and that action is
[heard by the whole room](../reference/softcode.md#guard-on-target), so Bruk
carries an [`ON_FAIL`](../reference/softcode.md#lifecycle-hooks) that says his
line aloud and the gatehouse hears him turn someone away. Note that the on_fail
action targets the archway, not Bruk, so his reaction takes no `target is me`
guard: he is a witness reacting to the exit's failure, not the thing that
failed.

## Build it

Dig the two rooms and stand Bruk in the gatehouse. `@dig Feast Hall = archway,
archway` cuts the archway both ways, and the forward face, from the gatehouse to
the hall, is the one the ward will key on:

```text
@dig Gatehouse
@teleport me = Gatehouse
@dig Feast Hall = archway, archway
@create Bruk
@tag Bruk = npc
drop Bruk
```

Give Bruk weak social defenses (a door greeter, not an interrogator) and a short
guest list. His `will` is what `persuade` fights and his `skill_detect_lies` is
what `fasttalk` fights, so low values make him easy to work:

```text
@set Bruk/will = 8
@set Bruk/skill_detect_lies = 8
@set Bruk/guest_list = Lady Vex, Raven
```

His `on_fail` says his line to the room whenever a move fails here. It is a
single statement, so it stays on one line, and `enactor` is the walker who was
just turned away:

```text
@set Bruk/on_fail = say(f'The list is the list. Walk away, {name(enactor)}.')  # on_fail targets the exit, not Bruk, so no target-is-me guard
```

Now the ward on the gatehouse, read as one question: is this a walk, through the
archway, with Bruk on post and conscious, by someone neither listed nor liked?
The walrus `(g := get('Bruk'))` binds Bruk once so the four reads that follow
share the one lookup, and the `and` chain stops early on a move through any other
exit:

```text
@set here/on_check = if has_atag('movement') and adata('exit') == get('archway') and (g := get('Bruk')) and loc(g) == me and not has_tag(g, 'unconscious') and name(actor) not in [t.strip() for t in str(get_attr(g, 'guest_list', '')).split(',')] and disposition(g, actor) < 2: block('Bruk plants his halberd across the archway. "Not on the list, not inside."')  # the leave ward runs for every exit, so this checks it is the archway
```

## Try it

As a nobody, the archway is closed and the room hears why:

```text
archway
  -> Bruk plants his halberd across the archway. "Not on the list, not inside."
     Bruk says, "The list is the list. Walk away, Mook."
```

The first line is the ward's `block()`, delivered only to you. The second is
Bruk's `on_fail`, which everyone in the gatehouse hears.

Work on his attitude. The first impression is a 3d6 roll, so the band you see
here varies, and against his `will` and `skill_detect_lies` of 8 a skilled
talker wins most contests:

```text
consider Bruk
  -> Bruk seems well-disposed toward you.     (a friendly first impression: +1)
archway
  -> Bruk plants his halberd across the archway. "Not on the list, not inside."
     (+1 is not yet +2)
persuade Bruk
  -> Bruk nods along — you've won some goodwill. (friendly)
archway
  -> You leave archway.                        (at +2 the halberd lifts)
```

`persuade` sticks: +1, permanent. `fasttalk` is the con, a +2 that wears off, so
walk in before it reverses, and if Bruk catches the lie it drops him a point for
good. From a neutral start, one fast-talk is enough on its own:

```text
fasttalk Bruk
  -> Bruk buys every word — for now. (friendly)
archway
  -> You leave archway.                        (in on borrowed goodwill)
```

A guest never needs charming, and the guard is a creature, not a lock. Anyone
named on the list walks straight through, and if Bruk is lured off his post the
archway is just an arch:

```text
archway             (as Raven, on the guest list)
  -> You leave archway.
archway             (with Bruk moved out of the gatehouse)
  -> You leave archway.                        (nobody bars the way)
```

## Going further

- **The whole wing off-limits.** When nobody passes anywhere, skip the ward:
  `@behavior Bruk = guard, challenge_message:Halt!` blocks all movement past him,
  honors disposition (friends at +2 still pass), and takes `allow_tags` so a
  uniform waves its wearer through.
- **Bribes.** Give Bruk an [`ON_PAYMENT`](../reference/softcode.md#lifecycle-hooks)
  that calls [`adjust_disposition(me, enactor, 1)`](../reference/softcode.md#fn-adjust_disposition)
  per 10 credits, guarded with `if target is me:` so only coins handed to Bruk
  count. It is the [toll gate](030_toll_gate.md)'s payment machinery aimed at his
  opinion instead of a latch.
- **Passphrase.** A `^*ravenfeather*:` listen trigger on Bruk that runs
  `adjust_disposition(me, enactor, 2)` turns the guest list into a secret knock.
- **Shift changes.** The ward already opens the archway whenever Bruk is not
  standing in it, so attach an [NPC schedule](068_npc_schedule.md) that walks him
  on and off post and the gate follows his hours with no change to the ward.
