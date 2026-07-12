"""死亡轮回系统（阶段 2.2，对照 LPC feature/damage.c + combatd.c + chard.c）。

实现 die / unconcious / revive / reincarnate / death_penalty / killer_reward /
make_corpse / announce / check_death，对照 [spec/layer_f_death.py](_die_spec 等)
规格 + LPC 原文。死亡触发由 heart_beat（check_death）判定：eff_qi/eff_jing<0
直接 die；qi/jing/jingli<0 先 unconcious，昏迷中再触发 die。

**2.2 范围控制**（收敛，对齐 04 §六 + ADR-0029 Wave 2 范围）：
- 阴间剧情（黑白无常/还阳）由 2.6 GovernanceSystem 承接：die 玩家分支末调
  ``governance.enter_underworld``（启动 death_stage EffectComp，ADR-0029
  §决策 6 衔接协议）。die 内仍只做 ghost=1 + move DEATH_ROOM。
- break_marriage / break_relation 后置 M3（die 中 stub 跳过）。
- log_file 死亡日志 + 频道谣言后置 M3（stub 跳过）。
- skill_death_penalty 简化 stub（所有技能 -1，真实 learned 公式后置 2.3/层 H）。
- PKS/MKS/shen/behavior_exp/balance 扣减后置 2.5 TitleComp（2.2 killer_reward
  只做 killer condition + pker 通缉机制核心）。
- winner_reward（unconcious 胜者奖励）后置 stub。
- make_corpse 装备重穿后置 2.3 Equipment（2.2 物品全转移 Inventory）。

**确定性**：death_penalty / killer_reward 无 random（对齐 LPC）。unconcious 的
revive 延时 random(100-con)+30 用系统 RNG（非 combat 确定性范围）。

[spec/layer_f_death.py](../spec/layer_f_death.py) /
[ADR-0029](../../../docs/adr/ADR-0029-world-governance-system.md)（阴间衔接） /
[feature/damage.c](../../../feature/damage.c) /
[adm/daemons/combatd.c](../../../adm/daemons/combatd.c)
"""

from __future__ import annotations

import random as _random

from xkx.runtime.components import (
    Attributes,
    Equipment,
    Identity,
    Inventory,
    Marks,
    Position,
    Progression,
    RoomComp,
    Skills,
    Vitals,
)
from xkx.runtime.conditions import (
    apply_condition,
    clear_condition,
    clear_one_condition,
    query_condition,
)
from xkx.runtime.ecs import World
from xkx.runtime.equipment import unequip
from xkx.runtime.query import move_to

# 阴间入口房间 id（ADR-0029 决策 3，房间系统未实现用字符串常量，2.6 接管）
DEATH_ROOM = "death/gate"

# 鬼魂/昏迷标记（Marks.flags，对照 LPC ghost / disable_player）
GHOST_FLAG = "ghost"
UNCONSCIOUS_FLAG = "unconscious"
DISABLED_FLAG = "disabled"


# ──────────────────────── 死亡触发判定（heart_beat） ────────────────────────


def check_death(world: World, eid: int, tick: int) -> bool:
    """heart_beat 死亡判定（[spec/layer_f](_heart_beat_death_trigger)）。

    - eff_qi<0 或 eff_jing<0 -> 直接 die()（致命伤）
    - qi<0 或 jing<0 或 jingli<0 -> living() 则 unconcious()，已昏迷则 die()

    ``tick`` 透传给 ``die()`` 供阴间剧情衔接（governance.enter_underworld
    首延 30 秒 next_tick=tick+30，ADR-0029 §决策 6）。

    返回是否触发死亡/昏迷（True=已处理，调用方应跳过常规 tick）。
    """
    vitals = world.get(eid, Vitals)
    if vitals is None:
        return False
    # 致命伤：eff_qi/eff_jing < 0 -> 直接 die
    if vitals.eff_qi < 0 or vitals.eff_jing < 0:
        die(world, eid, tick=tick)
        return True
    # qi/jing/jingli < 0 -> unconcious 或 die
    if vitals.qi < 0 or vitals.jing < 0 or vitals.jingli < 0:
        if _is_living(world, eid):
            unconcious(world, eid)
        else:
            die(world, eid, tick=tick)
        return True
    return False


# ──────────────────────── unconcious / revive / reincarnate ────────────────────────


