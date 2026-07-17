"""
Showcase verification — Character Systems (checklist items 132, 135-138,
140-143).

Drives every "Build it" command line from the nine tutorials
(docs/showcase/132_chargen_walkthrough.md .. 143_xp_spending.md) through a
real in-process world — the realm.testing.Simulator wires the same
store / propagation / scripting / dispatcher stack a live GameServer does —
then exercises each tutorial's "Try it" flow: raw input in, session output
out.

Determinism: skill checks use a level resolver (success iff effective
skill >= 10, with condition modifiers folded in exactly as the engine
does), so injuries, encumbrance, hunger, and traits change rolls by their
stated amounts. Effect beats are advanced by calling deliver_beat() by
hand; ticker behaviors are fired with @tr; the death path (item 140) uses a
diceless GURPS ruleset with resolve_round() fired by hand.

The BUILD_* transcripts are copied verbatim from the docs; the doc-sync
test at the bottom keeps them from drifting.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.core.beats import deliver_beat
from realm.core.checks import CheckResult, set_check_resolver, skill_level
from realm.testing import Simulator

# Output that must never appear while running a "Build it" transcript.
BUILD_RED_FLAGS = (
    "Unknown command", "Usage:", "not found", "Script error",
    "Eval error", "No permission", "Permission denied", "Bad parameter",
    "Unknown behavior",
)


# --- Build transcripts (each tutorial's exact "Build it" lines) ----------------

# docs/showcase/132_chargen_walkthrough.md
BUILD_132 = [
    "@dig The Induction Booth = booth, out",
    "booth",
    "@create Orientation Clerk",
    "@tag Orientation Clerk = npc",
    "drop Orientation Clerk",
    "@desc Orientation Clerk = A crisp officer behind a chrome desk, stylus poised over a fresh service record. Say ENLIST when you are ready to be inducted.",
    '@set Orientation Clerk/backgrounds = {"soldier": {"stats": {"strength": 12, "dexterity": 11, "health": 12}, "skills": {"melee": 12, "guns": 12}}, "scout": {"stats": {"strength": 10, "dexterity": 13, "health": 10}, "skills": {"stealth": 13, "climbing": 12}}}',
    "@set Orientation Clerk/menu = bg = V('backgrounds', {}); result = 'Choose a background -- ' + ', '.join(sorted(bg)) + '. Type the name.'",
    "@set Orientation Clerk/cmd_enlist = $enlist: (pemit(enactor, 'Your record is already filed; you are inducted.') if get_attr(enactor, 'template') else prompt(enactor, eval_attr(me, 'menu'), 'pick_bg'))",
    "@set Orientation Clerk/pick_bg = c = trim(arg0).lower(); bg = V('backgrounds', {}); r = bg.get(c); (prompt(enactor, 'No such background. ' + eval_attr(me, 'menu'), 'pick_bg') if not r else ([set_attr(enactor, k, v) for k, v in r['stats'].items()], [set_attr(enactor, 'skill_' + k, v) for k, v in r['skills'].items()], set_attr(enactor, 'template', c), prompt(enactor, 'Filed as ' + c + '. Pick a bonus skill -- stealth, melee, or guns.', 'pick_skill')))",
    "@set Orientation Clerk/pick_skill = s = trim(arg0).lower().replace(' ', '_'); (prompt(enactor, 'Pick stealth, melee, or guns.', 'pick_skill') if s not in ['stealth', 'melee', 'guns'] else (set_attr(enactor, 'skill_' + s, (int(get_attr(enactor, 'skill_' + s)) + 1) if get_attr(enactor, 'skill_' + s) != None else int(get_attr(enactor, 'dexterity', 10))), eval_attr(me, 'finish', enactor.id)))",
    "@set Orientation Clerk/finish = p = get('#' + arg0); st = int(get_attr(p, 'strength', 10)); set_attr(p, 'hp', st); set_attr(p, 'max_hp', st); set_attr(p, 'dodge', 7 + (int(get_attr(p, 'dexterity', 10)) + int(get_attr(p, 'health', 10))) // 8); pemit(p, 'Induction complete. HP ' + str(st) + ', Dodge ' + str(get_attr(p, 'dodge', 8)) + '. Welcome to the service, ' + get_attr(p, 'template', 'recruit') + '.')",
]

# docs/showcase/135_injury_treatment.md
BUILD_135 = [
    "@dig The Med Bay = medbay, out",
    "medbay",
    "@create live junction",
    "drop live junction",
    "@desc live junction = An exposed power coupling, arcing softly. GRIP WIRE if you must -- it will not be gentle.",
    "@set live junction/cmd_grip = $grip wire: (pemit(enactor, 'The coupling is spent for now -- your arm still remembers it.') if has_tag(enactor, 'wounded') else (remit(loc(enactor), name(enactor) + ' grabs the live wire and convulses!'), apply_effect(enactor, 'modifier_effect', kind='wounded', duration=10, check_mods={'all': -3}, apply_msg='Current rips up your arm -- the muscle seizes and will not answer right. (-3 to everything)', expire_msg='Feeling floods back into your arm. The injury has healed.'), damage(enactor, 2)))",
    "@create diagnostic slate",
    "drop diagnostic slate",
    "@desc diagnostic slate = A handheld med-scanner. CHECK <name> to read their motor control.",
    "@set diagnostic slate/cmd_check = $check *: t = get(trim(arg0)); (pemit(enactor, 'No one here by that name.') if not (t and loc(t) == loc(enactor)) else pemit(enactor, name(t) + ': a Melee roll ' + ('SUCCEEDS cleanly.' if skill_check(t, 'melee') else 'FAILS -- the hand is shaking.')))",
    "@create splint kit",
    "drop splint kit",
    "@desc splint kit = A roll of memory-foam splints and a nerve stimulator. SPLINT <name> to treat an injury.",
    "@set splint kit/cmd_splint = $splint *: t = get(trim(arg0)); (pemit(enactor, 'No patient here by that name.') if not (t and loc(t) == loc(enactor)) else (pemit(enactor, 'They have no injury to splint.') if not has_tag(t, 'wounded') else ((remove_effect(t, 'wounded'), heal(t, 1), remit(loc(enactor), name(enactor) + ' braces and binds ' + name(t) + \"'s arm. The seizing eases.\")) if skill_check(enactor, 'first_aid') else pemit(enactor, 'Your hands slip on the splint -- it will not set.'))))",
]

# docs/showcase/136_encumbrance.md
BUILD_136 = [
    "@dig The Loading Dock = dock, out",
    "dock",
    "@create cargo scale",
    "drop cargo scale",
    "@desc cargo scale = A battered freight scale bolted to the deck. STEP ON THE SCALE (command: HEFT) to gauge your load.",
    "@set cargo scale/cmd_heft = $heft: st = int(get_attr(enactor, 'strength', 10)); bl = st * st // 5; load = sum([int(get_attr(o, 'weight', 0)) for o in contents(enactor)]); lvl = 0 if load <= bl else (1 if load <= 2 * bl else (2 if load <= 3 * bl else (3 if load <= 6 * bl else 4))); names = ['None', 'Light', 'Medium', 'Heavy', 'X-Heavy']; move = int(get_attr(enactor, 'basic_move', 5)); emove = move * (5 - lvl) // 5; remove_effect(enactor, 'encumbered'); (None if lvl == 0 else apply_effect(enactor, 'modifier_effect', kind='encumbered', duration=0, check_mods={'all': -lvl})); pemit(enactor, 'Basic Lift ' + str(bl) + ' lbs. You carry ' + str(load) + ' lbs -> ' + names[lvl] + ' encumbrance (DX ' + str(-lvl) + ', Move ' + str(emove) + '/' + str(move) + ').')",
    "@create supply crate",
    "@set supply crate/weight = 25",
    "drop supply crate",
    "@create ammo case",
    "@set ammo case/weight = 45",
    "drop ammo case",
]

# docs/showcase/137_hunger_thirst.md
BUILD_137 = [
    "@dig The Mess Deck = mess, out",
    "mess",
    "@zone here = station",
    "@dig Cargo Hold = hold, mess",
    "hold",
    "@zone here = station",
    "mess",
    "@create life support monitor",
    "drop life support monitor",
    "@desc life support monitor = A wall panel of green readouts, one bar per crewman, ticking slowly downward.",
    "@behavior life support monitor = script_ticker, interval:1",
    "@set life support monitor/on_tick = [eval_attr(me, 'tick_meter', p.id) for r in zone_rooms('station') for p in contents(r) if has_tag(p, 'player')]",
    "@set life support monitor/tick_meter = p = get('#' + arg0); (None if not p else (set_attr(p, 'hunger', max(0, int(get_attr(p, 'hunger', 100)) - 10)), set_attr(p, 'thirst', max(0, int(get_attr(p, 'thirst', 100)) - 15)), eval_attr(me, 'assess', p.id)))",
    "@set life support monitor/assess = p = get('#' + arg0); h = int(get_attr(p, 'hunger', 100)); t = int(get_attr(p, 'thirst', 100)); (eval_attr(me, 'weaken', p.id) if (h <= 0 or t <= 0) else (pemit(p, 'Your stomach growls; your mouth is dry.') if (h <= 40 or t <= 40) else None))",
    "@set life support monitor/weaken = p = get('#' + arg0); m = dict(get_attr(p, 'check_mods', {}) or {}); m['starving'] = {'all': -2}; (None if has_tag(p, 'starving') else (add_tag(p, 'starving'), set_attr(p, 'check_mods', m), pemit(p, 'You are faint from hunger and thirst. (-2 to everything)')))",
    "@create ration dispenser",
    "drop ration dispenser",
    "@desc ration dispenser = A humming galley unit. EAT to draw a ration pack and a water bulb.",
    "@set ration dispenser/cmd_eat = $eat: (set_attr(enactor, 'hunger', 100), set_attr(enactor, 'thirst', 100), eval_attr(me, 'refresh', enactor.id), remit(loc(enactor), name(enactor) + ' tears into a ration pack and drains a water bulb.'))",
    "@set ration dispenser/refresh = p = get('#' + arg0); m = dict(get_attr(p, 'check_mods', {}) or {}); (m.pop('starving') if 'starving' in m else 0); set_attr(p, 'check_mods', m); remove_tag(p, 'starving')",
]

# docs/showcase/138_sleep_rest.md
BUILD_138 = [
    "@dig The Bunkroom = bunkroom, out",
    "bunkroom",
    "@create field cot",
    "drop field cot",
    "@desc field cot = A canvas cot with a thin blanket. REST to lie down and recover; WAKE to rise.",
    "@set field cot/cmd_rest = $rest: (pemit(enactor, 'You are already resting.') if has_tag(enactor, 'resting') else (apply_effect(enactor, 'regeneration', kind='resting', heal=3, duration=0, interval=1), remit(loc(enactor), name(enactor) + ' lies back on the cot and closes their eyes.')))",
    "@set field cot/cmd_wake = $wake: (remove_effect(enactor, 'resting'), remit(loc(enactor), name(enactor) + ' stirs and sits up.')) if has_tag(enactor, 'resting') else pemit(enactor, 'You are already up and about.')",
    "@set here/on_check = block('You are wrapped in sleep -- WAKE before you can move.') if has_atag('movement') and adata('exit') and has_tag(actor, 'resting') else None",
]

# docs/showcase/140_death_cloning.md
BUILD_140 = [
    "@dig The Clone Bay = clonebay, out",
    "clonebay",
    "@zone here = colony",
    "@dig The Combat Deck = deck, clonebay",
    "deck",
    "@zone here = colony",
    "clonebay",
    "@create resurrection controller",
    "drop resurrection controller",
    "@desc resurrection controller = A bank of glass vats trailing coolant mist, wired to a patient monitor that never blinks.",
    "@set resurrection controller/bay = The Clone Bay",
    "@set resurrection controller/fee = 50",
    "@behavior resurrection controller = script_ticker, interval:1",
    "@set resurrection controller/on_tick = [eval_attr(me, 'revive', p.id) for r in zone_rooms('colony') for p in contents(r) if has_tag(p, 'player') and has_tag(p, 'unconscious')]",
    "@set resurrection controller/revive = p = get('#' + arg0); bay = get(V('bay', '')); fee = int(V('fee', 50)); (None if not (p and bay) else (teleport_obj(p, bay), remove_tag(p, 'unconscious'), set_attr(p, 'hp', int(get_attr(p, 'max_hp', 10))), (transfer_credits(p, me, fee) if credits(p) >= fee else set_attr(p, 'credits', 0)), set_attr(p, 'clone_count', int(get_attr(p, 'clone_count', 0)) + 1), pemit(p, 'Cold light, then breath. You wake in a fresh body in the clone bay -- whole again. (clone #' + str(get_attr(p, 'clone_count', 1)) + ', ' + str(fee) + ' credits debited)'), remit(bay, 'A clone vat cracks open with a hiss -- ' + name(p) + ' is reborn.')))",
]

# docs/showcase/141_character_sheet.md
BUILD_141 = [
    "@dig The Med Scanner Alcove = alcove, out",
    "alcove",
    "@create bio-scanner",
    "drop bio-scanner",
    "@desc bio-scanner = A full-body med scanner on a swivel arm. Type SHEET to print your service record.",
    "@set bio-scanner/skills = melee guns stealth first_aid observation",
    "@set bio-scanner/cmd_sheet = $sheet: pemit(enactor, eval_attr(me, 'render', enactor.id))",
    """@set bio-scanner/render = p = get('#' + arg0); bar = repeat('=', 40); hp = int(get_attr(p, 'hp', 0)); mhp = max(1, int(get_attr(p, 'max_hp', 1))); filled = max(0, min(10, hp * 10 // mhp)); hpbar = f'[{repeat("#", filled)}{repeat("-", 10 - filled)}]'; sk = [s for s in V('skills', '').split() if get_attr(p, 'skill_' + s) != None]; cond = [t for t in tags(p) if t in ['wounded', 'bleeding', 'resting', 'starving', 'unconscious', 'encumbered', 'restrained']]; result = '\\n'.join([bar, f'  {name(p)}  --  {get_attr(p, "template", "unregistered")}', bar, f'  ST {get_attr(p, "strength", 10)}    DX {get_attr(p, "dexterity", 10)}    IQ {get_attr(p, "intelligence", 10)}    HT {get_attr(p, "health", 10)}', f'  HP {hpbar} {hp}/{mhp}     Dodge {get_attr(p, "dodge", 8)}', f'  CP {get_attr(p, "character_points", 0)}', '  Skills: ' + (', '.join([f'{s}-{get_attr(p, "skill_" + s)}' for s in sk]) or 'none trained'), '  Status: ' + (', '.join(cond) or 'nominal'), bar])""",
]

# docs/showcase/142_traits_in_play.md
BUILD_142 = [
    "@dig The Gene Clinic = clinic, out",
    "clinic",
    "@create trait console",
    "drop trait console",
    "@desc trait console = A surgical booth of needles and green gel. GRAFT <trait> to splice one in; PROVE to test yourself. Stock: reflexes, keen eye, claustrophobia.",
    '@set trait console/traits = {"reflexes": {"kind": "combat_reflexes", "mods": {"all": 1}, "msg": "Your reflexes wind tight -- +1 to everything."}, "keen_eye": {"kind": "keen_eye", "mods": {"observation": 2}, "msg": "The world sharpens -- +2 Observation."}, "claustrophobia": {"kind": "claustrophobia", "mods": {}, "msg": "A cold knot ties itself in your chest at the thought of tight spaces."}}',
    "@set trait console/cmd_graft = $graft *: t = trim(arg0).lower().replace(' ', '_'); d = V('traits', {}).get(t); (pemit(enactor, 'No such trait on file.') if not d else (pemit(enactor, 'That trait is already spliced in.') if has_tag(enactor, d['kind']) else apply_effect(enactor, 'modifier_effect', kind=d['kind'], duration=0, check_mods=d['mods'], apply_msg=d['msg'])))",
    "@set trait console/cmd_prove = $prove: pemit(enactor, 'Observation: ' + ('pass' if skill_check(enactor, 'observation') else 'fail') + ' | Melee: ' + ('pass' if skill_check(enactor, 'melee') else 'fail'))",
    "@dig The Crawlway = crawlway, clinic",
    "crawlway",
    "@tag here = cramped",
    "@set here/on_enter = (apply_effect(enactor, 'modifier_effect', kind='panic', duration=4, check_mods={'all': -2}, apply_msg='The walls crush inward. Your breath saws and your hands shake. (-2, panicking)') if has_tag(enactor, 'claustrophobia') and not has_tag(enactor, 'panic') else None)",
    "clinic",
]

# docs/showcase/143_xp_spending.md
BUILD_143 = [
    "@dig The Training Annex = annex, out",
    "annex",
    "@create training terminal",
    "drop training terminal",
    "@desc training terminal = A neural-drill rig with a padded headset. STUDY <skill> to spend character points -- one drill per skill, then it needs time to set.",
    "@set training terminal/cost = 4",
    "@set training terminal/cooldown = 3600",
    "@set training terminal/cmd_study = $study *: s = trim(arg0).lower().replace(' ', '_'); (pemit(enactor, 'Name a skill to drill.') if not s else eval_attr(me, 'drill', enactor.id, s))",
    "@set training terminal/drill = p = get('#' + arg0); s = arg1; cost = int(V('cost', 4)); cd = int(V('cooldown', 3600)); last = int(V('last_' + p.id + '_' + s, 0)); cp = int(get_attr(p, 'character_points', 0)); cur = int(get_attr(p, 'skill_' + s, get_attr(p, 'dexterity', 10))); (pemit(p, 'Neural buffers still consolidating ' + s.replace('_', ' ') + ' -- ' + str(cd - (now() - last)) + 's to go.') if now() - last < cd else (pemit(p, 'Drilling ' + s.replace('_', ' ') + ' costs ' + str(cost) + ' CP; you have ' + str(cp) + '.') if cp < cost else (set_attr(p, 'skill_' + s, cur + 1), set_attr(p, 'character_points', cp - cost), set_attr(me, 'last_' + p.id + '_' + s, now()), pemit(p, 'You drill ' + s.replace('_', ' ') + ' hard. It clicks -- now ' + str(cur + 1) + '. (' + str(cp - cost) + ' CP left)'))))",
]


# --- Harness -------------------------------------------------------------------


def level_resolver(obj, skill, modifier):
    """Diceless: success iff skill level + modifier >= 10. `modifier` already
    carries the summed condition modifiers (check()'s condition_modifier),
    so injuries, encumbrance, hunger, and traits all fold in here."""
    effective = skill_level(obj, skill) + modifier
    return CheckResult(effective >= 10, effective - 10, 10, effective, skill)


@pytest.fixture
def sim():
    simulator = Simulator()
    set_check_resolver(level_resolver)
    # prompt() finds player sessions through the engine's session manager;
    # the Simulator leaves it to the test to wire (as the combat suite does).
    simulator.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(simulator._sessions.values()))
    yield simulator
    set_check_resolver(None)
    simulator.close()


