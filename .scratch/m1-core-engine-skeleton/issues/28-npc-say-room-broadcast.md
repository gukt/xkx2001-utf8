# 28 - say 命令 + 房间广播（D4）

**What to build:** `say <内容>` 向同房间所有人广播一句话，并触发 `on_hear_say` 钩子。为 Chatter 与未来 NPC 反应提供广播通道。

**Blocked by:** None - 可立即开始。

**Status:** resolved（2026-07-20 re-pass：PlayerSession 驱动源 + say 广播）

- [x] `say <内容>` 命令存在，说话者收到确认消息
- [x] 同房间可观察实体能收到广播（测试可观察通道）
- [x] 触发 `on_hear_say` 事件，测试 handler 收到正确参数
- [x] 空内容被拒绝或给出提示
- [x] 现有测试全绿（不回归）

## Comments

### 2026-07-20 re-pass

- 复核既有 `say` / `room_say` / `on_hear_say`（确认消息、空内容拒绝、事件上下文、NPC→玩家 pending）。
- 落地 US33：`PlayerSession` 空 marker 组件；`scene_loader._build_player` 挂载；save codec（空 dict）；`_is_player_entity` 改查 `PlayerSession`（弃用 Position+Container−NpcSpawnMeta 启发式）。
- `pending_messages` 仍为扁平 list（M1 单玩家够用）；多玩家 per-bucket 推后。
- 测试：`TestSayBroadcast` 7（含 PlayerSession 挂载 / Container 假人不收广播 / 存档 round-trip）。
