"""练功运行时函数（M3-1 ADR-0032 决策 2，对照 LPC ``feature/skill.c``）。

- ``improve_skill``：技能熟练度提升（learned 阈值升级，对照 skill.c:149-182）。
- ``is_busy``：busy condition 检查（dazuo/tuna 期间，对照 LPC ``is_busy()``）。
- ``get_skill_data``：SkillData 查询（M3-1 stub，注册表后置内容生产）。

busy 用 EffectComp 表达（ADR-0032 决策 2 + ADR-0027 call_out->Effect 翻译），
非 LPC heart_beat 轮询的 ``start_busy`` 状态机。dazuo/tuna 启动
``effect_id="exercise"/"respirate"`` 的 EffectComp，命令入口用 ``is_busy`` 检查
（不改 s2 权限段签名，2026-07-13 实施期细化裁决，对照 LPC bai.c:15 命令内检查）。

[ADR-0032](../../../docs/adr/ADR-0032-family-core-loop-design.md) 决策 2
"""

from __future__ import annotations

from xkx.combat.context import SkillData
from xkx.dsl.layer0 import SkillDef
from xkx.runtime.components import Identity, Skills
from xkx.runtime.conditions import query_condition
from xkx.runtime.ecs import World

# busy condition 集合（dazuo/tuna 启动的 EffectComp effect_id）。
# 对照 LPC feature/action.c is_busy + pending/exercise、pending/respirate 标志。
BUSY_CONDITIONS: frozenset[str] = frozenset({"exercise", "respirate"})

# 多技能学习惩罚阈值（对照 skill.c:165 spi = 30）。
_LEARN_PENALTY_SPI = 30

# SkillData 注册表（M3-1 stub：空注册表，get_skill_data 返回默认实例）。
# 正式武学数据（valid_learn/practice_skill/valid_enable/招式表）后置内容生产子任务
# （ADR-0032 决策 2 + 决策 5），由题材包 CPK 注入（ADR-0031）。
_SKILL_DATA_REGISTRY: dict[str, SkillData] = {}


def register_skill_data(skill_id: str, data: SkillData) -> None:
    """注册 SkillData（题材包 CPK 加载时调用，M3-1 后置内容生产）。"""
    _SKILL_DATA_REGISTRY[skill_id] = data


def register_skill_defs(defs: list[SkillDef]) -> None:
    """批量注册 SkillDef（CPK 加载时调用，ADR-0036）。

    dsl ``SkillDef`` -> combat ``SkillData`` 转换（runtime 边界，保持 dsl 纯净）。
    练功 stub 字段映射；combat 招式字段（action/dodge/parry/...）用 SkillData 默认值
    （query_action 招式表后置内容生产扩展）。
    """
    for d in defs:
        register_skill_data(
            d.skill_id,
            SkillData(
                skill_type=d.skill_type,
                valid_learn=d.valid_learn,
                practice_skill=d.practice_skill,
                valid_enable=list(d.valid_enable),
            ),
        )


def get_skill_data(skill_id: str) -> SkillData:
    """查 SkillData（M3-1 stub：未注册返回默认实例，全允许）。

    默认实例 valid_learn=True / practice_skill=True / valid_enable=[]（空=不限制）。
    正式数据后置内容生产（ADR-0032 决策 2）。
    """
    return _SKILL_DATA_REGISTRY.get(skill_id, SkillData())


def is_busy(world: World, eid: int) -> bool:
    """busy 检查（对照 LPC feature/action.c:21 is_busy）。

    dazuo/tuna 启动的 EffectComp（effect_id in BUSY_CONDITIONS）存在则 busy。
    greenfield busy 用 EffectComp 表达（ADR-0032 决策 2），非 LPC heart_beat 轮询。
    """
    return any(query_condition(world, eid, name) > 0 for name in BUSY_CONDITIONS)


def improve_skill(
    world: World, eid: int, skill: str, amount: int, *, weak_mode: bool = False
) -> bool:
    """提升技能熟练度（对照 feature/skill.c:149-182）。

    - 仅对玩家生效（LPC ``!userp -> return``，greenfield 用 ``Identity.is_player``）。
    - weak_mode=True：只累积 learned 点数，不初始化技能、不升级（practice 限制特殊
      技能不得超过基础技能时用，对照 skill.c:159-181 的 ``!weak_mode`` 条件）。
    - 多技能惩罚：已学技能种类 > 30 时 amount 按超出量整除衰减（skill.c:164-168）。
    - amount 下限 1（skill.c:170）。
    - 升级阈值：``learned > (lvl+1)²`` 严格大于（skill.c:175），升级后 learned 清零
      （溢出丢失，不连续跳级）。

    返回是否触发升级（True=本次升级），调用方据此输出"进步了"消息。
    """
    ident = world.get(eid, Identity)
    if ident is None or not ident.is_player:
        return False  # LPC skill.c:153-154 !userp -> return
    skills = world.get(eid, Skills)
    if skills is None:
        skills = Skills()
        world.add(eid, skills)
    # weak_mode=1 且玩家 -> 跳过技能初始化（skill.c:159-162）
    if not weak_mode and skill not in skills.levels:
        skills.levels[skill] = 0
    # 多技能惩罚（skill.c:164-168）
    if len(skills.learned) > _LEARN_PENALTY_SPI:
        amount //= len(skills.learned) - _LEARN_PENALTY_SPI
    # amount 下限（skill.c:170）
    if not amount:
        amount = 1
    # 累积学习点（skill.c:172-173，无论 weak_mode）
    skills.learned[skill] = skills.learned.get(skill, 0) + amount
    # 升级判定（skill.c:175-181，仅 !weak_mode）
    if not weak_mode:
        level = skills.levels.get(skill, 0)
        if skills.learned[skill] > (level + 1) ** 2:
            skills.levels[skill] = level + 1
            skills.learned[skill] = 0  # 清零（溢出丢失，不连续跳级）
            return True
    return False
