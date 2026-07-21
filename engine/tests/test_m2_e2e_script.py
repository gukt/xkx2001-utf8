"""M2-26：六分区互联 + 端到端剧本（M2 收口）。

Seam：``load_mvp_scene`` + ``execute_line`` / ``TickLoop`` / 可查询组件状态。
不断言场景 YAML 内部结构快照。
"""

from __future__ import annotations

from collections import deque

from mud_engine.ai import spawn_scan
from mud_engine.combat_system import clear_engagement
from mud_engine.components import (
    Currency,
    Engaged,
    Exits,
    Faction,
    Identity,
    NpcSpawnMeta,
    Position,
    Riding,
    SkillLevels,
    Unconscious,
    Vitals,
)
from mud_engine.death_flow import handle_vitals_depleted
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import instantiate_item
from mud_engine.scenes import load_mvp_scene
from mud_engine.tick import TickLoop
from mud_engine.world import EntityId, World


def _room(world: World, key: str) -> EntityId:
    assert world.room_ids is not None
    return world.room_ids[key]


def _room_key(world: World, room: EntityId) -> str:
    assert world.room_ids is not None
    for key, entity in world.room_ids.items():
        if entity == room:
            return key
    raise AssertionError(f"room {room} not in room_ids")


def _npc_named(world: World, name: str, *, exclude: EntityId) -> EntityId:
    for entity in world.entities_with(Identity):
        if entity == exclude:
            continue
        if world.require_component(entity, Identity).name == name:
            return entity
    raise AssertionError(f"{name!r} not found")


def _wait_ferry_across(world: World, dock_key: str, *, ticks: int = 8) -> None:
    dock = _room(world, dock_key)
    exits = world.require_component(dock, Exits)
    if "across" in exits.by_direction:
        return
    for _ in range(ticks):
        TickLoop(lambda: None, world=world).advance()
        exits = world.require_component(dock, Exits)
        if "across" in exits.by_direction:
            return
    raise AssertionError(f"ferry across never appeared at {dock_key}")


def _reachable_keys(world: World, start_key: str) -> set[str]:
    """BFS 经静态 Exits + 渡口 across（若当前可见）。"""
    assert world.room_ids is not None
    seen: set[str] = set()
    queue: deque[str] = deque([start_key])
    while queue:
        key = queue.popleft()
        if key in seen:
            continue
        seen.add(key)
        exits = world.require_component(_room(world, key), Exits)
        for exit_info in exits.by_direction.values():
            nxt = _room_key(world, exit_info.target)
            if nxt not in seen:
                queue.append(nxt)
    return seen


PARTITION_PREFIXES = (
    "huashan_",
    "yangzhou_",
    "shaolin_",
    "wild_",
    "road_",
    "ferry_",
)


class TestM2GeographicConnectivity:
    def test_six_partitions_form_one_connected_graph(self) -> None:
        """从华山村出发，六个分区前缀房间均可到达（地理连贯性）。"""
        world, _ = load_mvp_scene()
        assert world.room_ids is not None
        # 渡口 across 可能初始不可见；推进到船靠西岸再测连通
        _wait_ferry_across(world, "ferry_west")
        reachable = _reachable_keys(world, "huashan_birth")
        for prefix in PARTITION_PREFIXES:
            keys = [k for k in world.room_ids if k.startswith(prefix)]
            assert keys, f"missing rooms for prefix {prefix}"
            assert any(k in reachable for k in keys), (
                f"partition {prefix} unreachable from huashan; "
                f"keys={keys} reachable_sample={sorted(reachable)[:12]}"
            )
        # 关键路径上的枢纽必须都在
        for key in (
            "huashan_birth",
            "road_huashan_yz",
            "yangzhou_guangchang",
            "yangzhou_dongmen",
            "road_yz_east",
            "wild_forest",
            "ferry_west",
            "ferry_east",
            "road_shaolin",
            "shaolin_shanmen",
        ):
            assert key in reachable

    def test_room_keys_have_no_duplicates_across_partitions(self) -> None:
        world, _ = load_mvp_scene()
        assert world.room_ids is not None
        keys = list(world.room_ids)
        assert len(keys) == len(set(keys))


