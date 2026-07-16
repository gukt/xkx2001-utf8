"""reset_action 行为等价测试（B 类补全，对照 feature/attack.c:143-171）。

覆盖战斗动作集重算的 greenfield 等价范围（当前阶段，actions 闭包/招式表后置
M3 combat）：无 CombatState no-op、无武器 type 推断（unarmed/单 prepare/双
prepare）、skill_map 映射更新 attack_skill、有武器保留 wield 设值。
"""

from __future__ import annotations

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import RoomDef
from xkx.runtime.components import CombatState
from xkx.runtime.equipment import reset_action, wield
from xkx.runtime.skill import map_skill, prepare_skill, set_skill
from xkx.runtime.world import build_world, spawn_player


def _player_world() -> tuple:
    """构建 1 房间 + 1 玩家场景（spawn_player 挂 CombatState），返回 (world, eid)。"""
    room = RoomDef(id="room/test", short="测试", long="测试房间。")
    ir = compile_scene([room], [])
    world, _, _ = build_world(ir)
    pid = spawn_player(world, "测试玩家", "room/test")
    return world, pid


def test_reset_action_noop_without_combat_state():
    """无 CombatState 组件 reset_action no-op（不建空，不报错）。"""
    world, pid = _player_world()
    world.remove(pid, CombatState)
    reset_action(world, pid)
    assert world.get(pid, CombatState) is None  # 没建空


def test_reset_action_unarmed_no_prepare():
    """无武器无 prepare -> attack_skill='unarmed'（attack.c:153）。"""
    world, pid = _player_world()
    reset_action(world, pid)
    assert world.get(pid, CombatState).attack_skill == "unarmed"


def test_reset_action_single_prepare_no_map():
    """单 prepare 无映射 -> attack_skill=prepare 的 key（attack.c:154）。"""
    world, pid = _player_world()
    set_skill(world, pid, "dugu-jiujian", 200)
    prepare_skill(world, pid, "sword", "dugu-jiujian")
    reset_action(world, pid)
    assert world.get(pid, CombatState).attack_skill == "sword"


def test_reset_action_single_prepare_with_map():
    """单 prepare + skill_map 映射 -> attack_skill=mapped（attack.c:158）。"""
    world, pid = _player_world()
    set_skill(world, pid, "dugu-jiujian", 200)
    prepare_skill(world, pid, "sword", "dugu-jiujian")
    map_skill(world, pid, "sword", "dugu-jiujian")
    reset_action(world, pid)
    assert world.get(pid, CombatState).attack_skill == "dugu-jiujian"


def test_reset_action_double_prepare_takes_first():
    """双 prepare -> 按 action_flag 选（后置默认首个，attack.c:156）。"""
    world, pid = _player_world()
    set_skill(world, pid, "dugu-jiujian", 200)
    set_skill(world, pid, "taiji-quan", 200)
    prepare_skill(world, pid, "sword", "dugu-jiujian")
    prepare_skill(world, pid, "unarmed", "taiji-quan")
    reset_action(world, pid)
    # action_flag 后置默认取首个（dict 插入序首个 sword）
    assert world.get(pid, CombatState).attack_skill == "sword"


def test_reset_action_weapon_keeps_wield_attack_skill():
    """有武器 -> 保留 wield 设的 attack_skill（weapon skill_type 桥接后置）。"""
    world, pid = _player_world()
    wield(world, pid, "test-sword", props={}, skill="sword", label="测试剑")
    # wield 已把 attack_skill 设为 "sword"
    assert world.get(pid, CombatState).attack_skill == "sword"
    reset_action(world, pid)
    # 有武器：reset_action 不重算（weapon skill_type 桥接后置），保留 wield 设值
    assert world.get(pid, CombatState).attack_skill == "sword"
