"""专家审核 checklist MVP（M3-3，ADR-0033 决策 4）。

对齐 [03 §八] 验证覆盖度六维矩阵（结构 / 数值 / 经济 / 任务逻辑 / 叙事 / 趣味），
前四维可机器 + 人工，后两维人工抽样。``REVIEW_CHECKLIST`` 是专家人工 review 的
结构化 checklist（人工 review 流程载体），``render_checklist_template`` 产出
markdown 模板。

**与自动化预检的关系**：预检（[precheck](precheck.py)）覆盖可机器化的维度
（暴力 / 敏感词 / 赌博 / 版权关键词 / license），checklist 覆盖预检无法判定的
人工维度（叙事一致性 / 趣味 / 数值平衡人工校准）。社区众审 / 平台终审后置。

[ADR-0033](../../../../docs/adr/ADR-0033-content-review-pipeline-mvp.md) 决策 4 /
[03 §八](../../../../docs/xkx-arch/03-DSL-UGC与Agent协作.md)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from xkx.content_review.rules import Category


class ReviewItemStatus(StrEnum):
    """专家审核项判定结果。"""

    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"
    NOTE = "note"  # 仅记录，不影响通过


@dataclass(frozen=True)
class ChecklistItem:
    """专家审核 checklist 项。

    Attributes:
        item_id: 项唯一标识。
        dimension: 03 §八六维（structure / numeric / economic / quest-logic /
            narrative / fun）。
        category: 对应预检维度（None = 纯人工，预检不覆盖）。
        description: 审核要点。
        required: 是否必查（False = 选查）。
        automated: 是否机器可查（False = 人工判）。
    """

    item_id: str
    dimension: str
    category: Category | None
    description: str
    required: bool = True
    automated: bool = False


#: 专家审核 checklist（M3 MVP，覆盖 03 §八六维）。
REVIEW_CHECKLIST: list[ChecklistItem] = [
    ChecklistItem(
        item_id="license_declared",
        dimension="structure",
        category=Category.LICENSE,
        description="CPK manifest 声明合规 license（非空，外部发布前校验白名单）。",
        automated=True,
    ),
    ChecklistItem(
        item_id="copyright_jinyong",
        dimension="narrative",
        category=Category.COPYRIGHT,
        description=(
            "金庸衍生角色 / 门派是否已清洗（改编化 / 标注同人非商用）。"
            "M3-4 后置，M3 阶段标记待处理。"
        ),
        automated=True,
    ),
    ChecklistItem(
        item_id="violence_scale",
        dimension="narrative",
        category=Category.VIOLENCE,
        description="暴力描写是否超武侠题材尺度（常态战斗不计）。",
    ),
    ChecklistItem(
        item_id="gambling_mechanics",
        dimension="narrative",
        category=Category.GAMBLING,
        description="是否含赌博玩法（合规风险）。",
        automated=True,
    ),
    ChecklistItem(
        item_id="sensitive_terms",
        dimension="narrative",
        category=Category.SENSITIVE,
        description="敏感词是否已接入合规词库扫描（M3 词库后置接入）。",
    ),
    ChecklistItem(
        item_id="structure_integrity",
        dimension="structure",
        category=None,
        description="rooms / npcs / quests 引用完整，entry_points.main_scene 可达"
        "（cpk_loader 已校验，专家确认无遗漏）。",
        automated=True,
    ),
    ChecklistItem(
        item_id="numeric_balance",
        dimension="numeric",
        category=None,
        description="NPC 属性 / 技能数值合理，无过强 / 过弱破坏平衡。",
    ),
    ChecklistItem(
        item_id="quest_logic_reachable",
        dimension="quest-logic",
        category=None,
        description="quest objectives 状态机可达，无死锁 / 不可完成。",
    ),
    ChecklistItem(
        item_id="narrative_consistency",
        dimension="narrative",
        category=None,
        description="世界观 / 对话 / 角色设定一致性，无矛盾。",
    ),
    ChecklistItem(
        item_id="fun_playtest",
        dimension="fun",
        category=None,
        description="playtest 反馈是否\"觉得好玩\"（人工抽样，目标玩家试玩）。",
        required=False,
    ),
]


@dataclass
class ExpertReview:
    """专家审核项判定记录（人工 review 流程载体）。

    Attributes:
        item_id: 对应 [ChecklistItem]。
        status: 判定结果。
        reviewer: 审核人。
        note: 备注。
    """

    item_id: str
    status: ReviewItemStatus
    reviewer: str = ""
    note: str = ""


def render_checklist_template() -> str:
    """渲染专家审核 checklist markdown 模板（人工 review 用）。"""
    lines: list[str] = []
    lines.append("# 专家审核 checklist（M3-3，ADR-0033）")
    lines.append("")
    lines.append(
        "> 对齐 [03 §八](../../../../docs/xkx-arch/03-DSL-UGC与Agent协作.md) "
        "六维矩阵。预检（自动化）覆盖可机器化维度，本 checklist 覆盖人工维度。"
        "社区众审 / 平台终审后置。"
    )
    lines.append("")
    lines.append("| item_id | 维度 | 预检维度 | 要点 | 必查 | 机器可查 | 判定 | 审核 | 备注 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for item in REVIEW_CHECKLIST:
        cat = item.category.value if item.category else "—"
        required = "是" if item.required else "否"
        automated = "是" if item.automated else "否"
        lines.append(
            f"| `{item.item_id}` | {item.dimension} | {cat} "
            f"| {item.description} | {required} | {automated} |  |  |  |"
        )
    lines.append("")
    lines.append("判定：`pass` / `fail` / `needs_review` / `note`。")
    lines.append("")
    return "\n".join(lines) + "\n"


__all__ = [
    "ReviewItemStatus",
    "ChecklistItem",
    "REVIEW_CHECKLIST",
    "ExpertReview",
    "render_checklist_template",
]
