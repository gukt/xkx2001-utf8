# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与"架构不变量"。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-20：`feat/m1-bcd-repass` 已 fast-forward 合入 `master`（含 13–35 + code-review 跟进）。下一步：M2 `/to-spec`。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1 扩展（B/C/D + smell 30–35）已在 `master`**。
- **工作分支**：`master`。
- **engine/**：402 测试绿。`lookup.py` / `capabilities.py` / `errors.py` / `world.entities_in_room`。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **`feat/m1-bcd-repass` → `master`**（2026-07-20）：fast-forward；旧目标分支与 m1 工作分支本地+远程已删。
- [x] **30–35 code-review 跟进**（`d1257ad3`）：去 lookup Middle Man 薄壳；`SceneLoadError` → `errors.py`；commands 不再空再导出 transfer 符号。
- [x] **票 30–35 resolved**（2026-07-20）：lookup / capabilities / transfer↔commands+veto / entities_in_room / ask·say 文案。
- [x] **票 13–29 全 resolved**（2026-07-20）：re-pass + 批量 review-fix 认证。
- [x] **13–29 三批 code-review + fix 闭环**（Nature / 物品 / NPC + #10 StrEnum）。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

1. **M2 `/to-spec`**：开 M2 场景端到端可玩规划。NPC `_spawn_scan` meta 挂载点 M2 复核（已写注释）。
2. 按 CLAUDE.md 待办：M3 前核对 [03-ugc-dsl-design-inheritance](.scratch/mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 细化后编辑器系统归类是否仍准确。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
