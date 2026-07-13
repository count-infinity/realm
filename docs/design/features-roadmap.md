# Features Roadmap — "The Realm of the Possible"

A running ledger of richer game features we've surveyed against REALM's
architecture — what other MU*s do (CoffeeMud, PennMUSH, Evennia) and
whether REALM could accommodate it. The recurring finding: because REALM is
a data-driven microkernel (the Python core is abstract mechanics; the game
is data + softcode), most "features" are **already expressible today** as
softcode + tags + behaviors, and only a few need a small net-new *kernel*
primitive. This table is where we track that split so ideas aren't lost.

Legend: **Softcode today** = buildable now, no core change · **Small kernel
bit** = needs one narrow primitive, then softcode · **Shipped** = built.

| Feature | Verdict | How / what's missing |
|---|---|---|
| **Instanced areas** (per-PC private copies — dungeons, puzzles) | ✅ **Shipped** (Stage 1) | `realm/core/instances.py` over `import_objects`; `ephemeral` transient flag; `enter_instance()` softcode; idle reaper. See [Ephemeral Rooms](ephemeral-rooms.md). |
| **Wilderness** (procgen coordinate cells too vast to hand-build) | 🔶 Small kernel bit | Same materialize-on-demand primitive as instances, keyed by `(x,y)` instead of PC. Needs kernel bit #3: **formula-resolved exit destinations** (an exit that get-or-creates the neighbor cell at traverse time). Then a map-provider softcode lib supplies `name/desc/terrain` per coordinate. |
| **Mounts / rideable creatures** | 🟢 Softcode today | A mount is an object you `enter` (containment) that moves through exits carrying its riders; the follow/party system already cascades occupants. Movement + `on_enter`/`on_move` softcode covers reins, mounting locks, encumbrance. |
| **Vehicles** (cars, boats — room-graph style) | 🟢 Softcode today | A vehicle is a container-room you board; "driving" = the vehicle object traversing exits (softcode picks the exit), occupants ride along. A `see-outside` view is a per-viewer `[[...]]` description reading the vehicle's current room. Continuous free-flight is the separate spatial primitive below. |
| **"See outside" from inside an object** (PennMUSH `TRANSPARENT`) | 🔶 Small kernel bit | Today perception is room-scoped. A transparent container that relays its *parent room's* look/speech to occupants is a small **perception-relay** hook (opt-in tag), reusing the two-pass propagation. Deferred. |
| **Flying spaceships / free-flight space** (continuous 3D) | 🔶 Kernel primitive (larger) | Discrete cells are just rooms (use wilderness). *Continuous* free-flight (arbitrary x/y/z, ranges, vectors) needs a **spatial sidecar**: coordinates + neighbor/range queries beside the room graph. Only build when a game genuinely needs continuous space; space *combat* on a room graph works today via the dice primitives. |
| **Races / species & mixing races** (CoffeeMud) | 🟢 Softcode today | A race is a `class_def`/data pack of attribute modifiers, skill grants, and tags applied at chargen; "mixed race" = composing two defs (average/blend modifiers in softcode). No kernel change — it's the same data-driven rules mechanism as classes/skills. |
| **Having children / lineage** (CoffeeMud) | 🟢 Softcode today | A child is a created object with `parent`/lineage attrs and a growth `on_tick` behavior; inheritance of traits is softcode reading both parents' data. Purely data + behaviors. |
| **Currency & exchange rates** (multiple currencies) | 🟢 Softcode today | Credits already exist; multiple currencies are attrs + a conversion table in a data pack; exchange = softcode arithmetic in the shop/economy layer. The game system owns currency, not the kernel. |
| **Effects / buffs / debuffs with duration** | 🟢 Softcode today | Condition effects + `apply_effect`/`remove_effect` + `on_tick` decay already exist; the two-pass check/react model *is* the effect-interception system (an effect's `on_check` can veto/modify). |

## Principles this table keeps honest

- **Default to softcode.** If a feature is rules/content, it belongs in a
  data pack or softcode, not the Python core. The bar for a kernel change is
  high: it must be something *no* amount of softcode can express (a new
  persistence mode, a new propagation reach, a new coordinate space).
- **One primitive, many features.** Instances and wilderness are the same
  materialize-on-demand mechanism; mounts and vehicles are the same
  board-a-container-that-moves mechanism. Look for the shared primitive
  before adding a feature-specific subsystem.
- **The spatial primitive is reserved.** Discrete space = rooms. Only
  *continuous* free-flight justifies coordinates-beside-rooms, and it stays
  unbuilt until a game needs it.
