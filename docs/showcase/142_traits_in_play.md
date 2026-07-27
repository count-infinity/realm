# 142. Traits in Play

> Checklist item 142 ([now]): *class_def/skill_def data, trait-driven triggers and wards*

**What you'll build:** a gene clinic that splices three GURPS-flavour traits
into a character and lets you watch them bite. Combat Reflexes adds +1 to
everything, Acute Vision sharpens Observation by +2, and Claustrophobia does
nothing at all until you step into a tight space and the walls close in. A
prove-it console rolls the difference out loud.

**Concepts:** a trait as a permanent
[`modifier_effect`](../reference/softcode.md#fn-apply_effect) (its `check_mods`
fold into every roll, and its mirrored tag is how the world knows you have it),
the split between a passive-modifier trait and a triggered one, and how grants
happen: proximity [`apply_effect`](../reference/softcode.md#fn-apply_effect)
here, [`class_def`](../guides/data-driven-rules.md) stats and skills at chargen
there.

## How it works

The finished clinic is one object carrying a table of traits and two verbs:
`graft` splices a trait onto whoever is standing at the console, and `prove`
rolls Observation and Melee so you can see the numbers move. Next door, a
cramped room reacts to one of those traits on its own. This section answers
four questions: what a trait actually is, why a tag rides alongside it, how a
trait with no number still changes the game, and where grants come from.

1. **A trait is a permanent condition.** The same `modifier_effect` that models
   a temporary wound in [135](135_injury_treatment.md) (a timed penalty that
   counts down and expires) becomes a lifelong advantage when you set
   `duration=0`, which the effect engine reads as "never expires." Combat
   Reflexes is `check_mods={'all': 1}`; Acute Vision is `{'observation': 2}`.
   Those fold through [`skill_check`](../reference/softcode.md#fn-skill_check)
   for free, because `check()` sums every registered condition modifier into the
   roll before the resolver ever sees it, so a trait is mechanically real the
   instant it is grafted: every relevant roll shifts.

2. **The tag is the grant's fingerprint.** Every effect mirrors its `kind` as a
   [tag](../reference/softcode.md#fn-has_tag) on its owner while active, so a
   character with Combat Reflexes is tagged `combat_reflexes` and a claustrophobe
   is tagged `claustrophobia`. That tag is the hook the *world* keys off, which
   is the whole trick behind a trait that has no passive number at all.

3. **Some traits are triggers, not modifiers.** Claustrophobia's `check_mods` are
   empty, so grafting it only sets the tag. The bite lives in the environment: a
   cramped room's [`ON_ENTER`](../reference/softcode.md#lifecycle-hooks) hook
   checks `has_tag(enactor, 'claustrophobia')` and, if so, applies a short
   `panic` effect (-2 to everything). This is the audit's "phobia = trigger": a
   disadvantage that costs nothing in the open and everything in the wrong room.
   Pair it with an [`on_check`](../design/action-phases.md) ward and the phobic
   is barred from the space entirely (see Going further).

4. **Grants come through two doors.** Here, the clinic grafts live with
   `apply_effect` on **proximity** authority: any object in your room can
   condition you, because `apply_effect` only checks that the target is within
   reach of the executor, never ownership ([059](059_tranquilizer.md)). The
   other door is chargen: a [`class_def`](../guides/data-driven-rules.md) or
   template writes starting stats and skills onto the sheet at creation
   ([132](132_chargen_walkthrough.md)), so a background arrives already trained.
   A `class_def` carries stats and skills as data; a starting *trait* rides the
   induction script that reads the choice (see Going further). Same idea,
   different clock: one splices a trait now, one issues it on day one.

## Build it

Dig the clinic and drop in the console. `@dig The Gene Clinic = clinic, out`
names the entry exit `clinic` and the return exit `out`, so `clinic` walks you
in.

```text
@dig The Gene Clinic = clinic, out
clinic
@create trait console
drop trait console
@desc trait console = A surgical booth of needles and green gel. GRAFT <trait> to splice one in; PROVE to test yourself. Stock: reflexes, keen eye, claustrophobia.
```

The trait table is one data attribute: a dict of the three traits keyed by the
name a player types, each carrying the effect `kind` (which becomes the tag),
its `check_mods`, and the line the recipient reads. It is a single dict value,
so it stays on one line, where [`@set`](../guides/world-management.md) evaluates
it into a real dictionary that [`V`](../reference/softcode.md#fn-v) reads back.

```text
@set trait console/traits = {"reflexes": {"kind": "combat_reflexes", "mods": {"all": 1}, "msg": "Your reflexes wind tight -- +1 to everything."}, "keen_eye": {"kind": "keen_eye", "mods": {"observation": 2}, "msg": "The world sharpens -- +2 Observation."}, "claustrophobia": {"kind": "claustrophobia", "mods": {}, "msg": "A cold knot ties itself in your chest at the thought of tight spaces."}}
```

The `graft` verb normalizes the typed name, looks it up, and splices the trait.
It refuses an unknown name, refuses a second graft of a trait you already carry
(a permanent effect would merely re-apply otherwise), and on success calls
`apply_effect` on the enactor with `duration=0`.

```text
@set trait console/cmd_graft = '''
$graft *:
t = trim(arg0).lower().replace(' ', '_')
d = V('traits', {}).get(t)
if not d:
    pemit(enactor, 'No such trait on file.')
elif has_tag(enactor, d['kind']):
    pemit(enactor, 'That trait is already spliced in.')
else:
    # duration=0 makes the effect permanent: a trait, not a timed buff
    apply_effect(enactor, 'modifier_effect', kind=d['kind'], duration=0,
                 check_mods=d['mods'], apply_msg=d['msg'])
'''
```

The `prove` verb rolls both skills and reports pass or fail for each, so the
trait modifiers are visible as they land. A `$`-command matches on one object,
so [`pemit`](../reference/softcode.md#fn-pemit) speaks to the enactor with no
guard needed.

```text
@set trait console/cmd_prove = '''
$prove:
obs = 'pass' if skill_check(enactor, 'observation') else 'fail'
melee = 'pass' if skill_check(enactor, 'melee') else 'fail'
pemit(enactor, f'Observation: {obs} | Melee: {melee}')
'''
```

Now the tight space that only a claustrophobe fears. Dig it, step in, and tag
the room `cramped` for flavour.

```text
@dig The Crawlway = crawlway, clinic
crawlway
@tag here = cramped
```

Its `on_enter` hook reacts to whoever just walked in. An `ON_ENTER` hook fires
for every entry the room witnesses, and `enactor` is the mover, so the guard is
the `if`: only a claustrophobe who is not already panicking gets the `panic`
effect. Someone else entering, or a claustrophobe already standing here, is left
alone.

```text
@set here/on_enter = '''
if has_tag(enactor, 'claustrophobia') and not has_tag(enactor, 'panic'):
    apply_effect(enactor, 'modifier_effect', kind='panic', duration=4,
                 check_mods={'all': -2},
                 apply_msg='The walls crush inward. Your breath saws and your hands shake. (-2, panicking)')
'''
clinic
```

## Try it

A middling character (Observation 8, Melee 9, both just shy of the mark) proves
themselves, then grafts up:

```text
> prove
Observation: fail | Melee: fail

> graft reflexes
Your reflexes wind tight -- +1 to everything.

> prove
Observation: fail | Melee: pass      (Melee 9 -> 10, over the line)

> graft keen eye
The world sharpens -- +2 Observation.

> prove
Observation: pass | Melee: pass      (Observation 8 +1 +2 = 11)
```

Two passive traits, two rolls visibly changed: that is a modifier trait in play.
Now take Claustrophobia, which reads as nothing until geography finds you:

```text
> graft claustrophobia
A cold knot ties itself in your chest at the thought of tight spaces.

> crawlway
The walls crush inward. Your breath saws and your hands shake. (-2, panicking)

> clinic
> prove
Observation: fail | Melee: fail      (the panic -2 drags both back under)
```

The triggered trait cost nothing in the clinic and everything in the crawlway,
and it stacked with the good traits in the same `check_mods` sum, so the net
roll is just the total of who you are. That is traits in play: not a
character-sheet footnote, but the number the dice actually see.

## Going further

- **Phobia as a wall, not just a wobble.** Standing in the crawlway,
  `@set here/on_check = block('The tight space looms; your nerve holds you back.')
  if has_atag('movement') and adata('exit') and has_tag(actor, 'claustrophobia')
  else None`. Because the ward lives on the *room* (a walk targets rooms, not the
  exit, so an [`on_check`](../design/action-phases.md) on the exit object never
  runs for traversal), it fires as the destination's pre-enter veto and turns the
  crawlway into a space the phobic simply keeps out of.
- **Berserk.** A trait tag a zone-master `ON_HITPRCNT` reads: below one third HP,
  force an `aggressive` behavior onto the trait-holder ([119](119_npc_morale.md)).
- **Traits as chargen grants.** The `class_def` data carries stats and skills,
  so a background arrives already trained. To make it *come with* Combat
  Reflexes, add an `apply_effect` line to the induction script that files the
  background ([132](132_chargen_walkthrough.md)), keyed to the chosen template,
  so the trait is issued at induction instead of grafted later.
- **Temporary traits.** Drop `duration=0` for a real number and the same
  machinery is a drug, a blessing, or a power-up that wears off, which is
  [129](129_cooking_buffs.md)'s buff relabeled an advantage.
