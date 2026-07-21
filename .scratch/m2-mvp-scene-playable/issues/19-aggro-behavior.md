# 19 — NPC 主动攻击行为：Behaviors kind="aggro"

**What to build:** 落地 spec Implementation Decisions「G1」：`BehaviorSpec` 新增 `kind="aggro"` 一支，复用现有字段 `when`（条件求值器表达的场景级开关条件，如"仅野外"，不是"是否已有可攻击目标"这种存在量词判断——那由 handler 逻辑本身现算，不硬塞进条件语言）；触发时调用 12 号票已定义的"建立交战关系"共享函数（与 `attack` 命令共用同一个底层函数，类似 `room_say` 被 `say` 命令与 Chatter 行为共用的模式），不是 NPC 自己发起一条新的攻击判定路径。触发目标选择 MVP 简化为"房间内第一个符合条件（未在交战状态）的玩家"，不做威胁值/仇恨列表。`ai.py` 的 `_tick_behavior` 分发函数新增对 `"aggro"` kind 的处理分支（与现有 `"chatter"` 分支并列，复用同一个 `AIController` 遍历骨架，不改 tick 调度框架）。

**Blocked by:** 12（`attack`/建立交战关系的共享函数）。

**Status:** resolved

- [ ] `ai.py` 的 `_tick_behavior` 新增 `"aggro"` 分支：条件求值（复用 `condition_from_data`/`evaluate`）通过后，扫描同房间实体找"第一个未在交战状态（不带 `Engaged`）的玩家"。
- [ ] 找到目标时调用 12 号票暴露的"建立交战关系"共享函数（若 12 号票未把该逻辑拆成独立可复用函数，本票需要先做这个小范围重构——遵循"复用已有逻辑而非另起判定路径"的硬约束，这是本票验收的核心）。
- [ ] 找不到符合条件目标时静默跳过（同 Chatter 概率不命中时的行为），不报错、不产生任何消息。
- [ ] MVP 简化验收：房间内多个符合条件玩家时只攻击"第一个"（遍历顺序需确定性，测试锁定，不依赖 set 遍历的不确定顺序——若现有 `entities_in_room` 返回顺序不确定，本票需要在扫描逻辑里显式排序）。
- [ ] tick 层测试：野外 NPC（挂 `aggro` behavior）在玩家进入房间后的若干 tick 内触发交战（不需要玩家主动 `attack`）；已在交战状态的玩家不会被同一个/另一个 aggro NPC 重复建立交战（MVP 1 对 1 约束，复用 12 号票已有约束）。
- [ ] 现有测试全绿不回归（尤其 `test_npc_extension.py` 现有 Chatter 相关测试）。
