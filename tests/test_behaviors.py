"""Tests for the Behavior system."""

import pytest

from realm.core.behaviors import Behavior, BehaviorRegistry
from realm.core.objects import GameObject


class SimpleBehavior(Behavior):
    """Simple test behavior."""

    behavior_id = "simple"


class TickingBehavior(Behavior):
    """Behavior that ticks."""

    behavior_id = "ticking"

    def __init__(self, **params):
        super().__init__(**params)
        self.tick_count = 0

    @property
    def should_tick(self) -> bool:
        return True

    @property
    def tick_interval(self) -> float:
        return self.get_param('interval', 1.0)

    async def tick(self, obj, delta):
        self.tick_count += 1


class CountingBehavior(Behavior):
    """Behavior that counts on_check / on_react calls."""

    behavior_id = "counting"

    def __init__(self, **params):
        super().__init__(**params)
        self.check_count = 0
        self.react_count = 0

    async def on_check(self, obj, action):
        self.check_count += 1

    async def on_react(self, obj, action):
        self.react_count += 1


class TestBehavior:
    """Test suite for Behavior base class."""

    def test_behavior_creation(self):
        b = SimpleBehavior(damage=10, speed=5)
        assert b.get_param('damage') == 10
        assert b.get_param('speed') == 5
        assert b.get_param('missing') is None
        assert b.get_param('missing', 'default') == 'default'

    def test_owner_initially_none(self):
        b = SimpleBehavior()
        assert b.owner is None

    def test_attach_sets_owner(self):
        obj = GameObject("test")
        b = SimpleBehavior()
        b.attach(obj)
        assert b.owner == obj

    def test_detach_clears_owner(self):
        obj = GameObject("test")
        b = SimpleBehavior()
        b.attach(obj)
        b.detach(obj)
        assert b.owner is None

    def test_default_should_tick_false(self):
        b = SimpleBehavior()
        assert b.should_tick is False

    def test_default_tick_interval(self):
        # 0 = tick on every server pulse; behaviors override for slower cadence
        b = SimpleBehavior()
        from realm.core.behaviors import WORLD_TICK
        assert b.tick_interval == WORLD_TICK

    def test_ticking_behavior(self):
        b = TickingBehavior(interval=0.5)
        assert b.should_tick is True
        assert b.tick_interval == 0.5

    @pytest.mark.asyncio
    async def test_tick_called(self):
        b = TickingBehavior()
        obj = GameObject("test")
        await b.tick(obj, 0.1)
        assert b.tick_count == 1

    def test_to_dict(self):
        b = SimpleBehavior(damage=10, name="test")
        data = b.to_dict()
        assert data['behavior_id'] == 'simple'
        assert data['params']['damage'] == 10
        assert data['params']['name'] == 'test'

    def test_from_dict(self):
        data = {'behavior_id': 'simple', 'params': {'damage': 10}}
        b = SimpleBehavior.from_dict(data)
        assert b.get_param('damage') == 10

    def test_repr(self):
        obj = GameObject("test")
        b = SimpleBehavior()
        obj.add_behavior(b)
        repr_str = repr(b)
        assert 'SimpleBehavior' in repr_str
        assert 'test' in repr_str


