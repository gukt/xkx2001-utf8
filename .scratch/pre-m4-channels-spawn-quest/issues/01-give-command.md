---
Status: resolved
---

# 01 — give 命令（物品交给 NPC）

**What to build:** 玩家可以用 `give <物品> to <目标>`（或等价语序）把背包里的一件物品转移进同房间某个 NPC 的容器（`Container`），作为一个通用命令能力独立交付——不挂任何任务判定，Quest 完成检测（票 `06`）后续挂在本命令的结算路径上，而不是反过来。目标解析复用现有物品/实体匹配（`matching.py`/`lookup.py`）在同房间范围找 NPC；物品转移复用 `transfer.py` 的 `transfer()` 原语（容量/重量校验、`no_drop` 等已有语义直接生效，不重新发明）。

对应 spec：[.scratch/pre-m4-channels-spawn-quest/spec.md](../spec.md) US23（"我想进行中把指定物品 give 给目标 NPC 后任务完成"的前置通用能力）。

**Blocked by:** None — 可立即开始。

- [x] `commands.py` 新增 `give` 命令：解析"物品名 + 目标名"（同房间 NPC，玩家当前不支持互相 give，OOS）；物品须在给予者 `Container`（背包）中；目标须是同房间、带 `Container` 的实体。
- [x] 复用 `transfer.py` 的 `transfer()` 完成物品从玩家 Container 移到 NPC Container，容量/重量超限、`no_drop` 等既有拒绝语义原样生效并给对应文案。
- [x] 目标不存在/不同房、物品不存在/不在背包、目标无法接收（如无 `Container`）等失败态均有清晰文案，且不改变任何组件状态（失败即原子回滚，不产生半转移）。
- [x] 成功文案（如"你把 X 交给了 Y。"）与其它转移类命令（`get`/`drop`）文风一致。
- [x] 命令注册遵循现有 `@register(...)` 模式（见 `get`/`drop`/`ask` 附近实现），含别名（如 `give ... to ...` 的介词解析，参考现有命令的参数解析方式）。
- [x] 测试：give 成功转移物品到 NPC 容器；NPC 容器可用 `look <npc>` 或既有断言方式验证物品已在其中；覆盖上述失败态；不破坏现有 `test_transfer.py`/物品相关测试基线。
- [x] `just test` 全绿。

## Comments

- 2026-07-22：落地 `give <物> to <NPC>`（parsing 介词 `to` + commands 复用 `transfer`）。无 Container / 无物 / 无 NPC / `no_drop` 均有清晰失败文案且不半转移；玩家互 give 明确拒绝。测试见 `test_give_command.py`。
