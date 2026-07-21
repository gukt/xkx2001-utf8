# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-21：M3 停机加固 Wave 0 `/implement` + `/code-review` fix 完成（664 绿）；下一步新 session 开 Wave 1。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2/M3 里程碑可宣布完成**；当前窗口 = **M3 停机加固**——**退出标准仅 P0（S0）**；同 effort 规划 **B3 wave**（选定 P1，非门闩）；**暂缓 M4**。加固整体完成后、开 M4 **之前**插入 **Pre-M4 引擎房间保真**（已记笔记，待 grill）。
- **工作分支**：`feat/m3-ugc-loop-creation-surface`（加固 Wave 0 fixed point：`m3-hardening-wave0-start`）。
- **engine/**：测试绿（664）；Wave 0（票 `01`–`05`）已落地并通过 `/code-review` fix——spec 见 [m3-hardening/spec.md](.scratch/m3-hardening/spec.md)，票见 [m3-hardening/issues/](.scratch/m3-hardening/issues/)，执行计划见 [implement-plan.md](.scratch/m3-hardening/implement-plan.md)。
- **拍板依据**：[评审 Final](.scratch/m3-engine-architecture-review/final/m3-engine-architecture-review-report.md)；[ADR-0007](docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)～[0009](docs/adr/0009-single-process-single-world.md)；[CONTEXT.md](CONTEXT.md)。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **M3 停机加固 Wave 0 落地：P0 五张独立实现票**（2026-07-21）：票 `01` 昏迷 tick 苏醒 / `02` 少林山门去持刃 / `03` combat 消灭全局态 / `04` `wire_runtime` / `05` `--validate`/`--strict`；fixed point `m3-hardening-wave0-start`。Review fix：CLI 严格校验测试按 `When*` 拆分复合断言；`DEFAULT_UNCONSCIOUS_RECOVERY_TICKS` + `_world_death_policy`。664 绿。
- [x] **Pre-M4 引擎房间保真：session 笔记落盘并排队**（2026-07-21）：LPC vs 引擎缺口对照写入 [.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)（[README](.scratch/pre-m4-engine-room-fidelity/README.md) + [session-notes](.scratch/pre-m4-engine-room-fidelity/session-notes-2026-07-21.md)）；`PROGRESS` Next Up 与 `CONTEXT` 词条标明 **加固整体完成后、M4 前** 开 `/grill-with-docs`。未开 to-spec / 未实现。
- [x] **M3 停机加固 `/to-tickets` 完成**（2026-07-21）：spec.md 拆成 11 张票（[.scratch/m3-hardening/issues/](.scratch/m3-hardening/issues/)）——**Wave P0** 七张实现票（`01`–`07`）+ **Wave B3** 四张（`08`–`11`）；配套 [to-tickets-notes.md](.scratch/m3-hardening/to-tickets-notes.md) + [implement-plan.md](.scratch/m3-hardening/implement-plan.md)。
- [x] **M3 停机加固 `/to-spec` 完成**（2026-07-21）：[spec.md](.scratch/m3-hardening/spec.md)（`ready-for-agent`）——同一 spec 两 wave：**Wave P0** + **Wave B3**；OOS：P1-1/5/8/9、评审 P2、M4。
- [x] **P1 排期拍板**（2026-07-21）：`/grill-with-docs` 续——**W1**（不升停机门闩）；下一刀 **B3**（P1-2/3/4/6/7）；时序 **Q3**；P1-1/5/8/9 → spec OOS（X1）。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

1. **M3 停机加固 Wave 1**（新 session，按 [implement-plan.md](.scratch/m3-hardening/implement-plan.md) Wave 1 提示词）：票 `06` 创作者契约 v0（阻塞于已落地的 `05`）+ `07` 票 Status 刷新 + 战斗事件契约测（阻塞于已落地的 `03`）。开工前打 `m3-hardening-wave1-start`。Wave 1 全关 = Wave P0 门闩关闭，才能改写「可诚实停机」。
2. 之后 Wave 2/3（spec Wave B3）。
3. **M3 停机加固整体完成（P0+B3）之后、开 M4 之前**：**Pre-M4 引擎房间保真**——新 session `/grill-with-docs`（输入 [.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)），再 `/to-spec` → `/to-tickets` → `/implement`。不并入 hardening；不走 wayfinder。细节见 [session-notes-2026-07-21.md](.scratch/pre-m4-engine-room-fidelity/session-notes-2026-07-21.md)。
4. 上述 Pre-M4 effort 关完（或 grill 明确缩 scope / 延期）后再决定是否开 M4——对照 [06](.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md) / [07](.scratch/mvp-scope/issues/07-governance-cost-tracking.md)。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [CONTEXT.md](CONTEXT.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [.scratch/progress-archive.md](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
- Post-MVP（不进 M0–M4）：[.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
- Pre-M4（加固后、M4 前）：[.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)。