class TestBehaviorRegistry:
    """Test suite for BehaviorRegistry."""

    def setup_method(self):
        # Snapshot the global registry — clearing it destructively would
        # unregister every import-time behavior for the rest of the session.
        self._saved = dict(BehaviorRegistry._behaviors)
        BehaviorRegistry._behaviors.clear()

    def teardown_method(self):
        BehaviorRegistry._behaviors.clear()
        BehaviorRegistry._behaviors.update(self._saved)

    def test_register_behavior(self):
        BehaviorRegistry.register(SimpleBehavior)
        assert 'simple' in BehaviorRegistry.list_all()

    def test_register_as_decorator(self):
        @BehaviorRegistry.register
        class DecoratedBehavior(Behavior):
            behavior_id = "decorated"

        assert 'decorated' in BehaviorRegistry.list_all()

    def test_get_behavior(self):
        BehaviorRegistry.register(SimpleBehavior)
        cls = BehaviorRegistry.get('simple')
        assert cls == SimpleBehavior

    def test_get_nonexistent(self):
        assert BehaviorRegistry.get('nonexistent') is None

    def test_create_behavior(self):
        BehaviorRegistry.register(SimpleBehavior)
        b = BehaviorRegistry.create('simple', damage=10)
        assert isinstance(b, SimpleBehavior)
        assert b.get_param('damage') == 10

    def test_create_nonexistent(self):
        assert BehaviorRegistry.create('nonexistent') is None

    def test_from_dict(self):
        BehaviorRegistry.register(SimpleBehavior)
        data = {'behavior_id': 'simple', 'params': {'damage': 10}}
        b = BehaviorRegistry.from_dict(data)
        assert isinstance(b, SimpleBehavior)
        assert b.get_param('damage') == 10

    def test_from_dict_missing_id(self):
        assert BehaviorRegistry.from_dict({}) is None

    def test_from_dict_unknown_id_falls_back_to_scripted(self):
        # An id with no Python class is assumed to name a behavior_def
        # (see realm.behaviors.scripted): the load path must hand back a
        # ScriptedBehavior rather than dropping the saved behavior, even
        # when the def object has not loaded yet.
        from realm.behaviors.scripted import ScriptedBehavior
        data = {'behavior_id': 'unknown', 'params': {}}
        restored = BehaviorRegistry.from_dict(data)
        assert isinstance(restored, ScriptedBehavior)
        assert restored.behavior_id == 'unknown'

    def test_describe_falls_back_to_docstring_first_line(self):
        class Documented(Behavior):
            """Does one thing well.

            Longer prose a builder never sees.
            """
            behavior_id = "documented"

        assert Documented.describe()['blurb'] == "Does one thing well."

    def test_describe_explicit_blurb_wins(self):
        class Labeled(Behavior):
            """Docstring line that should lose."""
            behavior_id = "labeled"
            blurb = "the declared one-liner"

        assert Labeled.describe()['blurb'] == "the declared one-liner"

    def test_describe_merges_param_specs_down_the_mro(self):
        class BaseSpec(Behavior):
            behavior_id = "base_spec"
            param_spec = {'duration': (15, 'beats until expiry'),
                          'kind': ('generic', 'the condition name')}

        class SubSpec(BaseSpec):
            behavior_id = "sub_spec"
            param_spec = {'damage': (1, 'HP per pulse'),
                          'kind': ('bleeding', 'overridden name')}

        params = SubSpec.describe()['params']
        assert set(params) == {'duration', 'kind', 'damage'}
        assert params['kind']['default'] == 'bleeding'   # subclass wins
        assert params['duration']['default'] == 15       # base survives

    def test_describe_infers_types_from_defaults(self):
        class Typed(Behavior):
            behavior_id = "typed"
            param_spec = {'count': (3, ''), 'tags': (['x'], ''),
                          'chance': (0.5, ''), 'label': (None, 'anything')}

        params = Typed.describe()['params']
        assert params['count']['type'] == 'int'
        assert params['tags']['type'] == 'list'
        assert params['chance']['type'] == 'float'
        assert params['label']['type'] == 'any'

    def test_shipped_palette_is_fully_described(self):
        # Every registered behavior must offer a blurb (declared or from
        # its docstring); this is what keeps @behavior/info and a future
        # builder palette from showing blank cards.
        import realm.behaviors    # noqa: F401 — registers the kit
        import realm.combat.behaviors    # noqa: F401
        for entry in BehaviorRegistry.describe_all():
            assert entry['blurb'], f"{entry['id']} has no blurb"

    def test_list_all(self):
        BehaviorRegistry.register(SimpleBehavior)
        BehaviorRegistry.register(CountingBehavior)
        all_ids = BehaviorRegistry.list_all()
        assert 'simple' in all_ids
        assert 'counting' in all_ids


class TestGameObjectBehaviors:
    """Test behavior integration with GameObject (no propagation —
    that's covered in test_propagation.py)."""

    def test_add_behavior(self):
        obj = GameObject("test")
        b = SimpleBehavior()
        obj.add_behavior(b)
        assert b in obj.get_behaviors()
        assert b.owner == obj

    def test_remove_behavior(self):
        obj = GameObject("test")
        b = SimpleBehavior()
        obj.add_behavior(b)
        obj.remove_behavior(b)
        assert b not in obj.get_behaviors()
        assert b.owner is None

    def test_get_behavior_by_type(self):
        obj = GameObject("test")
        simple = SimpleBehavior()
        counting = CountingBehavior()
        obj.add_behavior(simple)
        obj.add_behavior(counting)
        found = obj.get_behavior(CountingBehavior)
        assert found == counting

    def test_get_behavior_not_found(self):
        obj = GameObject("test")
        obj.add_behavior(SimpleBehavior())
        found = obj.get_behavior(CountingBehavior)
        assert found is None

    def test_no_duplicate_behaviors(self):
        obj = GameObject("test")
        b = SimpleBehavior()
        obj.add_behavior(b)
        obj.add_behavior(b)
        assert len(obj.get_behaviors()) == 1

    def test_adding_behavior_marks_dirty(self):
        obj = GameObject("test")
        obj.clear_dirty()
        obj.add_behavior(SimpleBehavior())
        assert obj.is_dirty()

    def test_removing_behavior_marks_dirty(self):
        obj = GameObject("test")
        b = SimpleBehavior()
        obj.add_behavior(b)
        obj.clear_dirty()
        obj.remove_behavior(b)
        assert obj.is_dirty()
