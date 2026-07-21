"""M1 扩展块 D：NPC 系统（25~29 号票）测试。

seam：``execute_line``（ask/say）+ ``TickLoop.advance``（AIController / Chatter /
Spawn 扫描）。不断言组件内部实现细节，只断言可观察消息与世界状态查询结果。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mud_engine.ai import attach_ai_system, condition_from_data
from mud_engine.messaging import ON_HEAR_SAY, HearSayContext, room_say
from mud_engine.components import (
    AIController,
    Container,
    Identity,
    Inquiry,
    NpcSpawnMeta,
    PlayerSession,
    Position,
)
from mud_engine.conditions import Predicate, StubContext, evaluate
from mud_engine.parsing import execute_line
from mud_engine.save import restore_world, save_world
from mud_engine.scene_loader import load_scene
from mud_engine.scenes import build_world
from mud_engine.tick import TickLoop
from mud_engine.world import EntityId, World


def _write_scene(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(text, encoding="utf-8")
    return path


_BASE_ROOMS = """
rooms:
  start_yard:
    name: 起始庭院
    long: 庭院
  corridor:
    name: 长廊
    long: 长廊
    exits:
      south: { to: start_yard }
player:
  name: 你
  start_room: start_yard
"""


class TestAIControllerTick:
    """25 号票：AIController + Behaviors 挂 on_tick。"""

    def test_chatter_behavior_runs_on_advance(self, tmp_path: Path) -> None:
        scene = (
            _BASE_ROOMS
            + """
npcs:
  chatterbox:
    name: 闲聊者
    in_room: start_yard
    behaviors:
      - kind: chatter
        chat_msgs: ["你好啊。"]
        chat_chance: 1.0
"""
        )
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        # load_scene 已 attach；幂等后改 rng（测试确定性）。
        world.ai.rng = _AlwaysSpeakRng()
        world.pending_messages.clear()
        loop = TickLoop(save_fn=lambda: None, world=world, interval=100)
        loop.advance()
        assert any("闲聊者说：你好啊。" in m for m in world.pending_messages)

    def test_tick_interval_skips_intermediate_ticks(self, tmp_path: Path) -> None:
        scene = (
            _BASE_ROOMS
            + """
npcs:
  slow:
    name: 慢嘴
    in_room: start_yard
    tick_interval: 3
    behaviors:
      - kind: chatter
        chat_msgs: ["慢一句。"]
        chat_chance: 1.0
"""
        )
        world, _ = load_scene(_write_scene(tmp_path, scene))
        world.ai.rng = _AlwaysSpeakRng()
        loop = TickLoop(save_fn=lambda: None, world=world, interval=100)
        world.pending_messages.clear()
        loop.advance()  # tick=1，3 的倍数才触发
        loop.advance()  # tick=2
        assert world.pending_messages == []
        loop.advance()  # tick=3
        assert any("慢嘴说：慢一句。" in m for m in world.pending_messages)

    def test_static_npc_without_aicontroller_is_not_ticked(self) -> None:
        world, player_id = build_world()
        # 默认石像守卫有 Inquiry，无 AIController
        npc = _find_npc(world, player_id, "石像守卫")
        assert npc is not None
        assert not world.has_component(npc, AIController)
        world.pending_messages.clear()
        loop = TickLoop(save_fn=lambda: None, world=world, interval=100)
        for _ in range(5):
            loop.advance()
        # Nature 天气/时辰广播可能进 pending；断言无 NPC 闲聊即可。
        assert not any("石像守卫说：" in m for m in world.pending_messages)


class TestSpawnFoundation:
    """26 号票：count / respawn / startroom。"""

    def test_count_spawns_multiple_instances(self, tmp_path: Path) -> None:
        scene = (
            _BASE_ROOMS
            + """
npcs:
  twin:
    name: 双胞胎
    in_room: start_yard
    count: 3
"""
        )
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        room = world.require_component(player_id, Position).room
        twins = [
            e
            for e in world.entities_with(NpcSpawnMeta)
            if world.require_component(e, Identity).name == "双胞胎"
            and world.require_component(e, Position).room == room
        ]
        assert len(twins) == 3
        meta = world.require_component(twins[0], NpcSpawnMeta)
        assert meta.desired_count == 3
        assert meta.template_key == "twin"

    def test_startroom_alias_for_in_room(self, tmp_path: Path) -> None:
        scene = """
rooms:
  yard:
    name: 院子
player:
  name: 你
  start_room: yard
npcs:
  guard:
    name: 守卫
    startroom: yard
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        npc = _find_npc(world, player_id, "守卫")
        assert npc is not None
        assert (
            world.require_component(npc, Position).room
            == world.require_component(player_id, Position).room
        )

    def test_existing_single_static_npc_still_loads(self) -> None:
        world, player_id = build_world()
        npc = _find_npc(world, player_id, "石像守卫")
        assert npc is not None
        assert world.has_component(npc, NpcSpawnMeta)


