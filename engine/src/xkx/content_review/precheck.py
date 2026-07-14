"""自动化预检（M3-3，ADR-0033 决策 2）。

对齐 [03 §八](../../../../docs/xkx-arch/03-DSL-UGC与Agent协作.md) 自动化预检：扫描
CPK 资产（``manifest.yaml`` + ``rooms/npcs/quests/items/rules/skills.yaml``）的所有
字符串值，匹配 [rules](rules.py) 4 类词表（暴力 / 敏感词 / 赌博 / 版权关键词）+
license 合规校验。

**扫描方式**：直接 ``yaml.safe_load`` 资产为 dict/list，递归遍历所有 str 值过词表。
不依赖 [layer0 Def](../dsl/layer0.py) 模型字段枚举（通用，新增字段自动覆盖，
Def 字段变更不波及预检）。

**license 合规**：空 license = ``block``（必须声明 license）；非空 = 放行（M3 宽松，
不校验白名单，外部发布前门3 严格化）。

**检测 ≠ 清洗**（用户决策 2026-07-14）：版权命中 ``needs_review`` 不 block，
M3-4 清洗后置。雪山派 4 金庸角色命中验证预检有效（标记待处理，不强制改）。

[ADR-0033](../../../../docs/adr/ADR-0033-content-review-pipeline-mvp.md) 决策 2 /
[03 §八](../../../../docs/xkx-arch/03-DSL-UGC与Agent协作.md)
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from xkx.content_review.rules import (
    ALL_TERMS,
    Category,
    Severity,
    Term,
    jinyong_role_work,
)
from xkx.dsl.cpk import CpkManifest

#: CPK 资产文件（与 [measure_revision](../../tools/measure_revision.py) SCENE_FILES 对齐）
ASSET_FILES: tuple[str, ...] = (
    "rooms.yaml",
    "npcs.yaml",
    "quests.yaml",
    "items.yaml",
    "rules.yaml",
    "skills.yaml",
)

#: Finding context 截断长度（字符）
CONTEXT_MAX = 80


@dataclass
class Finding:
    """单次违规命中。

    Attributes:
        cpk_id: 所属 CPK。
        file: 资产文件名（如 ``npcs.yaml``）或 ``manifest``。
        field_path: 字段路径（如 ``npcs[2].name``）。
        rule_id: 命中规则（对照 [rules](rules.py) ``Term.rule_id``）。
        category: 维度（暴力 / 敏感词 / 赌博 / 版权 / license）。
        severity: 严重级别。
        matched_term: 命中词。
        context: 命中文本片段（截断）。
        work: 版权归属小说（copyright 类填，供人工 review）。
    """

    cpk_id: str
    file: str
    field_path: str
    rule_id: str
    category: Category
    severity: Severity
    matched_term: str
    context: str
    work: str = ""


@dataclass
class PrecheckReport:
    """预检报告。

    Attributes:
        cpk_id: 所属 CPK。
        findings: 全部命中（按 file + field_path 排序）。
        license_ok: license 合规（空 license = False）。
        license_note: license 校验说明。
    """

    cpk_id: str
    findings: list[Finding] = field(default_factory=list)
    license_ok: bool = True
    license_note: str = ""

    @property
    def passed(self) -> bool:
        """无 block 级 finding 且 license 合规 = 通过。

        ``needs_review`` 不阻塞 passed（检测非清洗，需人工 review 后定）。
        """
        return self.license_ok and not any(
            f.severity == Severity.BLOCK for f in self.findings
        )

    @property
    def needs_review(self) -> bool:
        """存在 needs_review 级命中（需人工审核）。"""
        return any(f.severity == Severity.NEEDS_REVIEW for f in self.findings)

    def by_category(self) -> dict[Category, list[Finding]]:
        """按维度分组命中。"""
        groups: dict[Category, list[Finding]] = {}
        for f in self.findings:
            groups.setdefault(f.category, []).append(f)
        return groups

    def summary(self) -> str:
        """单行摘要（CLI 打印用）。"""
        parts = [
            f"CPK={self.cpk_id}",
            f"passed={self.passed}",
            f"findings={len(self.findings)}",
        ]
        if self.findings:
            cats = self.by_category()
            cat_str = ", ".join(
                f"{c.value}:{len(fs)}" for c, fs in cats.items()
            )
            parts.append(f"[{cat_str}]")
        if not self.license_ok:
            parts.append(f"license: {self.license_note}")
        return " | ".join(parts)

    def to_dict(self) -> dict:
        """序列化为 dict（写 ``_review.json`` 用，ADR-0022 可序列化）。"""
        return {
            "cpk_id": self.cpk_id,
            "passed": self.passed,
            "needs_review": self.needs_review,
            "license_ok": self.license_ok,
            "license_note": self.license_note,
            "findings": [
                {
                    "file": f.file,
                    "field_path": f.field_path,
                    "rule_id": f.rule_id,
                    "category": f.category.value,
                    "severity": f.severity.value,
                    "matched_term": f.matched_term,
                    "context": f.context,
                    "work": f.work,
                }
                for f in self.findings
            ],
        }


def _walk_strings(obj: object, path: str = "") -> Iterable[tuple[str, str]]:
    """递归遍历 dict/list，yield ``(field_path, str_value)``。

    不依赖具体 Def 模型（通用，新增字段自动覆盖）。
    """
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for key, val in obj.items():
            child = f"{path}.{key}" if path else str(key)
            yield from _walk_strings(val, child)
    elif isinstance(obj, list):
        for idx, val in enumerate(obj):
            child = f"{path}[{idx}]" if path else f"[{idx}]"
            yield from _walk_strings(val, child)


def _scan_text(text: str, terms: list[Term]) -> Iterable[tuple[Term, str]]:
    """对一段文本扫描词表，yield ``(term, matched_term)``。"""
    for term in terms:
        if not term.terms:
            continue
        for t in term.terms:
            if t in text:
                yield term, t


def _truncate(text: str, term: str, max_len: int = CONTEXT_MAX) -> str:
    """取命中词周围文本片段（含命中词），截断到 max_len。"""
    idx = text.find(term)
    if idx < 0:
        return text[:max_len]
    start = max(0, idx - max_len // 2)
    end = min(len(text), idx + len(term) + max_len // 2)
    snippet = text[start:end]
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + snippet + suffix


def _work_for(term: Term, matched: str) -> str:
    """版权类命中返回出处小说（[jinyong_role_work]），否则空。"""
    if term.category == Category.COPYRIGHT:
        return jinyong_role_work(matched) or ""
    return ""


def _check_license(manifest: CpkManifest) -> tuple[bool, str]:
    """license 合规校验：空 = block，非空 = 放行（M3 宽松）。"""
    if not manifest.license:
        return False, "license 为空（必须声明 license）"
    return True, f"license={manifest.license}"


def precheck_cpk(
    cpk_dir: Path | str,
    *,
    terms: list[Term] | None = None,
) -> PrecheckReport:
    """扫描 CPK 资产，产出预检报告。

    流程（ADR-0033 决策 2）：

    1. 读 ``manifest.yaml`` -> ``CpkManifest``（pydantic 校验 + license 合规）
    2. 递归扫描 manifest 文本字段（cpk_id / author / market 等）
    3. 逐个读资产 YAML（``rooms/npcs/quests/items/rules/skills``，缺失跳过），
       ``yaml.safe_load`` -> dict/list -> 递归扫描所有 str 值过词表
    4. 命中 -> ``Finding``，copyright 类附 ``work``（版权归属小说）

    Args:
        cpk_dir: CPK 目录路径（含 ``manifest.yaml`` + 资产 YAML）。
        terms: 词表（默认 [rules.ALL_TERMS](rules.py)）。

    Returns:
        ``PrecheckReport``：``passed`` = 无 block 级命中 + license 合规。
    """
    cpk_dir = Path(cpk_dir)
    manifest_path = cpk_dir / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"CPK manifest 缺失: {manifest_path}")

    manifest = CpkManifest.model_validate(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    )
    scan_terms = terms if terms is not None else ALL_TERMS

    findings: list[Finding] = []

    # license 合规
    license_ok, license_note = _check_license(manifest)
    if not license_ok:
        findings.append(
            Finding(
                cpk_id=manifest.cpk_id,
                file="manifest",
                field_path="license",
                rule_id="license_missing",
                category=Category.LICENSE,
                severity=Severity.BLOCK,
                matched_term="",
                context=license_note,
            )
        )

    # 扫描 manifest 文本字段（cpk_id / author / market 等）
    for path, text in _walk_strings(manifest.model_dump()):
        for term, matched in _scan_text(text, scan_terms):
            findings.append(
                Finding(
                    cpk_id=manifest.cpk_id,
                    file="manifest",
                    field_path=path,
                    rule_id=term.rule_id,
                    category=term.category,
                    severity=term.severity,
                    matched_term=matched,
                    context=_truncate(text, matched),
                    work=_work_for(term, matched),
                )
            )

    # 扫描资产 YAML
    for asset_file in ASSET_FILES:
        asset_path = cpk_dir / asset_file
        if not asset_path.exists():
            continue
        data = yaml.safe_load(asset_path.read_text(encoding="utf-8"))
        if data is None:
            continue
        for path, text in _walk_strings(data):
            for term, matched in _scan_text(text, scan_terms):
                findings.append(
                    Finding(
                        cpk_id=manifest.cpk_id,
                        file=asset_file,
                        field_path=path,
                        rule_id=term.rule_id,
                        category=term.category,
                        severity=term.severity,
                        matched_term=matched,
                        context=_truncate(text, matched),
                        work=_work_for(term, matched),
                    )
                )

    # 排序：file -> field_path -> rule_id
    findings.sort(key=lambda f: (f.file, f.field_path, f.rule_id, f.matched_term))

    return PrecheckReport(
        cpk_id=manifest.cpk_id,
        findings=findings,
        license_ok=license_ok,
        license_note=license_note,
    )


__all__ = [
    "ASSET_FILES",
    "Finding",
    "PrecheckReport",
    "precheck_cpk",
]
