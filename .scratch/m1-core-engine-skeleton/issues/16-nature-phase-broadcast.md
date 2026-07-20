# 16 - 时辰切换广播（B4）

**What to build:** 相位切换时给所有户外房间在线玩家推一条 `time_msg`，挂 `on_nature_change` 事件点。玩家感知时间流动；广播机制本身可复用于未来天气变化。

**Blocked by:** 13 - 需要相位切换发生点。

**Status:** resolved（2026-07-20 re-pass：户外玩家判定改用 PlayerSession）

- [x] 相位切换时分发 `on_nature_change` 事件
- [x] 户外房间在线玩家收到 `time_msg`（经命令返回消息或等价可观察通道）
- [x] 室内玩家不收到 outdoors 广播
- [x] 注册测试 handler 断言 `on_nature_change` 被调用且参数正确
- [x] 现有测试全绿（不回归）

## Comments

### 2026-07-20 re-pass

- 复核既有 `TestPhaseBroadcast`：`on_nature_change` 分发、户外 `pending_messages`、室内不收。
- `_outdoor_player_ids` 改查 `PlayerSession` + `Position` + 房间 `outdoors`（承接 28 号票驱动源缝）；弃用 Container 启发式。
- 补测：户外挂 Container 的非玩家实体不产生额外广播副本。
- **残余债务**：`pending_messages` 仍为世界级扁平 list（M1 单玩家）；多玩家 per-session 消息桶未做，多连线时需重做投递模型。
