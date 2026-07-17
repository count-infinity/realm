"""
Showcase verification — Combat & Conflict Extensions (standalone tutorials).

Items: 109 cover system, 111 grenades, 112 non-lethal takedowns,
113 dueling system, 114 bounty board, 115 arena with spectators,
117 armor degradation, 118 bleeding & first aid, 119 NPC morale,
120 combat replay log.

Every command line in each tutorial's "Build it" section is driven
through the real dispatcher (raw input in -> session output out),
exactly as typed in the docs; the plays then exercise the tutorials'
"Try it" flows and assert outcomes.

Determinism: skill checks use the level resolver (success iff effective
skill >= 10, contests go to the higher skill, ties to the opponent);
combat swings use a diceless GURPS ruleset (3d6 always rolls 10, damage
a flat 3 before DR). Encounter beats are fired by calling
resolve_round() by hand; wait() fuses fire on tick_waits() pumps;
out-of-combat effect beats advance via deliver_beat().
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.combat.manager import CombatManager, set_combat_manager
from realm.combat.rulesets.gurps import GURPSRuleset
from realm.combat.system import CombatSystem
from realm.core.beats import deliver_beat
from realm.core.checks import CheckResult, set_check_resolver, skill_level
from realm.testing import Simulator


def level_resolver(obj, skill, modifier):
    effective = skill_level(obj, skill) + modifier
    return CheckResult(
        success=effective >= 10,
        margin=effective - 10,
        roll=10,
        effective=effective,
        skill=skill,
    )


class SteadyRuleset(GURPSRuleset):
    """GURPS with the dice removed: 3d6 always 10, damage a flat 3."""

    def roll_3d6(self):
        return 10, [3, 3, 4]

    def roll_damage(self, attacker, defender, attack_result, weapon=None):
        from realm.combat.ruleset import DamageResult, DamageType
        return DamageResult(total=3, damage_by_type={DamageType.PHYSICAL: 3})


# --- Build transcripts (the tutorials' exact "Build it" lines) -----------------

# docs/showcase/109_cover_system.md
BUILD_109 = [
    "@dig The Killhouse = killhouse, out",
    "killhouse",
    "@create overturned dropship hull",
    "drop overturned dropship hull",
    "@desc overturned dropship hull = Half a cargo dropship, belly-up, its plating scorched and buckled. Good cover -- while it lasts.",
    "@tag overturned dropship hull = cover",
    "@create laser carbine",
    "@set laser carbine/damage_dice = 2d",
    "@set laser carbine/damage_type = burning",
    "@set laser carbine/skill_type = ranged",
    "@set laser carbine/acc = 2",
    "@tag laser carbine = ranged",
    "drop laser carbine",
    "@set overturned dropship hull/plating = 2",
    "@set overturned dropship hull/cmd_shred = $shred hull: p = get_attr(me, 'plating', 0) - 1; (pemit(enactor, 'The hull is already scrap.') if not has_tag(me, 'cover') else ((set_attr(me, 'plating', 0), remove_tag(me, 'cover'), remit(loc(me), name(enactor) + ' blasts the hull apart -- it is cover for no one now!')) if p <= 0 else (set_attr(me, 'plating', p), remit(loc(me), name(enactor) + ' tears chunks off the hull. It will not stand much more.'))))",
]

# docs/showcase/111_grenades.md
BUILD_111 = [
    "@dig The Bunker = bunker, out",
    "bunker",
    "@dig The Trench = trench, bunker",
    "@create reflexes",
    "@tag reflexes = skill_def",
    "@set reflexes/stat = dexterity",
    "@set reflexes/penalty = 0",
    "@create throwing",
    "@tag throwing = skill_def",
    "@set throwing/stat = dexterity",
    "@set throwing/penalty = 0",
    "@reload",
    "@create frag grenade",
    "@set frag grenade/fuse = 6",
    "@set frag grenade/cmd_pull = $pull pin: pemit(enactor, 'Pick it up first -- you do not arm a grenade you are not holding.') if loc(me) != enactor else (pemit(enactor, 'The pin is already out!') if get_attr(me, 'armed', 0) else (set_attr(me, 'armed', 1), remit(loc(enactor), name(enactor) + ' pulls the pin. The spoon pings away.'), wait(get_attr(me, 'fuse', 6), 'trigger me/boom')))",
    "@set frag grenade/cmd_throw = $throw grenade *: doors = [e for e in exits(loc(enactor)) if not has_tag(e, 'closed')]; aimed = [e for e in doors if name(e) == trim(arg0)]; (pemit(enactor, 'You are not holding the grenade.') if loc(me) != enactor else (pemit(enactor, 'No open exit called ' + trim(arg0) + ' here.') if not aimed else eval_attr(me, 'fly', aimed[0].id)))",
    "@set frag grenade/fly = e = get('#' + arg0); good = skill_check(enactor, 'throwing'); others = [x for x in exits(loc(enactor)) if not has_tag(x, 'closed') and x != e]; pick = e if good or not others else others[rand(0, len(others) - 1)]; d = get('#' + str(get_attr(pick, 'destination', ''))); (None if not d else (remit(loc(enactor), name(enactor) + ' hurls the grenade through the ' + name(pick) + ' exit' + ('!' if pick == e else ' -- no, wide! It caroms off the frame and skips the wrong way!')), teleport_obj(me, d), remit(d, 'A grenade bounces in and skitters across the floor!')))",
    "@set frag grenade/boom = spot = loc(me); held = spot != None and not has_tag(spot, 'room'); (remit(loc(spot), 'The live grenade slips through ' + name(spot) + \"'s fingers!\"), teleport_obj(me, loc(spot)), wait(0, 'trigger me/boom')) if held else eval_attr(me, 'blast')",
    "@set frag grenade/blast = room = loc(me); del_attr(me, 'armed'); (None if not room else (remit(room, 'WHUMP. The grenade goes off in a fist of smoke and shrapnel!'), [pemit(o, 'You dive clear of the blast!') if skill_check(o, 'reflexes', -1) else (pemit(o, 'Shrapnel tears into you!'), damage(o, roll('2d6'))) for o in contents(room) if has_tag(o, 'player') or has_tag(o, 'npc')], destroy_obj(me)))",
    "drop frag grenade",
]

# docs/showcase/112_nonlethal_takedowns.md
BUILD_112 = [
    "@dig The Brig = brig, out",
    "brig",
    "@create fortitude",
    "@tag fortitude = skill_def",
    "@set fortitude/stat = health",
    "@set fortitude/penalty = 0",
    "@reload",
    "@create leather cosh",
    "drop leather cosh",
    "@desc leather cosh = A sand-filled sock of a weapon. SAP someone with it -- quietly.",
    "@set leather cosh/cmd_sap = $sap *: t = get(trim(arg0)); (pemit(enactor, 'No sign of them in reach.') if not (t and loc(t) == loc(enactor) and (has_tag(t, 'player') or has_tag(t, 'npc'))) else (pemit(enactor, 'They are already out cold.') if has_tag(t, 'unconscious') else ((remit(loc(enactor), name(enactor) + ' saps ' + name(t) + ' behind the ear -- they fold up like wet paper.'), apply_effect(t, 'modifier_effect', kind='unconscious', duration=8, apply_msg='A starburst of white -- then nothing.', expire_msg='You come to with a skull full of gravel.')) if contest(enactor, 'melee', t, 'fortitude') else remit(loc(enactor), name(t) + ' twists away from ' + name(enactor) + \"'s cosh!\"))))",
    "@create iron binders",
    "drop iron binders",
    "@desc iron binders = Rimed iron cuffs on a short chain. BIND the unconscious; RELEASE the forgiven.",
    "@set iron binders/cmd_bind = $bind *: t = get(trim(arg0)); (pemit(enactor, 'No sign of them in reach.') if not (t and loc(t) == loc(enactor)) else (pemit(enactor, 'They are wide awake -- put them down first.') if not has_tag(t, 'unconscious') else (pemit(enactor, 'They are already in irons.') if has_tag(t, 'restrained') else (apply_effect(t, 'modifier_effect', kind='restrained', duration=0), remit(loc(enactor), name(enactor) + ' snaps iron binders around ' + name(t) + \"'s wrists.\")))))",
    "@set iron binders/cmd_release = $release *: t = get(trim(arg0)); (remove_effect(t, 'restrained'), remit(loc(enactor), name(enactor) + ' unlocks the binders.')) if t and loc(t) == loc(enactor) and has_tag(t, 'restrained') else pemit(enactor, 'They are not in your irons.')",
    "@set here/on_check = block('The binders hold -- you are going nowhere.') if atype == 'event:on_leave' and has_tag(actor, 'restrained') else None",
]

# docs/showcase/113_dueling.md
BUILD_113 = [
    "@dig The Ring = ring, out",
    "ring",
    "@set here/on_check = block('The Ring hosts sanctioned duels only -- DUEL <name> to issue a challenge.') if atype == 'combat:on_attack' and not (has_tag(actor, 'duelist') and has_tag(target, 'duelist')) else None",
    "@create dueling stone",
    "drop dueling stone",
    "@desc dueling stone = A waist-high basalt block, its top hollowed into a coin bowl. DUEL <name> to put money on your grievance.",
    "@set dueling stone/stake = 25",
    "@set dueling stone/cmd_duel = $duel *: t = get(trim(arg0)); s = get_attr(me, 'stake', 25); (pemit(enactor, 'A duel is already in the making. Wait for it to settle.') if get_attr(me, 'challenged') else (pemit(enactor, 'They are not here to face you.') if not (t and has_tag(t, 'player') and loc(t) == loc(me) and t != enactor) else (pemit(enactor, 'One of you cannot cover the ' + str(s) + '-credit stake.') if credits(enactor) < s or credits(t) < s else (set_attr(me, 'challenger', enactor.id), set_attr(me, 'challenged', t.id), remit(loc(me), name(enactor) + ' lays a gauntlet on the dueling stone before ' + name(t) + '.'), prompt(t, name(enactor) + ' challenges you to a duel for ' + str(s) + ' credits. Type ACCEPT to fight -- anything else declines.', 'answer')))))",
    "@set dueling stone/answer = a = get('#' + str(get_attr(me, 'challenger', ''))); b = get('#' + str(get_attr(me, 'challenged', ''))); s = get_attr(me, 'stake', 25); (None if not (a and b and enactor == b) else ((del_attr(me, 'challenger'), del_attr(me, 'challenged'), remit(loc(me), name(b) + ' declines the duel. The gauntlet is returned.')) if trim(arg0).lower() != 'accept' else (transfer_credits(a, me, s), transfer_credits(b, me, s), add_tag(a, 'duelist'), add_tag(b, 'duelist'), remit(loc(me), 'The stakes -- ' + str(2 * s) + ' credits -- rattle into the stone. FIGHT!'), start_combat(a, b))))",
    "@set dueling stone/on_death = a = get('#' + str(get_attr(me, 'challenger', ''))); b = get('#' + str(get_attr(me, 'challenged', ''))); s = get_attr(me, 'stake', 25); w = enactor; (None if not (a and b and w and (w == a or w == b) and has_tag(w, 'duelist')) else (transfer_credits(me, w, 2 * s), remove_tag(a, 'duelist'), remove_tag(b, 'duelist'), del_attr(me, 'challenger'), del_attr(me, 'challenged'), remit(loc(me), name(w) + ' stands over a fallen rival. The stone pays out ' + str(2 * s) + ' credits.')))",
]

# docs/showcase/114_bounty_board.md
BUILD_114 = [
    "@dig The Bounty Office = office, out",
    "office",
    "@zone here = badlands",
    "@dig Rattler Gulch = gulch, office",
    "gulch",
    "@zone here = badlands",
    "office",
    "@create bounty board",
    "drop bounty board",
    "@desc bounty board = Sun-cracked cork and yellowed paper. POST <name> to draft a contract, then PAY this board to stake it. BOUNTIES lists what is open.",
    "@zone/master bounty board = badlands",
    "@set bounty board/cmd_post = $post *: set_attr(me, 'pending_' + enactor.id, trim(arg0)); pemit(enactor, 'Contract drafted on ' + trim(arg0) + '. Now stake the reward: PAY <amount> TO bounty board.')",
    "@set bounty board/on_payment = paid = credits(me) - get_attr(me, 'till', 0); set_attr(me, 'till', credits(me)); nm = get_attr(me, 'pending_' + enactor.id, ''); led = get_attr(me, 'ledger') or []; pot = paid + sum([e[1] for e in led if e[0] == nm]); (pemit(enactor, 'Draft a contract first: POST <name>.') if not nm else (set_attr(me, 'ledger', [e for e in led if e[0] != nm] + [[nm, pot]]), del_attr(me, 'pending_' + enactor.id), act(me, 'The office crier bellows: ' + str(pot) + ' credits on the head of ' + nm + '!', targeting='zone')))",
    "@set bounty board/cmd_bounties = $bounties: led = get_attr(me, 'ledger') or []; (pemit(enactor, 'The board is bare. The badlands sleep easy.') if not led else [pemit(enactor, '[WANTED] ' + e[0] + ' -- ' + str(e[1]) + ' credits.') for e in led])",
    "@set bounty board/on_death = led = get_attr(me, 'ledger') or []; heads = [o for o in contents(here) if get_attr(o, 'hp', 1) <= 0 and name(o) in [e[0] for e in led]]; pot = sum([e[1] for e in led if e[0] in [name(o) for o in heads]]); (None if not (heads and pot and enactor and has_tag(enactor, 'player')) else (transfer_credits(me, enactor, pot), set_attr(me, 'ledger', [e for e in led if e[0] not in [name(o) for o in heads]]), act(me, 'BOUNTY CLAIMED: ' + name(enactor) + ' collects ' + str(pot) + ' credits for ' + ', '.join([name(o) for o in heads]) + '.', targeting='zone')))",
    "gulch",
    "@create Dreg Farrow",
    "@tag Dreg Farrow = npc",
    "@set Dreg Farrow/hp = 6",
    "@set Dreg Farrow/max_hp = 6",
    "@set Dreg Farrow/skill_melee = 10",
    "@set Dreg Farrow/dodge = 0",
    "drop Dreg Farrow",
    "office",
]

# docs/showcase/115_arena_spectators.md
BUILD_115 = [
    "@dig The Fight Pit = pit, out",
    "pit",
    "@dig The Stands = seats, pit",
    "pit",
    "@create ringside bell",
    "drop ringside bell",
    "@desc ringside bell = A brass bell on a rope, sized to be heard over a crowd. It rings itself when blood is up.",
    "@set ringside bell/stands = The Stands",
    "@set ringside bell/relay = s = get(get_attr(me, 'stands', '')); (remit(s, '[pit] ' + str(arg0)) if s else None)",
    "@set ringside bell/tally = result = ' -- '.join([name(o) + ' ' + str(get_attr(o, 'hp', 0)) + '/' + str(get_attr(o, 'max_hp', 0)) for o in contents(loc(me)) if has_tag(o, 'in_combat')])",
    "@set ringside bell/on_attack = eval_attr(me, 'relay', name(enactor) + ' wades in! ' + eval_attr(me, 'tally'))",
    "@set ringside bell/on_damage = eval_attr(me, 'relay', name(enactor) + ' draws blood! ' + eval_attr(me, 'tally'))",
    "@set ringside bell/on_death = eval_attr(me, 'relay', 'THE CROWD ROARS -- ' + name(enactor) + ' takes the pit!')",
    "@set ringside bell/listen_taunt = ^*: eval_attr(me, 'relay', name(enactor) + ' bellows: ' + escape(arg0)) if enactor else None",
]

# docs/showcase/117_armor_degradation.md (an ADMIN build)
BUILD_117 = [
    "@dig The Outfitter = outfitter, out",
    "outfitter",
    "@create flak vest",
    "@tag flak vest = wearable",
    "@set flak vest/slot = torso",
    "@set flak vest/dr = 3",
    "@set flak vest/condition = 3",
    "@desc flak vest = Ceramic plates in a webbing carrier. [[c = get_attr(me, 'condition', 0); result = 'The plates look factory-fresh.' if c >= 3 else ('Cracks spider across the plates.' if c > 0 else 'The carrier is full of ceramic gravel. It will stop nothing.')]]",
    "@set flak vest/on_wear = c = get_attr(me, 'condition', 0); (pemit(enactor, 'The vest is shredded -- it will stop nothing until it is repaired.') if c <= 0 else (set_attr(enactor, 'damage_resistance', get_attr(me, 'dr', 3)), set_attr(enactor, 'armor_condition', c), set_attr(enactor, 'on_damage', get_attr(me, 'degrade')), pemit(enactor, 'You cinch the flak vest tight. (DR ' + str(get_attr(me, 'dr', 3)) + ', ' + str(c) + ' plates)')))",
    "@set flak vest/degrade = c = get_attr(me, 'armor_condition', 0); (None if c <= 0 else ((set_attr(me, 'armor_condition', 0), set_attr(me, 'damage_resistance', 0), pemit(me, 'Your vest takes the brunt -- and comes apart at the seams. It will stop nothing more.')) if c <= 1 else (set_attr(me, 'armor_condition', c - 1), pemit(me, 'Your vest soaks the worst of it. (' + str(c - 1) + ' plates left)'))))",
    "@set flak vest/on_remove = set_attr(me, 'condition', get_attr(enactor, 'armor_condition', 0)); set_attr(enactor, 'damage_resistance', 0); del_attr(enactor, 'armor_condition'); del_attr(enactor, 'on_damage'); pemit(enactor, 'You shrug out of the vest.')",
    "drop flak vest",
    "@create mending bench",
    "drop mending bench",
    "@desc mending bench = A scarred workbench of clamps and rivet guns. Drop armor here and REPAIR VEST.",
    "@set mending bench/cmd_repair = $repair vest: v = get('flak vest'); (pemit(enactor, 'Lay the vest on the bench first -- drop it here.') if not (v and loc(v) == loc(me)) else ((set_attr(v, 'condition', 3), remit(loc(me), name(enactor) + ' hammers the plating flat and rivets in fresh ceramic.')) if skill_check(enactor, 'armoury') else pemit(enactor, 'You bend a plate the wrong way. No good.')))",
]

# docs/showcase/118_bleeding_first_aid.md
BUILD_118 = [
    "@dig The Red Yard = yard, out",
    "yard",
    "@create triage post",
    "drop triage post",
    "@desc triage post = A leaning pole flying a faded red cross. It has seen worse days than yours.",
    "@set triage post/on_damage = [apply_effect(o, 'damage_over_time', kind='bleeding', damage=1, interval=1, duration=8, tick_msg='Your wound runs red -- the blood keeps coming.', room_msg='{name} is losing blood.', expire_msg='The wound finally clots.') for o in contents(here) if (has_tag(o, 'player') or has_tag(o, 'npc')) and not has_tag(o, 'bleeding') and not has_tag(o, 'unconscious') and get_attr(o, 'hp', 0) > 0 and get_attr(o, 'hp', 0) < get_attr(o, 'max_hp', 0)]",
    "@create field satchel",
    "drop field satchel",
    "@desc field satchel = Rolled dressings, a bone needle, gut thread. BANDAGE <name> to stop a bleed.",
    "@set field satchel/cmd_bandage = $bandage *: t = get(trim(arg0)); (pemit(enactor, 'No patient by that name here.') if not (t and loc(t) == loc(enactor)) else (pemit(enactor, 'They are not bleeding.') if not has_tag(t, 'bleeding') else ((remove_effect(t, 'bleeding'), heal(t, 1), remit(loc(enactor), name(enactor) + ' ties off ' + name(t) + \"'s wound. The bleeding stops.\")) if skill_check(enactor, 'first_aid') else pemit(enactor, 'The dressing soaks through. It will not hold.'))))",
]

# docs/showcase/119_npc_morale.md
BUILD_119 = [
    "@dig Raider Lair = lair, out",
    "lair",
    "@create nerve",
    "@tag nerve = skill_def",
    "@set nerve/stat = health",
    "@set nerve/penalty = 0",
    "@reload",
    "@create Vex",
    "@tag Vex = npc",
    "@set Vex/hp = 12",
    "@set Vex/max_hp = 12",
    "@set Vex/skill_melee = 12",
    "@set Vex/dodge = 0",
    "@set Vex/health = 8",
    "@set Vex/dexterity = 14",
    "drop Vex",
    '@behavior Vex = aggressive, taunt:"Your boots -- I want them."',
    "@set Vex/hitprcnt = 50",
    "@set Vex/on_hitprcnt = detach_behavior(me, 'aggressive'); (say('I yield! I yield -- the loot is yours, only stop!'), set_attr(me, 'combat_strategy', [['', 'wait']]), add_tag(me, 'surrendered'), adjust_disposition(me, enactor, 5)) if not skill_check(me, 'nerve') else (say('Not like this!'), attach_behavior(me, 'fleeing', flee_percent=99))",
]

# docs/showcase/120_combat_replay.md
BUILD_120 = [
    "@dig The Fight Cage = cage, out",
    "cage",
    "@create match chronicle",
    "drop match chronicle",
    "@desc match chronicle = A brass automaton hunched over a ledger, pen scratching by itself. REPLAY reads the record back; the owner may WIPE LEDGER.",
    "@set match chronicle/scribe = rows = (get_attr(me, 'log') or []) + [[now(), str(arg0)]]; set_attr(me, 'log', rows[-30:])",
    "@set match chronicle/tally = result = ' / '.join([name(o) + ' ' + str(get_attr(o, 'hp', 0)) + ':' + str(get_attr(o, 'max_hp', 0)) for o in contents(loc(me)) if has_tag(o, 'in_combat')])",
    "@set match chronicle/on_attack = eval_attr(me, 'scribe', name(enactor) + ' presses the attack. [' + eval_attr(me, 'tally') + ']')",
    "@set match chronicle/on_damage = eval_attr(me, 'scribe', name(enactor) + ' lands a telling blow. [' + eval_attr(me, 'tally') + ']')",
    "@set match chronicle/on_death = eval_attr(me, 'scribe', 'FINISH -- ' + name(enactor) + ' ends it.')",
    "@set match chronicle/listen_words = ^*: eval_attr(me, 'scribe', name(enactor) + ' shouts: ' + escape(arg0)) if enactor else None",
    "@set match chronicle/cmd_replay = $replay: rows = get_attr(me, 'log') or []; (pemit(enactor, 'The ledger is blank.') if not rows else [pemit(enactor, '[' + str(now() - r[0]) + 's ago] ' + r[1]) for r in rows])",
    "@set match chronicle/cmd_wipe = $wipe ledger: (del_attr(me, 'log'), pemit(enactor, 'You tear out the used pages. The automaton dips its pen.')) if enactor == owner(me) else pemit(enactor, 'The automaton clutches its ledger jealously.')",
]

BUILD_RED_FLAGS = (
    "Unknown command", "Usage:", "not found", "Script error",
    "can't", "don't", "No permission",
)


# --- Harness -------------------------------------------------------------------


@pytest.fixture
def sim():
    simulator = Simulator()
    set_check_resolver(level_resolver)
    # GameServer wires the session manager at startup; the Simulator
    # leaves it to the test (needed by prompt()).
    simulator.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(simulator._sessions.values()))
    yield simulator
    set_check_resolver(None)
    simulator.close()


@pytest.fixture
def combat():
    """A live CombatManager on a diceless ruleset; beats fired by hand."""
    from realm.combat.combatant import clear_combatant_cache
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
    """Drive raw command lines through the dispatcher, keeping the
    deterministic resolver pinned (a build's @reload re-installs the
    GURPS dice resolver)."""
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


def objs(sim, name):
    return sim.store.find_cached(name=name)


def text(sim, player):
    return "\n".join(sim.seen(player))


def fighter(sim, name, where, **over):
    """A player with a workable GURPS sheet against the diceless ruleset."""
    attrs = dict(hp=30, max_hp=30, skill_melee=16, dodge=0,
                 strength=10, dexterity=10)
    attrs.update(over)
    return sim.player(name, location=where, **attrs)


async def rounds(manager, someone, n=1):
    """Fire n combat beats on someone's encounter."""
    encounter = manager.encounter_of(someone)
    assert encounter is not None, f"{someone.name} is not in a fight"
    for _ in range(n):
        await encounter.resolve_round()


