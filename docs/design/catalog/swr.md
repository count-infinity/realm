# SWR-FUSS (Star Wars Reality, SMAUG-derived) command surface — space/ship emphasis

| Codebase | Type | Group | Name | Scope | Description |
| --- | --- | --- | --- | --- | --- |
| swr | Player | piloting | board <ship> | any | Enter a ship/vehicle via its hatch. |
| swr | Player | piloting | leaveship | pilot | Exit ship to the room/space outside. |
| swr | Player | piloting | launch | pilot | Take off from ground/dock into space (cockpit). |
| swr | Player | piloting | land [target] | pilot | Land on planet or dock at a bay. |
| swr | Player | piloting | drive <dir> | pilot | Pilot a land speeder/vehicle one direction. |
| swr | Player | piloting | fly | pilot | Atmospheric-flight stub (unimplemented). |
| swr | Player | piloting | accelerate/speed/velocity <n> | pilot | Set sublight speed. |
| swr | Player | piloting | trajectory/course/vector <x y z> | pilot | Set heading toward coordinates. |
| swr | Player | piloting | calculate <system> | pilot | Compute hyperspace jump coordinates. |
| swr | Player | piloting | hyperspace/lightspeed | pilot | Jump to hyperspace toward calculated system. |
| swr | Player | piloting | jumpvector/entryvector <x y z> | pilot | Set hyperspace entry/exit vector. |
| swr | Player | piloting | autopilot | pilot | Toggle automated navigation. |
| swr | Player | piloting | autotrack | pilot | Auto-follow the current target. |
| swr | Player | piloting | refuel | pilot | Refuel ship (at fuel source). |
| swr | Player | piloting | openhatch / closehatch | pilot | Open/close ship boarding hatch. |
| swr | Player | piloting | openbay / closebay | pilot | Open/close carrier launch bay doors. |
| swr | Player | combat-space | target <ship> | pilot | Acquire a target ship in the system. |
| swr | Player | combat-space | fire [weapon] | pilot | Fire lasers/turbolasers at target. |
| swr | Player | combat-space | bomb | pilot | Drop bomb / proton ordnance. |
| swr | Player | combat-space | reload | pilot | Reload torpedoes/missiles. |
| swr | Player | combat-space | chaff | pilot | Launch countermeasures vs incoming missiles. |
| swr | Player | combat-space | recharge / autorecharge (shields) | pilot | Recharge shields; toggle auto-recharge. |
| swr | Player | combat-space | tractorbeam <ship> | pilot | Capture/hold another ship with tractor beam. |
| swr | Player | info | status | pilot | Show ship status (hull/shields/energy/speed). |
| swr | Player | info | radar | pilot | Scan nearby ships/objects in the starsystem. |
| swr | Player | info | info | pilot | Show current ship's stats/details. |
| swr | Player | info | ships | any | List ships (in shipyard/area you can access). |
| swr | Player | info | speeders | any | List land vehicles present. |
| swr | Player | info | starsystems | any | List known star systems. |
| swr | Player | info | planets | any | List planets. |
| swr | Player | ship | buyship <type> | any | Buy a ship at a shipyard. |
| swr | Player | ship | sellship <ship> | any | Sell a ship back at a shipyard. |
| swr | Player | ship | clanbuyship <type> | any | Buy a ship using clan funds. |
| swr | Player | ship | repairship / repair | pilot | Repair ship at a repair shop. |
| swr | Player | ship | addpilot <name> | pilot | Authorize another pilot for the ship. |
| swr | Player | ship | rempilot <name> | pilot | Revoke a ship pilot's authorization. |
| swr | Player | comm | spacetalk <msg> | pilot | Radio comm to ships in the same system. |
| swr | Player | comm | clantalk <msg> | any | Clan/faction private channel. |
| swr | Player | clan | clans | any | List clans/factions. |
| swr | Player | clan | newclan | any | Petition/create a new clan (application). |
| swr | Player | clan | induct <player> | any | Induct a player into your clan (leader). |
| swr | Player | clan | outcast <player> | any | Remove a member from your clan (leader). |
| swr | Player | clan | donate <amount> | any | Deposit credits to clan treasury. |
| swr | Player | clan | withdraw <amount> | any | Withdraw credits from clan treasury. |
| swr | OLC | ship | makeship <name> | immortal | Create a new ship prototype (lvl 105). |
| swr | OLC | ship | setship <field> <val> | immortal | Edit ship fields: shipyard/type/class/hyperspeed/maxspeed/etc (lvl 103). |
| swr | OLC | ship | showship <ship> | immortal | View a ship's full data (lvl 102). |
| swr | OLC | ship | copyship <src> <dst> | immortal | Clone a ship prototype (lvl 105). |
| swr | OLC | ship | resetship <ship> | immortal | Reset ship to spawn/prototype state (lvl 103). |
| swr | OLC | ship | allships / allspeeders | immortal | List every ship/vehicle in game. |
| swr | OLC | planet | makestarsystem <name> | immortal | Create a star system (lvl 103). |
| swr | OLC | planet | setstarsystem <field> <val> | immortal | Edit star system data (lvl 103). |
| swr | OLC | planet | showstarsystem <name> | immortal | View star system data (lvl 102). |
| swr | OLC | planet | makeplanet <name> | immortal | Create a planet in a system (lvl 105). |
| swr | OLC | planet | setplanet <field> <val> | immortal | Edit planet data (lvl 105). |
| swr | OLC | building | makerepair / repairset / repairstat / repairshops | immortal | Create/edit repair shops (shipyards) (lvl 102). |
| swr | OLC | building | makeshop / shopset / shopstat / shops | immortal | Create/edit vendor shops (inherited from SMAUG, extended). |
| swr | OLC | building | instaroom | immortal | Quick-create a room (lvl 102). |
| swr | Admin | clan | makeclan / setclan / showclan | immortal | Create/edit/view clan records (lvl 102-103). |
| swr | OLC | building | redit / rset / oset / mset / mpedit | builder | Room/object/mob/mobprog editing (inherited from SMAUG). |
| swr | Admin | building | aset / sset / slookup / foldarea | immortal | Area/skill/save admin (inherited from SMAUG). |
| swr | Player | comm | say / tell / channels | any | Standard chat (inherited from SMAUG/Diku). |
| swr | Player | info | look / score / who / where | any | Standard info (inherited from SMAUG/Diku). |
