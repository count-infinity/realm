# 193. GMCP / OOB data

> Checklist item 193 — [now] — *GMCP on telnet + websocket, oob() softcode*

**What you'll build:** a bridge console whose verbs push structured
out-of-band data — ship status and character vitals — straight to a
Mudlet-class client's HUD, with no visible text.

**Concepts:** GMCP (telnet option 201) and its websocket parity, the
engine's own emissions (`Room.Info`, `Char.Vitals`), and the `oob()`
softcode function for sending your own packages.

## How it works

Out-of-band data is a **side channel to the client**, parallel to the
text a player reads. On telnet, REALM negotiates GMCP (option 201) and
frames each message as `IAC SB GMCP <Package> <json> IAC SE`; the
websocket gateway sends the same package/payload pairs, so a browser
client and Mudlet see identical data (`tests/test_oob.py` exercises both
edges). A client that never negotiates the channel simply receives
nothing — every emission is a safe no-op.

The engine already pushes two packages on its own:

- **`Room.Info`** on every move — `{id, name, exits}` for the room you
  entered, so a client can keep a live map (see the movement pipeline).
- **`Char.Vitals`** each combat round — `{hp, max_hp, round}` for a
  gauge that tracks the fight.

Your softcode sends its own with **`oob(target, package, data)`**:
`target` is the player, `package` is a dotted name your client agreed to
(`Ship.Status`, `Char.Vitals`, anything), and `data` is a dict. Like
`pemit`, it is queued and delivered after the script, and it is a no-op
for a player whose client never asked for OOB — so you can push
unconditionally and never spam a plain telnet user.

Because it is just a function, *any* trigger can push: a console verb, an
`on_tick`, an `ON_DAMAGE` witness updating a vitals panel. The client
decides what to draw; the game just states the facts.

## Build it

A console fixed in the room. Give it some ship state to report, then a
`$scan` verb that pushes a `Ship.Status` package (and a one-line
confirmation the player *does* see), and a `$readout` verb that pushes
the enactor's vitals:

```text
@create bridge console
drop bridge console
@set bridge console/hull = 87
@set bridge console/shields = 62
@set bridge console/cmd_scan = $scan: oob(enactor, 'Ship.Status', {'hull': V('hull', 100), 'shields': V('shields', 100)}); pemit(enactor, 'Sensor sweep sent to your console HUD.')
@set bridge console/cmd_readout = $readout: oob(enactor, 'Char.Vitals', {'hp': get_attr(enactor, 'hp', 10), 'max_hp': get_attr(enactor, 'max_hp', 10)}); pemit(enactor, 'Vitals telemetry pushed.')
```

The dict values are ordinary function calls, evaluated when the verb
runs, so the numbers are always current. Reusing the engine's
`Char.Vitals` package name means a client that already draws the combat
gauge lights up for your readout too, for free.

## Try it

On a Mudlet-class client (with a GMCP handler registered for these
packages):

```text
> scan
Sensor sweep sent to your console HUD.
    ... client receives GMCP: Ship.Status {"hull": 87, "shields": 62}
> readout
Vitals telemetry pushed.
    ... client receives GMCP: Char.Vitals {"hp": 9, "max_hp": 12}
```

On a plain telnet client the confirmation lines still print and the OOB
frames are silently dropped — same build, no errors, no leaked JSON. Walk
between rooms and the client also sees the engine's own `Room.Info` on
each arrival.

## Going further

- **A vitals ticker:** attach `script_ticker` and push `Char.Vitals` from
  `on_tick` for every player in the room, so client gauges track HP
  outside combat too.
- **Custom map data:** emit a `Room.Players` package listing who is
  present from an `ON_ENTER`/`ON_LEAVE` witness, feeding a client-side
  roster panel.
- **Menu channels:** send a `Client.Menu` package your client turns into
  clickable buttons, then wire each button to a normal command — GMCP
  carries the UI, softcode handles the click.
- **Negotiation check:** clients announce support via `Core.Supports`;
  gate a rich readout on it and fall back to a text `sheet`
  ([190](190_score_screen.md)) for everyone else.
