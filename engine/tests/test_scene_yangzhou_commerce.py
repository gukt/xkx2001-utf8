"""M2-23：扬州商业地标 + 马厩（buy/sell + 坐骑购买）。

Seam：``load_mvp_scene`` + ``execute_line``。
"""

from __future__ import annotations

from openmud.components import Currency, Exits, Identity, Mount, Position, Riding
from openmud.parsing import execute_line
from openmud.scenes import load_mvp_scene
from openmud.world import EntityId, World


def _room(world: World, key: str) -> EntityId:
    assert world.room_ids is not None
    return world.room_ids[key]


def _move_to(world: World, player_id: EntityId, key: str) -> None:
    world.require_component(player_id, Position).room = _room(world, key)


class TestYangzhouCommerceAndStable:
    def test_six_landmarks_plus_stable_keys(self) -> None:
        world, _ = load_mvp_scene()
        assert world.room_ids is not None
        for key in (
            "yangzhou_kedian",
            "yangzhou_qianzhuang",
            "yangzhou_datiepu",
            "yangzhou_biaoju",
            "yangzhou_wumiao",
            "yangzhou_chaguan",
            "yangzhou_stable",
        ):
            assert key in world.room_ids

    def test_landmarks_reachable_from_hub_graph(self) -> None:
        world, _ = load_mvp_scene()
        # 客栈挂北大街；钱庄/茶馆挂东大街；打铁铺/马厩挂西大街；镖局挂南大街；武庙挂广场
        beidajie = world.require_component(_room(world, "yangzhou_beidajie"), Exits)
        assert beidajie.by_direction["east"].target == _room(world, "yangzhou_kedian")
        dong = world.require_component(_room(world, "yangzhou_dongdajie"), Exits)
        assert dong.by_direction["north"].target == _room(world, "yangzhou_qianzhuang")
        assert dong.by_direction["south"].target == _room(world, "yangzhou_chaguan")
        xi = world.require_component(_room(world, "yangzhou_xidajie"), Exits)
        assert xi.by_direction["north"].target == _room(world, "yangzhou_datiepu")
        assert xi.by_direction["south"].target == _room(world, "yangzhou_stable")
        nan = world.require_component(_room(world, "yangzhou_nandajie"), Exits)
        assert nan.by_direction["west"].target == _room(world, "yangzhou_biaoju")
        square = world.require_component(_room(world, "yangzhou_guangchang"), Exits)
        assert square.by_direction["northeast"].target == _room(world, "yangzhou_wumiao")

    def test_bank_buy_and_sell(self) -> None:
        world, player_id = load_mvp_scene()
        _move_to(world, player_id, "yangzhou_qianzhuang")
        world.require_component(player_id, Currency).amount = 100
        buy = execute_line(world, player_id, "buy 银票")
        assert any("银票" in line for line in buy)
        assert world.require_component(player_id, Currency).amount < 100
        sell = execute_line(world, player_id, "sell 银票")
        assert any("银票" in line and ("两" in line or "银" in line) for line in sell)

    def test_smith_buy_and_sell(self) -> None:
        world, player_id = load_mvp_scene()
        _move_to(world, player_id, "yangzhou_datiepu")
        world.require_component(player_id, Currency).amount = 200
        buy = execute_line(world, player_id, "buy 钢刀")
        assert any("钢刀" in line for line in buy)
        sell = execute_line(world, player_id, "sell 钢刀")
        assert any("钢刀" in line for line in sell)

    def test_stable_buy_mount_then_ride(self) -> None:
        world, player_id = load_mvp_scene()
        _move_to(world, player_id, "yangzhou_stable")
        world.require_component(player_id, Currency).amount = 200
        buy = execute_line(world, player_id, "buy 黄骠马")
        assert any("黄骠马" in line for line in buy)
        ride = execute_line(world, player_id, "ride 黄骠马")
        assert any("骑上" in line for line in ride)
        assert world.has_component(player_id, Riding)
        mount = world.require_component(player_id, Riding).mount_id
        assert world.has_component(mount, Mount)

    def test_display_npcs_present(self) -> None:
        world, _ = load_mvp_scene()
        names = {world.require_component(e, Identity).name for e in world.entities_with(Identity)}
        for name in ("店小二", "钱庄伙计", "铁匠", "镖头", "庙祝", "茶博士", "马夫"):
            assert name in names