# --- 109. Cover system -----------------------------------------------------------


class TestCoverSystem:

    async def test_native_cover_spoils_ranged_fire(self, sim, combat):
        builder = await build(sim, BUILD_109)
        killhouse = room(sim, "The Killhouse")
        assert builder.location is killhouse
        # skill_ranged 11: hits at full skill (roll 10), misses at -2 cover.
        ace = fighter(sim, "Ace", killhouse, skill_ranged=11)
        bruce = fighter(sim, "Bruce", killhouse, hp=20, max_hp=20)

        await sim.do(ace, "get laser carbine")
        await sim.do(ace, "wield laser carbine")
        assert "You ready laser carbine." in text(sim, ace)

        await sim.do(ace, "attack Bruce")
        await sim.do(ace, "queue withdraw")
        await rounds(combat, ace)                      # Ace opens the range
        assert "You fall back out of reach." in text(sim, ace)

        await sim.do(ace, "queue shoot Bruce")
        await rounds(combat, ace)                      # clean shot: hits
        assert int(bruce.db.get("hp")) == 17

        await sim.do(bruce, "queue cover")
        await sim.do(ace, "queue wait")
        await rounds(combat, ace)                      # Bruce digs in
        out = text(sim, bruce)
        assert "You duck behind the overturned dropship hull." in out
        assert "takes cover behind the overturned dropship hull" in text(sim, ace)

        await sim.do(ace, "queue shoot Bruce")
        await rounds(combat, ace)                      # -2 vs cover: a miss
        assert int(bruce.db.get("hp")) == 17

    async def test_destructible_cover_denies_the_next_taker(self, sim, combat):
        builder = await build(sim, BUILD_109)
        killhouse = room(sim, "The Killhouse")
        ace = fighter(sim, "Ace", killhouse, skill_ranged=11)
        bruce = fighter(sim, "Bruce", killhouse, hp=20, max_hp=20)
        hull = obj(sim, "overturned dropship hull")

        await sim.do(builder, "shred hull")
        assert "tears chunks off the hull" in text(sim, builder)
        assert hull.has_tag("cover")
        await sim.do(builder, "shred hull")
        assert "cover for no one now!" in text(sim, builder)
        assert not hull.has_tag("cover")
        await sim.do(builder, "shred hull")
        assert "The hull is already scrap." in text(sim, builder)

        # With the tag gone, the engine refuses the maneuver.
        await sim.do(ace, "attack Bruce")
        await sim.do(bruce, "queue cover")
        await sim.do(ace, "queue wait")
        await rounds(combat, ace)
        assert "There's nothing here to take cover behind." in text(sim, bruce)


