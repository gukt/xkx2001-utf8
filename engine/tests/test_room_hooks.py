"""Pre-M4-01：房间钩子协议 + 注册表 + 窄 ctx + 挂载 / UGC 拒绝（S0 + S2）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from mud_engine.components import Exits, HiddenExits, Position, RoomFreeState, RoomHookBinding
from mud_engine.errors import SceneLoadError
from mud_engine.pack import load_pack
from mud_engine.parsing import execute_line
from mud_engine.room_hooks import (
    RoomHookContext,
    clear_room_hooks,
    get_room_hook,
    register_room_hook,
    relocate_entity,
)
from mud_engine.scene_loader import load_scene
from mud_engine.tick import TickLoop
from mud_engine.world import World


def _minimal_two_room_world() -> tuple[World, int, int, int]:
    """手建两房 + 玩家，不经 YAML（S0 直调）。"""
    world = World()
    room_a = world.create_entity()
    room_b = world.create_entity()
    world.add_component(room_a, Exits())
    world.add_component(room_b, Exits())
    world.room_ids = {"a": room_a, "b": room_b}
    player = world.create_entity()
    world.add_component(player, Position(room=room_a))
    from mud_engine.components import Identity, PlayerSession

    world.add_component(player, Identity(name="测者"))
    world.add_component(player, PlayerSession())
    world.primary_player_id = player
    return world, room_a, room_b, player


class RecordingHook:
    """测试专用哑钩子：记录生命周期调用，不进官方切片包。"""

    def __init__(self) -> None:
        self.enters: list[int] = []
        self.leaves: list[int] = []
        self.ticks: list[int] = []

    def on_enter(self, ctx: RoomHookContext) -> None:
        assert ctx.actor_id is not None
        self.enters.append(ctx.actor_id)
        ctx.set_state({"last_enter": ctx.actor_id})
        ctx.message_room("哑钩子：有人进来了")

    def on_leave(self, ctx: RoomHookContext) -> None:
        assert ctx.actor_id is not None
        self.leaves.append(ctx.actor_id)

    def on_tick(self, ctx: RoomHookContext) -> None:
        self.ticks.append(ctx.tick if ctx.tick is not None else -1)
        if ctx.schedule_due("boom"):
            ctx.remove_exit("east")
            ctx.clear_schedule("boom")
            ctx.message_room("哑钩子：崩塌")


class ExplodingHook:
    def on_enter(self, ctx: RoomHookContext) -> None:
        raise RuntimeError("钩子爆炸")


@pytest.fixture(autouse=True)
def _clean_hook_registry() -> None:
    clear_room_hooks()
    yield
    clear_room_hooks()


class TestRoomHookRegistry:
    def test_register_and_get(self) -> None:
        hook = RecordingHook()
        register_room_hook("test_dummy", hook)
        assert get_room_hook("test_dummy") is hook

    def test_unregistered_returns_none(self) -> None:
        assert get_room_hook("no_such_hook") is None


class TestRoomHookContextS0:
    def test_add_and_remove_exit(self) -> None:
        world, room_a, room_b, player = _minimal_two_room_world()
        ctx = RoomHookContext(world, room_a, actor_id=player)
        ctx.add_exit("east", room_b)
        exits = world.require_component(room_a, Exits)
        assert "east" in exits.by_direction
        assert exits.by_direction["east"].target == room_b
        ctx.remove_exit("east")
        assert "east" not in exits.by_direction

    def test_add_exit_by_room_key(self) -> None:
        world, room_a, room_b, player = _minimal_two_room_world()
        ctx = RoomHookContext(world, room_a, actor_id=player)
        ctx.add_exit("east", "b")
        assert world.require_component(room_a, Exits).by_direction["east"].target == room_b

    def test_hide_and_reveal_exit(self) -> None:
        world, room_a, room_b, player = _minimal_two_room_world()
        exits = world.require_component(room_a, Exits)
        from mud_engine.components import Exit

        exits.by_direction["north"] = Exit(target=room_b)
        ctx = RoomHookContext(world, room_a, actor_id=player)
        ctx.hide_exit("north")
        assert "north" not in exits.by_direction
        hidden = world.require_component(room_a, HiddenExits)
        assert "north" in hidden.by_direction
        ctx.reveal_exit("north")
        assert "north" in exits.by_direction
        assert "north" not in hidden.by_direction

    def test_schedule_and_free_state(self) -> None:
        world, room_a, _room_b, player = _minimal_two_room_world()
        ctx = RoomHookContext(world, room_a, actor_id=player, tick=5)
        ctx.set_state({"step": 1})
        assert ctx.get_state() == {"step": 1}
        ctx.schedule("boom", due_tick=10)
        free = world.require_component(room_a, RoomFreeState)
        assert free.schedules["boom"] == 10
        assert ctx.schedule_due("boom") is False
        ctx2 = RoomHookContext(world, room_a, actor_id=player, tick=10)
        assert ctx2.schedule_due("boom") is True
        ctx2.clear_schedule("boom")
        assert "boom" not in free.schedules

    def test_message_room_and_actor(self) -> None:
        world, room_a, _room_b, player = _minimal_two_room_world()
        ctx = RoomHookContext(world, room_a, actor_id=player)
        ctx.message_room("房间广播")
        ctx.message_actor("只给你")
        messages = world.drain_messages(player)
        assert "房间广播" in messages
        assert "只给你" in messages

    def test_move_entity_changes_position(self) -> None:
        world, room_a, room_b, player = _minimal_two_room_world()
        ctx = RoomHookContext(world, room_a, actor_id=player)
        ctx.move_entity(player, room_b)
        assert world.require_component(player, Position).room == room_b

    def test_relocate_entity_standalone(self) -> None:
        world, room_a, room_b, player = _minimal_two_room_world()
        relocate_entity(world, player, room_b)
        assert world.require_component(player, Position).room == room_b
        # 独立方法本体：不经 ctx 也可调用（供未来 SkillBehavior）
        relocate_entity(world, player, room_a)
        assert world.require_component(player, Position).room == room_a

    def test_readonly_snapshot_fields(self) -> None:
        world, room_a, _room_b, player = _minimal_two_room_world()
        ctx = RoomHookContext(world, room_a, actor_id=player, params={"x": 1}, tick=3)
        assert ctx.room_id == room_a
        assert ctx.actor_id == player
        assert ctx.params == {"x": 1}
        assert ctx.tick == 3
        assert isinstance(ctx.is_day, bool)
        assert isinstance(ctx.is_night, bool)
        # 窄 ctx：公开面无 World；内部仅 ``_world``
        assert not hasattr(type(ctx), "world")
        assert "world" not in vars(ctx)
        assert ctx._world is world  # noqa: SLF001


class TestDummyHookLifecycleS0:
    def test_direct_lifecycle_calls(self) -> None:
        world, room_a, room_b, player = _minimal_two_room_world()
        hook = RecordingHook()
        ctx = RoomHookContext(world, room_a, actor_id=player, tick=1)
        ctx.add_exit("east", room_b)
        ctx.schedule("boom", due_tick=1)
        hook.on_enter(ctx)
        assert world.require_component(room_a, RoomFreeState).data["last_enter"] == player
        assert any("哑钩子：有人进来了" in m for m in world.drain_messages(player))
        hook.on_leave(ctx)
        assert hook.leaves == [player]
        hook.on_tick(ctx)
        assert "east" not in world.require_component(room_a, Exits).by_direction
        assert any("崩塌" in m for m in world.drain_messages(player))

    def test_hook_exception_propagates(self) -> None:
        world, room_a, _room_b, player = _minimal_two_room_world()
        hook = ExplodingHook()
        ctx = RoomHookContext(world, room_a, actor_id=player)
        with pytest.raises(RuntimeError, match="钩子爆炸"):
            hook.on_enter(ctx)


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


_OFFICIAL_SCENE = """rooms:
  start:
    name: 起点
    exits:
      north: hooked
  hooked:
    name: 钩子房
    exits:
      south: start
    hooks:
      hook_id: test_dummy
      params:
        tag: s2
