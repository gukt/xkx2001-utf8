# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与"架构不变量"。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-21：M2 Wave 0 四票实现完成（`01`–`04`），全量 430 测试 + `just verify-*` 绿；待 `/code-review`（fixed point `m2-wave0-start`）。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1 扩展验证矩阵已落地**；**M2 Wave 0 实现完成**，待 code-review → fix → Wave 1。
- **工作分支**：`feat/m2-mvp-scene-playable`（fixed point tag：`m2-wave0-start`）。
- **engine/**：测试绿（430 passed）。`just verify-items` / `just verify-npc` / `just verify-nature`。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **M2 Wave 0 落地：注册表 prefactor + 战斗算法 + 技能数据 + spawner 修复**（2026-07-21）：四票各一 commit（`d5a951aa`/`4735c5f0`/`a028d2fe`/`bef2ae40`）。`01` `ROOM_CAPABILITIES`/`NPC_CAPABILITIES`；`02` `combat.resolve_attack`+`PowerModel`；`03` `skills:`/`SKILLS`/`SkillBehavior`；`04` `world.spawners`+全灭重生。未跑 `/code-review`（按 implement-plan 留给下一环节）。
- [x] **M2 `/to-tickets` 拆票 + 实现计划**（2026-07-21）：分支 `feat/m2-mvp-scene-playable`；26 张票 [.scratch/m2-mvp-scene-playable/issues/](.scratch/m2-mvp-scene-playable/issues/)；[implement-plan.md](.scratch/m2-mvp-scene-playable/implement-plan.md)。
- [x] **M1 Nature 验证矩阵（B1–B5 + A2）**（2026-07-21）：[`just verify-nature`](justfile)；[verify-nature-cli.md](.scratch/m1-core-engine-skeleton/verify-nature-cli.md)。
- [x] **M1 NPC 验证矩阵（D1–D5）**（2026-07-20）：[`just verify-npc`](justfile)；[verify-npc-cli.md](.scratch/m1-core-engine-skeleton/verify-npc-cli.md)。
- [x] **`verify/m1-items` 物品命令补齐 + 场景夹具 + 一键矩阵**（2026-07-20）：[`just verify-items`](justfile)；[verify-items-cli.md](.scratch/m1-core-engine-skeleton/verify-items-cli.md)。

## In Progress

当前无进行中项——下一环节是 Wave 0 `/code-review`。

## Blocked

**当前无阻塞项。**

## Next Up

1. **M2 Wave 0 `/code-review`**：fixed point=`m2-wave0-start`，spec=`.scratch/m2-mvp-scene-playable/spec.md` + issues `01`–`04` → fix → 再进 Wave 1。
2. **M2 Wave 1 `/implement`**：票 `05`–`09`（角色成长 / 死亡状态机 / 货币商店 / 门派框架 / 渡船），见 [implement-plan.md](.scratch/m2-mvp-scene-playable/implement-plan.md)。
3. 按 CLAUDE.md 待办：M3 前核对 [03-ugc-dsl-design-inheritance](.scratch/mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 细化后编辑器系统归类是否仍准确。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
