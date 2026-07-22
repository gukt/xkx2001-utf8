"""pre-m4-channels-spawn-quest-06：声明式 Quest（S1 + S3）。

seam：``execute_line`` + ``QuestProgress`` / ``Currency``；官方场景闭环用
``load_mvp_scene``。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mud_engine.components import Container, Currency, Identity, Position, QuestProgress
from mud_engine.parsing import execute_line
from mud_engine.save import restore_world, save_world
from mud_engine.scene_loader import SceneLoadError, load_scene
from mud_engine.scenes import load_mvp_scene
from mud_engine.world import EntityId, World


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_MINI = """rooms:
  biaoju:
    name: 镖局
    exits:
      north: {to: guide}
    objects:
      cargo: 1
      chief: 1
  guide:
    name: 向导房
    exits:
      south: {to: biaoju}
    objects:
      guide_npc: 1
items:
  cargo:
    name: 镖货
    short: 一箱镖货
npcs:
  chief:
    name: 镖头
    inquiry:
      default: 有镖要运吗？
  guide_npc:
    name: 向导
    inquiry:
      default: 来交镖？
player:
  name: 你
  start_room: biaoju
  currency: 10
quests:
  escort_run:
    name: 试运镖
    accept:
      require_npc: chief
    complete:
      give_item: cargo
      to_npc: guide_npc
    reward:
      currency: 50
"""


def _npc(world: World, name: str) -> EntityId:
    for entity in world.entities_with(Identity):
        if world.require_component(entity, Identity).name == name:
            return entity
    raise AssertionError(name)


class TestQuestAccept:
    class WhenSameRoomAsRequiredNpc:
        def test_accepts_and_marks_active(self, tmp_path: Path) -> None:
            world, player_id = load_scene(_write_scene(tmp_path, _MINI))
            messages = execute_line(world, player_id, "quest accept escort_run")
            assert any("接取" in m or "试运镖" in m for m in messages)
            progress = world.require_component(player_id, QuestProgress)
            assert progress.quests["escort_run"] == "active"

        def test_repeat_accept_rejected(self, tmp_path: Path) -> None:
            world, player_id = load_scene(_write_scene(tmp_path, _MINI))
            execute_line(world, player_id, "quest accept escort_run")
            messages = execute_line(world, player_id, "quest accept escort_run")
            assert any("已经" in m or "进行中" in m for m in messages)
            assert world.require_component(player_id, QuestProgress).quests["escort_run"] == "active"

    class WhenNotSameRoomAsRequiredNpc:
        def test_rejects_without_state_change(self, tmp_path: Path) -> None:
            world, player_id = load_scene(_write_scene(tmp_path, _MINI))
            guide_room = world.room_ids["guide"]
            world.require_component(player_id, Position).room = guide_room
            messages = execute_line(world, player_id, "quest accept escort_run")
            assert any("无法接取" in m or "不在" in m or "没有" in m for m in messages)
            assert "escort_run" not in world.require_component(player_id, QuestProgress).quests

    class WhenAskAboutWork:
        def test_ask_does_not_accept_quest(self, tmp_path: Path) -> None:
            world, player_id = load_scene(_write_scene(tmp_path, _MINI))
            execute_line(world, player_id, "ask 镖头 about 工作")
            assert "escort_run" not in world.require_component(player_id, QuestProgress).quests


class TestQuestCompleteViaGive:
    class WhenActiveQuestMatchesGive:
        def test_completes_rewards_and_consumes_item(self, tmp_path: Path) -> None:
            world, player_id = load_scene(_write_scene(tmp_path, _MINI))
            execute_line(world, player_id, "quest accept escort_run")
            execute_line(world, player_id, "get 镖货")
            world.require_component(player_id, Position).room = world.room_ids["guide"]
            before = world.require_component(player_id, Currency).amount
            messages = execute_line(world, player_id, "give 镖货 to 向导")
            assert any("完成" in m or "领赏" in m or "银两" in m for m in messages)
            progress = world.require_component(player_id, QuestProgress)
            assert progress.quests["escort_run"] == "completed"
            assert world.require_component(player_id, Currency).amount == before + 50
            guide = _npc(world, "向导")
            assert not world.require_component(guide, Container).items

        def test_ordinary_give_without_matching_quest_has_no_quest_copy(self, tmp_path: Path) -> None:
            # 未接任务时 give 仍是普通转移（向导有 Container）
            world, player_id = load_scene(_write_scene(tmp_path, _MINI))
            execute_line(world, player_id, "get 镖货")
            world.require_component(player_id, Position).room = world.room_ids["guide"]
            messages = execute_line(world, player_id, "give 镖货 to 向导")
            assert any("交给了" in m for m in messages)
            assert not any("完成" in m for m in messages)
            assert "escort_run" not in world.require_component(player_id, QuestProgress).quests


class TestQuestFlagsComplete:
    class WhenRequiredFlagsSatisfied:
        def test_completes_on_flag_set(self, tmp_path: Path) -> None:
            scene = """rooms:
  yard:
    name: 院子
    exits: {}
    objects:
      sage: 1
npcs:
  sage:
    name: 隐士
player:
  name: 你
  start_room: yard
  currency: 0
quests:
  flag_trial:
    name: 旗标试炼
    accept:
      require_npc: sage
    complete:
      flags:
        saw_omen: true
    reward:
      currency: 5
"""
            world, player_id = load_scene(_write_scene(tmp_path, scene))
            execute_line(world, player_id, "quest accept flag_trial")
            from mud_engine.quest import set_quest_flag

            msgs = set_quest_flag(world, player_id, "saw_omen", True)
            assert any("完成" in m for m in msgs)
            assert world.require_component(player_id, QuestProgress).quests["flag_trial"] == "completed"
            assert world.require_component(player_id, Currency).amount == 5


class TestQuestSaveRestore:
    def test_active_quest_survives_restore(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _MINI))
        execute_line(world, player_id, "quest accept escort_run")
        save_root = tmp_path / "save"
        save_world(world, player_id, save_root)
        restored = restore_world(save_root)
        assert restored is not None
        world2, player2 = restored
        assert world2.require_component(player2, QuestProgress).quests["escort_run"] == "active"


class TestOfficialEscortQuest:
    def test_biaoju_to_guide_loop(self) -> None:
        world, player_id = load_mvp_scene()
        assert "escort_delivery" in world.quests
        world.require_component(player_id, Position).room = world.room_ids["yangzhou_biaoju"]
        messages = execute_line(world, player_id, "quest accept escort_delivery")
        assert any("接取" in m or "镖" in m for m in messages)
        execute_line(world, player_id, "get 镖货")
        world.require_component(player_id, Position).room = world.room_ids["huashan_guide"]
        before = world.require_component(player_id, Currency).amount
        messages = execute_line(world, player_id, "give 镖货 to 向导")
        assert world.require_component(player_id, QuestProgress).quests["escort_delivery"] == "completed"
        assert world.require_component(player_id, Currency).amount > before
        assert any("完成" in m or "银两" in m or "赏" in m for m in messages)


class TestQuestSchemaRejects:
    def test_unknown_accept_npc_rejected(self, tmp_path: Path) -> None:
        doc = yaml.safe_load(_MINI)
        doc["quests"]["escort_run"]["accept"]["require_npc"] = "missing_npc"
        with pytest.raises(SceneLoadError, match="require_npc|未定义"):
            load_scene(_write_scene(tmp_path, yaml.dump(doc, allow_unicode=True)))
