---
Status: resolved
---

# 10 — 机关 #10 柔丝索跨玩家捕获

**What to build:** 新增一个 `SkillBehavior`（招式命中回调，非 `RoomHook` 房间生命周期钩子）：施法者对同房间另一名玩家使用柔丝索类招式命中后，直调 `01` 建的「受限实体移动」方法本体（该方法需同时可被 `RoomHook` 窄 `ctx` 与 `SkillBehavior` 双方共享调用，不只挂在 `ctx` 对象上），把目标玩家移动到指定房间。被捕获后目标玩家确实出现在目标房间（可观察的位置变化）。测试用同一 `World` 内的双 `PlayerSession` seam（复用频道/spawn/任务 effort 落地的能力）驱动"捕获者 + 被捕获者"两个会话。不新建通用远程传送命令面。在 `xingxiu_mechanics.yaml` 追加对应验收房间（供双会话测试落脚）。

对应 spec：US43–46；Testing S0/S1。

**Blocked by:** `01`（受限实体移动方法本体需实现为可复用独立方法）。

- [x] 新增柔丝索类 `SkillBehavior`：命中回调里直调受限实体移动方法本体（不经过 `RoomHook` 注册表，不假装自己是房间钩子）。
- [x] 移动效果：目标玩家的 `Position` 变为指定房间（复用既有「改位置 + 分发进出房间事件」路径）。
- [x] 不新建通用远程传送命令面；本机关的改世界能力仍收在窄 `ctx`/受限移动方法本体范围内。
- [x] `xingxiu_mechanics.yaml` 追加至少一条验收房间（施法房 + 目标房）。
- [x] 测试（S0）：直调 `SkillBehavior` 命中回调 + 受限移动方法本体，断言目标位置变化。
- [x] 测试（S1）：同一 `World` 内 `spawn_player_session` 出两个会话（捕获者/被捕获者），捕获者对被捕获者使用招式命中后，断言被捕获者 `Position` 随之改变（不需要真实联网）。
- [x] `just test` 全绿。

## Comments

### 实现摘要（2026-07-22 Wave 6）

- **SkillBehavior**：`silk_rope`（`SilkRopeCaptureBehavior`）；`hit_ob` 直调 `relocate_entity(world, defender_id, to_room)`，不经 `RoomHook` 注册表
- **活引用**：`CombatContext` 增可选 `world` / `attacker_id` / `defender_id`（默认 `None`）；`build_combat_context` 填入。纯函数测试不填；缺引用或未知房间键时只播报不改世界
- **params / 构造**：`SilkRopeCaptureBehavior(capture_room="silk_prison")`；内置默认键 `silk_prison`
- **切片**：`silk_yard`（施法房）+ `silk_prison`（捕获房）；`dig_base` 出口 `silk`；顶层 `skills.silk_rope`（招式「柔丝索」force=40）；`player.skills.silk_rope: 1`
- **播报**：`柔丝索缠住对方，将其拽入密室！`
- **测试**：`engine/tests/test_xingxiu_mechanics_10.py`（S0 直调 / S1 双会话 `resolve_one_strike` + `attack`/`TickLoop` / 切片可玩）
- **不做**：通用远程传送命令面；不把本机关做成 `RoomHook`
