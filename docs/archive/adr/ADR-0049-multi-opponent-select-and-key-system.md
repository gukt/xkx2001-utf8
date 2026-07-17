# ADR-0049：多对手 select_opponent + 钥匙系统（B-2/C5 残留后置收尾）

- 状态：已通过（2026-07-15）
- 日期：2026-07-15
- 阶段：M3 收官后技术债补缺口第 4 轮（B-2/C5 残留后置收尾）
- 关联：[ADR-0045](ADR-0045-hatred-vendetta-triggers.md)（hatred+vendetta，多对手后置项本 ADR 实施）/ [ADR-0044](ADR-0044-door-open-close-locked.md)（门 open/close+LOCKED，钥匙系统后置项本 ADR 实施）/ [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md)（combat 确定性边界，select 纳入 seed 链）/ [ADR-0039](ADR-0039-combat-path-unification.md)（战斗路径统一）/ [feature/attack.c](../../feature/attack.c) select_opponent + MAX_OPPONENT / [d/zhongnan/donglang.c](../../d/zhongnan/donglang.c) do_unlock 钥匙门 / [05](../xkx-arch/05-第三轮专家对抗复审报告.md) Q3

## 背景

[ADR-0045](ADR-0045-hatred-vendetta-triggers.md) 后置多对手 select_opponent（风险最高，确定性 seed + 全战斗路径回归）；[ADR-0044](ADR-0044-door-open-close-locked.md) 后置钥匙系统（locked 字段就位，钥匙匹配开锁后置）。本 ADR 实施这两项残留后置，berserk/动态 exit/SMASHED 仍后置（见 §不做）。

**调研发现**（三路并行代码调研）：

- **多对手 select_opponent 实为修正已有语义 bug**：[engine.py](../../engine/src/xkx/runtime/engine.py) `CombatBridge.update` 原遍历每个 attacker 的**所有** `enemy_ids` 构建 input_log（每 tick 打所有敌人），而 [commands.py](../../engine/src/xkx/runtime/commands.py) `advance_combat` 只用 `enemy_ids[0]` 做结束判定--伤害打到所有敌人，但只有第一个敌人死才触发战斗结束。LPC [attack.c:79-87](../../feature/attack.c) `select_opponent` 是每 heart_beat 选 1 个对手打（`random(MAX_OPPONENT)`，单敌人确定性 fallback `enemy[0]`）。推进 select_opponent 同时修正这个不一致。
- **钥匙系统低成本**：`locked` 字段 + `Inventory.items`（id 集合）+ `_resolve_item_id` 三路匹配已就位，只需加 `key_id` 字段 + `unlock` 命令，无新基础设施。LPC 钥匙门全走动态 exit + `present(key)` 检查（[donglang.c](../../d/zhongnan/donglang.c)/[houyuan.c](../../d/city/houyuan.c)），greenfield 用标准 doors + locked + key_id 表达（动态 exit 后置，见 §不做）。

## 决策

### 1. 多对手 select_opponent（CombatBridge select + combat seed）

`CombatBridge.update` input_log 构建从"遍历所有 enemy_ids"改为"每 attacker 用 `DeterministicRNG(seed)` 调 select_opponent 选 1 个"（对齐 LPC `attack.c:79-87`）：

```python
which = select_rng.rand(MAX_OPPONENT)  # LPC random(MAX_OPPONENT=4)
victim_id = enemy_ids[which] if which < len(enemy_ids) else enemy_ids[0]
```

- `MAX_OPPONENT = 4`（[engine.py](../../engine/src/xkx/runtime/engine.py) 常量，对齐 `attack.c:12`）。
- `seed = seed_base + tick`（combat seed），select 的 random 纳入 combat seed 链（同 seed + 同 enemy_ids -> 同 select -> 同 input_log）。replay 接收已 select 的 input_log，不重 select。
- 单敌人时 `which >= 1` 必 fallback `enemy[0]`，行为不变（确定性，对齐 LPC `sizeof(enemy)=1`）。

### 2. combat_selects 跨层传递（combat 决策 -> advance_combat）

`CombatBridge.update` 把本回合 select 结果写 `world.combat_selects: dict[int, int]`（attacker_id -> victim_id），`advance_combat` 读取取 `target_id`（结束判定/消息用）。

- **combat 包自包含边界不破坏**（ADR-0023 决策 2）：select 决策在 `CombatBridge`（runtime 适配层），写 `world` 临时属性；combat 包（`system.py`/`replay_fn`）不反向依赖 runtime，仍接收已构建的 input_log。
- fallback `enemy_ids[0]`：engine 未接入 / pid 未被 select 的退化情况。

### 3. 钥匙系统（key_id + unlock_door + unlock 命令）

- `DoorDef`/`DoorEntry` 加 `key_id: str = ""`（关联钥匙物品 id，对照 LPC `present(key)`），`build_world` 透传。
- `unlock_door(world, room_eid, direction) -> str`（[doors.py](../../engine/src/xkx/runtime/doors.py)）：解锁（`locked=False`）+ 开门（`closed=False`）+ 同步对面 locked+closed。返回 `no_door`/`not_locked`/`ok`。钥匙匹配检查在调用方。
- `_sync_other_side` 扩展 `locked: bool | None = None` 参数（None=仅同步 closed，解锁时传 locked=False 同步对面）。
- `unlock` 命令（[commands.py](../../engine/src/xkx/runtime/commands.py)，对照 LPC `donglang.c do_unlock`）：检查 `door.key_id in inv.items`（对照 `present(key, this_player())`）-> 调 `unlock_door`。无门/未锁/无钥匙分别提示。
- 钥匙物品用现有 `ItemDef`（id+name+aliases），无新物品类型。场景 `xueshan/obj/key`（铁钥匙）+ `dadian` 北铁锁门（locked+key_id）+ `cangjing` 藏经阁 + 钥匙放 `changlang` 地面（take 拾取）。

