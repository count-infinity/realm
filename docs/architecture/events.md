# Action Propagation

REALM's single message pathway. Every game action — speech, movement,
getting an item, a sword blow — is an ``Action`` propagated through the
room in **two passes** (CoffeeMud-style):

1. **Check pass** — every visited object (and its behaviors) may
   inspect, modify, or ``block()`` the action. Locks are enforced here
   too. The pass always runs to completion, so observers see even
   blocked attempts.
2. **React pass** — objects accumulate audience messages, queue
   trailing actions, and mutate state in response.

```python
from realm.core.propagation import Action, ROOM_TARGET_CHAIN, propagate

action = Action(
    actor=player,
    target=room,
    action_type="event:speech",
    chain=ROOM_TARGET_CHAIN,
    extra={"message": "hello"},
)
action.add_message("actor", 'You say, "{speech}"', success_only=True)
action.add_message("room", '{actor} says, "{speech}"', success_only=True)
await propagate(action)
```

Messages address audiences (``actor`` / ``target`` / ``room``), render
**per looker** (perception applies — an unseen speaker narrates as
"Someone"), and ``success_only`` messages are suppressed when the
action is blocked.

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
  resolved once per recipient, transforms registered with
  ``register_speech_renderer`` can garble it for a listener who lacks the
  language, leak fragments of a whisper to a bystander, or slur it for a
  drunk speaker — see below.

Any new speech-family action should carry its body as ``{speech}`` rather
than interpolating it, for both reasons.

### Per-listener speech renderers

```python
from realm.core.propagation import register_speech_renderer

def garble(body, action, looker):
    if action.action_type != "event:speech":
        return body
    tongue = action.actor.db.get('speaking')
    if tongue and looker and tongue not in (looker.db.get('languages') or []):
        return f"<something in {tongue}>"
    return body

register_speech_renderer(garble)
```

Called once per recipient while their copy of the message is rendered, in
registration order, each seeing the previous one's output (a drunk speaker
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

Namespaced strings, not an enum: ``event:speech``, ``event:on_enter``,
``item:on_get``, ``combat:on_death``, ``event:payment``... The suffix
maps to softcode triggers — an object with an ``ON_ENTER`` attribute
runs it when something enters its room.

## Common patterns

```python
# Gate an action (locks + behaviors may veto), then act:
from realm.core.verbs import gate_item_action
action = await gate_item_action(actor, "item:on_get", target,
                                fail_msg="You can't.")
if action is not None:
    target.location = actor
    action.add_message("actor", "You pick up {target:a}.")
    deliver_messages(action)
```

The manipulation verb cores in ``realm/core/verbs.py`` are the
reference implementations.