def unconcious(world: World, eid: int, defeater: int | None = None) -> None:
    """昏迷（[spec/layer_f](_unconcious)，feature/damage.c:105-135）。

    清零 qi/jing/jingli + 设 unconscious 标记 + revive 定时器 + 消息。
    已昏迷（!living）则不再触发（LPC 前置条件）。
    """
    vitals = world.get(eid, Vitals)
    if vitals is None:
        return
    if not _is_living(world, eid):
        return  # 已昏迷不再触发
    # 清零 qi/jing/jingli
    vitals.qi = 0
    vitals.jing = 0
    vitals.jingli = 0
    # 设 unconscious 标记（disable_player 等价）
    _set_flag(world, eid, UNCONSCIOUS_FLAG)
    # revive 定时器：random(100-con)+30（系统 RNG，非 combat 确定性范围）
    attrs = world.get(eid, Attributes)
    con = attrs.con_ if attrs else 20
    delay = _random.randint(0, max(0, 100 - con - 1)) + 30
    apply_condition(world, eid, "revive", delay)
    # 消息 + announce（2.2 最小，消息推送后置 M3）
    announce(world, eid, "unconcious")
    _tell(world, eid, "\n你的眼前一黑，接著什么也不知道了。\n")
    # winner_reward(defeater) 后置 stub（昏迷胜者奖励，非 killer_reward）
    _mark_dirty(world, eid)


def revive(world: World, eid: int, quiet: bool = False) -> None:
    """苏醒（[spec/layer_f](_revive)，feature/damage.c:137-150）。

    清 unconscious 标记 + 移除 revive 定时器。quiet=False 输出苏醒消息。
    die 中 revive(1) 强制安静苏醒（处理昏迷中死亡场景）。
    """
    _clear_flag(world, eid, UNCONSCIOUS_FLAG)
    clear_one_condition(world, eid, "revive")
    if not quiet:
        announce(world, eid, "revive")
        _tell(world, eid, "\n慢慢地你终于又有了知觉。\n")
    _mark_dirty(world, eid)


def reincarnate(world: World, eid: int) -> None:
    """还阳（[spec/layer_f](_reincarnate)，feature/damage.c:255-264）。

    清 ghost 标记 + 完整恢复 qi/jing/eff_qi/eff_jing/jingli/neili 到 max
    （非渐进恢复，与 heal_up 区别）。
    """
    vitals = world.get(eid, Vitals)
    if vitals is None:
        return
    _clear_flag(world, eid, GHOST_FLAG)
    vitals.qi = vitals.max_qi
    vitals.eff_qi = vitals.max_qi
    vitals.jing = vitals.max_jing
    vitals.eff_jing = vitals.max_jing
    vitals.jingli = vitals.max_jingli
    vitals.neili = vitals.max_neili
    _mark_dirty(world, eid)


# ──────────────────────── die 主流程 ────────────────────────


