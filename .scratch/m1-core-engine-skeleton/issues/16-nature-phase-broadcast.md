# 16 - 时辰切换广播（B4）

**What to build:** 相位切换时给所有户外房间在线玩家推一条 `time_msg`，挂 `on_nature_change` 事件点。玩家感知时间流动；广播机制本身可复用于未来天气变化。

**Blocked by:** 13 - 需要相位切换发生点。

**Status:** ready-for-agent

- [ ] 相位切换时分发 `on_nature_change` 事件
- [ ] 户外房间在线玩家收到 `time_msg`（经命令返回消息或等价可观察通道）
- [ ] 室内玩家不收到 outdoors 广播
- [ ] 注册测试 handler 断言 `on_nature_change` 被调用且参数正确
- [ ] 现有测试全绿（不回归）
