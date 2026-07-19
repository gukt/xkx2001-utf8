# 项目进度

> 本文件是跨 session 的"活的状态"--每个 session 第一件事读它，知道做到哪、下一步做啥、什么卡住。
> 每个 session 结束前更新它。这是交接的唯一信源。
>
> 2026-07-17 项目重设、07-18 新目标定稿（原目标与取舍战略已放弃）。新目标用 `/wayfinder` 走完 [.scratch/mvp-scope/](.scratch/mvp-scope/) 10/10 票决策并写回 [CLAUDE.md](CLAUDE.md) 的"项目一句话"与"架构不变量"。重设前的进度历史见 [docs/archive/PROGRESS.md](docs/archive/PROGRESS.md)，仅作背景参考。

**最后更新**：2026-07-19：M1 12 号票落地（组件字段三态标注，[12](.scratch/m1-core-engine-skeleton/issues/12-component-field-tri-state.md) resolved）：`components.py` 字段三态从"运行时可变 vs 启动固定"两态补第三态"瞬时（运行时可变不进存档）"，用 dataclass field metadata（`TRANSIENT` key）+ `transient_field()` helper 标注（避坑清单 §28，为 §37 分层铺路，Nature 衍生态 B 块会是第一个真实用例）；`save.py` `_serialize_entity` 序列化 chokepoint 调 `_strip_transient` 兜底过滤：瞬时字段一律不进存档、codec 误带剔除+记警告、无瞬时字段组件 no-op 快路径零回归；288->292 测试全绿，`/code-review` 双轴过（0 硬违规/0 spec 缺失）。A 块 frontier 剩 [11](.scratch/m1-core-engine-skeleton/issues/11-yaml-unknown-section-passthrough.md)；mvp-scope 10/10 票全解决；M1 01~12 全 resolved（A 块 07/08/09/10/12 落地，11 待）。综合笔记 [.scratch/m1-core-engine-skeleton/research-m1-extension-items-npc-nature.md](.scratch/m1-core-engine-skeleton/research-m1-extension-items-npc-nature.md)。

## 当前状态速览

- **阶段**：M0 完成；M1 01~12 号票全 resolved（12 三态标注 / 09 领域事件点 / 10 条件求值器 / 08 命令生命周期钩子 / 07 事件总线+on_tick）；M1 扩展 A 块 [07-12 六票](.scratch/m1-core-engine-skeleton/issues/) 中 07/08/09/10/12 已落地，frontier 剩 11；mvp-scope 10/10 票全解决（02 战斗/效果边界已拍板 [ADR-0004](docs/adr/0004-combat-effects-boundary-engine.md)）。下一步：A 块 frontier 11 `/implement`；B/C/D 待 `/to-tickets`。
- **engine/ 现状**：`src/mud_engine/` 下 `world`/`components`/`commands`/`conditions`/`parsing`/`intent`/`matching`/`scenes`/`scene_loader`/`save`/`tick`/`events`/`cli`/`__main__`。场景数据 `engine/data/m1_default_scene.yaml`，存档 `engine/save/`（运行时产物，gitignore）。`python -m mud_engine` 跑通真终端闭环：移动/查看/拾取丢弃/容器/门与锁、方向与物品别名、静态 NPC 展示、周期+退出存档+崩溃恢复、on_tick 事件分发、命令 before/after 生命周期钩子、领域事件点（移动/物品/门）+ 条件求值器最小版 + 组件字段三态标注（瞬时字段不进存档）（块 A 地基）。292 测试，`just gate` 全绿。

## Done

> 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)。

