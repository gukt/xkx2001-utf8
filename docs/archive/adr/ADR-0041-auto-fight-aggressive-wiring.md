# ADR-0041：auto_fight 接入运行时（MVP aggressive 触发）

- 状态：已通过（2026-07-14）
- 日期：2026-07-14
- 阶段：M3 收官后技术债补缺口（B-2 架构一致性）
- 关联：[ADR-0039](ADR-0039-combat-path-unification.md) 决策 4（auto_fight 接入后置，本 ADR 实施）/ [ADR-0027](ADR-0027-combat-callout-formation-golden-trace.md)（auto_fight + call_out 翻译）/ [CLAUDE.md](../../CLAUDE.md) 关键架构不变量（Command 仅外部意图，System tick 派生变更不经 Command）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) Q3 裁决 / [feature/attack.c](../../feature/attack.c) init() + [adm/daemons/combatd.c](../../adm/daemons/combatd.c) auto_fight/start_*

## 背景

[ADR-0039](ADR-0039-combat-path-unification.md) 决策 4 预告 auto_fight 接入作为可选后续轮。auto_fight.py 管线（`auto_fight` + `start_fight` + 5 防御检查）+ 测试已就位（[test_callout_translation.py](../../engine/tests/test_callout_translation.py)），但 **on_start_fight 默认 no-op，未接入运行时**（无 handler 注册，无事件触发调用）。本 ADR 实施接入。

**LPC 规格**（[feature/attack.c](../../feature/attack.c) init() L229-258 + [combatd.c](../../adm/daemons/combatd.c) L852-962）：

- `init()` 由 MudOS 在对象进房间时自动调用（非 heart_beat）。
- 三触发优先级 hatred > vendetta > aggressive：`userp(ob) && is_killing(ob->id)` / `vendetta_mark` / `attitude==aggressive"` -> `COMBAT_D->auto_fight(this_object(), ob, type)`。
- `auto_fight`：NPC vs NPC 跳过 + `looking_for_trouble` 防重入 + `call_out("start_"+type, 0, me, ob)` 延迟 0 秒。
- `start_*`：4 防御检查 + `kill_ob` -> `set_heart_beat(1)` + enemy 数组，后续 heart_beat 驱动。

## 决策

### 1. MVP 仅 aggressive 触发

NPC `attitude=aggressive` + 玩家进房间 -> `auto_fight(npc, player, AGGRESSIVE)`。hatred（需 `killer` 数据结构，跨房间追杀仇人）/ vendetta（需门派世仇数据）/ berserk（look 命令随机触发）后置。符合 CLAUDE.md"收敛优先于完备"。

### 2. initiate_combat 公共函数（逻辑下移）

建双向敌对关系逻辑（`CombatState.enemy_ids` 互加 + `is_fighting=True`）从 `commands._start_combat` 下移到 `auto_fight.initiate_combat`。供 `aggressive_start_fight_handler`（NPC 主动攻击）+ `commands._start_combat`（玩家发起）共用，避免循环依赖（auto_fight 不导入 commands）。`commands._start_combat` 改为委托 `initiate_combat`。

### 3. aggressive_start_fight_handler

AGGRESSIVE 触发的 on_start_fight handler：调 `initiate_combat(world, me_id, obj_id, to_death=True)`（对齐 LPC `kill_ob`）。建敌对关系后，后续攻击由 CombatBridge tick 驱动（ADR-0039 已就绪）。

### 4. room-enter 触发（go 命令内）

`go()` 移动后调 `_trigger_room_enter_fight`：遍历新房间内 `attitude=aggressive` 的 NPC，调 `auto_fight(npc, player, AGGRESSIVE)`（对齐 LPC `init()` 进入房间触发）。只玩家进房间触发（对齐 LPC `this_player()` 是玩家）。若玩家进入战斗（`is_fighting`），`_run_combat` 推进（CLI 同步模式，对齐 kill 命令）。

> room-enter 触发在 go Command 内（玩家意图驱动的移动），非 System tick。NPC 主动攻击的"触发"是进入房间事件（LPC init()），建敌对关系后的"持续攻击"由 CombatBridge tick 驱动（System，ADR-0039）。触发与驱动分离，符合 Q3 裁决（Command 仅外部意图，System tick 派生变更）。

### 5. handler 注册

- `cli.load_game` 注册 `AGGRESSIVE` handler（demo 接入运行时，对齐 kill/fight 走 CombatBridge 的 demo 体验）。
- e2e 测试用 `register_start_fight_handler` + `finally pop` 隔离（对齐 [test_callout_translation.py](../../engine/tests/test_callout_translation.py) 既有模式，避免全局 `_START_FIGHT_HANDLERS` 跨测试污染）。

## 不做（范围边界）

- **hatred/vendetta/berserk 后置**：hatred 需 `killer` 数据结构（CombatState 加 `killer_ids`），vendetta 需门派世仇数据，berserk 需 look 命令扩展。MVP 只接 aggressive。
- **多对手**（ADR-0039 不做）：房间内多个 aggressive NPC 触发后，`_run_combat` 只推进 `enemy_ids[0]`，多对手 select_opponent 后置。
- **call_out(0) 延迟**：greenfield 同步执行（ADR-0027 §1.2 已决策，无 duration=0 EffectComp 语义复杂度）。
- **NPC vs NPC 不触发**：`auto_fight` 内 `!_is_player(me) && !_is_player(obj)` 跳过（对齐 LPC `!userp` 双方）。
- **不修改 LPC 源**（只读规格）。

## 产出位置

- [runtime/auto_fight.py](../../engine/src/xkx/runtime/auto_fight.py)：`initiate_combat` + `aggressive_start_fight_handler`
- [runtime/commands.py](../../engine/src/xkx/runtime/commands.py)：`_start_combat` 委托 `initiate_combat` + `go` 加 `_trigger_room_enter_fight`
- [cli.py](../../engine/src/xkx/cli.py)：`load_game` 注册 AGGRESSIVE handler
- [scenes/xueshan_micro/npcs.yaml](../../engine/scenes/xueshan_micro/npcs.yaml)：`yelang`（野狼，aggressive，放忘忧谷验证）
- [scenes/xueshan_micro/rooms.yaml](../../engine/scenes/xueshan_micro/rooms.yaml)：`xueshan/wangyou` 加 `yelang`
- [tests/test_xueshan_e2e.py](../../engine/tests/test_xueshan_e2e.py)：B-2 测试（注册 handler 触发攻击 / 未注册 no-op）

## 关联

- [ADR-0039](ADR-0039-combat-path-unification.md) 决策 4（本 ADR 实施，handler 建敌对关系后由 ADR-0039 的 CombatBridge 驱动）
- [ADR-0027](ADR-0027-combat-callout-formation-golden-trace.md) §1.2（auto_fight + call_out(0) 同步执行翻译）
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) Q3 裁决（Command 仅外部意图，System tick 派生变更--room-enter 触发在 Command，持续攻击在 System）
- [feature/attack.c](../../feature/attack.c) init() / [adm/daemons/combatd.c](../../adm/daemons/combatd.c) auto_fight + start_*（LPC 规格源，保真度基准）
