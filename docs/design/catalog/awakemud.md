# AwakeMUD (Shadowrun 3e, CircleMUD/Diku C++) command surface — Matrix/rigging/magic emphasis

| Codebase | Type | Group | Name | Scope | Description |
| --- | --- | --- | --- | --- | --- |
| awakemud | Player | matrix | jack <deck> / unjack | decker | Jack cyberdeck into/out of a jackpoint. |
| awakemud | Player | matrix | connect / logon [host] | decker | Log the persona onto a matrix host. |
| awakemud | Player | matrix | logoff / logout / disconnect / quit | decker | Jack out; disconnect from the matrix. |
| awakemud | Player | matrix | look | decker | View current host, its icons and subsystems. |
| awakemud | Player | matrix | scan | decker | Scan/map adjacent hosts and datastore contents. |
| awakemud | Player | matrix | locate <target> | decker | Locate access node, file, decker, or paydata. |
| awakemud | Player | matrix | analyze <target> | decker | Analyze host/icon/security for ratings. |
| awakemud | Player | matrix | run <program> | decker | Run a utility against a subsystem (attack/decrypt/etc). |
| awakemud | Player | matrix | load / unload / upload / swap <prog> | decker | Load programs from deck memory into active memory. |
| awakemud | Player | matrix | download <file> | decker | Download paydata/file to deck storage. |
| awakemud | Player | matrix | decrypt <subsystem> | decker | Decrypt an encrypted file or subsystem. |
| awakemud | Player | matrix | disarm | decker | Disarm a data bomb on a file. |
| awakemud | Player | matrix | crash <deck> | decker | Crash a target's deck (matrix attack). |
| awakemud | Player | matrix | evade | decker | Evade/shake an active trace. |
| awakemud | Player | matrix | parry | decker | Defend against IC in matrix combat. |
| awakemud | Player | matrix | abort | decker | Abort the current matrix operation. |
| awakemud | Player | matrix | redirect | decker | Redirect the datatrail to slow trace. |
| awakemud | Player | matrix | trace <target> | decker | Trace another icon's origin. |
| awakemud | Player | matrix | tap <target> | decker | Tap a line/comm for surveillance. |
| awakemud | Player | matrix | restrict | decker | Restrict/lock down a host subsystem (control). |
| awakemud | Player | matrix | reveal | decker | Reveal hidden icons in the host. |
| awakemud | Player | matrix | max | decker | Show deck's max/active memory usage. |
| awakemud | Player | matrix | score / position | decker | Persona/deck status while decking. |
| awakemud | Player | matrix | asist | decker | Toggle ASIST/hitcher perception link. |
| awakemud | Player | matrix | software | decker | List programs stored on the deck. |
| awakemud | Player | matrix | talk / call / answer / hangup | decker | Comcall (in-matrix phone/comms). |
| awakemud | Player | matrix | selffry | immortal | Debug: fry own persona (test command). |
| awakemud | Player | vehicle | drive [dir] | rigger | Drive a vehicle manually one direction. |
| awakemud | Player | vehicle | rig <vehicle> | rigger | Jack into vehicle control rig (VCR) to pilot. |
| awakemud | Player | vehicle | control | rigger | Enter remote-control/drone rigging deck. |
| awakemud | Player | vehicle | speed <n> | rigger | Set the vehicle's cruising speed. |
| awakemud | Player | vehicle | chase <target> | rigger | Pursue another vehicle/target. |
| awakemud | Player | vehicle | flyto / land | rigger | Fly aircraft to a destination / land it. |
| awakemud | Player | vehicle | gridguide <dest> | rigger | Autonav via GridGuide to a saved destination. |
| awakemud | Player | vehicle | ram <target> | rigger | Ram another vehicle or obstacle. |
| awakemud | Player | vehicle | driveby | rigger | Perform a drive-by attack while moving. |
| awakemud | Player | vehicle | target <mount> | rigger | Acquire target for a vehicle-mounted weapon. |
| awakemud | Player | vehicle | man <mount> | any | Man a mounted weapon/turret. |
| awakemud | Player | vehicle | mount <weapon> | rigger | Install a weapon onto a vehicle mount. |
| awakemud | Player | vehicle | upgrade <vehicle> | rigger | Install/modify vehicle mods (workshop). |
| awakemud | Player | vehicle | switch | any | Switch between front/back seats of a vehicle. |
| awakemud | Player | vehicle | pop | any | Pop trunk/hood/hidden compartment. |
| awakemud | Player | vehicle | tow <vehicle> | rigger | Tow another vehicle. |
| awakemud | Player | vehicle | push | any | Push a disabled vehicle. |
| awakemud | Player | vehicle | transfer | any | Transfer occupants/gear between vehicles. |
| awakemud | Player | vehicle | repair / fix | any | Repair vehicle/rig damage. |
| awakemud | Player | vehicle | subscribe / unsubscribe | rigger | Manage rigger's subscribed drone list. |
| awakemud | Player | vehicle | watch <vehicle> | any | Watch a vehicle's occupants/actions. |
| awakemud | Player | vehicle | vemote / osay | rigger | Emote/speak as/from the vehicle. |
| awakemud | Player | vehicle | wheresmycar | any | Locate your owned/garaged vehicle. |
| awakemud | Player | magic | cast <spell> [target] | mage | Cast a sorcery spell. |
| awakemud | Player | magic | ritualcast <spell> | mage | Perform a ritual sorcery casting. |
| awakemud | Player | magic | spells | mage | List known spells / spellbook. |
| awakemud | Player | magic | dispell <spell> | mage | Dispel a sustained/active spell. |
| awakemud | Player | magic | conjure <type> <force> | mage | Conjure an elemental/nature spirit. |
| awakemud | Player | magic | spirits / elementals | mage | List bound spirits and elementals. |
| awakemud | Player | magic | banish <spirit> | mage | Banish a hostile/enemy spirit. |
| awakemud | Player | magic | domain | mage | Show/set the mage's spirit domain. |
| awakemud | Player | magic | manifest | mage | Manifest an astral form to the physical. |
| awakemud | Player | magic | project | mage | Astrally project from the body. |
| awakemud | Player | magic | perceive | mage | Enter/leave astral perception. |
| awakemud | Player | magic | assense <target> | mage | Astrally assense an aura for info. |
| awakemud | Player | magic | focus <item> | mage | Activate/deactivate a magical focus. |
| awakemud | Player | magic | bond / unbond <focus> | mage | Bond a focus/weapon foci to the mage. |
| awakemud | Player | magic | powerdown | mage | Drop all sustained spells/foci. |
| awakemud | Player | magic | cleanse | mage | Cleanse background/astral taint. |
| awakemud | Player | magic | metamagic | mage | View/manage learned metamagic techniques. |
| awakemud | Player | magic | initiate | mage | Undergo initiation to raise grade. |
| awakemud | Player | magic | addpoint | mage | Spend karma as a power point (non-initiate). |
| awakemud | Player | magic | submerse | decker | Otaku equivalent of initiation (resonance). |
| awakemud | Player | magic | heal / treat | mage | Magically heal / first-aid treat wounds. |
| awakemud | Player | magic | design <spell> | mage | Design a new spell formula (workshop). |
| awakemud | Player | cyberware | cyberware | any | List installed cyberware. |
| awakemud | Player | cyberware | bioware | any | List installed bioware. |
| awakemud | Player | cyberware | activate / deactivate <ware> | any | Toggle cyberware (e.g. spurs, smartlink). |
| awakemud | Player | cyberware | boost | any | Trigger boosted reflexes / wired reflexes. |
| awakemud | Player | cyberware | reflex | any | Set wired-reflex activation level. |
| awakemud | Player | cyberware | download / upload <ware> | any | Move data to/from headware memory. |
| awakemud | Player | cyberware | chipload / load <chip> | any | Load a skillsoft/activesoft into a chipjack. |
| awakemud | Player | cyberware | drugs | any | List active drugs and addiction status. |
| awakemud | Player | cyberware | patch | any | Apply a stim/trauma/slap patch. |
| awakemud | Player | object | build <parts> | decker | Build a cyberdeck from component parts. |
| awakemud | Player | object | cook <chip> | any | Burn/cook an optical chip (softs). |
| awakemud | Player | object | program <target> | decker | Program matrix software / persona programs. |
| awakemud | Player | object | design <part> | any | Design deck part / program / spell (crafting). |
| awakemud | Player | object | attach / unattach <item> | any | Attach accessory (scope, silencer) to gear. |
| awakemud | Player | object | install / uninstall | any | Install/remove modular components. |
| awakemud | Player | object | packup / unpack | any | Pack/unpack a workshop or facility. |
| awakemud | Player | object | repair / fix <item> | any | Repair damaged equipment. |
| awakemud | Player | object | restring <item> <desc> | any | Rename/redescribe owned gear (cosmetic). |
| awakemud | Player | object | ammo / reload / draw / holster | any | Manage firearm ammo, reload, draw, holster. |
| awakemud | Player | object | get/drop/give/put/wear/remove/wield | any | Standard Diku object handling (representative). |
| awakemud | Player | comm | say / ' / sayto / osay | any | Local room speech (incl. one-way osay). |
| awakemud | Player | comm | tell / reply | any | Private cross-game tells. |
| awakemud | Player | comm | ooc / question / ht / rt / shout | any | OOC, newbie-question, hired, RPE, shout channels. |
| awakemud | Player | comm | phone / call / answer / hangup | any | In-world phone system. |
| awakemud | Player | comm | radio | any | Squad radio (frequency-based). |
| awakemud | Player | comm | broadcast / , | any | Broadcast to nearby radios. |
| awakemud | Player | comm | emote / : / vemote | any | Freeform / vehicle emotes. |
| awakemud | Player | comm | ignore / block | any | Ignore/block another player. |
| awakemud | Player | comm | history / says / oocs / tells | any | Recall channel message history. |
| awakemud | Player | comm | pgroup | any | Player-group (runner-team) management. |
| awakemud | Player | info | score / status / affects | any | Character sheet, condition, active effects. |
| awakemud | Player | info | skills / abilities / powers | any | List skills, active/adept abilities. |
| awakemud | Player | info | pools / cpool | any | Show dice pools (combat/spell/etc). |
| awakemud | Player | info | penalties | any | Show current wound/situational penalties. |
| awakemud | Player | info | inventory / equipment / pockets | any | List carried/worn gear. |
| awakemud | Player | info | tke / karma | any | Show total karma earned (TKE). |
| awakemud | Player | info | networth / balance / gold | any | Show nuyen and net worth. |
| awakemud | Player | info | memory / remember / forget | any | Remember/forget introduced names. |
| awakemud | Player | info | who / quickwho / where | any | Who-list and player locations. |
| awakemud | Player | info | recap / jobs / quests / progress | any | Runs/jobs log and advancement progress. |
| awakemud | Player | info | leaderboards | any | View leaderboards. |
| awakemud | Player | info | look / examine / probe / scan | any | Look, examine, probe, scan surroundings. |
| awakemud | Player | info | map / survey / exits | any | Room map, area survey, exit list. |
| awakemud | Player | info | consider / diagnose / assense | any | Assess target's toughness/wounds/aura. |
| awakemud | Player | info | train / practice / learn / teach | any | Improve/learn skills at a trainer. |
| awakemud | Player | info | customize / toggle / configure / display | any | Player preferences, prompt, toggles. |
| awakemud | Player | info | banish (mob) / hail / consent | any | Social-flow and consent controls. |
| awakemud | OLC | building | redit | builder | Room editor (OLC). |
| awakemud | OLC | building | medit | builder | Mobile (NPC) editor (OLC). |
| awakemud | OLC | building | iedit | builder | Object/item editor (OLC). |
| awakemud | OLC | building | vedit | builder | Vehicle editor (OLC). |
| awakemud | OLC | building | icedit | builder | IC (intrusion countermeasures/matrix ICE) editor. |
| awakemud | OLC | building | sedit | builder | Shop editor (OLC). |
| awakemud | OLC | building | zedit | builder | Zone/reset editor (OLC). |
| awakemud | OLC | building | qedit | builder | Quest editor (OLC). |
| awakemud | OLC | building | hedit / helpedit | builder | Help-file editor (OLC). |
| awakemud | OLC | building | houseedit | builder | Apartment/house/complex editor. |
| awakemud | Builder | building | dig / oneway / undig <dir> | builder | Create/remove exits and linked rooms. |
| awakemud | Builder | building | *list (rlist/mlist/ilist/vlist/…) | builder | List protos by type in a zone. |
| awakemud | Builder | building | *clone (rclone/mclone/iclone/vclone/…) | builder | Clone a prototype. |
| awakemud | Builder | building | *delete (rdelete/mdelete/…) | immortal | Delete a prototype/zone. |
| awakemud | Builder | building | *find (vfind/setfind/shopfind) | builder | Search protos/sets/shops. |
| awakemud | Builder | building | vnum / vstat / stat / vteleport | builder | Inspect vnums, stat objects, teleport by vnum. |
| awakemud | Builder | building | iload / wizload | builder | Load an item/mob prototype into the world. |
| awakemud | Builder | building | zreset / zone / zswitch / zdelete | builder | Zone reset and management. |
| awakemud | Builder | building | goto / at / teleport / vteleport | builder | Move to/act at a location. |
| awakemud | Builder | building | redesc / exdescs / tempdesc | builder | Edit room/extra/temporary descriptions. |
| awakemud | Builder | building | phonelist / hlist / iclist / slist | builder | List phones/helps/ICE/spells protos. |
| awakemud | Admin | immortal | advance / self_advance | immortal | Set a player's level. |
| awakemud | Admin | immortal | set / valset / vset / pgset | immortal | Edit player/obj/vehicle values and pgroups. |
| awakemud | Admin | immortal | skillset / spellset / abilityset | immortal | Grant/set a player's skills/spells/abilities. |
| awakemud | Admin | immortal | award / deduct / charge / payout / garnish | immortal | Adjust karma/nuyen; economy admin. |
| awakemud | Admin | immortal | force / forceget / forceput | immortal | Force a character to act. |
| awakemud | Admin | immortal | switch / possess / return | immortal | Puppet/possess an NPC. |
| awakemud | Admin | immortal | snoop / send / restore | immortal | Snoop a session, message, full-heal. |
| awakemud | Admin | immortal | purge / destroy / load | immortal | Purge/destroy/load entities. |
| awakemud | Admin | immortal | invis / incognito / visible / poofin/poofout | immortal | Wizinvis and entrance/exit messages. |
| awakemud | Admin | immortal | freeze / thaw / mute / notitle / squelch | immortal | Player disciplinary controls. |
| awakemud | Admin | immortal | ban / unban / banvpn / authorize | immortal | Site bans and account authorization. |
| awakemud | Admin | immortal | echo / aecho / gecho / zecho / vteleport | immortal | Echo text to room/area/game/zone. |
| awakemud | Admin | immortal | wizhelp / wwho / wtell / wf | immortal | Immortal help, who, wiztell, wizfeel. |
| awakemud | Admin | immortal | hcontrol / houseedit | immortal | Housing (player apartment) admin. |
| awakemud | Admin | immortal | copyover / reboot / shutdown / crashmud | immortal | Server lifecycle control. |
| awakemud | Admin | immortal | cheatlog / cheatmark / logwatch / tridlog | immortal | Audit/anti-cheat logging. |
| awakemud | Admin | immortal | perfmon / metrics / users / fuckups | immortal | Performance, metrics, connected users, error log. |
| awakemud | Admin | immortal | olc / debug / settime / wizlock / slowns | immortal | OLC toggle and low-level dev tools. |
