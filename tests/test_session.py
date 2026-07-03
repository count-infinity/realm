"""Tests for the Session and SessionManager classes."""


import pytest

from realm.core.objects import GameObject
from realm.gateway.session import Session, SessionManager, SessionState


class TestSession:
    """Test suite for Session class."""

    def test_session_creation(self):
        """Session can be created with defaults."""
        session = Session()
        assert session.id is not None
        assert session.state == SessionState.CONNECTED
        assert session.player is None
        assert session.protocol == "unknown"
        assert session.address == "unknown"

    def test_session_with_params(self):
        """Session can be created with protocol and address."""
        session = Session(protocol="telnet", address="127.0.0.1:12345")
        assert session.protocol == "telnet"
        assert session.address == "127.0.0.1:12345"

    def test_custom_session_id(self):
        """Session can be created with custom ID."""
        session = Session(session_id="my-custom-id")
        assert session.id == "my-custom-id"

    def test_idle_time(self):
        """Session tracks idle time."""
        session = Session()
        # Idle time should be very small right after creation
        assert session.idle_time >= 0
        assert session.idle_time < 1

    def test_touch_updates_activity(self):
        """touch() updates last activity timestamp."""
        session = Session()
        initial_idle = session.idle_time
        session.touch()
        # After touch, idle time should reset
        assert session.idle_time <= initial_idle

    @pytest.mark.asyncio
    async def test_send_and_receive(self):
        """Messages can be sent and received."""
        session = Session()

        # Push input (simulating protocol handler)
        await session.push_input("test command")

        # Receive input
        received = await session.receive()
        assert received == "test command"

    def test_send_nowait(self):
        """send_nowait adds to output queue."""
        session = Session()
        session.send_nowait("Hello!")

        # Check queue has the message
        assert not session._output_queue.empty()

    def test_push_input_nowait(self):
        """push_input_nowait adds to input queue."""
        session = Session()
        session.push_input_nowait("command")

        # Check queue has the command
        result = session.receive_nowait()
        assert result == "command"

    def test_receive_nowait_empty(self):
        """receive_nowait returns None when queue is empty."""
        session = Session()
        result = session.receive_nowait()
        assert result is None

    def test_session_data(self):
        """Session can store arbitrary data."""
        session = Session()
        session.set_data('key', 'value')
        assert session.get_data('key') == 'value'
        assert session.get_data('missing') is None
        assert session.get_data('missing', 'default') == 'default'

    def test_link_player(self):
        """Session can be linked to a player."""
        session = Session()
        player = GameObject("TestPlayer", tags=['player'])

        session.link_player(player)

        assert session.player == player
        assert session.state == SessionState.PLAYING

    def test_unlink_player(self):
        """Session can be unlinked from a player."""
        session = Session()
        player = GameObject("TestPlayer", tags=['player'])
        session.link_player(player)

        session.unlink_player()

        assert session.player is None
        assert session.state == SessionState.CONNECTED

    @pytest.mark.asyncio
    async def test_flush_output(self):
        """flush_output sends all queued messages."""
        session = Session()
        written = []

        async def writer(msg):
            written.append(msg)

        session.set_writer(writer)
        await session.send("message 1")
        await session.send("message 2")

        await session.flush_output()

        assert written == ["message 1", "message 2"]
        assert session._output_queue.empty()


