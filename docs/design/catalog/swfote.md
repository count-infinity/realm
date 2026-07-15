# SWFOTEFUSS (SW: Future of the Empire) command catalog — Force / empire / space additions over base SMAUG (SWR lineage)

| Codebase | Type | Group | Name | Scope | Description |
|---|---|---|---|---|---|
| swfote | Player | force | `lightning`/`force_lightning <victim>` | force-user (Sith) | Force lightning damage attack |
| swfote | Player | force | `slash <victim>` | force-user | Lightsaber slash strike |
| swfote | Player | force | `whirlwind` | force-user | Spinning saber hits all foes in room |
| swfote | Player | force | `squeeze`/`choke <victim>` | force-user (Sith) | Force grip/choke, ongoing damage |
| swfote | Player | force | `strike <victim>` | force-user | Telekinetic force strike |
| swfote | Player | force | `heal` | force-user (Jedi) | Force-heal self hp/wounds |
| swfote | Player | force | `protect <target>` | force-user | Grant force protection to ally |
| swfote | Player | force | `shield`/`fshield` | force-user | Raise defensive force shield |
| swfote | Player | force | `refresh` | force-user | Restore movement/energy via Force |
| swfote | Player | force | `awareness` | force-user | Force danger-sense / perception buff |
| swfote | Player | force | `sense` | force-user | Sense beings/force presence |
| swfote | Player | force | `meditate` | force-user | Meditate to regain force/mana |
| swfote | Player | force | `identify` | force-user | Force-identify an object |
| swfote | Player | force | `fdisguise` | force-user | Cloak identity via the Force |
| swfote | Player | force | `finish <victim>` | force-user | Finishing blow on downed foe |
| swfote | Player | force | `parry` | force-user (passive) | Auto lightsaber parry in melee |
| swfote | Player | force | `reflect` | force-user (passive) | Deflect blaster bolts with saber |
| swfote | Player | force | `finfo [power]` | force-user | Show force skills/level/alignment status |
| swfote | Player | force | `fhelp [topic]` | force-user | Force-specific help system |
| swfote | Player | force | `makelightsaber` | force-user | Craft a lightsaber |
| swfote | Player | force | `makedualsaber`/`dwieldsaber` | force-user | Craft/dual-wield double saber |
| swfote | Player | force | `train <stat>` | any/force-user | Train stats/force level at trainer |
| swfote | Player | force | `teach <skill>` | force-user | Teach a skill to another player |
| swfote | Player | force | `student`/`convert <name>` | force-user (master) | Take/convert a player as apprentice |
| swfote | Player | force | `promote <name>` | force-user (master) | Advance apprentice's force rank |
| swfote | Player | force | `master <name>` | force-user (master) | Mastery-train an apprentice |
| swfote | Player | force | `instruct <name>` | force-user (master) | Instruct student in a force skill |
| swfote | Builder | force | `fstat <power>` | immortal | View force-power definition (level/type/cost) |
| swfote | OLC | force | `fset <power> <field>` | immortal | Edit force-power data (Jedi/Sith/general, cost, effects) |
| swfote | Builder | force | `fhstat <topic>` | immortal | View force-help entry |
| swfote | OLC | force | `fhset <topic> <field>` | immortal | Edit force-help entries |
| swfote | Admin | force | `setforcer <victim> <lvl> [jedi/sith/neutral] <status> <pct>` | immortal | Set player force level/alignment/skill |
| swfote | Admin | force | `make_master`/`makemaster` | immortal | Grant force-master status |
| swfote | Builder | alignment | `mset <mob> align <n>` | immortal | Set alignment (light/dark side axis) |
| swfote | Player | empire | `clans` | any | List clans/factions/empires |
| swfote | Player | empire | `showclan <clan>` | any | Show clan detail |
| swfote | Player | empire | `clanstat <clan>` | member | Clan status/treasury/troops |
| swfote | Player | empire | `members` | member | List clan members |
| swfote | Player | empire | `clantalk`/`;` | member | Clan communication channel |
| swfote | Player | empire | `wartalk` | member | Wartime clan channel |
| swfote | Player | empire | `enlist` | any | Enlist/apply to a clan |
| swfote | Player | empire | `induct <name>` | leader | Induct a player into clan |
| swfote | Player | empire | `outcast <name>` | leader | Expel a clan member |
| swfote | Player | empire | `empower <name>` | leader | Grant leadership/deputy powers |
| swfote | Player | empire | `resign` | member | Resign from clan |
| swfote | Player | empire | `outlaw`/`unoutlaw <name>` | leader | Manage clan outlaw list |
| swfote | Player | empire | `war <clan>`/`checkwar` | leader | Declare/check inter-clan war |
| swfote | Player | empire | `buytroops`/`clanbuytroops` | leader | Purchase clan military troops |
| swfote | Player | empire | `setwage <n>` | leader | Set member wage payout |
| swfote | Player | empire | `donate`/`withdraw` | member/leader | Clan bank deposit/withdraw |
| swfote | Player | empire | `senate` | senator | Galactic senate assembly |
| swfote | Admin | empire | `addsenator`/`remsenator <name>` | immortal | Manage senate membership |
| swfote | Admin | empire | `makeclan`/`newclan`/`remclan` | immortal | Create/remove clan/empire |
| swfote | Builder | empire | `setclan <field>` | immortal | Edit clan properties |
| swfote | Player | planet | `planets` | any | List planets |
| swfote | Player | planet | `showplanet <planet>` | any | Show planet detail/owner |
| swfote | Player | planet | `capture` | member | Capture planet for your clan/empire |
| swfote | Admin | planet | `makeplanet <name>` | immortal | Create a planet |
| swfote | Builder | planet | `setplanet <field>` | immortal | Edit planet (owner, taxes, resources) |
| swfote | Player | space | `starsystems` | any | List star systems |
| swfote | Player | space | `showstarsystem <sys>` | any | Show star system detail |
| swfote | Admin | space | `makestarsystem <name>` | immortal | Create star system (SWR lineage) |
| swfote | Builder | space | `setstarsystem <field>` | immortal | Edit star system |
| swfote | Player | ship | `board`/`launch`/`land` | pilot | Enter/launch/land a ship |
| swfote | Player | ship | `leaveship` | any | Exit a docked ship |
| swfote | Player | ship | `fly`/`drive <dir>` | pilot | Pilot ship/vehicle |
| swfote | Player | ship | `accelerate <speed>` | pilot | Set ship speed |
| swfote | Player | ship | `trajectory`/`jumpvector`/`calculate` | pilot | Plot/hyperspace course |
| swfote | Player | ship | `hyperspace` | pilot | Enter hyperspace |
| swfote | Player | ship | `radar`/`status`/`info`/`target` | pilot | Ship sensors/status/targeting |
| swfote | Player | ship | `fire`/`reload`/`bomb` | pilot | Ship weapons fire/reload/bombing |
| swfote | Player | ship | `tractorbeam`/`chaff` | pilot | Tractor capture / countermeasures |
| swfote | Player | ship | `autopilot`/`autotrack`/`autorecharge` | pilot | Ship automation toggles |
| swfote | Player | ship | `refuel`/`recharge`/`shiprepair` | pilot | Ship maintenance |
| swfote | Player | ship | `openhatch`/`closehatch`/`openbay`/`closebay`/`shiplock` | pilot | Ship access control |
| swfote | Player | ship | `addpilot`/`rempilot` | owner | Manage authorized pilots |
| swfote | Player | ship | `buyship`/`sellship`/`ordership` | any | Purchase/sell/order ships |
| swfote | Player | ship | `clanbuyship`/`clangiveship`/`clansalvage`/`orderclanship` | member | Clan/empire ship logistics |
| swfote | Player | ship | `ships`/`allships`/`shiplist`/`showship`/`shipstat` | any | List/inspect ships |
| swfote | Player | ship | `speeders`/`allspeeders` | any | List ground speeders |
| swfote | Admin | ship | `makeship`/`setship`/`removeship`/`copyship`/`freeship` | immortal | Build/edit ship prototypes |
| swfote | Admin | ship | `makesimulator`/`endsimulator` | immortal | Ship combat training simulator |
| swfote | Player | ship | `bounty`/`addbounty`/`rembounty` | any/immortal | Bounty-hunting board |
| swfote | OLC | building | `redit` | immortal | Room editor (inherited from SMAUG) |
| swfote | OLC | building | `sedit` | immortal | Skill editor (inherited from SMAUG) |
| swfote | OLC | building | `hedit` | immortal | Help editor (inherited from SMAUG) |
| swfote | OLC | building | `cedit` | immortal | Command-table editor (inherited from SMAUG) |
| swfote | OLC | building | `mpedit`/`opedit`/`rpedit` | immortal | Mob/obj/room prog editors (inherited) |
| swfote | Builder | building | `oset`/`mset`/`rset`/`sset` | immortal | Set obj/mob/room/skill fields (inherited) |
| swfote | Builder | building | `reset` | immortal | Room reset editor (inherited from SMAUG) |
| swfote | Admin | info | `goto`/`transfer`/`mwhere`/`memory`/`purge`/`slay`/`restore` | immortal | Standard SMAUG wiz commands (inherited) |
