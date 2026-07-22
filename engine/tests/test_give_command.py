"""pre-m4-channels-spawn-quest-01：give 命令（物品交给同房 NPC）。

seam：``execute_line`` + Container 可观察状态。不挂任务判定。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from mud_engine.components import Container, Identity, Position
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import load_scene
from mud_engine.world import EntityId, World


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def _load(tmp_path: Path, *, npc_has_container: bool = True) -> tuple[World, EntityId, EntityId]:
    """院子里一块石头 + 一名守卫；可选给守卫挂 Container。"""
    doc = {
        "rooms": {
            "yard": {
                "name": "院子",
                "long": "院子",
                "objects": {"stone": 1, "guard": 1},
            }
        },
        "items": {
            "stone": {
                "name": "石头",
                "aliases": ["石"],
                "short": "一块石头",
                "long": "一块普通的石头。",
            }
        },
        "npcs": {
            "guard": {
                "name": "石像守卫",
                "aliases": ["守卫"],
                "short": "一尊守卫",
                "long": "一尊石像。",
                "inquiry": {"default": "……"},
            }
        },
        "player": {"name": "你", "start_room": "yard"},
    }
    world, player_id = load_scene(_write_scene(tmp_path, yaml.dump(doc, allow_unicode=True)))
    npc = _npc_named(world, "石像守卫")
    assert npc is not None
    if npc_has_container and not world.has_component(npc, Container):
        world.add_component(npc, Container())
    return world, player_id, npc


def _npc_named(world: World, name: str) -> EntityId | None:
    for entity in world.entities_with(Identity, Position):
        if world.require_component(entity, Identity).name == name:
            return entity
    return None


def _item_in(world: World, holder: EntityId, name: str) -> EntityId | None:
    container = world.require_component(holder, Container)
    for item in container.items:
        if world.require_component(item, Identity).name == name:
            return item
    return None


class TestGive:
    class WhenPlayerHasItemAndNpcHasContainer:
        def test_moves_the_item_to_the_npc_container(self, tmp_path: Path) -> None:
            world, player_id, npc = _load(tmp_path)
            execute_line(world, player_id, "get 石头")
            execute_line(world, player_id, "give 石头 to 石像守卫")
            assert _item_in(world, player_id, "石头") is None
            assert _item_in(world, npc, "石头") is not None

        def test_reports_handing_it_over(self, tmp_path: Path) -> None:
            world, player_id, _ = _load(tmp_path)
            execute_line(world, player_id, "get 石头")
            messages = execute_line(world, player_id, "give 石头 to 石像守卫")
            assert any("交给了" in m and "石像守卫" in m for m in messages)

        def test_accepts_npc_alias(self, tmp_path: Path) -> None:
            world, player_id, npc = _load(tmp_path)
            execute_line(world, player_id, "get 石头")
            execute_line(world, player_id, "give 石 to 守卫")
            assert _item_in(world, npc, "石头") is not None

    class WhenArgumentsAreIncomplete:
        def test_returns_a_usage_hint(self, tmp_path: Path) -> None:
            world, player_id, _ = _load(tmp_path)
            messages = execute_line(world, player_id, "give")
            assert any("用法" in m or "给" in m for m in messages)

    class WhenItemIsNotInInventory:
        def test_returns_you_do_not_have_it(self, tmp_path: Path) -> None:
            world, player_id, npc = _load(tmp_path)
            messages = execute_line(world, player_id, "give 石头 to 石像守卫")
            assert any("你没有" in m for m in messages)
            assert _item_in(world, npc, "石头") is None

    class WhenNpcIsMissing:
        def test_returns_a_hint_and_changes_nothing(self, tmp_path: Path) -> None:
            world, player_id, _ = _load(tmp_path)
            execute_line(world, player_id, "get 石头")
            before = set(world.require_component(player_id, Container).items)
            messages = execute_line(world, player_id, "give 石头 to 路人甲")
            assert any("没有" in m for m in messages)
            assert set(world.require_component(player_id, Container).items) == before

    class WhenNpcHasNoContainer:
        def test_returns_a_hint_and_changes_nothing(self, tmp_path: Path) -> None:
            world, player_id, npc = _load(tmp_path, npc_has_container=False)
            assert not world.has_component(npc, Container)
            execute_line(world, player_id, "get 石头")
            before = set(world.require_component(player_id, Container).items)
            messages = execute_line(world, player_id, "give 石头 to 石像守卫")
            assert any("接" in m or "装不下" in m for m in messages)
            assert set(world.require_component(player_id, Container).items) == before

    class WhenItemIsNoDrop:
        def test_returns_no_drop_message_and_keeps_item(self, tmp_path: Path) -> None:
            doc = {
                "rooms": {
                    "yard": {
                        "name": "院子",
                        "objects": {"token": 1, "guard": 1},
                    }
                },
                "items": {
                    "token": {
                        "name": "令牌",
                        "no_drop": True,
                        "no_drop_message": "这是任务物品，不能丢弃。",
                    }
                },
                "npcs": {
                    "guard": {
                        "name": "石像守卫",
                        "inquiry": {"default": "……"},
                    }
                },
                "player": {"name": "你", "start_room": "yard"},
            }
            world, player_id = load_scene(
                _write_scene(tmp_path, yaml.dump(doc, allow_unicode=True))
            )
            npc = _npc_named(world, "石像守卫")
            assert npc is not None
            world.add_component(npc, Container())
            execute_line(world, player_id, "get 令牌")
            messages = execute_line(world, player_id, "give 令牌 to 石像守卫")
            assert any("不能丢弃" in m for m in messages)
            assert _item_in(world, player_id, "令牌") is not None
            assert _item_in(world, npc, "令牌") is None
