# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与"架构不变量"。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-20：13–35 **全 23 张 resolved**。smell ticket 30-35 已逐个 `/implement` + `just gate` 全绿（402）。下一步：跑 `/code-review` 双轴 -> 合 `feat/m1-bcd-repass` 回 `master` -> 开 M2 `/to-spec`。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；M1 扩展票 13–35 **全 resolved**（代码在 `feat/m1-bcd-repass`，待 `/code-review` 后合回 `master`）。
- **工作分支**：`feat/m1-bcd-repass`（相对 `master` 含 review-fix 加固 + smell ticket 30-35）。
- **engine/**：402 测试绿。新增/加固：`lookup.py`、`capabilities.py`、`world.entities_in_room`。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **票 13–29 全 resolved**（2026-07-20）：13/14/16/18/27/28 完整 `/implement` re-pass；15/17/19-26/29 经批量 review-fix 认证标 resolved（用户决策，未走独立 `/implement`，各 ticket Comments 注明）。
- [x] **code-review 跟进（13/14/16/18/27/28 批）**（2026-07-20）：Standards 测拆分 + Spec restore 场景路径 + ask 共享谓词 + nature YAML 读盘收回 `scene_loader`；父 spec D3 收窄写进 [spec-extension](.scratch/m1-core-engine-skeleton/spec-extension.md) 范围修订。
- [x] **票 13/14/16/18/27/28 re-pass resolved**：时辰循环、谓词、广播+PlayerSession、物品能力组件、ask、say。
- [x] **13–29 三批 code-review + fix 闭环**（Nature `e687d43f` / 物品 `79b831ef`+`cbfe8084` / NPC `bab2f44f` + #10 StrEnum `3c84e151`）：18 真修 + 6 误报，398 绿。
- [x] **清空 13–29 Status**（commit `5b206224`）准备逐票 re-pass。
- [x] **票 30–35 resolved**（2026-07-20）：30 lookup 去重 / 31 capabilities 注册表 / 32+33 transfer↔commands 拆模块 + veto 去重 / 34 entities_in_room / 35 ask/say 文案统一。逐票 `/implement` + `just gate` 402 绿。

## In Progress

当前无进行中项（本 session 已 handoff）。

## Blocked

**当前无阻塞项。**

## Next Up

1. **跑 `/code-review` 双轴**（Standards + Spec）review 本分支全部变更；按 review 意见 fix 后合 `feat/m1-bcd-repass` 回 `master`。
2. **M2 `/to-spec`**：开 M2 场景端到端可玩规划。NPC `_spawn_scan` meta 挂载点 M2 复核（已写注释）。
3. 按 CLAUDE.md 待办：M3 前核对 [03-ugc-dsl-design-inheritance](.scratch/mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 细化后编辑器系统归类是否仍准确。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