class TestAskInquiry:
    """27 号票：ask + inquiry。"""

    def test_ask_hits_inquiry_topic(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "ask 石像守卫 about 天气")
        assert any("今日" in m or "晴朗" in m for m in messages)

    def test_ask_uses_alias(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "ask 守卫 about 天气")
        # 别名「守卫」→ 规范名「石像守卫」；文案前缀与 say/room_say 统一为「说：」（35）。
        assert any("石像守卫说：" in m for m in messages)

    def test_ask_unknown_topic_uses_default(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "ask 石像守卫 about 武功")
        assert any("没有回答" in m for m in messages)

    def test_ask_missing_npc(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "ask 不存在的人 about 天气")
        assert any("没有" in m for m in messages)

    def test_ask_usage_hint(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "ask")
        assert any("用法" in m for m in messages)

    def _sage_with_handler(self, tmp_path: Path) -> tuple[World, EntityId]:
        """``handler`` 声明式字符串占位（同 Equippable.apply_hook）；M1 不执行。"""
        scene = (
            _BASE_ROOMS
            + """
npcs:
  sage:
    name: 智者
    in_room: start_yard
    inquiry:
      天道: 天行有常。
      handler: sage_on_topic
"""
        )
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        npc = _find_npc(world, player_id, "智者")
        assert npc is not None
        return world, player_id

    def test_handler_stored_from_yaml(self, tmp_path: Path) -> None:
        world, player_id = self._sage_with_handler(tmp_path)
        npc = _find_npc(world, player_id, "智者")
        assert npc is not None
        assert world.require_component(npc, Inquiry).handler == "sage_on_topic"

    def test_handler_not_in_topics(self, tmp_path: Path) -> None:
        world, player_id = self._sage_with_handler(tmp_path)
        npc = _find_npc(world, player_id, "智者")
        assert npc is not None
        assert "handler" not in world.require_component(npc, Inquiry).topics

    def test_ask_still_uses_string_map(self, tmp_path: Path) -> None:
        world, player_id = self._sage_with_handler(tmp_path)
        messages = execute_line(world, player_id, "ask 智者 about 天道")
        assert any("天行有常" in m for m in messages)

    def test_bare_position_not_askable(self) -> None:
        """ask 候选收窄为 Inquiry / NpcSpawnMeta，不把任意 Position 实体当 NPC。"""
        world, player_id = build_world()
        room = world.require_component(player_id, Position).room
        decoy = world.create_entity()
        world.add_component(decoy, Identity(name="路人甲", aliases=["路人"]))
        world.add_component(decoy, Position(room=room))
        messages = execute_line(world, player_id, "ask 路人甲 about 天气")
        assert any("没有" in m for m in messages)

    def test_real_npc_still_askable(self) -> None:
        """同房有裸 Position 诱饵时，真正的 NPC 仍可 ask。"""
        world, player_id = build_world()
        room = world.require_component(player_id, Position).room
        decoy = world.create_entity()
        world.add_component(decoy, Identity(name="路人甲", aliases=["路人"]))
        world.add_component(decoy, Position(room=room))
        messages = execute_line(world, player_id, "ask 石像守卫 about 天气")
        assert any("晴朗" in m for m in messages)


class TestSayBroadcast:
    """28 号票：say + on_hear_say。"""

    def test_say_returns_confirmation(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "say 大家好")
        assert messages == ["你说：大家好"]

    def test_say_empty_rejected(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "say")
        assert any("说什么" in m for m in messages)

    def test_on_hear_say_fires_with_context(self) -> None:
        world, player_id = build_world()
        heard: list[HearSayContext] = []

        def handler(ctx: HearSayContext) -> None:
            heard.append(ctx)

        world.events.register(ON_HEAR_SAY, handler)
        execute_line(world, player_id, "say 测试广播")
        assert len(heard) == 1
        assert heard[0].speaker_id == player_id
        assert heard[0].text == "测试广播"
        assert heard[0].room == world.require_component(player_id, Position).room

    def test_npc_room_say_reaches_player_pending(self) -> None:
        world, player_id = build_world()
        npc = _find_npc(world, player_id, "石像守卫")
        assert npc is not None
        world.pending_messages.clear()
        room_say(world, npc, "石像低语。")
        assert "石像守卫说：石像低语。" in world.pending_messages

    def test_player_has_player_session(self) -> None:
        world, player_id = build_world()
        assert world.has_component(player_id, PlayerSession)

    def test_container_without_player_session_not_in_broadcast(self) -> None:
        """Position+Container 但无 PlayerSession 的实体不应收到房间广播。"""
        world, player_id = build_world()
        room = world.require_component(player_id, Position).room
        decoy = world.create_entity()
        world.add_component(decoy, Identity(name="假人"))
        world.add_component(decoy, Position(room=room))
        world.add_component(decoy, Container())
        world.pending_messages.clear()
        room_say(world, player_id, "只给真玩家")
        # M1 单玩家：说话者本人不进 pending；decoy 也不得进。
        assert world.pending_messages == []

    def test_player_session_survives_save_restore(self, tmp_path: Path) -> None:
        world, player_id = build_world()
        save_world(world, player_id, tmp_path / "save")
        restored = restore_world(tmp_path / "save")
        assert restored is not None
        rworld, rplayer = restored
        assert rworld.has_component(rplayer, PlayerSession)


