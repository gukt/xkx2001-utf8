"""Pre-M4-11 收口：十类机关 S3 清单 + 与 m2_mvp_scene 互不干扰。

接缝：S3 ``load_xingxiu_mechanics`` / ``load_mvp_scene``；S2 内容包禁 hooks
（复核 ``test_room_hooks.TestUgcRejectsHooksS2``，本文件不重复造测）。
"""

from __future__ import annotations

from mud_engine.components import Exits, RoomHookBinding
from mud_engine.scenes import (
    MVP_SCENE_PATH,
    XINGXIU_MECHANICS_PATH,
    load_mvp_scene,
    load_xingxiu_mechanics,
)
from mud_engine.skills import get_skill_behavior

# 十类机关：房间键 → 期望 hook_id（``random_of`` / ``silk_rope`` 另测）
_HOOKED_ROOMS: dict[str, str] = {
    "dig_peak": "dig_collapse",
    "jade_gate": "multi_step_gate",
    "desert_maze": "lost_in_maze",
    "cliff_edge": "skill_gate",
    "cliff_base": "skill_gate",
    "sunlit_room": "time_of_day_passage",
    "magnetic_hall": "magnetic_iron",
    "ambush_trail": "bandit_ambush",
    "sun_moon_cave": "kill_order",
}


class TestXingxiuTenMechanicsInventoryS3:
    def test_official_slice_has_ten_mechanism_types(self) -> None:
        assert XINGXIU_MECHANICS_PATH.is_file()
        world, player_id = load_xingxiu_mechanics()
        assert world.pack_manifest is None
        assert player_id is not None

        for room_key, hook_id in _HOOKED_ROOMS.items():
            assert room_key in world.room_ids, room_key
            binding = world.require_component(
                world.room_ids[room_key], RoomHookBinding
            )
            assert binding.hook_id == hook_id

        # 机关 #2：加载期 random_of 落地为普通出口（无 hooks）
        assert "fork_hub" in world.room_ids
        hub = world.room_ids["fork_hub"]
        assert world.get_component(hub, RoomHookBinding) is None
        north = world.require_component(hub, Exits).by_direction["north"]
        assert north.target in (
            world.room_ids["fork_left"],
            world.room_ids["fork_right"],
        )

        # 机关 #10：SkillBehavior（非 RoomHook）+ 捕获房存在
        assert get_skill_behavior("silk_rope") is not None
        assert "silk_yard" in world.room_ids
        assert "silk_prison" in world.room_ids

    def test_mvp_scene_has_no_room_hooks_and_loads_independently(self) -> None:
        assert MVP_SCENE_PATH.is_file()
        assert MVP_SCENE_PATH.resolve() != XINGXIU_MECHANICS_PATH.resolve()
        world, player_id = load_mvp_scene()
        assert player_id is not None
        assert list(world.entities_with(RoomHookBinding)) == []
        # 扬州场景仍可独立加载（与星宿切片互不修改对方内容）
        assert "yangzhou_guangchang" in world.room_ids
        assert "dig_peak" not in world.room_ids
