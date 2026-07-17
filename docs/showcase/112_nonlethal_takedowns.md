# 112. Non-lethal takedowns

> Checklist item 112 — [now] — *engine unconsciousness, restraint wards, captives*

**What you'll build:** A cosh that puts people down without killing
them, iron binders that keep a captive put, and a clear map of the
engine's **two ways to end up on the floor** — the HP-zero death path
versus the softcode knockout.

**Concepts:** the `unconscious` kind-tag (item 59's tranquilizer,
here by blunt force), `contest()` for opposed takedowns, permanent
`modifier_effect`s as restraints, the room `on_check` ward from item
53's snare, and what the native defeat path does for players versus
NPCs.

## How it works

**The death path (native).** When combat drives anything to 0 HP, the
one death path fires, and it is asymmetric by design:

| | Players | NPCs |
|---|---|---|
| At 0 HP | fall **unconscious in place**, tagged `unconscious` | **die** into a lootable `corpse of X` (which decays) |
| Comes back via | `firstaid` / healing — the tag lifts when HP > 0 | nothing — a fresh spawn is a new creature |

So you *cannot* capture an NPC by beating it down — zero HP is a
corpse. Capturing requires the second path.

**The knockout path (softcode).** Item 59 established the trick: an
effect with `kind='unconscious'` mirrors that kind as a **tag** on the
victim while active, and the engine's own gates key on the tag — no HP
harmed. While it holds, the victim cannot walk (`You are unconscious.`)
or fight (same), and `is_combat_capable()` refuses them, so *nobody can
start combat against a captive* — downed means out of the fight, both
directions. Unlike HP-zero, this one expires on its own (beats), so a
sapped guard wakes up with a headache instead of a gravestone.

The cosh resolves as a **quick contest** — attacker's Melee against the
victim's Fortitude (`contest()`, ties to the defender) — so a hardy
target shrugs it off. That's the same opposed-check shape as item 53's
snare struggle.

**Restraints are a ward, not a rope.** The binders attach a *permanent*
(`duration=0`) `modifier_effect` with `kind='restrained'` — again just
a kind-tag — and the room's `on_check` ward vetoes any `event:on_leave`
by a `restrained` actor: item 53's snare pattern with the tag renamed.
Binding requires the target already unconscious (you do not handcuff
someone mid-swing), and `$release` strips the effect. Because the
restraint outlives the knockout, your captive wakes up *still bound* —
that is the capture.

## Build it

The brig, the resistance skill as data, and the cosh:

```text
@dig The Brig = brig, out
brig
@create fortitude
@tag fortitude = skill_def
@set fortitude/stat = health
@set fortitude/penalty = 0
@reload
@create leather cosh
drop leather cosh
@desc leather cosh = A sand-filled sock of a weapon. SAP someone with it -- quietly.
@set leather cosh/cmd_sap = $sap *: t = get(trim(arg0)); (pemit(enactor, 'No sign of them in reach.') if not (t and loc(t) == loc(enactor) and (has_tag(t, 'player') or has_tag(t, 'npc'))) else (pemit(enactor, 'They are already out cold.') if has_tag(t, 'unconscious') else ((remit(loc(enactor), name(enactor) + ' saps ' + name(t) + ' behind the ear -- they fold up like wet paper.'), apply_effect(t, 'modifier_effect', kind='unconscious', duration=8, apply_msg='A starburst of white -- then nothing.', expire_msg='You come to with a skull full of gravel.')) if contest(enactor, 'melee', t, 'fortitude') else remit(loc(enactor), name(t) + ' twists away from ' + name(enactor) + "'s cosh!"))))
```

The binders and the ward that makes them real:

```text
@create iron binders
drop iron binders
@desc iron binders = Rimed iron cuffs on a short chain. BIND the unconscious; RELEASE the forgiven.
@set iron binders/cmd_bind = $bind *: t = get(trim(arg0)); (pemit(enactor, 'No sign of them in reach.') if not (t and loc(t) == loc(enactor)) else (pemit(enactor, 'They are wide awake -- put them down first.') if not has_tag(t, 'unconscious') else (pemit(enactor, 'They are already in irons.') if has_tag(t, 'restrained') else (apply_effect(t, 'modifier_effect', kind='restrained', duration=0), remit(loc(enactor), name(enactor) + ' snaps iron binders around ' + name(t) + "'s wrists.")))))
@set iron binders/cmd_release = $release *: t = get(trim(arg0)); (remove_effect(t, 'restrained'), remit(loc(enactor), name(enactor) + ' unlocks the binders.')) if t and loc(t) == loc(enactor) and has_tag(t, 'restrained') else pemit(enactor, 'They are not in your irons.')
@set here/on_check = block('The binders hold -- you are going nowhere.') if atype == 'event:on_leave' and has_tag(actor, 'restrained') else None
```

## Try it

```text
sap Zeke            -> ... folds up like wet paper.   (Melee vs Fortitude)
sap Brick           -> Brick twists away from your cosh!   (the hardy resist)
bind Zeke           -> ... snaps iron binders around Zeke's wrists.
```

Eight beats later Zeke comes to ("a skull full of gravel") — bound.
From Zeke's side:

```text
out                 -> The binders hold -- you are going nowhere.
```

`release Zeke` and the door works again. Meanwhile the *death* path,
for contrast: knock a **thug NPC** to 0 HP in combat and you get
`corpse of thug` — no captive, no interrogation. Beat a **player**
to 0 and they collapse where they stand until someone kneels down with
`firstaid` — HP back above zero lifts the tag, no timer.

Note the guard rails you got free: while Zeke is unconscious, `attack
Zeke` refuses (`is_combat_capable` excludes the downed) — captives are
not free XP — and item 52's mercy rule means bleed effects skip them.

## Going further

- **Drag the captive** — a `$drag *` on the binders that `move_to`s a
  restrained target along with you needs *relocation* authority: works
  on your own prisoners (your NPCs), or via an admin-owned paddy wagon.
- **Struggle out** — give the binders a hold rating and copy item 53's
  `$struggle` contest verbatim (`might` vs `hold`, the rating eroding
  per attempt).
- **Turn them in** — a bounty office (item 114) that pays for
  `restrained` captives delivered alive: the `$claim` checks
  `has_tag(t, 'restrained')` instead of listening for deaths.
- **Sap from stealth only** — require `has_tag(enactor, 'hidden')` and
  drop the contest to a flat -4'd Fortitude roll: assassin rules, item
  160's sneaking as the setup.
