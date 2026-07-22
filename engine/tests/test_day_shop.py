"""Pre-M4-05：day_shop → 夜间拒入 entry_guard。

接缝：S2 ``load_scene``；S3 ``load_mvp_scene`` + Nature 相位。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mud_engine.components import EntryGuard, Position
from mud_engine.errors import SceneLoadError
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import load_scene
from mud_engine.scenes import load_mvp_scene


def _write_scene(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


_BASE_ROOMS = {
    "street": {
        "name": "街上",
        "long": "街上。",
        "exits": {"north": "shop"},
    },
    "shop": {
        "name": "铺子",
        "long": "铺子内。",
        "day_shop": True,
        "exits": {"south": "street"},
    },
}


class TestDayShopLoad:
    def test_compiles_to_entry_guard_is_day(self, tmp_path: Path) -> None:
        data = {
            "rooms": _BASE_ROOMS,
            "player": {"name": "你", "start_room": "street"},
        }
        world, _ = load_scene(_write_scene(tmp_path, data))
        shop = world.room_ids["shop"]
        guard = world.require_component(shop, EntryGuard)
        assert guard.condition == {"predicate": "is_day"}
        assert "晚上" in guard.deny_message or "夜" in guard.deny_message
        extras = world.entity_extension_data(shop)
        assert "day_shop" not in extras

    def test_conflict_with_handwritten_entry_guard(self, tmp_path: Path) -> None:
        rooms = {
            "street": _BASE_ROOMS["street"],
            "shop": {
                "name": "铺子",
                "long": "铺子内。",
                "day_shop": True,
                "entry_guard": {
                    "condition": {"predicate": "is_day"},
                    "deny_message": "不行。",
                },
                "exits": {"south": "street"},
            },
        }
        data = {"rooms": rooms, "player": {"name": "你", "start_room": "street"}}
        with pytest.raises(SceneLoadError, match="day_shop"):
            load_scene(_write_scene(tmp_path, data))


class TestDayShopRuntime:
    def test_day_allows_entry(self, tmp_path: Path) -> None:
        data = {
            "rooms": _BASE_ROOMS,
            "player": {"name": "你", "start_room": "street"},
        }
        world, player_id = load_scene(_write_scene(tmp_path, data))
        assert world.nature is not None
        for i, phase in enumerate(world.nature.phases):
            if phase.name in ("day", "dusk"):
                world.nature.phase_index = i
                break
        assert world.nature.is_day
        execute_line(world, player_id, "go north")
        assert world.require_component(player_id, Position).room == world.room_ids["shop"]

    def test_night_denies_entry(self, tmp_path: Path) -> None:
        data = {
            "rooms": _BASE_ROOMS,
            "player": {"name": "你", "start_room": "street"},
        }
        world, player_id = load_scene(_write_scene(tmp_path, data))
        assert world.nature is not None
        for i, phase in enumerate(world.nature.phases):
            if phase.name in ("night", "midnight", "dawn"):
                world.nature.phase_index = i
                break
        assert world.nature.is_night
        before = world.require_component(player_id, Position).room
        lines = execute_line(world, player_id, "go north")
        assert world.require_component(player_id, Position).room == before
        assert any("晚上" in line or "夜" in line or "不开" in line for line in lines)


class TestOfficialDatiepu:
    def _to_xidajie(self, world, player_id) -> None:
        execute_line(world, player_id, "go south")
        execute_line(world, player_id, "go south")
        execute_line(world, player_id, "go north")
        execute_line(world, player_id, "go north")
        execute_line(world, player_id, "go west")

    def test_mvp_blacksmith_has_day_shop_guard(self) -> None:
        world, _ = load_mvp_scene()
        shop = world.room_ids["yangzhou_datiepu"]
        guard = world.require_component(shop, EntryGuard)
        assert guard.condition.get("predicate") == "is_day"

    def test_mvp_blacksmith_day_allows_night_denies(self) -> None:
        world, player_id = load_mvp_scene()
        shop = world.room_ids["yangzhou_datiepu"]
        self._to_xidajie(world, player_id)
        assert "西大街" in " ".join(execute_line(world, player_id, "look"))

        assert world.nature is not None
        world.nature.seek_phase("day")
        execute_line(world, player_id, "go north")
        assert world.require_component(player_id, Position).room == shop
        execute_line(world, player_id, "go south")

        world.nature.seek_phase("night")
        street = world.require_component(player_id, Position).room
        lines = execute_line(world, player_id, "go north")
        assert world.require_component(player_id, Position).room == street
        assert any("晚上" in line or "不开" in line for line in lines)
