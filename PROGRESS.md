# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与"架构不变量"。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-20：13–29 **三批 code-review + fix 闭环**（Nature `e687d43f` / 物品 `79b831ef`+`cbfe8084` / NPC `bab2f44f` + #10 StrEnum `3c84e151`）。398 测试绿。6 条标记 smell 建 ticket 30-35 待下个 session 接力；BCD 逐票 re-pass 仍待 15/17/19-26/29。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；M1 扩展代码已在 `master`，但正对票 13–29 做纪律化 re-pass（清空 Status → 逐票 `/implement` → `/code-review`）。
- **工作分支**：`feat/m1-bcd-repass`（相对 `master` 含 re-pass + review-fix）。
- **engine/**：393 测试绿。新增/加固：`PlayerSession`、`npc_query.is_askable_npc`、`world.scene_path` + `world_meta.json`、`read_nature_config`。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **code-review 跟进（13/14/16/18/27/28 批）**（2026-07-20）：Standards 测拆分 + Spec restore 场景路径 + ask 共享谓词 + nature YAML 读盘收回 `scene_loader`；父 spec D3 收窄写进 [spec-extension](.scratch/m1-core-engine-skeleton/spec-extension.md) 范围修订。
- [x] **票 13/14/16/18/27/28 re-pass resolved**：时辰循环、谓词、广播+PlayerSession、物品能力组件、ask、say。
- [x] **清空 13–29 Status**（commit `5b206224`）准备逐票 re-pass。
- [x] **M1 扩展 B/C/D 首轮落地**（已合 `master`，见归档）：首轮并行冲刺，后改纪律化 re-pass。
- [x] **M1 扩展 `/to-tickets` 拆 B/C/D**（票 13–29）。

## In Progress

当前无进行中项（本 session 已 handoff）。

## Blocked

**当前无阻塞项。**

## Next Up

1. **接力 6 个 smell ticket 30-35**（下个 session 逐个 `/implement`）：#6 查找去重 / #7 能力组件注册 / #8+#9 transfer↔commands 拆模块（关联）/ NPC #7 `entities_in_room`（含 import 循环处理）/ NPC #8 文案。#10 StrEnum 本 session 已重构（commit 3c84e151）。NPC `_spawn_scan` meta 挂载点 M2 复核（已写注释）。BCD re-pass 待票 15/17/19-26/29 仍待走 `/implement` + `/code-review` 双轴 + 勾 AC。
2. **建议下一批**：并行 **15**（户外 look）+ **19**（transfer）+ **25**（Behavior/AIController）；或先收尾 Nature **15 → 17**。
3. 每票：`claimed` → `/implement`（含 TDD seam）→ **正式 `/code-review` 双轴** → 勾 AC / `resolved` → 汇报过目。
4. 全票 re-pass 完：`just gate` → 合回 `master` → 再开 M2 `/to-spec`。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
