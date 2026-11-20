# Action Propagation

REALM's single message pathway. Every game action — speech, movement,
getting an item, a sword blow — is an ``Action`` propagated through the
room in **two passes with the engine effect between them** (CoffeeMud-style
check/execute, completed into a before/apply/after trio — see
[Action phases](../design/action-phases.md)):

1. **Check pass** — every visited object (and its behaviors) may
   inspect, modify, or ``block()`` the action, seeing the world **before**
   the effect. Locks are enforced here too. The pass always runs to
   completion, so observers see even blocked attempts.
2. **Apply** — the action's engine effect (the tag flip, the credit
   transfer, the item move), passed by the caller as
   ``propagate(action, apply=...)``. Runs only if the action was not
   blocked; it may itself refuse (``action.block(reason)``), which reads
   exactly like a ward veto.
3. **React pass** — objects accumulate audience messages, queue trailing
   actions, and react, seeing the world **after** the effect. ``ON_<EVENT>``
   softcode fires here (via the engine observer) only for actions that
   actually applied.

The one rule every hook can rely on: **``on_check`` sees the world before,
``ON_<EVENT>`` sees the world after, and the veto is the only thing that
stops the middle.**

```python
from realm.core.propagation import Action, ROOM_TARGET_CHAIN, propagate
from realm.std.talk.actions import TalkAction

action = Action(
    actor=player,
    target=room,
    action_type=TalkAction.SPEECH,      # == "event:speech"
    chain=ROOM_TARGET_CHAIN,
    extra={"message": "hello"},
)
action.add_message("actor", 'You say, "{speech}"', success_only=True)
action.add_message("room", '{actor} says, "{speech}"', success_only=True)
await propagate(action)
```

### Action types

``action_type`` is a ``namespace:verb`` string (``"event:on_enter"``,
``"combat:on_damage"``, ``"item:on_get"``). The kernel's own vocabulary
(movement, looking, connection, failure, lifecycle) is
``realm.core.action_types.ActionType``; each feature that owns more keeps its
own enum next to it: ``TalkAction`` (``realm.std.talk.actions``),
``ItemAction``, ``CombatAction``, ``EconomyAction``, ``AbilityAction``. Each is
a ``StrEnum``, so each member *is* its string:
``ActionType.ON_ENTER == "event:on_enter"``, it hashes into string sets, and it
serialises as the plain string.

Engine code always routes through an enum, and so should yours when you
mean an engine or feature event. The reason is a bug class, not style: a behavior
decides whether to react by comparing ``action.action_type``, so a typo'd
literal (``"event:on_entre"``) never matches and the behavior **silently
stops firing** — no error, just a dead feature. ``ActionType.ON_ENTRE``
instead raises ``AttributeError`` the moment the module imports.

```python
from realm.core.action_types import ActionType

async def on_react(self, obj, action):
    if action.action_type != ActionType.ON_ENTER:   # typo-proof
        return
```

**An action type is declared once**, by the feature that owns it, with
everything that hangs off it (``realm/core/eventdefs.py``):

```python
feature.event(ItemAction.ON_GET, hook="GET", doc="this object is picked up",
              target_lock=("basic", "You can't pick up {name}."))
feature.event(TalkAction.SPEECH, doc="say", payload={"message": "what was said"},
              speech=True, listen=True, target_lock=("speech", "You can't speak here."))
```

The declaration gives the ``ON_<HOOK>`` softcode attribute, the line in the
reference and ``@events``, the ``adata()`` keys (the generated payload table;
``tests/test_payload_docs_match_engine.py`` checks them against what the
engine really sends), the lock enforced on the target or tool, whether
``{actor}`` is a voice (``voice_as``), and whether softcode ``^listen``
triggers overhear its ``extra["message"]`` (``listen``; a whisper is not). A world without the owning feature
has none of it: without ``items``, ``ON_GET`` is not a hook.

Undeclared types stay legal: ability domains minted at runtime
(``f"{domain}:{slug}"``) and builder-invented types fired from softcode
``act()`` (``'event:toll'`` fires ``ON_TOLL``) use the suffix as the hook.

Messages address audiences — ``actor``, ``target``, ``room``, ``remote``, or
one a feature registers (``@feature.audience("zone")``) — render **per
looker** (perception applies — an unseen speaker narrates as "Someone"), and
``success_only`` messages are suppressed when the action is blocked. A
message for an audience nobody registered logs a WARNING.

### Message tokens

``format_message`` substitutes, for each of ``actor`` / ``target`` /
``tool``: ``{actor}`` (bare name), ``{actor:a}`` (indefinite),
``{actor:the}`` (definite). Each is named via ``get_display_name(looker)``,
which is what makes rendering perception-aware.

``{speech}`` is the **spoken body** — the player's own words, taken from
``extra['message']`` (or ``extra['pose']``). It is deliberately resolved
**last**, after the participant tokens, and that ordering carries weight:

