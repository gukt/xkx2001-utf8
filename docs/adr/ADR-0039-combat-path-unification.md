# ADR-0039：战斗路径统一（kill/fight -> CombatState + CombatBridge tick 驱动）

- 状态：已通过（2026-07-14）
- 日期：2026-07-14
- 阶段：M3 收官后技术债补缺口（B 架构一致性）
- 关联：[CLAUDE.md](../../CLAUDE.md) 关键架构不变量（tick=1s 驱动 + System tick 派生变更不经 Command）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 7（派生变更审计覆盖缺口）+ Q3 裁决（Command 仅覆盖外部意图，System.update 覆盖派生变更）/ [04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 2.4 Combat / [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md)（combat 确定性边界，本轮启用其重放）/ [ADR-0027](ADR-0027-combat-callout-formation-golden-trace.md)（auto_fight + call_out 翻译）/ [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)（System 基类）

## 背景

**LPC 战斗机制**（[adm/daemons/combatd.c](../../adm/daemons/combatd.c) + [feature/attack.c](../../feature/attack.c) + [cmds/std/kill.c](../../cmds/std/kill.c) 实证）：

- kill/fight 命令**只建立敌对关系**：`kill_ob(obj)` -> `fight_ob(obj)` -> `set_heart_beat(1)` + 加入 `enemy` 数组，**命令返回**。绝不同步多回合循环。
- 后续攻击由 **heart_beat 每秒 1 tick 驱动**：`heart_beat()` -> `attack()` -> `select_opponent()` -> `COMBAT_D->fight()` -> `do_attack()`。玩家发起 kill 后，所有持续攻击由 heart_beat 自动驱动，玩家在 tick 间可输入 flee/surrender/换技能。
- NPC 主动攻击是**事件触发（进入房间 init()）+ heart_beat 持续**两段式（auto_fight + start_berserk/hatred/vendetta/aggressive）。

**greenfield 现状**（[commands.py](../../engine/src/xkx/runtime/commands.py) `kill`/`fight` 函数）：

- kill/fight 命令**命令内同步多回合循环**（`for _ in range(max_rounds):` 每回合 player 攻 + npc 反击，一次命令调用内全部结算完毕）。
- **绕过已就位的 tick 驱动架构**：`CombatState` 组件（[components.py](../../engine/src/xkx/runtime/components.py)，`enemy_ids`/`is_fighting`/`guarding`）+ `CombatBridge` 适配器（[engine.py:142](../../engine/src/xkx/runtime/engine.py)）+ `_auto_advance` 推进模式（[cli.py:165](../../engine/src/xkx/cli.py)）全部就位，但 kill/fight 既不设 CombatState 也不依赖 CombatBridge。
- `CombatState.is_fighting` 永不被设为 True -> commands.py 中"战斗中不能练功/打坐/吐纳"等检查（第 997/1063/1108/1153 行）**永不触发**。
- `CombatState.enemy_ids` 零写入点 -> `CombatBridge.tick` **空转**（combatants 为空直接 return）。
- [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) 投入的 combat 确定性重放（input log + `replay` + CombatBridge）在实际 demo **未生效**（战斗走命令内 `next_seed()` 同步循环，不记录 input log，不可 replay）。

**违反的不变量**（CLAUDE.md 关键架构不变量）：

- **"tick=1s + compute<100ms + 非均匀 tick"**：kill 命令不是 tick 驱动，命令内瞬时结算 30 回合。
- **"Command 仅覆盖外部意图，System tick 派生变更不经 Command"**（05 Q3 裁决）：kill 命令在 Command 内做战斗 mutation（resolve_attack + apply_effects），战斗派生变更（伤害/死亡/经验）应经 System tick（CombatBridge）。

**dissent 7**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 7 条）："System.update 的 mutation（战斗外 exp/jingli、condition 效果、heal）无 Command 级审计轨迹。战斗有副作用账本覆盖，其他 System 逐个决定审计粒度。"--命令内同步循环使战斗 mutation 留在 Command 内，既不走 System tick 也未用 CombatBridge 的副作用账本 + input log 审计轨迹。

## 决策

### 1. 统一战斗走 CombatBridge tick 驱动（废弃命令内同步循环）

kill/fight 命令**只建立敌对关系**（对齐 LPC `kill_ob`/`fight_ob`），战斗派生变更由 `CombatBridge.tick` 驱动（对齐 LPC heart_beat）：

- **kill 命令**：建立 `CombatState`（双向 `enemy_ids` + `is_fighting=True`，对齐 LPC `enemy` 数组 + `set_heart_beat(1)`），返回"发起攻击"消息，**不再命令内循环**。
- **fight 命令**：同 kill（建立 CombatState）+ 点到为止标记（qi 比例判赢，对齐 LPC fight 模式 `do_attack` 后 `remove_enemy`）。
- **战斗推进**：复用 `_auto_advance` 模式（cli.py:165），检测 `is_fighting` 循环 `engine.tick()`（CombatBridge 驱动每回合攻击）直到战斗结束。CLI auto_advance 保持即时体验（玩家无需手动 wait），但语义上是 tick 推进（对齐 LPC）。
- **死亡/战斗结束判定**：每 tick 后检查（NPC 死移除/玩家死走死亡轮回/fight qi 比例判赢/flee 中断），战斗结束清 CombatState（`enemy_ids=[]` + `is_fighting=False`）。判定逻辑从 kill 命令内移到 auto_advance 推进循环。
- **可中断性**：flee 命令清 `enemy_ids` 中断战斗（对齐 LPC `remove_enemy`），玩家可在 tick 间逃跑。本轮基础 flee，完整 flee/surrender 语义后置。

### 2. 确定性重放启用（ADR-0023 落地）

战斗走 CombatBridge 后，[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) 的 combat 确定性重放**实际生效**：

- `CombatBridge.update` 按 `enemy_ids` 构建 `input_log`（[engine.py:177](../../engine/src/xkx/runtime/engine.py)），战斗输入进 input log。
- `replay(snapshot, seed, input_log)` 可重放整场战斗（同 snapshot + seed + input_log -> 同输出）。
- kill/fight 命令建立的敌对关系 + auto_advance 推进的 tick 序列构成可重放的战斗轨迹。
- 战斗 mutation 经 CombatBridge 的 Effect 账本（dissent 7 审计轨迹）+ input log，不再留在 Command 内。

> 命令内 `next_seed()` 同步循环的确定性（同 seed 序列同输出）保留为"命令序列重放"语义，但战斗本身的重放走 CombatBridge input log（更细粒度，ADR-0023 范围）。

### 3. is_fighting 正确设置（战斗中检查生效）

kill/fight 建立 `CombatState.is_fighting=True` 后，commands.py 中"战斗中不能练功/打坐/吐纳"等检查（第 997/1063/1108/1153 行）**正确触发**。战斗结束清 `is_fighting=False` 恢复。这是 greenfield 战斗状态机的正确化（当前 is_fighting 永不 True 是 bug）。

### 4. auto_fight 接入（B-2，可选后续轮）

NPC 主动攻击（[auto_fight.py](../../engine/src/xkx/runtime/auto_fight.py)）当前管线实现 + 有测试但**未接入运行时**（on_start_fight 默认 no-op，无题材数据注册 handler，无事件触发调用）。本轮 B-1 聚焦玩家发起的战斗（kill/fight）路径统一；B-2 auto_fight 接入（on_start_fight handler 实现 + 进入房间事件触发 + NPC aggressive/hatred/vendetta 标记）作为可选后续轮，触发条件：demo/全量迁移需要 NPC 主动攻击威胁感时。

## 不做（本轮范围边界）

- **不做多对手 select_opponent**：LPC `enemy` 数组（MAX_OPPONENT=4）+ `select_opponent` 随机选敌；本轮 kill/fight 单对手（一对 enemy_ids），多对手后置。
- **不做主动性 guard 判定**：LPC `fight()` 的 `random(victim_dex*3) < me_str*2` 观望判定（[combatd.c:818](../../adm/daemons/combatd.c)）；本轮每回合互攻（attacker 攻 victim + victim 反击），guard 观望后置。
- **不做完整 flee/surrender 语义**：本轮基础 flee（清 enemy_ids 中断），LPC 完整逃跑/投降机制后置。
- **不做 B-2 auto_fight 接入**（本 ADR 决策 4）：可选后续轮。
- **不改 combat 确定性边界**（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) combat-only 范围不变）：本轮是启用其重放，不扩展范围。
- **不改 resolve_attack 七步管线**：本轮只改战斗驱动方式（命令内循环 -> tick 驱动），不改 resolve_attack 纯函数。

