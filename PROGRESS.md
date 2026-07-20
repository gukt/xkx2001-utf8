# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与"架构不变量"。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-20：`/to-spec` 产出 M2 spec（[.scratch/m2-mvp-scene-playable/spec.md](.scratch/m2-mvp-scene-playable/spec.md)，`ready-for-agent`）。下一步：M2 `/to-tickets`。

## 当前状态速览

- **阶段**：M0 完成；mvp-scope 10/10；**M1 扩展（B/C/D + smell 30–35）已在 `master`**；**M2 spec 已产出，待 `/to-tickets`**。
- **工作分支**：`master`。
- **engine/**：402 测试绿。`lookup.py` / `capabilities.py` / `errors.py` / `world.entities_in_room`。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **`/to-spec` 产出 M2 spec**（2026-07-20）：[.scratch/m2-mvp-scene-playable/spec.md](.scratch/m2-mvp-scene-playable/spec.md)（`Status: ready-for-agent`）。覆盖 [10 号票](.scratch/mvp-scope/issues/10-mvp-scenes-selection.md) 六类场景（华山村/扬州/少林/野外/官道/渡口）+ [08 号票](.scratch/mvp-scope/issues/08-subsystem-classification-research.md) 对应 12 个 MVP 必做子系统，按 [ADR-0004](docs/adr/0004-combat-effects-boundary-engine.md) 接缝手法分 A~H 八块（战斗地基/角色成长/死亡轮回/金钱/门派+少林/坐骑交通/NPC 主动攻击+Spawn 修复/六场景内容）。顺带设计了 `ai.py` `_spawn_scan` 坑（模板全灭后扫描失效）的修复方案（块 C2：从聚合存活实例改为独立 `world.spawners` 模板注册表）。规模远大于 M1，spec 内建议 `/to-tickets` 按块分批拆票分批验收，配合 07 号票止损线。
- [x] **`feat/m1-bcd-repass` → `master`**（2026-07-20）：fast-forward；旧目标分支与 m1 工作分支本地+远程已删。
- [x] **30–35 code-review 跟进**（`d1257ad3`）：去 lookup Middle Man 薄壳；`SceneLoadError` → `errors.py`；commands 不再空再导出 transfer 符号。
- [x] **票 30–35 resolved**（2026-07-20）：lookup / capabilities / transfer↔commands+veto / entities_in_room / ask·say 文案。
- [x] **票 13–29 全 resolved**（2026-07-20）：re-pass + 批量 review-fix 认证。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

1. **M2 `/to-tickets`**：把 [M2 spec](.scratch/m2-mvp-scene-playable/spec.md) 按块 A~H 拆票（建议分批拆分批验收，spec 「Further Notes」已给实现顺序建议：A 战斗 -> B 角色成长 -> C 死亡 -> D 金钱 -> E/F 门派+坐骑 -> G NPC 主动攻击 -> H 场景内容）。
2. 按 CLAUDE.md 待办：M3 前核对 [03-ugc-dsl-design-inheritance](.scratch/mvp-scope/issues/03-ugc-dsl-design-inheritance.md) 细化后编辑器系统归类是否仍准确。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
