"""HealSystem：自然恢复系统（阶段 2.2，对照 LPC feature/damage.c heal_up）。

tick 驱动自然恢复 qi/jing/jingli/neili + eff_qi/eff_jing 缓慢恢复。受战斗状态
影响（战斗中恢复速率约 1/3），water/food 耗尽时玩家停止恢复。完全确定性无 random。

核心不变量（三层资源，[spec/layer_f](_heal_up_spec) invariant）：
- 0 <= qi <= eff_qi <= max_qi（jing 同理）
- jingli <= max_jingli * 2（可超 max，上限 max*2）
- neili <= max_neili

heal_up 恢复规则（对照 feature/damage.c:270-331）：
1. water/food 每 tick -1（>0 时）
2. water/food < 1 且玩家 -> 停止恢复（脱水/饥饿）
3. jing += fighting ? con/9+max_jingli/30 : con/3+max_jingli/10，钳位 eff_jing
4. jing >= eff_jing 时 eff_jing++（达上限后才涨上限，上限 max_jing）
5. qi 同理（eff_qi）
6. jingli += fighting ? (str+dex)/12 : (str+dex)/4（仅 max_jingli>0 且 <max 时），上限 max*2
7. neili += fighting ? force/6 : force/2（仅 max_neili>0 且 <max 时），上限 max

[spec/layer_f_death.py](../spec/layer_f_death.py) /
[feature/damage.c](../../../feature/damage.c)
"""

from __future__ import annotations

from xkx.runtime.components import (
    Attributes,
    CombatState,
    Identity,
    Skills,
    Vitals,
)
from xkx.runtime.ecs import World
from xkx.runtime.systems import System


class HealSystem(System):
    """自然恢复 System（2.2，tick 驱动 heal_up）。

    每 tick 遍历有 Vitals 的实体调 heal_up。非均匀 tick 由 Engine.tick 驱动
    （1s 基准），heal_up 本身每 tick 调用（greenfield 简化；LPC heart_beat 内
    heal_up 每 5-14 秒子 tick 触发，非均匀后置）。
    """

    name = "HealSystem"

    def update(self, world: World, tick: int) -> None:
        for eid in list(world.entities_with(Vitals)):
            heal_up(world, eid)


def heal_up(world: World, eid: int) -> int:
    """自然恢复（对照 LPC feature/damage.c:270-331 heal_up）。

    返回 update_flag（>0 表示有属性更新，0 无变化）。完全确定性无 random。
    """
    vitals = world.get(eid, Vitals)
    if vitals is None:
        return 0
    update_flag = 0
    identity = world.get(eid, Identity)
    is_player = identity is not None and identity.is_player
    combat = world.get(eid, CombatState)
    fighting = combat is not None and combat.is_fighting

    # 1. water/food 递减（>0 时）
    if vitals.water > 0:
        vitals.water -= 1
        update_flag += 1
    if vitals.food > 0:
        vitals.food -= 1
        update_flag += 1

    # 2. 玩家 water/food < 1 停止恢复（脱水/饥饿）
    if is_player and (vitals.water < 1 or vitals.food < 1):
        _mark_dirty(world, eid)
        return update_flag

    attrs = world.get(eid, Attributes)
    if attrs is None:
        _mark_dirty(world, eid)
        return update_flag
    con = attrs.con_
    str_ = attrs.str_
    dex_ = attrs.dex_
    max_jingli = vitals.max_jingli
    max_neili = vitals.max_neili

    # 3. jing 恢复 + 钳位 eff_jing
    jing_rate = (con // 9 + max_jingli // 30) if fighting else (con // 3 + max_jingli // 10)
    vitals.jing += jing_rate
    if vitals.jing >= vitals.eff_jing:
        vitals.jing = vitals.eff_jing
        # 4. jing 达 eff_jing 上限后 eff_jing++（上限 max_jing）
        if vitals.eff_jing < vitals.max_jing:
            vitals.eff_jing += 1
            update_flag += 1
    else:
        update_flag += 1

    # 5. qi 恢复 + 钳位 eff_qi
    qi_rate = (con // 9 + max_neili // 30) if fighting else (con // 3 + max_neili // 10)
    vitals.qi += qi_rate
    if vitals.qi >= vitals.eff_qi:
        vitals.qi = vitals.eff_qi
        if vitals.eff_qi < vitals.max_qi:
            vitals.eff_qi += 1
            update_flag += 1
    else:
        update_flag += 1

    # 6. jingli 恢复（仅 max_jingli>0 且 jingli<max_jingli 时，上限 max*2）
    if max_jingli > 0 and vitals.jingli < max_jingli:
        jingli_rate = (str_ + dex_) // 12 if fighting else (str_ + dex_) // 4
        vitals.jingli += jingli_rate
        if vitals.jingli > max_jingli * 2:
            vitals.jingli = max_jingli * 2
        update_flag += 1

    # 7. neili 恢复（仅 max_neili>0 且 neili<max_neili 时，上限 max）
    if max_neili > 0 and vitals.neili < max_neili:
        skills = world.get(eid, Skills)
        force_skill = skills.levels.get("force", 0) if skills else 0
        neili_rate = force_skill // 6 if fighting else force_skill // 2
        vitals.neili += neili_rate
        if vitals.neili > max_neili:
            vitals.neili = max_neili
        update_flag += 1

    _mark_dirty(world, eid)
    return update_flag


def _mark_dirty(world: World, eid: int) -> None:
    """ADR-0022 §4：mutation 后 mark_dirty 供 StorageSystem 周期 persist。"""
    storage = getattr(world, "storage_system", None)
    if storage is not None:
        storage.mark_dirty(eid)
