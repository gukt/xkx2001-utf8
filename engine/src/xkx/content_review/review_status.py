"""审核状态集成（M3-3，ADR-0033 决策 3）。

预检结果与 CPK manifest 关联（[03 §八]）：manifest 的 ``review_status`` 字段存
当前审核状态（轻量），详细 findings 落 ``_review.json``（资产 / 审核元数据分离，
避免审核迭代污染资产真相源）。

**状态推导**（[derive_status]）：

- 有 ``block`` 级 finding 或 license 不合规 -> ``rejected``
- 无 ``block`` 但有 ``needs_review`` -> ``needs_review``
- 无 ``block`` 无 ``needs_review`` -> ``passed``

**写回 manifest**（[sync_manifest_status]）：默认预检只落 ``_review.json``，不动
manifest.yaml（保护注释 / 格式）。``sync_manifest_status`` 显式同步时用 yaml 往返
写回（MVP 会丢失 YAML 注释，正式环境后置 ruamel；标注 rationale）。

[ADR-0033](../../../../docs/adr/ADR-0033-content-review-pipeline-mvp.md) 决策 3 /
[03 §八](../../../../docs/xkx-arch/03-DSL-UGC与Agent协作.md)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import yaml

from xkx.content_review.precheck import PrecheckReport
from xkx.content_review.rules import Severity
from xkx.dsl.cpk import CpkManifest, ReviewStatus

#: 详细 findings 报告文件名（CPK 目录下）
REVIEW_REPORT_FILENAME = "_review.json"


def derive_status(report: PrecheckReport) -> ReviewStatus:
    """根据预检报告推导审核状态。

    - 有 ``block`` 级 finding 或 license 不合规 -> ``rejected``
    - 无 ``block`` 但有 ``needs_review`` -> ``needs_review``
    - 否则 -> ``passed``
    """
    if not report.license_ok or any(
        f.severity == Severity.BLOCK for f in report.findings
    ):
        return ReviewStatus.REJECTED
    if report.needs_review:
        return ReviewStatus.NEEDS_REVIEW
    return ReviewStatus.PASSED


def write_review_report(
    cpk_dir: Path | str,
    report: PrecheckReport,
) -> Path:
    """落 ``_review.json``（derived status + findings + 时间戳）。

    Args:
        cpk_dir: CPK 目录。
        report: 预检报告。

    Returns:
        ``_review.json`` 路径。
    """
    cpk_dir = Path(cpk_dir)
    payload = {
        "cpk_id": report.cpk_id,
        "derived_status": derive_status(report).value,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "report": report.to_dict(),
    }
    out_path = cpk_dir / REVIEW_REPORT_FILENAME
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def sync_manifest_status(cpk_dir: Path | str) -> ReviewStatus | None:
    """读 ``_review.json`` derived_status，若 manifest 状态不同则写回 manifest。

    用 yaml 往返写回（``model_dump(mode="json")`` -> ``yaml.safe_dump``）。**MVP
    会丢失 manifest.yaml 注释**（正式环境后置 ruamel 保注释；标注 rationale）。
    默认预检不调用此函数（保护格式），需显式同步（CI / 人工）。

    Returns:
        同步后的 status，或 ``None``（无 ``_review.json``）。
    """
    cpk_dir = Path(cpk_dir)
    review_path = cpk_dir / REVIEW_REPORT_FILENAME
    if not review_path.exists():
        return None

    derived = ReviewStatus(json.loads(review_path.read_text(encoding="utf-8"))["derived_status"])

    manifest_path = cpk_dir / "manifest.yaml"
    manifest = CpkManifest.model_validate(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    )
    if manifest.review_status == derived:
        return derived

    data = manifest.model_dump(mode="json")
    data["review_status"] = derived.value
    # sort_keys=False 保留 CpkManifest 字段定义顺序
    manifest_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return derived


__all__ = [
    "REVIEW_REPORT_FILENAME",
    "derive_status",
    "write_review_report",
    "sync_manifest_status",
]