## 不做（范围边界）

- **berserk**：LPC 规格陷阱（[combatd.c:888](../../adm/daemons/combatd.c) `!userp(me)` 早退）--本质是玩家邪派互殴机制（邪派 NPC 被看仅 flavor「瞪你一眼」无战斗，仅邪派玩家被看才触发 kill/fight）。做成"NPC 第四触发"是对 LPC 规格的有意偏离，需单独 ADR 裁决语义；且硬前置 `look <target>` 命令（当前 look 仅房间视图）+ 缺 `quest_exp` 字段。忠实 LPC 则单机 demo 几乎无法触发。继续后置。
- **动态 exit 模式**：标准 doors + locked + 钥匙 + 层1 `valid_leave` 规则已覆盖所有现有场景（[gate.c](../../d/zhongnan/gate.c) 已被 ADR-0042 重映射为标准 doors；钥匙门用 locked+key_id 表达；NPC 在场挡路用 valid_leave）。运行时 set/delete exits 触及 go/look/序列化/双向同步 4 处 + 序列化语义分歧（LPC reload 重置 vs greenfield 持久化粘住），风险高收益低。继续后置。
- **SMASHED 位**：LPC 全仓库死代码（[ADR-0044](ADR-0044-door-open-close-locked.md) 已实证），跳过。
- **钥匙折断**（LPC `destruct(ob)`）：unlock 不消耗钥匙（行为等价容差内），`break_on_use` 后置。
- **open/close 按门名/id 匹配方向**：MVP 只接受方向，后置按需扩（[ADR-0044](ADR-0044-door-open-close-locked.md)）。
- **不修改 LPC 源**（只读规格）。

## 不变量

- **combat 确定性范围=combat-only**：select_opponent 的 `random(MAX_OPPONENT)` 用 combat seed（`seed_base+tick`），属 combat 决策（选打谁），不扩展到 heal/exp/condition 等非 combat System。replay 接收已 select 的 input_log，确定性链"同 seed + 同 enemy_ids -> 同 input_log -> 同 results"成立（ADR-0045 §不变量预留）。
- **Command 仅外部意图**：select_opponent 在 `CombatBridge` System tick 内（战斗派生变更经 System），不经 Command；advance_combat 只读 select 结果做结束判定。
- **combat 包自包含**（ADR-0023 决策 2）：select 在 runtime 适配层（CombatBridge），combat 包不反向依赖 runtime。
- **序列化**（ADR-0022）：`key_id`（str）可序列化；`combat_selects` 是单回合临时状态（每 bridge.update 覆盖），不进存档。

## 产出位置

- [runtime/engine.py](../../engine/src/xkx/runtime/engine.py)：`MAX_OPPONENT` 常量 + `CombatBridge.update` select_opponent + `world.combat_selects`
- [runtime/commands.py](../../engine/src/xkx/runtime/commands.py)：`advance_combat` 读 combat_selects + `unlock` 命令 + `_adapter_unlock` + COMMAND_REGISTRY
- [runtime/doors.py](../../engine/src/xkx/runtime/doors.py)：`unlock_door` + `_sync_other_side` 扩展 locked
- [runtime/components.py](../../engine/src/xkx/runtime/components.py)：`DoorEntry.key_id`
- [dsl/layer0.py](../../engine/src/xkx/dsl/layer0.py)：`DoorDef.key_id`
- [runtime/world.py](../../engine/src/xkx/runtime/world.py)：`build_world` 透传 `key_id`
- [scenes/xueshan_micro/items.yaml](../../engine/scenes/xueshan_micro/items.yaml)：`xueshan/obj/key`（铁钥匙）
- [scenes/xueshan_micro/rooms.yaml](../../engine/scenes/xueshan_micro/rooms.yaml)：`dadian` 北铁锁门（locked+key_id）+ `cangjing` 藏经阁 + `changlang` 钥匙
- [tests/test_engine.py](../../engine/tests/test_engine.py)：+3 测试（select 只打 1 个 / 多对手确定性 / 单敌人 fallback）
- [tests/test_xueshan_e2e.py](../../engine/tests/test_xueshan_e2e.py)：+1 测试（advance_combat 多对手未选中者满血）
- [tests/test_doors.py](../../engine/tests/test_doors.py)：+4 测试（locked 挡路 / 无钥匙拒 / 有钥匙开+双向同步 / 未锁提示）+ `_game` 升级 item_registry

## 关联

- [ADR-0045](ADR-0045-hatred-vendetta-triggers.md)（hatred+vendetta，多对手后置项本 ADR 收尾）
- [ADR-0044](ADR-0044-door-open-close-locked.md)（门 open/close+LOCKED，钥匙系统后置项本 ADR 收尾）
- [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md)（combat 确定性边界，select 纳入 seed 链 + 自包含边界）
- [feature/attack.c](../../feature/attack.c) select_opponent + MAX_OPPONENT / [adm/daemons/combatd.c](../../adm/daemons/combatd.c) start_berserk !userp 早退 / [d/zhongnan/donglang.c](../../d/zhongnan/donglang.c) do_unlock 钥匙门（LPC 规格源）
