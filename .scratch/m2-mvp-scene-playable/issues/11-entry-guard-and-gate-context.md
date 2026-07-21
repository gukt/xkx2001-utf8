# 11 — 房间级门槏：EntryGuard 组件 + EntityGateContext（条件求值器新用法）

**What to build:** 落地 spec Implementation Decisions「E2」：`EntryGuard(condition: Condition, deny_message: str)` 挂在需要身份/装备校验的目标房间上，走 01 号票的房间级能力注册表。新增一个引擎自带（非空挂占位）的 `on_before_enter_room` 订阅者：检查 `to_room` 是否有 `EntryGuard`，有则构造 `EntityGateContext(faction_id=..., gender=..., is_wielding_edged_weapon=...)`（从发起移动的玩家实体读取 08 号票的 `Faction`、本票新增的 `Gender`、物品栏物品类型现算出来的**只读快照**，不是活引用），调 `conditions.evaluate`，不满足则 `Deny(deny_message)`。**关键约束：不扩展条件求值器语法**——`EntityGateContext` 只是新实现一份 `ConditionContext` 协议的具体类（与 `NatureState` 同构），`Predicate`/`Equals`/`And`/`Or`/`Not` 五种节点原样复用，`evaluate()` 函数不改一行。新增两个最小组件：`Gender(value: str)`（题材包决定取值集合，引擎不校验枚举，可选挂玩家/NPC）与 `ItemTags(tags: frozenset[str])`（如 `{"weapon","edged"}`，供"是否持有某类武器"现算，不新建专属武器类型枚举字段）。这是本 spec 唯一"新增一种 Context 实现类型"的地方，spec 特别标注需要格外注意契约测试覆盖，防止未来第三、第四种 Context 类型各自发明不兼容协议形状。

**Blocked by:** 01（`EntryGuard`/`Gender`/`ItemTags` 走注册表挂载），08（`EntityGateContext.faction_id` 需要 08 号票的 `Faction` 组件已存在）。

**Status:** resolved

- [x] `EntryGuard(condition, deny_message)` 组件落地，走房间级能力注册表（YAML `entry_guard:` 字段：条件表达式 + 拒绝文案，条件表达式复用 `ai.py` 里 `condition_from_data` 已定义的结构化 dict 形状，不新发明一套 YAML 条件语法）。
- [x] `Gender(value: str)`/`ItemTags(tags: frozenset[str])` 两个最小组件落地，`ItemTags` 走物品级能力注册表（`capabilities.CAPABILITIES`，本已存在的物品注册表，不是 01 号票新增的房间/NPC 注册表）。
- [x] `EntityGateContext` 实现 `ConditionContext` 协议（`phase`/`is_night`/`is_day`/`is_raining` 若不适用可返回合理缺省值——**或**评估是否需要扩展 `ConditionContext` 协议本身以容纳 `faction_id`/`gender`/`is_wielding_edged_weapon` 这几个新查询面；spec 明确"未来扩展查询面只需往协议加属性，旧 handler 不破坏"，本票需要做出这个协议扩展并确保不破坏 `NatureState`/`StubContext` 现有实现）。
- [x] `is_wielding_edged_weapon` 现算逻辑：遍历玩家物品栏挂 `ItemTags` 的物品，判断是否含 `"edged"`（或类似语义标签，具体标签集合由实现阶段与 24 号票的少林山门场景内容协调确定）。
- [x] `on_before_enter_room` 内置订阅者：`to_room` 挂 `EntryGuard` 时求值，`Deny` 时移动不发生（复用现有 `run_vetoable`/`Deny` 机制，不新发明否决信号）。
- [x] 契约测试：`EntityGateContext` 补一份类似 `test_conditions.TestStubContextProtocol` 的协议契约测试（`isinstance(ctx, ConditionContext)` 或扩展协议成立）。
- [x] 命令层测试：玩家不满足门槏条件时移动被拒绝并收到 `deny_message`；满足条件时正常进入；无 `EntryGuard` 的房间不受影响（零回归）。
- [x] 现有测试全绿不回归。

## Comments

- 2026-07-21：`ConditionContext` 扩 `faction_id`/`gender`/`is_wielding_edged_weapon`；`EntityGateContext` + `attach_entry_guards`；刃器标签约定 `edged`。