# --- 111. Grenades -----------------------------------------------------------------


class TestGrenades:

    async def test_pin_throw_fuse_and_blast(self, sim, combat):
        builder = await build(sim, BUILD_111)
        bunker = room(sim, "The Bunker")
        trench = room(sim, "The Trench")
        assert builder.location is bunker
        # Thrower: dexterity 14 -> throwing 12 (passes). In the trench:
        # Brick dives clear (reflexes 13), Mook eats shrapnel, the thug dies.
        zeke = sim.player("Zeke", location=bunker, dexterity=14,
                          hp=30, max_hp=30)
        brick = sim.player("Brick", location=trench, dexterity=14,
                           hp=30, max_hp=30)
        mook = sim.player("Mook", location=trench, dexterity=8,
                          hp=30, max_hp=30)
        thug = sim.obj("trench thug", location=trench, tags=["npc"],
                       hp=1, max_hp=1, dexterity=8)

        await sim.do(zeke, "pull pin")
        assert "Pick it up first" in text(sim, zeke)

        await sim.do(zeke, "get frag grenade")
        await run_lines(sim, builder, ["@set frag grenade/fuse = 0"])
        await sim.do(zeke, "pull pin")
        assert "pulls the pin. The spoon pings away." in text(sim, builder)
        await sim.do(zeke, "pull pin")
        assert "The pin is already out!" in text(sim, zeke)

        await sim.do(zeke, "throw grenade trench")
        assert "hurls the grenade through the trench exit!" in text(sim, builder)
        assert obj(sim, "frag grenade").location is trench
        assert "A grenade bounces in" in text(sim, brick)

        sim.seen(mook)
        await sim.engine.tick_waits()                  # the fuse runs out
        brick_out = text(sim, brick)
        assert "WHUMP." in brick_out
        assert "You dive clear of the blast!" in brick_out
        assert int(brick.db.get("hp")) == 30
        assert "Shrapnel tears into you!" in text(sim, mook)
        assert int(mook.db.get("hp")) < 30
        # The thug went to zero: the shared death path made a corpse.
        assert [o for o in trench.contents if o.name.startswith("corpse of")]
        assert objs(sim, "frag grenade") == []         # the casing is spent

    async def test_held_too_long_drops_and_detonates_at_your_feet(self, sim, combat):
        builder = await build(sim, BUILD_111)
        bunker = room(sim, "The Bunker")
        zeke = sim.player("Zeke", location=bunker, dexterity=8,
                          hp=30, max_hp=30)

        await sim.do(zeke, "get frag grenade")
        await run_lines(sim, builder, ["@set frag grenade/fuse = 0"])
        await sim.do(zeke, "pull pin")

        await sim.engine.tick_waits()                  # boom: still in hand
        assert "slips through Zeke's fingers!" in text(sim, builder)
        assert obj(sim, "frag grenade").location is bunker
        await sim.engine.tick_waits()                  # the chained blast
        assert "WHUMP." in text(sim, zeke)
        assert int(zeke.db.get("hp")) < 30             # reflexes 7: no save
        assert objs(sim, "frag grenade") == []

    async def test_bad_throw_scatters_through_another_exit(self, sim, combat):
        builder = await build(sim, BUILD_111)
        bunker = room(sim, "The Bunker")
        limbo = room(sim, "Limbo")
        mook = sim.player("Mook", location=bunker, dexterity=8,
                          hp=30, max_hp=30)

        await sim.do(mook, "throw grenade trench")
        assert "You are not holding the grenade." in text(sim, mook)

        await sim.do(mook, "get frag grenade")
        await sim.do(mook, "throw grenade nowhere")
        assert "No open exit called nowhere here." in text(sim, mook)

        # throwing 6: the throw goes wide -- the only other open exit
        # is 'out', so it skips into Limbo. Unarmed, so no boom follows.
        await sim.do(mook, "throw grenade trench")
        assert "It caroms off the frame" in text(sim, builder)
        assert obj(sim, "frag grenade").location is limbo
        await sim.engine.tick_waits()
        assert objs(sim, "frag grenade")               # inert, intact


