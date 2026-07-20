# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与"架构不变量"。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-20：M1 扩展 B/C/D（13–29 十七票）全部落地；分支 `feat/m1-extension-bcd`；`docs/define-new-target` 已删；364 测试，`just gate` 全绿。M1 扩展四块（A+B+C+D）齐，下一步 M2 `/to-spec`。

## 当前状态速览

- **阶段**：M0 完成；M1 01~29 全 resolved（骨架 01–06 + 扩展 A 07–12 + B Nature 13–17 + C 物品 18–24 + D NPC 25–29）；mvp-scope 10/10 票全解决。**M1 扩展已合入 `master`**。下一步：M2（一个 MVP 场景端到端可玩）`/to-spec`。
- **engine/ 现状**：`src/mud_engine/` 含 `world`/`components`/`commands`/`conditions`/`nature`/`transfer`/`ai`/`parsing`/`intent`/`matching`/`scenes`/`scene_loader`/`save`/`tick`/`events`/`cli`/`__main__`。场景 `engine/data/m1_default_scene.yaml`（户外庭院 + nature 相位 + 石像守卫 inquiry）。闭环：移动/查看/拾取丢弃/put/容器容量重量/堆叠/no_take·no_drop、门与锁、Nature 时辰天气与户外 look/广播、ask/say/Chatter、存档与崩溃恢复、事件总线与钩子。364 测试，`just gate` 全绿。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **M1 扩展 B/C/D 十七票落地**（[13–29](.scratch/m1-core-engine-skeleton/issues/)，resolved；2026-07-20）：分支卫生（推 master、删 `docs/define-new-target`、开 `feat/m1-extension-bcd`）+ `/to-tickets` 拆 13–29 + 并行落地。**B Nature**：`nature.py`（`NatureState`/`DayPhase`/`Weather`/`attach_nature`/`on_nature_change`）、户外 `Description.outdoors`、look 时辰×天气、`pending_messages` 广播、可注入时钟/RNG；`test_nature.py`（26）。**C 物品**：`Stackable`/`Valuable`/`Equippable`/`Consumable`/`ItemFlags`/`Weight`、`transfer.py` 统一原语、堆叠合并拆分、put/take from、look 物品增强、容量重量上限；`test_items_extension.py`（18）。**D NPC**：`ai.py`（`AIController`/`Behaviors`/Chatter/Spawn 扫描）、`Inquiry` + `ask`、`say` + `on_hear_say`；`test_npc_extension.py`（19）。364 测试，`just gate` 全绿。
- [x] **M1 扩展 `/to-tickets` 拆 B/C/D**（2026-07-20）：按 [spec-extension.md](.scratch/m1-core-engine-skeleton/spec-extension.md) 拆 [13–29 十七票](.scratch/m1-core-engine-skeleton/issues/)（B 13–17 / C 18–24 / D 25–29），依赖边写清；跳过重跑 to-spec（扩展 spec 已 ready-for-agent）。
- [x] **M1 12 号票：组件字段三态标注**（[12](.scratch/m1-core-engine-skeleton/issues/12-component-field-tri-state.md)，resolved）：`transient_field()` + save chokepoint `_strip_transient`；`test_transient_fields.py`（4）。
- [x] **M1 11 号票：YAML 未识别段透传**（[11](.scratch/m1-core-engine-skeleton/issues/11-yaml-unknown-section-passthrough.md)，resolved）：顶层/实体级未识别段透传不丢、不进存档。
- [x] **M1 09 号票：领域事件点（移动/物品/门）**（[09](.scratch/m1-core-engine-skeleton/issues/09-domain-event-points.md)，resolved）：移动/物品/门领域事件空挂；`TransferContext` 对齐块 C transfer。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

1. **合回 master**：在 `feat/m1-extension-bcd` 上确认干净后 merge 进 `master` 并推送。
2. **M2 `/to-spec`**：一个 MVP 场景端到端可玩（新手村/扬州子集/少林/野外/官道/渡口/坐骑，见 CLAUDE.md 架构不变量第 7 条）；战斗/效果边界已定 [ADR-0004](docs/adr/0004-combat-effects-boundary-engine.md)。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
