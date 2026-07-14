# ADR-0037：M3-1 子任务 5 可玩 demo 整合（CLI 接 Engine + 消息缓冲 + 死亡轮回接入）

- 状态：已通过（2026-07-13）
- 日期：2026-07-13
- 阶段：M3 Wave 2（M3-1 子任务 5 可玩 demo 整合）
- 关联 dissent：[ADR-0032](ADR-0032-family-core-loop-design.md) 决策 4（死亡轮回整合）/ [ADR-0029](ADR-0029-world-governance-system.md) 开放问题 1（death_stage 归 GovernanceSystem）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 7（call_out->Effect tick 推进）/ dissent 8（消息系统渐进）

## 背景

M3-1 子任务 1-4 完成拜师（bai/kneel）、练功（learn/practice/dazuo/tuna/enable）、任务链（fight）命令组 + 雪山派子集内容。但 [16-M3](../xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) M3-1 验收要求"1 门派完整循环可跑（拜师 -> 练功 -> 战斗 -> 任务 -> 死亡轮回 -> 还阳）"，落地时发现 3 个缺口：

1. **CLI REPL 未接入新命令**：[cli.py](../../engine/src/xkx/cli.py) 的 `parse_and_run` 只有 S5a 的 go/get/kill/ask/give/quest/look/inventory/hp，拜师/练功/fight 命令未接入（命令函数已实现于 commands.py，8 段管线已注册，但 CLI 前端未接）。
2. **练功 busy + 死亡轮回需要 tick 推进**：dazuo/tuna 启动 exercise/respirate EffectComp（每 tick 增长 neili/jingli，结束判定 max 提升）；die() 启动 death_stage EffectComp（首延 30 tick + 5 段每段 5 tick 推进到还阳）。CLI 当前无 tick 循环（Game 无 Engine），busy 永不完成、死亡永不还阳。
3. **`_handle_player_death` 是 S5a 简化版**：传送 spawn_room + 恢复 qi/jingli，未接阶段 2 [death.die()](../../engine/src/xkx/runtime/death.py) + [governance](../../engine/src/xkx/runtime/governance.py) 阴间轮回（ADR-0032 决策 4"死亡部分只需内容整合 + 阴间还阳衔接 2.6"未落地）。

## 问题

1. **tick 推进方式**：练功 busy 与死亡轮回都需要 tick 驱动，CLI 无 tick 循环。需决定 CLI 如何接入 Engine 推进。
2. **消息丢弃**：`ConditionSystem.update` 丢弃 `result.messages`，`_tell`（death/governance）占位 `return None`（消息系统后置 M3）。CLI 自动推进时阴间 5 段剧情/练功完成消息玩家看不到。
3. **death_stage 被 ConditionSystem 误处理**（落地遗漏）：ADR-0029 开放问题 1 裁决"death_stage 归 GovernanceSystem 独立遍历"，但 [ConditionSystem.on_tick](../../engine/src/xkx/runtime/conditions.py) 遍历所有 EffectComp（含 death_stage），`_default_trigger` 衰减 duration + update 修改 next_tick，导致 GovernanceSystem 看不到 `next_tick<=tick`，阴间剧情无法推进到还阳。阶段 2 test_governance 未暴露（只用 GovernanceSystem，不注册 ConditionSystem）。
4. **内容缺口**：darba（fight_win 任务 giver）未放置到任何房间；gongcang 剃度 `kneel` require `pending/join_lama` 但 `bai gongcang` 收徒后不设该 flag -> kneel 永远"未得到受戒许可"。

## 决策

### 决策 1：CLI 接 Engine + 自动推进（用户裁决）

`load_game` 创建 `Engine(world)` + 注册 `HealSystem` + `ConditionSystem` + `GovernanceSystem`（不注册 CombatBridge/StorageSystem/ConnectionSystem -- CLI kill 同步多回合、demo 不存档、无会话），挂 `game.engine`。

`parse_and_run` 执行命令后：
- 状态变更命令跑 1 heartbeat tick（HealSystem 自然恢复 + Condition 衰减）+ 打印 `pending_messages`；
- `dazuo`/`tuna` 后 `_auto_advance`：循环 tick 直到 exercise/respirate EffectComp 移除（练功完成）；
- `kill` 玩家死亡后 `_auto_advance`：循环 tick 直到 death_stage EffectComp 移除（还阳）；
- `_AUTO_ADVANCE_MAX_TICKS=200`（阴间 55 tick + 余量）防无限循环。

