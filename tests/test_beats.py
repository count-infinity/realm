"""
Beats — the game turn-clock (see docs/design/time-and-beats.md).

A ``BeatBehavior`` is advanced by ``deliver_beat(obj)``: once per source-beat,
scaled by the creature's ``db.beat_multiplier`` (haste 2.0, slow 0.5, a
Time-Lord bubble 0.25) with fractional carry. The ambient driver skips
combatants (double-tick guard) since their encounter drives them instead.
"""

from __future__ import annotations

import pytest

from realm.core.beats import (
    BeatBehavior,
    ambient_beat_targets,
    deliver_beat,
    has_beat_behavior,
)
from realm.core.objects import GameObject


class CountingBeat(BeatBehavior):
    """Counts experienced beats into ``db.beats_felt``."""

    behavior_id = "counting_beat"

    async def on_beat(self, obj: GameObject) -> None:
        obj.db.set("beats_felt", int(obj.db.get("beats_felt") or 0) + 1)


def _counter(obj: GameObject) -> int:
    return int(obj.db.get("beats_felt") or 0)


@pytest.mark.asyncio
class TestDeliverBeat:

    async def test_one_beat_per_source_beat_by_default(self):
        obj = GameObject("mob")
        obj.add_behavior(CountingBeat())
        for _ in range(3):
            await deliver_beat(obj)
        assert _counter(obj) == 3

    async def test_no_beat_behaviors_is_a_noop(self):
        obj = GameObject("rock")
        await deliver_beat(obj)          # must not raise
        assert not has_beat_behavior(obj)

    async def test_has_beat_behavior(self):
        plain = GameObject("plain")
        beaty = GameObject("beaty")
        beaty.add_behavior(CountingBeat())
        assert has_beat_behavior(beaty)
        assert not has_beat_behavior(plain)


@pytest.mark.asyncio
class TestBeatMultiplier:

    async def test_haste_doubles_beats(self):
        obj = GameObject("sprinter")
        obj.db.beat_multiplier = 2.0
        obj.add_behavior(CountingBeat())
        await deliver_beat(obj)
        assert _counter(obj) == 2          # two experienced beats per source

    async def test_slow_halves_with_fractional_carry(self):
        obj = GameObject("sludge")
        obj.db.beat_multiplier = 0.5
        obj.add_behavior(CountingBeat())
        # 0.5 accumulates: source-beats land as 0,1,0,1 -> 2 felt over 4.
        felt_pattern = []
        for _ in range(4):
            before = _counter(obj)
            await deliver_beat(obj)
            felt_pattern.append(_counter(obj) - before)
        assert felt_pattern == [0, 1, 0, 1]
        assert _counter(obj) == 2

    async def test_time_lord_quarter_speed(self):
        obj = GameObject("victim")
        obj.db.beat_multiplier = 0.25     # slow-time bubble
        obj.add_behavior(CountingBeat())
        for _ in range(4):
            await deliver_beat(obj)
        assert _counter(obj) == 1          # one felt beat every 4 source-beats

    async def test_fractional_one_and_a_half(self):
        obj = GameObject("blur")
        obj.db.beat_multiplier = 1.5
        obj.add_behavior(CountingBeat())
        pattern = []
        for _ in range(4):
            before = _counter(obj)
            await deliver_beat(obj)
            pattern.append(_counter(obj) - before)
        assert pattern == [1, 2, 1, 2]     # 1.5 carries: 1,2,1,2


@pytest.mark.asyncio
class TestBulletTime:
    """Slowing a creature dilates ALL its beat-based effects together — the
    poison slows exactly as the fighter does."""

    async def test_effects_dilate_uniformly_under_slow(self):
        from realm.behaviors import DamageOverTimeBehavior

        fast = GameObject("fast", tags=["creature"])
        fast.db.hp = 100
        fast.add_behavior(DamageOverTimeBehavior(kind="venom", damage=1,
                                                 interval=1, duration=0))
        slow = GameObject("slow", tags=["creature"])
        slow.db.hp = 100
        slow.db.beat_multiplier = 0.25    # bullet-time on this one
        slow.add_behavior(DamageOverTimeBehavior(kind="venom", damage=1,
                                                 interval=1, duration=0,
                                                 jitter=False))
        for _ in range(4):
            await deliver_beat(fast)
            await deliver_beat(slow)
        # Same 4 source-beats: the fast one bled 4, the slowed one only 1.
        assert int(fast.db.get("hp")) == 96
        assert int(slow.db.get("hp")) == 99


