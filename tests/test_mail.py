"""
MUD_PLAN step 7.4: mail (the ``mail`` feature).

Mail is addressed to a character and held by that character's account, so
it waits for whichever character the person logs in with next.
"""

from __future__ import annotations

import pytest

from realm.config.loader import Settings
from realm.core.action_types import ActionType
from realm.core.propagation import Action, propagate
from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


def _text(sim, who):
    return "\n".join(sim.seen(who))


def _people(sim):
    inn = sim.room("Inn")
    ann = sim.player("Ann", location=inn)
    sim.account("ann", ann)
    gus = sim.obj("Gus", tags=["player"])                  # offline
    gus_alt = sim.obj("Gusalt", tags=["player"])
    gus_account = sim.account("gus", gus, gus_alt)
    return inn, ann, gus, gus_alt, gus_account


async def test_send_to_an_offline_player_and_read_after_login(sim):
    inn, ann, gus, gus_alt, gus_account = _people(sim)
    await sim.do(ann, "mail gus = Supper/Come by the inn at six.")
    assert "Mail sent to Gus." in _text(sim, ann)
    letters = sim.store.find_cached(tag="mail")
    assert len(letters) == 1 and letters[0].location is gus_account

    # Gus logs in, on his other character: the mail waits on the account.
    from realm.std.accounts.account import link_character
    alt = sim.player("Altgus", location=inn)
    link_character(gus_account, alt)
    sim.session(alt).account = gus_account
    await propagate(Action(actor=alt, target=inn, action_type=ActionType.CONNECT))
    assert "You have 1 unread message." in _text(sim, alt)
    await sim.do(alt, "mail")
    out = _text(sim, alt)
    assert "Ann" in out and "Supper" in out and "1" in out
    await sim.do(alt, "mail 1")
    out = _text(sim, alt)
    assert "Come by the inn at six." in out and "From: Ann" in out
    assert letters[0].db.read is True


async def test_an_online_recipient_is_told(sim):
    inn, ann, _gus, _gus_alt, _acct = _people(sim)
    bob = sim.player("Bob", location=sim.room("Dock"))
    sim.account("bob", bob)
    await sim.do(ann, "mail bob = Hi/Just saying hi.")
    assert "You have new mail from Ann." in _text(sim, bob)


async def test_delete_and_reply(sim):
    inn, ann, gus, _alt, gus_account = _people(sim)
    bob = sim.player("Bob", location=inn)
    sim.account("bob", bob)
    await sim.do(ann, "mail bob = One/first")
    await sim.do(ann, "mail bob = Two/second")
    await sim.do(bob, "mail/reply 1 = got it")
    replies = [m for m in sim.store.find_cached(tag="mail") if m.db.to == "Ann"]
    assert replies and replies[0].db.subject == "Re: One" and replies[0].db.body == "got it"
    await sim.do(bob, "mail/delete 1")
    sim.seen(bob)
    await sim.do(bob, "mail")
    out = _text(sim, bob)
    assert "Two" in out and "One" not in out


async def test_no_such_message_or_recipient(sim):
    inn, ann, _gus, _alt, _acct = _people(sim)
    await sim.do(ann, "mail 9")
    assert "You have no message 9." in _text(sim, ann)
    await sim.do(ann, "mail zed = Hi/there")
    assert "No one called 'zed'" in _text(sim, ann)
    sim.obj("Wisp", tags=["player"])                        # no account
    await sim.do(ann, "mail wisp = Hi/there")
    assert "Wisp cannot receive mail." in _text(sim, ann)


async def test_the_limit():
    sim = Simulator(settings=Settings(raw={"MAIL_LIMIT": 2}))
    try:
        inn, ann, gus, _alt, gus_account = _people(sim)
        for n in range(3):
            await sim.do(ann, f"mail gus = Note {n}/body")
        assert len(sim.store.find_cached(tag="mail")) == 2
        assert "Gus's mailbox is full." in _text(sim, ann)
    finally:
        sim.close()


async def test_system_mail_from_softcode(sim):
    inn, ann, gus, _alt, gus_account = _people(sim)
    clerk = sim.obj("guild clerk", location=inn)
    result, err = await sim.eval(clerk, "result = send_mail('Gus', 'Dues', 'Your dues are late.')")
    assert err is None and result is True
    letter = sim.store.find_cached(tag="mail")[0]
    assert letter.db.sender == "guild clerk" and letter.location is gus_account
