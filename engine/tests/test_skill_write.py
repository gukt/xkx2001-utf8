"""skill 读写 API 行为等价测试（B 类补全，对照 feature/skill.c）。

覆盖 set_skill / delete_skill / map_skill / prepare_skill + 读函数
query_skills / query_skill_map / query_skill_prepare。对照 LPC
[feature/skill.c](../../feature/skill.c) L14-78。

正式化前这些函数仅 stubs.py 薄包装（直接操作 dict），缺失 3 处 LPC 行为：
delete_skill 没清 learned、map/prepare_skill 没查 mapped_to 已学、无技能存在性
验证。本测试覆盖补齐后的等价行为。
"""

from __future__ import annotations

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import RoomDef
from xkx.runtime.components import Skills
from xkx.runtime.skill import (
    delete_skill,
    map_skill,
    prepare_skill,
    query_skill_map,
    query_skill_prepare,
    query_skills,
    set_skill,
)
from xkx.runtime.world import build_world, spawn_player


def _player_world() -> tuple:
    """构建 1 房间 + 1 玩家场景，返回 (world, player_eid)。"""
    room = RoomDef(id="room/test", short="测试", long="测试房间。")
    ir = compile_scene([room], [])
    world, _, _ = build_world(ir)
    pid = spawn_player(world, "测试玩家", "room/test")
    return world, pid


# ──────────────────────── set_skill（skill.c:17-25） ────────────────────────


def test_set_skill_sets_level():
    """set_skill 设等级（skill.c:23-24 skills[skill]=val）。"""
    world, pid = _player_world()
    set_skill(world, pid, "sword", 50)
    assert world.get(pid, Skills).levels["sword"] == 50


def test_set_skill_overwrites_existing():
    """set_skill 覆盖既有等级。"""
    world, pid = _player_world()
    set_skill(world, pid, "sword", 50)
    set_skill(world, pid, "sword", 120)
    assert world.get(pid, Skills).levels["sword"] == 120


def test_set_skill_auto_creates_skills_component():
    """无 Skills 组件时 set_skill 自动建并挂载（_ensure_skills get-or-create）。"""
    world, pid = _player_world()
    # 先移除 Skills 模拟无组件实体
    world.remove(pid, Skills)
    assert world.get(pid, Skills) is None
    set_skill(world, pid, "blade", 30)
    s = world.get(pid, Skills)
    assert s is not None
    assert s.levels["blade"] == 30


# ──────────────────────── delete_skill（skill.c:27-38） ────────────────────────


def test_delete_skill_removes_level():
    """delete_skill 删 levels（skill.c:30）。"""
    world, pid = _player_world()
    set_skill(world, pid, "sword", 50)
    assert delete_skill(world, pid, "sword") is True
    assert "sword" not in world.get(pid, Skills).levels


def test_delete_skill_also_clears_learned():
    """delete_skill 同时清 learned（补齐 LPC skill.c:31-33 map_delete learned）。

    正式化前 stubs 薄包装只删 levels 不删 learned，本测试锁定补齐行为。
    """
    world, pid = _player_world()
    set_skill(world, pid, "sword", 50)
    world.get(pid, Skills).learned["sword"] = 100
    assert delete_skill(world, pid, "sword") is True
    assert "sword" not in world.get(pid, Skills).learned


def test_delete_skill_returns_false_if_absent():
    """delete_skill 技能不存在返回 False（skill.c:35-37）。"""
    world, pid = _player_world()
    assert delete_skill(world, pid, "nope") is False


def test_delete_skill_returns_false_without_component():
    """无 Skills 组件 delete_skill 返回 False（不建空，对照 skill.c:29 mapp 检查）。"""
    world, pid = _player_world()
    world.remove(pid, Skills)
    assert delete_skill(world, pid, "sword") is False


# ──────────────────────── map_skill（skill.c:42-58） ────────────────────────


