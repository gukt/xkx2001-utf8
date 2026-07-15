"""pilot 样本 id=6：feature/damage.c:die 迁移代码。

对照 LPC feature/damage.c L152-253，在 engine 现有 death.die（death.py:171
简化版，只读参考不调用）基础上补全被简化的后置分支到行为等价。本文件为
一次性测量代码，不污染 src/xkx（ADR-0048 决策 8）。

补全的后置分支（对照 triage[5] B 类缺口）：
1. wizardp + env/immortal 免死早退（L180）
2. log_file PKILL_DATA / PLAYER_DEATH 死亡日志三段子分支（L209-224）
3. remove_all_killer + all_inventory(env).remove_killer(me) 战斗关系清理（L230-231）
4. dismiss_team（L244）
5. interrupt_me（is_busy 时，L234-235）
6. CHANNEL_D.do_channel 谣言广播（无 killer 玩家死亡，L195-206）
7. MARRY_D.break_marriage（L249）
8. CHAR_D.break_relation（风清扬弟子，L250）

后置 stub（无对应引擎实现，用模块级可替换函数桩，测试 monkeypatch）：
- log_file / do_channel / break_marriage / break_relation / remove_all_killer /
  remove_killer / dismiss_team / interrupt_me / find_object / load_object /
  query_env_immortal / delete_poisoner

LPC die 为 void；本迁移返回 None，副作用落在 world 状态 + 上述 stub 调用记录。
"""

from __future__ import annotations

import time
from typing import Any

from tools.sampling.pilot.stubs import wizardp

from xkx.runtime.components import (
    FamilyComp,
    Identity,
    Marks,
    Position,
    RoomComp,
    Vitals,
)
from xkx.runtime.conditions import clear_condition
from xkx.runtime.death import (
    GHOST_FLAG,
    UNCONSCIOUS_FLAG,
    announce,
    death_penalty,
    killer_reward,
    make_corpse,
    revive,
    unconcious,
)
from xkx.runtime.query import environment, move_to

# 风清扬师傅 prototype_id（对照 LPC L250 family/master_id=="feng qingyang"）。
_FENG_QINGYANG_MASTER = "feng qingyang"


# ──────────────────────── 后置 stub（模块级可替换） ────────────────────────
# 这些 API 在新引擎完全无实现（triage[5] missing_apis），桩默认 no-op/回落，
# 测试通过 monkeypatch 替换为可观测副作用。不进 stubs.py（样本特有，ADR-0048
# 决策 2：样本特有桩用 monkeypatch 不进共享桩文件）。


def log_file(file_name: str, msg: str) -> None:
    """LPC log_file efun（对照 L211/213/217/221）。

    桩：no-op（death.py:13 注释"log_file 死亡日志后置 M3"）。
    真实：按 file_name 追加写 LOG_DIR/<file_name>。
    """


def do_channel(rum_ob: Any, channel: str, msg: str) -> None:
    """CHANNEL_D->do_channel（对照 L201/204 谣言广播）。

    桩：no-op（death.py:13 注释"频道谣言后置 M3"）。
    """


def break_marriage(world: Any, eid: int) -> None:
    """MARRY_D->break_marriage（对照 L249）。

    桩：no-op（death.py:243 注释"break_marriage 后置 M3"）。
    """


def break_relation(world: Any, eid: int) -> None:
    """CHAR_D->break_relation（对照 L250 风清扬弟子师徒断裂）。

    桩：no-op（death.py:243 注释"break_relation 后置 M3"）。
    """


def remove_all_killer(world: Any, eid: int) -> None:
    """this_object()->remove_all_killer()（对照 L230）。

    桩：no-op（CombatState.enemy_ids/killer_ids 有数据无清理方法）。
    真实：清 eid 的 CombatState.killer_ids + enemy_ids 中所有目标。
    """


def remove_killer(world: Any, observer_eid: int, target_eid: int) -> None:
    """all_inventory(env)->remove_killer(this_object())（对照 L231）。

    桩：no-op（同上）。真实：observer 从其 killer_ids/enemy_ids 移除 target。
    """


def dismiss_team(world: Any, eid: int) -> None:
    """this_object()->dismiss_team()（对照 L244）。

    桩：no-op（无 Team 组件/系统）。
    """


def interrupt_me(world: Any, eid: int) -> None:
    """this_object()->interrupt_me()（对照 L235 is_busy 时打断）。

    桩：no-op（is_busy 有但打断当前动作未实现）。
    """


def find_object(path: str) -> Any:
    """LPC find_object efun（对照 L197 谣言 NPC 代理）。

    桩：返回 None（greenfield 无 LPC 对象路径加载模型）。
    真实：按路径找已加载单例对象。
    """
    return None


