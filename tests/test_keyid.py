"""
Keyid — the friendly, unique, opt-in ``$handle`` layered over the canonical
uuid (docs/design/object-identity.md).

Covers the @keyid command, ``get('$keyid')`` resolution, uniqueness
(conflict, never merge), rename/clear/clone behavior, protection from bare
@set/set_attr, the configurable sigil, and worldio import handling.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    s.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(s._sessions.values()))
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _reset_keyid_sigil():
    """Keep the module-global sigil at its default across tests."""
    from realm.scripting.functions import DEFAULT_KEYID_SIGIL, set_keyid_sigil
    set_keyid_sigil(DEFAULT_KEYID_SIGIL)
    yield
    set_keyid_sigil(DEFAULT_KEYID_SIGIL)


def admin(sim, room):
    p = sim.player("Ada", location=room)
    p.add_tag("admin")
    return p


async def resolves_to(sim, actor, spec):
    """The id ``get(spec)`` resolves to, as softcode sees it (or None)."""
    result, error = await sim.eval(
        actor, f"o = get({spec!r}); result = o.id if o is not None else None")
    assert error is None, error
    return result


class TestResolution:

    async def test_set_and_resolve(self, sim):
        room = sim.room("Vault")
        ada = admin(sim, room)
        core = sim.obj("BankNet Core", location=room)
        await sim.do(ada, "@keyid BankNet Core = banknet_core")
        assert any("banknet_core" in m for m in sim.seen(ada))
        assert await resolves_to(sim, ada, "$banknet_core") == core.id

    async def test_missing_keyid_resolves_none(self, sim):
        room = sim.room("Vault")
        ada = admin(sim, room)
        assert await resolves_to(sim, ada, "$nope") is None

    async def test_survives_rename(self, sim):
        room = sim.room("Vault")
        ada = admin(sim, room)
        core = sim.obj("BankNet Core", location=room)
        await sim.do(ada, "@keyid BankNet Core = banknet_core")
        await sim.do(ada, "@name BankNet Core = Old Vault Computer")
        # A name lookup would now miss; the keyid still hits.
        assert await resolves_to(sim, ada, "$banknet_core") == core.id

    async def test_show_reports_current(self, sim):
        room = sim.room("Vault")
        ada = admin(sim, room)
        sim.obj("BankNet Core", location=room)
        await sim.do(ada, "@keyid BankNet Core = banknet_core")
        sim.seen(ada)
        await sim.do(ada, "@keyid BankNet Core")
        assert any("$banknet_core" in m for m in sim.seen(ada))


class TestUniqueness:

    async def test_conflict_is_refused_not_merged(self, sim):
        room = sim.room("Vault")
        ada = admin(sim, room)
        core = sim.obj("BankNet Core", location=room)
        decoy = sim.obj("Decoy Core", location=room)
        await sim.do(ada, "@keyid BankNet Core = banknet_core")
        sim.seen(ada)
        await sim.do(ada, "@keyid Decoy Core = banknet_core")
        msg = " ".join(sim.seen(ada))
        assert "Refused" in msg and "already belongs" in msg
        # Still resolves to the FIRST holder; the decoy stays keyless.
        assert await resolves_to(sim, ada, "$banknet_core") == core.id
        assert decoy.db.get("keyid") is None

    async def test_reassign_same_object_is_idempotent(self, sim):
        room = sim.room("Vault")
        ada = admin(sim, room)
        core = sim.obj("BankNet Core", location=room)
        await sim.do(ada, "@keyid BankNet Core = banknet_core")
        await sim.do(ada, "@keyid BankNet Core = banknet_core")
        assert await resolves_to(sim, ada, "$banknet_core") == core.id

    async def test_changing_keyid_frees_the_old(self, sim):
        room = sim.room("Vault")
        ada = admin(sim, room)
        core = sim.obj("BankNet Core", location=room)
        await sim.do(ada, "@keyid BankNet Core = old_handle")
        await sim.do(ada, "@keyid BankNet Core = new_handle")
        assert await resolves_to(sim, ada, "$new_handle") == core.id
        assert await resolves_to(sim, ada, "$old_handle") is None

    async def test_clear(self, sim):
        room = sim.room("Vault")
        ada = admin(sim, room)
        core = sim.obj("BankNet Core", location=room)
        await sim.do(ada, "@keyid BankNet Core = banknet_core")
        await sim.do(ada, "@keyid BankNet Core =")
        assert await resolves_to(sim, ada, "$banknet_core") is None
        assert core.db.get("keyid") is None


class TestProtection:

    async def test_set_is_redirected_to_keyid(self, sim):
        room = sim.room("Vault")
        ada = admin(sim, room)
        core = sim.obj("BankNet Core", location=room)
        await sim.do(ada, "@set BankNet Core/keyid = sneaky")
        assert any("@keyid" in m for m in sim.seen(ada))
        assert core.db.get("keyid") is None

    async def test_softcode_set_attr_cannot_write_keyid(self, sim):
        room = sim.room("Vault")
        ada = admin(sim, room)
        core = sim.obj("BankNet Core", location=room)
        await sim.eval(ada, f"set_attr(get('#{core.id}'), 'keyid', 'sneaky')")
        assert core.db.get("keyid") is None


class TestClone:

    async def test_clone_drops_keyid(self, sim):
        room = sim.room("Vault")
        ada = admin(sim, room)
        core = sim.obj("BankNet Core", location=room)
        await sim.do(ada, "@keyid BankNet Core = banknet_core")
        sim.seen(ada)
        await sim.do(ada, "@clone BankNet Core = Branch Core")
        clones = [o for o in sim.store.all_cached() if o.name == "Branch Core"]
        assert len(clones) == 1
        assert clones[0].db.get("keyid") is None
        # The original stays the sole holder.
        assert await resolves_to(sim, ada, "$banknet_core") == core.id


class TestConfigurableSigil:

    async def test_multi_char_sigil(self, sim):
        from realm.scripting.functions import set_keyid_sigil
        room = sim.room("Vault")
        ada = admin(sim, room)
        core = sim.obj("BankNet Core", location=room)
        await sim.do(ada, "@keyid BankNet Core = banknet_core")
        set_keyid_sigil("$$")
        assert await resolves_to(sim, ada, "$$banknet_core") == core.id
        # A single '$' is now just a name prefix — a miss, not the keyid.
        assert await resolves_to(sim, ada, "$banknet_core") is None

    def test_bad_sigils_rejected(self):
        from realm.scripting.functions import set_keyid_sigil
        for bad in ("", "key", "a", "#x", "$ ", "x" * 17):
            with pytest.raises(ValueError):
                set_keyid_sigil(bad)


class TestImportKeyid:

    async def test_clone_import_conflict_lands_keyless(self, sim):
        room = sim.room("Vault")
        ada = admin(sim, room)
        core = sim.obj("BankNet Core", location=room)
        await sim.do(ada, "@keyid BankNet Core = banknet_core")

        from realm.persistence.worldio import import_objects
        data = {"realm_format": 1, "objects": [
            {"id": "src-1", "name": "Imported Core", "tags": ["thing"],
             "attrs": {"keyid": "banknet_core", "note": "hi"}}]}
        imported = await import_objects(data, sim.store)

        assert len(imported) == 1
        # Conflict → keyless; ordinary attrs still carry over.
        assert imported[0].db.get("keyid") is None
        assert imported[0].db.get("note") == "hi"
        assert sim.store.keyid_holder("banknet_core").id == core.id

    async def test_clone_import_free_keyid_carries_over(self, sim):
        from realm.persistence.worldio import import_objects
        data = {"realm_format": 1, "objects": [
            {"id": "src-1", "name": "Imported Core", "tags": ["thing"],
             "attrs": {"keyid": "fresh_core"}}]}
        imported = await import_objects(data, sim.store)
        assert imported[0].db.get("keyid") == "fresh_core"
        assert sim.store.keyid_holder("fresh_core").id == imported[0].id

    async def test_sync_overwrite_changes_keyid_in_place(self, sim):
        # Same object (matched by stable id); the file now assigns a NEW,
        # free keyid — a plain overwrite, not a conflict.
        from realm.persistence.worldio import apply_plan, diff_plan
        room = sim.room("Vault")
        core = sim.obj("BankNet Core", location=room)
        ok, _ = sim.store.claim_keyid(core, "old_handle")
        core.db.set("keyid", "old_handle")
        assert ok

        data = {"realm_format": 1, "objects": [
            {"id": core.id, "name": "BankNet Core", "tags": ["thing"],
             "attrs": {"keyid": "new_handle"}}]}
        plan = diff_plan(data, zone="anywhere", persistence=sim.store)
        assert not plan.conflict
        await apply_plan(data, plan, sim.store)

        assert core.db.get("keyid") == "new_handle"
        assert sim.store.keyid_holder("new_handle").id == core.id
        assert sim.store.keyid_holder("old_handle") is None  # old handle freed

    def test_sync_overwrite_to_a_taken_keyid_still_conflicts(self, sim):
        # Overwriting is fine, but not by stealing a DIFFERENT object's handle.
        from realm.persistence.worldio import diff_plan
        room = sim.room("Vault")
        core = sim.obj("BankNet Core", location=room)
        other = sim.obj("Other Core", location=room)
        sim.store.claim_keyid(core, "core_handle")
        core.db.set("keyid", "core_handle")
        sim.store.claim_keyid(other, "other_handle")
        other.db.set("keyid", "other_handle")

        data = {"realm_format": 1, "objects": [
            {"id": core.id, "name": "BankNet Core", "tags": ["thing"],
             "attrs": {"keyid": "other_handle"}}]}
        plan = diff_plan(data, zone="anywhere", persistence=sim.store)
        assert plan.conflict
        assert any("other_handle" in reason for _n, reason in plan.conflict)

    def test_sync_plan_flags_keyid_conflict(self, sim):
        from realm.persistence.worldio import diff_plan
        room = sim.room("Vault")
        core = sim.obj("BankNet Core", location=room)
        ok, _ = sim.store.claim_keyid(core, "banknet_core")
        core.db.set("keyid", "banknet_core")
        assert ok
        # A file entry with a DIFFERENT id claiming the same keyid.
        data = {"realm_format": 1, "objects": [
            {"id": "other-id", "name": "Other", "tags": ["thing"],
             "attrs": {"keyid": "banknet_core"}}]}
        plan = diff_plan(data, zone="anywhere", persistence=sim.store)
        assert plan.conflict
        assert any("banknet_core" in reason for _n, reason in plan.conflict)
