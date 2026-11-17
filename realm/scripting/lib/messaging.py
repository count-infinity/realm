"""
Softcode functions: Messages, prompts, out-of-band data and custom events.

Each function is registered with ``@softfn``; one that takes the run's
``ScriptFrame`` as ``frame`` reads the executor, enactor, store and queue
from it. See ``realm/scripting/registry.py`` for the flags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.scripting.registry import softfn

if TYPE_CHECKING:
    from realm.core.objects import GameObject

# Keys act() refuses in a payload: the engine sets them itself.
_ACT_RESERVED_KEYS = {'message', 'remote_rooms'}

@softfn(takes_frame=False, group='Messaging & prompts', readonly=True)
def ansi(codes: str, text: str) -> str:
    """
    Penn-style color: ansi('rh', 'My thing') — lowercase letters =
    foreground (r g y b m c w x), 'h' brightens it, UPPERCASE =
    background, u = underline, i = inverse video. Returns
    |-markup + reset.

    Example: ansi('rh', 'DANGER')
    """
    from realm.core.markup import marker
    mk = marker()
    fg = None
    bg = None
    bright = False
    flags = ''
    for ch in str(codes):
        if ch in 'rgybmcwx':
            fg = ch
        elif ch in 'RGYBMCWX':
            bg = ch.lower()
        elif ch == 'h':
            bright = True
        elif ch == 'u':
            flags += mk + 'u'
        elif ch == 'i':
            flags += mk + 'v'   # Penn 'i' = inverse video
    markup = ''
    if fg:
        markup += mk + (fg.upper() if bright else fg)
    elif bright:
        markup += mk + 'h'
    if bg:
        markup += mk + '[' + bg
    return f"{markup}{flags}{text}{mk}n"

@softfn(takes_frame=False, group='Messaging & prompts', readonly=True)
def escape(text: str) -> str:
    """Escape color markup in player-provided text (|| literals).

    Example: say('They said: ' + escape(arg0))
    """
    from realm.core.markup import escape as _escape
    return _escape(str(text))

@softfn(group='Messaging & prompts')
def prompt(frame, target, text: str, callback: str,
           persistent: bool = False) -> bool:
    """
    Ask a player a question; their next line runs the ``callback``
    attribute (on the executor) with the answer as arg0 — a softcode
    wizard. Chain by prompting again inside the callback.
    ``persistent=True`` survives a reboot. Requires the executor to
    control the target's own object (self/owned/admin).

    Example: prompt(enactor, 'What is your name?', 'on_name')
    """
    who = frame.resolve(target)
    if who is None or not who.is_player:
        return False
    frame.command_queue.append(
        ('prompt', who, (str(text), str(callback),
                         frame.executor.id if frame.executor else None,
                         bool(persistent))))
    return True

@softfn(group='Messaging & prompts')
def pemit(frame, target: GameObject | str, message: str) -> None:
    """Send a private message to a target (delivered after the script),
    exactly as written (ROM's ``send_to_char``: a lowercase first letter
    stays lowercase).

    Example: pemit(enactor, 'A voice only you can hear...')
    """
    target_obj = frame.resolve(target)
    if target_obj is not None:
        frame.command_queue.append(('pemit', target_obj, str(message)))

@softfn(group='Messaging & prompts')
def remit(frame, room: GameObject | str, message: str) -> None:
    """Emit a message to everyone in a room (delivered after the script).
    A room broadcast is ROM's ``act()``: its first letter is capitalized.

    Example: remit(here, 'The ground trembles.')
    """
    room_obj = frame.resolve(room)
    if room_obj is not None:
        frame.command_queue.append(('remit', room_obj, str(message)))

@softfn(group='Messaging & prompts')
def oemit(frame, exclude: GameObject | str, message: str) -> None:
    """Emit to the executor's room, excluding one object. A room broadcast
    is ROM's ``act()``: its first letter is capitalized.

    Example: oemit(enactor, 'Bob vanishes in smoke.')
    """
    exclude_obj = frame.resolve(exclude)
    if exclude_obj is not None:
        frame.command_queue.append(('oemit', exclude_obj, str(message)))

@softfn(group='Firing your own events')
def act(frame, target: GameObject | str, message: str = "",
        targeting: str = "remote", action_type: str = "event:act",
        extra: dict | None = None,
        tags: list | set | tuple | None = None) -> bool:
    """
    Fire a PROPAGATED action that can reach BEYOND your own room —
    unlike pemit/remit (which just deliver text), this runs the
    two-pass engine, so behaviors can veto or react at both ends.

    ``targeting`` chooses the audience:
      - ``'remote'`` — the TARGET's room (a different room from yours):
        scry, remote cast. A ward in *your* room or the destination can
        block it, and occupants there witness/react.
      - ``'zone'`` — every room in the target's zone (an alarm).
      - ``'room'`` — the target's room, local but propagated.

    The message reaches the far room's occupants (the ``'remote'``
    audience). Reaching a destination is authority-gated by its
    ``reach`` lock (open by default, like teleport) — a room or zone can
    set ``lock_reach`` to lock out remote actions.

    Because ``ON_<EVENT>`` hooks match on the action type's suffix, an
    ``action_type`` you invent needs no registration: fire
    ``'event:toll'`` and any object with an ``on_toll`` attribute reacts.

    ``extra`` is the event's payload: each key becomes an
    ``adata(key)`` a reactor can read, and an ``on_check`` ward can
    rewrite it with ``set_adata``. The ``message`` is always present as
    ``adata('message')``; keys named ``message`` or ``remote_rooms``
    are reserved and ignored. ``tags`` are action tags a ward can key
    on with ``has_atag``.

    Note that one action object crosses every leg of a ``'zone'`` or
    ``'remote'`` send, so a ward that rewrites the payload in one room
    changes what the *later* rooms receive. That is the mechanism
    behind a containment bulkhead, and a surprise if you expected each
    room to be judged independently.

    Example:
        # scry — watch a distant room
        act(thing, 'A scrying eye blinks open.', targeting='remote')

        # a zone-wide alarm: the message reaches every room in the
        # zone, and each room's wards get the two-pass. The softcode
        # ON_<EVENT> hook fires in the actor's room only.
        act(intruder, 'Klaxons wail!', targeting='zone',
            action_type='event:alert')

        # a custom local event: objects with an on_toll hook answer
        act(me, 'A deep bell tolls.', targeting='room',
            action_type='event:toll')

        # a payload the reactors read and a ward can rewrite
        act(me, 'Coolant vents!', targeting='zone',
            action_type='event:breach',
            extra={'severity': 8}, tags=['hazard'])
    """
    obj = frame.resolve(target)
    if obj is None:
        return False
    payload = {}
    if isinstance(extra, dict):
        payload = {str(k): v for k, v in extra.items()
                   if str(k) not in _ACT_RESERVED_KEYS}
    frame.command_queue.append(
        ('act', obj, (str(message), str(targeting), str(action_type),
                      payload, [str(t) for t in (tags or [])])))
    return True

@softfn(group='Messaging & prompts')
def oob(frame, target: GameObject | str, package: str, data: dict) -> None:
    """
    Send structured out-of-band data (GMCP) to a player's client —
    custom UI panels from softcode. Delivered after the script,
    like pemit. No-op for clients without an OOB channel.

    Example: oob(enactor, 'Ship.Status', {'hull': 87})
    """
    target_obj = frame.resolve(target)
    if target_obj is not None and isinstance(data, dict):
        frame.command_queue.append(('oob', target_obj, (str(package), data)))