# --- 112. Non-lethal takedowns ------------------------------------------------------


class TestNonlethalTakedowns:

    async def test_sap_bind_wake_and_release(self, sim, combat):
        builder = await build(sim, BUILD_112)
        brig = room(sim, "The Brig")
        mara = fighter(sim, "Mara", brig, skill_melee=14)
        zeke = sim.player("Zeke", location=brig, health=8,
                          hp=13, max_hp=13)
        brick = sim.player("Brick", location=brig, health=14,
                           hp=13, max_hp=13)

        # Melee 14 vs Fortitude 14: the tie goes to the target.
        await sim.do(mara, "sap Brick")
        assert "twists away from Mara's cosh!" in text(sim, mara)
        assert not brick.has_tag("unconscious")

        # Melee 14 vs Fortitude 8: down he goes -- no HP touched.
        await sim.do(mara, "sap Zeke")
        assert "fold up like wet paper" in text(sim, mara)
        assert "A starburst of white -- then nothing." in text(sim, zeke)
        assert zeke.has_tag("unconscious")
        assert int(zeke.db.get("hp")) == 13

        # Captives are out of the combat system entirely.
        await sim.do(mara, "attack Zeke")
        assert "not something you can fight" in text(sim, mara)

        await sim.do(mara, "bind Brick")
        assert "They are wide awake -- put them down first." in text(sim, mara)
        await sim.do(mara, "bind Zeke")
        assert "snaps iron binders around Zeke's wrists." in text(sim, mara)
        assert zeke.has_tag("restrained")

        # The knockout expires on its own beats; the restraint does not.
        for _ in range(8):
            await deliver_beat(zeke)
        assert not zeke.has_tag("unconscious")
        assert "skull full of gravel" in text(sim, zeke)
        assert zeke.has_tag("restrained")

        await sim.do(zeke, "out")
        assert "The binders hold -- you are going nowhere." in text(sim, zeke)
        assert zeke.location is brig

        await sim.do(mara, "release Zeke")
        assert not zeke.has_tag("restrained")
        await sim.do(zeke, "out")
        assert zeke.location is room(sim, "Limbo")

    async def test_death_path_contrast_corpse_vs_unconscious(self, sim, combat):
        builder = await build(sim, BUILD_112)
        brig = room(sim, "The Brig")
        mara = fighter(sim, "Mara", brig, skill_melee=14, dodge=12)
        thug = sim.obj("brig thug", location=brig, tags=["npc"],
                       hp=3, max_hp=3, dodge=0)
        loot = sim.obj("shiv", location=thug, tags=["thing"])

        # NPCs at zero HP DIE -- no captive, a lootable corpse.
        await sim.do(mara, "attack brig thug")
        await rounds(combat, mara)
        corpses = [o for o in brig.contents if o.name.startswith("corpse of")]
        assert len(corpses) == 1 and loot.location is corpses[0]

        # Players at zero HP fall unconscious in place, and firstaid revives.
        bruiser = sim.obj("bruiser", location=brig, tags=["npc"],
                          hp=30, max_hp=30, skill_melee=16, dodge=12)
        dana = fighter(sim, "Dana", brig, hp=3, skill_melee=4)
        await sim.do(dana, "attack bruiser")
        await rounds(combat, dana)
        assert dana.has_tag("unconscious")
        assert dana.location is brig
        assert "Everything goes black..." in text(sim, dana)

        medic = fighter(sim, "Medic", brig, skill_first_aid=14)
        await sim.do(medic, "firstaid Dana")
        assert not dana.has_tag("unconscious")
        assert int(dana.db.get("hp")) > 0


