---
Status: ready-for-agent
---

# 03 — 假多人 seam：按会话收件箱

**What to build:** 把当前单一扁平的 `world.pending_messages`（M1 单玩家假设下的共享队列，见 `world.py` 注释）改造为按接收者分发：每个带 `PlayerSession` 的实体有自己的消息收件箱，投递方（`room_say`、Nature 相位广播、死亡流程、交战结算等现有约 11 处 `pending_messages.append` 调用点）改为指定具体接收者实体，而不是塞进一个全局列表。提供测试/脚本 seam：同一 `World` 上可创建两个（或以上）挂 `PlayerSession` 的实体，分别对其派发命令，各自只收到该会话应收到的消息（比如同房 `say` 只投给房间内其它玩家会话的收件箱，不是全局广播）。单玩家 CLI（`cli.py`）体验不变——仍驱动"主会话"实体、drain 逻辑照旧打印，不要求本票改 REPL。

对应 spec：[.scratch/pre-m4-channels-spawn-quest/spec.md](../spec.md) US1、US2；建议实现顺序第 3 步的地基部分（票 `05` Channel 依赖本票）。

**Blocked by:** None — 可立即开始。

- [ ] 引入按会话/按实体的消息投递机制（例如 `World` 增加 `push_message(entity_id, text)` 或等价 API，内部维护 `entity_id -> list[str]` 而不是单一 `pending_messages: list[str]`），保留一个"主会话"概念供单玩家 CLI 沿用现有 drain 行为不变。
- [ ] 现有全部投递点（`messaging.room_say`、`death_flow.py` 的昏迷/复活/战胜文案、`nature.py` 相位广播、`combat_system.py` 拒绝/结算文案）改为指定接收者实体，而不是无条件 append 进全局列表；单玩家场景下行为与迁移前一致（回归测试锁定既有单玩家命令测试全绿）。
- [ ] 提供创建额外 `PlayerSession` 实体的测试/脚本辅助（不要求命令面/CLI 改动，纯 `World`/组件层 API 即可）。
- [ ] 测试（S1）：在同一 `World` 创建两个 `PlayerSession` 实体放进同一房间，A `say` 后断言 B 的收件箱收到"{A}说：..."、A 自己收到"你说：..."、且两者收件箱互不串号；不同房间的会话不会收到彼此房间广播。
- [ ] 不引入 `tune`/退订；本票不做 Channel（票 `05` 在本票之上继续）。
- [ ] `just test` 全绿，尤其是既有单玩家 CLI/命令回归测试。

## Comments