def load_object(path: str) -> Any:
    """LPC load_object efun（对照 L198）。

    桩：返回 path 字符串占位（无对象模型，仅满足调用契约）。
    """
    return path


def query_env_immortal(world: Any, eid: int) -> bool:
    """query("env/immortal")（对照 L180 wizard 不死分支）。

    桩：返回 False（"env" 在 POSTPONED_KEYS，query 返回 None+warn；用本桩
    回落避免噪音 + 让 wizard 免死分支可被 monkeypatch 触发）。
    """
    return False


def delete_poisoner(world: Any, eid: int) -> None:
    """delete("poisoner")（对照 L185 中毒者记录清除）。

    桩：no-op（"poisoner" 为 unknown key，delete 会 raise DbaseKeyError；
    用本桩安全跳过）。
    """


def getuid(world: Any, eid: int) -> str:
    """LPC getuid(me) efun（对照 L212/214/218/222 日志玩家 id）。

    桩：从 Identity.aliases[0] 取（account.account_id 等价），无则空串。
    """
    ident = world.get(eid, Identity)
    if ident and ident.aliases:
        return ident.aliases[0]
    return ""


# ──────────────────────── 内部辅助 ────────────────────────


def _is_player(world: Any, eid: int) -> bool:
    """userp 判定（对照 LPC userp(this_object())）。"""
    ident = world.get(eid, Identity)
    return ident is not None and ident.is_player


def _is_living(world: Any, eid: int) -> bool:
    """living 判定（对照 LPC living()，!unconscious && !disabled）。

    对照 death._is_living：Marks.flags 不含 unconscious/disabled。
    """
    marks = world.get(eid, Marks)
    if marks is None:
        return True
    return (
        UNCONSCIOUS_FLAG not in marks.flags
        and "disabled" not in marks.flags
    )


def _get_room(world: Any, room_id: str | None) -> RoomComp | None:
    """按 room_id 找 RoomComp（对照 death._get_room，线性扫描）。"""
    if room_id is None:
        return None
    for eid in world.entities_with(RoomComp):
        room = world.get(eid, RoomComp)
        if room is not None and room.room_id == room_id:
            return room
    return None


def _entity_name(world: Any, eid: int) -> str:
    """killer->name() / me->query("name")（对照 L202/205/218）。

    greenfield 无 name() 方法，用 Identity.name（对齐 death.make_corpse 模式）。
    无 Identity 回落空串。
    """
    ident = world.get(eid, Identity)
    return ident.name if ident else ""


def _theme_death_room(world: Any) -> str:
    """DEATH_ROOM 常量（对照 L247 move DEATH_ROOM）。

    对照 death._theme_config：从 world.theme_config 读 death_room，无则默认。
    """
    theme = getattr(world, "theme_config", None)
    if theme is not None and getattr(theme, "death_room", None):
        return theme.death_room
    return "death/gate"


def _start_death(world: Any, eid: int, tick: int) -> None:
    """DEATH_ROOM->start_death(obj)（对照 L248）。

    对照 death.die：衔接阴间剧情 governance.enter_underworld（启动 death_stage
    EffectComp，ADR-0029 §决策 6）。延迟 import 规避 governance -> death 反向依赖。
    """
    from xkx.runtime import governance

    governance.enter_underworld(world, eid, tick)


def _save(world: Any, eid: int) -> None:
    """this_object()->save()（对照 L245）。对照 death._save。"""
    storage = getattr(world, "storage_system", None)
    if storage is None:
        return
    persist_now = getattr(storage, "persist_now", None)
    if persist_now is not None:
        persist_now(eid)
    else:
        storage.mark_dirty(eid)


def _set_ghost(world: Any, eid: int) -> None:
    """ghost = 1（对照 L246，damage.c 模块变量 ghost）。

    greenfield：设 Marks.flags GHOST_FLAG（对齐 death._set_flag）。
    """
    marks = world.get(eid, Marks)
    if marks is None:
        marks = Marks()
        world.add(eid, marks)
    marks.flags.add(GHOST_FLAG)


# ──────────────────────── die 主流程 ────────────────────────