player:
  name: 你
  start_room: start
"""


class TestSceneHookMountS2:
    def test_official_track_loads_and_mounts(self, tmp_path: Path) -> None:
        hook = RecordingHook()
        register_room_hook("test_dummy", hook)
        world, player_id = load_scene(_write(tmp_path, "scene.yaml", _OFFICIAL_SCENE))
        assert world.pack_manifest is None
        hooked = world.room_ids["hooked"]
        binding = world.get_component(hooked, RoomHookBinding)
        assert binding is not None
        assert binding.hook_id == "test_dummy"
        assert binding.params == {"tag": "s2"}

        execute_line(world, player_id, "go north")
        assert player_id in hook.enters
        assert any("哑钩子：有人进来了" in m for m in world.drain_messages(player_id))

        execute_line(world, player_id, "go south")
        assert player_id in hook.leaves

    def test_unregistered_hook_id_fails_load(self, tmp_path: Path) -> None:
        scene = _OFFICIAL_SCENE.replace("test_dummy", "missing_hook")
        with pytest.raises(SceneLoadError, match="未注册|hooks|hook_id"):
            load_scene(_write(tmp_path, "scene.yaml", scene))

    def test_tick_subscription_runs_hook(self, tmp_path: Path) -> None:
        hook = RecordingHook()
        register_room_hook("test_dummy", hook)
        world, _player_id = load_scene(_write(tmp_path, "scene.yaml", _OFFICIAL_SCENE))
        loop = TickLoop(lambda: None, world=world, interval=1)
        loop.advance()
        assert hook.ticks  # on_tick 被订阅并调用

    def test_rooms_without_hooks_unaffected(self, tmp_path: Path) -> None:
        hook = RecordingHook()
        register_room_hook("test_dummy", hook)
        world, player_id = load_scene(_write(tmp_path, "scene.yaml", _OFFICIAL_SCENE))
        # 在起点 look / 不进钩子房 → 不触发 enter
        execute_line(world, player_id, "look")
        assert hook.enters == []


_UGC_BANDIT_MIN_VALUE_SCENE = """rooms:
  start:
    name: 起点
    exits:
      north: trail
  trail:
    name: 劫径
    exits:
      south: start
    objects:
      road_bandit: 0
    hooks:
      hook_id: bandit_ambush
      params:
        npc: road_bandit
        min_item_value: 100
