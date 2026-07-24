"""M2-04：Spawner 蓝图注册表——template 全灭后扫描仍能补齐。

核心回归：desired_count=1 且 respawn=True 的模板，存活实例被手工全部移除后，
下一次 _spawn_scan 仍能按 SpawnerBlueprint 重建（旧实现从存活实例聚合 metas，
全灭后 template_key 消失，静默跳过）。

Polishing-09 / C11：房间 objects ``random_of`` 补刷期抽签（S2 + S4）。
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from openmud.ai import spawn_scan
from openmud.components import (
    Description,
    Exits,
    Identity,
    ItemSpawnMeta,
    NpcSpawnMeta,
    Position,
)
from openmud.scene_loader import SceneLoadError, load_scene


class _ScriptedChoiceRng(random.Random):
    """确定性 ``choice``：按序返回预设值，耗尽后回退到种子 Random。"""

    def __init__(self, picks: list[object], *, seed: int = 0) -> None:
        super().__init__(seed)
        self._picks = list(picks)

    def choice(self, seq):  # type: ignore[no-untyped-def]
        seq_list = list(seq)
        if self._picks:
            pick = self._picks.pop(0)
            if pick not in seq_list:
                raise AssertionError(f"scripted pick {pick!r} not in {seq_list!r}")
            return pick
        return super().choice(seq_list)


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_SCENE_RESPAWN = """rooms:
  yard:
    name: 院子
    exits: {}
    objects:
      gate_master: 1
      wanderer: 1
npcs:
  gate_master:
    name: 门派掌门
    short: 一位掌门
    long: 门派唯一掌门。
    respawn: true
    inquiry:
      default: 少侠有礼。
  wanderer:
    name: 路人
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
        old_entity = victims[0]
        for entity in victims:
            world.destroy_entity(entity)

        assert not any(
            world.require_component(e, NpcSpawnMeta).template_key == "gate_master"
            for e in world.entities_with(NpcSpawnMeta)
        )

        spawn_scan(world)

        rebuilt = [
            e
            for e in world.entities_with(NpcSpawnMeta)
            if world.require_component(e, NpcSpawnMeta).template_key == "gate_master"
        ]
        assert len(rebuilt) == 1
        npc = rebuilt[0]
        assert npc != old_entity  # 新实体，非复活原 id
        assert world.require_component(npc, Identity).name == blueprint.name
        assert world.require_component(npc, Description).short == blueprint.short
        assert world.require_component(npc, Description).long == blueprint.long
        assert world.require_component(npc, Position).room == blueprint.startroom
        meta = world.require_component(npc, NpcSpawnMeta)
        assert meta.desired_count == 1
        assert meta.respawn is True
        assert meta.startroom == blueprint.startroom

    def test_respawn_false_template_not_rebuilt_after_wipeout(self, tmp_path: Path) -> None:
        world, _ = load_scene(_write_scene(tmp_path, _SCENE_RESPAWN))
        victims = [
            e
            for e in world.entities_with(NpcSpawnMeta)
            if world.require_component(e, NpcSpawnMeta).template_key == "wanderer"
        ]
        assert len(victims) == 1
        world.destroy_entity(victims[0])
        spawn_scan(world)
        assert not any(
            world.require_component(e, NpcSpawnMeta).template_key == "wanderer"
            for e in world.entities_with(NpcSpawnMeta)
        )

    def test_spawners_registered_once_per_template_key(self, tmp_path: Path) -> None:
        scene = """rooms:
  yard:
    name: 院子
    exits: {}
    objects:
      patrol: 3
npcs:
  patrol:
    name: 巡逻兵
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


_SCENE_RANDOM_OBJECTS = """rooms:
  forest:
    name: 落日林
    exits:
      south:
        to: camp
    objects:
      wildlife:
        random_of:
        - crow
        - rabbit
        - snake
        count: 1
  camp:
    name: 营地
    exits:
      north:
        to: forest
      east:
        random_of:
        - lake_a
        - lake_b
  lake_a:
    name: 湖畔甲
    exits:
      west:
        to: camp
  lake_b:
    name: 湖畔乙
    exits:
      west:
        to: camp
npcs:
  crow:
    name: 乌鸦
    respawn: true
  rabbit:
    name: 野兔
    respawn: true
  snake:
    name: 毒蛇
    respawn: true
player:
  name: 你
  start_room: camp
"""


class TestRandomObjectsPoolC11:
    """C11：补刷期 objects 候选组抽签；与出口加载期 random_of 正交。"""

    def test_load_accepts_random_of_slot_shape(self, tmp_path: Path) -> None:
        world, _ = load_scene(
            _write_scene(tmp_path, _SCENE_RANDOM_OBJECTS),
            rng=_ScriptedChoiceRng(["lake_a", "crow"]),
        )
        assert ("forest", "wildlife") in world.random_object_slots
        bp = world.random_object_slots[("forest", "wildlife")]
        assert bp.candidates == ("crow", "rabbit", "snake")
        assert bp.desired_count == 1
        assert bp.respawn is True
        assert len(bp.slots) == 1
        eid = bp.slots[0]
        assert eid is not None
        assert world.require_component(eid, NpcSpawnMeta).template_key == "crow"
        # 候选模板登记蓝图但不占普通 spawn_scan 名额（desired_count=0）
        assert world.spawners["crow"].desired_count == 0
        assert world.spawners["rabbit"].desired_count == 0

    def test_rejects_mapping_without_random_of(self, tmp_path: Path) -> None:
        scene = """rooms:
  yard:
    name: 院子
    exits: {}
    objects:
      bad:
        count: 1
