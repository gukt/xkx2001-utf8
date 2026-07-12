"""多人协同攻击修正的声明式载体（题材数据注入 combat 内核做攻击修正）。

CombatModifier 是"题材数据注入 combat 内核做攻击修正"的声明式载体，类似
``HitCallbackResult``/``SkillData``（见 ``context.py``）。内核只做分发与数值修正，
具体协同攻击逻辑由题材数据声明，保持 ADR-0003 主题无关性。

决策依据 ADR-0027 §2.2：
- 协同攻击是题材内容（题材包武学脚本），不进 combat 内核。CombatModifier
  提供主题无关的通用字段结构，武侠题材与非武侠题材的协同攻击平等走同一
  声明路径。
- 内核职责：CombatSystem tick 中调 ``resolve_attack`` 前检查参战双方的协同标记，
  命中则从题材数据查 CombatModifier，注入 ``CombatContext`` 快照做 ap/dp 修正 +
  message 入 ledger + post_action 声明式副作用（order=47，对齐 SkillData
  post_action 语义）。
- 题材数据职责：填充 modifier_type / participants / 修正值 / message / post_action
  回调名。内核不解释 modifier_type 字符串与 post_action 回调名。

主题无关硬门禁：源码不得含武侠语义字面量（test_combat_modifier 断言）。

[ADR-0027](../../../docs/adr/ADR-0027-combat-callout-formation-golden-trace.md) §2.2
[ADR-0003](../../../docs/adr/ADR-0003-combatkernel-theme-neutrality.md) 主题无关性
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CombatModifier:
    """多人协同攻击修正的声明式载体（题材数据注入，内核只分发不解释）。

    frozen dataclass + slots=True：不可变（快照边界一次性求值后冻结，符合
    ADR-0023 单 tick 快照不可变语义）+ 内存紧凑（高频构造的值对象）。

    字段主题无关：``modifier_type`` 是通用类型枚举字符串（"formation" /
    "formation_break" / "combined_attack"），内核不解释其语义；``participants``
    是参与者 eid 列表（int，主题无关）；``message`` 含 ``$N``/``$n`` 占位符由
    PronounContext 渲染（见 ADR-0028）；``post_action`` 是回调名字符串，题材数据
    声明的 post_action，内核不解释。

    注入路径（ADR-0027 §2.2 内核职责）：
    - ``attack_modifier`` 叠加到 attacker 的 apply_attack（ap 修正）
    - ``defense_modifier`` 叠加到 victim 的 apply_dodge（dp 修正）
    - ``message`` 按 ADR-0023 ledger 交织顺序入账本（LEDGER_MESSAGE）
    - ``post_action`` 按 SkillData post_action 语义（order=47，声明式副作用入 ledger）
    """

    modifier_type: str
    """协同修正类型（通用枚举字符串，题材数据声明，内核不解释）。

    取值示例："formation" / "formation_break" / "combined_attack"。内核不做
    类型分发，只透传给题材数据侧的 post_action 回调。
    """

    participants: tuple[int, ...] = field(default_factory=tuple)
    """参与者 eid 列表（主题无关 int）。内核不解释参与者语义，只透传。"""

    attack_modifier: int = 0
    """ap 修正（加成为正，惩罚为负）。注入 attacker.apply_attack（ap += attack_modifier）。"""

    defense_modifier: int = 0
    """dp 修正（加成为正，惩罚为负）。注入 victim.apply_dodge（dp += defense_modifier）。"""

    message: str = ""
    """协同攻击文本（含 $N/$n 占位符，PronounContext 渲染，ADR-0028）。

    空串表示无附加文本。非空时按 ADR-0023 ledger 交织顺序入账本。
    """

    post_action: str | None = None
    """声明式 post_action 回调名（题材数据声明，内核不解释）。

    None = 无 post_action；非空时按 SkillData post_action 语义（order=47，
    声明式副作用入 ledger）。内核只透传回调名，具体执行由题材数据侧回调实现。
    """