# --- 113. Dueling system -------------------------------------------------------------


class TestDueling:

    async def test_ward_blocks_unsanctioned_swings(self, sim, combat):
        builder = await build(sim, BUILD_113, admin=True)
        ring = room(sim, "The Ring")
        ace = fighter(sim, "Ace", ring, credits=100)
        bruce = fighter(sim, "Bruce", ring, credits=100)

        await sim.do(ace, "attack Bruce")
        await rounds(combat, ace)
        assert "The Ring hosts sanctioned duels only" in text(sim, ace)
        assert int(bruce.db.get("hp")) == 30           # nothing landed

    async def test_declined_challenge_moves_no_money(self, sim, combat):
        builder = await build(sim, BUILD_113, admin=True)
        ring = room(sim, "The Ring")
        ace = fighter(sim, "Ace", ring, credits=100)
        bruce = fighter(sim, "Bruce", ring, credits=100)
        stone = obj(sim, "dueling stone")

        await sim.do(ace, "duel Bruce")
        assert "challenges you to a duel for 25 credits" in text(sim, bruce)
        handler = sim.session(bruce).input_handler
        assert handler is not None, "prompt() should capture the next line"
        await handler(sim.session(bruce), "no")
        assert "declines the duel" in text(sim, ace)
        assert stone.db.get("challenger") is None
        assert int(ace.db.get("credits")) == 100
        assert int(bruce.db.get("credits")) == 100
        assert not ace.has_tag("duelist")

    async def test_full_duel_escrow_fight_and_payout(self, sim, combat):
        builder = await build(sim, BUILD_113, admin=True)
        ring = room(sim, "The Ring")
        # Ace defends everything (dodge 12); Bruce is two hits from down.
        ace = fighter(sim, "Ace", ring, credits=100, dodge=12)
        bruce = fighter(sim, "Bruce", ring, credits=100, hp=6, max_hp=6)
        stone = obj(sim, "dueling stone")

        await sim.do(ace, "duel Bruce")
        handler = sim.session(bruce).input_handler
        await handler(sim.session(bruce), "accept")
        assert "The stakes -- 50 credits -- rattle into the stone. FIGHT!" \
            in text(sim, ace)
        assert int(stone.db.get("credits") or 0) == 50   # escrow on the stone
        assert int(ace.db.get("credits")) == 75
        assert int(bruce.db.get("credits")) == 75
        assert ace.has_tag("duelist") and bruce.has_tag("duelist")
        assert combat.encounter_of(ace) is not None

        await rounds(combat, ace, 2)                   # 6 -> 3 -> down
        assert bruce.has_tag("unconscious")            # players never die
        assert "stands over a fallen rival. The stone pays out 50 credits." \
            in text(sim, ace)
        assert int(ace.db.get("credits")) == 125
        assert int(bruce.db.get("credits")) == 75
        assert not ace.has_tag("duelist") and not bruce.has_tag("duelist")
        assert stone.db.get("challenger") is None


