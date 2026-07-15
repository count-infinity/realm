# PennMUSH Command & Softcode Function Surface Catalog

| Codebase | Type | Group | Name | Scope | Description |
|----------|------|-------|------|-------|-------------|
| pennmush | OLC | building | @dig <room>[=<exits>] | builder | Create room, optionally open exits to/from |
| pennmush | OLC | building | @open <exit>[=<dest>] | builder | Open exit in current room to destination |
| pennmush | OLC | building | @create <object> | builder | Create a new thing object |
| pennmush | OLC | building | @clone <obj>[=<name>] | controls target | Duplicate an object with its attributes |
| pennmush | OLC | building | @link <obj>=<dest> | controls target | Set exit dest / object home / player home |
| pennmush | OLC | building | @unlink <exit> | controls target | Remove exit destination or room drop-to |
| pennmush | OLC | building | @parent <obj>=<parent> | controls target | Set attribute-inheritance parent |
| pennmush | OLC | building | @name <obj>=<name> | controls target | Rename object (and player aliases) |
| pennmush | Builder | object | @set <obj>=<flag/attr> | controls target | Set flags or attributes on object |
| pennmush | Builder | object | @lset <obj>/<attr>=<flag> | controls target | Set attribute flags (locked, no_command...) |
| pennmush | Builder | object | @lock <obj>[/<type>]=<key> | controls target | Set a boolean lock (basic/use/enter/...) |
| pennmush | Builder | object | @unlock/@ulock/@elock | controls target | Remove or manage locks of a type |
| pennmush | Builder | object | @atrlock <obj>/<attr> | controls target | Lock/unlock an attribute against edits |
| pennmush | Builder | object | @atrchown <obj>/<attr>=<who> | controls target | Change attribute owner |
| pennmush | Builder | object | @cpattr <o>/<a>=<o>/<a> | controls target | Copy attribute(s) between objects |
| pennmush | Builder | object | @mvattr <o>/<a>=<o>/<a> | controls target | Move (rename) attribute(s) |
| pennmush | Builder | object | @edit <obj>/<attr>=<old>,<new> | controls target | Search/replace within attribute text |
| pennmush | Builder | object | @wipe <obj>[/<pat>] | controls target | Delete matching attributes en masse |
| pennmush | Builder | object | @chown <obj>=<player> | controls target | Change object owner |
| pennmush | Builder | object | @chzone <obj>=<zone> | controls target | Set object's zone master |
| pennmush | Builder | object | @destroy/@recycle/@nuke <obj> | controls target | Destroy object (undestroy to restore) |
| pennmush | Builder | object | @undestroy <obj> | controls target | Cancel pending destruction |
| pennmush | Builder | object | @teleport <obj>=<dest> | controls target | Move object to a location |
| pennmush | Builder | object | @flag/@power/@attribute | wizard | Define/alter flags, powers, attribute perms |
| pennmush | Builder | object | @firstexit <exit-list> | controls target | Reorder exit to front of room's exit list |
| pennmush | Builder | object | @quota / @squota | builder | View/set object-creation quota |
| pennmush | Builder | info | @decompile <obj> | controls target | Emit commands to recreate object |
| pennmush | Builder | info | @find / @search | builder | Find objects by name/owner/type/attr |
| pennmush | Builder | info | @entrances <obj> | builder | List exits/links pointing at object |
| pennmush | Builder | info | @scan <obj> | any | Show which $-commands would match input |
| pennmush | Builder | info | @grep <obj>/<pat> | controls target | Search object's attributes (regex/wild) |
| pennmush | Builder | info | @sweep [here/inv] | any | List listening/puppet/connected objects |
| pennmush | Player | object | @describe/@idescribe <obj>=<text> | controls target | Set DESCRIBE attr (@desc alias of @set) |
| pennmush | Player | object | @succ/@fail/@osucc/@drop/@ex... | controls target | Set standard message/action attributes |
| pennmush | Admin | admin | @force <obj>=<cmd> | controls target | Make object execute command as itself |
| pennmush | Admin | queue | @switch <str>=<pat>,<act>,... | any | Branch: run action for first matching pattern |
| pennmush | Admin | queue | @select <str>=<pat>,<act>,... | any | Like @switch, non-regex first-match branch |
| pennmush | Admin | queue | @dolist <list>=<cmd> | any | Iterate command over list items (##/#@) |
| pennmush | Admin | queue | @wait <secs>/<pid>=<cmd> | any | Delay command; @wait until <time> |
| pennmush | Admin | queue | @trigger <obj>/<attr>=<args> | controls target | Queue an attribute as a command with args |
| pennmush | Admin | queue | @include <obj>/<attr> | any | Inline-run attr in current queue/registers |
| pennmush | Admin | queue | @break/@assert <cond>=<cmd> | any | Abort/continue action list on condition |
| pennmush | Admin | queue | @retry / @skip / @ifelse | any | Loop-restart / conditional queue control |
| pennmush | Admin | queue | @halt [<obj>] | controls target | Clear queued/waiting commands for object |
| pennmush | Admin | queue | @ps [all/summary] | any | List queued/semaphore/wait commands |
| pennmush | Admin | queue | @notify/@drain <obj>[=<n>] | controls target | Signal/flush semaphore queue on object |
| pennmush | Admin | admin | @function <name>=<obj>/<attr> | wizard | Define global user function (softcode) |
| pennmush | Admin | admin | @hook <cmd>=<obj>/<attr> | wizard | Attach pre/post hooks to a built-in command |
| pennmush | Admin | admin | @command <name> | wizard | Add/restrict/inspect a command definition |
| pennmush | Admin | admin | @program / @quitprogram | wizard | Route object's input to an attribute (prompt) |
| pennmush | Admin | admin | @boot/@kick/@newpassword | wizard | Disconnect player, force cycle, reset pass |
| pennmush | Admin | admin | @shutdown/@restart/@dump | wizard | Server lifecycle and DB save control |
| pennmush | Admin | admin | @sitelock / @disable / @enable | wizard | Ban sites; toggle commands/functions |
| pennmush | Admin | admin | @config [set] | wizard | View/change runtime config options |
| pennmush | Admin | admin | @sql <query> | wizard | Run raw SQL against configured database |
| pennmush | Admin | admin | @mapsql <obj>/<attr>=<query> | wizard | Run SQL, trigger attr per result row |
| pennmush | Admin | admin | @wall/@rwall/@wizwall | wizard | Broadcast to all / royalty / wizards |
| pennmush | Admin | comm | @emit <msg> | any | Emit text to room, unattributed |
| pennmush | Admin | comm | @pemit <obj>=<msg> | any | Send private message to object/player |
| pennmush | Admin | comm | @remit <room>=<msg> | any | Emit to all contents of a room |
| pennmush | Admin | comm | @oemit <obj>=<msg> | any | Emit to room except named object |
| pennmush | Admin | comm | @lemit <msg> | any | Emit to object's outermost location |
| pennmush | Admin | comm | @zemit <zone>=<msg> | any | Emit to all rooms in a zone |
| pennmush | Admin | comm | @nspemit/@nsemit/... | wizard | Nospoof-suppressed emit variants |
| pennmush | Admin | comm | @prompt <obj>=<msg> | any | Pemit without trailing newline (prompt) |
| pennmush | Admin | comm | @message <recip>=<attr>,<args> | any | Format+send localizable attr-based message |
| pennmush | Player | comm | say <msg> / " <msg> | any | Speak aloud to the room |
| pennmush | Player | comm | pose <msg> / : <msg> | any | Emote an action (Name does...) |
| pennmush | Player | comm | semipose / ; <msg> | any | Emote with no leading space |
| pennmush | Player | comm | whisper <obj>=<msg> | any | Private message to someone in same room |
| pennmush | Player | comm | page <player>=<msg> | any | Send remote page; supports lists/ports |
| pennmush | Player | comm | think <msg> | any | Evaluate/echo text only to yourself |
| pennmush | Player | channel | @chat/@channel/@cemit | any | Join, admin, and speak on channels |
| pennmush | Player | channel | addcom/delcom/comtitle/comlist | any | Channel alias management |
| pennmush | Player | mail | @mail [<msg>] | any | Send/read/manage internal @mail |
| pennmush | Player | mail | @malias | any | Manage mail alias lists |
| pennmush | Player | info | look [<obj>] | any | Examine room/object/attribute |
| pennmush | Player | info | examine <obj> | controls target | Full dump of flags/attrs/locks |
| pennmush | Player | info | inventory / score | any | List carried items / money |
| pennmush | Player | info | who / doing / session | any | Online player list and connection info |
| pennmush | Player | info | brief <obj> | any | Look without long descriptions |
| pennmush | Player | object | get/drop/give/enter/leave | any | Manipulate/move objects and self |
| pennmush | Player | object | goto/go/home/follow/desert | any | Movement and follow mechanics |
| pennmush | Player | object | use / buy / with | any | Trigger USE, economy, WITH-object actions |
| pennmush | Softcode-fn | softcode | u(obj/attr,args) | any | Call attr as user function, return result |
| pennmush | Softcode-fn | softcode | ulocal(...) | any | Like u() but preserves q-registers |
| pennmush | Softcode-fn | softcode | ulambda(<code>,args) | any | Call anonymous/inline code as function |
| pennmush | Softcode-fn | softcode | pfun(attr,args) | any | Call attr respecting caller permissions |
| pennmush | Softcode-fn | softcode | zfun/ufun(...) | any | Zone-master u(); generic user-fn call |
| pennmush | Softcode-fn | softcode | udefault(obj/attr,def,args) | any | u() with default if attr absent |
| pennmush | Softcode-fn | softcode | fn(name,args) | any | Call built-in even if overridden |
| pennmush | Softcode-fn | softcode | eval(obj,attr) / get_eval | controls target | Get attribute and evaluate its contents |
| pennmush | Softcode-fn | softcode | objeval(obj,code) | see_all | Evaluate code as if by another object |
| pennmush | Softcode-fn | softcode | localize(code) | any | Evaluate with saved/restored registers |
| pennmush | Softcode-fn | softcode | benchmark(code,n) | any | Time repeated evaluation of code |
| pennmush | Softcode-fn | list | iter(list,expr[,idelim,odelim]) | any | Map expr over list (##=item, #@=index) |
| pennmush | Softcode-fn | list | map(obj/attr,list[,delim]) | any | Apply user-fn to each list element |
| pennmush | Softcode-fn | list | filter(attr,list,...) / filterbool | any | Keep elements where fn returns true/1 |
| pennmush | Softcode-fn | list | fold(attr,list[,base]) | any | Left-fold/reduce list through a user-fn |
| pennmush | Softcode-fn | list | munge(attr,l1,l2,delim) | any | Permute l2 by fn's reordering of l1 |
| pennmush | Softcode-fn | list | mix(attr,l1,l2,...) | any | Apply fn across parallel lists elementwise |
| pennmush | Softcode-fn | list | step(attr,list,n,...) | any | Apply fn to list n elements at a time |
| pennmush | Softcode-fn | list | foreach(attr,string) | any | Apply fn to each character of a string |
| pennmush | Softcode-fn | list | sort/sortby/sortkey(list) | any | Sort list (typed / by user-fn / by key) |
| pennmush | Softcode-fn | list | setunion/setinter/setdiff/setsymdiff | any | Set operations on two lists |
| pennmush | Softcode-fn | list | itemize/elist/list | any | Human-readable "a, b, and c" listing |
| pennmush | Softcode-fn | list | match/matchall/grab/graball | any | Wildcard-find element(s) in a list |
| pennmush | Softcode-fn | list | regrab/regraball/reglmatch(all)(i) | any | Regex-find element(s) in a list |
| pennmush | Softcode-fn | list | namegrab/namegraball | any | Match list by object name |
| pennmush | Softcode-fn | list | fold/extract/elements/index/ldelete | any | Slice/index/delete positional list items |
| pennmush | Softcode-fn | list | lreplace/linsert/lset/splice/merge | any | Positional insert/replace/merge on lists |
| pennmush | Softcode-fn | list | shuffle/randword/randextract/unique | any | Randomize / dedupe list elements |
| pennmush | Softcode-fn | list | first/rest/last/revwords/flip | any | Head/tail/reverse word helpers |
| pennmush | Softcode-fn | list | words/wordpos/lnum/table | any | Count words; number lists; column tables |
| pennmush | Softcode-fn | softcode | switch(str,pat,act,...) / switchall | any | Function-form pattern branch (case alias) |
| pennmush | Softcode-fn | softcode | reswitch(all)(i)(str,re,act,...) | any | Regex-based switch |
| pennmush | Softcode-fn | softcode | cond/condall/ncond(pairs) | any | Evaluate first true condition's value |
| pennmush | Softcode-fn | softcode | if/ifelse(cond,then,else) | any | Boolean branch, lazy-evaluated |
| pennmush | Softcode-fn | softcode | firstof/allof/strfirstof/strallof | any | First non-false / all-true collector |
| pennmush | Softcode-fn | softcode | default/edefault/udefault | any | Fallback value if attr empty/missing |
| pennmush | Softcode-fn | softcode | setq/setr/r/letq/listq/unsetq | any | Set/read q-registers (0-9,a-z,named) |
| pennmush | Softcode-fn | softcode | ibreak/ilev/itext/inum/ if/stext/slev | any | Introspect iter()/switch() nesting state |
| pennmush | Softcode-fn | object | get(obj/attr) | controls target | Read attribute value (no eval) |
| pennmush | Softcode-fn | object | xget(obj,attr) | controls target | get() with separate obj/attr args |
| pennmush | Softcode-fn | object | set(obj,attr:val) | controls target | Set an attribute or flag |
| pennmush | Softcode-fn | object | attrib_set(obj/attr,val) | controls target | Set/clear attribute (clears if no val) |
| pennmush | Softcode-fn | object | lattr/xattr/regxattr(obj[,pat]) | controls target | List attribute names by wildcard/regex |
| pennmush | Softcode-fn | object | nattr/regnattr | controls target | Count matching attributes |
| pennmush | Softcode-fn | object | hasattr(p)(val)(obj/attr) | controls target | Test attribute existence/value |
| pennmush | Softcode-fn | object | grep/grepi/wildgrep/regrep(obj,pat,txt) | controls target | Search attribute contents |
| pennmush | Softcode-fn | object | scan(obj,cmd) | see_all | Which $-commands match a command string |
| pennmush | Softcode-fn | object | v(attr) / get_eval | any | Read+eval attr on self (%-substitution) |
| pennmush | Softcode-fn | object | edit(str,old,new) | any | String search/replace |
| pennmush | Softcode-fn | object | clone/create/dig/open/pcreate | builder | Object creation from softcode |
| pennmush | Softcode-fn | object | link/tel/set/name/lock(function forms) | controls target | Side-effecting build ops in softcode |
| pennmush | Softcode-fn | object | wipe(obj) | controls target | Delete attributes via softcode |
| pennmush | Softcode-fn | info | name/fullname/iname/accname/moniker | any | Object display names and variants |
| pennmush | Softcode-fn | info | num/objid/pmatch/locate | any | Resolve name/dbref to object reference |
| pennmush | Softcode-fn | info | loc/rloc/where/home/room/con/exit/next | any | Object location and container walking |
| pennmush | Softcode-fn | info | lcon/lexits/lplayers/lvcon/xcon(...) | any | List contents/exits (visible/typed) db-walk |
| pennmush | Softcode-fn | info | ncon/nexits/nplayers(...) | any | Count contents/exits db-walk variants |
| pennmush | Softcode-fn | info | children/parent/lparent/nchildren | any | Parent/child inheritance chain |
| pennmush | Softcode-fn | info | type/hastype/owner/money/quota | any | Object type/owner/economy metadata |
| pennmush | Softcode-fn | info | controls(a,b) | any | Does a control b? (core permission test) |
| pennmush | Softcode-fn | info | visible/nearby/findable/valid | any | Visibility, proximity, name-validity tests |
| pennmush | Softcode-fn | info | flags/lflags/hasflag/orflags/andflags | any | Read/test object flags |
| pennmush | Softcode-fn | info | powers/haspower/orlpowers/andlpowers | any | Read/test object powers |
| pennmush | Softcode-fn | info | lock/locks/elock/testlock/lockfilter | controls target | Read/evaluate/filter by lock expressions |
| pennmush | Softcode-fn | info | lockflags/lockowner/clock | controls target | Lock metadata |
| pennmush | Softcode-fn | info | zone/zwho/zfun | any | Zone membership and zone-master calls |
| pennmush | Softcode-fn | info | config/mudname/mudurl/version | any | Server identity and config values |
| pennmush | Softcode-fn | info | nextdbref/objmem/playermem/lstats | wizard | DB internals, memory, object stats |
| pennmush | Softcode-fn | info | followers/following/entrances | any | Follow relationships; inbound links |
| pennmush | Softcode-fn | info | lsearch/nlsearch/nsearch(class,...) | any | Search DB by owner/type/flag/eval |
| pennmush | Softcode-fn | string | ansi(codes,text) | any | Apply ANSI/color markup to text |
| pennmush | Softcode-fn | string | render(text,type) / tag/endtag/tagwrap | any | Emit Pueblo/HTML/markup for clients |
| pennmush | Softcode-fn | string | align/lalign(widths,cols) | any | Multi-column aligned text layout |
| pennmush | Softcode-fn | string | center/ljust/rjust/wrap/table | any | Pad, justify, wrap text |
| pennmush | Softcode-fn | string | strlen/strcat/mid/left/right/strinsert | any | Basic string length/slice/concat family |
| pennmush | Softcode-fn | string | before/after/strdelete/strreplace | any | Substring extract/delete/replace family |
| pennmush | Softcode-fn | string | ucstr/lcstr/capstr/space/repeat/trim/squish | any | Case, whitespace, repeat helpers |
| pennmush | Softcode-fn | string | escape/secure/decompose/lit | any | Neutralize special chars for safe eval |
| pennmush | Softcode-fn | string | strmatch/regmatch(i)/wildmatch | any | Wildcard/regex match with capture groups |
| pennmush | Softcode-fn | string | regedit(all)(i)(str,re,repl) | any | Regex search-and-replace |
| pennmush | Softcode-fn | string | edit/tr/scramble/reverse/merge | any | Character transform/replace helpers |
| pennmush | Softcode-fn | string | pos/lpos/member/comp/strmatch | any | Locate substring/element position |
| pennmush | Softcode-fn | string | accent/stripaccents/chr/ord/art/spellnum | any | Accents, char codes, articles, num words |
| pennmush | Softcode-fn | string | soundex/soundslike/suggest | any | Phonetic match / spelling suggestions |
| pennmush | Softcode-fn | string | encode64/decode64/urlencode/formdecode | any | Base64 / URL / form encoding |
| pennmush | Softcode-fn | math | add/sub/mul/div/fdiv/floordiv/modulo/... | any | Core arithmetic family (2..N args) |
| pennmush | Softcode-fn | math | max/min/bound/abs/sign/inc/dec/round/trunc | any | Scalar numeric helpers |
| pennmush | Softcode-fn | math | sqrt/power/log/ln/e/pi/sin/cos/tan/... | any | Transcendental / trig family |
| pennmush | Softcode-fn | math | and/or/not/xor/nand/nor/cand/cor/t | any | Boolean logic (cand/cor short-circuit) |
| pennmush | Softcode-fn | math | eq/neq/gt/gte/lt/lte/comp | any | Comparison family |
| pennmush | Softcode-fn | math | band/bor/bxor/bnand/bnot/shl/shr/baseconv | any | Bitwise ops and base conversion |
| pennmush | Softcode-fn | math | lmath(op,list) | any | Apply arithmetic op across a whole list |
| pennmush | Softcode-fn | math | mean/median/stddev/root/remainder/fraction | any | Statistics and number formatting |
| pennmush | Softcode-fn | math | rand/die(n,sides)/lnum | any | Random numbers and dice rolls |
| pennmush | Softcode-fn | math | isint/isnum/isdbref/isobjid/isword/isregexp | any | Type/format predicates |
| pennmush | Softcode-fn | vector | vadd/vsub/vmul/vdot/vcross | any | Vector arithmetic on space-delim lists |
| pennmush | Softcode-fn | vector | vmag/vunit/vdim/vmax/vmin | any | Vector magnitude, normalize, dimension |
| pennmush | Softcode-fn | vector | dist2d/dist3d | any | Euclidean distance between points |
| pennmush | Softcode-fn | vector | ctu(deg,rad,grad) | any | Convert angle units |
| pennmush | Softcode-fn | json | json(type,val...) | any | Construct JSON value of given type |
| pennmush | Softcode-fn | json | json_query(json,path...) | any | Query/extract/size/type from JSON |
| pennmush | Softcode-fn | json | json_map(attr,json) / json_mod | any | Map fn over JSON; modify JSON in place |
| pennmush | Softcode-fn | json | isjson(str) | any | Validate JSON text |
| pennmush | Softcode-fn | json | oob(...) / wsjson / wshtml | any | Out-of-band / websocket JSON+HTML output |
| pennmush | Softcode-fn | sql | sql(query[,delims]) | wizard | Run SQL, return rows as delimited list |
| pennmush | Softcode-fn | sql | mapsql(attr,query) | wizard | Run SQL, apply user-fn per result row |
| pennmush | Softcode-fn | sql | sqlescape(str) | wizard | Escape a string for safe SQL |
| pennmush | Softcode-fn | crypt | digest(algo,str) | any | Hash string (sha256, md5, ...) |
| pennmush | Softcode-fn | crypt | hmac(algo,key,str) | any | Keyed HMAC digest |
| pennmush | Softcode-fn | crypt | encrypt/decrypt(str,key) | any | Symmetric string cipher |
| pennmush | Softcode-fn | crypt | checkpass(player,pass) | wizard | Verify a player's password |
| pennmush | Softcode-fn | time | time/utctime/mtime/ctime/secs/msecs | any | Current/object timestamps |
| pennmush | Softcode-fn | time | convsecs/convtime/csecs/ctime | any | Convert between epoch and formatted time |
| pennmush | Softcode-fn | time | timefmt(fmt,secs) / etimefmt | any | strftime-style time formatting |
| pennmush | Softcode-fn | time | timestring/stringsecs/etime/timecalc | any | Duration formatting/parsing/arithmetic |
| pennmush | Softcode-fn | time | starttime/restarttime/uptime/restarts | any | Server timing info |
| pennmush | Softcode-fn | time | isdaylight/secscalc | any | DST check; second arithmetic |
| pennmush | Softcode-fn | info | lwho/mwho/nwho/xwho/zwho(id) | any | Online player dbref lists (filtered) |
| pennmush | Softcode-fn | info | conn/idle/doing/hidden/recv/sent | any | Per-connection state (idle, doing, bytes) |
| pennmush | Softcode-fn | info | ports/lports/host/ipaddr/ssl/terminfo | wizard | Descriptor/network info per player |
| pennmush | Softcode-fn | info | pidinfo/lpids/getpids | any | Queue process (PID) introspection |
| pennmush | Softcode-fn | info | player/pmatch/alias/fullalias/quota | any | Player lookup and metadata |
| pennmush | Softcode-fn | comm | emit/pemit/remit/oemit/lemit/zemit | any | Side-effecting emit functions |
| pennmush | Softcode-fn | comm | prompt/message/speak/cemit | any | Prompt, formatted, RP-speech, channel emit |
| pennmush | Softcode-fn | comm | ns*emit (nspemit,nsemit,...) | wizard | Nospoof-suppressed emit function forms |
| pennmush | Softcode-fn | channel | cwho/cflags/cinfo/cbuffer/cdesc/cowner | any | Channel roster and metadata |
| pennmush | Softcode-fn | channel | channels/clock/cstatus/ctitle/crecall | any | Channel membership, locks, recall buffer |
| pennmush | Softcode-fn | channel | cbufferadd/cmsgs/cusers/cmogrifier | controls target | Channel buffer/message admin |
| pennmush | Softcode-fn | mail | mail/maillist/mailfrom/mailsend | any | Read/list/send @mail from softcode |
| pennmush | Softcode-fn | mail | mailstats/mailstatus/mailsubject/mailtime | any | Mail metadata queries |
| pennmush | Softcode-fn | info | textfile/textentries/textsearch | any | Read/search server help/text files |
| pennmush | Softcode-fn | info | functions/commands/cmds/config/colors | any | Introspect available fns/cmds/config |
| pennmush | Softcode-fn | softcode | null(x) / @@(x) | any | Discard args, return empty (comments) |
| pennmush | Softcode-fn | info | connlog/connrecord/addrlog | wizard | Connection-history log queries |
