"""M1 扩展块 D：NPC 系统（25~29 号票）测试。

seam：``execute_line``（ask/say）+ ``TickLoop.advance``（AIController / Chatter /
Spawn 扫描）。不断言组件内部实现细节，只断言可观察消息与世界状态查询结果。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mud_engine.ai import attach_ai_system, condition_from_data
from mud_engine.commands import ON_HEAR_SAY, HearSayContext, room_say
from mud_engine.components import (
    AIController,
    Identity,
    Inquiry,
    NpcSpawnMeta,
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
        world._ai_rng = _AlwaysSpeakRng()  # type: ignore[attr-defined]
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
        world._ai_rng = _AlwaysSpeakRng()  # type: ignore[attr-defined]
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
        assert world.require_component(npc, Position).room == world.require_component(
            player_id, Position
        ).room

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
        assert any("说道" in m for m in messages)

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


class TestChatter:
    """29 号票：Chatter 行为 + 条件求值。"""

    def test_chatter_with_night_condition(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        world._ai_rng = _AlwaysSpeakRng()  # type: ignore[attr-defined]
        loop = TickLoop(save_fn=lambda: None, world=world, interval=100)

        import mud_engine.ai as ai_mod

        # 白天：不说
        monkeypatch.setattr(
            ai_mod,
            "_condition_context",
            lambda _w: StubContext(phase="day", is_night=False, is_day=True),
        )
        world.pending_messages.clear()
        loop.advance()
        assert world.pending_messages == []

        # 夜里：说
        monkeypatch.setattr(
            ai_mod,
            "_condition_context",
            lambda _w: StubContext(phase="night", is_night=True, is_day=False),
        )
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


class TestAttachIdempotent:
    def test_attach_ai_system_twice_is_safe(self) -> None:
        world, _ = build_world()
        attach_ai_system(world)
        attach_ai_system(world)
        # 不应因重复注册导致双倍 chatter；默认场景无 AIController，空转即可。
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
