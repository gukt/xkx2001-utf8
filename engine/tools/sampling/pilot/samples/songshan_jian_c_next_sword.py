"""pilot 样本 id=5：kungfu/skill/songshan-jian.c:next_sword 迁移代码。

对照 LPC kungfu/skill/songshan-jian.c L137-188（next_sword post_action），
迁移四档武器对抗判定 + 副作用链到行为等价。本文件为一次性测量代码，
不污染 src/xkx（ADR-0048 决策 8）。

核心障碍（B 类架构缺口）：greenfield 无独立"物品实例对象"实体。LPC 中
weapon/ob 是物品对象（有 weight()/name()/query("rigidity")/unequip()/move()
方法 + value/weapon_prop 属性），greenfield 物品仅是 Inventory/Equipment 槽位
里的 str item_id，物品本身属性无组件承接。因此 weapon->weight()/query("rigidity")
/name()/set("value")/set("weapon_prop") 等"物品对象属性读写"全部无对应实现
（rigidity/value/weapon_prop 还是 unknown key，query/set 直接 raise DbaseKeyError）。

简化策略（照 triage 简化建议）：建样本特有 item 桩 -- 一个 item_id -> 属性 dict
的注册表，weight/rigidity/name/value/weapon_prop 从测试注入固定值；weapon/ob
的 name()/weight()/query()/set()/unequip()/move() 等价行为经该注册表承接。
注册表经函数参数注入（默认空表），不进 stubs.py（红线：样本特有桩用测试
monkeypatch / 参数注入，不进 stubs.py）。
"""

from __future__ import annotations

from typing import Any, Protocol

from tools.sampling.pilot.stubs import (
    HIW,
    HIY,
    NOR,
    message_vision,
    query_jiali,
    query_str,
    reset_action,
)

from xkx.combat.result import RESULT_PARRY
from xkx.runtime.components import Equipment
from xkx.runtime.equipment import unequip
from xkx.runtime.query import environment, query, query_skill


class ItemRegistry(Protocol):
    """样本特有 item 桩协议（承接 LPC 物品对象属性读写）。

    LPC weapon/ob 是物品对象，有 weight()/name()/query("rigidity"/"value"/
    "weapon_prop")/set(...)/unequip()/move()。greenfield 物品无实体，本桩用
    item_id -> 属性 dict 注册表承接。测试注入固定值；move 到房间因物品无
    Position 组件未实现（注释标出，记为待迁移面）。
    """

    def weight(self, item_id: str) -> int: ...
    def rigidity(self, item_id: str) -> int: ...
    def name(self, item_id: str) -> str: ...
    def value(self, item_id: str) -> int: ...
    def weapon_prop(self, item_id: str) -> int: ...
    def set_name(self, item_id: str, name: str) -> None: ...
    def set_value(self, item_id: str, value: int) -> None: ...
    def set_weapon_prop(self, item_id: str, value: int) -> None: ...
    def move_to_room(self, item_id: str, room_id: str) -> None: ...


class _DictItemRegistry:
    """默认 item 桩：dict 注册表（测试可注入自定义实现覆盖）。

    所有属性默认 0/空串，weight 默认 0（LPC 武器 weight 通常 >0，由测试注入）。
    move_to_room no-op（物品无 Position 组件，掉落房间未实现，记为待迁移面）。
    """

    def __init__(self, items: dict[str, dict[str, Any]] | None = None) -> None:
        self._items: dict[str, dict[str, Any]] = items or {}

    def _get(self, item_id: str, key: str, default: Any) -> Any:
        return self._items.get(item_id, {}).get(key, default)

    def weight(self, item_id: str) -> int:
        return int(self._get(item_id, "weight", 0))

    def rigidity(self, item_id: str) -> int:
        return int(self._get(item_id, "rigidity", 0))

    def name(self, item_id: str) -> str:
        return str(self._get(item_id, "name", item_id))

    def value(self, item_id: str) -> int:
        return int(self._get(item_id, "value", 0))

    def weapon_prop(self, item_id: str) -> int:
        return int(self._get(item_id, "weapon_prop", 0))

    def set_name(self, item_id: str, name: str) -> None:
        self._items.setdefault(item_id, {})["name"] = name

    def set_value(self, item_id: str, value: int) -> None:
        self._items.setdefault(item_id, {})["value"] = value

    def set_weapon_prop(self, item_id: str, value: int) -> None:
        self._items.setdefault(item_id, {})["weapon_prop"] = value

    def move_to_room(self, item_id: str, room_id: str) -> None:
        # 物品无 Position 组件，掉落房间未实现（后置 M3 物品系统）。
        # 记录到注册表以便测试断言"武器已脱离装备槽"。
        self._items.setdefault(item_id, {})["dropped_room"] = room_id