class TestM2SpawnScanOnRealScene:
    def test_singleton_respawn_after_wipeout_on_mvp_scene(self) -> None:
        """04 号票回归：真实六分区场景下 desired_count=1 + respawn 全灭后仍补齐。"""
        world, _ = load_mvp_scene()
        assert "wild_bandit" in world.spawners
        blueprint = world.spawners["wild_bandit"]
        assert blueprint.desired_count == 1
        assert blueprint.respawn is True

        victims = [
            e
            for e in world.entities_with(NpcSpawnMeta)
            if world.require_component(e, NpcSpawnMeta).template_key == "wild_bandit"
        ]
        assert len(victims) == 1
        old = victims[0]
        world.destroy_entity(old)
        assert not any(
            world.require_component(e, NpcSpawnMeta).template_key == "wild_bandit"
            for e in world.entities_with(NpcSpawnMeta)
        )

        spawn_scan(world)
        rebuilt = [
            e
            for e in world.entities_with(NpcSpawnMeta)
            if world.require_component(e, NpcSpawnMeta).template_key == "wild_bandit"
        ]
        assert len(rebuilt) == 1
        assert rebuilt[0] != old
        assert world.require_component(rebuilt[0], Identity).name == "山贼"
        assert world.require_component(rebuilt[0], Position).room == blueprint.startroom


class TestM2PlayerDefeatBranch:
    def test_player_unconscious_then_revive_in_mvp_scene(self) -> None:
        """独立覆盖战败：昏迷 → 再次归零 → 死而复生。"""
        world, player_id = load_mvp_scene()
        world.require_component(player_id, Position).room = _room(world, "wild_forest")
        vitals = world.require_component(player_id, Vitals)
        vitals.qi_current = 0
        handle_vitals_depleted(world, player_id)
        assert world.has_component(player_id, Unconscious)
        assert any("昏迷" in m for m in world.pending_messages)

        handle_vitals_depleted(world, player_id)
        assert not world.has_component(player_id, Unconscious)
        assert any("死而复生" in m for m in world.pending_messages)
        assert world.require_component(player_id, Position).room == _room(
            world, "huashan_birth"
        )
        assert world.require_component(player_id, Vitals).qi_current > 0


