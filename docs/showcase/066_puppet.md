# 066. Puppet

> Checklist item 66 ([now]): *@force, control locks, consent-based possession, output forwarding*

**What you'll build:** a marionette you drive as a second body, looking,
walking, and speaking through it, with everything it perceives piped
back to you. Then the darker trick: possessing another *player*, which
works only because they explicitly handed you their strings.
**Concepts:** `@force` through the real dispatcher, the
[`controls()`](../reference/softcode.md#fn-controls) authority model,
`@lock/control` as opt-in possession consent, puppet output forwarding,
the force-depth cap, and why a puppet can never do more than its own
permissions allow.

## How it works

The finished toy is one command, `@force`, resting on one authority
rule, `controls()`. Everything else is a consequence of those two, so
this section answers what `@force` actually runs and who is allowed to
be forced.

### What does `@force` actually run?

`@force <target> = <command>` runs a command **as** the target, through
the real dispatcher, so the parsing, the permission checks, and the
propagation are all the ordinary ones. Two consequences make it a
*body* and not a macro:

1. **You experience what it experiences.** The forced command runs
   against a puppet session whose output is forwarded to you, prefixed:
   `[marionette] The Puppeteer's Booth ...`. Force a `look` and you read
   the room through its eyes; force a `get` and you feel its fingers
   close. Its world echoes, meaning its speech and its footsteps, you
   witness from wherever you happen to stand, like anyone else in the
   room, so those lines reach you unprefixed.
2. **The puppet acts with its own station, not yours.** The dispatcher
   checks the *puppet's* permissions, and an NPC body rates as a PLAYER,
   so `@force marionette = @dig ...` is refused. Possession never
   escalates privilege: you can only ever do *less* through a body than
   you can as yourself.

### Who may possess what?

Possession asks the engine's one authority question,
[`controls()`](../reference/softcode.md#fn-controls): you control
yourself, what you own, and what has been delegated to you. Your
`@create`d marionette is yours because you own it, so force away. A
*player* is nobody's property, so forcing one fails, unless they opt in,
because the last resort of `controls()` is the target's own **control
lock**. `@lock/control me = <expression>` is a player signing their
strings over to whoever passes the expression: the haunted-house ghost,
the hypnotist's pocket watch, the drinking game. They set it, and they
can clear it (`@lock/control me =`), so the consent stays revocable and
inspectable. A forced command can itself force (chained puppets), capped
at depth 3, because marionettes all the way down is a bug and not a
feature.

Both `@force` and `@lock` are builder-permission commands today, so
player-to-player possession is a consent *model* the builder wires into
playables: a cursed doll with a `$possess` softcode command (built like
the [dialogue-tree NPC](067_dialogue_tree_npc.md)'s `$talk`) uses the
same [`force()`](../reference/softcode.md#fn-force) and control-lock
machinery at player level.

## Build it

Dig the booth and step inside, working from your workroom:

```text
@dig The Puppeteer's Booth = booth, out
booth
```

Now make the body. It is an ordinary tagged NPC with a description,
nothing more, because possession is authority and not machinery:

```text
@create marionette
@tag marionette = npc
drop marionette
@desc marionette = A jointed wooden figure, strings trailing up into nothing.
```

That is the whole build. Take it for a walk: look through its eyes, put
words in its mouth, then send it out the door and back:

```text
@force marionette = look
@force marionette = say I dance for no one.
@force marionette = out
@force marionette = booth
```

## Try it

Each forced command answers back with the puppet's name in front, and
the room description you get is the one the marionette can see:

```text
> @force marionette = look
[marionette] The Puppeteer's Booth
[marionette] A jointed wooden figure, strings trailing up into nothing.

> @force marionette = say I dance for no one.
marionette says, "I dance for no one."

> @force marionette = @dig Vault
[marionette] Permission denied.
```

The `say` line has no prefix because its speech is real speech: you hear
it in the room like anyone standing there. The `@dig` is refused because
an NPC body has player-level hands.

Now the consent model, with a second player, Wren. Forcing her fails
until she signs her strings over to anything tagged `mesmerist`:

```text
> @force Wren = say The stars are lovely.
You don't control Wren.

(Wren) @lock/control me = caller.has_tag('mesmerist')
Lock/control set on Wren.

> @tag me = mesmerist
> @force Wren = say The stars are lovely.
Wren says, "The stars are lovely."
```

And Wren watches herself say it, because the command ran through her own
body. She takes her strings back any time with `@lock/control me =`,
which clears the lock, or keeps it and lends her body to anything tagged
`mesmerist`, forever. That is the entire policy surface: one lock, on
her, owned by her.

## Going further

- **A softcode driver:** `@set marionette/cmd_pilot = $pilot *:
  force(me, arg0)`. Anyone passing the marionette's `use` lock can type
  `pilot <command>` and drive it without `@force`, since softcode
  [`force()`](../reference/softcode.md#fn-force) is the same primitive
  without the output forwarding. Gate it with
  `@lock/use marionette = caller.has_tag('licensed')`.
- **A haunted body:** give a ghost NPC softcode that `force(victim,
  ...)`, and it works exactly when the victim's control lock admits the
  ghost, so the horror is opt-in by construction.
- **Sensory-only puppets:** a `$peer` command on a crystal ball that
  runs `force(me, 'look')` from wherever the ball sits gives you remote
  eyes with the same authority story (see also the
  [security camera](054_security_camera.md)).
- **Puppet chains:** force the marionette to `@force` a second puppet,
  which is legal to depth 3, after which the engine cuts the strings.
