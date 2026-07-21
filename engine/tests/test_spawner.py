"""M2-04：Spawner 蓝图注册表——template 全灭后扫描仍能补齐。

核心回归：desired_count=1 且 respawn=True 的模板，存活实例被手工全部移除后，
下一次 _spawn_scan 仍能按 SpawnerBlueprint 重建（旧实现从存活实例聚合 metas，
全灭后 template_key 消失，静默跳过）。
"""

from __future__ import annotations

from pathlib import Path

from mud_engine.ai import _spawn_scan
from mud_engine.components import Description, Identity, NpcSpawnMeta, Position
from mud_engine.scene_loader import load_scene
from mud_engine.world import World


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_SCENE_RESPAWN = """
rooms:
  yard:
    name: 院子
    exits: {}
npcs:
  gate_master:
    name: 门派掌门
    short: 一位掌门
    long: 门派唯一掌门。
    in_room: yard
    count: 1
    respawn: true
    inquiry:
      default: 少侠有礼。
  wanderer:
    name: 路人
    in_room: yard
    count: 1
    respawn: false
player:
  name: 你
  start_room: yard
"""


class TestSpawnerBlueprintTotalWipeout:
    def test_respawn_true_template_rebuilds_after_all_instances_removed(
        self, tmp_path: Path
    ) -> None:
        """template 全灭：从存活实例聚合会丢 template_key；蓝图注册表仍能发现缺口。"""
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE_RESPAWN))
        assert "gate_master" in world.spawners
        blueprint = world.spawners["gate_master"]
        assert blueprint.desired_count == 1
        assert blueprint.respawn is True

        victims = [
            e
            for e in world.entities_with(NpcSpawnMeta)
            if world.require_component(e, NpcSpawnMeta).template_key == "gate_master"
        ]
        assert len(victims) == 1
        old_meta_id = id(world.require_component(victims[0], NpcSpawnMeta))
        for entity in victims:
            world.destroy_entity(entity)

        assert not any(
            world.require_component(e, NpcSpawnMeta).template_key == "gate_master"
            for e in world.entities_with(NpcSpawnMeta)
        )

        _spawn_scan(world)

        rebuilt = [
            e
            for e in world.entities_with(NpcSpawnMeta)
            if world.require_component(e, NpcSpawnMeta).template_key == "gate_master"
        ]
        assert len(rebuilt) == 1
        npc = rebuilt[0]
        assert world.require_component(npc, Identity).name == blueprint.name
        assert world.require_component(npc, Description).short == blueprint.short
        assert world.require_component(npc, Description).long == blueprint.long
        assert world.require_component(npc, Position).room == blueprint.startroom
        meta = world.require_component(npc, NpcSpawnMeta)
        assert meta.desired_count == 1
        assert meta.respawn is True
        assert meta.startroom == blueprint.startroom
        # 新实例带全新 NpcSpawnMeta（不为上一实例对象）。
        assert id(meta) != old_meta_id

    def test_respawn_false_template_not_rebuilt_after_wipeout(self, tmp_path: Path) -> None:
        world, _ = load_scene(_write_scene(tmp_path, _SCENE_RESPAWN))
        victims = [
            e
            for e in world.entities_with(NpcSpawnMeta)
            if world.require_component(e, NpcSpawnMeta).template_key == "wanderer"
        ]
        assert len(victims) == 1
        world.destroy_entity(victims[0])
        _spawn_scan(world)
        assert not any(
            world.require_component(e, NpcSpawnMeta).template_key == "wanderer"
            for e in world.entities_with(NpcSpawnMeta)
        )

    def test_spawners_registered_once_per_template_key(self, tmp_path: Path) -> None:
        scene = """
rooms:
  yard:
    name: 院子
    exits: {}
npcs:
  patrol:
    name: 巡逻兵
    in_room: yard
    count: 3
    respawn: true
player:
  name: 你
  start_room: yard
"""
        world, _ = load_scene(_write_scene(tmp_path, scene))
        assert set(world.spawners) == {"patrol"}
        assert world.spawners["patrol"].desired_count == 3
        assert (
            len(
                [
                    e
                    for e in world.entities_with(NpcSpawnMeta)
                    if world.require_component(e, NpcSpawnMeta).template_key == "patrol"
                ]
            )
            == 3
        )