def die(world: World, eid: int, killer_id: int | None = None, *, tick: int = 0) -> None:
    """死亡主流程（[spec/layer_f](_die)，feature/damage.c:152-253）。

    no_death 房玩家转 unconcious；玩家 ghost=1 move DEATH_ROOM；NPC 移除 Position。
    玩家分支末衔接阴间剧情（governance.enter_underworld 启动 death_stage
    EffectComp，ADR-0029 §决策 3 + §决策 6 衔接协议）。

    Args:
        world: ECS 世界。
        eid: 死亡实体 id。
        killer_id: 击杀者实体 id（None=非击杀致死，如致命伤/昏迷中死）。
        tick: 当前 tick（阴间剧情首延 next_tick=tick+30；默认 0 向后兼容
            无 tick 上下文的调用方，tick=0 时首延触发 tick=30）。
    """
    vitals = world.get(eid, Vitals)
    if vitals is None:
        return
    identity = world.get(eid, Identity)
    is_player = identity is not None and identity.is_player
    position = world.get(eid, Position)
    room_id = position.room_id if position else None
    room = _get_room(world, room_id)

    # no_death 房玩家转 unconcious（不真正死亡）
    if is_player and room is not None and room.no_death:
        unconcious(world, eid)
        return
    # !living 则 revive(1) 安静苏醒（昏迷中死亡场景）
    if not _is_living(world, eid):
        revive(world, eid, quiet=True)
    # clear_condition + delete poisoner
    clear_condition(world, eid)
    # announce dead
    announce(world, eid, "dead")
    # death_penalty（玩家且非 no_death 房）
    if is_player and (room is None or not room.no_death):
        death_penalty(world, eid)
    # killer_reward（有 killer）
    if killer_id is not None:
        killer_reward(world, killer_id, eid)
    # make_corpse（非 no_death 房玩家 / NPC）
    if not is_player or room is None or not room.no_death:
        make_corpse(world, eid, killer_id)
    # 玩家 vs NPC 分支
    if is_player:
        # 血量清 1（非 0，避免下一 tick 触发 unconcious/die）
        vitals.qi = 1
        vitals.eff_qi = 1
        vitals.jing = 1
        vitals.eff_jing = 1
        vitals.jingli = 1
        # no_death 房玩家恢复 eff 不进鬼魂（早退）
        if room is not None and room.no_death:
            vitals.eff_qi = vitals.max_qi
            vitals.eff_jing = vitals.max_jing
            _mark_dirty(world, eid)
            return
        # ghost=1 + move DEATH_ROOM（阴间入口）+ 衔接阴间剧情（ADR-0029 §决策 3/6）
        _set_flag(world, eid, GHOST_FLAG)
        move_to(world, eid, DEATH_ROOM)
        _save(world, eid)
        # 阴间剧情衔接（2.6）：启动 death_stage EffectComp（gate.c 物品销毁 +
        # 白无常 5 段剧情，首延 30 秒）。延迟 import 规避 governance -> death
        # 反向循环依赖（governance 模块级 import death 用于 reincarnate 等）。
        # 时序：enter_underworld 启动 EffectComp 但首延 30 秒，die 后立即状态
        # 不变（ghost=1 + DEATH_ROOM + 无还阳），GovernanceSystem tick 推进 30
        # 秒后才播第一段剧情（ADR-0029 §决策 4 非均匀 tick）。
        from xkx.runtime import governance

        governance.enter_underworld(world, eid, tick)
        # break_marriage / break_relation 后置 M3（stub 跳过）
    else:
        # NPC destruct：移除 Position（从房间消失，S5a 对齐）
        if position is not None:
            world.remove(eid, Position)
    _mark_dirty(world, eid)


# ──────────────────────── death_penalty / killer_reward / make_corpse ────────────────────────


