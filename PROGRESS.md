# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与"架构不变量"。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-21：Nature B1–B5 + A2 一键验证矩阵落地（`just verify-nature`）；M1 扩展验证收口，可进 M2 `/to-tickets`。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1 物品 + NPC + Nature 验证矩阵已落地**；M2 spec 已产出，待 `/to-tickets`。
- **工作分支**：`master`。
- **engine/**：测试绿。`just verify-items` / `just verify-npc` / `just verify-nature`。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **M1 Nature 验证矩阵（B1–B5 + A2）**（2026-07-21）：[`just verify-nature`](justfile)；[verify-nature-cli.md](.scratch/m1-core-engine-skeleton/verify-nature-cli.md)；默认场景户外/室内 + `nature:` 夹具已够；B1–B5 已完备，M2+ 不当缺口。
- [x] **M1 NPC 验证矩阵（D1–D5）**（2026-07-20）：默认场景补闲人/夜猫/巡逻兵×2 夹具；[`just verify-npc`](justfile)；[verify-npc-cli.md](.scratch/m1-core-engine-skeleton/verify-npc-cli.md)；D1–D5 已完备，可选/M2 不当缺口。
- [x] **`verify/m1-items` 物品命令补齐 + 场景夹具 + 一键矩阵**（2026-07-20）：`get`/`take`；`drop <数量>`；`get all`/`drop all`；`no_take`→**`no_get`**（事件 `on_get`）；`i` 显示堆叠 `×N`；[`just verify-items`](justfile)；手测说明 [.scratch/m1-core-engine-skeleton/verify-items-cli.md](.scratch/m1-core-engine-skeleton/verify-items-cli.md)。
- [x] **`/to-spec` 产出 M2 spec**（2026-07-20）：[.scratch/m2-mvp-scene-playable/spec.md](.scratch/m2-mvp-scene-playable/spec.md)（`ready-for-agent`）。**暂缓** `/to-tickets`，待 M1 手测验证收口。
- [x] **`feat/m1-bcd-repass` → `master`**（2026-07-20）：fast-forward；旧目标分支与 m1 工作分支本地+远程已删。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

1. **M2 `/to-tickets`**（M1 扩展验证已收口：items / npc / nature）。
2. 按 CLAUDE.md 待办：M3 前核对 [03-ugc-dsl-design-inheritance](.scratch/mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 细化后编辑器系统归类是否仍准确。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
