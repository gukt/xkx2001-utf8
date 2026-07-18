"""场景数据 YAML 加载器测试：默认场景结构、静态展示型 NPC 可见性、加载期校验错误。

覆盖 06 号票 acceptance：① 房间/物品/NPC 从 YAML 加载；② 静态 NPC 在 look 中
可见且无任何专门行为；③ 引用不存在的房间键/缺字段等结构性错误给出清晰定位
（文件 + 大致出错的条目键），不是裸解析异常堆栈。按 Given/When 场景分组成
嵌套类，方法名只写 Then（见 engine/README.md「测试约定」）。
"""

from pathlib import Path

import pytest

from mud_engine.components import (
    Container,
    Description,
    Doors,
    DoorState,
    Exits,
    Identity,
    Position,
)
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import SceneLoadError, load_scene
from mud_engine.scenes import build_world
from mud_engine.world import EntityId, World


def _write_scene(tmp_path: Path, content: str) -> Path:
    """把一段 YAML 写到临时文件，返回路径（供加载期校验错误测试）。"""
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


# 一个最简合法场景，校验错误测试在此基础上做局部破坏。
_MINIMAL_SCENE = """
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
player:
  name: 你
  start_room: start_yard
"""


class TestLoadDefaultScene:
    def test_places_the_player_in_the_start_room(self) -> None:
        world, player_id = build_world()
        room = world.require_component(player_id, Position).room
        assert world.require_component(room, Identity).name == "起始庭院"

    def test_floor_item_is_placed_in_its_configured_room(self) -> None:
        world, player_id = build_world()
        start_room = world.require_component(player_id, Position).room
        floor = world.require_component(start_room, Container)
        assert len(floor.items) == 1
        item = next(iter(floor.items))
        assert world.require_component(item, Identity).name == "石头"

    def test_bidirectional_exits_are_loaded_explicitly(self) -> None:
        # YAML 里两个方向都显式声明（不做反向自动补全），与 01 号票行为等价：
        # start_yard north->corridor，corridor south->start_yard。
        world, player_id = build_world()
        start_room = world.require_component(player_id, Position).room
        start_exits = world.require_component(start_room, Exits)
        corridor = start_exits.by_direction["north"].target
        corridor_exits = world.require_component(corridor, Exits)
        assert corridor_exits.by_direction["south"].target == start_room

    def test_direction_aliases_survive_the_yaml_round_trip(self) -> None:
        world, player_id = build_world()
        start_room = world.require_component(player_id, Position).room
        exits = world.require_component(start_room, Exits)
        assert "北道" in exits.by_direction["north"].aliases


class TestStaticDisplayNpc:
    """06 号票新增的场景元素：只有 Identity+Description+Position、无任何行为的实体。"""

    def test_creates_an_entity_with_identity_description_and_position(self) -> None:
        world, player_id = build_world()
        npc = _find_npc_in_start_room(world, player_id)
        assert npc is not None
        assert world.require_component(npc, Identity).name == "石像守卫"
        assert world.has_component(npc, Description)
        assert world.has_component(npc, Position)

    def test_npc_is_not_in_the_rooms_item_container(self) -> None:
        # NPC 用 Position 表达"在房间里"，不进房间的 Container--否则会被 take。
        world, player_id = build_world()
        npc = _find_npc_in_start_room(world, player_id)
        assert npc is not None
        start_room = world.require_component(player_id, Position).room
        floor = world.require_component(start_room, Container)
        assert npc not in floor.items

    def test_npc_is_visible_when_the_player_looks(self) -> None:
        # 06 号票 acceptance：look 该房间能看到 NPC 的存在。
        world, player_id = build_world()
        combined = " ".join(execute_line(world, player_id, "look"))
        assert "石像守卫" in combined

    def test_npc_does_not_respond_to_take(self) -> None:
        # 静态展示型 NPC 无任何专门为它设计的命令；take 它像 take 一个不存在的物品。
        world, player_id = build_world()
        messages = execute_line(world, player_id, "take 石像守卫")
        assert any("这里没有" in m for m in messages)