def death_penalty(world: World, eid: int) -> None:
    """死亡惩罚（[spec/layer_f](_death_penalty)，combatd.c:987-1025，确定性无 random）。

    combat_exp 三段扣减 + potential 扣半。shen/behavior_exp/balance/death_times/
    death_count/thief 后置 2.5 TitleComp（2.2 跳过，无组件承接）。
    """
    prog = world.get(eid, Progression)
    if prog is None:
        return
    clear_condition(world, eid)
    combat_exp = prog.combat_exp
    # amount = min(combat_exp/100, 5000)
    amount = min(combat_exp // 100, 5000)
    if amount > 50:
        # 分支 A：combat_exp > 5000，扣 amount + potential 扣半
        prog.combat_exp -= amount
        prog.potential = prog.potential // 2
    elif combat_exp > 20:
        # 分支 B：20 < combat_exp <= 5000，扣固定 20
        prog.combat_exp -= 20
    # 分支 C：combat_exp <= 20，不扣
    # skill_death_penalty 真实 learned 公式（2.3 衔接，对照 skill.c:121-147）
    skill_death_penalty(world, eid)
    _save(world, eid)
    _mark_dirty(world, eid)


def killer_reward(world: World, killer_id: int, victim_id: int) -> None:
    """击杀奖励（[spec/layer_f](_killer_reward)，combatd.c:1027-1096，确定性无 random）。

    killer condition 施加（killer 玩家 + 城区）+ pker 叠加（双玩家）。
    PKS/MKS/shen/behavior_exp 后置 2.5 TitleComp（2.2 跳过计数，无组件承接）。
    """
    victim_pos = world.get(victim_id, Position)
    room = _get_room(world, victim_pos.room_id if victim_pos else None)
    # no_death 房不执行（外层门控）
    if room is not None and room.no_death:
        return
    killer_identity = world.get(killer_id, Identity)
    killer_is_player = killer_identity is not None and killer_identity.is_player
    victim_identity = world.get(victim_id, Identity)
    victim_is_player = victim_identity is not None and victim_identity.is_player
    # killer condition（killer 玩家 + /d/city/ 城区，对照 LPC strsrch "/d/city/"）
    if killer_is_player and _is_city_room(room):
        apply_condition(world, killer_id, "killer", 100)
    # pker 叠加（双玩家，对照 LPC pking 标记检查；2.2 简化无 pking 标记，直接 +120）
    if killer_is_player and victim_is_player:
        apply_condition(
            world, killer_id, "pker", query_condition(world, killer_id, "pker") + 120
        )
    # PKS/MKS/shen/behavior_exp 扣减后置 2.5 TitleComp
    _mark_dirty(world, killer_id)


def make_corpse(
    world: World, victim_id: int, killer_id: int | None = None
) -> int | None:
    """生成尸体（[spec/layer_f](_make_corpse)，chard.c:116-171）。

    ghost 不生成尸体（物品掉环境）；正常生成尸体实体 + 物品转移。
    装备重穿后置 2.3 Equipment（2.2 物品全转移 Inventory，无装备槽）。
    返回尸体 eid（ghost 返回 None）。
    """
    marks = world.get(victim_id, Marks)
    is_ghost = marks is not None and GHOST_FLAG in marks.flags
    victim_pos = world.get(victim_id, Position)
    room_id = victim_pos.room_id if victim_pos else None
    inv = world.get(victim_id, Inventory)

    if is_ghost:
        # ghost 装备卸下 + 物品掉环境（房间地面）
        equipped_items = _unequip_all(world, victim_id)
        if room_id:
            room = _get_room(world, room_id)
            if room is not None:
                if inv is not None:
                    room.items |= inv.items
                room.items.update(equipped_items)
        if inv is not None:
            inv.items.clear()
        _mark_dirty(world, victim_id)
        return None

    # 正常生成尸体实体
    victim_identity = world.get(victim_id, Identity)
    corpse_name = (victim_identity.name if victim_identity else "未知") + "的尸体"
    corpse_eid = world.new_entity()
    world.add(
        corpse_eid,
        Identity(name=corpse_name, aliases=["corpse"], prototype_id="corpse"),
    )
    if room_id:
        world.add(corpse_eid, Position(room_id=room_id))
    # 装备重穿（2.3）：卸下所有装备（反向扣减 apply_*）+ 装备物品转移尸体
    equipped_items = _unequip_all(world, victim_id)
    corpse_inv = Inventory()
    if inv is not None:
        corpse_inv.items = set(inv.items)
        inv.items.clear()
    corpse_inv.items.update(equipped_items)
    world.add(corpse_eid, corpse_inv)
    _mark_dirty(world, victim_id)
    _mark_dirty(world, corpse_eid)
    return corpse_eid


# ──────────────────────── announce（消息，2.2 最小） ────────────────────────


_ANNOUNCE_MESSAGES = {
    "dead": "倒在地上，挣扎了几下就死了。",
    "unconcious": "扑通一声倒在地上。",
    "revive": "悠悠醒转。",
}


def announce(world: World, eid: int, event: str) -> str:
    """死亡/昏迷/苏醒事件通告（[spec/layer_f](_announce)，combatd.c:966-980）。

    2.2 最小：返回消息文本（不实际推送网络，消息系统后置 M3）。消息模板由种族
    设置（race/*.c），2.2 用默认。
    """
    return _ANNOUNCE_MESSAGES.get(event, "")


# ──────────────────────── 内部辅助 ────────────────────────


def _is_living(world: World, eid: int) -> bool:
    """对象是否可操作（LPC living()，!disable_player）。

    greenfield：Marks.flags 不含 unconscious/disabled。
    """
    marks = world.get(eid, Marks)
    if marks is None:
        return True
    return UNCONSCIOUS_FLAG not in marks.flags and DISABLED_FLAG not in marks.flags


def _set_flag(world: World, eid: int, flag: str) -> None:
    marks = world.get(eid, Marks)
    if marks is None:
        marks = Marks()
        world.add(eid, marks)
    marks.flags.add(flag)


def _clear_flag(world: World, eid: int, flag: str) -> None:
    marks = world.get(eid, Marks)
    if marks is not None:
        marks.flags.discard(flag)


def _get_room(world: World, room_id: str | None) -> RoomComp | None:
    """按 room_id 找 RoomComp（线性扫描，房间数有限）。"""
    if room_id is None:
        return None
    for eid in world.entities_with(RoomComp):
        room = world.get(eid, RoomComp)
        if room is not None and room.room_id == room_id:
            return room
    return None


def _is_city_room(room: RoomComp | None) -> bool:
    """是否 /d/city/ 城区房间（对照 LPC strsrch(file_name(env), "/d/city/")）。

    greenfield room_id 以 "city/" 开头（如 "city/guangchang"）。
    """
    return room is not None and room.room_id.startswith("city/")


def _tell(world: World, eid: int, msg: str) -> None:
    """向实体输出消息（LPC tell_object，2.2 最小不推送，消息系统后置 M3）。"""
    # 消息推送由 connection/ws_server 后置，2.2 仅占位
    return None


def _save(world: World, eid: int) -> None:
    """存档（LPC save()，die/death_penalty 中防回档）。

    优先调 StorageSystem.persist_now 同步存单实体；无 StorageSystem 则 mark_dirty。
    """
    storage = getattr(world, "storage_system", None)
    if storage is None:
        return
    persist_now = getattr(storage, "persist_now", None)
    if persist_now is not None:
        persist_now(eid)
    else:
        storage.mark_dirty(eid)


def _mark_dirty(world: World, eid: int) -> None:
    """ADR-0022 §4：mutation 后 mark_dirty 供 StorageSystem 周期 persist。"""
    storage = getattr(world, "storage_system", None)
    if storage is not None:
        storage.mark_dirty(eid)


def _unequip_all(world: World, eid: int) -> list[str]:
    """卸下实体所有装备（死亡/尸体生成用），返回装备物品 id 列表。

    对照 LPC make_corpse 装备物品转移：greenfield 先 unequip（反向扣减
    apply_*）再收集物品 id 转移。无 Equipment 组件返回空列表。
    """
    equipment = world.get(eid, Equipment)
    if equipment is None:
        return []
    items: list[str] = []
    if equipment.weapon:
        items.append(equipment.weapon)
    if equipment.secondary_weapon:
        items.append(equipment.secondary_weapon)
    items.extend(equipment.armors.values())
    for item_id in items:
        unequip(world, eid, item_id)
    return items


def skill_death_penalty(world: World, eid: int) -> bool:
    """skill_death_penalty（对照 LPC feature/skill.c:121-147，2.3 衔接 2.2 stub）。

    learned 进度体系（确定性无 random）：
    - 无 learned（空 dict）：所有 ``skills[sk]--``（<0 删除），设
      ``learned[sk] = (降后 lvl+1)²/2``
    - 有 learned：若 ``learned[sk] > (lvl+1)²/2`` 阈值则扣 learned，否则
      ``skills[sk]--`` + 累加 ``learned[sk] += (降后 lvl+1)²/2``
    - 清空 skill_map（LPC ``skill_map = 0``）

    greenfield 修正：LPC 无 learned 分支 ``learned = ([sk:val])`` 在循环内覆盖
    整个 mapping 只记最后一个（显然 bug），greenfield 用 ``learned[sk] = t``
    累加记所有技能进度。wizard 判定后置（greenfield 无 wiz_level 组件）。
    """
    skills = world.get(eid, Skills)
    if skills is None or not skills.levels:
        return False
    has_learned = bool(skills.learned)
    for sk in list(skills.levels.keys()):
        if not has_learned:
            # 无 learned：skills[sk]-- + 设 learned[sk] = (降后 lvl+1)²/2
            skills.levels[sk] -= 1
            if skills.levels[sk] < 0:
                del skills.levels[sk]
                skills.learned.pop(sk, None)
            else:
                lvl = skills.levels[sk]
                skills.learned[sk] = (lvl + 1) * (lvl + 1) // 2
        else:
            # 有 learned：阈值判定（threshold 用降前 lvl）
            lvl = skills.levels.get(sk, 0)
            threshold = (lvl + 1) * (lvl + 1) // 2
            learned_val = skills.learned.get(sk, 0)
            if learned_val > threshold:
                skills.learned[sk] = learned_val - threshold
            else:
                skills.levels[sk] = lvl - 1
                if skills.levels[sk] < 0:
                    del skills.levels[sk]
                    skills.learned.pop(sk, None)
                else:
                    after = skills.levels[sk]
                    skills.learned[sk] = (
                        learned_val + (after + 1) * (after + 1) // 2
                    )
    skills.skill_map.clear()
    _mark_dirty(world, eid)
    return True
