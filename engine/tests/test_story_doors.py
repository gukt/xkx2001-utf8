"""Pre-M4-06：剧情门三件套（耗钥 / 无向 / NPC 挡向）+ 翰林。

接缝：S1 ``execute_line``；S2 ``load_scene``；S3 ``load_mvp_scene``。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from mud_engine.components import (
    Container,
    DoorState,
    Exits,
    HiddenExits,
    Identity,
    NpcSpawnMeta,
    Position,
)
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import load_scene
from mud_engine.scenes import load_mvp_scene


def _write_scene(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def _story_scene() -> dict:
    return {
        "rooms": {
            "yard": {
                "name": "前院",
                "long": "前院。",
                "exits": {
                    "south": "street",
                    "west": "garden",
                    "east": {
                        "to": "inner",
                        "door": "locked",
                        "key": "story_key",
                        "consume_key": True,
                        "hidden_until_unlocked": True,
                    },
                },
                "block_exits": {"west": {"npc": "guard_npc"}},
                "objects": {"story_key": 1, "guard_npc": 1},
            },
            "street": {"name": "街上", "long": "街上。", "exits": {"north": "yard"}},
            "garden": {"name": "小园", "long": "小园。", "exits": {"east": "yard"}},
            "inner": {"name": "内院", "long": "内院。", "exits": {"west": "yard"}},
        },
        "items": {"story_key": {"name": "钥匙", "aliases": ["key"]}},
        "npcs": {"guard_npc": {"name": "门卫"}},
        "player": {"name": "你", "start_room": "street"},
    }


class TestConsumeKey:
    def test_story_unlock_consumes_key(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _story_scene()))
        execute_line(world, player_id, "go north")
        execute_line(world, player_id, "get 钥匙")
        assert any(
            world.require_component(i, Identity).name == "钥匙"
            for i in world.require_component(player_id, Container).items
        )
        lines = execute_line(world, player_id, "unlock east")
        assert any("解锁" in line for line in lines)
        bag = world.require_component(player_id, Container)
        assert not any(
            world.get_component(i, Identity) and world.require_component(i, Identity).name == "钥匙"
            for i in bag.items
        )

    def test_standard_unlock_keeps_key(self, tmp_path: Path) -> None:
        data = {
            "rooms": {
                "a": {
                    "name": "A",
                    "long": "A",
                    "exits": {
                        "north": {
                            "to": "b",
                            "door": "locked",
                            "key": "iron_key",
                        }
                    },
                    "objects": {"iron_key": 1},
                },
                "b": {"name": "B", "long": "B", "exits": {"south": "a"}},
            },
            "items": {"iron_key": {"name": "铁钥匙"}},
            "player": {"name": "你", "start_room": "a"},
        }
        world, player_id = load_scene(_write_scene(tmp_path, data))
        execute_line(world, player_id, "get 铁钥匙")
        execute_line(world, player_id, "unlock north")
        names = [
            world.require_component(i, Identity).name
            for i in world.require_component(player_id, Container).items
        ]
        assert "铁钥匙" in names


class TestHiddenUntilUnlocked:
    def test_hidden_exit_absent_until_unlock(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _story_scene()))
        execute_line(world, player_id, "go north")
        yard = world.room_ids["yard"]
        assert "east" not in world.require_component(yard, Exits).by_direction
        assert "east" in world.require_component(yard, HiddenExits).by_direction
        look = " ".join(execute_line(world, player_id, "look"))
        assert "east" not in look.split("出口：")[-1] if "出口：" in look else True

        before = world.require_component(player_id, Position).room
        go = execute_line(world, player_id, "go east")
        assert world.require_component(player_id, Position).room == before
        assert any("没有出口" in line for line in go)

        execute_line(world, player_id, "get 钥匙")
        execute_line(world, player_id, "unlock east")
        assert "east" in world.require_component(yard, Exits).by_direction
        assert "east" not in world.require_component(yard, HiddenExits).by_direction
        # 解锁后可走（门变为开）
        execute_line(world, player_id, "go east")
        assert world.require_component(player_id, Position).room == world.room_ids["inner"]


class TestBlockExits:
    def test_npc_blocks_direction(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _story_scene()))
        execute_line(world, player_id, "go north")
        before = world.require_component(player_id, Position).room
        lines = execute_line(world, player_id, "go west")
        assert world.require_component(player_id, Position).room == before
        assert any("挡" in line for line in lines)

        # 移走 NPC 后可通行
        npc = next(
            e
            for e in world.entities_in_room(before)
            if (m := world.get_component(e, NpcSpawnMeta)) and m.template_key == "guard_npc"
        )
        world.destroy_entity(npc)
        execute_line(world, player_id, "go west")
        assert world.require_component(player_id, Position).room == world.room_ids["garden"]


class TestOfficialHanlin:
    def _arrive_hanlin(self, world, player_id):
        execute_line(world, player_id, "go south")
        execute_line(world, player_id, "go south")
        execute_line(world, player_id, "go north")
        execute_line(world, player_id, "go north")
        execute_line(world, player_id, "go east")
        execute_line(world, player_id, "go northeast")
        return world.room_ids["yangzhou_hanlin"]

    def test_mvp_hanlin_npc_blocks_west(self) -> None:
        world, player_id = load_mvp_scene()
        hanlin = self._arrive_hanlin(world, player_id)
        assert world.require_component(player_id, Position).room == hanlin
        blocked = execute_line(world, player_id, "go west")
        assert any("挡" in line for line in blocked)

    def test_mvp_hanlin_hidden_east_until_unlock_consumes_key(self) -> None:
        world, player_id = load_mvp_scene()
        hanlin = self._arrive_hanlin(world, player_id)
        assert "east" not in world.require_component(hanlin, Exits).by_direction
        missing = execute_line(world, player_id, "go east")
        assert any("没有出口" in line for line in missing)

        execute_line(world, player_id, "get 闺房钥匙")
        execute_line(world, player_id, "unlock east")
        bag_names = [
            world.require_component(i, Identity).name
            for i in world.require_component(player_id, Container).items
        ]
        assert "闺房钥匙" not in bag_names
        execute_line(world, player_id, "go east")
        assert (
            world.require_component(player_id, Position).room
            == world.room_ids["yangzhou_hanlin_neiyuan"]
        )
