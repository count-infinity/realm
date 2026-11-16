"""
MUD_PLAN step 7 acceptance: two players in different rooms talk by
``tell`` and on ``gossip``; one logs out; the other mails them; the first
logs in and reads it. Over the real login path.
"""

from __future__ import annotations

from realm.server.game import GameServer
from tests.test_accounts import Instant, _client


async def test_tell_gossip_logout_mail_login_read():
    from realm.core.objects import GameObject
    from realm.packs import import_pack

    srv = GameServer(db_path=":memory:", enable_telnet=False, tick_interval=0,
                     game_system=Instant)
    await srv.start()
    try:
        await import_pack("channels", srv.persistence)
        ann = await _client(srv)
        await ann.send("create ann correcthorse")
        await ann.send("Bree")
        bob = await _client(srv, address="10.0.0.2")
        await bob.send("create bob correcthorse")
        await bob.send("Cole")
        dock = GameObject("The Dock", tags=["room"])
        await srv.persistence.save(dock)
        bob.player.location = dock
        assert ann.player.location is not bob.player.location

        assert "Bree tells you, 'where are you?'" in await _said(ann, bob,
                                                                "tell cole where are you?")
        assert "Cole tells you, 'at the dock'" in await _said(bob, ann, "reply at the dock")
        assert "[gossip] Bree: fish tonight!" in await _said(ann, bob, "gossip fish tonight!")

        await bob.send("logout")
        out = await ann.send("tell cole still there?")
        assert "Cole is not online" in out
        assert "Mail sent to Cole." in await ann.send("mail cole = Fish/Bring a net.")

        out = await bob.send("connect bob correcthorse")
        assert bob.player.name == "Cole"
        assert "You have 1 unread message." in out
        out = await bob.send("mail 1")
        assert "From: Bree" in out and "Bring a net." in out
    finally:
        await srv.stop()


async def _said(speaker, listener, line):
    start = len(listener.out)
    await speaker.send(line)
    await listener.session.flush_output()
    return "\n".join(listener.out[start:])