- **Player text is never token-substituted.** Bake the body into the
  template (``f'{{actor}} says, "{message}"'``) and a player typing
  ``say meet {actor}`` reads back as *"meet Alice"*. As a token it stays
  literal.
- **It is the seam for per-listener speech.** Because ``{speech}`` is
  resolved once per recipient, transforms declared with
  ``feature.speech_renderer`` can garble it for a listener who lacks the
  language, leak fragments of a whisper to a bystander, or slur it for a
  drunk speaker — see below.

Any new speech-family action should carry its body as ``{speech}`` rather
than interpolating it, for both reasons.

### Per-listener speech renderers

```python
@feature.speech_renderer
def garble(body, action, looker):
    if action.action_type != TalkAction.SPEECH:
        return body
    tongue = action.actor.db.get('speaking')
    if tongue and looker and tongue not in (looker.db.get('languages') or []):
        return f"<something in {tongue}>"
    return body
```

Called once per recipient while their copy of the message is rendered, in
feature order, each seeing the previous one's output (a drunk speaker
of a foreign tongue slurs *and* garbles). ``looker`` is None when nobody
in particular is addressed.

A renderer transforms only the **spoken words**, never the narration around
them — the room still reads "Alice says," in the game's own voice.

A renderer must not raise; one that does is logged and skipped, keeping the
last good body. That is the opposite of an ``on_check`` ward, which fails
*closed*, and the difference is the hook's job: a ward exists to **deny**,
so "it errored" must never read as "it allowed"; a renderer only rephrases,
so swallowing the sentence would be the worse failure.

### Voice-only disguise (`db.voice_as`)

An actor with a `voice_as` attribute is *attributed* by that name in
in-character speech — say, pose, whisper, shout, semipose — for every
listener but themselves. (Out-of-character `ooc` is deliberately exempt: it
is the *player* speaking, not the character, so it always shows the real
name — its line bakes `.name` rather than the `{actor}` token.)

```
Ada.db.voice_as = "a distorted voice"
Ada: say who goes there
  Bob hears:  a distorted voice says, "who goes there"
  Ada hears:  You say, "who goes there"
  Bob's `look` still lists:  Ada          # face unaffected
```

This is deliberately narrower than a disguise (which changes
`get_display_name` everywhere): `voice_as` touches only the `{actor}` of a
*speech* action, so a modulator can hide a voice while leaving the face
known, or a mask can hide the face — via a name resolver — while the voice
gives you away. The speaker always hears their own true attribution.

## Who sees an action

- **Behaviors** on the actor, target, and room contents get
  ``on_check`` / ``on_react`` calls.
- **Observers** registered on the engine see every action — the script
  engine (softcode ``^listen`` and ``ON_<EVENT>`` triggers), the
  stealth system, and hostile-combat auto-initiation are all observers.
- **Zone masters** witness events in their member rooms.

## Action types

Namespaced strings: ``event:speech``, ``event:on_enter``, ``item:on_get``,
``combat:on_death``, ``event:payment``... Each declared type names its
``ON_<HOOK>`` softcode attribute (an object with ``ON_ENTER`` runs it when
something enters its room); ``@events`` lists every hook in the world with
the feature that declares it.

## Common patterns

```python
# Gate an action (locks + behaviors may veto), then act:
from realm.std.items.verbs import gate_item_action
action = await gate_item_action(actor, "item:on_get", target,
                                fail_msg="You can't.")
if action is not None:
    target.location = actor
    action.add_message("actor", "You pick up {target:a}.")
    deliver_messages(action)
```

The manipulation verb cores in ``realm/std/items/verbs.py`` are the
reference implementations.

## Capitals: a game's choice, not the kernel's

The kernel sends a line exactly as written. The two paths that narrate
someone's doing to an audience, ``deliver_messages`` (every templated
message) and a room broadcast (``GameObject.msg_contents``, which softcode
``remit`` and ``oemit`` use), pass each line through the world's **line
formatters** (``feature.line_formatter``, ``realm.core.world.format_line``);
a world that declares none sends ``"{actor} arrives."`` naming "the
cityguard" as "the cityguard arrives.". ``obj.msg(text)`` to one object,
softcode ``pemit`` and a command's own output never pass through them.

ROM capitalizes the first letter of what ``act()`` sends and leaves
``send_to_char`` as written. That rule is the ``basics`` feature's
formatter, applied when ``CAPITALIZE_LINES`` is on (the Merc scaffold and
Midgaard write ``CAPITALIZE_LINES = True``): the first visible character,
colour codes stepped over, never every line (``realm.core.markup.capitalize``),
so "The cityguard arrives.". A feature that composes a sentence starting
with a name for one player ("the guildmaster teaches:", ``look``'s title
line, combat's "CRITICAL! the beastly fido hits you") runs that sentence
through ``format_line`` too, so a game gets capitals everywhere or nowhere.
