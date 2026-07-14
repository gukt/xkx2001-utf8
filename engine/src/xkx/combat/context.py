"""``resolve_attack`` 的输入：战斗开始时的不可变快照 + seed。

快照取自 ECS 组件（Vitals/Attributes/CombatState/Skills 等），在战斗开始边界
一次性拷贝。``resolve_attack`` 只读快照、不 mutate 任何现场状态，所有变更
产出为 Effect（见 ``result.py``）由调用方 apply。

T6（ADR-0023）扩展：
- ``SkillData`` 招式描述载体（主题无关字段，题材数据填充具体值）。
- ``HitCallbackResult`` hit_ob/hit_by 回调的声明式结果载体（回调实现由题材数据
  声明，在快照构建边界求值为声明式 result，内核只做返回类型分发，不解释回调
  逻辑--保持 ADR-0003 主题无关性 + 快照可序列化以支撑确定性重放）。

2.4（ADR-0027）扩展：
- ``CombatantSnapshot.formation_modifier``：阵法合击修正载体（``CombatModifier``，
  主题无关声明式载体）。题材数据在快照构建边界注入（runtime 层 CombatBridge 从
  Marks 查阵法标记 -> 查题材数据 CombatModifier -> 注入本字段），combat 包不查
  Marks，由 runtime 层注入（后置整合）。CombatSystem.tick 只读本字段，构建
  CombatContext 时 apply 到快照副本（ap/dp 修正 + message 替换）。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from xkx.combat.modifier import CombatModifier

# attack_type 取值（对应 include/combat.h）
TYPE_REGULAR = 0
TYPE_RIPOSTE = 1
TYPE_QUICK = 2

# 默认徒手武器/技能名（题材无关；具体武器名由题材数据声明，内核不解释，见 ADR-0003）
WEAPON_UNARMED = "unarmed"

# skill_power 用途（对应 LPC SKILL_USAGE_*）
SKILL_USAGE_ATTACK = 1
SKILL_USAGE_DEFENSE = 2


class SkillData(BaseModel):
    """招式描述载体（主题无关字段结构，具体招式内容由题材数据填充）。

    字段对齐 LPC ``action`` mapping（``feature/attack.c`` ``reset_action`` 取
    ``query("actions")``）。内核不解释招式名（如"试探"/"横扫"），只做 ``$N``/
    ``$n``/``$w``/``$l`` 占位符替换。

    T6 补 ADR-0023 简化台账第 6 项（技能 action 描述）：快照从 SkillData 取值
    而非固定字面量。武侠武学与非武侠武器平等走同一声明路径。
    """

    action: str = "$N一招「试探」，攻向$n$l"
    dodge: int = 30
    parry: int = 30
    damage: int = 20
    force: int = 100
    damage_type: str = "击伤"
    # post_action 声明式副作用（题材数据声明；内核不解释，只 apply 返回值入 ledger）
    # None = 无 post_action；非空时按规格 side_effects order=47 在七步后处理阶段 apply
    post_action_result: str | None = None
    # M3-1 练功 stub（ADR-0032 决策 2，正式武学数据后置内容生产子任务）。
    # LPC SKILL_D(skill)->method() 的声明式简化：valid_learn/practice_skill 简化为
    # 布尔（LPC 是函数可动态判定，greenfield 内容生产期由题材数据声明）。
    skill_type: str = ""  # LPC type()：martial/knowledge/...（learn combat_exp 门控用）
    valid_learn: bool = True  # LPC valid_learn(me) 简化布尔
    practice_skill: bool = True  # LPC practice_skill(me) 简化布尔（武器检查后置）
    valid_enable: list[str] = Field(default_factory=list)  # 可 enable 的种类（空=不限制）


class HitCallbackResult(BaseModel):
    """hit_ob/hit_by 回调的声明式结果载体（ADR-0023 决策 4）。

    LPC 中 ``hit_ob``/``hit_by`` 回调可返回 ``string``（追加文本）/ ``int``
    （damage 修正或覆盖）/ ``mapping``（含 ``result`` 文本 + ``damage`` 修正）。
    回调实现由题材数据声明（武侠武学/非武侠武器各自的回调逻辑），在快照构建
    边界求值为本载体。内核只做返回类型分发：

    - ``message``: 追加文本，入 ledger 为 ``LEDGER_MESSAGE``（对应 string 返回）
    - ``damage_delta``: damage 修正，入 ledger 为 ``KIND_DAMAGE`` 副作用（对应
      mapping 的 ``damage`` 键；hit_ob 叠加、hit_by 覆盖由调用方区分）
    - ``override``: 仅 hit_by 有效，覆盖最终 damage（对应 int 返回）

    主题无关：字段通用，具体值由题材数据填充。可序列化以支撑确定性重放。
    """

    message: str = ""
    damage_delta: int = 0
    override: int | None = None


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
    apply_speed: int = 0  # 2.3：apply/speed（fight/riposte 判定，ADR-0026 §1）

    # 武器类型（None = 空手）；题材无关，内核不解释具体武器名
    weapon: str | None = None
    # 本回合招式所用技能 id（题材数据声明；S2 前由 weapon 推断，见 ADR-0003）
    attack_skill: str = WEAPON_UNARMED
    # 武器显示名（$w 占位符替换值；题材数据声明）
    weapon_label: str = "拳头"

    # 招式描述（T6：从 SkillData 取值，见 ADR-0023 决策 4 第 6 项）
    # 占位符：$N=施动者名 $n=目标名 $w=武器 $l=攻击部位
    action_message: str = "$N一招「试探」，攻向$n$l"
    action_force: int = 100
    action_dodge: int = 30
    action_parry: int = 30
    action_damage: int = 20
    action_damage_type: str = "击伤"
    # post_action 声明式副作用文本（None=无；非空时七步后处理入 ledger，规格 order=47）
    action_post_action_result: str | None = None

    # hit_ob/hit_by 回调载体（T6：mapping 分支补全，见 ADR-0023 决策 4 第 1 项）
    # hit_ob：命中时叠加 damage_bonus + 追加文本（规格 side_effects order=23/25/26）
    # 回调实现由题材数据声明，在快照边界求值为 HitCallbackResult（内核只分发返回类型）
    hit_ob_bonus: int = 0  # S1 int 加成（向后兼容；叠加到 damage_bonus）
    hit_ob: HitCallbackResult | None = None  # T6 mapping 分支（声明式 result 载体）
    # hit_by：被命中时覆盖最终 damage + 追加文本（规格 side_effects order=32/33）
    hit_by_override: int | None = None  # S1 int 覆盖（向后兼容）
    hit_by: HitCallbackResult | None = None  # T6 mapping 分支（声明式 result 载体）

    # guarding temp（LPC set_temp("guarding")；riposte 触发条件之一，规格 order=48）
    # victim guarding=1 且 TYPE_REGULAR + damage<1 时触发 riposte 递归（T6 决策 4 第 2 项）
    guarding: int = 0

    # is_fighting 标记（LPC is_fighting()；skill_power DEFENSE 折减判定，主题无关）
    # 快照内可判定，不依赖运行时 ECS（ADR-0023 决策 4 第 4 项）
    is_fighting: bool = False

    # fight/dodge temp（LPC set_temp("fight/dodge")；skill_power DEFENSE 加成，规格 order=7）
    # is_fighting() 时 DEFENSE 额外乘 (100 + fight/dodge/10) / 100
    fight_dodge: int = 0

    # 阵法合击修正载体（ADR-0027 §2.3 special_attack 调用点）。
    # 题材数据在快照构建边界注入：runtime 层 CombatBridge 从 Marks 查阵法标记 ->
    # 查题材数据 CombatModifier -> 注入本字段。combat 包不查 Marks（combat 包自包含，
    # ADR-0023 决策 2），由 runtime 层注入（后置整合）。
    # CombatSystem.tick 只读本字段：非空时 apply 到快照副本（ap/dp 修正 + message
    # 替换），再调 resolve_attack。None = 无阵法修正，行为不变（回归基线）。
    formation_modifier: CombatModifier | None = None


class CombatContext(BaseModel):
    """``resolve_attack`` 的输入：双方快照 + seed + 攻击类型。"""

    attacker: CombatantSnapshot
    victim: CombatantSnapshot
    seed: int
    attack_type: int = TYPE_REGULAR
    # 身体部位（LPC limbs；S1 固定最小集）
    limbs: tuple[str, ...] = ("头部", "胸口", "腹部", "左臂", "右臂", "左腿", "右腿")
    # riposte 递归深度（防死循环，ADR-0023 决策 4 第 2 项；LPC 无显式限制但由
    # guarding temp 消耗自然终止，T6 加硬上限兜底）
    riposte_depth: int = 0
