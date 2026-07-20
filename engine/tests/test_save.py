"""05 号票测试：存档与崩溃恢复。

覆盖 05 号票 acceptance：
- #3 存档/恢复一致性：save 后重新构建全新 world 实例从存档恢复，玩家位置、
  物品栏、房间地面物品、出口表（含动态增删）、门状态（含运行时变更）与保存前一致。
- #4 崩溃安全：存档写入中途被中断（模拟进程被杀）不破坏上一次已成功写入的存档，
  重启恢复到写入开始前的状态。
- #5 单条目损坏容错：单个 entity 文件被人为损坏时恢复跳过它 + 记警告，其余
  条目正常恢复，进程不拒绝启动。
- #6 存档格式人类可读：JSON，可人工打开检查。

测试只断言外部可观察行为（保存前后可查询的世界状态），不断言存档文件内部
具体字段布局（见 05 号票 acceptance 第 7 条）。

按 Given/When 场景分组成嵌套类，方法名只写 Then（见 engine/README.md「测试约定」）。
"""

import json
import logging
from pathlib import Path

import pytest

from mud_engine.components import Container, Doors, Exits, Identity, Position
from mud_engine.parsing import execute_line
from mud_engine.save import has_save, restore_world, save_world
from mud_engine.scene_loader import load_scene
from mud_engine.scenes import build_world
from mud_engine.world import EntityId, World


def _room_name(world: World, room_id: EntityId) -> str:
    return world.require_component(room_id, Identity).name


def _world_state(world: World, player_id: EntityId) -> dict:
    """提取可观察世界状态，跨 world 实例可比（用名字而非 entity id）。

    覆盖 05 验收 #3 列的全部状态：玩家位置、玩家物品栏、房间地面物品、出口表、
    门状态；顺带 NPC 在场（验证静态 NPC 也跨存档恢复）。
    """
    player_room_id = world.require_component(player_id, Position).room
    player_inv = sorted(
        _room_name(world, i) for i in world.require_component(player_id, Container).items
    )

    floors: dict[str, list[str]] = {}
    exits_map: dict[str, dict[str, str]] = {}
    doors_map: dict[str, dict[str, tuple]] = {}
    for room in world.entities_with(Identity, Exits):
        name = _room_name(world, room)
        container = world.get_component(room, Container)
        floors[name] = sorted(
            _room_name(world, i) for i in (container.items if container else set())
        )
        exits_map[name] = {
            d: _room_name(world, e.target)
            for d, e in world.require_component(room, Exits).by_direction.items()
        }
        doors = world.get_component(room, Doors)
        if doors is not None:
            dm: dict[str, tuple] = {}
            for direction, door in doors.by_direction.items():
                key_name = (
                    _room_name(world, door.key_item_id) if door.key_item_id is not None else None
                )
                dm[direction] = (door.state.value, key_name)
            doors_map[name] = dm

    npcs: dict[str, list[str]] = {}
    for entity in world.entities_with(Identity, Position):
        if entity == player_id:
            continue
        room = world.require_component(entity, Position).room
        npcs.setdefault(_room_name(world, room), []).append(_room_name(world, entity))
    npcs = {k: sorted(v) for k, v in npcs.items()}

    return {
        "player_room": _room_name(world, player_room_id),
        "player_inv": player_inv,
        "floors": floors,
        "exits": exits_map,
        "doors": doors_map,
        "npcs": npcs,
    }


def _mutate_state(world: World, player_id: EntityId) -> None:
    """把默认场景推进到一个"处处与初始态不同"的状态，供一致性比对。

    覆盖玩家位置/物品栏/地面物品/出口表（动态增）/门状态（运行时变更）五项：
    拿石头、开南门进储藏室、回庭院、去长廊拿钥匙并解锁+开北门、进静室、丢石头、
    给静室动态加一条 down 出口指向长廊。
    """
    execute_line(world, player_id, "get 石头")
    execute_line(world, player_id, "open south")
    execute_line(world, player_id, "go south")  # -> 储藏室
    execute_line(world, player_id, "go north")  # -> 起始庭院
    execute_line(world, player_id, "go north")  # -> 长廊
    corridor = world.require_component(player_id, Position).room
    execute_line(world, player_id, "get 钥匙")
    execute_line(world, player_id, "unlock north")
    execute_line(world, player_id, "open north")
    execute_line(world, player_id, "go north")  # -> 静室
    execute_line(world, player_id, "drop 石头")
    # 动态出口：静室加一条 down -> 长廊（静室原本是死胡同，无任何出口）。
    from mud_engine.components import Exit

    quiet = world.require_component(player_id, Position).room
    world.require_component(quiet, Exits).by_direction["down"] = Exit(target=corridor)


