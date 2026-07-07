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
action.add_message("actor", 'You say, "hello"', success_only=True)
action.add_message("room", '{actor} says, "hello"', success_only=True)
await propagate(action)
```

Messages address audiences (``actor`` / ``target`` / ``room``), render
**per looker** (perception applies — an unseen speaker narrates as
"Someone"), and ``success_only`` messages are suppressed when the
action is blocked.

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
