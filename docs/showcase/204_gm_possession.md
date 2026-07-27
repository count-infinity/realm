# 204. GM possession tools

> Checklist item 204 ([now]): *@force, control locks, puppet forwarding*

**What you'll build:** the staff toolkit for running a live scene through an
NPC, so you speak and act as Baron Haldor with `@force`, read his room from
outside it, and hand a trusted player a signet ring that lets *them* drive the
Baron while they still hold no staff powers of their own.

**Concepts:** `@force` through the real dispatcher (the room sees the NPC, not
you), the puppet session that forwards a forced command's output back to the
forcer, the player-level ceiling on a forced body, and a softcode
[`force()`](../reference/softcode.md#fn-force) relay gated by a `use` lock.

## How it works

The finished toolkit is two pieces: the `@force` command you already hold as
staff, and one small object, a signet ring, that lends the same reach to a
player you trust. Nothing is wired onto the Baron beyond a single tag, because
possession in REALM is settled by authority rather than by machinery. This
section answers four questions: why the room hears the Baron instead of you,
what comes back to your screen, where a forced body's ceiling sits, and how the
ring gives a player a share of your power without giving them your rank.

### Why does the room hear the Baron and not you?

`@force <target> = <command>` runs a command **as** the target through the same
dispatcher a player types into, so the parsing, the permission checks, and the
propagation are all the ordinary ones. When you type
`@force Baron Haldor = say Kneel before your Baron.`, the `say` builtin runs
with the Baron as the actor and propagates from where the Baron stands, so
everyone present reads `Baron Haldor says, "Kneel before your Baron."` and
nothing in that line points back at you. Seamless attribution is what makes
`@force` a tool for running scenes rather than a narration trick, and it is the
same machinery the [puppet](066_puppet.md) tutorial dissects; this tutorial is
about using it at the table.

Who may wear whom is decided by the engine's one authority predicate,
[`controls()`](../reference/softcode.md#fn-controls): you control yourself, what
you own, and whatever has been delegated to you, and an admin controls
everything. A Baron you `@create`d is therefore yours to wear, while forcing
someone else's object is refused with a message naming the target you lack
control of.
`@force` is registered as a builder-permission command on top of that, which
keeps possession a staff tool; the ring below is how a player gets a measured
share of it.

### What comes back to your screen, and what does not

A forced command runs against a puppet session, a stand-in for the live
connection the Baron does not have. Anything the command would print to the
Baron's own screen is forwarded to yours with his name in front, once, at the
head of the message rather than on every line:

```text
[Baron Haldor] 
The Throne Room
---------------

You see:
  a signet ring

Exits: None
```

So `@force Baron Haldor = look` reads you the room the Baron is standing in even
when you are somewhere else entirely, which is the cheapest pair of remote eyes
staff has.

Two limits are better learned before a scene than during one. First, the puppet
session lives only for the length of the command, so what you receive is that
one command's output and nothing after it: a player who speaks in the Baron's
room a moment later reaches the room, not you. A continuous feed is a different
build, and the [security camera](054_security_camera.md) is the one to copy.
Second, propagated output is never forwarded, because it was never addressed to
the Baron's screen in the first place. His speech and his poses travel outward
through the room to everyone standing in it, so you read them unprefixed as an
ordinary bystander when you are present, and you miss them when you are not.

### Where is the ceiling on a forced body?

The dispatcher checks the *Baron's* permission tier rather than yours, and the
Baron sits at player level, so `@force Baron Haldor = @dig A Secret Vault` comes
back as `[Baron Haldor] Permission denied.` with no room created. Possession
lowers what you may do and never raises it, which is exactly what makes it safe
to hand out: a body reaches less than a builder does, always.

The `@tag Baron Haldor = npc` line in the build is load bearing for that
sentence and is not decoration. A role is read off tags, the two tags that reach
player level are `player` and `npc`, and an object carrying neither is rated a
guest. A guest is refused even `say`, so forcing an untagged prop answers
`Permission denied.` for the most ordinary command in the game.

### How does a player with no staff powers drive the Baron?

The softcode twin of `@force` is [`force()`](../reference/softcode.md#fn-force),
which asks the same authority question of the *object running the script*
instead of the person typing. You create the signet ring, so you own it, and
REALM delegates an owner's authority to the objects they own, which is why the
ring reaches the Baron even while an ordinary player is the one working it. The
[`use` lock](../reference/softcode.md#locks-permissions) is then the entire
permission surface: `caller.has_tag('steward')` admits your co-GM and turns
everyone else away, and removing the tag makes the ring inert in the same
second. The ring may simply lie in the room, since a `$`-command is found on
anything in reach and needs no one to be holding it.

Two behaviours shape how the relay feels in play. A `$`-command is consulted
only after the builtins have had their turn, so the relay verb must be a word
the engine does not already own: `act` is free, while `grab`, for instance, is
an alias of `get` and would answer `Get what?` long before the ring saw it. And
softcode `force()` builds its puppet session with no watcher attached, so the
forced command's direct output is discarded rather than forwarded, which means
`act say ...` behaves exactly as expected while `act look` returns nothing to
the steward. Everything that propagates through the room (speech, poses, arrival
and departure) still lands normally, and that covers nearly all of what a co-GM
does during a scene.

## Build it

Start with the body. It is an ordinary object with a description, tagged `npc`
so the dispatcher rates it at player level, plus the ring it will be driven by:

```text
@create Baron Haldor
@tag Baron Haldor = npc
drop Baron Haldor
@desc Baron Haldor = A stout man in a fur-trimmed robe, eyes flicking to the door.
@create signet ring
drop signet ring
```

The relay is one line. `$act *` binds everything after the verb as `arg0` and
hands it straight to the Baron, so the ring never needs to know what the
commands mean:

```text
@set signet ring/cmd_act = $act *:force('Baron Haldor', arg0)
```

Finally the lock, which is the whole of the policy. Without it the ring would
answer to anyone who walked past it:

```text
@lock/use signet ring = caller.has_tag('steward')
```

## Try it

Run the Baron live. The room hears him and the transcript holds no trace of
you:

```text
> @force Baron Haldor = say Kneel before your Baron.
Baron Haldor says, "Kneel before your Baron."

> @force Baron Haldor = pose steeples his fingers.
Baron Haldor steeples his fingers.
```

Both of those reached you as propagation, because you are standing in the room.
A command that prints to the body instead arrives prefixed, once, with the
Baron's name, and it reports whichever room he is standing in:

```text
> @force Baron Haldor = look
[Baron Haldor] 
The Throne Room
---------------

You see:
  a signet ring

Players here:
  Bela

Exits: None
```

Building through the body is refused at the Baron's own tier, so the vault is
never dug:

```text
> @force Baron Haldor = @dig A Secret Vault
[Baron Haldor] Permission denied.
```

Now bring in a co-GM. Untagged, Wren fails the `use` lock, and a `$`-command
that fails its lock simply stops, so her attempt produces no response at all
and no one hears the Baron:

```text
(Wren) act say I hold no office.

> @tag Wren = steward
Added tag 'steward' to Wren.

(Wren) act say The court is in session.
Baron Haldor says, "The court is in session."
```

Those two lines are the result worth confirming deliberately. Wren is a plain
player who holds no builder rank, `@force` would answer her `Permission
denied.`, and yet the Baron speaks for her, because the ring carries its owner's
authority and the lock decided she was allowed to pick it up. Take the tag back
with `@untag Wren = steward` and the same command goes quiet again.

## Going further

- **A whole cast.** One GM can force any NPC in the scene, switching bodies line
  by line without ever appearing as themselves. A wand collapses the switching
  into one verb:
  `@set GM wand/cmd_speak = $speak *=*:force(get(arg0), 'say ' + arg1)`, after
  which `speak Herald=Hear ye!` puts words in the herald's mouth. The pattern's
  two wildcards bind as `arg0` and `arg1`, and
  [`get()`](../reference/softcode.md#fn-get) turns the name into the object.
- **Possession with consent.** The last resort of `controls()` is the target's
  own control lock, so `@lock/control me = caller.has_tag('mesmerist')` signs a
  player's strings over to anything carrying that tag, and clearing the lock
  takes them back. Both `@force` and `@lock` are builder commands, so staff sets
  the lock on the player's behalf and staff does the forcing; the player-level
  version of the same trick is a cursed doll running softcode `force()`, built
  exactly like the ring above. The [puppet](066_puppet.md) tutorial works
  through the consent model in full.
- **Remote eyes without a body.** Since softcode `force()` discards the forced
  command's output, a scrying bowl reads the far room directly instead of
  forcing a `look`:
  `@set scrying bowl/cmd_peer = $peer:pemit(enactor, 'You see: ' + ', '.join([name(o) for o in contents(get('The Throne Room'))]))`,
  which uses [`pemit()`](../reference/softcode.md#fn-pemit),
  [`contents()`](../reference/softcode.md#fn-contents), and
  [`name()`](../reference/softcode.md#fn-name). That is a snapshot on demand; for
  a live feed, build the [security camera](054_security_camera.md).
- **Several rings, several offices.** The lock expression is the only thing
  separating the tools, so a second ring reading
  `@lock/use herald's rod = caller.has_tag('crier')` hands a different player a
  different body, and each office is granted or revoked with one tag.
