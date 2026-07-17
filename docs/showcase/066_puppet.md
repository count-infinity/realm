# 066. Puppet

> Checklist item 66 — [now] — *@force, control locks, consent-based possession, output forwarding*

**What you'll build:** a marionette you drive as a second body —
looking, walking, speaking through it, with everything it perceives
piped back to you — and then the darker trick: possessing another
*player*, which works only because they explicitly handed you their
strings.
**Concepts:** `@force` through the real dispatcher, the `controls()`
authority model, `@lock/control` as opt-in possession consent, puppet
output forwarding, the force-depth cap, and why a puppet can never do
more than its own permissions allow.

## How it works

**`@force <target> = <command>` runs a command AS the target, through
the real dispatcher** — real parsing, real permission checks, real
propagation. Two consequences make it a *body* and not a macro:

1. **You experience what it experiences.** The forced command runs
   against a puppet session whose output is forwarded to you,
   prefixed: `[marionette] The Puppeteer's Booth ...`. Force a `look`
   and you see the room through its eyes; force a `get` and you feel
   its fingers close. (World echoes — its speech, its footsteps — you
   simply witness from wherever you stand, like anyone else.)
2. **The puppet acts with its own station, not yours.** The dispatcher
   checks the *puppet's* permissions: an NPC body rates as a PLAYER,
   so `@force marionette = @dig ...` is refused. Possession never
   escalates privilege — you can only ever do *less* through a body
   than you can as yourself.

**Who may possess what is the engine's one authority question:**
`controls()`. You control yourself, what you own, and what's been
delegated to you. Your `@create`d marionette is yours — force away. A
*player* is nobody's property: forcing one fails... unless they opt
in, because the last resort of `controls()` is the target's own
**control lock**. `@lock/control me = <expression>` is a player
signing their strings over to whoever passes the expression — the
haunted-house ghost, the hypnotist's pocket watch, the drinking game.
They set it; they can clear it (`@lock/control me =`); consent,
revocable, inspectable. A forced command can itself force (chained
puppets), capped at depth 3 — marionettes all the way down is a bug,
not a feature.

(Both `@force` and `@lock` are builder-permission commands today, so
player-to-player possession is a consent *model* the builder wires
into playables — a cursed doll with a `$possess` softcode command uses
the same `force()`/control-lock machinery at player level.)

## Build it

A booth, and the body (from your workroom):

```
@dig The Puppeteer's Booth = booth, out
booth
@create marionette
@tag marionette = npc
drop marionette
@desc marionette = A jointed wooden figure, strings trailing up into nothing.
```

That's the whole build — possession is authority, not machinery. Take
it for a walk:

```
@force marionette = look
@force marionette = say I dance for no one.
@force marionette = out
@force marionette = booth
```

## Try it

Each forced command answers back with the prefix:

```
@force marionette = look        → [marionette] The Puppeteer's Booth
                                  [marionette] A jointed wooden figure...
@force marionette = say I dance for no one.
                                → marionette says, "I dance for no one."
                                  (you hear it in the room, like anyone)
@force marionette = @dig Vault  → [marionette] Permission denied.
                                  (an NPC body has player-level hands)
```

Now the consent model, with a second player — say, Wren:

```
(you)  @force Wren = say The stars are lovely.
                                → You don't control Wren.
(Wren) @lock/control me = caller.has_tag('mesmerist')
(you)  @tag me = mesmerist
(you)  @force Wren = say The stars are lovely.
                                → Wren says, "The stars are lovely."
                                  — and Wren watches herself say it
```

Wren takes her strings back any time: `@lock/control me =` (clears the
lock) — or keeps them and lends her body to anything tagged
`mesmerist`, forever. That is the entire policy surface: one lock, on
her, owned by her.

## Going further

- **A softcode driver:** `@set marionette/cmd_pilot = $pilot *:
  force(me, arg0)` — anyone passing the marionette's `use` lock can
  type `pilot <command>` and drive it without `@force` (softcode
  `force()` is the same primitive, minus the output forwarding). Gate
  it: `@lock/use marionette = caller.has_tag('licensed')`.
- **A haunted body:** give a ghost NPC softcode that
  `force(victim, ...)` — it works exactly when the victim's control
  lock admits the ghost. The horror is opt-in by construction.
- **Sensory-only puppets:** a `$peer` command on a crystal ball that
  `force(me, 'look')` from wherever the ball sits — remote eyes with
  the same authority story (see also item 54's camera).
- **Puppet chains:** force the marionette to `@force` a second puppet
  — legal to depth 3, then the engine cuts the strings.
