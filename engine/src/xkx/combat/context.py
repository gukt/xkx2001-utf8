"""``resolve_attack`` 的输入：战斗开始时的不可变快照 + seed。

快照取自 ECS 组件（Vitals/Attributes/CombatState/Skills 等），在战斗开始边界
一次性拷贝。``resolve_attack`` 只读快照、不 mutate 任何现场状态，所有变更
产出为 Effect（见 ``result.py``）由调用方 apply。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# attack_type 取值（对应 include/combat.h）
TYPE_REGULAR = 0
TYPE_RIPOSTE = 1
TYPE_QUICK = 2

# 默认徒手武器/技能名（题材无关；具体武器名由题材数据声明，内核不解释，见 ADR-0003）
WEAPON_UNARMED = "unarmed"


class CombatantSnapshot(BaseModel):
    """战斗参与者的不可变快照。字段映射 LPC dbase 的战斗相关键。"""

    entity_id: int
    name: str

    # 四维属性（LPC str/dex/int/con）
    str_: int = 10
    dex_: int = 10
    int_: int = 10
    con_: int = 10

    # 资源池：气/精/精力（LPC qi/jing/jingli；neili 内力不进核心签名，见 ADR-0003）
    qi: int = 100
    max_qi: int = 100
    eff_qi: int = 100
    jing: int = 100
    max_jing: int = 100
    jingli: int = 100
    max_jingli: int = 100

    # 经验/潜能
    combat_exp: int = 0
    potential: int = 0
    max_potential: int = 100

    # 技能 {skill_id: level}
    skills: dict[str, int] = Field(default_factory=dict)

    # 临时修正（LPC set_temp("apply/...")）
    apply_attack: int = 0
    apply_dodge: int = 0
    apply_parry: int = 0
    apply_damage: int = 0
    apply_armor: int = 0

    # 武器类型（None = 空手）；题材无关，内核不解释具体武器名
    weapon: str | None = None
    # 本回合招式所用技能 id（题材数据声明；S2 前由 weapon 推断，见 ADR-0003）
    attack_skill: str = WEAPON_UNARMED
    # 武器显示名（$w 占位符替换值；题材数据声明）
    weapon_label: str = "拳头"

    # 招式描述（S1 简化：从快照取，未来从 SkillData 取）
    # 占位符：$N=施动者名 $n=目标名 $w=武器 $l=攻击部位
    action_message: str = "$N一招「试探」，攻向$n$l"
    action_force: int = 100
    action_dodge: int = 30
    action_parry: int = 30
    action_damage: int = 20
    action_damage_type: str = "击伤"

    # S1 hit_ob/hit_by 回调的最小载体（int 加成/覆盖；mapping 分支后置）
    hit_ob_bonus: int = 0  # 叠加到 damage_bonus
    hit_by_override: int | None = None  # 覆盖最终 damage（None=不覆盖）


class CombatContext(BaseModel):
    """``resolve_attack`` 的输入：双方快照 + seed + 攻击类型。"""

    attacker: CombatantSnapshot
    victim: CombatantSnapshot
    seed: int
    attack_type: int = TYPE_REGULAR
    # 身体部位（LPC limbs；S1 固定最小集）
    limbs: tuple[str, ...] = ("头部", "胸口", "腹部", "左臂", "右臂", "左腿", "右腿")
