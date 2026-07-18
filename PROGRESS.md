# 项目进度

> 本文件是跨 session 的"活的状态"——每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> **2026-07-17 项目重设，2026-07-18 新目标定稿+CLAUDE.md 重写完成**：原目标与取舍战略已放弃，新目标已用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 9/10 票决策（[02](.scratch/mvp-scope/issues/02-engine-boundary-combat-effects.md) 用户主动标"暂定"未拍板，不阻塞其他票）并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与"架构不变量"章节。重设前的完整进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)（含更早的按阶段归档 [docs/archive/progress-archive/](docs/archive/progress-archive/)），仅作背景参考。

**最后更新**：2026-07-18（M1 第 0 步：`engine/` 工作区绿场重置完成）

## 当前状态速览

- **阶段**：M0 完成；M1 spec 已产出；**M1 第 0 步（工作区重置）已完成**。下一步：`/to-tickets` 拆功能票再 `/implement`。
- **分支**：见当前 git 分支。
- **engine/ 现状**：绿场。旧实现冻结于 tag `archive/engine-pre-m1-rewrite`（[ADR-0002](docs/adr/0002-engine-workspace-greenfield-reset.md)）。工作区仅有最小包 + 冒烟测试 + `prototypes/ecs_ugc`。

## Done

- **M1 第 0 步：engine 工作区绿场重置**（[.scratch/m1-core-engine-skeleton/issues/00-engine-workspace-reset.md](.scratch/m1-core-engine-skeleton/issues/00-engine-workspace-reset.md)）：tag `archive/engine-pre-m1-rewrite`；移除旧 `src/tests/scenes/tools`；路径仍为 `engine/`；[ADR-0002](docs/adr/0002-engine-workspace-greenfield-reset.md)；CLAUDE/justfile/M1 spec 已同步。
- **`/to-spec` 产出 M1 spec**：[.scratch/m1-core-engine-skeleton/spec.md](.scratch/m1-core-engine-skeleton/spec.md)（Status: ready-for-agent）。范围=移动/查看/拾取丢弃/门与动态出口/存档骨架；CLI 真终端；ECS 组件按复用性拆分；解析/执行两阶段 + 别名。
- **`/wayfinder` mvp-scope 地图 9/10 票解决**（[.scratch/mvp-scope/map.md](.scratch/mvp-scope/map.md)，[02](.scratch/mvp-scope/issues/02-engine-boundary-combat-effects.md) 暂定挂起）。结论摘要见 [CLAUDE.md](CLAUDE.md)「架构不变量」；[ADR-0001](docs/adr/0001-no-lpc-behavior-equivalence-verification.md)。
- **重写 [CLAUDE.md](CLAUDE.md)** 项目一句话 + 架构不变量 8 条。

## In Progress

- **`/prototype` ECS×UGC 手感**（可选收尾）：`just proto-ecs-ugc`（`engine/prototypes/ecs_ugc/`）。结论已部分吸收进 M1 spec；若不再跑可标完成。

## Blocked

**当前无阻塞项。**

## Next Up

1. 新 session：读本文件 + [CLAUDE.md](CLAUDE.md) + [M1 spec](.scratch/m1-core-engine-skeleton/spec.md)。确认 `engine/` 已是绿场（不要去「恢复」旧代码）。
2. 对 M1 spec 跑 `/to-tickets`，写入 `.scratch/m1-core-engine-skeleton/issues/`（从 01 起；00 已 resolved），再逐票 `/implement`。
3. [02-engine-boundary-combat-effects](.scratch/mvp-scope/issues/02-engine-boundary-combat-effects.md) 建议在 M2 `/to-spec` 前用 `/prototype` 或 `/design-an-interface` 补上——不阻塞 M1。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 单条 ≤2 行，细节进 ADR（[docs/adr/](docs/adr/)，重设后从头编号）。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