# --- 114. Bounty board ----------------------------------------------------------------


class TestBountyBoard:

    async def test_post_stake_announce_and_verified_claim(self, sim, combat):
        builder = await build(sim, BUILD_114)
        office = room(sim, "The Bounty Office")
        gulch = room(sim, "Rattler Gulch")
        board = obj(sim, "bounty board")
        assert builder.location is office
        hunter = fighter(sim, "Ryn", gulch, dodge=12, credits=0)

        await run_lines(sim, builder, ["@set me/credits = 200"])
        await sim.do(builder, "post Dreg Farrow")
        assert "Contract drafted on Dreg Farrow." in text(sim, builder)

        await sim.do(builder, "pay 60 to bounty board")
        assert int(builder.db.get("credits")) == 140
        assert int(board.db.get("credits")) == 60      # escrow on the board
        assert board.db.get("ledger") == [["Dreg Farrow", 60]]
        # The crier is zone-wide: the hunter hears it a room away.
        assert "60 credits on the head of Dreg Farrow!" in text(sim, hunter)

        await sim.do(builder, "bounties")
        assert "[WANTED] Dreg Farrow -- 60 credits." in text(sim, builder)

        await sim.do(hunter, "attack Dreg Farrow")
        await rounds(combat, hunter, 2)                # 6 -> 3 -> dead
        assert int(hunter.db.get("credits")) == 60
        assert int(board.db.get("credits")) == 0
        assert board.db.get("ledger") == []
        assert "BOUNTY CLAIMED: Ryn collects 60 credits for Dreg Farrow." \
            in text(sim, builder)
        assert [o for o in gulch.contents if o.name.startswith("corpse of")]

        sim.seen(builder)
        await sim.do(builder, "bounties")
        assert "The board is bare." in text(sim, builder)

    async def test_paying_without_a_draft_is_refused(self, sim, combat):
        builder = await build(sim, BUILD_114)
        await run_lines(sim, builder, ["@set me/credits = 50"])
        await sim.do(builder, "pay 10 to bounty board")
        assert "Draft a contract first: POST <name>." in text(sim, builder)
        assert not obj(sim, "bounty board").db.get("ledger")


