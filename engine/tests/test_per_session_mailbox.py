"""pre-m4-channels-spawn-quest-03：按会话收件箱（假多人 seam）。

seam：同一 World 上双 PlayerSession + ``execute_line`` / ``drain_messages``。
"""

from __future__ import annotations

from mud_engine.components import Exits, Identity, Position
from mud_engine.messaging import room_say
from mud_engine.parsing import execute_line
from mud_engine.scenes import build_world


class TestPerSessionMailbox:
    class WhenTwoSessionsShareARoom:
        def test_other_session_receives_room_say(self) -> None:
            world, player_a = build_world()
            room = world.require_component(player_a, Position).room
            player_b = world.spawn_player_session(name="乙", room=room)

            messages_a = execute_line(world, player_a, "say 大家好")
            assert any("你说：大家好" in m for m in messages_a)
            assert world.drain_messages(player_a) == []
            # 主会话 Identity.name 默认是「你」，旁观文案为「你说：…」
            assert "你说：大家好" in world.drain_messages(player_b)

    class WhenSessionsAreInDifferentRooms:
        def test_room_say_does_not_cross(self) -> None:
            world, player_a = build_world()
            start = world.require_component(player_a, Position).room
            corridor = world.require_component(start, Exits).by_direction["north"].target
            player_b = world.spawn_player_session(name="乙", room=corridor)

            execute_line(world, player_a, "say 庭院密语")
            assert world.drain_messages(player_b) == []

    class WhenNpcSpeaksInSharedRoom:
        def test_all_sessions_receive_broadcast(self) -> None:
            world, player_a = build_world()
            room = world.require_component(player_a, Position).room
            player_b = world.spawn_player_session(name="乙", room=room)
            guard = None
            for entity in world.entities_in_room(room, exclude=player_a):
                if world.require_component(entity, Identity).name == "石像守卫":
                    guard = entity
                    break
            assert guard is not None
            room_say(world, guard, "石像低语。")
            assert "石像守卫说：石像低语。" in world.drain_messages(player_a)
            assert "石像守卫说：石像低语。" in world.drain_messages(player_b)

    class WhenUsingPendingMessagesCompatView:
        def test_pending_messages_mirrors_primary_mailbox(self) -> None:
            world, player_a = build_world()
            assert world.primary_player_id == player_a
            room = world.require_component(player_a, Position).room
            player_b = world.spawn_player_session(name="乙", room=room)
            execute_line(world, player_b, "say 乙发言")
            assert any("乙说：乙发言" in m for m in world.pending_messages)
            world.pending_messages.clear()
            assert world.drain_messages(player_a) == []