@pytest.fixture
def combat():
    """A live CombatManager on a diceless ruleset; beats fired by hand."""
    from realm.combat.combatant import clear_combatant_cache
    from realm.combat.manager import CombatManager, set_combat_manager
    from realm.combat.rulesets.gurps import GURPSRuleset
    from realm.combat.system import CombatSystem

    class SteadyRuleset(GURPSRuleset):
        def roll_3d6(self):
            return 10, [3, 3, 4]

        def roll_damage(self, attacker, defender, attack_result, weapon=None):
            from realm.combat.ruleset import DamageResult, DamageType
            return DamageResult(total=3, damage_by_type={DamageType.PHYSICAL: 3})

    clear_combatant_cache()
    manager = CombatManager(
        CombatSystem(ruleset=SteadyRuleset()),
        beat_min=4.0, beat_max=600.0, beat_default=300.0,
    )
    set_combat_manager(manager)
    yield manager
    manager.stop_all()
    set_combat_manager(None)
    clear_combatant_cache()


async def run_lines(sim, player, lines):
    for line in lines:
        await sim.do(player, line)
        set_check_resolver(level_resolver)


async def build(sim, lines, *, admin=False):
    """Run one tutorial's build transcript as a builder from Limbo."""
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
    builder.add_tag("builder")
    if admin:
        builder.add_tag("admin")
    await run_lines(sim, builder, lines)
    out = "\n".join(sim.seen(builder))
    for flag in BUILD_RED_FLAGS:
        assert flag not in out, f"build tripped {flag!r}:\n{out}"
    return builder


