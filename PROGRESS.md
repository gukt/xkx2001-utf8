# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-21：M3 停机加固 Wave 0 `/implement` 完成（票 `01`–`05`，5 commit；fixed point `m3-hardening-wave0-start`；657 绿）；待 `/code-review`。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2/M3 里程碑可宣布完成**；当前窗口 = **M3 停机加固**——**退出标准仅 P0（S0）**；同 effort 规划 **B3 wave**（选定 P1，非门闩）；**暂缓 M4**。
- **工作分支**：`feat/m3-ugc-loop-creation-surface`（加固 Wave 0 fixed point：`m3-hardening-wave0-start`）。
- **engine/**：测试绿（657）；Wave 0 五张票已落地并各自 commit，尚未跑 `/code-review`——spec 见 [m3-hardening/spec.md](.scratch/m3-hardening/spec.md)，票见 [m3-hardening/issues/](.scratch/m3-hardening/issues/)，执行计划见 [implement-plan.md](.scratch/m3-hardening/implement-plan.md)。
- **拍板依据**：[评审 Final](.scratch/m3-engine-architecture-review/final/m3-engine-architecture-review-report.md)；[ADR-0007](docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)～[0009](docs/adr/0009-single-process-single-world.md)；[CONTEXT.md](CONTEXT.md)。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **M3 停机加固 `/to-tickets` 完成**（2026-07-21）：spec.md 拆成 11 张票（[.scratch/m3-hardening/issues/](.scratch/m3-hardening/issues/)）——**Wave P0** 七张实现票（`01` 昏迷苏醒 / `02` 持刃门禁 / `03` combat.py 消灭全局态 / `04` `wire_runtime` / `05` `--validate`/`--strict` / `06` 创作者契约 v0 / `07` 票状态刷新 + 战斗事件契约测）+ **Wave B3** 四张（`08` `messaging.py` / `09` 双轨范本文档 / `10` 三条交叉测试 / `11` GAP 台账）；P0-1/P0-9/B3-1 因已由 ADR 落盘不开票。阻塞关系：`06` 阻塞于 `05`；`07`/`10` 阻塞于 `03`；`09` 阻塞于 `06`；其余（`01`/`02`/`03`/`04`/`05`/`08`/`11`）可立即开始。配套产出拆票分析笔记 [to-tickets-notes.md](.scratch/m3-hardening/to-tickets-notes.md)（拆分原则 + 关键歧义决策 + spec 决策块映射）与执行计划 [implement-plan.md](.scratch/m3-hardening/implement-plan.md)（4 wave：Wave 0/1=spec Wave P0，Wave 2/3=spec Wave B3；`/code-review` 循环 + Wave 提示词模板）。下一步在新 session 按 Wave 0 模板跑 `/implement`。
- [x] **M3 停机加固 `/to-spec` 完成**（2026-07-21）：[spec.md](.scratch/m3-hardening/spec.md)（`ready-for-agent`）——同一 spec 两 wave：**Wave P0**（停机门闩 S0，评审 P0-1～9 全 9 项）+ **Wave B3**（排期非门闩，P1-2/3/4/6/7）；OOS：P1-1/5/8/9、评审 P2、M4；输入源评审 Final 报告 + 对抗裁决 + ADR-0007～0009 + PROGRESS 拍板摘要，ADR 已落项只引用不重开。下一步 `/to-tickets`。
- [x] **P1 排期拍板**（2026-07-21）：`/grill-with-docs` 续——**W1**（不升停机门闩）；下一刀 **B3**（P1-2/3/4/6/7）：范文 C1、GAP 台账 G1、ADR-0009（R1）、`messaging.py`（M1）、交叉测 T1；时序 **Q3**（同 spec：P0 wave→B3 wave）；P1-1/5/8/9 → spec OOS（X1）。
- [x] **M3 停机加固拍板**（2026-07-21）：`/grill-with-docs`——S0 仅 P0；Effect 延期（ADR-0007）；昏迷 tick 苏醒；少林场景去掉持刃条件；频道/登录单机降级（ADR-0008）；暂缓 M4。
- [x] **M3 UGC 闭环打通一次**（2026-07-21）：Wave 3 票 [05](.scratch/m3-ugc-loop-creation-surface/issues/05-e2e-verification-and-docs.md)——`test_m3_pack_loop.py` + `verify_m3_pack_loop.py` + `just verify-m3`；示例包端到端剧本 / 坏包 `--validate` / CLI 存档恢复；[spec](.scratch/m3-ugc-loop-creation-surface/spec.md)。Review fix：拆复合断言、逐步串跑断言、`test_verify_m3_matrix`、lint 全绿。649 绿。

## In Progress

**M3 停机加固 Wave 0**：票 `01`–`05` 已实现并 commit；fixed point `m3-hardening-wave0-start`；全量 657 绿。**待 `/code-review`**（spec：`.scratch/m3-hardening/spec.md` + Wave 0 五张 issue），修完 fix 后再把 Done 条目写入本文件并开 Wave 1。

## Blocked

**当前无阻塞项。**

## Next Up

1. **`/code-review` Wave 0**（fixed point `m3-hardening-wave0-start`）→ fix → `just test` 绿 → 再开 **Wave 1**（`06` 创作者契约 v0，阻塞于已落地的 `05`；`07` 票 Status 刷新 + 战斗事件契约测，阻塞于已落地的 `03`）。
2. Wave 1 全关后：更新本文件「可诚实停机」；再推进 Wave 2/3（spec Wave B3）。
3. Wave 3 完成后再决定是否开 M4——对照 [06](.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md) / [07](.scratch/mvp-scope/issues/07-governance-cost-tracking.md)。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [CONTEXT.md](CONTEXT.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [.scratch/progress-archive.md](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
- Post-MVP（不进 M0–M4）：[.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
