# 142. Traits in Play

> Checklist item 142 — [now] — *traits as check_mods effects, a trait tag the world reacts to, phobia via ON_ENTER, how grants work*

**What you'll build:** a gene clinic that splices three real GURPS-flavour
traits into a character and lets you *watch them bite*. **Combat Reflexes**
adds +1 to everything, **Acute Vision** sharpens your Observation by +2,
and **Claustrophobia** does nothing at all — until you step into a tight
space and the walls close in. A prove-it console rolls the difference out
loud.

**Concepts:** a trait as a permanent `modifier_effect` (its `check_mods`
folds into every roll; its mirrored **tag** is how the world knows you have
it), the split between a **passive modifier** trait and a **triggered**
one, and how grants work — proximity `apply_effect` here, `class_def`
skills at chargen there.

## How it works

1. **A trait is a permanent condition.** The same `modifier_effect` that
   makes a two-beat fear ([135](135_injury_treatment.md)) makes a
   lifelong advantage — just set `duration=0` (permanent). Combat Reflexes
   is `check_mods={'all': 1}`; Acute Vision is `{'observation': 2}`. Those
   fold through `skill_check()` for free, so the trait is *mechanically
   real* the instant it's grafted: every relevant roll shifts.

2. **The tag is the grant's fingerprint.** Every effect mirrors its `kind`
   as a tag, so a character with Combat Reflexes is tagged
   `combat_reflexes` and a claustrophobe is tagged `claustrophobia`. That
   tag is the hook the *world* keys off — which is the whole trick behind
   a trait that has no passive number at all.

3. **Some traits are triggers, not modifiers.** Claustrophobia's
   `check_mods` are empty; grafting it only sets the tag. The bite lives in
   the environment: a cramped room's `ON_ENTER` checks
   `has_tag(enactor, 'claustrophobia')` and, if so, slaps on a short
   `panic` effect (−2 to everything). This is the audit's "phobia = `ON_*`
   trigger" — a disadvantage that costs nothing in the open and everything
   in the wrong room. (Pair it with an `on_check` ward and the phobic can
   be *barred* from the space entirely — see Going further.)

4. **How grants happen — two doors.** Here, the clinic **grafts live** with
   `apply_effect` on **proximity** authority: a machine in your room can
   condition you, no ownership needed ([059](059_tranquilizer.md)). The
   *other* door is chargen: a `class_def` or template writes starting stats
   and skills onto the sheet at creation ([132](132_chargen_walkthrough.md),
   [data-driven rules](../guides/data-driven-rules.md)) — grants baked in
   at birth. Same idea, different clock: one splices a trait now, one
   issues it on day one.

## Build it

The clinic, the trait table (one data attribute), and the graft verb:

```text
@dig The Gene Clinic = clinic, out
clinic
@create trait console
drop trait console
@desc trait console = A surgical booth of needles and green gel. GRAFT <trait> to splice one in; PROVE to test yourself. Stock: reflexes, keen eye, claustrophobia.
@set trait console/traits = {"reflexes": {"kind": "combat_reflexes", "mods": {"all": 1}, "msg": "Your reflexes wind tight -- +1 to everything."}, "keen_eye": {"kind": "keen_eye", "mods": {"observation": 2}, "msg": "The world sharpens -- +2 Observation."}, "claustrophobia": {"kind": "claustrophobia", "mods": {}, "msg": "A cold knot ties itself in your chest at the thought of tight spaces."}}
@set trait console/cmd_graft = $graft *: t = trim(arg0).lower().replace(' ', '_'); d = get_attr(me, 'traits', {}).get(t); (pemit(enactor, 'No such trait on file.') if not d else (pemit(enactor, 'That trait is already spliced in.') if has_tag(enactor, d['kind']) else apply_effect(enactor, 'modifier_effect', kind=d['kind'], duration=0, check_mods=d['mods'], apply_msg=d['msg'])))
@set trait console/cmd_prove = $prove: pemit(enactor, 'Observation: ' + ('pass' if skill_check(enactor, 'observation') else 'fail') + ' | Melee: ' + ('pass' if skill_check(enactor, 'melee') else 'fail'))
```

The tight space that only a claustrophobe fears:

```text
@dig The Crawlway = crawlway, clinic
crawlway
@tag here = cramped
@set here/on_enter = (apply_effect(enactor, 'modifier_effect', kind='panic', duration=4, check_mods={'all': -2}, apply_msg='The walls crush inward. Your breath saws and your hands shake. (-2, panicking)') if has_tag(enactor, 'claustrophobia') and not has_tag(enactor, 'panic') else None)
clinic
```

## Try it

A middling character (Observation 8, Melee 9 — both just shy of the mark)
proves themselves, then grafts up:

```text
prove                -> Observation: fail | Melee: fail
graft reflexes       -> Your reflexes wind tight -- +1 to everything.
prove                -> Observation: fail | Melee: pass      (9 -> 10, over the line)
graft keen eye       -> The world sharpens -- +2 Observation.
prove                -> Observation: pass | Melee: pass      (8 +1 +2 = 11)
```

Two passive traits, two rolls visibly changed — that's a modifier trait in
play. Now take Claustrophobia, which reads as *nothing*… until geography
finds you:

```text
graft claustrophobia -> A cold knot ties itself in your chest...
crawlway             -> The walls crush inward. Your breath saws and your hands shake. (-2, panicking)
clinic
prove                -> Observation: fail | Melee: fail      (the panic -2 drags both back under)
```

The triggered trait cost nothing in the clinic and everything in the duct —
and it stacked with the good traits in the same `check_mods` ledger, so the
net roll is just the sum of who you are. That is traits in play: not a
character-sheet footnote, but the number the dice actually see.

## Going further

- **Phobia as a wall, not just a wobble:** add `@set crawlway/on_check =
  block('You cannot make yourself go in.') if has_atag('movement') and
  adata('exit') and has_tag(actor, 'claustrophobia') else None` — the
  `ON_* + ward` pairing, a space the phobic simply won't enter.
- **Berserk:** a trait tag a zone-master `ON_HITPRCNT` reads — below 1/3
  HP, force an `aggressive` behavior on the trait-holder ([119](119_npc_morale.md)).
- **Traits as chargen grants:** put these in a `class_def`'s data so a
  background *comes with* Combat Reflexes — issued at induction
  ([132](132_chargen_walkthrough.md)) instead of grafted later.
- **Temporary traits:** drop `duration=0` for a real number and the same
  machinery is a drug, a blessing, a power-up that wears off — [129](129_cooking_buffs.md)'s buff, relabeled an advantage.
