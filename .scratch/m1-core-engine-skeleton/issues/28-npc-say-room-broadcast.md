# 28 - say 命令 + 房间广播（D4）

**What to build:** `say <内容>` 向同房间所有人广播一句话，并触发 `on_hear_say` 钩子。为 Chatter 与未来 NPC 反应提供广播通道。

**Blocked by:** None - 可立即开始。

**Status:** ready-for-agent

- [ ] `say <内容>` 命令存在，说话者收到确认消息
- [ ] 同房间可观察实体能收到广播（测试可观察通道）
- [ ] 触发 `on_hear_say` 事件，测试 handler 收到正确参数
- [ ] 空内容被拒绝或给出提示
- [ ] 现有测试全绿（不回归）