def room(sim, name):
    matches = [o for o in sim.store.find_cached(name=name) if o.has_tag("room")]
    assert matches, f"no room named {name!r}"
    return matches[0]


def obj(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no object named {name!r}"
    return matches[0]


def text(sim, player):
    return "\n".join(sim.seen(player))


async def rounds(manager, someone, n=1):
    encounter = manager.encounter_of(someone)
    assert encounter is not None, f"{someone.name} is not in a fight"
    for _ in range(n):
        await encounter.resolve_round()


# --- 132. Chargen walkthrough --------------------------------------------------


class TestChargenWalkthrough:

    async def test_wizard_writes_a_full_sheet(self, sim):
        await build(sim, BUILD_132, admin=True)
        booth = room(sim, "The Induction Booth")
        rook = sim.player("Rook", location=booth)

        await sim.do(rook, "enlist")
        assert "Choose a background -- scout, soldier" in text(sim, rook)
        sess = sim.session(rook)
        assert sess.input_handler is not None, "enlist should prompt"

        await sess.input_handler(sess, "soldier")
        assert "Pick a bonus skill" in text(sim, rook)
        assert rook.db.get("strength") == 12
        assert rook.db.get("skill_guns") == 12
        assert rook.db.get("template") == "soldier"

        sess = sim.session(rook)
        assert sess.input_handler is not None, "background should re-prompt"
        await sess.input_handler(sess, "melee")
        out = text(sim, rook)
        assert "Induction complete. HP 12, Dodge 9" in out
        assert rook.db.get("skill_melee") == 13      # soldier's 12, +1 bonus
        assert int(rook.db.get("hp")) == 12          # derived from ST
        assert int(rook.db.get("max_hp")) == 12
        assert int(rook.db.get("dodge")) == 9        # 7 + (11+12)//8

    async def test_bad_background_reprompts_then_takes_the_next_answer(self, sim):
        await build(sim, BUILD_132, admin=True)
        booth = room(sim, "The Induction Booth")
        dex = sim.player("Dex", location=booth)

        await sim.do(dex, "enlist")
        sess = sim.session(dex)
        await sess.input_handler(sess, "wizard")
        assert "No such background." in text(sim, dex)
        assert dex.db.get("template") is None

        sess = sim.session(dex)
        await sess.input_handler(sess, "scout")
        assert dex.db.get("template") == "scout"
        assert dex.db.get("skill_stealth") == 13

    async def test_enlisting_twice_is_refused(self, sim):
        await build(sim, BUILD_132, admin=True)
        booth = room(sim, "The Induction Booth")
        vet = sim.player("Vet", location=booth, template="soldier")
        await sim.do(vet, "enlist")
        assert "already filed" in text(sim, vet)


# --- 135. Injury & treatment ---------------------------------------------------


class TestInjuryTreatment:

    async def test_injury_folds_into_rolls_and_treatment_clears_it(self, sim):
        await build(sim, BUILD_135)
        medbay = room(sim, "The Med Bay")
        zeke = sim.player("Zeke", location=medbay, skill_melee=12,
                          hp=20, max_hp=20)
        mara = sim.player("Mara", location=medbay, skill_first_aid=14)
        ferd = sim.player("Ferd", location=medbay, skill_first_aid=6)

        await sim.do(mara, "check Zeke")
        assert "a Melee roll SUCCEEDS cleanly." in text(sim, mara)

        await sim.do(zeke, "grip wire")
        assert "grabs the live wire and convulses!" in text(sim, zeke)
        assert zeke.has_tag("wounded")
        assert int(zeke.db.get("hp")) == 18                 # -2 HP
        assert zeke.db.get("check_mods") == {"wounded": {"all": -3}}

        await sim.do(mara, "check Zeke")
        assert "FAILS -- the hand is shaking." in text(sim, mara)   # 12 - 3 = 9

        await sim.do(ferd, "splint Zeke")                   # first_aid 6: fails
        assert "Your hands slip on the splint" in text(sim, ferd)
        assert zeke.has_tag("wounded")

        await sim.do(mara, "splint Zeke")                   # first_aid 14: works
        assert "braces and binds Zeke's arm" in text(sim, mara)
        assert not zeke.has_tag("wounded")
        assert not zeke.db.get("check_mods")                # condition stripped
        assert int(zeke.db.get("hp")) == 19                 # the dressing's +1

        await sim.do(mara, "check Zeke")
        assert "a Melee roll SUCCEEDS cleanly." in text(sim, mara)

    async def test_injury_heals_on_its_own_timer(self, sim):
        await build(sim, BUILD_135)
        medbay = room(sim, "The Med Bay")
        zeke = sim.player("Zeke", location=medbay, skill_melee=12,
                          hp=20, max_hp=20)
        await sim.do(zeke, "grip wire")
        assert zeke.has_tag("wounded")
        for _ in range(10):
            await deliver_beat(zeke)
        assert not zeke.has_tag("wounded")                  # clotted after 10 beats
        assert "the injury has healed." in text(sim, zeke).lower()

    async def test_grab_and_check_refusals(self, sim):
        await build(sim, BUILD_135)
        medbay = room(sim, "The Med Bay")
        zeke = sim.player("Zeke", location=medbay, skill_melee=12,
                          hp=20, max_hp=20)
        await sim.do(zeke, "check Nobody")
        assert "No one here by that name." in text(sim, zeke)
        await sim.do(zeke, "grip wire")
        await sim.do(zeke, "grip wire")                     # already wounded
        assert "your arm still remembers it." in text(sim, zeke)


# --- 136. Encumbrance ----------------------------------------------------------


class TestEncumbrance:

    async def test_load_scales_the_penalty(self, sim):
        await build(sim, BUILD_136)
        dock = room(sim, "The Loading Dock")
        hef = sim.player("Hef", location=dock, strength=10, basic_move=5)

        await sim.do(hef, "heft")
        assert "Basic Lift 20 lbs. You carry 0 lbs -> None encumbrance (DX 0, Move 5/5)." \
            in text(sim, hef)
        assert not hef.db.get("check_mods")

        await sim.do(hef, "get supply crate")
        await sim.do(hef, "heft")
        assert "You carry 25 lbs -> Light encumbrance (DX -1, Move 4/5)." in text(sim, hef)
        assert hef.db.get("check_mods") == {"encumbered": {"all": -1}}

        await sim.do(hef, "get ammo case")
        await sim.do(hef, "heft")
        assert "You carry 70 lbs -> Heavy encumbrance (DX -3, Move 2/5)." in text(sim, hef)
        assert hef.db.get("check_mods") == {"encumbered": {"all": -3}}

        await sim.do(hef, "drop ammo case")
        await sim.do(hef, "heft")
        assert "You carry 25 lbs -> Light encumbrance (DX -1, Move 4/5)." in text(sim, hef)

        await sim.do(hef, "drop supply crate")
        await sim.do(hef, "heft")
        assert "You carry 0 lbs -> None encumbrance (DX 0, Move 5/5)." in text(sim, hef)
        assert not hef.db.get("check_mods")

    async def test_strength_raises_the_ceiling(self, sim):
        await build(sim, BUILD_136)
        dock = room(sim, "The Loading Dock")
        ox = sim.player("Ox", location=dock, strength=14, basic_move=5)
        await sim.do(ox, "get supply crate")
        await sim.do(ox, "get ammo case")
        await sim.do(ox, "heft")                            # BL 39, 70 lbs -> Light
        assert "Basic Lift 39 lbs. You carry 70 lbs -> Light encumbrance" in text(sim, ox)


# --- 137. Hunger & thirst ------------------------------------------------------


class TestHungerThirst:

    async def test_meters_drain_warn_and_faint_then_a_ration_restores(self, sim):
        builder = await build(sim, BUILD_137, admin=True)
        mess = room(sim, "The Mess Deck")
        vale = sim.player("Vale", location=mess)

        for _ in range(7):
            await sim.do(builder, "@tr life support monitor/on_tick")
            set_check_resolver(level_resolver)

        stream = text(sim, vale)
        assert "Your stomach growls; your mouth is dry." in stream   # thresholds
        assert "You are faint from hunger and thirst." in stream     # bottomed out
        assert vale.has_tag("starving")
        assert vale.db.get("check_mods") == {"starving": {"all": -2}}
        assert int(vale.db.get("thirst")) == 0
        assert int(vale.db.get("hunger")) == 30

        await sim.do(vale, "eat")
        assert "tears into a ration pack" in text(sim, vale)
        assert int(vale.db.get("hunger")) == 100
        assert int(vale.db.get("thirst")) == 100
        assert not vale.has_tag("starving")
        assert not vale.db.get("check_mods")

    async def test_no_meters_outside_the_zone(self, sim):
        builder = await build(sim, BUILD_137, admin=True)
        limbo = room(sim, "Limbo")
        drifter = sim.player("Drifter", location=limbo)      # unzoned
        for _ in range(5):
            await sim.do(builder, "@tr life support monitor/on_tick")
            set_check_resolver(level_resolver)
        assert drifter.db.get("hunger") is None              # never touched


# --- 138. Sleep & rest ---------------------------------------------------------


class TestSleepRest:

    async def test_rest_heals_locks_movement_and_wake_ends_it(self, sim):
        await build(sim, BUILD_138)
        bunkroom = room(sim, "The Bunkroom")
        nyx = sim.player("Nyx", location=bunkroom, hp=10, max_hp=30)

        await deliver_beat(nyx)
        assert int(nyx.db.get("hp")) == 10                  # no passive regen

        await sim.do(nyx, "rest")
        assert "lies back on the cot" in text(sim, nyx)
        assert nyx.has_tag("resting")

        for _ in range(3):
            await deliver_beat(nyx)
        assert int(nyx.db.get("hp")) == 19                  # +3 a beat

        await sim.do(nyx, "out")
        assert "You are wrapped in sleep -- WAKE before you can move." in text(sim, nyx)
        assert nyx.location is bunkroom

        await sim.do(nyx, "wake")
        assert not nyx.has_tag("resting")
        await deliver_beat(nyx)
        assert int(nyx.db.get("hp")) == 19                  # healer gone

        await sim.do(nyx, "out")
        assert nyx.location is room(sim, "Limbo")

    async def test_wake_when_up_is_a_no_op(self, sim):
        await build(sim, BUILD_138)
        bunkroom = room(sim, "The Bunkroom")
        nyx = sim.player("Nyx", location=bunkroom, hp=10, max_hp=30)
        await sim.do(nyx, "wake")
        assert "already up and about." in text(sim, nyx)


# --- 140. Death & cloning ------------------------------------------------------


class TestDeathCloning:

    async def test_downed_player_is_cloned_and_billed(self, sim, combat):
        builder = await build(sim, BUILD_140, admin=True)
        clonebay = room(sim, "The Clone Bay")
        deck = room(sim, "The Combat Deck")
        cass = sim.player("Cass", location=deck, hp=4, max_hp=30,
                          skill_melee=16, dodge=0, credits=100)
        bruiser = sim.obj("bruiser", location=deck, tags=["npc"],
                          hp=30, max_hp=30, skill_melee=16, dodge=12)

        await sim.do(cass, "attack bruiser")
        for _ in range(3):
            if cass.has_tag("unconscious"):
                break
            await rounds(combat, cass)
        assert cass.has_tag("unconscious")                  # players fall, don't die
        assert cass.location is deck

        await sim.do(builder, "@tr resurrection controller/on_tick")
        assert cass.location is clonebay                    # reborn across the station
        assert not cass.has_tag("unconscious")
        assert int(cass.db.get("hp")) == 30                 # restored to full
        assert int(cass.db.get("credits")) == 50            # 100 - 50 clone fee
        assert int(cass.db.get("clone_count")) == 1
        out = text(sim, cass)
        assert "is reborn." in out
        assert "You wake in a fresh body" in out

    async def test_npc_death_leaves_a_corpse(self, sim, combat):
        await build(sim, BUILD_140, admin=True)
        deck = room(sim, "The Combat Deck")
        ryn = sim.player("Ryn", location=deck, hp=30, max_hp=30,
                         skill_melee=16, dodge=12)
        mook = sim.obj("deck mook", location=deck, tags=["npc"],
                       hp=3, max_hp=3, dodge=0)
        await sim.do(ryn, "attack deck mook")
        await rounds(combat, ryn)
        corpses = [o for o in deck.contents if o.name.startswith("corpse of")]
        assert len(corpses) == 1                            # native corpse path


# --- 141. Character sheet -------------------------------------------------------


class TestCharacterSheet:

    async def test_formatted_sheet_and_native_points(self, sim):
        await build(sim, BUILD_141)
        alcove = room(sim, "The Med Scanner Alcove")
        ivo = sim.player("Ivo", location=alcove, template="soldier",
                         strength=12, dexterity=11, intelligence=10, health=12,
                         hp=9, max_hp=12, dodge=9, character_points=6,
                         skill_melee=13, skill_guns=12)
        ivo.add_tag("wounded")

        await sim.do(ivo, "sheet")
        out = text(sim, ivo)
        assert "Ivo  --  soldier" in out
        assert "ST 12    DX 11    IQ 10    HT 12" in out
        assert "HP [#######---] 9/12     Dodge 9" in out
        assert "CP 6" in out
        assert "Skills: melee-13, guns-12" in out
        assert "Status: wounded" in out

        # The native sheet is the always-current source of truth.
        await sim.do(ivo, "points")
        pts = text(sim, ivo)
        assert "Character points: 6" in pts
        assert "melee" in pts and "13" in pts

    async def test_untrained_and_nominal_read_cleanly(self, sim):
        await build(sim, BUILD_141)
        alcove = room(sim, "The Med Scanner Alcove")
        raw = sim.player("Raw", location=alcove, hp=10, max_hp=10)
        await sim.do(raw, "sheet")
        out = text(sim, raw)
        assert "Skills: none trained" in out
        assert "Status: nominal" in out


# --- 142. Traits in play -------------------------------------------------------


class TestTraitsInPlay:

    async def test_modifier_traits_shift_rolls_and_a_phobia_bites(self, sim):
        await build(sim, BUILD_142)
        clinic = room(sim, "The Gene Clinic")
        rell = sim.player("Rell", location=clinic,
                          skill_observation=8, skill_melee=9)

        await sim.do(rell, "prove")
        assert "Observation: fail | Melee: fail" in text(sim, rell)

        await sim.do(rell, "graft reflexes")
        assert "reflexes wind tight" in text(sim, rell)
        await sim.do(rell, "prove")
        assert "Observation: fail | Melee: pass" in text(sim, rell)   # +1 all

        await sim.do(rell, "graft keen eye")
        await sim.do(rell, "prove")
        assert "Observation: pass | Melee: pass" in text(sim, rell)   # +2 obs

        await sim.do(rell, "graft claustrophobia")
        assert rell.has_tag("claustrophobia")
        await sim.do(rell, "crawlway")
        assert "The walls crush inward." in text(sim, rell)
        assert rell.has_tag("panic")

        await sim.do(rell, "clinic")
        await sim.do(rell, "prove")
        assert "Observation: fail | Melee: fail" in text(sim, rell)   # panic -2 drags both

    async def test_unknown_trait_and_double_graft(self, sim):
        await build(sim, BUILD_142)
        clinic = room(sim, "The Gene Clinic")
        rell = sim.player("Rell", location=clinic,
                          skill_observation=8, skill_melee=9)
        await sim.do(rell, "graft flight")
        assert "No such trait on file." in text(sim, rell)
        await sim.do(rell, "graft reflexes")
        await sim.do(rell, "graft reflexes")
        assert "already spliced in." in text(sim, rell)


# --- 143. XP spending ----------------------------------------------------------


class TestXpSpending:

    async def test_study_spends_cp_gated_by_cooldown_and_purse(self, sim):
        builder = await build(sim, BUILD_143, admin=True)
        annex = room(sim, "The Training Annex")
        dex = sim.player("Dex", location=annex, character_points=12,
                         dexterity=10, skill_melee=10, skill_stealth=10)

        await sim.do(dex, "study melee")
        assert "You drill melee hard. It clicks -- now 11. (8 CP left)" in text(sim, dex)
        assert dex.db.get("skill_melee") == 11
        assert int(dex.db.get("character_points")) == 8

        await sim.do(dex, "study melee")                    # cooldown
        assert "still consolidating melee" in text(sim, dex)
        assert dex.db.get("skill_melee") == 11              # unchanged

        await sim.do(dex, "study stealth")                  # a different skill: free
        assert "It clicks -- now 11. (4 CP left)" in text(sim, dex)

        await run_lines(sim, builder, ["@set training terminal/cooldown = 0"])
        await sim.do(dex, "study melee")                    # cooldown lifted
        assert "It clicks -- now 12. (0 CP left)" in text(sim, dex)
        assert int(dex.db.get("character_points")) == 0

        await sim.do(dex, "study guns")                     # out of points
        assert "Drilling guns costs 4 CP; you have 0." in text(sim, dex)
        assert dex.db.get("skill_guns") is None

    async def test_native_improve_is_the_ungated_baseline(self, sim):
        await build(sim, BUILD_143, admin=True)
        annex = room(sim, "The Training Annex")
        pat = sim.player("Pat", location=annex, character_points=4,
                         dexterity=10, skill_stealth=11)
        await sim.do(pat, "improve stealth")
        assert "You train stealth to 12" in text(sim, pat)
        assert pat.db.get("skill_stealth") == 12
        assert int(pat.db.get("character_points")) == 0


# =========================================================================
# Docs <-> tests sync — the transcripts above must match the tutorials
# =========================================================================

from pathlib import Path  # noqa: E402

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

DOC_TRANSCRIPTS = {
    "132_chargen_walkthrough.md": BUILD_132,
    "135_injury_treatment.md": BUILD_135,
    "136_encumbrance.md": BUILD_136,
    "137_hunger_thirst.md": BUILD_137,
    "138_sleep_rest.md": BUILD_138,
    "140_death_cloning.md": BUILD_140,
    "141_character_sheet.md": BUILD_141,
    "142_traits_in_play.md": BUILD_142,
    "143_xp_spending.md": BUILD_143,
}


def test_tutorial_docs_contain_the_exact_tested_command_lines():
    """Every Build-it line exercised above appears verbatim in its doc, so
    the tutorials can never drift from what the tests prove works."""
    for doc_name, lines in DOC_TRANSCRIPTS.items():
        doc_text = (DOCS / doc_name).read_text(encoding="utf-8")
        for line in lines:
            assert line in doc_text, (
                f"{doc_name} is missing a tested tutorial line:\n{line}")