def test_map_skill_sets_when_mapped_to_learned():
    """map_skill mapped_to 已学则设映射（skill.c:56-57）。"""
    world, pid = _player_world()
    set_skill(world, pid, "dugu-jiujian", 200)
    map_skill(world, pid, "sword", "dugu-jiujian")
    assert world.get(pid, Skills).skill_map["sword"] == "dugu-jiujian"


def test_map_skill_skips_when_mapped_to_not_learned():
    """map_skill mapped_to 未学则不设（补齐 LPC skill.c:53 undefinedp 检查）。

    正式化前 stubs 薄包装不查 mapped_to 已学，本测试锁定补齐行为。
    """
    world, pid = _player_world()
    map_skill(world, pid, "sword", "dugu-jiujian")
    assert "sword" not in world.get(pid, Skills).skill_map


def test_map_skill_clears_when_none():
    """map_skill mapped_to=None 清除映射（skill.c:44-47）。"""
    world, pid = _player_world()
    set_skill(world, pid, "dugu-jiujian", 200)
    map_skill(world, pid, "sword", "dugu-jiujian")
    map_skill(world, pid, "sword")
    assert "sword" not in world.get(pid, Skills).skill_map


# ──────────────────────── prepare_skill（skill.c:62-78） ────────────────────────


def test_prepare_skill_sets_when_mapped_to_learned():
    """prepare_skill mapped_to 已学则设准备（skill.c:76-77）。"""
    world, pid = _player_world()
    set_skill(world, pid, "dugu-jiujian", 200)
    prepare_skill(world, pid, "sword", "dugu-jiujian")
    assert world.get(pid, Skills).skill_prepare["sword"] == "dugu-jiujian"


def test_prepare_skill_skips_when_mapped_to_not_learned():
    """prepare_skill mapped_to 未学则不设（补齐 LPC skill.c:73）。"""
    world, pid = _player_world()
    prepare_skill(world, pid, "sword", "dugu-jiujian")
    assert "sword" not in world.get(pid, Skills).skill_prepare


def test_prepare_skill_clears_when_none():
    """prepare_skill mapped_to=None 清除准备（skill.c:64-67）。"""
    world, pid = _player_world()
    set_skill(world, pid, "dugu-jiujian", 200)
    prepare_skill(world, pid, "sword", "dugu-jiujian")
    prepare_skill(world, pid, "sword")
    assert "sword" not in world.get(pid, Skills).skill_prepare


# ──────────────────────── 读函数（skill.c:14/111/116） ────────────────────────


def test_query_skills_returns_copy():
    """query_skills 返回 levels 副本，外部改不影响组件（skill.c:14）。"""
    world, pid = _player_world()
    set_skill(world, pid, "sword", 50)
    snapshot = query_skills(world, pid)
    snapshot["sword"] = 999
    assert world.get(pid, Skills).levels["sword"] == 50


def test_query_skill_map_returns_copy():
    """query_skill_map 返回 skill_map 副本（skill.c:111）。"""
    world, pid = _player_world()
    set_skill(world, pid, "dugu-jiujian", 200)
    map_skill(world, pid, "sword", "dugu-jiujian")
    snapshot = query_skill_map(world, pid)
    snapshot["sword"] = "tampered"
    assert world.get(pid, Skills).skill_map["sword"] == "dugu-jiujian"


def test_query_skill_prepare_returns_copy():
    """query_skill_prepare 返回 skill_prepare 副本（skill.c:116）。"""
    world, pid = _player_world()
    set_skill(world, pid, "dugu-jiujian", 200)
    prepare_skill(world, pid, "sword", "dugu-jiujian")
    snapshot = query_skill_prepare(world, pid)
    snapshot["sword"] = "tampered"
    assert world.get(pid, Skills).skill_prepare["sword"] == "dugu-jiujian"


def test_query_skills_empty_without_component():
    """无 Skills 组件读函数返回空 dict（非 raise）。"""
    world, pid = _player_world()
    world.remove(pid, Skills)
    assert query_skills(world, pid) == {}
    assert query_skill_map(world, pid) == {}
    assert query_skill_prepare(world, pid) == {}
