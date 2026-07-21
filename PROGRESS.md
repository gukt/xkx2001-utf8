# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-21：M3 Wave 2 `/implement` + `/code-review` fix 完成。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2 完成**；**M3 Wave 0/1/2 完成**（票 `01`–`04`）；下一步 Wave 3（票 `05`）；post-MVP 见 [.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
- **工作分支**：`feat/m3-ugc-loop-creation-surface`（Wave 2 fixed point tag：`m3-wave2-start`）。
- **engine/**：测试绿（621）。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **M3 Wave 2 `/implement` + `/code-review` fix**（2026-07-21）：票 `03` CLI `--pack`/`--validate` + 票 `04` 废弃探测站示例包；fixed point `m3-wave2-start`。Review fix：缺目录错误前缀分层、默认存档目录断言、测试拆复合断言。621 绿。
- [x] **M3 Wave 1 `/implement` + `/code-review` fix**（2026-07-21）：票 `02`——`load_pack` + `World.pack_manifest` + `reattach_pack_manifest`；`save.py` 零改动；fixed point `m3-wave1-start`。Review fix：拆成功路径与 restore 复合断言。591 绿。
- [x] **M3 Wave 0 `/implement` + `/code-review` fix**（2026-07-21）：票 `01`——`PackManifest` + `load_manifest` + `PackManifestError`；fixed point `m3-wave0-start`。Review fix：去掉 helper 路径 Data Clump、合并 `_as_string`、`extra: dict[str, object]`。577 绿。
- [x] **M3 `/to-spec` + `/to-tickets` 完成**（2026-07-21）：[spec.md](.scratch/m3-ugc-loop-creation-surface/spec.md)（`ready-for-agent`）；5 张票 `01`–`05`；[to-tickets-notes.md](.scratch/m3-ugc-loop-creation-surface/to-tickets-notes.md)；[implement-plan.md](.scratch/m3-ugc-loop-creation-surface/implement-plan.md)（4 wave）。
- [x] **编辑器丢弃 + post-MVP backlog**（2026-07-21）：[ADR-0006](docs/adr/0006-no-engine-editor-board-post-mvp-creator-platform.md)；子系统 9→丢弃；Web 创作者平台 + 留言板记入 [post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)；档位 18/4/9/11。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

1. M3 Wave 3 `/implement`：票 `05`（端到端剧本 + `verify-m3` + 里程碑文档），见 [implement-plan.md](.scratch/m3-ugc-loop-creation-surface/implement-plan.md)。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [.scratch/progress-archive.md](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
- Post-MVP（不进 M0–M4）：[.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
