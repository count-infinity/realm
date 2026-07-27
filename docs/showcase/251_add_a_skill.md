# 251. Add a skill: salvage diagnostics

> Checklist item 251 ([now]): *skill_def objects, @reload, skill-gated details, banded checks paying into an economy*

**What you'll build:** a reclamation bay that runs on a skill the engine
has never heard of. You define `diagnostics` as data, reload the rules,
and the world starts treating trained and untrained characters
differently: a technician reads something off a scorched coupling that a
deckhand looks straight past, certifies it with a roll, and the press
pays by the grade on the certificate.

**Concepts:** `skill_def` objects, `@reload` for the cached skill table,
the untrained default, `@detail` conditions that call `skill()`, and a
`$`-command whose payout rides on the check.

## How it works

A skill in REALM is not a Python constant. It is an object tagged
`skill_def` carrying two fields, and the running game reads it. That has
one consequence worth stating before the build: the engine happily
resolves a check against a skill nobody defined, so a build can look
finished while quietly doing nothing useful.

### What does defining the skill actually buy you?

Ask for a check against a skill the table has never seen and you get a
flat floor. `skill_level` reads the trained attribute first, then the
governing-attribute default, and failing both returns
`DEFAULT_ATTRIBUTE - 5`, which is **5**. Not five plus anything: five,
for everyone, no matter how clever or deft the character is.

Give the same character a real definition and the number starts
answering to them. With `intelligence` 12 and a `-4` untrained penalty:

| the character | effective skill |
|---|---|
| trained, `skill_diagnostics` 14 | 14 |
| untrained, skill **defined** | 8 (12 minus 4) |
| untrained, skill **undefined** | 5 (the flat floor) |

That middle row is the whole point. Defining the skill is what tells the
engine which characteristic governs it, so a smart character is
measurably better at diagnostics before anyone trains a single level.

### Why does a skill need `@reload` when a class does not?

The check table is cached for speed. Creating the `skill_def` object
writes the data; `@reload` re-reads those objects and reinstalls the
table so checks see it. Classes are read fresh at each character
creation, so they need no reload. Skip the reload and every check keeps
returning the flat 5, which is exactly the failure that looks like a
broken script rather than a stale cache.

### How does the world notice the skill?

Two ways, and this build uses both.

Passively, through a `@detail` whose condition calls `skill()`. The
condition is evaluated per viewer at look time, so the coupling shows its
extra line to a technician and stays quiet for everyone else, with no
hook and no bookkeeping.

Actively, through [`check_roll`](../reference/softcode.md#fn-check_roll)
inside a `$`-command, which turns the skill into a decision: certify the
part honestly, or log it as scrap.

### Why is the press verb `reclaim` rather than `sell`?

Builtins dispatch before `$`-commands, and `sell` is a builtin. A
`$sell *` trigger on the press would never fire; the engine's merchant
command answers first with "There's no merchant here." Reach for a verb
the engine does not already own. `reclaim` and `diagnose` are both free.

## Build it

Dig the bay and step in.

```text
@dig Reclamation Bay = bay, out
bay
```

Define the skill. It is an ordinary object: a name, the governing
characteristic, and the penalty an untrained character takes. The
`@reload` is the step that installs it into the live check table.

```text
@create diagnostics
@tag diagnostics = skill_def
@set diagnostics/stat = intelligence
@set diagnostics/penalty = -4
@reload
```

Put a wreck on the bench. Its true worth lives in `grade`, which the
scanner reads and the press pays against.

```text
@create battered coupling
drop battered coupling
@desc battered coupling = A thruster coupling, scorched down one flank.
@set battered coupling/grade = 3
```

Now the passive half. A `@detail` condition runs per viewer, so this line
reaches a trained eye and nobody else.

```text
@detail battered coupling = skill('diagnostics') >= 10 -> Beneath the scoring, the induction rings look unpitted.
```

The scanner is the active half. It refuses anything without a `grade`,
rolls the new skill, and writes a certificate: the true grade on a
success, a pessimistic 1 on a failure. Note that a botched reading still
certifies something, so a poor technician costs the seller money rather
than blocking the sale.

```text
@create hand scanner
drop hand scanner
@set hand scanner/cmd_diagnose = '''
$diagnose *:
part = get(trim(arg0))
if not part:
    pemit(enactor, 'No such part on the bench.')
elif not get_attr(part, 'grade'):
    pemit(enactor, name(part) + ' is not salvage.')
else:
    r = check_roll(enactor, 'diagnostics', 0)
    if not r.success:
        # a bad read still certifies, just at the lowest grade
        set_attr(part, 'certified', 1)
        pemit(enactor, 'You log ' + name(part) + ' as scrap. The scanner beeps once, unconvinced.')
    else:
        set_attr(part, 'certified', get_attr(part, 'grade'))
        pemit(enactor, 'You certify ' + name(part) + ' at grade ' + str(get_attr(part, 'grade')) + '.')
'''
```

Last, the press, funded so it has something to pay out with. It buys
certified stock only, at forty credits a grade, and the certificate is
the only thing it reads. That is the economy reacting to the skill.

```text
@create reclamation press
drop reclamation press
@eval adjust_credits(get('reclamation press'), 1000)
@set reclamation press/cmd_reclaim = '''
$reclaim *:
part = get(trim(arg0))
if not part:
    pemit(enactor, 'Bring the part to the press.')
elif not get_attr(part, 'certified'):
    pemit(enactor, 'The press idles. It takes certified stock only.')
else:
    pay = get_attr(part, 'certified') * 40
    transfer_credits(me, enactor, pay)
    destroy_obj(part)
    remit(here, 'The press swallows the part and counts out ' + str(pay) + ' credits.')
'''
```

## Try it

Give one character the skill and leave another without it, then have
each look at the same coupling.

```text
> @set Vex/skill_diagnostics = 14
Set Vex/skill_diagnostics = 14

(as Vex)
> look battered coupling
A thruster coupling, scorched down one flank.
Beneath the scoring, the induction rings look unpitted.

(as Doss, untrained)
> look battered coupling
A thruster coupling, scorched down one flank.
```

The press turns away uncertified stock, so the skill is the gate on the
whole transaction.

```text
(as Vex)
> reclaim battered coupling
The press idles. It takes certified stock only.

> diagnose battered coupling
You certify battered coupling at grade 3.

> reclaim battered coupling
The press swallows the part and counts out 120 credits.
```

The certify line varies with the roll: a failed check logs the coupling
as scrap and the press pays 40 instead of 120. To watch the definition
itself do the work, comment out the `@reload` and rebuild: every
`diagnose` then rolls against a flat 5 and a sharp technician reads no
better than a deckhand.

## Going further

- **Train it in-world.** The trainer NPC in
  [069](069_trainer_npc.md) sells skill levels for character points, and
  it reads the same table, so `diagnostics` becomes buyable the moment it
  is defined.
- **Grant it at chargen.** A `class_def` with
  `skills = {"diagnostics": 12}` starts salvagers already competent. See
  [Skills & Classes as Data](../guides/data-driven-rules.md).
- **Band the payout.** `check_roll` returns a margin, so a wide success
  could certify one grade above the part's own and a narrow one could
  shave the price, turning skill into money rather than a pass gate.
- **Ship it.** The skill, the class, and the bay are ordinary objects, so
  `@export` and a [content pack](../guides/content-packs.md) move the
  whole trade to another game. See [235](235_content_packs.md).
- **Let the wreck argue back.** Give the coupling an `ON_USE` hook that
  fires when a technician handles it, remembering with a
  [`target` guard](../reference/softcode.md#guard-on-target) that the
  hook reaches every object in the room.
