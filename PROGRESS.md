# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与"架构不变量"。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-21：M2 Wave 4 `/implement` + `/code-review` fix 完成；下一环节 Wave 5。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1 扩展验证矩阵已落地**；**M2 Wave 0–4 实现 + code-review fix 完成**，待 Wave 5。
- **工作分支**：`feat/m2-mvp-scene-playable`（Wave 4 fixed point tag：`m2-wave4-start`）。
- **engine/**：测试绿（551 passed）。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **M2 Wave 4 `/implement` + `/code-review` fix**（2026-07-21）：fixed point `m2-wave4-start`。票 `21`–`25`：华山村 / 扬州枢纽+城门 / 扬州商业+马厩 / 少林寺 / 野外·官道·渡口，累加 `m2_mvp_scene.yaml`。Review fix：他派门禁测试、向导去向文案、渡船缺船专用提示（解析候选 + `go`）。551 测试绿；`just verify-*` 全绿。
- [x] **M2 Wave 3 `/implement` + `/code-review` fix**（2026-07-21）：fixed point `m2-wave3-start`。票 `15`–`20`：Terrain/骑乘、SkillBehavior 钩子、DeathPolicy、NPC loot/重生、aggro、同名消歧。Review fix：无 loot 仍给击杀经验、`post_action` 不改本回合结果、物品掉落断言。521 测试绿。
- [x] **M2 Wave 2 `/code-review` fix**（2026-07-21）：fixed point `m2-wave2-start`。EntryGuard 坏条件 fail-closed；`learn` 校验 `level_req`；And 拒绝文案落到子条件。494 测试绿。
- [x] **M2 Wave 2 落地：坐骑 / 门槏 / 战斗接线 / practice / learn**（2026-07-21）：五票各一 commit。`10`–`14` resolved。fixed point `m2-wave2-start`。
- [x] **M2 Wave 1 `/code-review` fix**（2026-07-21）：fixed point `m2-wave1-start`。修复：`status` 不展示银两；实体 `skills` 引用始终校验全局 `SKILLS`；`Unconscious`/`Dead` codec 走 `NPC_CAPABILITIES`。462 测试绿。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

1. **M2 Wave 5 `/implement`**：票 `26`（六分区互联 + 端到端剧本）；开工前打 tag `m2-wave5-start`，见 [implement-plan.md](.scratch/m2-mvp-scene-playable/implement-plan.md)。
2. 按 CLAUDE.md 待办：M3 前核对 [03-ugc-dsl-design-inheritance](.scratch/mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 细化后编辑器系统归类是否仍准确。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
