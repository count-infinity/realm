"""
The ``vitals`` feature.

Natural regeneration out of combat, and the positions that speed it:
resting and sleeping (MUD_PLAN step 2). See docs/guides/life-and-death.md.
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.vitals.positions import (
    asleep_deaf,
    asleep_interceptor,
    asleep_sight,
    cmd_rest,
    cmd_sleep,
    cmd_stand,
    position_gate,
    position_marker,
    position_multiplier,
    roused_observer,
)
from realm.std.vitals.regen import Vitals, regen_observer, regen_sweep

feature = Feature(
    'vitals',
    doc='Regeneration out of combat; resting and sleeping.',
)

feature.setting(
    "REGEN_INTERVAL", 15,
    "Seconds between regeneration ticks. Each tick a character out of combat "
    "regains the game system's `regen` amount of each pool below full.")
feature.setting("REST_REGEN", 2, "Regeneration multiplier while resting.")
feature.setting("SLEEP_REGEN", 4, "Regeneration multiplier while asleep.")

feature.command('rest', cmd_rest, category='general',
                help_text='Sit down and rest (recover faster)', usage='rest')
feature.command('sleep', cmd_sleep, category='general',
                help_text='Go to sleep (recover fastest)', usage='sleep')
feature.command('stand', cmd_stand, aliases=['wake'], category='general',
                help_text='Stand up, or wake up', usage='stand')

feature.observer(regen_observer)
feature.observer(roused_observer)
feature.reaper(regen_sweep)
feature.traversal_gate(position_gate, reason="position")
feature.input_interceptor(asleep_interceptor, order=10)
feature.sight_rule(asleep_sight)
feature.deaf_rule(asleep_deaf)
feature.marker(position_marker)


@feature.on_install
def _offer_vitals(world) -> None:
    """``world.services["vitals"]``: the recovering set, one tick, and the
    multipliers other features append to."""
    service = Vitals(world)
    service.multipliers.append(position_multiplier)
    world.services["vitals"] = service


@feature.on_boot
async def _seed(world) -> None:
    """Characters saved below full start recovering at boot."""
    world.services["vitals"].seed()
