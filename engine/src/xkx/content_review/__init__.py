"""内容审核 pipeline MVP（M3-3，ADR-0033）。

创作期工具，不进 runtime 导入图（runtime 不 import 本包）。仅依赖 stdlib +
已有 pyyaml + pydantic，无新运行时依赖（04 §六 收敛原则）。

组件：

- [rules](rules.py)：4 类词表（暴力 / 敏感词 / 赌博 / 版权关键词）+ Severity /
  Category。
- [precheck](precheck.py)：自动化预检（扫描 CPK 资产所有 str 值 + license 校验）。
- [review_status](review_status.py)：审核状态推导 + ``_review.json`` 落盘 + manifest
  同步。
- [checklist](checklist.py)：专家审核 checklist MVP（六维矩阵，人工 review 载体）。

**M3-4 版权清洗（71 文件改编化 / 标注 / 授权）后置**（未商业化阶段过早清洗是过度
工程，用户决策 2026-07-14）。M3-3 只做**检测**，版权命中标记 ``needs_review``
不 block，商业化前清洗时预检已就位。

[ADR-0033](../../../../docs/adr/ADR-0033-content-review-pipeline-mvp.md) /
[03 §八](../../../../docs/xkx-arch/03-DSL-UGC与Agent协作.md)
"""

from xkx.content_review.checklist import (
    REVIEW_CHECKLIST,
    ChecklistItem,
    ExpertReview,
    ReviewItemStatus,
    render_checklist_template,
)
from xkx.content_review.precheck import (
    ASSET_FILES,
    Finding,
    PrecheckReport,
    precheck_cpk,
)
from xkx.content_review.review_status import (
    REVIEW_REPORT_FILENAME,
    derive_status,
    sync_manifest_status,
    write_review_report,
)
from xkx.content_review.rules import (
    ALL_TERMS,
    COPYRIGHT_TERMS,
    GAMBLING_TERMS,
    SENSITIVE_TERMS,
    VIOLENCE_TERMS,
    Category,
    Severity,
    Term,
    jinyong_role_work,
)

__all__ = [
    # rules
    "Severity",
    "Category",
    "Term",
    "VIOLENCE_TERMS",
    "SENSITIVE_TERMS",
    "GAMBLING_TERMS",
    "COPYRIGHT_TERMS",
    "ALL_TERMS",
    "jinyong_role_work",
    # precheck
    "ASSET_FILES",
    "Finding",
    "PrecheckReport",
    "precheck_cpk",
    # review_status
    "REVIEW_REPORT_FILENAME",
    "derive_status",
    "write_review_report",
    "sync_manifest_status",
    # checklist
    "REVIEW_CHECKLIST",
    "ChecklistItem",
    "ExpertReview",
    "ReviewItemStatus",
    "render_checklist_template",
]