npcs:
  crow:
    name: 乌鸦
player:
  name: 你
  start_room: yard
"""
        with pytest.raises(SceneLoadError, match="random_of"):
            load_scene(_write_scene(tmp_path, scene))

    def test_rejects_slot_key_colliding_with_template(self, tmp_path: Path) -> None:
        scene = """rooms:
  yard:
    name: 院子
    exits: {}
    objects:
      crow:
        random_of:
        - crow
        - rabbit
npcs:
  crow:
    name: 乌鸦
    respawn: true
  rabbit:
    name: 野兔
    respawn: true
player:
  name: 你
  start_room: yard
"""
        with pytest.raises(SceneLoadError, match="不得与模板键同名|模板键"):
            load_scene(_write_scene(tmp_path, scene))

    def test_rejects_fixed_and_random_same_template(self, tmp_path: Path) -> None:
        scene = """rooms:
  yard:
    name: 院子
    exits: {}
    objects:
      crow: 1
      wildlife:
        random_of:
        - crow
        - rabbit
npcs:
  crow:
    name: 乌鸦
    respawn: true
  rabbit:
    name: 野兔
    respawn: true
player:
  name: 你
  start_room: yard
"""
        with pytest.raises(SceneLoadError, match="固定放置|random_of|冲突"):
            load_scene(_write_scene(tmp_path, scene))

    def test_spawn_scan_redraws_independent_of_exit_random_of(
        self, tmp_path: Path
    ) -> None:
        """补刷期 objects 抽签与出口加载期 random_of 不共用求值路径。

        出口在 load 时已定死为 lake_a；多次 spawn_scan 后出口目标不变，
        而 wildlife 槽位按注入 rng 依次抽到不同候选。
        """
        world, _ = load_scene(
            _write_scene(tmp_path, _SCENE_RANDOM_OBJECTS),
            rng=_ScriptedChoiceRng(["lake_a", "crow"]),
        )
        camp = world.room_ids["camp"]
        exits = world.require_component(camp, Exits)
        fixed_target = exits.by_direction["east"].target
        assert fixed_target == world.room_ids["lake_a"]

        bp = world.random_object_slots[("forest", "wildlife")]
        seen: list[str] = []
        for pick in ("rabbit", "snake", "crow"):
            eid = bp.slots[0]
            assert eid is not None
            world.destroy_entity(eid)
            spawn_scan(world, rng=_ScriptedChoiceRng([pick]))
            new_eid = bp.slots[0]
            assert new_eid is not None
            seen.append(world.require_component(new_eid, NpcSpawnMeta).template_key)
            # 出口目标仍为加载期选定，不受补刷抽签影响
            assert (
                world.require_component(camp, Exits).by_direction["east"].target
                == fixed_target
            )
        assert seen == ["rabbit", "snake", "crow"]

    def test_item_pool_load_and_respawn_redraw(self, tmp_path: Path) -> None:
        """物品候选组：S2 加载 + S4 补刷重抽（与 NPC 池对称）。"""
        scene = """rooms:
  yard:
    name: 院子
    exits: {}
    objects:
      scrap:
        random_of:
        - twig
        - pebble
items:
  twig:
    name: 小树枝
    respawn: true
  pebble:
    name: 石子
    respawn: true
npcs: {}
player:
  name: 你
  start_room: yard
"""
        world, _ = load_scene(
            _write_scene(tmp_path, scene),
            rng=_ScriptedChoiceRng(["twig"]),
        )
        bp = world.random_object_slots[("yard", "scrap")]
        assert bp.kind == "item"
        assert bp.candidates == ("twig", "pebble")
        eid = bp.slots[0]
        assert eid is not None
        assert world.require_component(eid, ItemSpawnMeta).template_key == "twig"
        world.destroy_entity(eid)
        spawn_scan(world, rng=_ScriptedChoiceRng(["pebble"]))
        new_eid = bp.slots[0]
        assert new_eid is not None
        assert world.require_component(new_eid, ItemSpawnMeta).template_key == "pebble"

    def test_rejects_mixed_item_and_npc_candidates(self, tmp_path: Path) -> None:
        scene = """rooms:
  yard:
    name: 院子
    exits: {}
    objects:
      mix:
        random_of:
        - twig
        - crow
items:
  twig:
    name: 小树枝
    respawn: true
npcs:
  crow:
    name: 乌鸦
    respawn: true
player:
  name: 你
  start_room: yard
"""
        with pytest.raises(SceneLoadError, match="不能混用|物品与 NPC"):
            load_scene(_write_scene(tmp_path, scene))

    def test_respawn_false_pool_does_not_refill(self, tmp_path: Path) -> None:
        scene = """rooms:
  yard:
    name: 院子
    exits: {}
    objects:
      critter:
        random_of:
        - crow
        - rabbit
npcs:
  crow:
    name: 乌鸦
    respawn: false
  rabbit:
    name: 野兔
    respawn: false
player:
  name: 你
  start_room: yard
"""
        world, _ = load_scene(
            _write_scene(tmp_path, scene),
            rng=_ScriptedChoiceRng(["crow"]),
        )
        bp = world.random_object_slots[("yard", "critter")]
        assert bp.respawn is False
        eid = bp.slots[0]
        assert eid is not None
        world.destroy_entity(eid)
        spawn_scan(world, rng=_ScriptedChoiceRng(["rabbit"]))
        assert bp.slots[0] is None or not world.has_entity(bp.slots[0])
        assert not any(
            world.require_component(e, NpcSpawnMeta).template_key in {"crow", "rabbit"}
            for e in world.entities_with(NpcSpawnMeta)
        )