- [x] **M1 12 号票：组件字段三态标注**（[12-component-field-tri-state](.scratch/m1-core-engine-skeleton/issues/12-component-field-tri-state.md)，resolved）：`components.py` 字段三态从"运行时可变 vs 启动固定"两态补第三态"瞬时（运行时可变不进存档）"，用 dataclass field metadata（`TRANSIENT` key）+ `transient_field()` helper 标注（避坑清单 §28，为 §37"短延迟内存态 vs 长周期持久态"分层铺路，Nature 衍生态 B 块会是第一个真实用例）；`save.py` `_serialize_entity` 序列化 chokepoint 调 `_strip_transient` 兜底过滤：瞬时字段一律不进存档、codec 误带剔除并记警告（surfacing 编码 bug，不静默吞也不让一个 codec 失误破坏整次存档）、无瞬时字段组件走 no-op 快路径零回归。新增 `test_transient_fields.py`（4）：正确 codec 省略瞬时字段 + 恢复后回默认 / leaky codec 被 chokepoint 兜底剔除+记警告 / 现有组件 payload 不被过滤增删。288->292 测试全绿，`/code-review` 双轴过（0 硬违规/0 spec 缺失，3 判断题均 acceptable）。
- [x] **M1 09 号票：领域事件点（移动/物品/门）**（[09-domain-event-points](.scratch/m1-core-engine-skeleton/issues/09-domain-event-points.md)，resolved）：在 `_cmd_go`/`_cmd_take`/`_cmd_drop`/门命令路径埋**领域语义级**事件点（空挂调用，M1 默认放行不改现有命令行为），复用 07 的 `world.events` 事件总线。移动：`on_before_enter_room`（可否决，移动前）/ `on_enter_room` / `on_leave_room`（移动后，leave 先 enter）/ `on_traverse_blocked`（出口存在但被门挡住时，带 `door_state` 区分关/锁）；物品：`on_take` / `on_drop`（均可否决，转移前）；门：`on_door_state_change`（open/close/unlock 改状态处，经 `_set_door_state` helper 集中分发；knock 与无变化路径不触发）。与 08 的命令级 `on_command_before`/`on_command_after` 互补：08 看命令 intent（粗粒度），09 看领域上下文（细粒度，"门被打开"由 open/close/unlock 三处收敛到一个事件名）。4 个 frozen dataclass 上下文锁定形状（`EnterRoomContext`/`TraverseBlockedContext`/`TransferContext`/`DoorStateChangeContext`，字段全 EntityId/枚举无 mutable 引用；`TransferContext` 的 `src`/`dst` 形状对齐块 C `transfer(item, src, dst)` 原语 spec user story 23）。可否决 before 复用 08 的 `Allow`/`Deny`（领域级无 `Replace` 改写语义），经 `_run_vetoable`（与 08 `_run_before_hooks` 同模式、首个 `Deny` 短路、`None` 容错）聚合。新增 `test_domain_events.py`（47），241->288 测试全绿，`/code-review` 双轴过（0 硬违规/0 spec 缺失，Duplicated Code 判断题已正当化）。
- [x] **M1 10 号票：通用条件表达式求值器最小版**（[10-condition-expression-evaluator](.scratch/m1-core-engine-skeleton/issues/10-condition-expression-evaluator.md)，resolved；**补记**：commit `1a6d1800`，前 session 落地未更新 PROGRESS，此处基于 commit + spec user story 8/9 补记）：新增 `conditions.py`（`evaluate(condition, context) -> bool` 纯函数，spec 块 A user story 8/9/A2）+ `test_conditions.py`。支持字面量谓词（`is_night`/`is_day`/`is_raining`）、相等比较（`phase == night`）、布尔组合（`and`/`or`/`not`）；表达式形状按"未来可换受限 AST"设计，M1 用结构化 Python 字面量占位、不引入裸 Python lambda（避坑清单 §F）。是门/物品/NPC 动态规则的共同条件子语言地基。212->241 测试。
- [x] **M1 08 号票：命令生命周期钩子 before/after**（[08-command-lifecycle-hooks](.scratch/m1-core-engine-skeleton/issues/08-command-lifecycle-hooks.md)，resolved）：`execute` 外包 `on_command_before`/`on_command_after`（Inform 7 四段式"前置校验->执行->后置通知"精炼，"夜里 NPC 不卖酒""诅咒物品拿不起"等前置否决规则的挂载点）。`Allow`/`Deny(message)`/`Replace(intent)` 三态 frozen dataclass（形状被 `TestCommandLifecycleContract` 锁定）。before 按注册顺序遍历：`Replace` 改写生效意图（链式，后续钩子看到改写后的）、首个 `Deny` 否决并短路、`Allow`/`None`（容错）放行；`Replace` 改写动词后按生效意图重新解析处理函数；`Deny` 跳过 after。after 按注册顺序折叠消息列表。钩子复用 07 的 `world.events` 注册表（`register(ON_COMMAND_BEFORE, handler)` 与 `commands.register` 同构）；给 `EventBus` 加 `handlers_for`（返回 handler 列表副本）供 before 否决短路 / after 消息折叠自行聚合（07 已为"调用方自行取聚合"预留，`dispatch` 顺手 DRY 复用 `handlers_for`，on_tick 零回归）。挂 `world.events` 天然实例隔离（每 `build_world` 一个空 bus，测试间不泄漏）。新增 `test_command_hooks.py`（24）+ `test_events.py` 扩展 `handlers_for` 契约（4），184->212 测试全绿，`/code-review` 双轴过。
- [x] **M1 07 号票：事件总线 + on_tick 分发**（[07-event-bus-and-on-tick-dispatch](.scratch/m1-core-engine-skeleton/issues/07-event-bus-and-on-tick-dispatch.md)，resolved）：新增 `events.py`（`EventBus` 按 key 路由 handler 列表 + `TickContext` frozen dataclass + `ON_TICK` 常量），挂 `World.events`（实例隔离、不进存档）；`TickLoop` 加可选 `world` 参数，`advance` 推进 tick 后、周期存档前分发 `on_tick`（fire-and-forget 不短路，§12 多规则按 any/all 聚合不互斥）；存档走 `save_fn` 等价机制（issue 验收 #4 允许），`force_save` 不分发 on_tick（退出前立即存档不触发世界推进）。ADR-0004"骨架固定+钩子策略注入"手法推广到非战斗系统的共同地基（`register` 与 `commands.register` 同构、与 `register_condition` 同源）。新增 `test_events.py`（12）+ `test_tick.py` 扩展（6），166->184 测试全绿，`/code-review` 双轴过（0 硬违规/0 spec 缺失，1 判断题已正当化）。