class TestSaveAndRestoreState:
    """05 验收 #3：save 后重新构建全新 world 实例从存档恢复，状态与保存前一致。"""

    def test_state_after_restore_matches_state_before_save(self, tmp_path) -> None:
        world, player_id = build_world()
        _mutate_state(world, player_id)
        before = _world_state(world, player_id)

        save_world(world, player_id, tmp_path)

        restored = restore_world(tmp_path)
        assert restored is not None
        world2, player2 = restored
        after = _world_state(world2, player2)
        assert after == before

    def test_restored_world_is_a_fresh_instance(self, tmp_path) -> None:
        # 恢复出的 world 与原 world 是独立对象：改一个不影响另一个的可观察状态。
        world, player_id = build_world()
        save_world(world, player_id, tmp_path)
        world2, player2 = restore_world(tmp_path)

        execute_line(world2, player2, "get 石头")  # 在恢复出的世界里拿石头
        # 原 world 的起始庭院地面仍有石头（未被波及）。
        start = world.require_component(player_id, Position).room
        floor = world.require_component(start, Container)
        assert any(world.require_component(i, Identity).name == "石头" for i in floor.items)

    def test_save_then_has_save_is_true(self, tmp_path) -> None:
        world, player_id = build_world()
        assert has_save(tmp_path) is False
        save_world(world, player_id, tmp_path)
        assert has_save(tmp_path) is True


class TestRestoredDynamicExitAndDoorChanges:
    """出口表运行时增删与门状态运行时变更跨存档恢复（验收 #3 的出口表/门状态项）。"""

    def test_dynamically_added_exit_survives_restore(self, tmp_path) -> None:
        world, player_id = build_world()
        start = world.require_component(player_id, Position).room
        corridor = world.require_component(start, Exits).by_direction["north"].target
        from mud_engine.components import Exit

        world.require_component(start, Exits).by_direction["up"] = Exit(target=corridor)
        save_world(world, player_id, tmp_path)

        world2, player2 = restore_world(tmp_path)
        start2 = world2.require_component(player2, Position).room
        exits2 = world2.require_component(start2, Exits)
        assert "up" in exits2.by_direction
        assert (
            exits2.by_direction["up"].target
            == world2.require_component(start2, Exits).by_direction["north"].target
        )  # up 与 north 指向同一个房间（长廊）

    def test_changed_door_state_survives_restore(self, tmp_path) -> None:
        from mud_engine.components import DoorState

        world, player_id = build_world()
        execute_line(world, player_id, "open south")  # 起始庭院 south 门从关变开
        save_world(world, player_id, tmp_path)

        world2, player2 = restore_world(tmp_path)
        start2 = world2.require_component(player2, Position).room
        door = world2.require_component(start2, Doors).by_direction["south"]
        assert door.state is DoorState.OPEN


class TestAtomicCrashSafety:
    """05 验收 #4：写入中途崩溃不破坏上一次已成功写入的存档，恢复到写入前状态。"""

    def test_crash_mid_save_leaves_previous_save_intact(self, tmp_path) -> None:
        # 第一次存档成功（状态 A），再改到状态 B 并让第二次存档中途崩溃，
        # 恢复应得到 A 而非 B（也不应是 A/B 混合）。
        world, player_id = build_world()
        execute_line(world, player_id, "get 石头")  # 状态 A：玩家持有石头
        save_world(world, player_id, tmp_path)
        state_a = _world_state(world, player_id)

        # 推进到状态 B（与 A 不同）。
        execute_line(world, player_id, "drop 石头")
        execute_line(world, player_id, "go north")  # 去长廊
        state_b = _world_state(world, player_id)
        assert state_b != state_a  # 确认 B 确实不同于 A

        written: list[EntityId] = []

        def crash_after_two(entity_id: EntityId) -> None:
            written.append(entity_id)
            if len(written) == 2:
                raise RuntimeError("模拟进程被杀")

        with pytest.raises(RuntimeError, match="模拟进程被杀"):
            save_world(world, player_id, tmp_path, on_entity_saved=crash_after_two)

        restored = restore_world(tmp_path)
        assert restored is not None
        world2, player2 = restored
        # 恢复到 A（上一次成功发布的快照），不是 B，也不是混合。
        assert _world_state(world2, player2) == state_a