## 产出位置

- [runtime/commands.py](../../engine/src/xkx/runtime/commands.py)：kill/fight 命令重写（建立 CombatState，不再命令内循环）+ flee 命令（清 enemy_ids）+ 战斗中检查生效验证。
- [cli.py](../../engine/src/xkx/cli.py)：`_auto_advance` 扩展战斗推进（检测 is_fighting，循环 tick + 战斗结束判定 + 死亡处理）。
- [runtime/engine.py](../../engine/src/xkx/runtime/engine.py)：`CombatBridge.update` 验证启用（可能补战斗结束判定 hook，若 auto_advance 侧无法判定）。
- [tests/test_s5_playtest.py](../../engine/tests/test_s5_playtest.py) / [tests/test_callout_translation.py](../../engine/tests/test_callout_translation.py)：kill/fight 测试改 tick 推进模式 + 新增确定性重放测试（同 snapshot+seed+input_log -> 同输出）。
- 本 ADR（决策）+ [PROGRESS.md](../../PROGRESS.md) 更新。

## 关联

- [CLAUDE.md](../../CLAUDE.md) 关键架构不变量：tick=1s 驱动 + System tick 派生变更不经 Command--本 ADR 决策 1 的依据。
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 7（派生变更审计覆盖缺口）+ Q3 裁决（Command 仅外部意图，System.update 覆盖派生变更）--本 ADR 决策 1/2 的依据。
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 2.4 Combat（Combat 迁移专项）。
- [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md)（combat 确定性边界，本 ADR 决策 2 启用其重放，范围不变）。
- [ADR-0027](ADR-0027-combat-callout-formation-golden-trace.md)（auto_fight + call_out 翻译，本 ADR B-2 的基础）。
- [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)（System 基类，CombatBridge 的基类）。
- [adm/daemons/combatd.c](../../adm/daemons/combatd.c) / [feature/attack.c](../../feature/attack.c) / [cmds/std/kill.c](../../cmds/std/kill.c)（LPC 战斗机制规格源，本 ADR 保真度基准）。
