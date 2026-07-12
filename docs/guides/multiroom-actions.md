# How-To: Multiroom Actions (scry, remote cast, zone alarm)

Most actions happen in one room. Some need to reach *another* — a scrying
spell that peers into a distant vault, a remote curse, a wing-wide alarm.
`act()` fires a **propagated** action that travels beyond the actor's room
while still riding the two-pass engine, so wards can veto and occupants can
react at both ends. (Contrast `pemit`/`remit`, which just *deliver text* —
no check, no reaction.)

```text
act(target, message, targeting='remote')
```

`targeting` picks the audience — the **targeting vocabulary**:

| `targeting` | reaches | use |
|---|---|---|
| `remote` | the **target's** room + its occupants | scry, remote cast |
| `zone` | every room sharing the target's `zone:` tag | a wing-wide alarm |
| `room` | the target's room, locally | a propagated local effect |

## Scry example

An orb in a distant vault; a mage in their study casts:

```text
@set orb/cmd_scry = $scry:act(me, 'A scrying eye blinks open here.', targeting='remote')
```

When a player runs `scry`, occupants of the **orb's** room see the eye —
the mage never leaves the study; only the action travels.

## Permission: the `reach` lock

Reaching into a room is **authority-gated**, like teleport — not left to
chance. Each destination is checked against its `reach` lock, which is
*open by default* but a room (or every room in a zone) can close:

```text
@lock vault/reach = caller.has_tag('seer')   # only seers may scry in
@lock vault/reach = False                     # nothing reaches in
```

A denied room is dropped entirely — the action never touches it. This is
the safe-by-default gate; the ward below is defense-in-depth on top.

## The two-pass still applies — at both ends

This is the point of `act()` over raw messaging: the action runs the
check pass in the **caster's** room *and* the **destination**, so a ward
in either can veto it. A `NO_MAGIC` behavior is just a room behavior that
blocks in its check pass:

```python
class NoMagicWard(Behavior):
    async def on_check(self, obj, action):
        if action.has_tag("magic"):
            action.block("The air here smothers magic.")
```

Attach it to the caster's room and the scry never leaves; attach it to the
vault and the scry is smothered on arrival. Tag your action `magic`
(`action_type='event:scry'` or add the tag) so wards can recognize it.
Occupants only witness the action if it survives both check passes.

## Zone alarm

```text
@set klaxon/on_intrusion = act(me, 'INTRUDER ALERT', targeting='zone', action_type='event:alarm')
```

Fires to every room carrying the same `zone:<name>` tag as the klaxon's
room — the whole wing hears it at once. The origin room's wards still get
a veto before it broadcasts.

## Under the hood

`act()` builds a propagation chain from the [targeting
vocabulary](../design/rules-kernel.md) — a `RemoteStep` over the origin
room (for local wards) and another over the destination room(s) plus their
occupants — and adds a `'remote'` message audience delivered there. It's
the kernel's abstract mechanism; `act()` is its softcode surface.
