"""pre-m4-channels-spawn-quest-05：Channel ``chat`` + ``system``（S1）。

seam：双 ``PlayerSession`` + ``execute_line`` / ``drain_messages`` / ``broadcast_system``。
"""

from __future__ import annotations

from mud_engine.components import Exits, PlayerSession, Position
from mud_engine.messaging import CHANNELS, broadcast_system, publish_channel
from mud_engine.parsing import execute_line
from mud_engine.scenes import build_world


class TestChannelChat:
    class WhenTwoSessionsInDifferentRooms:
        def test_both_receive_chat(self) -> None:
            world, player_a = build_world()
            start = world.require_component(player_a, Position).room
            corridor = world.require_component(start, Exits).by_direction["north"].target
            player_b = world.spawn_player_session(name="乙", room=corridor)

            messages_a = execute_line(world, player_a, "chat 世界你好")
            assert messages_a == ["你闲聊：世界你好"]
            assert world.drain_messages(player_a) == []
            assert "你闲聊：世界你好" in world.drain_messages(player_b)

        def test_empty_chat_rejected(self) -> None:
            world, player_a = build_world()
            messages = execute_line(world, player_a, "chat")
            assert any("用法：chat" in m for m in messages)


class TestChannelSystem:
    class WhenPlayerTriesToWriteSystem:
        def test_unknown_command_system_is_not_channel_fallthrough(self) -> None:
            world, player_a = build_world()
            messages = execute_line(world, player_a, "system 伪公告")
            assert any("未知命令" in m for m in messages)
            assert world.drain_messages(player_a) == []

        def test_publish_channel_rejects_player_writable_false(self) -> None:
            world, player_a = build_world()
            messages = publish_channel(world, "system", player_a, "伪公告")
            assert any("仅系统可写" in m for m in messages)
            assert world.drain_messages(player_a) == []

    class WhenApiInjectsSystem:
        def test_all_default_subscribers_receive(self) -> None:
            world, player_a = build_world()
            room = world.require_component(player_a, Position).room
            player_b = world.spawn_player_session(name="乙", room=room)
            broadcast_system(world, "服务器将于午夜维护。")
            assert "【系统】服务器将于午夜维护。" in world.drain_messages(player_a)
            assert "【系统】服务器将于午夜维护。" in world.drain_messages(player_b)


class TestChannelSubscriptions:
    class WhenSessionUnsubscribedFromChat:
        def test_does_not_receive_chat(self) -> None:
            world, player_a = build_world()
            room = world.require_component(player_a, Position).room
            player_b = world.spawn_player_session(name="乙", room=room)
            session_b = world.require_component(player_b, PlayerSession)
            session_b.subscriptions = frozenset({"system"})
            execute_line(world, player_a, "chat 密语")
            assert world.drain_messages(player_b) == []

    class WhenDefaultSessionCreated:
        def test_subscribes_chat_and_system(self) -> None:
            world, player_a = build_world()
            room = world.require_component(player_a, Position).room
            player_b = world.spawn_player_session(name="乙", room=room)
            for pid in (player_a, player_b):
                subs = world.require_component(pid, PlayerSession).subscriptions
                assert "chat" in subs
                assert "system" in subs

    class WhenChannelRegistry:
        def test_chat_writable_system_not(self) -> None:
            assert CHANNELS["chat"].player_writable is True
            assert CHANNELS["system"].player_writable is False