用户裁决（2026-07-13）：接 Engine + 自动推进（玩家无需手动 wait，demo 流畅）。对比"接 Engine + wait 命令"（最 MUD 保真但操作繁琐）/"命令内部同步推进"（耦合 System 进命令）/ "仅 e2e 接 tick"（CLI demo 不完整）。

### 决策 2：world 最小消息缓冲（消息系统渐进最小版）

`build_world` 初始化 `world.pending_messages: list[str] = []`（与 `current_tick`/`theme_config` 动态属性一致）。`_tell`（death/governance）改写缓冲；`ConditionSystem.update` 末尾 `extend(result.messages)`；CLI 跑 tick 后 `_drain_pending` 打印 + 清空。

**不违反"消息系统后置 M3"**：完整 WS 推送系统（connection/ws_server 按 eid 分发）后置 M3，本决策是最小渐进版（单玩家 demo 全量打印，多实体分发后置）。getattr 健壮处理未注入的测试 World，不影响现有测试。

### 决策 3：kill 玩家死亡接入 die()（ADR-0032 决策 4 落地）

`_handle_player_death` 改调 `die(world, player_id, killer_id, tick=_current_tick(game))`（替代 S5a 简化传送）。die() 设 ghost=1 + move `theme_config.death_room` + `enter_underworld` 启动 death_stage EffectComp。还阳由 GovernanceSystem 推进 death_stage 到 stage 4 调 `reincarnate_at`（恢复 + move revive_room），不在 kill 命令内完成。kill 消息保留"眼前一黑"，移除即时"有了知觉"（还阳由 tick 推进）。test_s5_playtest 适配为验证 die() 阴间路径。

### 决策 4：ConditionSystem 跳过 death_stage（ADR-0029 开放问题 1 落地遗漏修复）

`ConditionSystem.on_tick` + `update` 遍历跳过 `effect_id == "death_stage"`：on_tick 不分派 `_default_trigger`（避免衰减 duration），update 不修改 `next_tick`（避免 GovernanceSystem 看不到 `next_tick<=tick`）。death_stage 完全归 GovernanceSystem 独立遍历（ADR-0029 开放问题 1 裁决落地）。字面量 `"death_stage"` 在 conditions.py + 注释引用 ADR-0029（不 import governance 避免循环依赖）。

### 决策 5：内容修补

- `rooms.yaml`：darba 放 `xueshan/yanwu`（演武场，"僧人们练武的地方"适合切磋）。
- `bai` 命令：`_recruit_apprentice` 成功后若 `app_config.kneel.require_flag` 存在，设该 marks flag（对照 LPC gongcang attempt_apprentice 通过后 set pending/join_lama，do_kneel 检查后剃度）。samu 无 kneel 配置不触发。

### 决策 6：内容平衡（用户裁决）

darba（130 级强 NPC，fight_win 需玩家赢）+ samu（拜师需 longxiang-banruo 30 级，learn 升到 30 需数百次）保持 LPC 强度不弱化（保真是项目核心不变量）。e2e 用直接设玩家属性测完整逻辑闭环（强玩家赢 darba / 设 longxiang-banruo 30 拜 samu）；CLI demo 体验流程不强求通关。

## 验收

- 1733 tests 全绿（+9 test_m3_playtest e2e），ruff 全过
- test_theme_neutrality（cli 源码无武侠路径/门派名）+ test_load_test 硬门禁持续通过
- e2e 完整闭环：拜师 gongcang 剃度 -> 练功（dazuo/tuna/learn 可玩，busy 自动完成）-> darba fight_win（e2e 强玩家）-> 死亡轮回（die + 阴间 5 段 + 还阳）-> samu 拜师

## 关联

- [ADR-0032](ADR-0032-family-core-loop-design.md) 决策 4（死亡轮回整合，复用 2.2/2.6）落地
- [ADR-0029](ADR-0029-world-governance-system.md) 开放问题 1（death_stage 归 GovernanceSystem 独立遍历）落地遗漏修复
- dissent 7（call_out -> Effect 翻译，练功 busy + 阴间 death_stage 复用 EffectComp tick 推进，ADR-0027 模式延伸）
- dissent 8（消息系统渐进，world.pending_messages 最小缓冲非完整 WS 推送，后置 M3）