@pytest.mark.asyncio
class TestMultiplierEdges:
    """Audit regressions: expiry under haste, full stop, and DoS clamp."""

    async def test_haste_does_not_resurrect_an_expiring_effect(self):
        # Nominal duration 10, but only 1 beat of it remaining, on a hasted
        # (x2) creature. One source-beat = two experienced beats: the effect
        # expires on beat 1 (deleting its 'left' counter). A stale snapshot
        # would call it AGAIN on beat 2 — reading left=None, re-initializing to
        # the full duration (9 left), re-arming AND pulsing damage. The fresh
        # re-read must skip the already-detached effect.
        from realm.behaviors import DamageOverTimeBehavior

        mob = GameObject("mook", tags=["creature"])
        mob.db.hp = 100
        mob.db.beat_multiplier = 2.0
        effect = DamageOverTimeBehavior(kind="venom", damage=5, interval=1,
                                        duration=10, jitter=False)
        mob.add_behavior(effect)
        mob.db.effect_venom_left = 1                   # one beat from expiry

        await deliver_beat(mob)

        assert effect not in mob.get_behaviors()      # expired, gone
        assert not mob.has_tag("venom")
        assert mob.db.get("effect_venom_left") is None   # not re-armed to 9
        assert int(mob.db.get("hp")) == 100           # no resurrected pulse

    async def test_zero_multiplier_freezes(self):
        obj = GameObject("frozen")
        obj.db.beat_multiplier = 0.0                  # stasis, not 1.0
        obj.add_behavior(CountingBeat())
        for _ in range(5):
            await deliver_beat(obj)
        assert _counter(obj) == 0                     # experiences no beats

    async def test_absurd_multiplier_is_clamped(self):
        from realm.core.beats import MAX_BEAT_MULTIPLIER

        obj = GameObject("overclocked")
        obj.db.beat_multiplier = 1e12                 # softcode DoS attempt
        obj.add_behavior(CountingBeat())
        await deliver_beat(obj)
        # Bounded — not a trillion synchronous on_beat calls.
        assert 0 < _counter(obj) <= MAX_BEAT_MULTIPLIER

    async def test_stale_carry_cleared_when_multiplier_returns_to_one(self):
        obj = GameObject("shifter")
        obj.add_behavior(CountingBeat())
        obj.db.beat_multiplier = 0.5
        await deliver_beat(obj)                       # carry 0.5, 0 beats
        assert obj.db.get("beat_acc")
        obj.db.beat_multiplier = 1.0                  # haste lapses
        await deliver_beat(obj)
        assert not obj.db.get("beat_acc")             # carry cleared, no early beat


@pytest.mark.asyncio
class TestDoubleTickGuard:
    """The ambient driver must skip objects an encounter already drives."""

    async def test_ambient_targets_exclude_combatants(self):
        out = GameObject("wanderer")
        out.add_behavior(CountingBeat())

        fighting = GameObject("duelist", tags=["in_combat"])
        fighting.add_behavior(CountingBeat())

        inert = GameObject("statue")            # no beat behavior

        targets = ambient_beat_targets([out, fighting, inert])
        assert out in targets
        assert fighting not in targets          # driven by its encounter
        assert inert not in targets             # nothing to advance

    async def test_reboot_scrubs_stale_in_combat_tag(self):
        # Encounters don't survive a reboot but the in_combat tag persists.
        # Without a load-time scrub, a mid-fight-saved creature reloads tagged
        # with no encounter — the ambient driver skips it forever and its beat
        # effects freeze. The scrub must clear the tag so it rejoins the beat.
        from realm.persistence.manager import (
            PersistenceManager,
            set_active_manager,
        )
        from realm.server.game import GameServer

        pm = PersistenceManager(":memory:")
        await pm.initialize()
        set_active_manager(pm)
        try:
            mob = GameObject(name="Brawler", tags=["creature", "in_combat"])
            mob.add_behavior(CountingBeat())        # a beat effect (would freeze)
            mob.db.combat_queued = "attack goblin"
            await pm.save(mob)
            assert mob not in ambient_beat_targets([mob])   # skipped while tagged

            # __new__ skips __init__: the scrub touches only .persistence.
            server = GameServer.__new__(GameServer)
            server.persistence = pm
            await server._scrub_stale_combat_state()

            assert not mob.has_tag("in_combat")
            assert mob.db.get("combat_queued") is None
            assert mob in ambient_beat_targets([mob])   # rejoins the ambient beat
        finally:
            set_active_manager(None)
            await pm.close()


class TestHeartbeatDefault:

    def test_settings_default_heartbeat_is_fast(self):
        from realm.config.loader import Settings
        assert Settings().tick_interval == pytest.approx(0.1)

    def test_settings_world_beat_and_reap_interval(self):
        from realm.config.loader import Settings
        s = Settings()
        assert s.world_beat == pytest.approx(4.0)
        assert s.reap_interval == pytest.approx(5.0)
