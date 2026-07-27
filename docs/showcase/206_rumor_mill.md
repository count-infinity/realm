# 206. Rumor mill

> Checklist item 206 ([now]): *rumor attrs hopping via on_tick, ^listen pickup, decay*

**What you'll build:** a town where gossip travels on its own. Seed one
NPC with a rumor and it spreads mouth to mouth on the world heartbeat,
every NPC who overhears it becoming a new carrier, until the tale ages
out and is forgotten.

**Concepts:** an NPC's
[`on_tick`](../reference/softcode.md#lifecycle-hooks) as a gossip faucet
that speaks what the NPC knows, a
[`^listen`](../reference/softcode.md#triggers-attributes-on-objects)
pickup that turns overhearers into carriers (the same ears the
[voice recorder](007_voice_recorder.md) and the
[trivia host](102_trivia_host.md) use), NPC-to-NPC propagation because a
scripted [`say`](../reference/softcode.md#script-commands-simple-scripts-cmd-output-lines)
is real speech, and decay keyed on
[`now()`](../reference/softcode.md#fn-now).

## How it works

The finished mill is two ordinary NPCs standing in a room, each carrying
the same three attributes: a `ttl` number, an `on_tick` script that
speaks, and a `listen_rumor` trigger that listens. A rumor itself is just
two more attributes that appear and disappear as the tale travels,
`rumor` (the text) and `rumor_at` (the moment this NPC learned it). Add a
tenth gossip and nothing changes structurally, because there is no
registry and no coordinator anywhere: the town's behavior is the sum of
NPCs talking. This section answers four questions in the order you will
hit them, which are what makes a gossip talk, how a listener becomes a
carrier, how fast a tale actually travels, and what finally kills it.

### What makes a gossip talk?

The [`script_ticker`](../reference/softcode.md#lifecycle-hooks) behavior
runs an object's `on_tick` attribute on a cadence, so `on_tick` is where
the talking lives. When the NPC is carrying a fresh rumor it calls
[`say`](../reference/softcode.md#script-commands-simple-scripts-cmd-output-lines)
with a recognizable prefix, `Word is <rumor>`, and when it is carrying
nothing the tick does nothing at all and the NPC stands there quietly.

The behavior's `interval` counts **world beats**, not seconds, and a beat
is `world_beat` (4 seconds by default), so `interval:2` fires roughly
every eight seconds. That number and the `ttl` number below are measured
in different units, which is the one arithmetic trap in this build: keep
`ttl` comfortably larger than an interval or every tick will find its own
rumor already stale and the town will never say a word.

### How does a listener become a carrier?

Speech propagates to the room, and a
[`^pattern:code`](../reference/softcode.md#triggers-attributes-on-objects)
attribute fires when the pattern matches something overheard there. The
pickup pattern is `^*word is *`, whose second wildcard captures the rumor
text as [`arg1`](../reference/softcode.md#context-names), and the body
stores that text with [`set_attr`](../reference/softcode.md#fn-set_attr)
and stamps `rumor_at` with `now()`.

Two things keep this from turning into a shouting match. The engine skips
a speaker's own listen triggers, so an NPC never overhears itself and a
single gossip stays a single carrier. And the body runs **only if the NPC
is carrying nothing**, so once you know a tale you keep telling that one
rather than overwriting it with the next thing you hear.

Because the pickup pattern matches any speech at all, a *player* saying
"Word is the baron keeps a wolf" seeds the town exactly as an NPC does.
That is a feature worth knowing about before it surprises you.

### How fast does a rumor actually travel?

One beat per room, not one NPC per beat. A `say` is heard by everyone
present, so the moment Gale speaks, every gossip in the room who is
carrying nothing picks the tale up in that same beat. What takes time is
crossing the map: a rumor reaches the next room when a carrier walks
there (give an NPC the [`patrol`](061_patrolling_guard.md) behavior and it
makes rounds through real exits) or when a player repeats it somewhere
new. So the shape you get is a room converting at once and the town
converting at walking pace.

### What finally kills a rumor?

Age. Before speaking, the tick compares `now() - rumor_at` against the
NPC's `ttl`, and past that the rumor is dropped with
[`del_attr`](../reference/softcode.md#fn-del_attr) instead of spoken.
Each carrier stamps its own `rumor_at` when it learns the tale, so
carriers forget in the order they heard it and the mill goes quiet from
the outside in unless something fresh is seeded. `ttl` is plain seconds,
so 60 lets you watch a whole life cycle at the prompt while 86400 gives
you a rumor that lives a day.

### Why the marker phrase has no colon

A trigger attribute splits at its **first** colon, pattern on the left
and code on the right, so a marker phrase containing a colon would slice
the code in half. Storing `^*rumor: *:pemit(enactor, 'heard')` is
accepted by `@set`, which then warns that the attribute will not run and
names a syntax error, because everything after that first colon
(` *:pemit(enactor, 'heard')`) is not valid Python. A colon-free marker
like `word is` sidesteps the whole question.

## Build it

Two gossips in the square, tagged `npc` so the rest of your world can
find them. Add as many more as you like, since they all run the same
three attributes:

```text
@create Gossip Gale
@tag Gossip Gale = npc
drop Gossip Gale
@create Old Pip
@tag Old Pip = npc
drop Old Pip
```

How long a tale survives in one head, in seconds. Sixty is short enough
to watch decay happen while you are standing there:

```text
@set Gossip Gale/ttl = 60
@set Old Pip/ttl = 60
```

The gossip faucet. Each tick reads what the NPC knows, forgets it if it
has aged past `ttl`, and otherwise speaks it with the marker prefix.
Forgetting comes first so a stale tale is retired rather than repeated
one last time:

```text
@set Gossip Gale/on_tick = '''
r = V('rumor', '')
if r and now() - V('rumor_at', 0) > V('ttl', 60):
    del_attr(me, 'rumor')
elif r:
    say('Word is ' + r)
'''
@set Old Pip/on_tick = '''
r = V('rumor', '')
if r and now() - V('rumor_at', 0) > V('ttl', 60):
    del_attr(me, 'rumor')
elif r:
    say('Word is ' + r)
'''
```

The pickup. The pattern's trailing wildcard is the rumor text, and the
guard is what keeps a carrier loyal to its own tale:

```text
@set Gossip Gale/listen_rumor = '''
^*word is *:
# arg1 is the text after the marker; the engine skips a speaker's own ears
if not V('rumor', ''):
    set_attr(me, 'rumor', trim(arg1))
    set_attr(me, 'rumor_at', now())
'''
@set Old Pip/listen_rumor = '''
^*word is *:
# arg1 is the text after the marker; the engine skips a speaker's own ears
if not V('rumor', ''):
    set_attr(me, 'rumor', trim(arg1))
    set_attr(me, 'rumor_at', now())
'''
```

The heartbeat that drives the faucet. `interval` counts world beats, so
`interval:2` is about eight seconds between beats on default settings:

```text
@behavior Gossip Gale = script_ticker, interval:2
@behavior Old Pip = script_ticker, interval:2
```

Finally, seed one gossip. The rumor text goes on in the ordinary way, and
`rumor_at` is stamped through `@eval` because it wants the current clock
rather than a literal:

```text
@set Gossip Gale/rumor = the docks flood at dawn
@eval set_attr(get('Gossip Gale'), 'rumor_at', now())
```

## Try it

Force a beat with `@tr` instead of waiting on the clock, then look at
what the tale did to the room:

```text
> @tr Gossip Gale/on_tick
Gossip Gale says, "Word is the docks flood at dawn"
Triggered Gossip Gale/on_tick.

> @examine Old Pip
Name: Old Pip
...
Attributes:
  listen_rumor: "^*word is *:..."
  on_tick: "r = V('rumor', '')..."
  rumor: 'the docks flood at dawn'
  rumor_at: 1785122323
  ttl: 60
```

Pip overheard and is a carrier now, and her own next tick passes it on.
Note that Gale's line arrives with no trailing period, since `say`
reproduces the text exactly as the script built it, and the `rumor_at`
number is epoch seconds so yours will differ.

Now age Pip's copy past its `ttl` and beat her once more. The tick
forgets the tale rather than repeating it, and says nothing while doing
so:

```text
> @eval set_attr(get('Old Pip'), 'rumor_at', now() - 100)
Done.

> @tr Old Pip/on_tick
Triggered Old Pip/on_tick.
```

`@examine Old Pip` no longer lists a `rumor:` row, which is decay
working; the `rumor_at:` stamp stays behind and is simply overwritten by
the next tale she picks up. Two more results are worth confirming
deliberately. Give Pip a *different* rumor first and Gale's next tick
leaves it alone, because a carrier keeps its own tale:

```text
> @set Old Pip/rumor = the baron is poisoned
Set Old Pip/rumor = 'the baron is poisoned'

> @tr Gossip Gale/on_tick
Gossip Gale says, "Word is the docks flood at dawn"
Triggered Gossip Gale/on_tick.
```

And speak the marker yourself, next to two gossips who are carrying
nothing, to watch both of them pick it up on the one line:

```text
> say Word is the baron keeps a wolf
You say, "Word is the baron keeps a wolf"
```

## Going further

- **Chance, not certainty.** Wrap the `say` in
  `if rand(1, 3) == 1:` so gossips spill only sometimes.
  [`rand`](../reference/softcode.md#fn-rand) is inclusive at both ends, so
  that is a one-in-three beat and the spread turns lumpy rather than
  clockwork.
- **Mutation.** Have the pickup occasionally garble what it stores with
  [`replace`](../reference/softcode.md#fn-replace), as in
  `replace(arg1, 'dawn', 'midnight')`, and the tale drifts as it travels.
- **Legs.** Attach the `patrol` behavior alongside the ticker, as in
  `@behavior Old Pip = patrol, route:["north", "south"], pause:4` where
  the route is a JSON list of exit names, and the rumor leaves the square
  on foot.
- **Rumors with teeth.** Let a guard's listen react to one specific rumor
  (`^*the baron is poisoned*`) by raising the alarm, which turns gossip
  into a plot trigger feeding the
  [guard response](071_guard_response.md) zone master.
- **A rumor ledger.** A town crier that appends every distinct rumor it
  hears to a capped list, the way the
  [scene logger](205_scene_logger.md) keeps its transcript, gives players
  a `news` board of what is going around.