npcs:
  road_bandit:
    name: 劫匪
player:
  name: 你
  start_room: start
"""


class TestUgcRejectsHooksS2:
    def test_pack_track_rejects_hooks_field(self, tmp_path: Path) -> None:
        pack = tmp_path / "pack"
        pack.mkdir()
        (pack / "manifest.yaml").write_text(
            "id: ugc_hooks\nversion: 0.0.1\n",
            encoding="utf-8",
        )
        (pack / "scene.yaml").write_text(_OFFICIAL_SCENE, encoding="utf-8")
        register_room_hook("test_dummy", RecordingHook())
        with pytest.raises(SceneLoadError, match="hooks|内容包|UGC|官方"):
            load_pack(pack)

    def test_pack_rejects_bandit_ambush_min_item_value_params(self, tmp_path: Path) -> None:
        """S3 / C12：UGC 包声明 hooks（含 min_item_value）仍必须失败——未打开缺口。"""
        pack = tmp_path / "pack"
        pack.mkdir()
        (pack / "manifest.yaml").write_text(
            "id: ugc_bandit\nversion: 0.0.1\n",
            encoding="utf-8",
        )
        (pack / "scene.yaml").write_text(_UGC_BANDIT_MIN_VALUE_SCENE, encoding="utf-8")
        with pytest.raises(SceneLoadError, match="hooks|内容包|UGC|官方"):
            load_pack(pack)

    def test_cli_validate_rejects_pack_hooks(self, tmp_path: Path) -> None:
        """``--pack --validate`` 与非严格 ``load_pack`` 对 hooks 同为失败判定。"""
        from mud_engine.__main__ import _main

        pack = tmp_path / "pack"
        pack.mkdir()
        (pack / "manifest.yaml").write_text(
            "id: ugc_hooks\nversion: 0.0.1\n",
            encoding="utf-8",
        )
        (pack / "scene.yaml").write_text(_OFFICIAL_SCENE, encoding="utf-8")
        register_room_hook("test_dummy", RecordingHook())
        assert _main(["--pack", str(pack), "--validate"]) == 1
        assert _main(["--pack", str(pack), "--validate", "--strict"]) == 1

    def test_mounted_hook_exception_propagates(self, tmp_path: Path) -> None:
        register_room_hook("test_dummy", ExplodingHook())
        world, player_id = load_scene(_write(tmp_path, "scene.yaml", _OFFICIAL_SCENE))
        with pytest.raises(RuntimeError, match="钩子爆炸"):
            execute_line(world, player_id, "go north")

    def test_restore_remounts_hooks(self, tmp_path: Path) -> None:
        from mud_engine.runtime import wire_runtime
        from mud_engine.save import restore_world, save_world

        hook = RecordingHook()
        register_room_hook("test_dummy", hook)
        world, player_id = load_scene(_write(tmp_path, "scene.yaml", _OFFICIAL_SCENE))
        save_world(world, player_id, tmp_path / "save")
        restored = restore_world(tmp_path / "save")
        assert restored is not None
        world2, player2 = restored
        assert world2.scene_path is not None
        wire_runtime(world2, world2.scene_path)
        execute_line(world2, player2, "go north")
        assert player2 in hook.enters


class TestRoomFreeStateSave:
    def test_free_state_roundtrip(self, tmp_path: Path) -> None:
        from mud_engine.save import restore_world, save_world

        register_room_hook("test_dummy", RecordingHook())
        world, player_id = load_scene(_write(tmp_path, "scene.yaml", _OFFICIAL_SCENE))
        hooked = world.room_ids["hooked"]
        world.add_component(hooked, RoomFreeState(data={"n": 2}, schedules={"x": 9}))
        save_root = tmp_path / "save"
        save_world(world, player_id, save_root)
        restored = restore_world(save_root)
        assert restored is not None
        world2, _pid2 = restored
        # restore 不重建 room_ids；按 RoomHookBinding 定位钩子房
        hooked_rooms = list(world2.entities_with(RoomHookBinding))
        assert len(hooked_rooms) == 1
        free = world2.require_component(hooked_rooms[0], RoomFreeState)
        assert free.data == {"n": 2}
        assert free.schedules == {"x": 9}
        binding = world2.require_component(hooked_rooms[0], RoomHookBinding)
        assert binding.hook_id == "test_dummy"
