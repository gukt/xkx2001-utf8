# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-21：M3 停机加固 Wave 1 落地 + code-review fix（670 绿）；**Wave P0 门闩关闭 → 可诚实停机**。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2/M3 里程碑可宣布完成**；**M3 停机加固 Wave P0（票 `01`–`07`）已关闭 → 可诚实停机**。同 effort 仍有 **Wave B3**（票 `08`–`11`，选定 P1，非门闩）待做；**暂缓 M4**。加固整体（P0+B3）完成后、开 M4 **之前**插入 **Pre-M4 引擎房间保真**（已记笔记，待 grill）。
- **工作分支**：`feat/m3-ugc-loop-creation-surface`（加固 Wave 1 fixed point：`m3-hardening-wave1-start`）。
- **engine/**：测试绿（670）；创作者契约见 [docs/creator-contract-v0.md](docs/creator-contract-v0.md)；spec 见 [m3-hardening/spec.md](.scratch/m3-hardening/spec.md)，票见 [m3-hardening/issues/](.scratch/m3-hardening/issues/)，执行计划见 [implement-plan.md](.scratch/m3-hardening/implement-plan.md)。
- **拍板依据**：[评审 Final](.scratch/m3-engine-architecture-review/final/m3-engine-architecture-review-report.md)；[ADR-0007](docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)～[0009](docs/adr/0009-single-process-single-world.md)；[CONTEXT.md](CONTEXT.md)。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **M3 停机加固 Wave 1 落地：P0 收尾 → 可诚实停机**（2026-07-21）：票 `06` 创作者契约 v0（[docs/creator-contract-v0.md](docs/creator-contract-v0.md)）+ `07` M2 16–20 Status→resolved + 战斗事件契约测；fixed point `m3-hardening-wave1-start`。Review fix：伤害=气血差、死亡经 tick 清交战、恢复 scene_loader「不 import commands」。**Wave P0（`01`–`07`）全关**。670 绿。
- [x] **M3 停机加固 Wave 0 落地：P0 五张独立实现票**（2026-07-21）：票 `01` 昏迷 tick 苏醒 / `02` 少林山门去持刃 / `03` combat 消灭全局态 / `04` `wire_runtime` / `05` `--validate`/`--strict`；fixed point `m3-hardening-wave0-start`。Review fix：CLI 严格校验测试按 `When*` 拆分复合断言；`DEFAULT_UNCONSCIOUS_RECOVERY_TICKS` + `_world_death_policy`。664 绿。
- [x] **Pre-M4 引擎房间保真：session 笔记落盘并排队**（2026-07-21）：LPC vs 引擎缺口对照写入 [.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)（[README](.scratch/pre-m4-engine-room-fidelity/README.md) + [session-notes](.scratch/pre-m4-engine-room-fidelity/session-notes-2026-07-21.md)）；`PROGRESS` Next Up 与 `CONTEXT` 词条标明 **加固整体完成后、M4 前** 开 `/grill-with-docs`。未开 to-spec / 未实现。
- [x] **M3 停机加固 `/to-tickets` 完成**（2026-07-21）：spec.md 拆成 11 张票（[.scratch/m3-hardening/issues/](.scratch/m3-hardening/issues/)）——**Wave P0** 七张实现票（`01`–`07`）+ **Wave B3** 四张（`08`–`11`）；配套 [to-tickets-notes.md](.scratch/m3-hardening/to-tickets-notes.md) + [implement-plan.md](.scratch/m3-hardening/implement-plan.md)。
- [x] **M3 停机加固 `/to-spec` 完成**（2026-07-21）：[spec.md](.scratch/m3-hardening/spec.md)（`ready-for-agent`）——同一 spec 两 wave：**Wave P0** + **Wave B3**；OOS：P1-1/5/8/9、评审 P2、M4。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

1. **M3 停机加固 Wave 2**（新 session，按 [implement-plan.md](.scratch/m3-hardening/implement-plan.md) Wave 2 提示词）：票 `08` messaging 抽取 / `10` 三条交叉测 / `11` GAP 台账。开工前打 `m3-hardening-wave2-start`。
2. 之后 Wave 3（票 `09` 双轨范本文档，阻塞于已落地的 `06`）。
3. **M3 停机加固整体完成（P0+B3）之后、开 M4 之前**：**Pre-M4 引擎房间保真**——新 session `/grill-with-docs`（输入 [.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)），再 `/to-spec` → `/to-tickets` → `/implement`。不并入 hardening；不走 wayfinder。细节见 [session-notes-2026-07-21.md](.scratch/pre-m4-engine-room-fidelity/session-notes-2026-07-21.md)。
4. 上述 Pre-M4 effort 关完（或 grill 明确缩 scope / 延期）后再决定是否开 M4——对照 [06](.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md) / [07](.scratch/mvp-scope/issues/07-governance-cost-tracking.md)。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [CONTEXT.md](CONTEXT.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [.scratch/progress-archive.md](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
- Post-MVP（不进 M0–M4）：[.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
- Pre-M4（加固后、M4 前）：[.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)。