class TestM2EndToEndScript:
    def test_full_mvp_journey_script(self) -> None:
        """华山教程 → 扬州买卖骑马 → 野外胜仗 → 渡口 → 少林拜师练功。"""
        world, player_id = load_mvp_scene()
        assert world.require_component(player_id, Position).room == _room(
            world, "huashan_birth"
        )

        # 教程对话
        execute_line(world, player_id, "go north")
        ask = execute_line(world, player_id, "ask 向导 about 战斗")
        assert any("attack" in line or "战斗" in line for line in ask)
        where = execute_line(world, player_id, "ask 向导 about 去哪")
        assert any("扬州" in line for line in where)

        # 战斗教学
        execute_line(world, player_id, "go east")
        attack = execute_line(world, player_id, "attack 稻草人")
        assert any("交战" in line for line in attack)
        TickLoop(lambda: None, world=world).advance()
        assert any("气血" in m or "稻草人" in m for m in world.pending_messages)
        if world.has_component(player_id, Engaged):
            clear_engagement(world, player_id, reason="e2e")

        # 沿官道前往扬州：练武场 → 广场 → 村口 → 官道 → 南门
        execute_line(world, player_id, "go west")
        execute_line(world, player_id, "go south")
        road_lines = execute_line(world, player_id, "go south")
        assert world.require_component(player_id, Position).room == _room(
            world, "road_huashan_yz"
        )
        assert any("官道" in line or "扬州" in line for line in road_lines)
        execute_line(world, player_id, "go south")
        assert world.require_component(player_id, Position).room == _room(
            world, "yangzhou_nanmen"
        )

        # 钱庄 buy + sell
        execute_line(world, player_id, "go north")  # 南大街
        execute_line(world, player_id, "go north")  # 广场
        execute_line(world, player_id, "go east")  # 东大街
        execute_line(world, player_id, "go north")  # 钱庄
        money_before = world.require_component(player_id, Currency).amount
        buy_note = execute_line(world, player_id, "buy 银票")
        assert any("银票" in line for line in buy_note)
        assert world.require_component(player_id, Currency).amount < money_before
        sell_note = execute_line(world, player_id, "sell 银票")
        assert any("银票" in line for line in sell_note)

        # 打铁铺 buy + sell
        execute_line(world, player_id, "go south")  # 东大街
        execute_line(world, player_id, "go west")  # 广场
        execute_line(world, player_id, "go west")  # 西大街
        execute_line(world, player_id, "go north")  # 打铁铺
        buy_blade = execute_line(world, player_id, "buy 钢刀")
        assert any("钢刀" in line for line in buy_blade)
        # 先留着钢刀给少林门禁拒绝用；另买一把再卖验证 sell
        money_mid = world.require_component(player_id, Currency).amount
        execute_line(world, player_id, "buy 钢刀")
        sell_blade = execute_line(world, player_id, "sell 钢刀")
        assert any("钢刀" in line for line in sell_blade)
        assert world.require_component(player_id, Currency).amount != money_mid

        # 马厩买马，官道骑乘
        execute_line(world, player_id, "go south")  # 西大街
        execute_line(world, player_id, "go south")  # 马厩
        buy_horse = execute_line(world, player_id, "buy 黄骠马")
        assert any("黄骠马" in line for line in buy_horse)
        ride = execute_line(world, player_id, "ride 黄骠马")
        assert any("骑上" in line for line in ride)
        assert world.has_component(player_id, Riding)

        # 经东门官道（骑马）→ 野外遭遇
        execute_line(world, player_id, "go north")  # 西大街
        execute_line(world, player_id, "go east")  # 广场
        execute_line(world, player_id, "go east")  # 东大街
        execute_line(world, player_id, "go east")  # 东门
        rode = execute_line(world, player_id, "go east")  # 官道
        assert world.require_component(player_id, Position).room == _room(
            world, "road_yz_east"
        )
        assert any("官道" in line or "东门" in line for line in rode)
        # 陡坡骑不过去：下马步行
        denied = execute_line(world, player_id, "go east")
        assert any("骑不过去" in line for line in denied)
        execute_line(world, player_id, "unride")
        execute_line(world, player_id, "go east")  # wild_edge
        execute_line(world, player_id, "go east")  # wild_forest

        bandit = _npc_named(world, "山贼", exclude=player_id)
        TickLoop(lambda: None, world=world).advance()
        if not world.has_component(player_id, Engaged):
            execute_line(world, player_id, "attack 山贼")
        world.require_component(player_id, Vitals).qi_current = 200
        world.require_component(player_id, Vitals).qi_max = 200
        money_fight = world.require_component(player_id, Currency).amount
        for _ in range(50):
            if not world.has_component(bandit, Vitals):
                break
            if world.require_component(bandit, Vitals).qi_current <= 0:
                break
            TickLoop(lambda: None, world=world).advance()
        money_after = world.require_component(player_id, Currency).amount
        skills_mid = world.get_component(player_id, SkillLevels)
        assert money_after > money_fight or (
            skills_mid is not None and any(p.exp > 0 for p in skills_mid.levels.values())
        ) or any("打倒" in m or "银" in m for m in world.pending_messages)
        if world.has_component(player_id, Engaged):
            clear_engagement(world, player_id, reason="e2e")

        # 渡口过河
        execute_line(world, player_id, "go east")  # thicket
        execute_line(world, player_id, "go east")  # ferry_west
        _wait_ferry_across(world, "ferry_west")
        ferry = execute_line(world, player_id, "go across")
        assert world.require_component(player_id, Position).room == _room(
            world, "ferry_east"
        )
        assert any("岸" in line or "渡" in line for line in ferry)

        # 少林山门：刃器拒绝 → 放下通过
        execute_line(world, player_id, "go east")  # road_shaolin
        # 确保身上有钢刀（若战斗/掉落丢失则补）
        from mud_engine.components import Container

        bag = world.get_component(player_id, Container)
        names = set()
        if bag is not None:
            for item in bag.items:
                names.add(world.require_component(item, Identity).name)
        if "钢刀" not in names:
            blade = instantiate_item(world, "steel_blade")
            if bag is None:
                world.add_component(player_id, Container())
                bag = world.require_component(player_id, Container)
            bag.items.add(blade)
        denied_gate = execute_line(world, player_id, "go east")
        assert any("刀" in line or "刃" in line or "兵器" in line for line in denied_gate)
        assert world.require_component(player_id, Position).room == _room(
            world, "road_shaolin"
        )
        execute_line(world, player_id, "drop 钢刀")
        entered = execute_line(world, player_id, "go east")
        assert world.require_component(player_id, Position).room == _room(
            world, "shaolin_shanmen"
        )
        assert not any("不得" in line for line in entered)

        # join → learn → practice
        execute_line(world, player_id, "go north")
        join = execute_line(world, player_id, "join 少林")
        assert any("加入了少林" in line for line in join)
        assert world.require_component(player_id, Faction).faction_id == "shaolin"

        execute_line(world, player_id, "go east")  # 武场
        learn = execute_line(world, player_id, "learn martial")
        assert any("学会了" in line for line in learn)
        skills = world.require_component(player_id, SkillLevels)
        assert "luohan_quan" in skills.levels
        exp_before = skills.levels["luohan_quan"].exp
        practice = execute_line(world, player_id, "practice luohan_quan")
        assert any("经验" in line for line in practice)
        assert (
            world.require_component(player_id, SkillLevels).levels["luohan_quan"].exp
            > exp_before
            or any("升到了" in line for line in practice)
        )