class TestCorruptedEntryTolerance:
    """05 验收 #5：单个 entity 文件损坏时恢复跳过它 + 记警告，其余恢复，不拒绝启动。"""

    def _a_non_player_entity_file(self, tmp_path) -> object:
        """在已发布的存档里挑一个非玩家 entity 文件返回（Path）。"""
        snapshot_dir = (tmp_path / "current").resolve()
        files = sorted(snapshot_dir.glob("entity_*.json"))
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            if not data.get("is_player"):
                return f
        raise AssertionError("存档里找不到非玩家实体文件")

    def test_truncated_entry_is_skipped_and_others_restore(self, tmp_path, caplog) -> None:
        world, player_id = build_world()
        save_world(world, player_id, tmp_path)
        original_count = len(list(world.all_entities()))

        # 人为损坏一个非玩家存档条目（写半截 JSON）。
        target = self._a_non_player_entity_file(tmp_path)
        target.write_text("{ 损坏的半截 JSON", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            restored = restore_world(tmp_path)

        # 进程不拒绝启动：恢复了其余条目 + 玩家在。
        assert restored is not None
        world2, player2 = restored
        restored_count = len(list(world2.all_entities()))
        # 损坏的那一个被跳过：恢复后的实体数 = 原 - 1。
        assert restored_count == original_count - 1
        # 玩家仍在，且玩家位置/物品栏正常（其余条目正常恢复）。
        assert world2.require_component(player2, Position) is not None
        # 损坏被记录为警告。
        assert any("跳过" in r.message or "损坏" in r.message for r in caplog.records)

    def test_malformed_json_entry_is_skipped_without_crashing(self, tmp_path) -> None:
        world, player_id = build_world()
        save_world(world, player_id, tmp_path)
        target = self._a_non_player_entity_file(tmp_path)
        target.write_text("完全不是 JSON 的乱码 [[[", encoding="utf-8")

        restored = restore_world(tmp_path)  # 不应抛异常
        assert restored is not None


class TestSaveFormatHumanReadable:
    """05 验收 #6：存档文件人类可读（JSON，可人工打开检查）。"""

    def test_entity_file_is_readable_json_with_indent(self, tmp_path) -> None:
        world, player_id = build_world()
        save_world(world, player_id, tmp_path)
        snapshot_dir = (tmp_path / "current").resolve()
        a_file = next(snapshot_dir.glob("entity_*.json"))

        text = a_file.read_text(encoding="utf-8")
        # 多行 + 缩进（indent=2）才是"人类可读"而非单行 blob。
        assert "\n" in text
        record = json.loads(text)
        assert "id" in record
        assert "components" in record

    def test_player_entity_is_marked_in_its_file(self, tmp_path) -> None:
        # 玩家身份靠存档里的标记恢复，标记本身人类可读可见。
        world, player_id = build_world()
        save_world(world, player_id, tmp_path)
        snapshot_dir = (tmp_path / "current").resolve()
        player_file = snapshot_dir / f"entity_{player_id}.json"
        record = json.loads(player_file.read_text(encoding="utf-8"))
        assert record.get("is_player") is True


class TestNoSave:
    def test_restore_returns_none_when_no_save_exists(self, tmp_path) -> None:
        assert restore_world(tmp_path) is None
        assert has_save(tmp_path) is False


# 含未识别段的场景（顶层 world_rules + 物品 on_use/rules），供"不进存档"测试加载。
_PASSTHROUGH_SCENE = """
rooms:
  start_yard:
    name: 起始庭院
    long: 庭院
    exits:
      north: { to: corridor }
  corridor:
    name: 长廊
    long: 长廊
    exits:
      south: { to: start_yard }
items:
  stone:
    name: 石头
    long: 一块石头
    placed_in: start_yard
    on_use:
      effect:
        heal: 5
    rules:
      - when: is_night
        do: glow
player:
  name: 你
  start_room: start_yard
world_rules:
  - when: phase == night
    do: close_shops
"""


class TestPassthroughDataDoesNotEnterSave:
    """11 号票：透传数据是声明式静态数据、非运行时可变态，不进存档。

    场景数据里引擎不识别的段（顶层 world_rules/nature、物品 on_use/rules 等）由
    scene_loader 透传到 ``world.extension_data`` / ``entity_extension_data``，但存档
    只序列化运行时可变态（entities/components），故透传数据不落盘、restore 后为空。
    """

    @staticmethod
    def _load_scene_with_unknowns(tmp_path: Path) -> tuple[World, EntityId]:
        path = tmp_path / "scene.yaml"
        path.write_text(_PASSTHROUGH_SCENE, encoding="utf-8")
        return load_scene(path)

    def test_save_files_do_not_contain_passthrough_data(self, tmp_path: Path) -> None:
        world, player_id = self._load_scene_with_unknowns(tmp_path)
        save_root = tmp_path / "save"
        save_world(world, player_id, save_root)

        snapshot_dir = (save_root / "current").resolve()
        blob = "".join(f.read_text(encoding="utf-8") for f in snapshot_dir.glob("entity_*.json"))
        # 透传内容（顶层 world_rules、物品 on_use/rules）不落进任何 entity 存档文件。
        assert "on_use" not in blob
        assert "world_rules" not in blob
        assert "close_shops" not in blob
        assert "is_night" not in blob

    def test_restored_world_has_empty_extension_data(self, tmp_path: Path) -> None:
        world, player_id = self._load_scene_with_unknowns(tmp_path)
        save_root = tmp_path / "save"
        save_world(world, player_id, save_root)

        restored = restore_world(save_root)
        assert restored is not None
        world2, _ = restored
        # restore 不读 YAML、不重建透传数据：world 级扩展数据为空。
        assert world2.extension_data == {}