# --- 115. Arena with spectators --------------------------------------------------------


class TestArenaSpectators:

    async def test_stands_get_the_blow_by_blow_and_only_that(self, sim, combat):
        builder = await build(sim, BUILD_115)
        pit = room(sim, "The Fight Pit")
        stands = room(sim, "The Stands")
        ace = fighter(sim, "Ace", pit, dodge=12)
        bruce = fighter(sim, "Bruce", pit, hp=6, max_hp=20)
        sal = sim.player("Sal", location=stands)

        await sim.do(ace, "attack Bruce")
        await rounds(combat, ace)
        feed = text(sim, sal)
        assert "[pit] Ace wades in!" in feed
        assert "Bruce 6/20" in feed                    # the open-read tally
        assert "[pit] Ace draws blood!" in feed

        await sim.do(bruce, "say is that ALL")
        assert "[pit] Bruce bellows: is that ALL" in text(sim, sal)

        await rounds(combat, ace)
        feed = text(sim, sal)
        assert "Bruce 3/20" in feed                    # last round's toll
        assert "THE CROWD ROARS -- Ace takes the pit!" in feed

        # Ringside vs pit: fighters never see the relay tag...
        assert "[pit]" not in text(sim, ace)
        # ...and the stands never saw the pit's native narration.
        assert "squares off" not in feed


# --- 117. Armor degradation -------------------------------------------------------------


class TestArmorDegradation:

    async def test_soak_wear_out_shred_and_repair(self, sim, combat):
        builder = await build(sim, BUILD_117, admin=True)
        outfitter = room(sim, "The Outfitter")
        vest = obj(sim, "flak vest")
        # Nia swings at air (skill 4) but flees well (dexterity 14).
        nia = fighter(sim, "Nia", outfitter, hp=20, max_hp=20,
                      skill_melee=4, dexterity=14, skill_armoury=12)
        thug = sim.obj("pit thug", location=outfitter, tags=["npc"],
                       hp=30, max_hp=30, skill_melee=16, dodge=0)

        await sim.do(nia, "get flak vest")
        await sim.do(nia, "wear flak vest")
        assert "You cinch the flak vest tight. (DR 3, 3 plates)" in text(sim, nia)
        assert int(nia.db.get("damage_resistance")) == 3
        assert int(nia.db.get("armor_condition")) == 3
        assert nia.db.get("on_damage")                 # the ledger hook

        await sim.do(nia, "attack pit thug")
        await rounds(combat, nia)                      # hit 1: fully soaked
        assert "Your vest soaks the worst of it. (2 plates left)" in text(sim, nia)
        assert int(nia.db.get("hp")) == 20
        await rounds(combat, nia)                      # hit 2: fully soaked
        assert int(nia.db.get("hp")) == 20
        assert int(nia.db.get("armor_condition")) == 1
        await rounds(combat, nia)                      # hit 3: the vest breaks
        assert "comes apart at the seams" in text(sim, nia)
        assert int(nia.db.get("damage_resistance")) == 0
        assert int(nia.db.get("hp")) == 17             # the breaking hit lands

        await sim.do(nia, "flee out")
        await rounds(combat, nia)                      # dexterity 14: escapes
        assert nia.location is room(sim, "Limbo")
        await sim.do(nia, "outfitter")

        await sim.do(nia, "remove flak vest")
        assert "You shrug out of the vest." in text(sim, nia)
        assert int(vest.db.get("condition")) == 0      # wear synced back
        assert nia.db.get("armor_condition") is None
        assert nia.db.get("on_damage") is None

        await sim.do(nia, "wear flak vest")
        assert "The vest is shredded" in text(sim, nia)
        assert not nia.db.get("damage_resistance")

        await sim.do(nia, "remove flak vest")
        await sim.do(nia, "drop flak vest")
        await sim.do(nia, "repair vest")
        assert "hammers the plating flat" in text(sim, nia)
        assert int(vest.db.get("condition")) == 3

        await sim.do(nia, "get flak vest")
        await sim.do(nia, "wear flak vest")
        assert "(DR 3, 3 plates)" in text(sim, nia)
        assert int(nia.db.get("damage_resistance")) == 3

    async def test_repair_needs_the_vest_on_the_bench(self, sim, combat):
        builder = await build(sim, BUILD_117, admin=True)
        nia = fighter(sim, "Nia", room(sim, "The Outfitter"), skill_armoury=12)
        await sim.do(nia, "get flak vest")
        await sim.do(nia, "repair vest")
        assert "Lay the vest on the bench first" in text(sim, nia)


# --- 118. Bleeding & first aid -------------------------------------------------------------


