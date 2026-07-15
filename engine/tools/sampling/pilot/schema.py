"""pilot 工时记录 schema 与校验。

每样本一条 EffortRecord，记录迁移工时分项 + 分类纠偏。
方法论见 ADR-0048 + 17 §六。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# 合法值枚举
STATUSES = ("implemented", "pending")
FUNC_KINDS = ("logic", "data")
TIERS = ("low", "mid", "high")


@dataclass
class EffortMin:
    """工时分项（分钟）。"""

    read_spec: int = 0
    write_code: int = 0
    write_test: int = 0
    debug: int = 0

    @property
    def subtotal(self) -> int:
        return self.read_spec + self.write_code + self.write_test + self.debug


@dataclass
class EffortRecord:
    """单样本迁移工时记录。"""

    file: str
    func: str
    subsystem: str
    status: str  # 原分类
    func_kind: str  # 原分类
    tier: str
    call_count: int
    corrected_status: str = ""  # 纠偏后分类（若与 status 不同）
    corrected_kind: str = ""  # 纠偏后分类
    misclassified: bool = False
    misclass_reason: str = ""
    effort: EffortMin = field(default_factory=EffortMin)
    reusable_api: list[str] = field(default_factory=list)
    missing_api: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def effective_status(self) -> str:
        return self.corrected_status or self.status

    @property
    def effective_kind(self) -> str:
        return self.corrected_kind or self.func_kind

    @property
    def stratum(self) -> str:
        """分层键：effective_status × effective_kind × tier。"""
        return f"{self.effective_status}/{self.effective_kind}/{self.tier}"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["effort"]["subtotal"] = self.effort.subtotal
        return d

    def validate(self) -> list[str]:
        """返回校验错误列表（空=通过）。"""
        errs: list[str] = []
        if self.status not in STATUSES:
            errs.append(f"status 非法: {self.status}")
        if self.func_kind not in FUNC_KINDS:
            errs.append(f"func_kind 非法: {self.func_kind}")
        if self.tier not in TIERS:
            errs.append(f"tier 非法: {self.tier}")
        if self.corrected_status and self.corrected_status not in STATUSES:
            errs.append(f"corrected_status 非法: {self.corrected_status}")
        if self.corrected_kind and self.corrected_kind not in FUNC_KINDS:
            errs.append(f"corrected_kind 非法: {self.corrected_kind}")
        if self.misclassified and not self.corrected_status and not self.corrected_kind:
            errs.append("misclassified=true 但未填 corrected_status/corrected_kind")
        return errs