class TestDoorsInScene:
    """04 号票：门/锁状态从 YAML 加载到独立的 Doors 组件（door/key 字段）。"""

    def test_closed_door_state_is_loaded(self) -> None:
        world, player_id = build_world()
        start_room = world.require_component(player_id, Position).room
        doors = world.require_component(start_room, Doors)
        assert doors.by_direction["south"].state is DoorState.CLOSED
        assert doors.by_direction["south"].key_item_id is None

    def test_locked_door_state_binds_the_key_item_entity(self) -> None:
        world, player_id = build_world()
        start_room = world.require_component(player_id, Position).room
        corridor = world.require_component(start_room, Exits).by_direction["north"].target
        doors = world.require_component(corridor, Doors)
        door = doors.by_direction["north"]
        assert door.state is DoorState.LOCKED
        assert door.key_item_id is not None
        assert world.require_component(door.key_item_id, Identity).name == "铁钥匙"

    def test_room_without_doors_has_no_doors_component(self) -> None:
        world, player_id = build_world()
        start_room = world.require_component(player_id, Position).room
        corridor = world.require_component(start_room, Exits).by_direction["north"].target
        quiet_room = world.require_component(corridor, Exits).by_direction["north"].target
        assert not world.has_component(quiet_room, Doors)

    def test_door_field_is_optional(self, tmp_path: Path) -> None:
        # 不写 door 字段的出口 = 无门、自由通行，房间不挂 Doors 组件。
        path = _write_scene(tmp_path, _MINIMAL_SCENE)
        world, player_id = load_scene(path)
        start_room = world.require_component(player_id, Position).room
        assert not world.has_component(start_room, Doors)

    def test_dangling_door_key_mentions_room_and_item(self, tmp_path: Path) -> None:
        scene = """
rooms:
  start_yard:
    name: 起始庭院
    long: 庭院
    exits:
      north:
        to: corridor
        door: locked
        key: missing_key
  corridor:
    name: 长廊
    long: 长廊
    exits:
      south: { to: start_yard }
player:
  name: 你
  start_room: start_yard
"""
        path = _write_scene(tmp_path, scene)
        with pytest.raises(SceneLoadError) as exc_info:
            load_scene(path)
        msg = str(exc_info.value)
        assert "start_yard" in msg
        assert "missing_key" in msg

    def test_invalid_door_state_value_raises_with_location(self, tmp_path: Path) -> None:
        scene = """
rooms:
  start_yard:
    name: 起始庭院
    long: 庭院
    exits:
      north:
        to: corridor
        door: ajar
  corridor:
    name: 长廊
    long: 长廊
    exits:
      south: { to: start_yard }
player:
  name: 你
  start_room: start_yard
"""
        path = _write_scene(tmp_path, scene)
        with pytest.raises(SceneLoadError) as exc_info:
            load_scene(path)
        msg = str(exc_info.value)
        assert "start_yard" in msg
        assert "ajar" in msg
        assert "north" in msg


class TestSceneLoadErrors:
    """加载期结构性错误：抛 SceneLoadError，消息带文件路径与出错的数据键定位，
    不让裸 Python 异常堆栈糊到启动者脸上（06 号票 acceptance 第 4 条）。"""

    def test_dangling_exit_target_mentions_file_and_keys(self, tmp_path: Path) -> None:
        path = _write_scene(
            tmp_path, _MINIMAL_SCENE.replace("to: corridor", "to: nonexistent_room")
        )
        with pytest.raises(SceneLoadError) as exc_info:
            load_scene(path)
        msg = str(exc_info.value)
        assert "start_yard" in msg
        assert "nonexistent_room" in msg

    def test_dangling_item_placement_mentions_file_and_keys(self, tmp_path: Path) -> None:
        path = _write_scene(
            tmp_path,
            _MINIMAL_SCENE
            + """
items:
  stone:
    name: 石头
    long: 一块石头
    placed_in: nonexistent_room
""",
        )
        with pytest.raises(SceneLoadError) as exc_info:
            load_scene(path)
        msg = str(exc_info.value)
        assert "stone" in msg
        assert "nonexistent_room" in msg

    def test_dangling_npc_room_mentions_file_and_keys(self, tmp_path: Path) -> None:
        path = _write_scene(
            tmp_path,
            _MINIMAL_SCENE
            + """
npcs:
  guard:
    name: 石像守卫
    long: 一尊石像。
    in_room: nonexistent_room
""",
        )
        with pytest.raises(SceneLoadError) as exc_info:
            load_scene(path)
        msg = str(exc_info.value)
        assert "guard" in msg
        assert "nonexistent_room" in msg

    def test_dangling_player_start_room_mentions_the_key(self, tmp_path: Path) -> None:
        path = _write_scene(
            tmp_path,
            _MINIMAL_SCENE.replace("start_room: start_yard", "start_room: nonexistent_room"),
        )
        with pytest.raises(SceneLoadError) as exc_info:
            load_scene(path)
        assert "nonexistent_room" in str(exc_info.value)

    def test_missing_room_name_mentions_the_room_and_field(self, tmp_path: Path) -> None:
        path = _write_scene(tmp_path, _MINIMAL_SCENE.replace("    name: 起始庭院\n", ""))
        with pytest.raises(SceneLoadError) as exc_info:
            load_scene(path)
        msg = str(exc_info.value)
        assert "start_yard" in msg
        assert "name" in msg

    def test_malformed_yaml_raises_scene_load_error(self, tmp_path: Path) -> None:
        # 未闭合的引号 -> PyYAML 抛 YAMLError，加载器收口成 SceneLoadError。
        path = _write_scene(tmp_path, 'rooms: "未闭合的引号')
        with pytest.raises(SceneLoadError):
            load_scene(path)

    def test_error_message_includes_the_file_path(self, tmp_path: Path) -> None:
        path = _write_scene(tmp_path, _MINIMAL_SCENE.replace("to: corridor", "to: missing"))
        with pytest.raises(SceneLoadError) as exc_info:
            load_scene(path)
        assert str(path) in str(exc_info.value)


def _find_npc_in_start_room(world: World, player_id: EntityId) -> EntityId | None:
    """玩家起始房间里、除玩家本人外的 Position 持有者（即静态展示型 NPC）。"""
    start_room = world.require_component(player_id, Position).room
    for entity in world.entities_with(Position):
        if entity == player_id:
            continue
        if world.require_component(entity, Position).room == start_room:
            return entity
    return None
