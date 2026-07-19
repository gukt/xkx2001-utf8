# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与"架构不变量"。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-19：M1 07 号票落地（事件总线 + on_tick 分发，[07](.scratch/m1-core-engine-skeleton/issues/07-event-bus-and-on-tick-dispatch.md) resolved；`EventBus` 挂 `World.events` + `TickLoop.advance` 分发 on_tick，存档走 `save_fn` 等价机制；184 测试全绿）。A 块 frontier 剩 [10](.scratch/m1-core-engine-skeleton/issues/10-condition-expression-evaluator.md)/[11](.scratch/m1-core-engine-skeleton/issues/11-yaml-unknown-section-passthrough.md)/[12](.scratch/m1-core-engine-skeleton/issues/12-component-field-tri-state.md)，[08](.scratch/m1-core-engine-skeleton/issues/08-command-lifecycle-hooks.md)/[09](.scratch/m1-core-engine-skeleton/issues/09-domain-event-points.md) 已解锁；mvp-scope 10/10 票全解决；M1 01~07 全 resolved。综合笔记 [.scratch/m1-core-engine-skeleton/research-m1-extension-items-npc-nature.md](.scratch/m1-core-engine-skeleton/research-m1-extension-items-npc-nature.md)。

## 当前状态速览

- **阶段**：M0 完成；M1 01~07 号票全 resolved（07 事件总线+on_tick 分发）；M1 扩展 A 块 [07-12 六票](.scratch/m1-core-engine-skeleton/issues/) 中 07 已落地，frontier 剩 10/11/12，08/09 已解锁；mvp-scope 10/10 票全解决（02 战斗/效果边界已拍板 [ADR-0004](docs/adr/0004-combat-effects-boundary-engine.md)）。下一步：A 块 frontier 10/11/12 `/implement`，08/09 已解锁可做；B/C/D 待 `/to-tickets`。
- **engine/ 现状**：`src/mud_engine/` 下 `world`/`components`/`commands`/`parsing`/`intent`/`matching`/`scenes`/`scene_loader`/`save`/`tick`/`events`/`cli`/`__main__`。场景数据 `engine/data/m1_default_scene.yaml`，存档 `engine/save/`（运行时产物，gitignore）。`python -m mud_engine` 跑通真终端闭环：移动/查看/拾取丢弃/容器/门与锁、方向与物品别名、静态 NPC 展示、周期+退出存档+崩溃恢复、on_tick 事件分发（块 A 地基）。184 测试，`just gate` 全绿。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **M1 07 号票：事件总线 + on_tick 分发**（[07-event-bus-and-on-tick-dispatch](.scratch/m1-core-engine-skeleton/issues/07-event-bus-and-on-tick-dispatch.md)，resolved）：新增 `events.py`（`EventBus` 按 key 路由 handler 列表 + `TickContext` frozen dataclass + `ON_TICK` 常量），挂 `World.events`（实例隔离、不进存档）；`TickLoop` 加可选 `world` 参数，`advance` 推进 tick 后、周期存档前分发 `on_tick`（fire-and-forget 不短路，§12 多规则按 any/all 聚合不互斥）；存档走 `save_fn` 等价机制（issue 验收 #4 允许），`force_save` 不分发 on_tick（退出前立即存档不触发世界推进）。ADR-0004"骨架固定+钩子策略注入"手法推广到非战斗系统的共同地基（`register` 与 `commands.register` 同构、与 `register_condition` 同源）。新增 `test_events.py`（12）+ `test_tick.py` 扩展（6），166->184 测试全绿，`/code-review` 双轴过（0 硬违规/0 spec 缺失，1 判断题已正当化）。
- [x] **M1 扩展调研综合 + 范围决策**（2026-07-19）：用户要求 M1 不进 M2、深入打磨物品/NPC/Nature + DSL 动态规则。4 个并行 subagent 调研（物品/NPC/Nature/DSL，精读拆解说明书 + LPC + 旧方案/避坑清单），综合笔记 [.scratch/m1-core-engine-skeleton/research-m1-extension-items-npc-nature.md](.scratch/m1-core-engine-skeleton/research-m1-extension-items-npc-nature.md)。核心结论：三系统 + 战斗指向同一架构主线（ADR-0004 "骨架固定 + 钩子策略注入"推广到非战斗系统），当前 M1 缺事件分发基础设施（execute 无环绕 / tick 无分发 / world 无总线）+ 通用条件求值器是必补地基。用户拍板 M1 扩展 scope：块 A 引擎基础设施（事件点空挂 + 条件求值器 + YAML 透传 + 三态标注）+ 块 B Nature（时辰循环 + 条件 + 文案 + 广播 + 天气晴雨骨架）+ 块 C 物品（能力组件化全做占位 + 转移原语 + 堆叠 + 标志位 + 容器 + look + weight/max_capacity）+ 块 D NPC（Behavior/AIController 地基 + Spawn/Reset + ask/say/Chatter 轻量行为）。战斗/经济/任务/Nature 延伸全推 M2+。下一步 /to-spec 产出 M1 扩展 spec。**已产出**：独立扩展 spec [spec-extension.md](.scratch/m1-core-engine-skeleton/spec-extension.md)（不改原 spec.md，`ready-for-agent`），覆盖块 A 引擎基础设施（事件点空挂 + 条件求值器 + YAML 透传 + 三态标注）+ 块 B Nature（时辰循环 + 谓词 + 文案 + 广播 + 天气晴雨）+ 块 C 物品（能力组件化占位 + 转移原语 + 堆叠 + 标志位 + 容器 + look + weight/capacity）+ 块 D NPC（Behavior/AIController 地基 + Spawn/Reset + ask/say/Chatter），测试 seam 沿用 execute_line + tick_loop.advance + 求值器纯函数。下一步 /to-tickets 按 A/B/C/D 拆票（块 A 事件点地基是 B/C/D 共同前置）。**A 块已拆成 [07-12 六票](.scratch/m1-core-engine-skeleton/issues/)**（`ready-for-agent`，扁平命名 `NN-slug.md`）：07 事件总线+on_tick / 08 命令钩子 / 09 领域事件点 / 10 条件求值器 / 11 YAML 透传 / 12 三态标注；frontier 07/10/11/12，07 完成解锁 08/09。B/C/D 待 `/to-tickets`。
- [x] **mvp-scope 02 号票拍板：战斗/效果边界归引擎**（[02](.scratch/mvp-scope/issues/02-engine-boundary-combat-effects.md)，resolved；[ADR-0004](docs/adr/0004-combat-effects-boundary-engine.md)，2026-07-19）：用 `/design-an-interface` 三源调研（旧引擎 archive `resolve_attack` 七步 + `ConditionSystem`/`register_condition` 注入点；LPC `combatd.c do_attack` 七步 + `condition.c` heart_beat 调度；A06/D05 研究产出）+ 三个 radical 不同的边界设计对比，拍板"流程归引擎、数值归题材包"的精确边界--引擎内嵌"七步顺序 + AP/DP 概率判定结构 + Effect 调度/衰减/移除机制"为不变量，题材包注入"每步数值/文案/钩子行为 + PowerModel 公式 + condition handler + 声明式 stacking_policy/EffectMode"。选定"骨架固定+钩子策略注入"为主体，grafting"最大灵活"稿的 PowerModel 策略注入口（解决 `skill_power` 公式锁死武侠语义的裂缝）。战斗/状态/技能/死亡轮回四子系统归类（MVP 必做）维持不变，mvp-scope 10/10 票全解决，M2 `/to-spec` 可直接推进。
- [x] **M1 05 号票：心跳循环 + 存档与崩溃恢复**（[05-tick-loop-save-crash-recovery](.scratch/m1-core-engine-skeleton/issues/05-tick-loop-save-crash-recovery.md)，resolved）：新增 `save.py`（全量 per-entity JSON 存档 + staging 快照目录 + symlink 原子发布 + 容错 restore 跳过损坏条目记 warning）+ `tick.py`（`TickLoop`：tick 计数 + 间隔触发存档 + `force_save`）；`World` 加 `create_entity_with_id`/`all_entities`/`components_of` 供 restore/serialize（stable id，出口/门/容器引用直接生效）；`cli.run_repl` 接入 `tick_loop`（每命令 `advance`、退出前 `force_save`）；`__main__` 启动时 `has_save` 则 `restore_world` 否则 fresh scene。崩溃安全靠 staging 目录 + `os.replace` 原子发布 symlink（`current` 永远指向完整快照，写入中途崩溃留孤儿 staging 不影响上次发布）。新增 `test_save.py`（11）+ `test_tick.py`（6）+ `test_world`/`test_cli` 扩展，166 测试全绿，`/code-review` 双轴过（修了 `WithTheDefaultInterval` 嵌套类不在 `python_classes` 被静默跳过的硬违规 + 删 dead export `SaveError`）。
- [x] **M1 04 号票：门与动态出口**（[04-doors-and-dynamic-exits](.scratch/m1-core-engine-skeleton/issues/04-doors-and-dynamic-exits.md)，resolved）：新增独立于 `Exits` 的 `Doors` 组件（`DoorState` 开/关/锁 + `Door` 钥匙物品 id）+ `open`/`close`/`knock`/`unlock` 命令（复用 02 的 `match_target` 方向解析，`_parse_go` 重构为 `_parse_direction(verb=...)`）；`go` 关/锁门拦截、`look` 出口标注门状态；YAML 加 `door`/`key` 字段（顺带补上 06 号票留的门/锁表达后续小补丁，loader 顺序改 rooms->items->exits 以让门锁引用物品 entity id）。默认场景 start_yard south 关门、corridor north 锁门 + iron_key 钥匙（放 corridor）、新增 storage_room。动态出口靠 `Exits.by_direction` 可变 dict（03 已设计）+ 测试验证增删后 look/go 反映。新增 `test_doors.py`（31）+ `test_scene_loader` 门加载测试（6），139 测试全绿，`/code-review` 双轴过（修了 `AfterOpening` 嵌套类不带 `When*` 前缀被 pytest 静默跳过的硬违规；3 个判断性 smell 接受）。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

1. **M1 扩展 A 块 `/implement`（续）**：07 已落地（事件总线+on_tick）。A 块 frontier 剩 [10](.scratch/m1-core-engine-skeleton/issues/10-condition-expression-evaluator.md) 条件求值器 / [11](.scratch/m1-core-engine-skeleton/issues/11-yaml-unknown-section-passthrough.md) YAML 透传 / [12](.scratch/m1-core-engine-skeleton/issues/12-component-field-tri-state.md) 三态标注（无前置可立即开始）；[08](.scratch/m1-core-engine-skeleton/issues/08-command-lifecycle-hooks.md) 命令钩子 / [09](.scratch/m1-core-engine-skeleton/issues/09-domain-event-points.md) 领域事件点 已被 07 解锁。用 `/implement` 一次一个 ticket、清一次上下文。A 块完成后 `/to-tickets` 拆 B/C/D（B/C/D 相对独立可并行；A1 on_tick 给 B1 Nature 推进 + D1 NPC 行为，A2 条件求值器给 B/C/D 条件）。
2. M1 里程碑收尾：M1 扩展完成后准备 M2（一个 MVP 场景端到端可玩）`/to-spec`。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
