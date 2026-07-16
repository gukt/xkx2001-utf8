"""CHAR_D 角色初始化编排（对照 adm/daemons/chard.c setup_char）。

把 LPC ``adm/daemons/chard.c:22-114`` 的 ``setup_char`` daemon 编排正式化到
引擎层：8 种族 dispatch（当前只 human，其余后置 M3，ADR-0030 决策 3）+
dbase 兜底初始化 + eff 钳位 + 玩家 neili/jingli 超限钳位 + NPC force 自动
设置 + shen 公式 + max_encumbrance + reset_action。

human 种族基础由 ``setup_race``（race.py，对照 human.c setup_human 通用部分）
承接，本模块只做 chard.c L61-113 的编排层。门派加成（family.apply_family_bonuses）
不在 setup_char 范围，后置题材包 CPK。

POSTPONED：pighead/jiajin/shen_type/behavior_exp/quest_exp（dbase_map 无组件
承接）用本地默认值参与计算，待对应子系统迁移补全。

[ADR-0030](../../../docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md) /
[adm/daemons/chard.c](../../../adm/daemons/chard.c)
"""

from __future__ import annotations

from collections.abc import Callable

from xkx.runtime.components import (
    Attributes,
    Equipment,
    Identity,
    Progression,
    Skills,
    TitleComp,
    Vitals,
)
from xkx.runtime.ecs import World
from xkx.runtime.equipment import reset_action
from xkx.runtime.query import query_skill
from xkx.runtime.race import HUMAN_PROFILE, RaceProfile, setup_race

# 已知非人类种族（daemon 后置 M3，setup_char 时 noop 跳过，对照 chard.c:36-56）
_KNOWN_NONHUMAN_RACES: frozenset[str] = frozenset(
    {"妖魔", "野兽", "家畜", "飞禽", "游鱼", "蛇类", "昆虫"}
)


def setup_char(
    world: World,
    eid: int,
    *,
    race: str = "",
    rng: Callable[[], int] | None = None,
    profile: RaceProfile = HUMAN_PROFILE,
) -> str:
    """CHAR_D->setup_char 编排（对照 adm/daemons/chard.c L22-114）。

    Args:
        race: 种族名（未传或空走"人类"兜底，chard.c:27-30）。
        rng: 随机数生成器（返回非负整数，传 setup_race 属性随机；默认 random）。
        profile: 人类种族基础数据（题材包注入，ADR-0030，默认 HUMAN_PROFILE）。

    返回 dispatch 的种族名。

    范围：human 调 ``setup_race``；chard.c L61-113 编排层（dbase 兜底/eff 钳位/
    neili·jingli 超限钳位/NPC force/shen/max_encumbrance/reset_action）。8 种族
    daemon dispatch 当前只 human，其余 7 种族后置 M3（ADR-0030 决策 3），未知
    种族名 raise ValueError（chard.c:57-58 default error）。

    要求实体已挂载 Attributes/Vitals/Progression/Equipment 组件（spawn_player/
    build_world 完成）；Identity/Skills/TitleComp 可选（缺失则跳过对应编排）。
    """
    # chard.c:27-30：race 未定义兜底"人类"
    if not race:
        race = "人类"

    # chard.c:32-59：8 种族 switch dispatch（只 human 覆盖，其余后置 noop）
    if race == "人类":
        setup_race(world, eid, profile, rng=rng)
    elif race not in _KNOWN_NONHUMAN_RACES:
        raise ValueError(f"Chard: undefined race {race}.")

    attrs = world.get(eid, Attributes)
    vitals = world.get(eid, Vitals)
    prog = world.get(eid, Progression)
    ident = world.get(eid, Identity)
    skills = world.get(eid, Skills)
    assert vitals is not None and attrs is not None and prog is not None

    is_player = bool(ident and ident.is_player)

    # chard.c:64-66：jing/qi/jingli 未定义（<=0 视为未初始化）兜底 = max
    if vitals.jing <= 0:
        vitals.jing = vitals.max_jing
    if vitals.qi <= 0:
        vitals.qi = vitals.max_qi
    if vitals.jingli <= 0:
        vitals.jingli = vitals.max_jingli

    # chard.c:68-69：eff_jing/eff_qi 未定义或超 max 钳到 max
    if vitals.eff_jing == 0 or vitals.eff_jing > vitals.max_jing:
        vitals.eff_jing = vitals.max_jing
    if vitals.eff_qi == 0 or vitals.eff_qi > vitals.max_qi:
        vitals.eff_qi = vitals.max_qi

    # chard.c:75-92：玩家 force 有效 > 基础时，max_neili 钳到 force*con*2/3、
    # max_jingli 钳到 force*con/2（下限 100），neili/jingli 钳到各自 max。
    # LPC 两个独立 if 条件相同（force_eff>force_raw），合并为一块等价。
    if is_player and skills is not None:
        force_eff = query_skill(world, eid, "force")
        force_raw = query_skill(world, eid, "force", raw=True)
        if force_eff > force_raw:
            cap_neili = force_raw * attrs.con_ * 2 // 3
            if vitals.max_neili > cap_neili:
                vitals.max_neili = cap_neili
            if vitals.neili > vitals.max_neili:
                vitals.neili = vitals.max_neili
            cap_jingli = force_raw * attrs.con_ // 2
            if vitals.max_jingli > cap_jingli:
                vitals.max_jingli = cap_jingli
            if vitals.jingli > vitals.max_jingli:
                vitals.jingli = vitals.max_jingli
            if vitals.max_jingli < 100:
                vitals.max_jingli = 100

    # chard.c:94-95：NPC 有 max_neili 但 force<1 时 set_skill("force", max_neili/6)
    if (
        not is_player
        and skills is not None
        and vitals.max_neili
        and query_skill(world, eid, "force", raw=True) < 1
    ):
        skills.levels["force"] = vitals.max_neili // 6

    # chard.c:97-104：shen_type（POSTPONED 本地 0）兜底；shen 未定义（==0）时
    # 玩家=0、NPC=shen_type*combat_exp/10。shen 映射 TitleComp.shen 可写
    shen_type = 0  # POSTPONED，待 shen_type 子系统迁移
    title = world.get(eid, TitleComp)
    if title is not None and title.shen == 0:
        title.shen = 0 if is_player else shen_type * prog.combat_exp // 10

    # chard.c:109-111：max_encumbrance 为 0 时补 str*5000（简化：忽略 query_str-str
    # 的 1000 系数项，greenfield 无 query_str 派生）
    equipment = world.get(eid, Equipment)
    if equipment is not None and not equipment.max_encumbrance:
        equipment.max_encumbrance = attrs.str_ * 5000

    # chard.c:113：reset_action（actions 闭包后置 M3，当前只刷 attack_skill）
    reset_action(world, eid)

    return race


__all__ = ["setup_char"]