class TestBleedingFirstAid:

    async def test_wounds_bleed_on_the_beat_and_bandage_stops_them(self, sim, combat):
        builder = await build(sim, BUILD_118)
        yard = room(sim, "The Red Yard")
        ace = fighter(sim, "Ace", yard, dodge=12)
        bruce = fighter(sim, "Bruce", yard, hp=20, max_hp=20)
        ferd = fighter(sim, "Ferd", yard, skill_first_aid=6)
        mara = fighter(sim, "Mara", yard, skill_first_aid=14)

        await sim.do(ace, "attack Bruce")
        await rounds(combat, ace)                      # round 1: first wound
        assert int(bruce.db.get("hp")) == 17
        assert not bruce.has_tag("bleeding")           # hooks saw him unhurt

        await rounds(combat, ace)                      # round 2: now he bleeds
        assert bruce.has_tag("bleeding")
        assert int(bruce.db.get("hp")) == 14

        await rounds(combat, ace)                      # round 3: beat + swing
        assert int(bruce.db.get("hp")) == 10           # -1 bleed, -3 hit
        assert "Your wound runs red" in text(sim, bruce)

        # Ringside medics work mid-fight -- $bandage is a room command.
        await sim.do(ferd, "bandage Bruce")
        assert "The dressing soaks through." in text(sim, ferd)
        assert bruce.has_tag("bleeding")

        await sim.do(mara, "bandage Bruce")
        assert "ties off Bruce's wound. The bleeding stops." in text(sim, mara)
        assert not bruce.has_tag("bleeding")
        assert int(bruce.db.get("hp")) == 11           # the dressing's +1

        await rounds(combat, ace)                      # round 4: no bleed tick
        assert int(bruce.db.get("hp")) == 8            # only the swing
        # ...but the new wound sets him bleeding again -- battlefield rules.
        assert bruce.has_tag("bleeding")

        # The attacker was never wounded, so he never bled.
        assert not ace.has_tag("bleeding")

    async def test_bandage_refuses_the_unwounded(self, sim, combat):
        builder = await build(sim, BUILD_118)
        yard = room(sim, "The Red Yard")
        mara = fighter(sim, "Mara", yard, skill_first_aid=14)
        brick = fighter(sim, "Brick", yard)
        await sim.do(mara, "bandage Brick")
        assert "They are not bleeding." in text(sim, mara)
        await sim.do(mara, "bandage Nobody")
        assert "No patient by that name here." in text(sim, mara)


# --- 119. NPC morale ---------------------------------------------------------------------


class TestNPCMorale:

    async def test_broken_nerve_surrenders_and_warms_to_the_victor(self, sim, combat):
        from realm.core.disposition import get_disposition

        builder = await build(sim, BUILD_119)
        lair = room(sim, "Raider Lair")
        limbo = room(sim, "Limbo")
        vex = obj(sim, "Vex")
        hunter = fighter(sim, "Hunter", limbo, dodge=12)

        await sim.do(hunter, "lair")                   # aggressive engages
        assert '"Your boots -- I want them."' in text(sim, hunter)
        assert combat.encounter_of(vex) is not None

        await sim.do(hunter, "attack Vex")
        await rounds(combat, hunter)                   # 12 -> 9 (75%)
        assert not vex.has_tag("surrendered")
        await rounds(combat, hunter)                   # 9 -> 6: crosses 50%
        assert "I yield! I yield" in text(sim, hunter)
        assert vex.has_tag("surrendered")
        assert "aggressive" not in [b.behavior_id for b in vex.get_behaviors()]
        assert vex.db.get("combat_strategy") == [["", "wait"]]
        assert get_disposition(vex, hunter) == 5

        # Hands up means hands up: she waits the next beat out.
        await sim.do(hunter, "queue wait")
        await rounds(combat, hunter)
        assert int(vex.db.get("hp")) == 6
        assert int(hunter.db.get("hp")) == 30

    async def test_steady_nerve_flees_on_the_next_beat(self, sim, combat):
        builder = await build(sim, BUILD_119)
        lair = room(sim, "Raider Lair")
        limbo = room(sim, "Limbo")
        vex = obj(sim, "Vex")
        await run_lines(sim, builder, ["@set Vex/health = 13"])
        hunter = fighter(sim, "Hunter", limbo, dodge=12)

        await sim.do(hunter, "lair")
        await sim.do(hunter, "attack Vex")
        await rounds(combat, hunter, 2)                # crosses 50%: nerve holds
        assert "Not like this!" in text(sim, hunter)
        assert "fleeing" in [b.behavior_id for b in vex.get_behaviors()]

        await rounds(combat, hunter)                   # the override rule fires
        assert vex.location is limbo                   # out the only exit
        assert not vex.has_tag("in_combat")
        assert not vex.has_tag("surrendered")


# --- 120. Combat replay log -----------------------------------------------------------------


class TestCombatReplay:

    async def test_scribe_records_and_replay_reads_back_in_order(self, sim, combat):
        builder = await build(sim, BUILD_120)
        cage = room(sim, "The Fight Cage")
        chronicle = obj(sim, "match chronicle")
        ace = fighter(sim, "Ace", cage, dodge=12)
        bruce = fighter(sim, "Bruce", cage, hp=6, max_hp=20)

        await sim.do(ace, "attack Bruce")
        await rounds(combat, ace)                      # 6 -> 3
        await sim.do(bruce, "say remember this")
        await rounds(combat, ace)                      # 3 -> down: FINISH

        rows = chronicle.db.get("log")
        assert rows and len(rows) <= 30
        joined = "\n".join(r[1] for r in rows)
        assert "Ace presses the attack. [" in joined
        assert "Bruce 6:20" in joined                  # the pre-blow tally
        assert "Ace lands a telling blow." in joined
        assert "Bruce shouts: remember this" in joined
        assert "FINISH -- Ace ends it." in joined
        assert joined.index("Bruce 6:20") < joined.index("remember this") \
            < joined.index("FINISH")

        await sim.do(ace, "replay")
        out = text(sim, ace)
        assert "s ago] Ace presses the attack." in out
        assert "s ago] FINISH -- Ace ends it." in out

    async def test_wipe_is_owner_only(self, sim, combat):
        builder = await build(sim, BUILD_120)
        cage = room(sim, "The Fight Cage")
        chronicle = obj(sim, "match chronicle")
        ace = fighter(sim, "Ace", cage, dodge=12)
        bruce = fighter(sim, "Bruce", cage, hp=6, max_hp=20)
        await sim.do(ace, "attack Bruce")
        await rounds(combat, ace)
        assert chronicle.db.get("log")

        await sim.do(ace, "wipe ledger")
        assert "clutches its ledger jealously" in text(sim, ace)
        assert chronicle.db.get("log")

        await sim.do(builder, "wipe ledger")
        assert "You tear out the used pages." in text(sim, builder)
        assert not chronicle.db.get("log")
        await sim.do(builder, "replay")
        assert "The ledger is blank." in text(sim, builder)
