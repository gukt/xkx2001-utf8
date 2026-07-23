# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与架构不变量。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-23：Polishing S5 `verify_polishing` 矩阵落地；effort 收口齐。Next Up → M4 评估。**不自动开 M4**。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1/M2/M3 里程碑可宣布完成**；**M3 停机加固整体完成**。**暂缓 M4**。Pre-M4 三批已关。**Polishing 已关闭**（Wave 1–9 + S5 verify；票 `01`–`13` resolved）。
- **工作分支**：`feat/polishing`（可合入 master；勿在 master 上直接续作 polishing）。
- **engine/**：测试绿（975）；`just verify-polishing` 13/13。
- **拍板依据**：[CONTEXT.md](CONTEXT.md)；[ADR-0007](docs/adr/0007-effect-lifecycle-deferred-from-m2-m3-stop.md)～[0013](docs/adr/0013-local-nature-room-sticker.md)（Accepted）；Polishing 规格见 [.scratch/polishing/spec.md](.scratch/polishing/spec.md)。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **Polishing S5：`verify_polishing` 端到端矩阵**（2026-07-23）：`scripts/verify_polishing.py` + `test_verify_polishing_matrix.py` + `just verify-polishing`；票 `01`–`13` 各 ≥1 场景步骤；13/13 通过。正式门禁仍以各票单测为准。975 绿。**不自动开 M4**。
- [x] **Polishing Wave 9 落地：局部天气继承实现 + effort 关闭**（2026-07-23）：票 `13`；`LocalNature`/`local_nature`；合成查询；ADR-0013 `accepted`；fixed point `polishing-wave9-start`；974 绿。
- [x] **Polishing Wave 8 落地：局部天气继承 ADR**（2026-07-23）：票 `12`；ADR-0013（当时 `proposed`）；fixed point `polishing-wave8-start`。
- [x] **Polishing Wave 7 落地：多文件路径引用 `includes`**（2026-07-23）：票 `11`；fixed point `polishing-wave7-start`；961 绿。
- [x] **Polishing Wave 6 落地：随机 objects 表 + 刷怪条件 hooks params**（2026-07-23）：票 `09`/`10`；fixed point `polishing-wave6-start`；948 绿。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

### 1. M4 评估（独立拍板）

独立决定是否开 M4（商业化数据模型）。**不因 Polishing 关闭而自动滑入 M4**。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md) + [CONTEXT.md](CONTEXT.md) + 当前 effort 底稿。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [.scratch/progress-archive.md](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
- Post-MVP（不进 M0–M4）：[.scratch/mvp-scope/post-mvp-backlog.md](.scratch/mvp-scope/post-mvp-backlog.md)。
- Pre-M4（加固后、M4 前）：[.scratch/pre-m4-channels-spawn-quest/](.scratch/pre-m4-channels-spawn-quest/)（**已关**）→ [.scratch/pre-m4-engine-room-fidelity/](.scratch/pre-m4-engine-room-fidelity/)（**已关**）→ [.scratch/pre-m4-room-hooks-xingxiu/](.scratch/pre-m4-room-hooks-xingxiu/)（**已关**）。
- Polishing：[.scratch/polishing/](.scratch/polishing/)（**已关**；工作分支 `feat/polishing`）。