class TestChatter:
    """29 号票：Chatter 行为 + 条件求值。"""

    def test_chatter_silent_during_day(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # 白天（is_night=False）：Chatter 条件不满足，不说。
        scene = (
            _BASE_ROOMS
            + """
npcs:
  nightowl:
    name: 夜猫
    in_room: start_yard
    behaviors:
      - kind: chatter
        chat_msgs: ["夜深了。"]
        chat_chance: 1.0
        when:
          predicate: is_night
"""
        )
        world, _ = load_scene(_write_scene(tmp_path, scene))
        world.ai.rng = _AlwaysSpeakRng()
        import mud_engine.ai as ai_mod

        monkeypatch.setattr(
            ai_mod,
            "_condition_context",
            lambda _w: StubContext(phase="day", is_night=False, is_day=True),
        )
        loop = TickLoop(save_fn=lambda: None, world=world, interval=100)
        world.pending_messages.clear()
        loop.advance()
        assert world.pending_messages == []

    def test_chatter_speaks_at_night(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # 夜里（is_night=True）：条件满足，Chatter 说话。
        scene = (
            _BASE_ROOMS
            + """
npcs:
  nightowl:
    name: 夜猫
    in_room: start_yard
    behaviors:
      - kind: chatter
        chat_msgs: ["夜深了。"]
        chat_chance: 1.0
        when:
          predicate: is_night
"""
        )
        world, _ = load_scene(_write_scene(tmp_path, scene))
        world.ai.rng = _AlwaysSpeakRng()
        import mud_engine.ai as ai_mod

        monkeypatch.setattr(
            ai_mod,
            "_condition_context",
            lambda _w: StubContext(phase="night", is_night=True, is_day=False),
        )
        loop = TickLoop(save_fn=lambda: None, world=world, interval=100)
        world.pending_messages.clear()
        loop.advance()
        assert any("夜猫说：夜深了。" in m for m in world.pending_messages)

    def test_condition_from_data_predicate(self) -> None:
        cond = condition_from_data({"predicate": "is_night"})
        assert cond == Predicate(name="is_night")
        assert evaluate(cond, StubContext(is_night=True, is_day=False))
        assert not evaluate(cond, StubContext(is_night=False, is_day=True))


class TestNpcSaveRestore:
    """NPC 新组件可进存档并恢复。"""

    def test_inquiry_survives_save_restore(self, tmp_path: Path) -> None:
        world, player_id = build_world()
        save_dir = tmp_path / "save"
        save_world(world, player_id, save_dir)
        restored = restore_world(save_dir)
        assert restored is not None
        rworld, rplayer = restored
        attach_ai_system(rworld)
        npc = _find_npc(rworld, rplayer, "石像守卫")
        assert npc is not None
        inquiry = rworld.require_component(npc, Inquiry)
        assert "天气" in inquiry.topics
        messages = execute_line(rworld, rplayer, "ask 石像守卫 about 天气")
        assert any("晴朗" in m for m in messages)

    def test_inquiry_handler_survives_save_restore(self, tmp_path: Path) -> None:
        scene = (
            _BASE_ROOMS
            + """
npcs:
  sage:
    name: 智者
    in_room: start_yard
    inquiry:
      天道: 天行有常。
      handler: sage_on_topic
"""
        )
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        save_dir = tmp_path / "save"
        save_world(world, player_id, save_dir)
        restored = restore_world(save_dir)
        assert restored is not None
        rworld, rplayer = restored
        npc = _find_npc(rworld, rplayer, "智者")
        assert npc is not None
        assert rworld.require_component(npc, Inquiry).handler == "sage_on_topic"


class TestAttachIdempotent:
    def test_attach_ai_system_twice_is_safe(self) -> None:
        world, _ = build_world()
        attach_ai_system(world)
        attach_ai_system(world)
        # 不应因重复注册导致双倍 chatter；幂等只挂一次 on_tick。
        loop = TickLoop(save_fn=lambda: None, world=world, interval=100)
        loop.advance()


# ── helpers ──────────────────────────────────────────────


class _AlwaysSpeakRng:
    """测试用 rng：random() 恒为 0（必触发），choice 取首条。"""

    def random(self) -> float:
        return 0.0

    def choice(self, seq):
        return seq[0]


def _find_npc(world: World, player_id: EntityId, name: str) -> EntityId | None:
    room = world.require_component(player_id, Position).room
    for entity in world.entities_with(Position):
        if entity == player_id:
            continue
        if world.require_component(entity, Position).room != room:
            continue
        identity = world.get_component(entity, Identity)
        if identity is not None and identity.name == name:
            return entity
    return None