def damage_c_die(
    world: Any,
    eid: int,
    killer_id: int | None = None,
    killer_name: str | None = None,
    *,
    tick: int = 0,
) -> None:
    """damage.c:die 迁移（对照 feature/damage.c L152-253）。

    no_death 房玩家转 unconcious；玩家 ghost=1 move 阴间入口 + 衔接阴间剧情；
    NPC 移除 Position。补全 wizard 免死 / 死亡日志 / 战斗关系清理 / 谣言 /
    break_marriage / break_relation 等后置分支。

    Args:
        world: ECS 世界。
        eid: 死亡实体 id。
        killer_id: 击杀者实体 id（None=无对象击杀者；对照 LPC
            objectp(query_temp("last_damage_from"))）。
        killer_name: 击杀者字符串名（环境伤害来源；对照 LPC
            stringp(killer)，此时 killer_id 应为 None）。
        tick: 当前 tick（阴间剧情首延 next_tick=tick+30）。

    LPC die 为 void，本迁移返回 None。
    """
    vitals = world.get(eid, Vitals)
    if vitals is None:
        return

    is_player = _is_player(world, eid)
    room_id = environment(world, eid)
    room = _get_room(world, room_id)

    # L159-177：no_death 房玩家转 unconcious（不真正死亡）
    if is_player and room is not None and room.no_death:
        unconcious(world, eid)
        # L174：remove_call_out("revive")（已在 unconcious 重设 revive 定时器，
        # 对照 death.die no_death 分支仅 unconcious 后 return，不额外清 revive）
        return

    # L179：!living 则 revive(1) 安静苏醒（昏迷中死亡场景）
    if not _is_living(world, eid):
        revive(world, eid, quiet=True)

    # L180：wizard + env/immortal 免死早退（补全分支）
    if wizardp(world, eid) and query_env_immortal(world, eid):
        return

    # L234-235 前置：is_busy 时 interrupt_me（LPC L234 在玩家分支末，但 greenfield
    # clear_condition 会清 EffectComp 包括 busy action；LPC busy 是 action 非
    # condition，clear_condition 不清。故先记录 busy 再 clear，玩家分支用标志判定，
    # 行为等价：死亡打断 busy action + clear_condition 清 condition 各自独立）。
    from xkx.runtime.skill import is_busy

    was_busy = is_player and is_busy(world, eid)

    # L184：clear_condition（清除所有 condition）
    clear_condition(world, eid)
    # L185：delete("poisoner")（unknown key，桩安全跳过）
    delete_poisoner(world, eid)

    # L187：announce dead（2.2 最小返回文本不推送）
    announce(world, eid, "dead")

    # L189-190：玩家且非 no_death 房 -> death_penalty
    if is_player and (room is None or not room.no_death):
        death_penalty(world, eid)

    # L192-206：killer 分支
    if killer_id is not None:
        # L193：set_temp("my_killer", killer->query("id"))
        # greenfield "my_killer" 在 POSTPONED_KEYS，set 抛 DbaseKeyError；Marks.flags
        # 是 set 不能存值，用 "my_killer:<uid>" 约定存（与 last_eff_damage_from 一致，
        # _marks_value 可解析出 uid；存在性判定用 startswith）。
        killer_uid = getuid(world, killer_id)
        _set_mark_value(world, eid, "my_killer", killer_uid)
        # L194：killer_reward
        killer_reward(world, killer_id, eid)
    elif is_player:
        # L195-206：无对象 killer 的玩家死亡 -> 谣言广播
        # L197-198：find_object/load_object 谣言 NPC 代理（aqingsao）
        rum_ob = find_object("/d/city/npc/aqingsao")
        if rum_ob is None:
            rum_ob = load_object("/d/city/npc/aqingsao")
        # L200-205：stringp(killer) / else 两段谣言
        victim_name = _entity_name(world, eid)
        if killer_name is not None:
            do_channel(
                rum_ob, "rumor", f"{victim_name}{killer_name}。"
            )
        else:
            do_channel(
                rum_ob, "rumor", f"{victim_name}莫名其妙地死了。"
            )

    # L209-224：玩家死亡日志（log_file PKILL_DATA / PLAYER_DEATH）
    if is_player:
        _log_death(world, eid, killer_id, killer_name)

    # L226-228：非 no_death 房玩家 / NPC -> make_corpse + move 环境
    if (room is None or not room.no_death) or not is_player:
        corpse_eid = make_corpse(world, eid, killer_id)
        if corpse_eid is not None and room_id is not None:
            move_to(world, corpse_eid, room_id)

    # L230：this_object()->remove_all_killer()
    remove_all_killer(world, eid)
    # L231：all_inventory(environment())->remove_killer(this_object())
    # greenfield all_inventory(eid) 返回 Inventory.items（物品 id）非房间实体；
    # LPC 语义是房间内所有对象解除对死者的 killer 关系。改遍历房间内实体。
    if room_id is not None:
        for observer_eid in list(world.entities_in_room(room_id)):
            if observer_eid != eid:
                remove_killer(world, observer_eid, eid)

    # L233-252：玩家 vs NPC 分支
    if is_player:
        # L234-235：is_busy 时 interrupt_me（was_busy 在 clear_condition 前记录）
        if was_busy:
            interrupt_me(world, eid)
        # L236-238：血量清 1（非 0，避免下一 tick 触发 unconcious/die）
        vitals.jing = 1
        vitals.eff_jing = 1
        vitals.qi = 1
        vitals.eff_qi = 1
        vitals.jingli = 1
        # L239-243：no_death 房玩家恢复 eff 不进鬼魂（早退）
        if room is not None and room.no_death:
            vitals.eff_jing = vitals.max_jing
            vitals.eff_qi = vitals.max_qi
            return
        # L244：dismiss_team
        dismiss_team(world, eid)
        # L245：save
        _save(world, eid)
        # L246：ghost = 1
        _set_ghost(world, eid)
        # L247：move DEATH_ROOM
        move_to(world, eid, _theme_death_room(world))
        # L248：DEATH_ROOM->start_death（衔接阴间剧情）
        _start_death(world, eid, tick)
        # L249：MARRY_D->break_marriage
        break_marriage(world, eid)
        # L250：风清扬弟子 -> CHAR_D->break_relation
        if _is_feng_disciple(world, eid):
            break_relation(world, eid)
    else:
        # L251-252：NPC destruct（移除 Position，从房间消失）
        if world.get(eid, Position) is not None:
            world.remove(eid, Position)


