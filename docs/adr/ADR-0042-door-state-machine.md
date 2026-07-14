# ADR-0042：门状态机（标准 doors 模式 + DoorSystem + call_out 定时关门）

- 状态：已通过（2026-07-14）
- 日期：2026-07-14
- 阶段：M3 收官后技术债补缺口（C5 可玩性）
- 关联：[spec/layer_d_world.py](../../engine/src/xkx/spec/layer_d_world.py) 门规格（DoorStatus + create/open/close/check_door，runtime 未落地）/ [ADR-0027](ADR-0027-combat-callout-formation-golden-trace.md) call_out->EffectComp 翻译惯例 / [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) EffectComp 一等公民 / [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md) EffectComp 可序列化 / [inherit/room/room.c](../../inherit/room/room.c) + [d/zhongnan/gate.c](../../d/zhongnan/gate.c) LPC 规格

## 背景

**C5 门状态机从零建**：[RoomComp](../../engine/src/xkx/runtime/components.py) 之前无门字段，无 knock/open/close 命令，无 DoorSystem。[spec/layer_d_world.py](../../engine/src/xkx/spec/layer_d_world.py) 已有门规格（DoorStatus 位掩码 + create/open/close/check_door FunctionSpec），但 runtime 未落地。

**LPC 两种门模式**（[inherit/room/room.c](../../inherit/room/room.c) + [d/zhongnan/gate.c](../../d/zhongnan/gate.c)）：

- **标准 create_door**（room.c 基类）：`doors` mapping（dir -> {name, other_side_dir, status}），status 位掩码 CLOSED/LOCKED/SMASHED，`valid_leave` 查 CLOSED 挡路，open/close 命令改 status。
- **动态 exit + knock**（gate.c 类）：knock 开门 + `call_out("close_door", 10)` 定时关 + 双向 set/delete exits + 跨房间 message 同步。

用户确认走**标准 doors 状态模式**（exits 静态 + doors 状态字段），融合 knock 开门 + call_out 定时关 + 双向同步。

## 决策

### 1. 标准 doors 状态模式（exits 静态 + doors 状态字段）

`RoomComp.doors: dict[str, DoorEntry]`（方向 -> 门），`DoorEntry`：`name`/`other_room`/`other_dir`/`closed`。exits 静态声明不变（含门方向），门状态全在 doors 字段。`go` 查 `doors[direction].closed` 挡路（对照 LPC `valid_leave` doors status 检查）。`look` 出口标注门状态（如 `west(铁门关)`，对照 LPC `item_desc look_door`）。

### 2. knock 命令开门 + 定时关

`knock` 命令调 `doors.knock_door`：开门（`closed=False` + 同步对面 `doors[other_dir]`）+ remove 旧 `door_close` EffectComp（对齐 LPC `remove_call_out` 防重入）+ schedule 新 `door_close` EffectComp 定时关（对齐 LPC `call_out("close_door", N)`）。

`door_close` EffectComp：`effect_id="door_close"`, `kind="door"`, `target_id=room_eid`, `detail=direction`（用 EffectComp.detail 字段存门方向，不改 EffectComp 结构）, `next_tick=current_tick+N`。

### 3. DoorSystem（tick 驱动定时关门）

`DoorSystem(System)` tick 驱动 `door_close` EffectComp（非均匀 tick，`next_tick<=tick` 触发），到期关门（`closed=True` + 同步对面）+ remove EffectComp。仿 [GovernanceSystem](../../engine/src/xkx/runtime/governance.py) death_stage 模式（ADR-0029），复用 ADR-0027 call_out->EffectComp 翻译惯例。

### 4. 双向同步

开门/关门时 `_sync_other_side` 设对面房间 `doors[other_dir].closed`（对照 LPC `open_door` 递归调对面 `ob->check_door`）。通过 `DoorEntry.other_room` 找对面 RoomComp（线性扫描，房间数有限）。

### 5. ConditionSystem 跳过 door_close

`door_close` 归 DoorSystem 独占遍历。[ConditionSystem](../../engine/src/xkx/runtime/conditions.py) 的 `on_tick`（求值）+ `update` apply（推进 next_tick）都跳过 `door_close`（类似跳过 `death_stage`），避免 `_default_trigger` 衰减 duration / 推进 next_tick 干扰 DoorSystem 到期判定。

### 6. 全链路（layer0 -> ir -> world -> runtime）

`layer0.DoorDef`（pydantic）-> `ir.compile_room` model_dump 透传 -> `world.build_world` 构造 `DoorEntry` -> `RoomComp.doors`。门数据声明在 rooms.yaml（`doors: {dir: {name, other_room, other_dir, closed}}`）。

## 不做（范围边界）

- **LOCKED/SMASHED 位后置**：仅开/关状态（`closed: bool`），LPC 位掩码的锁/砸后置。
- **open/close 命令后置**：C5 只做 knock 触发开门 + call_out 定时关。标准模式的 open/close 命令后置。
- **锁/钥匙系统后置**：LOCKED + 钥匙匹配后置。
- **动态 exit 模式后置**：用标准 doors 状态模式（exits 静态），动态 set/delete exits 后置。
- **knock 全局命令**：knock 是全局 verb（COMMAND_REGISTRY），非 LPC 房间级 `add_action`，但门数据驱动（doors 字段，无门方向提示）。
- **不修改 LPC 源**（只读规格）。

## 产出位置

- [runtime/components.py](../../engine/src/xkx/runtime/components.py)：`DoorEntry` + `RoomComp.doors`
- [dsl/layer0.py](../../engine/src/xkx/dsl/layer0.py)：`DoorDef` + `RoomDef.doors`
- [dsl/ir.py](../../engine/src/xkx/dsl/ir.py)：`compile_room` model_dump 自动透传（无改）
- [runtime/world.py](../../engine/src/xkx/runtime/world.py)：`build_world` 构造 `DoorEntry`
- [runtime/doors.py](../../engine/src/xkx/runtime/doors.py)（新）：`knock_door` + `DoorSystem` + `_sync_other_side` + `_close_door`
- [runtime/commands.py](../../engine/src/xkx/runtime/commands.py)：`knock` 命令 + `go` 门检查 + `look` 门状态 + `_adapter_knock` + COMMAND_REGISTRY
- [runtime/conditions.py](../../engine/src/xkx/runtime/conditions.py)：`on_tick` + `update` apply 跳过 `door_close`
- [cli.py](../../engine/src/xkx/cli.py) + e2e helper：注册 `DoorSystem`
- [scenes/xueshan_micro/rooms.yaml](../../engine/scenes/xueshan_micro/rooms.yaml)：`xueshan/mishi` 密室 + `xueshan/wangyou` north 铁门示例（对照 LPC bingyin.c create_door）
- [tests/test_doors.py](../../engine/tests/test_doors.py)（新）：6 测试（门关挡路 / knock 开门 / 双向同步 / 定时关门 / look 门状态 / 无门提示）

## 关联

- [spec/layer_d_world.py](../../engine/src/xkx/spec/layer_d_world.py) 门规格（本 ADR runtime 落地，简化为开/关状态，位掩码后置）
- [ADR-0027](ADR-0027-combat-callout-formation-golden-trace.md) call_out->EffectComp 翻译惯例（door_close EffectComp）
- [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) EffectComp 一等公民 + System 基类（DoorSystem）
- [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md) EffectComp 可序列化（door_close 存档崩溃恢复）
- [inherit/room/room.c](../../inherit/room/room.c) / [d/zhongnan/gate.c](../../d/zhongnan/gate.c) / [cmds/std/open.c](../../cmds/std/open.c)（LPC 规格源，保真度基准）
