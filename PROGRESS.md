# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-21：M3 停机加固 `/to-spec` 完成（[spec.md](.scratch/m3-hardening/spec.md)，同 spec 两 wave P0→B3）；下一步 `/to-tickets`。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2/M3 里程碑可宣布完成**；当前窗口 = **M3 停机加固**——**退出标准仅 P0（S0）**；同 effort 规划 **B3 wave**（选定 P1，非门闩）；**暂缓 M4**。
- **工作分支**：`feat/m3-ugc-loop-creation-surface`（Wave 3 fixed point tag：`m3-wave3-start`）。
- **engine/**：测试绿（649）；加固实现尚未开工——spec 已产出（[m3-hardening/spec.md](.scratch/m3-hardening/spec.md)），下一步 `/to-tickets` 拆票。
- **拍板依据**：[评审 Final](.scratch/m3-engine-architecture-review/final/m3-engine-architecture-review-report.md)；[ADR-0007](docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)～[0009](docs/adr/0009-single-process-single-world.md)；[CONTEXT.md](CONTEXT.md)。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **M3 停机加固 `/to-spec` 完成**（2026-07-21）：[spec.md](.scratch/m3-hardening/spec.md)（`ready-for-agent`）——同一 spec 两 wave：**Wave P0**（停机门闩 S0，评审 P0-1～9 全 9 项）+ **Wave B3**（排期非门闩，P1-2/3/4/6/7）；OOS：P1-1/5/8/9、评审 P2、M4；输入源评审 Final 报告 + 对抗裁决 + ADR-0007～0009 + PROGRESS 拍板摘要，ADR 已落项只引用不重开。下一步 `/to-tickets`。
- [x] **P1 排期拍板**（2026-07-21）：`/grill-with-docs` 续——**W1**（不升停机门闩）；下一刀 **B3**（P1-2/3/4/6/7）：范文 C1、GAP 台账 G1、ADR-0009（R1）、`messaging.py`（M1）、交叉测 T1；时序 **Q3**（同 spec：P0 wave→B3 wave）；P1-1/5/8/9 → spec OOS（X1）。
- [x] **M3 停机加固拍板**（2026-07-21）：`/grill-with-docs`——S0 仅 P0；Effect 延期（ADR-0007）；昏迷 tick 苏醒；少林场景去掉持刃条件；频道/登录单机降级（ADR-0008）；暂缓 M4。
- [x] **M3 UGC 闭环打通一次**（2026-07-21）：Wave 3 票 [05](.scratch/m3-ugc-loop-creation-surface/issues/05-e2e-verification-and-docs.md)——`test_m3_pack_loop.py` + `verify_m3_pack_loop.py` + `just verify-m3`；示例包端到端剧本 / 坏包 `--validate` / CLI 存档恢复；[spec](.scratch/m3-ugc-loop-creation-surface/spec.md)。Review fix：拆复合断言、逐步串跑断言、`test_verify_m3_matrix`、lint 全绿。649 绿。
- [x] **M3 Wave 2 `/implement` + `/code-review` fix**（2026-07-21）：票 `03` CLI `--pack`/`--validate` + 票 `04` 废弃探测站示例包；fixed point `m3-wave2-start`。Review fix：缺目录错误前缀分层、默认存档目录断言、测试拆复合断言。621 绿。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

1. **M3 停机加固** `/to-spec`（已完成，见 [spec.md](.scratch/m3-hardening/spec.md)）→ **`/to-tickets`（下一步）** → `/implement`（**同一 spec，两 wave**）：
   - **Wave P0（停机门闩 / S0）**
     - P0-1：ADR-0007 已落（不实现持续 Effect）
     - P0-2：tick 自动苏醒（实现）
     - P0-3：官方场景 YAML 去掉少林持刃条件（不做 wield）
     - P0-4～P0-8：消灭战斗回合全局缓冲；`wire_runtime`；创作者契约 v0；`--validate` 未消费字段 warn；刷票 Status + 战斗事件最小契约测
     - P0-9：ADR-0008 已落
   - **Wave B3（排期，非门闩；P0 关完后做）**
     - P1-2：ADR-0009 已落
     - P1-3：抽出 `messaging.py`（`room_say` 搬家）
     - P1-4：官方/示例双轨范本文档（不包化）
     - P1-6：Pack×交战 restore；SkillBehavior×World tick；骑乘×渡船（各至少一条）
     - P1-7：GAP 台账（无橱窗包）
   - **OOS / 后置**：P1-1、P1-5、P1-8、P1-9；评审 P2；M4
2. Wave P0 全关后：更新本文件「可诚实停机」；B3 可继续；再决定是否开 M4——对照 [06](.scratch/mvp-scope/issues/06-scaling-commercialization-support-points.md) / [07](.scratch/mvp-scope/issues/07-governance-cost-tracking.md)。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [CONTEXT.md](CONTEXT.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [.scratch/progress-archive.md](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
- Post-MVP（不进 M0–M4）：[.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
