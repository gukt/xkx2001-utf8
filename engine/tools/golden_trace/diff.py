"""golden trace 三层 diff 工具（ADR-0027 §3）。

对照 LPC baseline（[baseline/](baseline/)）与 greenfield ``resolve_attack``
输出，分三层做行为等价验证（定位辅助验证，非主线门禁，[ADR-0009]
(../../../docs/adr/ADR-0009-original-driver-runnable.md)）：

- **L1 概率分布 diff**：greenfield 多 seed 采样统计 dodge/hit/parry 频率，
  对照 LPC 理论模型（dodge_p=dp/(ap+dp)，parry_p=pp/(ap+pp)，
  hit_p=1-d-p）+ baseline 实测（combat_stats.json），卡方检验或区间匹配。
- **L2 文本结构 diff**：按回合分隔 + ANSI 剥离 + do_attack 七步结构匹配
  （取招式 / AP-DP / 闪避 / 招架 / 伤害 / 状态 / 行为）+ 伤害描述分类映射
  （LPC 瘀青/瘀伤/肿 -> greenfield damage 区间，参考 s_combatd.c damage_msg）。
- **L3 语义 diff**：占位符 $N/$n/$w/$l 渲染对照 PronounContext
  （[ADR-0028](../../../docs/adr/ADR-0028-rank-d-spec-and-pronoun-context.md)）。

非侵入设计（对齐 [ADR-0013](../../../docs/adr/ADR-0013-engine-toolchain-prd.md)
Combat Replay Viewer）：只消费 ledger + baseline，不修改 combat 内核。

CLI::

    cd engine
    .venv/bin/python -m tools.golden_trace.diff --baseline baseline/ \
        --snapshot <snapshot.json> --seed 42 --rounds 1000
    .venv/bin/python -m tools.golden_trace.diff --baseline baseline/ \
        --greenfield <combat_sim_output.json>

[ADR-0027](../../../docs/adr/ADR-0027-combat-callout-formation-golden-trace.md) §3
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from xkx.combat.context import CombatantSnapshot, CombatContext
from xkx.combat.resolve_attack import ATTACK, DEFENSE, resolve_attack, skill_power
from xkx.combat.result import (
    RESULT_DODGE,
    RESULT_PARRY,
    CombatRoundResult,
)
from xkx.runtime.pronoun import PronounContext, PronounService

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# ANSI 转义序列（\x1b[...m），剥离后做文本结构 diff
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# LPC damage_type -> 中文描述（s_combatd.c damage_msg 的 case 分支）
# greenfield CombatantSnapshot.action_damage_type 默认 "击伤"，LPC 瘀伤类对应徒手
_LPC_DAMAGE_TYPES = ("擦伤", "抓伤", "割伤", "劈伤", "砍伤", "刺伤", "跌伤",
                     "鞭伤", "咬伤", "瘀伤", "挫伤", "内伤")

# 伤害描述分类（从 baseline clean 文本提取的伤害结算行关键词 -> 分类标签）
# 参考 s_combatd.c damage_msg "瘀伤" 分支的区间 -> 描述映射（行 135-142）：
#   damage<10  -> "轻轻地碰到"
#   damage<20  -> "瘀青"
#   damage<40  -> "肿了一块老高" / "痛得弯下腰去"
#   damage<80  -> "闷哼" / "吃了不小的亏"
#   damage<120 -> "退了两步"
#   damage<160 -> "连退了好几步"
#   damage<240 -> "吐出一口鲜血"
#   else       -> "飞了出去"
#
# baseline clean 实测的伤害结算行样本：
#   "结果一击命中，把你打得痛得弯下腰去！"  -> 中伤（damage 20-40）
#   "结果在你的左手造成一处瘀青。"          -> 轻伤（damage 10-20）
#   "结果一击命中，你的后心登时肿了一块老高！" -> 中伤（damage 20-40）
#   "结果你的两肋上被划出一道细长的血痕。"   -> 轻伤（割伤 damage 20-40，映射瘀伤轻伤）
#
# 伤害分类（粗粒度，对齐 LPC 描述性文本而非数值）：
_DAMAGE_CATEGORIES: list[tuple[str, tuple[str, ...]]] = [
    # (分类标签, 触发关键词元组)
    ("none", ("没有对", "造成任何伤害", "毫发无损")),
    ("graze", ("蹭破", "擦了一道白印", "牙印", "轻轻地碰到", "轻轻地蹭", "轻轻地划")),
    ("bruise", ("瘀青", "瘀伤", "血痕", "创口", "屁墩")),
    ("swell", ("肿了一块", "痛得弯下腰", "闷哼", "吃了不小的亏", "退了两步",
               "连退了好几步", "着实地被摔", "被摔了一下")),
    ("severe", ("吐出一口鲜血", "鲜血狂喷", "气血倒流", "皮开肉绽", "骨头",
                "血淋淋", "血肉模糊", "皮肉尽裂", "对穿而出", "飞了出去",
                "塌了下去", "惨叫", "喀喀")),
]

# 七步文本结构标签（对应 README §八 do_attack 七步）
STEP_ACTION = "action"        # (1) 取招式：攻击动作描述
STEP_APDP = "ap_dp"           # (2) AP/DP 计算：内部，无文本
STEP_DODGE = "dodge"          # (3) 闪避判定
STEP_PARRY = "parry"          # (4) 招架判定
STEP_DAMAGE = "damage"        # (5) 伤害结算
STEP_STATUS = "status"        # (6) 状态报告（括号内）
STEP_BEHAVIOR = "behavior"    # (7) 战斗行为

# 七步全序列（含无文本步骤，用于结构匹配）
SEVEN_STEPS = (
    STEP_ACTION, STEP_APDP, STEP_DODGE, STEP_PARRY,
    STEP_DAMAGE, STEP_STATUS, STEP_BEHAVIOR,
)

# 状态报告行特征（括号包裹，"你..."开头）
_STATUS_RE = re.compile(r"^\(\s*(.+?)\s*\)\s*$")
# 攻击动作行特征（含攻击动词）
_ACTION_VERBS = ("捶", "踢", "抓", "挥拳", "一抓", "一踢", "一拳", "攻", "击",
                 "刺", "砍", "劈", "抽", "咬", "摔")
# 闪避行特征
_DODGE_MARKERS = ("闪了开去", "及时避开", "躲开", "避开", "闪身")
# 招架行特征
_PARRY_MARKERS = ("格挡", "挡住", "招架")
# 伤害结算行特征（"结果..."开头）
_DAMAGE_PREFIX = "结果"
# 战斗行为行特征（非攻击方的"你...寻找/移动/盯/注视"等伺机行为）
_BEHAVIOR_MARKERS = ("寻找进攻", "伺机出手", "寻找机会", "移动著脚步",
                     "目不转睛", "注视", "企图寻找")


# ---------------------------------------------------------------------------
# ANSI 剥离 + 文本结构解析（L2 基础设施）
# ---------------------------------------------------------------------------


def strip_ansi(text: str) -> str:
    """剥离 ANSI 颜色码（\\x1b[...m）。

    baseline clean 已剥离，raw 保留；diff 统一先剥离再做结构匹配。
    """
    return _ANSI_RE.sub("", text)


def classify_damage_line(text: str) -> str:
    """伤害结算行 -> 伤害分类标签（瘀青/瘀伤/肿/轻伤/重伤等映射）。

    LPC 伤害文本是描述性（非数值），按 s_combatd.c damage_msg 区间 -> 描述
    映射分类。返回 "none" / "graze" / "bruise" / "swell" / "severe" 之一；
    无法分类返回 "unknown"。
    """
    for category, keywords in _DAMAGE_CATEGORIES:
        if any(kw in text for kw in keywords):
            return category
    return "unknown"


def classify_line(line: str) -> str:
    """单行文本 -> 七步结构标签。

    依据 baseline clean 实测的文本特征做关键词匹配：
    - 状态报告：括号包裹的 "( 你看起来...)"
    - 伤害结算：以 "结果" 开头
    - 闪避：含闪避关键词
    - 招架：含招架关键词
    - 战斗行为：含伺机行为关键词
    - 攻击动作：含攻击动词 + 攻击部位/目标
    - 其他：返回空字符串（非七步文本，如回合分隔/对话/死亡衔接）
    """
    stripped = line.strip()
    if not stripped:
        return ""
    # 状态报告（括号包裹）
    if _STATUS_RE.match(stripped):
        return STEP_STATUS
    # 伤害结算（"结果..."开头）
    if stripped.startswith(_DAMAGE_PREFIX):
        return STEP_DAMAGE
    # 闪避判定
    if any(m in stripped for m in _DODGE_MARKERS):
        return STEP_DODGE
    # 招架判定
    if any(m in stripped for m in _PARRY_MARKERS):
        return STEP_PARRY
    # 战斗行为（伺机出手等）
    if any(m in stripped for m in _BEHAVIOR_MARKERS):
        return STEP_BEHAVIOR
    # 攻击动作（含攻击动词）
    if any(v in stripped for v in _ACTION_VERBS):
        return STEP_ACTION
    return ""


@dataclass
class RoundText:
    """单回合解析后的文本结构（七步标签 -> 文本行）。

    AP/DP 步骤无文本（内部计算），故 steps 不含 ``ap_dp`` 键。
    """

    lines: list[str] = field(default_factory=list)
    steps: dict[str, str] = field(default_factory=dict)
    damage_category: str = "none"

    @property
    def has_dodge(self) -> bool:
        """本回合是否闪避。"""
        return STEP_DODGE in self.steps

    @property
    def has_parry(self) -> bool:
        """本回合是否招架。"""
        return STEP_PARRY in self.steps

    @property
    def has_hit(self) -> bool:
        """本回合是否命中（有伤害结算行 = 命中）。"""
        return STEP_DAMAGE in self.steps and self.damage_category != "none"


def parse_rounds(text: str) -> list[RoundText]:
    """按回合分隔解析 baseline 文本 -> 回合列表。

    回合分隔规则（README §九）：combat heart_beat 1 回合/秒，回合间空行分隔；
    每回合以"攻击动作行"开头（取招式步骤）。非七步文本（对话/死亡衔接/
    场景描述）不归属任何回合（被跳过或作为回合间分隔）。

    解析策略：按空行分块，每块内逐行分类；块中若含攻击动作行则视为一个回合。
    """
    cleaned = strip_ansi(text)
    rounds: list[RoundText] = []
    # 按连续空行分块
    blocks = re.split(r"\n\s*\n", cleaned)
    for block in blocks:
        round_lines = [ln for ln in block.split("\n") if ln.strip()]
        if not round_lines:
            continue
        # 块内须含攻击动作行才算一个 do_attack 回合
        classified = [(ln, classify_line(ln)) for ln in round_lines]
        if not any(tag == STEP_ACTION for _, tag in classified):
            continue
        rt = RoundText(lines=round_lines)
        damage_cat = "none"
        for ln, tag in classified:
            if tag == STEP_DAMAGE:
                cat = classify_damage_line(ln)
                if cat != "unknown":
                    damage_cat = cat
                rt.steps[tag] = ln.strip()
            elif tag:
                rt.steps[tag] = ln.strip()
        rt.damage_category = damage_cat
        rounds.append(rt)
    return rounds


# ---------------------------------------------------------------------------
# L1 概率分布 diff
# ---------------------------------------------------------------------------


def lpc_theoretical_probs(
    attacker: CombatantSnapshot, victim: CombatantSnapshot
) -> dict[str, float]:
    """LPC 理论概率模型（layer_e 31 处 random 概率模型）。

    resolve_attack 中 dodge/parry 是顺序判定（非独立）：
    - (3) dodge 先判定：P(dodge) = dp / (ap + dp)，成功则 return
    - (4) dodge 失败后 parry 判定：P(parry) = (1 - P(dodge)) * pp / (ap + pp)
    - (5) hit = 1 - P(dodge) - P(parry)

    故边际概率为条件概率链（非 dp/(ap+dp) + pp/(ap+pp) 独立相加）。
    ap/dp/pp 取 ``skill_power`` 计算值（与 resolve_attack 内部一致）。
    parry：victim 有 parry 技能用 parry，否则用 attack_skill（与 resolve_attack 一致）。
    """
    attack_skill = attacker.attack_skill
    ap = max(1, skill_power(attacker, attack_skill, ATTACK))
    dp = max(1, skill_power(victim, "dodge", DEFENSE))
    parry_skill = "parry" if "parry" in victim.skills else attack_skill
    pp = max(
        1,
        skill_power(
            victim, parry_skill, DEFENSE, apply_parry_path=(parry_skill == "parry")
        ),
    )
    dodge_p = dp / (ap + dp)
    # parry 在 dodge 失败后才判定（resolve_attack 顺序 return 语义）
    parry_p = (1.0 - dodge_p) * pp / (ap + pp)
    hit_p = 1.0 - dodge_p - parry_p
    if hit_p < 0:
        hit_p = 0.0
    return {"dodge_p": dodge_p, "parry_p": parry_p, "hit_p": hit_p}


@dataclass
class SampleStats:
    """greenfield 多 seed 采样的统计结果。"""

    n: int = 0
    dodge: int = 0
    parry: int = 0
    hit: int = 0

    @property
    def dodge_p(self) -> float:
        return self.dodge / self.n if self.n > 0 else 0.0

    @property
    def parry_p(self) -> float:
        return self.parry / self.n if self.n > 0 else 0.0

    @property
    def hit_p(self) -> float:
        return self.hit / self.n if self.n > 0 else 0.0


def sample_distribution(
    attacker: CombatantSnapshot,
    victim: CombatantSnapshot,
    n: int = 1000,
    seed_base: int = 0,
    limbs: tuple[str, ...] | None = None,
) -> SampleStats:
    """greenfield 多 seed 采样统计 dodge/hit/parry 频率。

    构造同属性 CombatantSnapshot + resolve_attack N 次（每次 seed 不同），
    统计 result_code 分布。非侵入：只读快照 + 调纯函数，不 mutate 现场。
    """
    if limbs is None:
        limbs = ("头部", "胸口", "腹部", "左臂", "右臂", "左腿", "右腿")
    stats = SampleStats()
    for i in range(n):
        ctx = CombatContext(
            attacker=attacker.model_copy(),
            victim=victim.model_copy(),
            seed=seed_base + i,
            limbs=limbs,
        )
        result = resolve_attack(ctx)
        stats.n += 1
        if result.result_code == RESULT_DODGE:
            stats.dodge += 1
        elif result.result_code == RESULT_PARRY:
            stats.parry += 1
        else:
            stats.hit += 1
    return stats


def chi_square_goodness_of_fit(
    observed: list[int], expected_probs: list[float]
) -> float:
    """卡方拟合优度检验（返回 p 值）。

    ``observed``：观测频数列表 [dodge, parry, hit]。
    ``expected_probs``：理论概率列表 [dodge_p, parry_p, hit_p]。
    p > 0.05 表示观测分布与理论分布无显著差异（通过）。

    样本量小（n<5 per cell）时返回 -1.0 表示检验不可靠（改用区间匹配）。
    """
    n = sum(observed)
    if n == 0:
        return 0.0
    expected = [p * n for p in expected_probs]
    # 期望频数 < 5 时卡方检验不可靠
    if any(e < 5 for e in expected):
        return -1.0
    chi2 = sum((o - e) ** 2 / e for o, e in zip(observed, expected, strict=True))
    # 自由度 = 类别数 - 1 = 2（三分类：dodge/parry/hit）
    df = len(observed) - 1
    return _chi2_p_value(chi2, df)


def _chi2_p_value(chi2: float, df: int) -> float:
    """卡方分布的 p 值（上侧概率）。

    用 Wilson-Hilferty 正态近似（df>=1）：
    z = ((chi2/df)^(1/3) - (1 - 2/(9*df))) / sqrt(2/(9*df))
    p = 1 - Phi(z)
    """
    if df <= 0:
        return 1.0
    if chi2 <= 0:
        return 1.0
    c = 2.0 / (9.0 * df)
    ratio = chi2 / df
    if ratio <= 0:
        return 1.0
    z = (ratio ** (1.0 / 3.0) - (1 - c)) / (c ** 0.5)
    # 标准正态 CDF 的上侧概率
    return 1.0 - _normal_cdf(z)


def _normal_cdf(z: float) -> float:
    """标准正态分布 CDF（Abramowitz & Stegun 26.2.17 近似）。"""
    # 用 erf 近似
    return 0.5 * (1.0 + _erf(z / (2 ** 0.5)))


def _erf(x: float) -> float:
    """erf 近似（Abramowitz & Stegun 7.1.26，最大误差 1.5e-7）。"""
    sign = 1.0 if x >= 0 else -1.0
    ax = abs(x)
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911
    t = 1.0 / (1.0 + p * ax)
    y = 1.0 - (
        (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t
    ) * _exp(-ax * ax)
    return sign * y


def _exp(x: float) -> float:
    """math.exp 的包装（避免顶层 import math 被误删）。"""
    import math

    return math.exp(x)


@dataclass
class L1Report:
    """L1 概率分布 diff 报告。"""

    passed: bool = False
    method: str = ""  # "chi_square" / "interval_match"
    n_samples: int = 0
    sample_probs: dict[str, float] = field(default_factory=dict)
    theoretical_probs: dict[str, float] = field(default_factory=dict)
    baseline_probs: dict[str, float] = field(default_factory=dict)
    chi_square_p: float | None = None
    tolerance: float = 0.0
    issues: list[str] = field(default_factory=list)


def diff_l1(
    attacker: CombatantSnapshot,
    victim: CombatantSnapshot,
    baseline_probs: dict[str, float],
    n_samples: int = 1000,
    seed_base: int = 0,
    tolerance: float = 0.08,
) -> L1Report:
    """L1 概率分布 diff：greenfield 采样 vs LPC 理论模型 + baseline 实测。

    判定（ADR-0027 §3.4）：
    - 主判定：greenfield 采样分布与 LPC 理论模型一致（卡方 p>0.05 或区间匹配）。
    - 辅助参照：baseline 实测分布（n=15 样本小，作参考非门禁）。

    ``tolerance``：区间匹配容差（采样概率与理论概率差 <= tolerance 视为一致）。
    """
    stats = sample_distribution(attacker, victim, n=n_samples, seed_base=seed_base)
    theory = lpc_theoretical_probs(attacker, victim)

    sample_probs = {
        "dodge_p": stats.dodge_p,
        "parry_p": stats.parry_p,
        "hit_p": stats.hit_p,
    }

    report = L1Report(
        n_samples=n_samples,
        sample_probs=sample_probs,
        theoretical_probs=theory,
        baseline_probs=baseline_probs,
        tolerance=tolerance,
    )

    # 卡方检验（样本足够时首选）
    observed = [stats.dodge, stats.parry, stats.hit]
    expected_probs = [theory["dodge_p"], theory["parry_p"], theory["hit_p"]]
    p_value = chi_square_goodness_of_fit(observed, expected_probs)

    if p_value >= 0:
        # 卡方检验可用
        report.method = "chi_square"
        report.chi_square_p = p_value
        report.passed = p_value > 0.05
        if not report.passed:
            report.issues.append(
                f"卡方检验 p={p_value:.4f} <= 0.05，采样分布与理论模型有显著差异"
            )
    else:
        # 期望频数不足，改用区间匹配
        report.method = "interval_match"
        diffs = {
            k: abs(sample_probs[k] - theory[k])
            for k in ("dodge_p", "parry_p", "hit_p")
        }
        report.passed = all(d <= tolerance for d in diffs.values())
        if not report.passed:
            for k, d in diffs.items():
                if d > tolerance:
                    report.issues.append(
                        f"{k}: 采样 {sample_probs[k]:.4f} vs 理论 {theory[k]:.4f}"
                        f"，偏差 {d:.4f} 超容差 {tolerance}"
                    )

    # baseline 实测对照（参考，不影响 passed 判定）
    for k in ("dodge_p", "parry_p", "hit_p"):
        base_val = baseline_probs.get(k)
        if base_val is None:
            continue
        diff = abs(sample_probs[k] - base_val)
        # baseline n=15 样本小，容差放宽（binomial 95% CI 约 +-0.25 @ p=0.3）
        if diff > 0.25:
            report.issues.append(
                f"{k}: 采样 {sample_probs[k]:.4f} vs baseline {base_val:.4f}"
                f"（n=15 样本小，参考）"
            )

    return report


# ---------------------------------------------------------------------------
# L2 文本结构 diff
# ---------------------------------------------------------------------------


@dataclass
class L2Report:
    """L2 文本结构 diff 报告。"""

    passed: bool = False
    baseline_rounds: int = 0
    greenfield_rounds: int = 0
    step_match_rate: float = 0.0
    damage_category_matches: int = 0
    damage_category_mismatches: int = 0
    issues: list[str] = field(default_factory=list)
    round_details: list[dict[str, Any]] = field(default_factory=list)


def greenfield_round_structure(result: CombatRoundResult) -> RoundText:
    """从 greenfield resolve_attack 结果提取七步文本结构。

    greenfield 输出的 ``result.messages`` 对应七步中产出文本的步骤：
    - (1) action_message（取招式）
    - (3) dodge 消息（闪避时）/ (4) parry 消息（招架时）
    - (5) 伤害结算消息（命中时）
    - (6)(7) 状态/行为消息（T6 未完整产出，post_action 可补）

    AP/DP (2) 无文本（内部计算）。
    """
    rt = RoundText()
    for text in result.messages:
        tag = classify_line(text)
        if tag:
            rt.steps[tag] = text
            rt.lines.append(text)
        else:
            rt.lines.append(text)
    # 命中时从伤害消息分类
    if STEP_DAMAGE in rt.steps:
        rt.damage_category = classify_damage_line(rt.steps[STEP_DAMAGE])
    # result_code 推断 dodge/parry
    if result.result_code == RESULT_DODGE:
        rt.steps.setdefault(STEP_DODGE, "(dodge)")
    elif result.result_code == RESULT_PARRY:
        rt.steps.setdefault(STEP_PARRY, "(parry)")
    return rt


def diff_l2(
    baseline_text: str,
    greenfield_results: list[CombatRoundResult],
) -> L2Report:
    """L2 文本结构 diff：baseline 七步文本 vs greenfield resolve_attack 输出。

    匹配维度：
    - 回合数对照（baseline 14 回合 vs greenfield N 回合）
    - 七步结构匹配（dodge/parry/hit 分支一致性）
    - 伤害描述分类映射（瘀青/瘀伤/肿 -> greenfield damage 区间分类）

    非逐字 diff（LPC random() 每次不同），只校验结构 + 分类一致性。
    """
    baseline_rounds = parse_rounds(baseline_text)
    greenfield_rounds = [greenfield_round_structure(r) for r in greenfield_results]

    report = L2Report(
        baseline_rounds=len(baseline_rounds),
        greenfield_rounds=len(greenfield_rounds),
    )

    n = min(len(baseline_rounds), len(greenfield_rounds))
    if n == 0:
        report.issues.append(
            f"回合数为 0（baseline={len(baseline_rounds)}, "
            f"greenfield={len(greenfield_rounds)}）"
        )
        report.passed = False
        return report

    step_matches = 0
    step_total = 0
    cat_matches = 0
    cat_mismatches = 0

    for i in range(n):
        b = baseline_rounds[i]
        g = greenfield_rounds[i]
        detail: dict[str, Any] = {"round": i}

        # 分支一致性（dodge/parry/hit）
        branch_match = (
            b.has_dodge == g.has_dodge and b.has_parry == g.has_parry
        )
        step_total += 1
        if branch_match:
            step_matches += 1
        else:
            report.issues.append(
                f"回合 {i}: 分支不一致 baseline(dodge={b.has_dodge},"
                f"parry={b.has_parry}) vs greenfield(dodge={g.has_dodge},"
                f"parry={g.has_parry})"
            )
        detail["branch_match"] = branch_match

        # 伤害分类映射（命中回合）
        if b.has_hit and g.has_hit:
            step_total += 1
            if b.damage_category == g.damage_category:
                cat_matches += 1
                step_matches += 1
                detail["damage_category"] = b.damage_category
            else:
                cat_mismatches += 1
                report.issues.append(
                    f"回合 {i}: 伤害分类不一致 baseline={b.damage_category}"
                    f" vs greenfield={g.damage_category}"
                )
                detail["damage_category_mismatch"] = (
                    f"{b.damage_category} vs {g.damage_category}"
                )

        report.round_details.append(detail)

    report.step_match_rate = (
        step_matches / step_total if step_total > 0 else 0.0
    )
    report.damage_category_matches = cat_matches
    report.damage_category_mismatches = cat_mismatches

    # 回合数差异（参考，不直接 fail）
    if len(baseline_rounds) != len(greenfield_rounds):
        report.issues.append(
            f"回合数差异：baseline={len(baseline_rounds)} vs "
            f"greenfield={len(greenfield_rounds)}（参考，非门禁）"
        )

    # 通过标准：分支一致性 100% + 伤害分类匹配率 >= 80%
    report.passed = (
        step_matches == step_total
        and cat_mismatches <= max(1, cat_matches // 5)
    )
    return report


# ---------------------------------------------------------------------------
# L3 语义 diff
# ---------------------------------------------------------------------------


@dataclass
class L3Report:
    """L3 语义 diff 报告。"""

    passed: bool = False
    placeholders_checked: int = 0
    render_matches: int = 0
    render_mismatches: int = 0
    issues: list[str] = field(default_factory=list)
    details: list[dict[str, Any]] = field(default_factory=list)


def diff_l3(
    templates_and_contexts: list[tuple[str, PronounContext]],
) -> L3Report:
    """L3 语义 diff：占位符 $N/$n/$w/$l 渲染对照 PronounContext。

    输入：(模板, PronounContext) 对列表。每个模板含 $N/$n/$w/$l 等占位符，
    用 ``PronounService.render`` 渲染，对照预期（模板内占位符替换后应与
    PronounContext 对应字段一致）。

    本函数验证 ``PronounService.render`` 正确替换 10 变量占位符（$N/$n/$P/$p/
    $C/$c/$R/$r/$S/$s），combat 的 $w/$l 由 resolve_attack 内部 ``_render``
    处理（$w=weapon_label, $l=limb），L3 只校验 PronounContext 的 10 变量。
    """
    report = L3Report()
    for template, ctx in templates_and_contexts:
        rendered = PronounService.render(template, ctx)
        # 构造预期：手动替换占位符
        expected = template
        replacements = {
            "$N": ctx.name_me,
            "$n": ctx.name_you,
            "$P": ctx.pronoun_me,
            "$p": ctx.pronoun_you,
            "$C": ctx.close,
            "$c": ctx.close_rev,
            "$R": ctx.respect,
            "$r": ctx.respect_rev,
            "$S": ctx.self,
            "$s": ctx.self_rude,
        }
        for ph, val in replacements.items():
            expected = expected.replace(ph, val)

        # 统计占位符数量
        for ph in replacements:
            count = template.count(ph)
            report.placeholders_checked += count

        if rendered == expected:
            report.render_matches += 1
        else:
            report.render_mismatches += 1
            report.issues.append(
                f"渲染不一致：template={template!r} "
                f"rendered={rendered!r} expected={expected!r}"
            )
        report.details.append({
            "template": template,
            "rendered": rendered,
            "expected": expected,
            "match": rendered == expected,
        })

    report.passed = report.render_mismatches == 0 and report.placeholders_checked > 0
    return report


# ---------------------------------------------------------------------------
# 综合报告
# ---------------------------------------------------------------------------


@dataclass
class DiffReport:
    """三层 diff 综合报告（JSON 可序列化）。"""

    l1: L1Report = field(default_factory=L1Report)
    l2: L2Report = field(default_factory=L2Report)
    l3: L3Report = field(default_factory=L3Report)

    @property
    def passed(self) -> bool:
        """三层全通过（L1 概率 + L2 文本结构 + L3 语义）。"""
        return self.l1.passed and self.l2.passed and self.l3.passed

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 可存储字典。"""
        return {
            "passed": self.passed,
            "l1": _report_to_dict(self.l1),
            "l2": _report_to_dict(self.l2),
            "l3": _report_to_dict(self.l3),
        }


def _report_to_dict(report: Any) -> dict[str, Any]:
    """dataclass -> dict（递归）。"""
    if hasattr(report, "__dataclass_fields__"):
        result: dict[str, Any] = {}
        for k in report.__dataclass_fields__:
            v = getattr(report, k)
            if hasattr(v, "__dataclass_fields__"):
                result[k] = _report_to_dict(v)
            elif isinstance(v, list):
                result[k] = [
                    _report_to_dict(i) if hasattr(i, "__dataclass_fields__") else i
                    for i in v
                ]
            elif isinstance(v, dict):
                result[k] = {
                    kk: _report_to_dict(vv) if hasattr(vv, "__dataclass_fields__") else vv
                    for kk, vv in v.items()
                }
            else:
                result[k] = v
        return result
    return report


# ---------------------------------------------------------------------------
# baseline 消费
# ---------------------------------------------------------------------------


def load_baseline(baseline_dir: str | Path) -> dict[str, Any]:
    """加载 baseline 目录（combat_huashan_clean.txt + combat_stats.json + meta.json）。

    返回 dict：{"clean_text": str, "stats": dict, "meta": dict}
    """
    base = Path(baseline_dir)
    clean_text = (base / "combat_huashan_clean.txt").read_text(encoding="utf-8")
    stats = json.loads((base / "combat_stats.json").read_text(encoding="utf-8"))
    meta = json.loads((base / "meta.json").read_text(encoding="utf-8"))
    return {"clean_text": clean_text, "stats": stats, "meta": meta}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools.golden_trace.diff",
        description="golden trace 三层 diff 工具（ADR-0027 §3）",
    )
    parser.add_argument(
        "--baseline",
        required=True,
        help="baseline 目录路径（含 combat_huashan_clean.txt + combat_stats.json）",
    )
    parser.add_argument(
        "--snapshot",
        help="greenfield CombatSnapshot JSON 文件路径（用于 L1 采样）",
    )
    parser.add_argument(
        "--greenfield",
        help="greenfield combat-sim 输出 JSON 文件路径（含 output_frames，用于 L2）",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=1000,
        help="L1 采样次数（默认 1000）",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="L1 采样 seed 基（默认 0）",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.08,
        help="L1 区间匹配容差（默认 0.08）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式报告",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：加载 baseline + greenfield -> 三层 diff -> 打印报告。

    退出码：0=三层全通过 / 1=参数错误 / 2=diff 有差异（非全通过）。
    """
    args = _build_arg_parser().parse_args(argv)
    baseline = load_baseline(args.baseline)
    baseline_probs = baseline["stats"].get("probabilities", {})

    # L1：需要 snapshot 构造同属性快照采样
    l1 = L1Report()
    if args.snapshot:
        from xkx.combat.replay import CombatSnapshot

        snap = CombatSnapshot.model_validate_json(
            Path(args.snapshot).read_text(encoding="utf-8")
        )
        # 取前两个 combatant 做 attacker/victim
        ids = sorted(snap.combatants.keys())
        if len(ids) >= 2:
            attacker = snap.combatants[ids[0]]
            victim = snap.combatants[ids[1]]
            l1 = diff_l1(
                attacker,
                victim,
                baseline_probs,
                n_samples=args.rounds,
                seed_base=args.seed,
                tolerance=args.tolerance,
            )

    # L2：需要 greenfield combat-sim 输出（output_frames）
    l2 = L2Report()
    greenfield_results: list[CombatRoundResult] = []
    if args.greenfield:
        data = json.loads(Path(args.greenfield).read_text(encoding="utf-8"))
        greenfield_results = [
            CombatRoundResult.model_validate(f) for f in data.get("output_frames", [])
        ]
    if greenfield_results:
        l2 = diff_l2(baseline["clean_text"], greenfield_results)
    else:
        # 无 greenfield 输出时，仅校验 baseline 自身可解析
        rounds = parse_rounds(baseline["clean_text"])
        l2.baseline_rounds = len(rounds)
        l2.passed = len(rounds) > 0
        if not l2.passed:
            l2.issues.append("baseline 无法解析出任何回合")

    # L3：占位符渲染对照（内置测试用例）
    test_ctx = PronounContext(
        name_me="甲",
        name_you="乙",
        pronoun_me="你",
        pronoun_you="他",
        close="小兄弟",
        close_rev="大哥",
        respect="大侠",
        respect_rev="少侠",
        self="在下",
        self_rude="老子",
    )
    templates = [
        "$N对$n喝道：「今日不是你死就是我活！」",
        "$C看$p一眼，$S决定出手。",
        "$R对$c说：$s来也！",
        "$N挥$w攻向$n的$l。",
    ]
    l3 = diff_l3([(t, test_ctx) for t in templates])

    report = DiffReport(l1=l1, l2=l2, l3=l3)

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_report(report)

    return 0 if report.passed else 2


def _print_report(report: DiffReport) -> None:
    """人类可读报告输出。"""
    status = "PASS" if report.passed else "FAIL"
    print(f"=== golden trace diff 综合结果: {status} ===\n")

    l1 = report.l1
    print(f"[L1 概率分布] {'PASS' if l1.passed else 'FAIL'}")
    print(f"  方法: {l1.method}, 采样数: {l1.n_samples}")
    if l1.chi_square_p is not None:
        print(f"  卡方 p 值: {l1.chi_square_p:.4f}")
    print(
        f"  采样: dodge={l1.sample_probs.get('dodge_p', 0):.4f} "
        f"parry={l1.sample_probs.get('parry_p', 0):.4f} "
        f"hit={l1.sample_probs.get('hit_p', 0):.4f}"
    )
    print(
        f"  理论: dodge={l1.theoretical_probs.get('dodge_p', 0):.4f} "
        f"parry={l1.theoretical_probs.get('parry_p', 0):.4f} "
        f"hit={l1.theoretical_probs.get('hit_p', 0):.4f}"
    )
    print(
        f"  baseline: dodge={l1.baseline_probs.get('dodge_p', 0):.4f} "
        f"parry={l1.baseline_probs.get('parry_p', 0):.4f} "
        f"hit={l1.baseline_probs.get('hit_p', 0):.4f}"
    )
    for issue in l1.issues:
        print(f"  ! {issue}")
    print()

    l2 = report.l2
    print(f"[L2 文本结构] {'PASS' if l2.passed else 'FAIL'}")
    print(f"  baseline 回合数: {l2.baseline_rounds}")
    print(f"  greenfield 回合数: {l2.greenfield_rounds}")
    print(f"  结构匹配率: {l2.step_match_rate:.2%}")
    print(f"  伤害分类匹配/不匹配: {l2.damage_category_matches}/{l2.damage_category_mismatches}")
    for issue in l2.issues:
        print(f"  ! {issue}")
    print()

    l3 = report.l3
    print(f"[L3 语义] {'PASS' if l3.passed else 'FAIL'}")
    print(f"  占位符检查数: {l3.placeholders_checked}")
    print(f"  渲染匹配/不匹配: {l3.render_matches}/{l3.render_mismatches}")
    for issue in l3.issues:
        print(f"  ! {issue}")
    print()


if __name__ == "__main__":
    raise SystemExit(main())
