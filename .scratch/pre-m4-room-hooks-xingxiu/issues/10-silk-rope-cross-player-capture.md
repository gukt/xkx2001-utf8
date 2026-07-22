---
Status: ready-for-agent
---

# 10 — 机关 #10 柔丝索跨玩家捕获

**What to build:** 新增一个 `SkillBehavior`（招式命中回调，非 `RoomHook` 房间生命周期钩子）：施法者对同房间另一名玩家使用柔丝索类招式命中后，直调 `01` 建的「受限实体移动」方法本体（该方法需同时可被 `RoomHook` 窄 `ctx` 与 `SkillBehavior` 双方共享调用，不只挂在 `ctx` 对象上），把目标玩家移动到指定房间。被捕获后目标玩家确实出现在目标房间（可观察的位置变化）。测试用同一 `World` 内的双 `PlayerSession` seam（复用频道/spawn/任务 effort 落地的能力）驱动"捕获者 + 被捕获者"两个会话。不新建通用远程传送命令面。在 `xingxiu_mechanics.yaml` 追加对应验收房间（供双会话测试落脚）。

对应 spec：US43–46；Testing S0/S1。

**Blocked by:** `01`（受限实体移动方法本体需实现为可复用独立方法）。

- [ ] 新增柔丝索类 `SkillBehavior`：命中回调里直调受限实体移动方法本体（不经过 `RoomHook` 注册表，不假装自己是房间钩子）。
- [ ] 移动效果：目标玩家的 `Position` 变为指定房间（复用既有「改位置 + 分发进出房间事件」路径）。
- [ ] 不新建通用远程传送命令面；本机关的改世界能力仍收在窄 `ctx`/受限移动方法本体范围内。
- [ ] `xingxiu_mechanics.yaml` 追加至少一条验收房间（施法房 + 目标房）。
- [ ] 测试（S0）：直调 `SkillBehavior` 命中回调 + 受限移动方法本体，断言目标位置变化。
- [ ] 测试（S1）：同一 `World` 内 `spawn_player_session` 出两个会话（捕获者/被捕获者），捕获者对被捕获者使用招式命中后，断言被捕获者 `Position` 随之改变（不需要真实联网）。
- [ ] `just test` 全绿。

## Comments

