# ADR-0045：hatred + vendetta 触发（auto_fight 三触发之余收尾）

- 状态：已通过（2026-07-14）
- 日期：2026-07-14
- 阶段：M3 收官后技术债补缺口第 3 轮（B-2 架构一致性）
- 关联：[ADR-0041](ADR-0041-auto-fight-aggressive-wiring.md)（auto_fight aggressive 接入，本 ADR 补 hatred/vendetta）/ [ADR-0039](ADR-0039-combat-path-unification.md)（战斗路径统一）/ [feature/attack.c](../../feature/attack.c) init() + killer 数组 / [adm/daemons/combatd.c](../../adm/daemons/combatd.c) start_hatred/start_vendetta + killer_reward + death_penalty / [05](../xkx-arch/05-第三轮专家对抗复审报告.md) Q3（Command 仅外部意图，System tick 派生变更）

## 背景

[ADR-0041](ADR-0041-auto-fight-aggressive-wiring.md) 落地 MVP aggressive 触发（room-enter + handler 注册 + initiate_combat），明确 hatred/vendetta/berserk/多对手后置。本 ADR 实施 hatred + vendetta（berserk/多对手仍后置）。

**LPC 规格源调查发现**（与任务描述直觉有两处重要修正）：

- **hatred**（[feature/attack.c](../../feature/attack.c)）：`killer` 数组 = NPC"要杀到死的目标 id 列表"。`kill_ob` 写 killer（`fight_ob` 不写）。`init()` 优先级最高：`is_killing(player.id)` -> hatred。`remove_enemy` 检查 `is_killing` 拒移除 killer 目标（玩家逃离后记忆保留）。`die()` -> `remove_all_killer` 清 killer。**"跨房间追杀"实相**是 `pursuer` + `random_move` 在 heart_beat 随机移动寻敌重遇触发（NPC AI 范畴，后置）；greenfield 做"重入房间重触"即可。
- **vendetta 是标记式追杀，非"门派世仇"**（[combatd.c:1091](../../adm/daemons/combatd.c) killer_reward + [attack.c:250](../../feature/attack.c) init）：杀有 `vendetta_mark` 的 NPC -> 击杀者获 `vendetta/<mark>` 标记；带标记者遇同类 `vendetta_mark` NPC -> vendetta 触发。`death_penalty`（combatd.c:1017）玩家死亡清所有 vendetta 标记。实例：捕头 `vendetta_mark="authority"`，杀捕头获标记，遇其他捕头追杀。

## 决策

### 1. hatred（killer_ids，重入房间重触）

`CombatState` 加 `killer_ids: list[int]`（对齐 LPC killer 数组）。`initiate_combat(to_death=True)` **双向**写 killer_ids（attacker + target 互加，对齐 `kill_ob` 写 this_object 的 killer）；`to_death=False`（fight 模式）不写（对齐 `fight_ob` 不写 killer）。

`_trigger_room_enter_fight` 扩展三触发优先级（对齐 LPC `init()` if-else）：hatred（`player_id in npc.killer_ids`）> vendetta > aggressive。NPC 死亡实体移除 Position，killer_ids 随实体消失（对齐 LPC `die()` 清 killer）。

### 2. vendetta（标记式追杀）

`NpcDef`/`NpcBehavior` 加 `vendetta_mark: str`。玩家 vendetta 标记存 `Marks.flags`（如 `"vendetta:guard"`），复用 set[str] 无需新组件。

- `_handle_npc_death` 扩展：NPC 有 `vendetta_mark` -> 给 killer 设 `vendetta:<mark>` flag（对齐 `killer_reward` 的 `add("vendetta/"+vmark,1)`）。
- `_trigger_room_enter_fight` vendetta 分支：NPC 有 `vendetta_mark` 且 player 有 `vendetta:<mark>` flag -> VENDETTA。
- `_handle_player_death` 清所有 `vendetta:*` flags（对齐 `death_penalty` 的 `delete("vendetta")`）。

### 3. 三触发优先级 hatred > vendetta > aggressive