## In Progress

当前无进行中项。

## Blocked

**当前无阻塞项。**

## Next Up

1. **M1 扩展 A 块 `/implement`（续）**：07/08/09/10/12 已落地（事件总线+on_tick / 命令 before/after 钩子 / 领域事件点 / 条件求值器 / 三态标注）。A 块 frontier 剩 [11](.scratch/m1-core-engine-skeleton/issues/11-yaml-unknown-section-passthrough.md) YAML 透传（无前置可立即开始）。用 `/implement` 一次一个 ticket、清一次上下文。A 块完成后 `/to-tickets` 拆 B/C/D（B/C/D 相对独立可并行；A1 on_tick 给 B1 Nature 推进 + D1 NPC 行为，A2 条件求值器给 B/C/D 条件，A1 领域事件点给 B Nature 切换广播 / C 转移 reject 钩子 / D NPC 进房反应）。
2. M1 里程碑收尾：M1 扩展完成后准备 M2（一个 MVP 场景端到端可玩）`/to-spec`。

## 交接约定

- 开工读：本文件 + [CLAUDE.md](CLAUDE.md)。收工更新 Done/In Progress/Blocked/Next Up + 日期。
- Done 滑动窗口只留最近 5 条，更早的见 [已完成项归档](.scratch/progress-archive.md)；单条细节进 issue / ADR（[docs/adr/](docs/adr/)） / 调研笔记。
- 旧引擎源码：`git show archive/engine-pre-m1-rewrite:engine/...`，禁止当重写起点。
