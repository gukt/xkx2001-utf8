"""pilot 样本 id=12：adm/daemons/s_combatd.c:death_penalty 迁移代码。

对照 LPC adm/daemons/s_combatd.c L874-907，在 engine death.py:254 简化版
基础上补 6 项后置分支到行为等价。本文件为一次性测量代码，不污染 src/xkx
（ADR-0048 决策 8）。

simp=true：src death.py:254 已有简化版（只读参考，不调用），本文件独立
等价实现，补全被简化的后置分支：
1. death_times 递增判定（combat_exp>=10000*death_times，L882-883）
2. shen 扣 1/20（L884，shen 已映射 TitleComp.shen）
3. behavior_exp 扣 1/20（L885，后置 key）
4. balance 超 10000 部分扣半（L896-897，后置 key）
5. death_count+1（L898，后置 key）
6. delete vendetta（L899，后置 key）
7. delete_temp rob_victim/initiator（L900-901，后置 marks）
8. thief 减半（L902-903，后置 key）
"""

from __future__ import annotations

from typing import Any

from tools.sampling.pilot.stubs import wizardp

from xkx.runtime.components import Identity, Progression, TitleComp
from xkx.runtime.conditions import clear_condition
from xkx.runtime.death import _save, skill_death_penalty
from xkx.runtime.ecs import World


def _postponed_get(world: World, eid: int, key: str) -> int:
    """读后置 key 的样本特有桩（对照 death_times/behavior_exp/balance/death_count/thief）。

    LPC 这些 key 存于 dbase mapping，death_penalty 读旧值做扣减。新引擎
    POSTPONED_KEYS 写会 raise DbaseKeyError（query 读返回 None+warn）。本桩
    用 world 上的 ``_postponed_db`` dict 承接（按 eid 隔离），避开 raise
    并保证扣减语义可观测。返回 0 表示无旧值（对齐 LPC 未设 key 默认 0）。
    """
    store = _postponed_store(world, eid)
    return store.get(key, 0)


def _postponed_store(world: World, eid: int) -> dict[str, Any]:
    """取（或建）实体后置 key 的临时存储 dict。"""
    store_map = getattr(world, "_postponed_db", None)
    if store_map is None:
        store_map = {}
        world._postponed_db = store_map  # type: ignore[attr-defined]
    store = store_map.get(eid)
    if store is None:
        store = {}
        store_map[eid] = store
    return store


def _postponed_add(world: World, eid: int, key: str, delta: int) -> int:
    """后置 key 增量写（对照 LPC add(key, delta) 语义）。

    返回写入后新值（old + delta），无旧值时 old=0。
    """
    store = _postponed_store(world, eid)
    store[key] = store.get(key, 0) + delta
    return store[key]


def _postponed_set(world: World, eid: int, key: str, val: Any) -> Any:
    """后置 key 直接写（对照 LPC set(key, val) 语义，如 thief 减半）。"""
    store = _postponed_store(world, eid)
    store[key] = val
    return val


def _postponed_delete(world: World, eid: int, key: str) -> int:
    """后置 key 删除（对照 LPC delete(key)/delete_temp(key) 语义）。

    返回 1=已删，0=原本无此 key。
    """
    store = _postponed_store(world, eid)
    if key in store:
        del store[key]
        return 1
    return 0


def _is_player(world: World, eid: int) -> bool:
    """userp(victim) 等价（对照 L877）。

    LPC userp 判定是否玩家对象。新引擎 Identity.is_player 字段。
    """
    ident = world.get(eid, Identity)
    return ident is not None and ident.is_player


def death_penalty(world: World, victim: int) -> None:
    """s_combatd.c:death_penalty 迁移（对照 adm/daemons/s_combatd.c L874-907）。

    补 6 项后置分支（death.py:254 简化版跳过）：
    1. death_times 递增判定（combat_exp>=10000*death_times）
    2. shen 扣 1/20（已映射 TitleComp.shen）
    3. behavior_exp 扣 1/20（后置 key）
    4. balance 超 10000 部分扣半（后置 key）
    5. death_count+1（后置 key）
    6. delete vendetta / rob_victim / initiator（后置 key/temp）
    7. thief 减半（后置 key）

    返回 None（LPC void 函数，无 actor 可见消息）。副作用全部作用于 victim
    组件/后置 store。save 副作用走 _save（persist_now 单实体，若 storage
    签名不匹配则 mark_dirty，对照 death.py:447）。
    """
    # L877：if (!userp(victim)) return;
    if not _is_player(world, victim):
        return

    # L879：if (wizardp(victim)) return;
    if wizardp(world, victim):
        return

    # L880：victim->clear_condition();
    clear_condition(world, victim)

    prog = world.get(victim, Progression)
    if prog is None:
        return

    # L882-883：death_times 递增判定
    # if( combat_exp >= 10000 * death_times ) add("death_times", 1);
    death_times = _postponed_get(world, victim, "death_times")
    if prog.combat_exp >= 10000 * death_times:
        _postponed_add(world, victim, "death_times", 1)

    # L884：victim->add("shen", -(int)victim->query("shen") / 20);
    # shen 已映射 TitleComp.shen，可直接读写
    title = world.get(victim, TitleComp)
    if title is not None:
        title.shen = title.shen - title.shen // 20

    # L885：victim->add("behavior_exp", -behavior_exp / 20);
    behavior_exp = _postponed_get(world, victim, "behavior_exp")
    _postponed_add(world, victim, "behavior_exp", -(behavior_exp // 20))

    # L886-887：amount = combat_exp / 100; if (amount > 5000) amount = 5000;
    amount = prog.combat_exp // 100
    if amount > 5000:
        amount = 5000

    # L888-894：combat_exp 三段扣减
    if amount > 50:
        # 分支 A：扣 amount + potential 扣半
        # L889：victim->add("combat_exp", -amount);
        prog.combat_exp -= amount
        # L890-891：if (potential > 0) add("potential", -potential/2);
        if prog.potential > 0:
            prog.potential = prog.potential - prog.potential // 2
    elif prog.combat_exp > 20:
        # L893-894：分支 B：20 < combat_exp <= 5000，扣固定 20
        prog.combat_exp -= 20
    # 分支 C：combat_exp <= 20，不扣

    # L896-897：balance 超 10000 部分扣半
    # amount = balance - 10000; if (amount > 0) add("balance", -amount/2);
    balance = _postponed_get(world, victim, "balance")
    balance_over = balance - 10000
    if balance_over > 0:
        _postponed_add(world, victim, "balance", -(balance_over // 2))

    # L898：victim->add("death_count", 1);
    _postponed_add(world, victim, "death_count", 1)

    # L899：victim->delete("vendetta");
    _postponed_delete(world, victim, "vendetta")

    # L900-901：victim->delete_temp("rob_victim"); delete_temp("initiator");
    _postponed_delete(world, victim, "rob_victim")
    _postponed_delete(world, victim, "initiator")

    # L902-903：if (thief) set("thief", thief / 2);
    thief = _postponed_get(world, victim, "thief")
    if thief:
        _postponed_set(world, victim, "thief", thief // 2)

    # L904：victim->skill_death_penalty();
    skill_death_penalty(world, victim)

    # L905：victim->save();
    _save(world, victim)
