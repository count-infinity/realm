# TinyMUX 2.x command & softcode-function surface (player/builder/admin)

| Codebase | Type | Group | Name | Scope | Description |
|---|---|---|---|---|---|
| tinymux | Player | info | look [<obj>] | any | Look at room/object, show description & contents |
| tinymux | Player | object | examine <obj> | controls/see | Show object attributes, flags, owner |
| tinymux | Player | object | get/drop/give <obj> | location | Pick up, drop, or give objects/money |
| tinymux | Player | object | goto/enter/leave/use <exit> | location | Move via exit, enter/leave vehicle, use object |
| tinymux | Player | object | inventory / score | any | List carried objects / show money & stats |
| tinymux | Player | comm | say/pose/"/:/;/\\ <msg> | location | Speak or emote to the room |
| tinymux | Player | comm | whisper <who>=<msg> | location | Private message to someone in room |
| tinymux | Player | comm | page <who>=<msg> | any | Send remote private message (switches: /list /reply) |
| tinymux | Player | info | who / doing / session | any | List connected players, doing lines, session info |
| tinymux | Player | info | +help/help/info | any | Read help & info text files |
| tinymux | Player | object | kill/slay <who> | any/wizard | Attack player (kill=combat, slay=instant/wizard) |
| tinymux | Player | queue | think <expr> | any | Evaluate expression, show result to self |
| tinymux | Player | admin | quit/logout/QUIT | any | Disconnect or drop to login screen |
| tinymux | Builder | building | @dig <room>=<exitto>,<exitback> | builder | Create room with linked exits (MUX-distinct argv) |
| tinymux | Builder | building | @open <exit>=<loc>,<back> | builder | Create exit in current room, optional linkback |
| tinymux | Builder | building | @create <obj>[=<cost>] | builder | Create a thing object |
| tinymux | Builder | building | @clone <obj>[=<newname>] | controls | Duplicate object with attributes |
| tinymux | Builder | building | @link <obj>=<dest> | builder/controls | Link exit/home/drop-to destination |
| tinymux | Builder | building | @unlink <exit> | controls | Remove exit link / room drop-to |
| tinymux | Builder | building | @destroy <obj> | controls | Destroy object (switch: /override) |
| tinymux | Builder | building | @teleport <obj>=<dest> | controls | Move object to location |
| tinymux | Builder | object | @name <obj>=<name>[;aliases] | controls | Rename object |
| tinymux | Builder | object | @moniker <obj>=<text> | controls | Set ANSI display moniker (MUX-distinct) |
| tinymux | Builder | object | @describe/@desc <obj>=<text> | controls | Set description (via @set/attr; @edit edits it) |
| tinymux | Builder | object | @set <obj>=<flag>/<attr>:<val> | controls | Set flags or attributes on object |
| tinymux | Builder | object | &<attr> <obj>=<val> | controls | Set user attribute (leadin shorthand) |
| tinymux | Builder | object | @lock <obj>[/<type>]=<key> | controls | Set a lock (default/use/enter/etc.) |
| tinymux | Builder | object | @unlock <obj>[/<type>] | controls | Remove a lock |
| tinymux | Builder | object | @parent <obj>=<parent> | controls | Set attribute-inheritance parent |
| tinymux | Builder | object | @chown <obj>[=<player>] | controls/wizard | Change object owner (@chownall wizard) |
| tinymux | Builder | object | @chzone <obj>=<zone> | controls | Assign object to a zone master |
| tinymux | Builder | object | @cpattr / @mvattr / @edit | controls | Copy, move, or search-replace attributes |
| tinymux | Builder | object | @wipe <obj> | controls | Delete all attributes on object |
| tinymux | Builder | object | @decompile <obj> | controls | Emit commands to recreate object's attrs/flags |
| tinymux | Builder | info | @find / @entrances / @search | builder | Find owned objects / exits leading to / DB search |
| tinymux | Builder | info | @scan / @sweep | any | Show which cmds match / list listeners & bugs |
| tinymux | Builder | object | @quota | any/wizard | Show or set building quota |
| tinymux | Builder | object | @reference <name>=<obj> | any | Named #-reference alias for a dbref (MUX-distinct) |
| tinymux | Admin | queue | @force <obj>=<cmd> | controls | Make object execute a command as itself |
| tinymux | Admin | queue | @switch <val>=<pat>,<cmd>,... | any | Branch command execution on pattern match |
| tinymux | Admin | queue | @dolist <list>=<cmd> | any | Run command once per list element (##/#@ tokens) |
| tinymux | Admin | queue | @wait <secs>[/<sem>]=<cmd> | any | Queue command after delay or on semaphore |
| tinymux | Admin | queue | @notify/@drain <obj>[=<n>] | controls | Signal/drain semaphore-waiting queue entries |
| tinymux | Admin | queue | @halt <obj> | controls | Halt queued commands for object |
| tinymux | Admin | queue | @ps [<obj>] | any | Show queued command entries |
| tinymux | Admin | queue | @kick / @restart | wizard | Force queue cycle / soft process restart |
| tinymux | Admin | queue | @trigger <obj>/<attr>[=args] | controls | Run an attribute as a command |
| tinymux | Admin | queue | @assert / @break <cond>=<cmd> | any | Abort or continue action list on condition |
| tinymux | Admin | queue | @if <cond>=<then>,<else> | any | Conditional command (argv form) |
| tinymux | Admin | queue | @include <obj>/<attr> | any | Inline-execute another attribute's actions |
| tinymux | Admin | queue | @program <obj>=<attr> | controls | Capture player input into an attribute (@quitprogram) |
| tinymux | Admin | admin | @function <name>=<obj>/<attr> | god | Register a global user-defined softcode function |
| tinymux | Admin | admin | @addcommand/@delcommand | god | Add/remove a global command hooked to an attr (MUX-distinct) |
| tinymux | Admin | admin | @hook <cmd>=<obj>/<attr> | god | Attach before/after/permit hook to a builtin cmd (MUX-distinct) |
| tinymux | Admin | admin | @icmd <player>=<cmds> | god | Enable/disable commands per-object (MUX-distinct) |
| tinymux | Admin | admin | @attribute / @flag / @power | god | Define/rename attributes, flags, powers |
| tinymux | Admin | admin | @cron / @crontab / @crondel | any | Schedule recurring commands cron-style (MUX-distinct) |
| tinymux | Admin | admin | @query <db>=<sql> | wizard | Run SQL against configured external DB |
| tinymux | Admin | admin | @lua <code> | any | Execute embedded Lua (MUX-distinct) |
| tinymux | Admin | admin | @toad/@newpassword/@boot/@pcreate | wizard | Destroy player / reset pw / disconnect / make player |
| tinymux | Admin | admin | @shutdown/@dump/@dbck/@restart | wizard | Server lifecycle, DB save & integrity |
| tinymux | Admin | admin | @wall / @motd / @admin / @config | wizard | Broadcast, message-of-day, runtime config |
| tinymux | Admin | comm | @emit/@nemit/@femit <msg> | location | Emit unattributed text to room |
| tinymux | Admin | comm | @pemit/@npemit <who>=<msg> | any | Emit text to specific player(s) |
| tinymux | Admin | comm | @oemit <who>=<msg> | location | Emit to room except named player |
| tinymux | Admin | comm | @fpose/@fsay/@fwd | controls | Force pose/say/forward as another object |
| tinymux | Player | mail | @mail <who>=<subj>/<msg> | any | Send/read/manage @mail (switches: read/list/etc.) |
| tinymux | Player | mail | @malias / @folder | any | Mail aliases and folder management |
| tinymux | Player | channel | addcom/delcom/comlist/allcom/clearcom | any | Comsys: join/leave/list channel aliases |
| tinymux | Player | channel | comtitle <alias>=<title> | any | Set per-channel title |
| tinymux | Admin | channel | @ccreate/@cdestroy/@cset/@clist | owner/wizard | Create/destroy/configure/list channels |
| tinymux | Admin | channel | @cemit/@cboot/@cchown/@cwho | owner | Emit to, boot from, reassign, list channel |
| tinymux | Softcode-fn | softcode | u(obj/attr,args) / ulocal / ulambda | any | Call attribute as function (ulocal preserves q-regs) |
| tinymux | Softcode-fn | softcode | get / xget / get_eval / eval / v(x) | controls attr | Fetch attribute value, optionally evaluated |
| tinymux | Softcode-fn | softcode | set / attrib_set(obj,attr,val) | controls | Set attribute from softcode |
| tinymux | Softcode-fn | softcode | default/edefault/udefault(attr,alt) | any | Attribute value with fallback (u-form calls) |
| tinymux | Softcode-fn | softcode | setq/setr/r(n)/listq/unsetq/letq | any | Read/write/scope q-registers (setr returns value) |
| tinymux | Softcode-fn | softcode | localize(expr) / objeval(obj,expr) | any | Evaluate with saved regs / as another object's perms |
| tinymux | Softcode-fn | softcode | switch/switchall/case/caseall | any | Pattern-branch evaluation |
| tinymux | Softcode-fn | softcode | if/ifelse/firstof/allof/@@(cmt) | any | Conditionals and null/comment |
| tinymux | Softcode-fn | softcode | iter/list/ilev/itext/inum | any | Loop over a list (##/itext nesting context) |
| tinymux | Softcode-fn | softcode | fold/foreach/map/filter/filterbool/munge | any | Higher-order list transforms |
| tinymux | Softcode-fn | softcode | while/step | any | Loop with condition / in chunks |
| tinymux | Softcode-fn | softcode | sandbox(obj/attr,...) | any | Evaluate under restricted permissions (MUX-distinct) |
| tinymux | Softcode-fn | softcode | trace / benchmark / astbench / rvbench | any/wizard | Debug/profile evaluation |
| tinymux | Softcode-fn | softcode | s/secure/escape/lit/subeval/asteval | any | Control (re)parsing & escaping of text |
| tinymux | Softcode-fn | softcode | lua(code) | any | Call embedded Lua from softcode (MUX-distinct) |
| tinymux | Softcode-fn | object | create/clone/destroy(obj) | controls | Create/clone/destroy object from softcode |
| tinymux | Softcode-fn | object | num/name/fullname/moniker/objid | any | Object dbref, name, unique objid |
| tinymux | Softcode-fn | object | owner/cowner/controls/isobjid/valid | any | Ownership & control checks |
| tinymux | Softcode-fn | object | loc/rloc/where/home/room/rooms | see | Object location, recursive loc, absolute room |
| tinymux | Softcode-fn | object | con/exit/next/lcon/lexits/children | see | Contents/exit-list iteration and traversal |
| tinymux | Softcode-fn | object | parent/lparent/name derivation | any | Parent chain queries |
| tinymux | Softcode-fn | object | locate/pmatch/pfind/lsearch/search | see | Match objects/players by name or criteria |
| tinymux | Softcode-fn | object | findable/nearby/lastcreate/entrances | any | Reachability, adjacency, recent creations |
| tinymux | Softcode-fn | object | link/tel/rloc/moniker (mutators) | controls | Softcode link/teleport helpers |
| tinymux | Softcode-fn | object | zone/inzone/zwho/zfun/zexits/zrooms/zthings/zchildren | any | Zone (ZMO) membership & delegated funcs |
| tinymux | Softcode-fn | list | lattr/lattrp/reglattr/nattr/attrcnt | see | List / regex-list / count attributes on object |
| tinymux | Softcode-fn | list | lattrcmds/lcmds/cmds | see | List $-command attributes on object (MUX-distinct) |
| tinymux | Softcode-fn | list | hasattr/hasattrp/objmem/wipe | controls | Attribute existence, memory, bulk clear |
| tinymux | Softcode-fn | info | flags/lflags/hasflag/andflags/orflags | any | Object flag queries |
| tinymux | Softcode-fn | info | type/hastype/hasquota/bittype/objmem | any | Object type & quota queries |
| tinymux | Softcode-fn | info | powers/haspower/hasflag | any | Power/permission queries |
| tinymux | Softcode-fn | info | visible/elock/lock/lockencode/lockdecode | see | Visibility and lock evaluation |
| tinymux | Softcode-fn | info | money/pack/unpack/baseconv | any | Money value and base/number conversions |
| tinymux | Softcode-fn | comm | emit/pemit/oemit/remit/cemit/pose/prompt | see | Emit text from softcode to room/player/channel |
| tinymux | Softcode-fn | comm | nsemit/nsoemit/nspemit/nsremit | wizard | No-spoof variants of emit functions |
| tinymux | Softcode-fn | comm | trigger(obj/attr,args) | controls | Fire an attribute as a command from softcode |
| tinymux | Softcode-fn | route | route(obj,cmd[,default]) | controls | Route/dispatch command by object's routing attr (MUX-distinct) |
| tinymux | Softcode-fn | info | verb(...) | controls | Trigger verb with actor/others/default messaging |
| tinymux | Softcode-fn | mail | mail/mailfrom/mailsubj/mailinfo/maillist | any | Read @mail metadata from softcode |
| tinymux | Softcode-fn | mail | mailcount/mailsize/mailstats/mailsend/mailreview | any | Mail counts, stats, send, review |
| tinymux | Softcode-fn | mail | malias/mailflags | any | Mail alias & flag queries |
| tinymux | Softcode-fn | channel | channels/chanobj/chaninfo/chanfind/cflags | any | Channel enumeration & metadata |
| tinymux | Softcode-fn | channel | chanuser(s)/cwho/cusers/cstatus/cbuffer/crecall | any | Channel membership & history |
| tinymux | Softcode-fn | channel | comalias/comtitle/cdesc/cowner/cmsgs/cmogrifier | any | Comsys alias/title/config lookups |
| tinymux | Softcode-fn | info | version/mudname/motd/config/stats/mtime | any | Server identity, config, uptime, DB stats |
| tinymux | Softcode-fn | info | lwho/lports/ports/who-style | any/wizard | Connected players/ports lists |
| tinymux | Softcode-fn | info | conn/idle/doing/host/siteinfo/poll/motd | any/wizard | Per-connection info & poll string |
| tinymux | Softcode-fn | info | conn{last,left,max,num,record,total}/playmem | any | Connection history & memory stats |
| tinymux | Softcode-fn | info | lplayers/nplayers/nthings/lrooms/lthings/lexits | any | Enumerate/count DB objects by type |
| tinymux | Softcode-fn | info | restarts/starttime/restarttime/startsecs/uptime | any | Server restart & start-time info |
| tinymux | Softcode-fn | info | textfile/dynhelp/terminfo/colordepth/gmcp | any/wizard | Help-file lookup, terminal caps, GMCP push |
| tinymux | Softcode-fn | math | add/sub/mul/div/fdiv/mod/floordiv/remainder/... | any | Core arithmetic (grouped; incl. i-integer variants) |
| tinymux | Softcode-fn | math | abs/sign/inc/dec/bound/round/trunc/ceil/floor/max/min | any | Scalar numeric helpers (grouped) |
| tinymux | Softcode-fn | math | sin/cos/tan/asin/acos/atan/atan2/exp/ln/log/sqrt/pi/e/power | any | Trig, log, exponent (grouped) |
| tinymux | Softcode-fn | math | band/bor/bxor/bnand/shl/shr/baseconv | any | Bitwise & base ops (grouped) |
| tinymux | Softcode-fn | math | eq/neq/gt/gte/lt/lte/and/or/not/xor/*bool/cand/cor | any | Comparison & boolean logic (grouped) |
| tinymux | Softcode-fn | math | mean/median/stddev/dist2d/dist3d/fmod | any | Statistics & geometry (grouped) |
| tinymux | Softcode-fn | math | vadd/vsub/vmul/vdot/vcross/vmag/vunit/vdim | any | Vector math (grouped) |
| tinymux | Softcode-fn | math | rand/lrand/die/pickrand/shuffle | any | Randomness & dice |
| tinymux | Softcode-fn | math | lmath/limath(op,list) | any | Apply arithmetic op across a list (MUX-distinct) |
| tinymux | Softcode-fn | math | roman/spellnum/digittime/isint/isnum/israt/isdbref/isobjid | any | Number formatting & type predicates |
| tinymux | Softcode-fn | string | strlen/strcat/cat/mid/left/right/first/rest/... | any | Core string slice/concat (grouped) |
| tinymux | Softcode-fn | string | ucstr/lcstr/capstr/caplist/trim/squish/space/repeat | any | Case, pad-trim, whitespace (grouped) |
| tinymux | Softcode-fn | string | ljust/rjust/center/cpad/lpad/rpad/columns/table/wrap | any | Alignment & column/table layout (grouped) |
| tinymux | Softcode-fn | string | edit/replace/strreplace/strinsert/strdelete/delete/insert | any | In-string edit/replace (grouped) |
| tinymux | Softcode-fn | string | pos/posn/lpos/wordpos/strmatch/match/matchall/member/after/before | any | Search/position within string/list (grouped) |
| tinymux | Softcode-fn | string | secure/escape/stripansi/stripaccents/accent/ansi/translate | any | ANSI/accent/escape handling (grouped) |
| tinymux | Softcode-fn | string | regmatch/regmatchi/regrab*/regedit*/reglattr* | any | Regex match/extract/edit (grouped) |
| tinymux | Softcode-fn | string | grab/graball/grep/grepi/regrep(i)/scramble/reverse/revwords | any | Grab/grep/scramble helpers (grouped) |
| tinymux | Softcode-fn | string | soundex/soundlike/strdistance/tr/chr/ord/art/subj/poss/aposs | any | Phonetic, char, pronoun helpers (grouped) |
| tinymux | Softcode-fn | list | words/vdim/wordstart/wordend/isword/elements/index/extract | any | Word/element extraction from list (grouped) |
| tinymux | Softcode-fn | list | sort/sortby/sortkey/strsort/shuffle/revwords | any | List sorting (grouped) |
| tinymux | Softcode-fn | list | ldelete/linsert/lreplace/ledit/lrand/lrest/last/itemize | any | List edit ops (grouped) |
| tinymux | Softcode-fn | list | setunion/setinter/setdiff/strunion/strinter/strdiff/unique/strunique | any | Set operations on lists (grouped) |
| tinymux | Softcode-fn | list | splice/merge/mix/zip/pack/unpack/remove/distribute/choose | any | List combine/split helpers (grouped) |
| tinymux | Softcode-fn | list | lnum/lreplace/wordpos/pickrand/table/columns | any | List generation & tabular output (grouped) |
| tinymux | Softcode-fn | time | time/secs/convsecs/convtime/timefmt/etimefmt/digittime | any | Time formatting & conversion (grouped) |
| tinymux | Softcode-fn | time | ctime/mtime/writetime/singletime/exptime/moon | any | Object timestamps, moon phase (grouped) |
| tinymux | Softcode-fn | info | json/json_query/json_mod/isjson | any | JSON build/query/modify (MUX-distinct) |
| tinymux | Softcode-fn | info | encrypt/decrypt/digest/sha1/hmac/crc32/crc32obj | any | Hash/crypto/checksum (grouped) |
| tinymux | Softcode-fn | info | encode64/decode64/url_escape/url_unescape | any | Encoding helpers |
| tinymux | Softcode-fn | info | die/error/beep/null/t/config/siteinfo | any | Misc control & info primitives |
| tinymux | Softcode-fn | info | sql/mapsql | wizard | Inline SQL query into softcode (build-time option) |
</content>
</invoke>
