"""
Every world store provides the members engine code calls (KERNEL_PLAN 2.3).
"""

from __future__ import annotations

import inspect

import pytest

from realm.persistence.manager import PersistenceManager
from realm.persistence.memory import MemoryStore
from realm.persistence.store import Store

MEMBERS = [name for name, value in vars(Store).items()
           if inspect.isfunction(value) and not name.startswith("_")]


def test_protocol_lists_the_engine_calls():
    assert sorted(MEMBERS) == sorted([
        "get_cached", "all_cached", "find_cached", "save", "delete",
        "keyid_holder", "claim_keyid", "release_keyid",
    ])


@pytest.mark.parametrize("store_class", [PersistenceManager, MemoryStore])
def test_store_provides_every_member(store_class):
    for name in MEMBERS:
        expected = getattr(Store, name)
        actual = getattr(store_class, name, None)
        assert actual is not None, f"{store_class.__name__} lacks {name}"
        assert (inspect.iscoroutinefunction(actual)
                == inspect.iscoroutinefunction(expected)), (
            f"{store_class.__name__}.{name}: sync/async differs from Store")


async def test_memory_store_is_a_store():
    assert isinstance(MemoryStore(), Store)