def _log_death(
    world: Any,
    eid: int,
    killer_id: int | None,
    killer_name: str | None,
) -> None:
    """死亡日志三段子分支（对照 L209-224）。

    - last_eff_damage_from 存在 -> PKILL_DATA + PLAYER_DEATH（PlayerKill）
    - objectp(killer) -> PLAYER_DEATH（被 killer 名 杀死）
    - stringp(killer) -> PLAYER_DEATH（died from killer_name）

    greenfield "last_eff_damage_from" 在 POSTPONED_KEYS（query 返回 None），
    用 Marks.flags 中 "last_eff_damage_from:<id>" 约定判定（receive_damage 写入）。
    """
    marks = world.get(eid, Marks)
    has_eff_dmg = marks is not None and _has_mark(marks, "last_eff_damage_from")
    name = _entity_name(world, eid)
    uid = getuid(world, eid)
    now = time.ctime()

    if has_eff_dmg:
        # L210-215：PlayerKill 日志（PKILL_DATA + PLAYER_DEATH）
        eff_from = _marks_value(marks, "last_eff_damage_from")
        msg = f"{name}({uid}) 被 {eff_from} 杀死了(PlayerKill) on {now}。"
        log_file("PKILL_DATA", msg)
        log_file("PLAYER_DEATH", msg)
    elif killer_id is not None:
        # L216-219：被 killer 对象杀死
        killer_nm = _entity_name(world, killer_id)
        log_file(
            "PLAYER_DEATH",
            f"{name}({uid}) 被 {killer_nm} 杀死了 on {now}。",
        )
    elif killer_name is not None:
        # L220-223：died from string killer
        log_file(
            "PLAYER_DEATH",
            f"{name}({uid}) died from {killer_name} on {now}。",
        )


def _set_mark_value(world: Any, eid: int, key: str, value: str) -> None:
    """存值型 temp 标记到 Marks.flags（"key:value" 约定）。

    greenfield Marks.flags 是 set[str] 不能存值（set_temp("marks/X", v) 仅 add
    sub_key 丢值）。LPC set_temp("my_killer", id) / receive_damage 写
    last_eff_damage_from 需存具体 id。约定 flag 形如 "key:value"，可被
    _has_mark / _marks_value 解析。
    """
    marks = world.get(eid, Marks)
    if marks is None:
        marks = Marks()
        world.add(eid, marks)
    # 先清旧值（同 key 不同 value），再写新值
    for f in list(marks.flags):
        if f == key or f.startswith(key + ":"):
            marks.flags.discard(f)
    marks.flags.add(f"{key}:{value}" if value else key)


def _has_mark(marks: Marks, key: str) -> bool:
    """Marks.flags 是否含 key（含 "key:..." 值型约定）。"""
    return any(f == key or f.startswith(key + ":") for f in marks.flags)


def _marks_value(marks: Marks, key: str) -> str:
    """从 Marks.flags 取值型标记的 value（"key:value" 约定）。"""
    for f in marks.flags:
        if f == key or f.startswith(key + ":"):
            return f.split(":", 1)[1] if ":" in f else ""
    return ""


def _is_feng_disciple(world: Any, eid: int) -> bool:
    """风清扬弟子判定（对照 L250 family/master_id=="feng qingyang"）。

    greenfield "family/master_id" 路径未映射（FamilyComp 不引入 family/ 路径），
    直接读 FamilyComp.master_id（components.py:332）。
    """
    fam = world.get(eid, FamilyComp)
    return fam is not None and fam.master_id == _FENG_QINGYANG_MASTER