def _victim_weapon_id(world: Any, victim_id: int) -> str | None:
    """取 victim 当前装备武器 item_id（对照 LPC victim->query_temp("weapon")）。

    LPC query_temp("weapon") 返回武器对象；greenfield 中 "weapon" key 映射到
    Skills.weapon（语义不符，triage 标"部分"），正确承接应为 Equipment.weapon
    装备槽（components.py:112）。本迁移用 Equipment.weapon 取 item_id 字符串。
    """
    equipment = world.get(victim_id, Equipment)
    return equipment.weapon if equipment else None


def songshan_jian_c_next_sword(
    world: Any,
    me_id: int,
    victim_id: int,
    weapon_id: str,
    damage: int,
    *,
    items: ItemRegistry | None = None,
    rng: Any | None = None,
) -> list[str]:
    """songshan-jian.c:next_sword 迁移（对照 L137-188）。

    LPC 签名 int next_sword(object me, object victim, object weapon, int damage)。
    post_action 在 do_attack 七步后处理触发，返回 1（LPC 契约）。
    本迁移返回房间可见消息 list[str]（message_vision 副作用经 facade 收集），
    LPC 命令返回值 1 不在命令路径（post_action 非命令），此处用消息列表承接。

    参数：
    - weapon_id：me 当前武器 item_id（LPC weapon 对象，桩承接属性）
    - items：item 桩注册表（None 用默认 _DictItemRegistry）
    - rng：随机源（None 用 Python random，combat 确定性后置；本函数 random 在
      wap 计算层属 combat 派生，按 ADR 用注入 rng 保证可测）

    返回 message_vision 产出的消息列表（顺序对齐 LPC 分支顺序）。
    """
    registry = items if items is not None else _DictItemRegistry()
    msgs: list[str] = []

    # L141：ob = victim->query_temp("weapon")（victim 防守武器）
    ob_id = _victim_weapon_id(world, victim_id)

    # L142-146：致命斩分支（eff_qi<0 且 qi<0）
    if query(world, victim_id, "eff_qi") < 0 and query(world, victim_id, "qi") < 0:
        wname = registry.name(weapon_id)
        # L144：message_vision(HIW"紧跟着剑光带过，"+weapon->name()+HIW"一剑..."NOR)
        msg = (
            HIW + "紧跟着剑光带过，" + wname + HIW
            + "一剑从$n左肩直劈到右腰，这一剑势道之凌厉，端的是匪夷所思，"
            + "只是闪电般一亮，$n已被斩成两截！\n" + NOR
        )
        msgs.append(message_vision(world, msg, me_id, victim_id))
        return msgs

    # L148：damage==RESULT_PARRY 且 victim 有防守武器
    if damage == RESULT_PARRY and ob_id is not None:
        # L151-156：wap = weapon 攻方力量
        # wap = weapon->weight()/500 + weapon->query("rigidity") + me->query_str()
        #       + me->query("jiali") + me->query_skill("songshan-jian")/3
        #       + me->query_temp("songshan_xuli")
        wap = (
            registry.weight(weapon_id) // 500
            + registry.rigidity(weapon_id)
            + query_str(world, me_id)
            + query_jiali(world, me_id)
            + query_skill(world, me_id, "songshan-jian") // 3
            + _query_xuli(world, me_id)
        )
        # L157-161：wdp = ob 守方力量
        # wdp = ob->weight()/500 + ob->query("rigidity") + victim->query_str()
        #       + victim->query("jiali") + victim->query_skill("parry")/3
        wdp = (
            registry.weight(ob_id) // 500
            + registry.rigidity(ob_id)
            + query_str(world, victim_id)
            + query_jiali(world, victim_id)
            + query_skill(world, victim_id, "parry") // 3
        )
        # L162：wap = random(wap/2) + wap/2
        half = wap // 2
        wap = _random(rng, half) + half

        wname = registry.name(weapon_id)
        oname = registry.name(ob_id)

        # L164-172：wap > 3*wdp -> 寸断（weapon 击碎 ob）
        if wap > 3 * wdp:
            msg = (
                HIY + "$N手上" + wname + HIY + "连连催劲，「」的一声响，与$n的"
                + oname + HIY + "一撞，喀喀喀十余声轻响过去，$n手中" + oname
                + HIY + "寸断，折成数十截掉在地下！\n"
            )
            msgs.append(message_vision(world, msg, me_id, victim_id))
            # L166-172：ob->unequip(); ob->move(environment(victim));
            #          ob->set("name","断碎的"+ob->query("name"));
            #          ob->set("value",0); ob->set("weapon_prop",0);
            #          victim->reset_action();
            unequip(world, victim_id, ob_id)
            room_id = environment(world, victim_id)
            if room_id is not None:
                registry.move_to_room(ob_id, room_id)  # 物品掉落未实现，桩记录
            registry.set_name(ob_id, "断碎的" + registry.name(ob_id))
            registry.set_value(ob_id, 0)
            registry.set_weapon_prop(ob_id, 0)
            reset_action(world, victim_id)
        # L173-177：wap > 2*wdp -> 脱手
        elif wap > 2 * wdp:
            msg = (
                HIW + "但是$N手上" + wname + HIW
                + "连连催劲，$n手臂酸麻，虎口剧痛，" + oname + HIW
                + "登时脱手！\n"
            )
            msgs.append(message_vision(world, msg, me_id, victim_id))
            # L175-177：ob->unequip(); ob->move(environment(victim)); victim->reset_action();
            unequip(world, victim_id, ob_id)
            room_id = environment(world, victim_id)
            if room_id is not None:
                registry.move_to_room(ob_id, room_id)
            reset_action(world, victim_id)
        # L178-180：wap > wdp -> 震动（注意 $N=victim，险些脱手）
        elif wap > wdp:
            msg = "$N只觉得手中" + oname + "一震，险些脱手！\n"
            # LPC L179 message_vision(msg, victim) -- me 位是 victim
            msgs.append(message_vision(world, msg, victim_id))
        # L181-184：else -> 火星
        else:
            msg = (
                "$N的" + wname + "和$n的" + oname
                + "相击，冒出点点的火星。\n"
            )
            msgs.append(message_vision(world, msg, me_id, victim_id))

    # L187：return 1（LPC post_action 契约；本迁移用消息列表承接）
    return msgs


def _query_xuli(world: Any, eid: int) -> int:
    """取嵩山蓄力值（对照 LPC me->query_temp("songshan_xuli")）。

    "songshan_xuli" classify=unknown，query 会 raise DbaseKeyError（triage 标"部分"）。
    桩：回落 0（蓄力机制未实现，需走 Marks flags 或 custom key 承接）。
    测试可 monkeypatch 本函数注入固定值。
    """
    return 0


def _random(rng: Any | None, n: int) -> int:
    """LPC random(n) 等价（对照 L162 random(wap/2)）。

    rng 为 None 时用 Python random（非 combat 确定性范围，与 xue.c learn 一致）。
    n <= 0 时返回 0（LPC random(0)=0）。
    """
    if n <= 0:
        return 0
    if rng is not None:
        return rng.rand(n) if hasattr(rng, "rand") else rng.randrange(n)
    import random

    return random.randrange(n)
