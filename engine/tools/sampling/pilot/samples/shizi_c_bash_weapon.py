"""pilot 样本 id=8：d/taohua/obj/shizi.c:bash_weapon 迁移代码。

对照 LPC d/taohua/obj/shizi.c L135-177，迁移桃花弹指神通砸武器的 combat
post_action。与 id=5 songshan-jian.c:next_sword 同构（四档判定 + unequip/
move/set/reset_action 副作用），差异：wap/wdp 公式用 neili 而非 jiali/xuli、
wap=random(wap)（非 random(wap/2)+wap/2）、四档阈值 2*wdp/wdp/wdp/2
（非 3/2/1）、断裂分支含 jiali<200 双消息 + damage<90 门控。本文件为一次性
测量代码，不污染 src/xkx（ADR-0048 决策 8）。

核心阻塞（triage[7]）：武器物品在 greenfield ECS 建模为 item_id 字符串
（Equipment.weapon: str|None），非实体，故 ob->weight()/query("rigidity")/
name()/query("weapon_prop/damage")/unequip()/move()/set() 一族对象方法调用
无直接等价目标。迁移用 WeaponItem 数据类做 item 属性台账适配层：
get_weapon(world, victim_eid) 取 victim 当前武器 item_id（Equipment.weapon，
对齐 query_temp("weapon")），返回 WeaponItem（weight/rigidity/damage/name），
默认值由测试注入控制四档命中。ob->unequip() 复用引擎 unequip(world,victim,item_id)；
ob->move()/set() 物品落入房间+改名/贬值因物品非实体无建模，以注释标出
（待迁移面：item-as-entity）；victim->reset_action() 用预建桩 no-op。
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from tools.sampling.pilot.stubs import (
    HIW,
    NOR,
    query_jiali,
    query_str,
    reset_action,
)

from xkx.runtime.commands import Game
from xkx.runtime.components import Equipment
from xkx.runtime.equipment import unequip
from xkx.runtime.query import query, query_skill, short


@dataclass
class WeaponItem:
    """武器物品属性台账（item-as-entity 缺口的适配层）。

    greenfield 物品非实体，无 weight()/query("rigidity")/name()/
    query("weapon_prop/damage") 对象方法。本类承载 bash_weapon 需读的 4 项
    物品属性，由 get_weapon 按 item_id 取得（测试注入控制四档命中）。
    """

    item_id: str
    name: str = "武器"
    weight: int = 0
    rigidity: int = 0
    damage: int = 0  # weapon_prop/damage


# item_id -> WeaponItem 台账。生产环境应由物品系统提供，此处为可注入默认表。
_WEAPON_REGISTRY: dict[str, WeaponItem] = {}


def get_weapon(world: object, victim_eid: int) -> WeaponItem | None:
    """取 victim 当前装备的武器（对照 LPC victim->query_temp("weapon")）。

    greenfield：victim 临时武器存于 Equipment.weapon（item_id 字符串），
    非武器对象 ob。返回 WeaponItem 台账条目（item-as-entity 缺口适配），
    无装备或台账无记录返回 None（对齐 LPC objectp(ob) 判假）。
    """
    equipment = world.get(victim_eid, Equipment)  # type: ignore[attr-defined]
    if equipment is None:
        return None
    item_id = equipment.weapon
    if not item_id:
        return None
    return _WEAPON_REGISTRY.get(item_id)


def _name(world: object, eid: int) -> str:
    """取实体显示名（对照 LPC $N/$n 代词替换）。"""
    return short(world, eid, raw=True)  # type: ignore[arg-type]


def bash_weapon(game: Game, actor_id: int, victim_id: int) -> list[str]:
    """shizi.c:bash_weapon 迁移（对照 L135-177）。

    桃花弹指神通砸武器 post_action：wap=neili+query_str+技能 与
    wdp=weight/500+rigidity+query_str+parry/2 对抗，四档判定
    （断裂 wap>2*wdp 且 damage<90 / 脱手 wap>wdp / 震动 wap>wdp/2 / 火星）。

    返回 actor 可见消息列表（LPC message_vision 副作用经代词替换后的文本）。
    LPC 原签名 int bash_weapon(me, victim) 返回 int + message_vision 房间广播；
    为测量可测性适配为返回消息列表（与 next_sword 同构样本对齐）。ob->move()/
    set() 物品落入房间+改名/贬值因物品非实体无建模，以注释标出。
    """
    world = game.world

    # L139：jiali = me->query("jiali")（dbase key 未映射，用预建桩回落 0）
    jiali = query_jiali(world, actor_id)

    # L141-142：neili>100 且 victim 有武器才进入判定
    neili = query(world, actor_id, "neili") or 0
    ob = get_weapon(world, victim_id)
    msgs: list[str] = []
    if not (neili > 100) or ob is None:
        return msgs

    # L143-149：wap / wdp 对抗公式
    wap = (
        int(neili)
        + query_str(world, actor_id)
        + query_skill(world, actor_id, "tanzhi-shentong", raw=True)
    )
    wdp = (
        ob.weight // 500
        + ob.rigidity
        + query_str(world, victim_id)
        + query_skill(world, victim_id, "parry") // 2
    )

    # L150：wap = random(wap)（系统 RNG，非 combat 确定性范围；wap<=0 返回 0）
    wap = random.randint(0, wap - 1) if wap > 0 else 0

    actor_name = _name(world, actor_id)
    victim_name = _name(world, victim_id)

    # L151-161：断裂分支（wap>2*wdp 且 damage<90）
    if wap > 2 * wdp and ob.damage < 90:
        # L153-154：jiali<200 双消息分支（普通断裂 / 火星四溅断裂）
        if jiali < 200:
            raw = HIW + "只听见「啪」地一声，$N手中的" + ob.name + HIW + "已经断为两截！\n" + NOR
        else:
            raw = (
                HIW + "小石子一撞之下，登时火星四溅，石子碎片八方乱射，"
                "「啪」地一声，" + ob.name + HIW + "断为两截！\n" + NOR
            )
        # message_vision 第二参为 victim（$N=victim 名）
        msgs.append(_render(raw, victim_name, ""))
        # L156-161：卸武器 + 物品落入房间 + 改名/贬值/清 weapon_prop + reset_action
        unequip(world, victim_id, ob.item_id)
        # ob->move(environment(victim))：物品落入房间，greenfield 物品非实体无
        #   建模（待迁移面 item-as-entity），此处以注释标出不产生副作用。
        # ob->set("name","断掉的"+name)/set("value",0)/set("weapon_prop",0)：
        #   物品改名/贬值/清属性，同属 item-as-entity 缺口，注释标出。
        reset_action(world, victim_id)
    # L162-169：脱手分支（wap>wdp）
    elif wap > wdp:
        if jiali < 200:
            raw = HIW + "$N只觉得手中" + ob.name + HIW + "把持不定，脱手飞出！\n" + NOR
        else:
            raw = (
                HIW
                + "小石子一撞之下，炸得粉碎，震得$N虎口疼痛，"
                + ob.name
                + HIW
                + "摔在地下！\n"
                + NOR
            )
        msgs.append(_render(raw, victim_name, ""))
        unequip(world, victim_id, ob.item_id)
        # ob->move(environment(victim))：物品落入房间，item-as-entity 缺口，注释标出。
        reset_action(world, victim_id)
    # L170-172：震动分支（wap>wdp/2）
    elif wap > wdp // 2:
        raw = "$N只觉得手中" + ob.name + "一震，险些脱手！\n"
        msgs.append(_render(raw, victim_name, ""))
    # L173-175：火星分支（else）
    else:
        raw = "$N射出的小石子和$n的" + ob.name + "相击，冒出点点的火星。\n"
        msgs.append(_render(raw, actor_name, victim_name))

    return msgs


def _render(msg: str, n_name: str, m_name: str) -> str:
    """message_vision 代词替换（$N/$n -> 名字）+ 砍 ANSI。

    对照 LPC message_vision：$N=第一参对象名、$n=第二参对象名。stubs.message_vision
    仅返回原 msg（代词替换后置 M3），此处本地完成替换以产出可断言文本。
    HIW/NOR 颜色常量为空串（颜色内核砍掉），strip_ansi 兜底清理测试注入带码串。
    """
    from tools.sampling.pilot.stubs import strip_ansi

    out = msg.replace("$N", n_name).replace("$n", m_name)
    return strip_ansi(out)
