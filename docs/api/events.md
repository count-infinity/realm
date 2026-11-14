# Propagation API

Quick reference for ``realm.core.propagation``. The concepts:
[Action Propagation](../architecture/events.md).

## Action

```python
# doctest: skip
Action(
    actor: GameObject | None,
    target: GameObject | None,
    action_type: str,           # "event:speech", "item:on_get", ...
    chain=None,                 # visit order; ROOM_TARGET_CHAIN for room-wide
    tool: GameObject | None = None,
    extra: dict = {},           # payload ("message", "amount", ...)
    tags: set[str] = set(),     # "scripted", "movement", ...
)

action.block(reason)                    # veto (check pass)
action.blocked / action.block_reason
action.add_message(audience, text, success_only=False)
action.add_modifier(value, reason)      # picked up by combat rolls
```

## Functions

```python
await propagate(action, deliver=True)   # run both passes (+ messages)
deliver_messages(action)                # deliver staged messages later
await gate_action(action, fail_msg=...) # check-pass-only convenience
get_world().engine                      # the running world's engine
feature.observer(async_fn)              # see every action (a feature)
world.observe(async_fn)                 # ... or for this world's life
```

## Canonical action builders

``realm.std.talk.verbs`` exports ``speech_action`` / ``pose_action`` (and
``do_say``, ``do_pose``, ...), and ``realm.std.items.verbs`` the manipulation
cores (``gate_item_action``, ``do_get``, ``do_drop``, ``do_give``,
``do_open``, ``do_close``) — use these instead of hand-building common
shapes.
