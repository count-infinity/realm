# Showcase & Tutorial Checklist

A master list of **250 orthogonal, tutorial-sized builds** demonstrating what
a MU* creator can do with REALM — **live, in-game, in softcode**. Each item
is meant to become a short step-by-step how-to built at a live prompt:
`@dig`/`@create`/`@set` an example into the world, explain the softcode
concepts it exercises, done. No Python modules, no restarts (except where an
item is explicitly gap-gated).

Inspiration drawn from the classic softcode archives at
[MUSHCode.com](https://mushcode.com/) and the
[lisdude MOO archive](https://lisdude.com/moo/#code), reimagined as REALM
trigger/behavior/ward patterns.

**Format:** `- [ ] N. **Name** [class] — what it is/does. *(REALM concepts it teaches)*`

Classes come from the [capability audit](capability_audit.md):
**[now]** buildable in softcode today · **[small]** blocked on a modest
engine addition (gap named in the audit) · **[major]** blocked on a missing
subsystem. Check items off as their tutorial + working in-game example lands.

**Progress: 75/250**

---

## 1. Interactive Objects & Gadgets (1–13)

- [x] 1. **Slot machine** [now] — pull a lever, weighted random payout table, house edge. *($-commands, rand()/switch() tables, transfer_credits, ON_PAYMENT)*
- [x] 2. **Vending machine** [now] — insert coins, dispense items spawned from prototypes. *(ON_PAYMENT, create_obj from prototype attrs, spawner vocabulary)*
- [x] 3. **Jukebox** [now] — pick a track from a menu, timed room-wide ambient lyrics. *(prompt() menus, wait() chains, remit, script_ticker)*
- [x] 4. **ATM / bank terminal** [now] — deposit, withdraw, check balance from any terminal. *(shared state on one bank object, eval_attr, attrs vs object identity)*
- [x] 5. **Magic 8-ball / oracle** [now] — shake it for a random cryptic answer. *(the hello-world $-command: one trigger, one switch(rand()))*
- [x] 6. **Flashlight** [now] — toggleable light source with battery drain that defeats dark rooms. *(light/dark tags, add_tag/remove_tag, on_tick drain)*
- [x] 7. **Voice recorder** [now] — records what is said in the room, plays it back later. *(^listen triggers, transcript attrs, $play)*
- [x] 8. **Camera** [now] — snapshot a room's description and occupants onto a photo item. *(create_obj, capturing world state via contents()/name())*
- [x] 9. **Music box / wind-up toy** [now] — wind it up, emotes on a timer until it runs down. *(wait() chains, decaying counter attrs)*
- [x] 10. **Typewriter & paper** [now] — write, read, and sign multi-page documents in-game. *(prompt() wizards, per-page attrs, the attribute editor)*
- [x] 11. **Mirror** [now] — look at it to see your own description and worn items. *(ON_LOOK, pemit to enactor, reading open attrs)*
- [x] 12. **Gift box** [now] — wrap any item; recipient unwraps to reveal it with fanfare. *(containers, set_lock per recipient, ON_OPEN)*
- [x] 13. **Fortune teller booth** [now] — coin-operated Zoltar dispensing printed fortune cards. *(composing ON_PAYMENT + spawned collectible items)*

## 2. Containers, Storage & Item Handling (14–24)

- [x] 14. **Basic container** [now] — a sack with weight/volume capacity limits. *(db.container, on_check wards, block(), weight-attr conventions)*
- [x] 15. **Locked chest & key** [now] — openable container guarded by a matching key item. *(@lock, lock/unlock/pick commands, key items, gated ON_UNLOCK)*
- [x] 16. **Combination safe** [now] — dial a numeric code to open; code settable by owner. *(prompt() input, secret attr flag)*
- [x] 17. **Bag of holding** [now] — container whose contents weigh nothing to the carrier. *(overriding a softcode weight convention cleanly)*
- [x] 18. **Refrigerator** [now] — food inside decays slower than food outside. *(decay behavior, ON_PUT/ON_GET adjusting decay ticks)*
- [x] 19. **Trash bin / incinerator** [now] — safe item disposal with a grace period before purge. *(ON_RECEIVE, expire()/ON_EXPIRE, soft-delete pattern)*
- [x] 20. **Bookshelf** [now] — browsable shelf listing readable books by title. *($browse, contents() loops, tag filtering)*
- [x] 21. **Ammo pouch** [now] — typed container that only accepts tagged ammunition. *(tag-filtered on_check ward)*
- [x] 22. **Coat check** [now] — leave an item, get a numbered claim ticket, redeem later. *(ticket pattern, paired-object bookkeeping attrs)*
- [x] 23. **Conveyor belt** [now] — items placed on it move to the next room every tick. *(script_ticker, move_to, room chaining)*
- [x] 24. **Loot crate** [now] — container populated from a weighted random loot table on first open. *(ON_OPEN one-shot flags, weighted rand tables, lazy spawning)*

## 3. Doors, Exits & Access Control (25–35)

- [x] 25. **Lockable door** [now] — a two-sided exit pair that locks/unlocks with a key. *(paired exits, shared door-state attrs, traverse locks)*
- [x] 26. **Keycard door** [now] — access by clearance level on the card, not the person. *(on_check wards reading carried items' attrs)*
- [x] 27. **Secret door** [now] — hidden exit revealed by searching or a Perception roll. *(concealed exits, search + skill_check, perception engine)*
- [x] 28. **One-way exit** [now] — chute or drop you cannot climb back up. *(single exits, ON_LEAVE/ON_ARRIVE message overrides)*
- [x] 29. **Timed door** [now] — opens on a switch and slams shut after 30 seconds. *(wait()/cancel_wait, state reversion, atomicity)*
- [x] 30. **Toll gate** [now] — pay a fee to traverse; owner collects the till. *(on_check credit gate, transfer_credits, ON_PAYMENT)*
- [x] 31. **Guarded exit** [now] — NPC blocks passage unless you're on the guest list or persuade it. *(guard behavior, disposition, persuade/fasttalk, wards)*
- [x] 32. **Airlock** [now] — two doors that can never be open at once, with a cycle sequence. *(interlocked on_check wards across objects, $cycle wait sequence)*
- [x] 33. **Portal pair** [now] — linked wormholes; step in one, exit the other, in either direction. *(programmatic exit creation: create_obj + exit tag + db.destination)*
- [x] 34. **Climbing exit** [now] — a cliff traverse requiring a Climbing roll, with fall damage on failure. *(skill-gated wards, damage(), ON_FAIL)*
- [x] 35. **Size-restricted crawlspace** [now] — only unencumbered or small characters fit through. *(stat-reading wards, helpful block() text)*

## 4. Rooms & Environment (36–47)

- [x] 36. **Weather system** [now] — zone-wide weather that drifts between states and broadcasts flavor. *(zone masters, on_tick, remit to zone_rooms())*
- [x] 37. **Day/night cycle** [now] — room descriptions and contents visibility swap with game time. *(softcode clock from now(), [[...]] time-branching descs)*
- [x] 38. **Dark room** [now] — pitch-black room requiring a light source to see or read. *(dark/light/nightvision tags — the perception engine)*
- [x] 39. **Underwater room** [now] — breath countdown, drowning damage, swimming checks. *(per-occupant on_tick meters, skill_check, damage())*
- [x] 40. **Zero-G compartment** [now] — movement verbs and emotes rewritten for freefall. *(movement wards by action tag, custom $-verbs, themed remit)*
- [x] 41. **Ambient room messages** [now] — occasional random flavor echoes tuned per room. *(script_ticker + rand gates, spam discipline)*
- [x] 42. **Room details** [now] — virtual look-targets (mural, control panel) without real objects. *(@detail, desc_extras, per-viewer conditions)*
- [x] 43. **Hazard room** [now] — radiation/heat zones dealing periodic damage with HT resistance. *(on_tick damage, skill_check('health'), zone_property severity)*
- [x] 44. **Instanced room** [now] — a per-player copy spun up on entry (private hotel room). *(enter_instance(), ephemeral areas, idle reaping)*
- [x] 45. **Procedural wilderness** [now] — coordinate-based grid rooms generated on demand. *(wilderness regions, map-provider attrs, cell reaping)*
- [x] 46. **Room capacity** [now] — small spaces that get crowded and block further entry. *(ENTER wards counting occupants)*
- [x] 47. **Falling between rooms** [now] — failing a check on a ledge drops you to the room below. *(skill gates, teleport_obj, forced movement)*

## 5. Traps, Hazards & Devices (48–59)

- [x] 48. **Gas bomb** [now] — armed with a fuse, fills the room with gas that spreads to adjacent rooms and forces HT rolls. *(wait() fuses, exits() graph spreading, resisted effects, expire())*
- [x] 49. **Landmine** [now] — buried item that triggers on room entry with a Per chance to spot. *(ON_ENTER triggers, contest() detection, concealment tags)*
- [x] 50. **Tripwire alarm** [now] — silent alert sent to the owner when someone crosses a room. *(ON_ENTER, pemit(owner(me)), remote notification)*
- [x] 51. **Pit trap** [now] — concealed trapdoor dumping victims into a cell below. *(trap state attrs, teleport_obj, escape contests)*
- [x] 52. **Poison dart trap** [now] — triggered by touching the wrong object; poison effect over time. *(ON_GET/ON_USE traps, apply_effect damage_over_time)*
- [x] 53. **Snare** [now] — restrains a victim in place until they break free with ST contests. *(restraint tags, movement wards, $struggle contest loops)*
- [x] 54. **Security camera & monitor** [now] — watch a remote room's activity live from a console. *(bug objects: ^listen + ON_ENTER/ON_LEAVE relays via pemit)*
- [x] 55. **Motion sensor log** [now] — records who entered/left a room with timestamps. *(ON_ENTER/ON_LEAVE, now(), in-object log attrs)*
- [x] 56. **Self-destruct sequence** [now] — station-wide countdown with abort code and consequences. *(cancellable wait() chains, escalating remits, secret codes)*
- [x] 57. **EMP charge** [now] — temporarily disables electronic gadgets in the room. *(tag-targeted loops, temporary state with wait() restore)*
- [x] 58. **Spreading fire** [now] — fire that grows, spreads to adjacent rooms, and is fought with extinguishers. *(cellular on_tick simulation over exits(), counterplay items)*
- [x] 59. **Tranquilizer mechanics** [now] — knockout effects, unconsciousness state, and waking up. *(engine unconscious tag, command lockout, recovery waits)*

## 6. NPCs & AI Behaviors (60–73)

- [x] 60. **Wandering NPC** [now] — ambles randomly through a zone, respecting no-go tags. *(wandering behavior, zone confinement)*
- [ ] 61. **Patrolling guard** [now] — walks a fixed route, pauses, reacts to open doors. *(patrol behavior, waypoints, ON_OPEN reactions)*
- [ ] 62. **Aggressive mob** [now] — attacks on sight based on faction standing. *(aggressive behavior, dispositions, start_combat)*
- [x] 63. **Shopkeeper** [now] — buys and sells from a live inventory with restock. *(shopkeeper behavior, list/buy/sell/pay, spawner restock)*
- [x] 64. **Bartender** [now] — serves drinks and answers keyword questions about rumors. *(^listen keyword patterns, consumables, rumor attrs)*
- [ ] 65. **Pet** [now] — follows its owner between rooms and responds to simple orders. *(db.following, $-command whitelists, ownership)*
- [ ] 66. **Puppet** [now] — a second body a player can possess and speak/act through. *(control locks, @force, puppet output forwarding)*
- [x] 67. **Dialogue-tree NPC** [now] — branching conversation with memory of past choices. *(prompt() callback chains, per-player memory attrs)*
- [x] 68. **NPC daily schedule** [now] — opens shop at 9, goes home at night, sleeps. *(softcode clock, attach_behavior/detach_behavior by hour)*
- [ ] 69. **Trainer NPC** [now] — teaches skills for money with prerequisites and limits. *(CP economy, $train wrappers, admin-owned masters and authority)*
- [ ] 70. **Pickpocket NPC** [now] — attempts theft with contested rolls; can be caught. *(contest(), move_to, the controls() authority model)*
- [x] 71. **Guard response** [now] — crimes witnessed in town summon guards to the scene. *(zone-master ON_ATTACK witnesses, responder scripts)*
- [ ] 72. **NPC reaction emotes** [now] — NPC visibly reacts to says, emotes, and weapon-drawing. *(^listen + ON_WIELD triggers, now()-based cooldowns)*
- [ ] 73. **Boss with phases** [now] — scripted combat behavior that changes at HP thresholds. *(ON_HITPRCNT, combat strategies, behavior swapping)*

## 7. Communication Systems (74–85)

- [ ] 74. **Custom channel** [now] — create a channel with history, muting, and per-channel aliases. *(world-zone master $-commands, pemit fan-out, history attrs)*
- [ ] 75. **In-game mail** [now] — persistent mail with CC and item attachments. *(post-office object storage, escrow inventory, ON_CONNECT notices)*
- [ ] 76. **Bulletin boards** [now] — per-location or per-org boards with expiring posts. *(board objects, post attrs, on_tick expiry)*
- [ ] 77. **Handheld radios** [now] — tune to frequencies; anyone on the channel hears you. *(^listen relays, search_world by attr, device-gated comms)*
- [ ] 78. **Station PA system** [now] — broadcast announcements to every room in a zone. *(remit loops over zone_rooms())*
- [ ] 79. **Languages** [small] — speech is garbled for listeners lacking the language skill. *(gap G2: per-listener speech transform hook)*
- [ ] 80. **Overheard whispers** [small] — whispering with a Per-based chance of being overheard. *(gap G2: per-bystander leak roll in whisper delivery)*
- [ ] 81. **Graffiti** [now] — write on walls; text persists as a room detail others can read. *(room-owned $-commands, desc_extras, executor authority)*
- [ ] 82. **Newspaper** [now] — periodic issue compiled from player/NPC submissions, sold at kiosks. *(publication attrs, on_tick releases, ON_PAYMENT kiosks)*
- [ ] 83. **Message in a bottle** [now] — send a note that arrives to a random player much later. *(on_tick delayed delivery, rand recipients, serendipity)*
- [ ] 84. **Voice disguise** [small] — modulator that changes your speech attribution. *(gap G2: speaker-attribution override in the speech pipeline)*
- [ ] 85. **Rich emote parser** [small] — targeted emotes with name substitution seen correctly by each viewer. *(gap G3: per-viewer naming/sdesc layer)*

## 8. Economy & Commerce (86–97)

- [x] 86. **Multi-denomination currency** [now] — credits in coins/chits with automatic change-making. *(credits() as canonical value, coin items, $exchange math)*
- [x] 87. **Bank accounts** [now] — deposits, transfers between players, and interest ticks. *(ledger attrs, transfer_credits, on_tick interest, audit logs)*
- [ ] 88. **Player-run shop stalls** [now] — rentable stalls where players price their own goods. *(delegated vendor attrs, on_tick rent, escrow)*
- [x] 89. **Auction house** [now] — timed listings, bidding, sniping protection, payouts. *(auction state attrs, escrow inventory, on_tick settlement)*
- [ ] 90. **Pawn shop** [now] — sells anything back at a percentage with buyback window. *(db.value valuation, expire() buyback windows)*
- [ ] 91. **Lottery** [now] — buy numbered tickets; scheduled global drawing pays the pot. *(ticket items, on_tick drawings, pot transfers)*
- [x] 92. **Commodity market** [now] — resource prices that drift with supply and random events. *(on_tick price drift, rand events, $market tables)*
- [ ] 93. **Housing rent** [now] — periodic rent with warnings, then lockout/eviction. *(on_tick billing, grace attrs, set_lock eviction)*
- [ ] 94. **Job board** [now] — NPC-posted paid tasks claimed and verified automatically. *(posting attrs, ON_GIVE/ON_PAYMENT validation, payouts)*
- [ ] 95. **Item durability & repair** [now] — wear from use, repair costs as a money sink. *(durability attrs, zone-master ON_DAMAGE bookkeeping, $repair)*
- [ ] 96. **Secure player trade** [now] — both parties stage items/money and confirm atomically. *(escrow objects, dual prompt() confirms, one-script commit)*
- [ ] 97. **Barter NPC** [now] — trades item-for-item against a want-list instead of cash. *(want-list attrs, ON_RECEIVE matching)*

## 9. Games & Recreation (98–108)

- [ ] 98. **Dice roller** [now] — `roll 3d6` with success/margin interpretation vs. a skill. *(roll(), margin_under(), the resolution primitives)*
- [ ] 99. **Card deck** [now] — shuffle, deal, hold hands only their owner can see. *(list attrs, rand shuffles, pemit-private state)*
- [ ] 100. **Poker table** [now] — multi-player hold'em with betting rounds and pot. *(sandboxed-Python state machines, prompt() turns, hidden info)*
- [ ] 101. **Chess board** [now] — two-player board rendered in ASCII with move validation. *(eval_attr render helpers, grid attrs, sandboxed validation)*
- [ ] 102. **Trivia host NPC** [now] — timed rounds of questions loaded from a data file. *(pack/attr question data, prompt() answer windows, scoring)*
- [ ] 103. **Rock-paper-scissors** [now] — challenge with optional wagers and simultaneous reveal. *(dual prompt() secrets, escrowed bets, reveal remit)*
- [ ] 104. **Scavenger hunt** [now] — staff-set list of items/locations to find, with leaderboard. *(ON_GET/ON_ARRIVE detection, registry attrs)*
- [ ] 105. **NPC races & betting** [now] — scheduled races with odds and payouts. *(on_tick simulation, odds attrs, betting-book objects)*
- [ ] 106. **Arm wrestling** [now] — quick contest of ST with crowd-pleasing play-by-play. *(contest(), remit spectacle, wagers)*
- [ ] 107. **Dart board** [now] — throw for score; doubles as a DX practice minigame. *(skill_check margins, CP practice awards)*
- [ ] 108. **Casino floor** [now] — chips exchange, house bank, and multiple table games tied together. *(composing prior builds into a venue)*

## 10. Combat & Conflict Extensions (109–120)

- [ ] 109. **Cover system** [now] — take cover behind room fixtures for ranged defense bonuses. *(the engine cover maneuver, cover-tagged fixtures)*
- [ ] 110. **Ammunition & reloading** [small] — ranged weapons consume ammo; reload actions in combat. *(gap G8: ruleset ammo consumption + reload maneuver)*
- [ ] 111. **Grenades** [now] — fuse timers, throwing skill, scatter on a miss. *(wait() fuses, room-loop damage(), rand scatter over exits())*
- [ ] 112. **Non-lethal takedowns** [now] — subdue instead of kill; captives and restraints. *(engine unconsciousness, ON_HITPRCNT surrender, restraint wards)*
- [ ] 113. **Dueling system** [now] — formal consent-based PvP with stakes and a referee. *(consent prompt()s, start_combat, stakes escrow)*
- [ ] 114. **Bounty board** [now] — post bounties on characters; claims verified on defeat. *(ON_DEATH verification, escrow payouts)*
- [ ] 115. **Arena with spectators** [now] — fight pit that broadcasts blow-by-blow to the stands. *(recorder relays: ON_ATTACK/ON_DAMAGE → remit to stands)*
- [ ] 116. **Called shots** [small] — target hit locations with penalties and effects. *(gap G9: hit-location maneuver in the GURPS ruleset)*
- [ ] 117. **Armor degradation** [now] — armor absorbs damage but wears out and needs repair. *(ON_DAMAGE bookkeeping, DR attrs, repair sinks)*
- [ ] 118. **Bleeding & first aid** [now] — wounds bleed over time; First Aid skill stabilizes. *(damage_over_time behavior, the firstaid command)*
- [ ] 119. **NPC morale** [now] — mobs check morale, flee, or surrender when losing. *(ON_HITPRCNT behavior swaps, fleeing behavior, dispositions)*
- [ ] 120. **Combat replay log** [now] — per-fight log reviewable afterwards by participants. *(recorder objects, event-appended log attrs, $replay)*

## 11. Crafting & Resources (121–131)

- [ ] 121. **Gathering nodes** [now] — mineable ore/salvage spots that deplete and respawn. *(depletion attrs, on_tick respawn, yield margins)*
- [ ] 122. **Recipe crafting** [now] — combine ingredients at a bench with a skill roll. *(recipe validation, destroy/create, margin quality)*
- [ ] 123. **Refining chain** [now] — ore → ingot → parts, each stage a different station. *(multi-stage pipelines, tag-gated stations)*
- [ ] 124. **Salvage & disassembly** [now] — break items into components based on what they are. *(reverse recipes, component tables by tag)*
- [ ] 125. **Quality tiers** [now] — craft margin determines fine/good/shoddy output with stat effects. *(margin-driven output attrs)*
- [ ] 126. **Blueprint items** [now] — learnable schematics that unlock recipes when studied. *(ON_USE unlocks, known-list attrs)*
- [ ] 127. **Crafting stations** [now] — recipes requiring specific benches/tools present. *(environment tag checks in recipes)*
- [ ] 128. **Hydroponics farming** [now] — plant, water, and harvest crops growing in real time. *(on_tick growth stages, stage-swapped descs)*
- [ ] 129. **Cooking with buffs** [now] — meals granting temporary bonuses; spoilage. *(modifier_effect consumables, decay spoilage)*
- [ ] 130. **Fishing** [now] — cast, wait, hook with a timing/skill minigame and catch tables. *(wait() + prompt() timing windows, catch tables)*
- [ ] 131. **Chemistry & poisons** [now] — mix reagents into acids, medicines, and toxins safely or not. *(risky recipes, failure effects, skill prereqs)*

## 12. Character Systems (132–143)

- [ ] 132. **Chargen walkthrough** [now] — multi-step chargen with validation and review. *(GameSystem ChargenSteps or admin-owned prompt() wizards)*
- [ ] 133. **Short-descs & introductions** [small] — strangers appear as "a tall woman" until introduced. *(gap G3: per-viewer naming/sdesc-recog layer)*
- [ ] 134. **Disguises** [small] — masks and outfits that change your apparent identity. *(gap G3: apparent-name override + softcode rename)*
- [ ] 135. **Injury & treatment** [now] — wound states affecting stats until treated or healed. *(modifier_effect conditions, firstaid, regeneration)*
- [ ] 136. **Encumbrance effects** [now] — carried weight slows movement and penalizes DX. *(ON_GET/ON_DROP weight sums, modifier_effect penalties)*
- [ ] 137. **Hunger & thirst** [now] — optional survival meters with food/drink satisfying them. *(on_tick meters, ON_USE consumables, zone policy toggles)*
- [ ] 138. **Sleep & rest** [now] — resting recovers FP/HP faster; sleeping players are vulnerable. *(rest tags, regeneration boosts, vulnerability wards)*
- [ ] 139. **Intoxication** [small] — drinks impair stats and slur your speech progressively. *(stacking modifier_effects work now; slurring needs gap G2)*
- [ ] 140. **Death & cloning** [now] — death, body handling, and sci-fi clone respawn with costs. *(ON_DEATH, engine corpses/unconsciousness, clone-bay flows)*
- [ ] 141. **Character sheet display** [now] — full sheet rendered attractively. *(the stats command, $sheet via eval_attr layout functions)*
- [ ] 142. **Traits in play** [now] — advantages/disadvantages that actively hook mechanics. *(class_def/skill_def data, trait-driven triggers and wards)*
- [ ] 143. **XP spending** [now] — earn and spend points to improve skills with time-based limits. *(the CP economy: points/improve, now()-based limits)*

## 13. Time, Scheduling & Automation (144–153)

- [ ] 144. **Game calendar & clock** [now] — custom epoch, month names, and time conversion utils. *(softcode clocks from now(), calendar tables in attrs)*
- [ ] 145. **Scheduled world events** [now] — cron-style events (market day, meteor shower). *(on_tick cron checks, event-registry attrs)*
- [ ] 146. **Item decay** [now] — food rots, corpses decompose, litter is swept up. *(decay behavior, expire()/ON_EXPIRE, @foreach sweeps)*
- [ ] 147. **Zone repop** [now] — areas reset spawns and states on a cycle, skipping occupied rooms. *(zone_reset behavior, reset_spec, ON_RESET)*
- [ ] 148. **Delayed actions** [now] — "the fuse burns down…" — patterns for one-off future effects. *(wait()/cancel_wait idioms, the persistence caveat)*
- [ ] 149. **Maintenance sweeper** [now] — nightly script that finds orphans and cleans junk data. *(on_tick housekeeping, search_world queries, destroy_obj)*
- [ ] 150. **Global countdown events** [now] — server-wide announcements at T-minus intervals. *(wait() chains, remit loops over all rooms)*
- [ ] 151. **Business hours** [now] — shops and services only operate at certain game times. *(clock-driven behavior attach/detach, [[...]] closed states)*
- [ ] 152. **Reboot-surviving timers** [now] — timers that resume correctly after server restart. *(db timestamps + on_tick vs in-memory wait(); expire() persists)*
- [ ] 153. **Time scaling** [now] — running game time faster than real time and what it breaks. *(clock factors, world tick vs beats, combat pace)*

## 14. Movement & Transportation (154–164)

- [ ] 154. **Elevator** [now] — multi-floor car with call buttons and moving-room illusion. *(exit relinking via db.destination, state-driven connections)*
- [ ] 155. **Drivable vehicle** [now] — enterable rover you steer through the world from inside. *(vehicle-as-container-room, $drive traversal, [[...]] outside view)*
- [ ] 156. **Scheduled shuttle** [now] — transport that departs on a timetable along a route. *(on_tick timetables, boarding windows)*
- [ ] 157. **Teleporter pads** [now] — networked pads with destination selection and effects. *(teleport_obj, registry attrs, arrival remits)*
- [ ] 158. **Mounts** [now] — ride an animal/bike for speed; dismount rules. *(containment or following, $ride/$dismount)*
- [ ] 159. **Group travel** [now] — follow/lead so parties move as one. *(the built-in follow/party system, follower cascade)*
- [x] 160. **Sneaking** [now] — move silently with Stealth vs. Per contests, hiding in rooms. *(hide command, stealth contests, concealment state)*
- [ ] 161. **Travel time** [now] — long-distance moves take real seconds with progress messages. *(ward-blocked exits + wait() progress + teleport arrival)*
- [ ] 162. **Tracking** [now] — follow footprints left by earlier travelers with Tracking rolls. *(ON_LEAVE evidence objects, expire() decay, $track checks)*
- [ ] 163. **Vehicle fuel** [now] — vehicles consume fuel; refueling stations and running dry. *(consumption attrs, refuel services)*
- [ ] 164. **Small spaceship** [now] — cockpit, cabin, airlock; launch, fly between sites, dock. *(multi-room vehicles, interlocks, docking = relinking — capstone)*

## 15. Building & World Tools (165–175)

- [ ] 165. **Prototype library** [now] — organize spawnable content with inheritance and tags. *(spawner prototypes, @parent, @clone, pack data)*
- [ ] 166. **Batchcode areas** [now] — build a whole zone from a repeatable build file. *(@export/@import area files, plan → apply diffs)*
- [ ] 167. **Random dungeon generator** [now] — spin up a connected derelict-ship layout on demand. *(softcode room/exit carving, instance templates, teardown)*
- [ ] 168. **Room templates** [now] — stamp out consistent rooms (corridor, quarters) fast. *(@clone/@parent templates, $stamp wizards)*
- [ ] 169. **Zone mass-edit** [now] — retag, redescribe, or audit every room in a zone at once. *(@find/@foreach, zone_rooms(), dry-run discipline)*
- [ ] 170. **Builder wizard** [now] — menu-driven room/exit creation for non-coders. *(prompt() building wizards, create_obj + exit wiring)*
- [ ] 171. **Dynamic descriptions** [now] — descs that weave in state (weather, damage, time). *([[...]] inline evaluation — REALM's flagship)*
- [ ] 172. **World audit report** [now] — find orphaned objects, broken exits, oversized attributes. *(@eval, search_world introspection, health queries)*
- [ ] 173. **CSV world import** [now] — bulk-load rooms/items/NPCs from structured data. *(area files, @import stable-id sync, realm import CLI)*
- [ ] 174. **Auto-map generator** [now] — render an ASCII map computed from actual room links. *(exits() graph BFS, sandboxed-Python rendering)*
- [ ] 175. **Player housing customization** [now] — players redescribe and furnish owned rooms safely. *(@chown, control locks, room-owned $-commands, safe attr flags)*

## 16. Admin, Moderation & Staff Tools (176–186)

- [ ] 176. **Staff dashboard** [now] — one command showing server health, players, recent errors. *(@stats, who, @eval ops queries)*
- [ ] 177. **Jail system** [now] — timeout misbehaving players with auto-release and logging. *(teleport_obj, exit locks, wait() release, log attrs)*
- [ ] 178. **Ban & sitelock manager** [small] — account/IP bans with expiry and audit history. *(gap G12: ban registry in AuthService; login lockout exists)*
- [ ] 179. **Character approval queue** [now] — staff review/approve chargen submissions. *(unapproved tags, gating wards, $approve + pemit)*
- [ ] 180. **Staff invisibility** [small] — dark mode for staff with proper who/room handling. *(invisible tag + quell exist; gap G4: perception-aware who)*
- [ ] 181. **Announcement system** [now] — formatted server-wide notices with history. *(remit loops, history attrs, opt-out filters)*
- [ ] 182. **Object snapshot/restore** [now] — back up and restore a single object's attributes. *(@clone backups, @export, @eval attr dumps)*
- [ ] 183. **Permission tiers in practice** [now] — a worked tour of roles, locks, and quelling. *(god/admin/builder/player roles, controls(), quell)*
- [ ] 184. **New-player onboarding** [now] — auto-greeting, mentor assignment, starter kit. *(world-master ON_CONNECT, first-login attrs, kit spawning)*
- [ ] 185. **Rate limiting** [small] — command flood and spam protection with backoff. *(gap G13: per-session flood throttle; sandbox limits exist)*
- [ ] 186. **Watchlist & alerts** [now] — staff alerts when flagged players log in or act. *(ON_CONNECT watchers, watched tags, staff pemits)*

## 17. Information & UI (187–197)

- [ ] 187. **Status prompt** [small] — configurable prompt showing HP/FP/status after commands. *(gap G10: per-player prompt line; oob() vitals work today)*
- [ ] 188. **Custom who list** [small] — who with location, idle, faction columns and sorting. *(gap G4: session surface for softcode — online_players()/idle)*
- [ ] 189. **In-room minimap** [now] — small ASCII map of nearby rooms shown on look. *(ON_LOOK pemit, exits() BFS, exploration-memory attrs)*
- [ ] 190. **Score screen** [now] — attractive at-a-glance character status. *($score, eval_attr layout functions)*
- [ ] 191. **Help system extensions** [now] — auto-generated help from command metadata. *(the built-in help pipeline: categories, usage, help_text)*
- [ ] 192. **Clickable links** [small] — clickable exits, items, and commands where supported. *(gap G11: MXP markup at the telnet edge)*
- [ ] 193. **GMCP/OOB data** [now] — push vitals and room info to modern clients (Mudlet). *(oob(), telnet GMCP, websocket parity)*
- [ ] 194. **Screenreader mode** [small] — accessible output: no ASCII art, clean tables, verbose cues. *(gap G7: per-session render options beyond color on/off)*
- [ ] 195. **Color themes** [small] — user-selectable palettes with a no-color fallback. *(gap G7: per-player palette remap; color off exists)*
- [ ] 196. **Personal aliases (nicks)** [now] — players define their own command/object shorthands. *(carried alias gadgets: inventory $-commands)*
- [ ] 197. **Idle & AFK states** [small] — auto-AFK with returning messages and who display. *(gap G4: idle exposed to softcode + auto-AFK hook)*

## 18. Quests & Storytelling (198–208)

- [ ] 198. **Quest framework** [now] — quest objects with stages, journal, and completion hooks. *(admin-owned quest masters, stage attrs, $quests journal)*
- [ ] 199. **Delivery quest** [now] — fetch/carry template with timers and failure states. *(ON_GIVE verification, deadline timestamps)*
- [ ] 200. **Collection counters** [now] — "salvage 5 relays" tracked automatically on acquisition. *(zone-master ON_GET counting, tagged objectives)*
- [ ] 201. **Branching quest** [now] — choices that lock/unlock different endings. *(prompt() branches, mutually exclusive state attrs)*
- [ ] 202. **World event: invasion** [now] — staged zone-wide event with phases and cleanup. *(zone-master phases, spawner waves, ON_RESET cleanup)*
- [ ] 203. **Cutscenes** [now] — timed, paced sequences of text shown to one or many players. *(wait()-paced pemit/remit, $skip via cancel_wait)*
- [ ] 204. **GM possession tools** [now] — staff speak/act through any NPC live in a scene. *(@force, control locks, puppet forwarding)*
- [ ] 205. **Scene logger** [now] — opt-in RP scene recording with pose order tracking. *(recorder ^listen + ON_POSE, consent attrs, $export)*
- [ ] 206. **Rumor mill** [now] — plant rumors that spread organically via NPCs over days. *(rumor attrs hopping via on_tick, ^listen pickup, decay)*
- [ ] 207. **Achievements** [now] — badges for milestones with hidden and progressive tiers. *(ON_* watchers, badge attrs, secret attr flags)*
- [ ] 208. **Collectible lore** [now] — scattered logs/books that unlock codex entries when found. *(ON_GET/ON_USE unlocks, $codex rendering)*

## 19. Puzzles & Mechanisms (209–218)

- [ ] 209. **Lever combination** [now] — pull levers in the right pattern to open the vault. *(ON_PUSH, shared pattern attrs on a controller object)*
- [ ] 210. **Keypad code** [now] — enter a code discovered elsewhere in the world. *(prompt() entry, secret attrs, hint placement)*
- [ ] 211. **Riddle door** [now] — answer free-text riddles with fuzzy answer matching. *(prompt() free text, normalization with string functions)*
- [ ] 212. **Weight-plate puzzle** [now] — place the right objects on pressure plates. *(ON_RECEIVE/ON_PUT contents sensing)*
- [ ] 213. **Power routing puzzle** [now] — reroute ship power through junctions to unlock a deck. *(graph-state attrs, eval_attr win checks)*
- [ ] 214. **Simon sequence** [now] — repeat a growing pattern of signals correctly. *(wait()-chained signals, prompt() echo-back, timing windows)*
- [ ] 215. **Shifting maze** [now] — maze whose exits rearrange on a timer or trigger. *(on_tick exit relinking, mutable topology)*
- [ ] 216. **Escape room** [now] — locked suite of puzzles against a countdown, resettable. *(enter_instance() suites — reset is a fresh instance)*
- [ ] 217. **Hidden object search** [now] — search-the-room mechanics with Per-based finds. *(concealment tags, the search command, seeded secrets)*
- [ ] 218. **Puzzle reset engineering** [now] — making any puzzle safely repeatable for the next group. *(ON_RESET/zone_reset, instances, $reset scripts)*

## 20. Social & Player Systems (219–229)

- [ ] 219. **Friends list** [now] — contacts with login/logout notifications and privacy opt-outs. *(world-master ON_CONNECT/ON_DISCONNECT, consent attrs)*
- [ ] 220. **Titles & badges** [now] — earned display titles shown in look/finger. *(title attrs, desc_extras rendering)*
- [ ] 221. **Player organizations** [now] — guilds/crews with ranks, invites, and rosters. *(org master objects, rank attrs, lock expressions)*
- [ ] 222. **Org treasury & storage** [now] — shared bank and lockers with rank-gated access. *(org credits, rank-gated $-commands, locked containers)*
- [ ] 223. **Elections** [now] — org leadership voting with terms, ballots, and tallies. *(ballot attrs, vote dedupe, on_tick tallies)*
- [ ] 224. **Petition/ticket system** [now] — players file requests; staff triage a queue. *(ticket-queue attrs, $claim/$resolve, pemit notifications)*
- [ ] 225. **Player-to-player notes** [now] — staff annotations and player-visible profiles. *(notes attrs with secret/visual attr flags)*
- [ ] 226. **Mentor program** [now] — veterans flagged to help newbies, with matchmaking. *(mentor tags, pairing attrs, ON_CONNECT nudges)*
- [ ] 227. **Event calendar & RSVP** [now] — players schedule events; reminders fire. *(event attrs, $rsvp, on_tick reminders)*
- [ ] 228. **Leaderboards** [now] — top crafters/fighters/richest, computed periodically. *(on_tick aggregation, search_world scans, cached boards)*
- [ ] 229. **Login streak rewards** [now] — daily/anniversary perks with catch-up grace. *(ON_CONNECT date math, streak attrs, perk spawning)*

## 21. Web & External Integration (230–239)

- [ ] 230. **Web character profiles** [major] — public character pages served over HTTP. *(gap G1: web layer)*
- [ ] 231. **REST API endpoints** [major] — expose who/roster/market data as JSON. *(gap G1: web layer — API + auth + serialization)*
- [ ] 232. **Discord bridge** [major] — relay a game channel to a Discord channel bidirectionally. *(gap G5: external chat-bridge service)*
- [ ] 233. **Webhooks on events** [small] — POST to external URLs on deaths, sales, logins. *(gap G6: config-declared event→webhook sink)*
- [ ] 234. **Website who widget** [major] — live "who's online" embedded on the game website. *(gap G1: web layer)*
- [ ] 235. **JSON content packs** [now] — load item/NPC definitions from versioned JSON files. *(@pack, realm pack import, pack authoring)*
- [ ] 236. **Email notifications** [major] — offline players get mail digests via email. *(gap G5: SMTP delivery + digest batching)*
- [ ] 237. **Web-based build forms** [major] — submit rooms/items for review from the website. *(gap G1: web → game content pipeline)*
- [ ] 238. **In-game news from RSS** [small] — external feed rendered as an in-world news terminal. *(gap G6: allowlisted feed-fetch; rendering is softcode)*
- [ ] 239. **Character export** [major] — download your character sheet from the web. *(gap G1: player-facing web exports; realm export CLI exists)*

## 22. Scripting & Extensibility (240–250)

- [x] 240. **Builder trigger system** [now] — on_enter/on_say/on_get triggers builders attach without code. *($-commands, ^listen, ON_<EVENT> — the native feature)*
- [x] 241. **Response scripting in data** [now] — NPC keyword/response packs loaded from data files. *(packs/area files carrying listen_*/cmd_* attrs)*
- [x] 242. **Inline functions in text** [now] — rand/time/conditionals evaluated inside descs and speech. *([[...]] inline blocks with viewer binding)*
- [x] 243. **Object-verb pattern** [now] — attach bespoke commands to a single object, Penn-style. *($-commands gated by the use lock — native)*
- [ ] 244. **Player macros** [now] — record and replay short command sequences with safeguards. *(personal alias gadgets, multi-line scripts, sandbox limits)*
- [ ] 245. **Event bus tour** [now] — subscribing to and emitting game events across systems. *(two-pass propagation, act() custom events, action tags)*
- [ ] 246. **Hot-reload workflow** [now] — the live-world dev loop: what updates instantly, what doesn't. *(softcode is always live; @reload for data rules)*
- [ ] 247. **Testing your game** [now] — scripted tests for triggers, behaviors, and areas. *(the realm.testing Simulator, pytest, virtual-clock waits)*
- [ ] 248. **Custom input handling** [now] — capture raw input for a minigame, code entry, or editor. *(prompt()/choose()/confirm() wizards, persistent prompts)*
- [ ] 249. **Writing a contrib** [now] — package a build from this list as a reusable, configurable module. *(content packs, area files, versioning)*
- [x] 250. **Restricted player scripting** [now] — a sandboxed mini-language letting players script their own gadgets safely. *(the sandbox itself: limits, controls() authority — the capstone)*

---

## Suggested tutorial arcs

All five arcs are fully `[now]` — each runs end-to-end in softcode today:

- **First builds:** 5 → 1 → 2 → 14 → 25 (oracle, slot machine, vending machine, container, door)
- **The heist:** 27 → 16 → 49 → 54 → 48 → 160 (secret door, safe, landmine, cameras, gas bomb, sneaking)
- **Living NPCs:** 60 → 64 → 67 → 68 → 71 (wanderer → bartender → dialogue → schedules → guard response)
- **A working economy:** 86 → 63 → 87 → 89 → 92 (currency → shopkeeper → bank → auctions → markets)
- **Softcode for builders:** 243 → 240 → 241 → 242 → 250 (object verbs → triggers → data packs → inline funcs → sandbox)