抽出 `_decide_room_enter_fight(world, npc_eid, player_id, behavior, player_flags) -> FightType | None` 纯函数做优先级判定（elif 链，对齐 LPC `init()` if-else）。`_trigger_room_enter_fight` 遍历房间**所有** NPC（之前只遍历 aggressive），每个 NPC 调 `_decide_room_enter_fight` 决定触发类型。每个 NPC 只触发其一。

### 4. handler 实质相同（都 to_death）

`hatred_start_fight_handler`/`vendetta_start_fight_handler` 与 `aggressive_start_fight_handler` 实质相同（都 `initiate_combat(to_death=True)`），区分仅为 FightType 语义标签（对齐 LPC `start_hatred`/`start_vendetta`/`start_aggressive` 都调 `kill_ob`）。建敌对关系后持续攻击由 CombatBridge tick 驱动（ADR-0039）。

## 不做（范围边界）

- **berserk**：shen 驱动的 look 触发（非 attitude 值），依赖 `look <target>` 命令先落地，后置。
- **多对手 select_opponent**：`advance_combat` 仍硬编码 `enemy_ids[0]`。hatred/vendetta 触发多敌对关系时只打首个（确定性 seed + 全战斗路径回归，风险最高，单独后置）。
- **跨房间定向追杀**：pursuer + random_move 属 NPC AI 范畴（M3+ 后置），greenfield 只做"重入房间重触"。
- **不修改 LPC 源**（只读规格）。

## 不变量

- **Command 仅外部意图**：hatred/vendetta 触发在 `go` Command 内（玩家意图驱动的移动事件，对齐 LPC `init()` 进入房间），非 System tick；建敌对关系后持续攻击由 CombatBridge tick 驱动（System，ADR-0039）。
- **combat 确定性范围=combat-only**：hatred/vendetta 触发不涉及 random（触发是确定性判定 `player_id in killer_ids` / `flag in player_flags`），不涉及 combat seed（多对手的 random select 才涉及，后置）。
- **序列化**（ADR-0022）：`killer_ids`（list[int]）/`vendetta_mark`（str）/vendetta flag（Marks.flags set[str]）全基本类型，可序列化。

## 产出位置

- [runtime/components.py](../../engine/src/xkx/runtime/components.py)：`CombatState.killer_ids` + `NpcBehavior.vendetta_mark`
- [dsl/layer0.py](../../engine/src/xkx/dsl/layer0.py)：`NpcDef.vendetta_mark`
- [runtime/world.py](../../engine/src/xkx/runtime/world.py)：`_spawn_npc` 透传 `vendetta_mark`
- [runtime/auto_fight.py](../../engine/src/xkx/runtime/auto_fight.py)：`initiate_combat` 双向写 killer_ids + `hatred_start_fight_handler` + `vendetta_start_fight_handler`
- [runtime/commands.py](../../engine/src/xkx/runtime/commands.py)：`_trigger_room_enter_fight` 三触发 + `_decide_room_enter_fight` + `_handle_npc_death` 写 vendetta + `_handle_player_death` 清 vendetta
- [cli.py](../../engine/src/xkx/cli.py)：`load_game` 注册 HATRED + VENDETTA handler
- [scenes/xueshan_micro/npcs.yaml](../../engine/scenes/xueshan_micro/npcs.yaml) + [rooms.yaml](../../engine/scenes/xueshan_micro/rooms.yaml)：`xueshan/npc/guard`（vendetta_mark=guard，放 luyeyuan 验证）
- [tests/test_xueshan_e2e.py](../../engine/tests/test_xueshan_e2e.py)：+3 测试（hatred 重触 / vendetta 标记写入 / 三触发优先级）

## 关联

- [ADR-0041](ADR-0041-auto-fight-aggressive-wiring.md)（auto_fight aggressive 接入，本 ADR 补 hatred/vendetta，三触发之余收尾）
- [ADR-0039](ADR-0039-combat-path-unification.md)（战斗路径统一，handler 建敌对关系后由 CombatBridge 驱动）
- [feature/attack.c](../../feature/attack.c) init() + killer 数组 + is_killing / [adm/daemons/combatd.c](../../adm/daemons/combatd.c) start_hatred/start_vendetta + killer_reward + death_penalty（LPC 规格源，保真度基准）