class TestSessionManager:
    """Test suite for SessionManager class."""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """SessionManager can create sessions."""
        manager = SessionManager()
        session = await manager.create_session(protocol="telnet", address="127.0.0.1")

        assert session is not None
        assert session.protocol == "telnet"
        assert session.address == "127.0.0.1"
        assert manager.session_count() == 1

    @pytest.mark.asyncio
    async def test_get_session(self):
        """Sessions can be retrieved by ID."""
        manager = SessionManager()
        session = await manager.create_session()

        retrieved = manager.get_session(session.id)
        assert retrieved == session

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self):
        """Getting nonexistent session returns None."""
        manager = SessionManager()
        result = manager.get_session("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_destroy_session(self):
        """Sessions can be destroyed."""
        manager = SessionManager()
        session = await manager.create_session()

        await manager.destroy_session(session)

        assert manager.session_count() == 0
        assert manager.get_session(session.id) is None

    @pytest.mark.asyncio
    async def test_link_player_to_session(self):
        """Players can be linked to sessions."""
        manager = SessionManager()
        session = await manager.create_session()
        player = GameObject("TestPlayer", tags=['player'])

        manager.link_player_to_session(session, player)

        assert session.player == player
        assert manager.get_session_by_player(player) == session
        assert manager.player_count() == 1

    @pytest.mark.asyncio
    async def test_player_reconnect(self):
        """New session replaces old for same player."""
        manager = SessionManager()
        session1 = await manager.create_session()
        session2 = await manager.create_session()
        player = GameObject("TestPlayer", tags=['player'])

        manager.link_player_to_session(session1, player)
        manager.link_player_to_session(session2, player)

        assert session1.player is None
        assert session2.player == player
        assert manager.get_session_by_player(player) == session2
        assert manager.player_count() == 1

    @pytest.mark.asyncio
    async def test_all_sessions(self):
        """all_sessions returns all active sessions."""
        manager = SessionManager()
        s1 = await manager.create_session()
        s2 = await manager.create_session()
        s3 = await manager.create_session()

        all_sessions = manager.all_sessions()
        assert len(all_sessions) == 3
        assert s1 in all_sessions
        assert s2 in all_sessions
        assert s3 in all_sessions

    @pytest.mark.asyncio
    async def test_playing_sessions(self):
        """playing_sessions returns only sessions with players."""
        manager = SessionManager()
        s1 = await manager.create_session()
        s2 = await manager.create_session()

        player = GameObject("TestPlayer", tags=['player'])
        manager.link_player_to_session(s1, player)

        playing = manager.playing_sessions()
        assert len(playing) == 1
        assert s1 in playing
        assert s2 not in playing

    @pytest.mark.asyncio
    async def test_sessions_by_address(self):
        """Sessions can be retrieved by address."""
        manager = SessionManager()
        s1 = await manager.create_session(address="192.168.1.1")
        s2 = await manager.create_session(address="192.168.1.1")
        s3 = await manager.create_session(address="192.168.1.2")

        same_address = manager.get_sessions_by_address("192.168.1.1")
        assert len(same_address) == 2
        assert s1 in same_address
        assert s2 in same_address
        assert s3 not in same_address

    @pytest.mark.asyncio
    async def test_connect_callback(self):
        """Connect callbacks are called on new sessions."""
        manager = SessionManager()
        connected = []

        async def on_connect(session):
            connected.append(session)

        manager.on_connect(on_connect)
        session = await manager.create_session()

        assert len(connected) == 1
        assert connected[0] == session

    @pytest.mark.asyncio
    async def test_disconnect_callback(self):
        """Disconnect callbacks are called on session destroy."""
        manager = SessionManager()
        disconnected = []

        async def on_disconnect(session):
            disconnected.append(session.id)

        manager.on_disconnect(on_disconnect)
        session = await manager.create_session()
        session_id = session.id

        await manager.destroy_session(session)

        assert len(disconnected) == 1
        assert disconnected[0] == session_id

    @pytest.mark.asyncio
    async def test_broadcast(self):
        """broadcast sends to all playing sessions."""
        manager = SessionManager()
        s1 = await manager.create_session()
        s2 = await manager.create_session()
        s3 = await manager.create_session()

        player1 = GameObject("Player1", tags=['player'])
        player2 = GameObject("Player2", tags=['player'])
        manager.link_player_to_session(s1, player1)
        manager.link_player_to_session(s2, player2)
        # s3 has no player

        await manager.broadcast("Hello everyone!")

        # s1 and s2 should have the message, s3 should not
        assert not s1._output_queue.empty()
        assert not s2._output_queue.empty()
        assert s3._output_queue.empty()

    @pytest.mark.asyncio
    async def test_broadcast_exclude(self):
        """broadcast can exclude a session."""
        manager = SessionManager()
        s1 = await manager.create_session()
        s2 = await manager.create_session()

        player1 = GameObject("Player1", tags=['player'])
        player2 = GameObject("Player2", tags=['player'])
        manager.link_player_to_session(s1, player1)
        manager.link_player_to_session(s2, player2)

        await manager.broadcast("Hello!", exclude=s1)

        # Only s2 should have the message
        assert s1._output_queue.empty()
        assert not s2._output_queue.empty()

    @pytest.mark.asyncio
    async def test_broadcast_to_room(self):
        """broadcast_to_room sends to players in a room."""
        manager = SessionManager()
        room = GameObject("Room", tags=['room'])

        s1 = await manager.create_session()
        s2 = await manager.create_session()
        s3 = await manager.create_session()

        player1 = GameObject("Player1", tags=['player'], location=room)
        player2 = GameObject("Player2", tags=['player'], location=room)
        player3 = GameObject("Player3", tags=['player'])  # Different room

        manager.link_player_to_session(s1, player1)
        manager.link_player_to_session(s2, player2)
        manager.link_player_to_session(s3, player3)

        await manager.broadcast_to_room(room, "Room message!")

        assert not s1._output_queue.empty()
        assert not s2._output_queue.empty()
        assert s3._output_queue.empty()  # Not in room
