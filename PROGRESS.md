# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-21：M3 Wave 0 `/implement` 完成（`01` manifest），待 `/code-review`。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2 完成**；**M3 Wave 0 已落地**（票 `01`），待 code-review 后进 Wave 1；post-MVP 见 [.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
- **工作分支**：`feat/m3-ugc-loop-creation-surface`（Wave 0 fixed point tag：`m3-wave0-start`）。
- **engine/**：测试绿（577）；`just verify-*` / `just verify-m2` 未改。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **M3 Wave 0 `/implement`**（2026-07-21）：票 `01`——`PackManifest` + `load_manifest` + `PackManifestError`；fixed point `m3-wave0-start`；15 新测 + 全量 577 绿。待 `/code-review`。
- [x] **M3 `/to-spec` + `/to-tickets` 完成**（2026-07-21）：[spec.md](.scratch/m3-ugc-loop-creation-surface/spec.md)（`ready-for-agent`）；5 张票 `01`–`05`；[to-tickets-notes.md](.scratch/m3-ugc-loop-creation-surface/to-tickets-notes.md)；[implement-plan.md](.scratch/m3-ugc-loop-creation-surface/implement-plan.md)（4 wave）。
- [x] **编辑器丢弃 + post-MVP backlog**（2026-07-21）：[ADR-0006](docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md)；子系统 9→丢弃；Web 创作者平台 + 留言板记入 [post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)；档位 18/4/9/11。
- [x] **M3 前核对：03 细化**（2026-07-21）：[03](.scratch/mvp-scope/issues/03-ugc-dsl-design-inheritance.md) Refinement；[ADR-0005](docs/adr/0005-m3-ugc-loop-creation-surface.md)（M3 包外创作面；编辑器归类已被 0006 修正）。
- [x] **M2 verify 能力面矩阵 + journey**（2026-07-21）：`verify_harness.py`；`verify_m2_*`；`just verify-m2`；pytest `test_verify_m2_matrices.py`。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

1. M3 Wave 0 `/code-review`（fixed point `m3-wave0-start`，spec：`.scratch/m3-ugc-loop-creation-surface/spec.md` + `issues/01-*.md`），fix 后进 Wave 1（票 `02`）。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
- Post-MVP（不进 M0–M4）：[.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
