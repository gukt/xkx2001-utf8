"""M2-01：房间级 / NPC 级能力注册表（H1 prefactor）测试。

验收 seam：注册表驱动的已知字段聚合 + 未知字段仍透传到 entity_extension_data；
现有 scene_loader / save 行为不回归（由既有测试覆盖）。
"""

from pathlib import Path

from mud_engine.capabilities import NPC_CAPABILITIES, ROOM_CAPABILITIES
from mud_engine.components import Description, Inquiry, Position
from mud_engine.scene_loader import load_scene
from mud_engine.world import EntityId, World


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_SCENE = """rooms:
  yard:
    name: 院子
    outdoors: true
    custom_room_flag: room-extra
    exits: {}
    objects:
      guard: 1
npcs:
  guard:
    name: 守卫
    inquiry:
      default: 哼。
    custom_npc_flag: npc-extra
player:
  name: 你
  start_room: yard
"""


class TestRoomNpcCapabilityRegistries:
    def test_unknown_room_field_goes_to_extension_data(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        room = world.require_component(player_id, Position).room
        extras = world.entity_extension_data(room)
        assert extras["custom_room_flag"] == "room-extra"
        # outdoors 是注册表已知字段，不得被当成未识别透传。
        assert "outdoors" not in extras
        assert world.require_component(room, Description).outdoors is True

    def test_unknown_npc_field_goes_to_extension_data(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        npc = _find_npc(world, player_id)
        extras = world.entity_extension_data(npc)
        assert extras["custom_npc_flag"] == "npc-extra"
        assert "inquiry" not in extras
        assert world.has_component(npc, Inquiry)

    def test_room_and_npc_registries_expose_capability_spec_shape(self) -> None:
        assert ROOM_CAPABILITIES
        assert NPC_CAPABILITIES
        for spec in (*ROOM_CAPABILITIES, *NPC_CAPABILITIES):
            assert hasattr(spec, "component_type")
            assert hasattr(spec, "known_fields")
            assert callable(spec.from_yaml)
            assert callable(spec.to_dict)
            assert callable(spec.from_dict)


def _find_npc(world: World, player_id: EntityId) -> EntityId:
    room = world.require_component(player_id, Position).room
    for entity in world.entities_in_room(room, exclude=player_id):
        return entity
    raise AssertionError("expected an NPC in the start room")
