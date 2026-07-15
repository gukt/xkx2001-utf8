# ADR-0044：门扩展（open/close 命令 + LOCKED 位）

- 状态：已通过（2026-07-14）
- 日期：2026-07-14
- 阶段：M3 收官后技术债补缺口第 3 轮（C5 门可玩性）
- 关联：[ADR-0042](ADR-0042-door-state-machine.md)（门状态机基础，本 ADR 实施其后置项）/ [cmds/std/open.c](../../cmds/std/open.c) + [cmds/std/close.c](../../cmds/std/close.c) / [inherit/room/room.c](../../inherit/room/room.c) open_door/close_door / [include/room.h](../../include/room.h) 位掩码常量 / [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §三 Q2（层1 唯一规则表示层）

## 背景

[ADR-0042](ADR-0042-door-state-machine.md) 落地标准 doors 状态模式 + knock 开门 + call_out 定时关，明确 open/close 命令 + LOCKED/SMASHED 位后置。本 ADR 实施后置项。

**LPC 规格源调查发现**：

- **DOOR_LOCKED / DOOR_SMASHED 是死代码**：[include/room.h:5-7](../../include/room.h) 定义位掩码常量（CLOSED=1/LOCKED=2/SMASHED=4），但全仓库 `d/`/`cmds/`/`inherit/`/`feature/` **无任何一处 set 或 check** LOCKED/SMASHED。所有 30+ 个 `create_door` 调用只用 `DOOR_CLOSED`。`room.c` 的 `open_door`/`close_door`/`valid_leave` 也只操作 CLOSED 位。无 smash 命令、无攻击门逻辑、无标准 lock/unlock 命令。
- **标准 open/close 无定时关**：[cmds/std/open.c](../../cmds/std/open.c) + [close.c](../../cmds/std/close.c) 调 `room.open_door/close_door` 改 status，**无 call_out 定时关**。定时关只属于动态 exit 模式（[gate.c](../../d/zhongnan/gate.c) 等，knock 开门 + call_out 关门）。ADR-0042 的 knock 融合了 gate.c 的定时关语义。
- **LPC 钥匙门全走动态 exit + 自定义 add_action**（[donglang.c](../../d/zhongnan/donglang.c) / [houyuan.c](../../d/city/houyuan.c)）：`present(key)` 检查 + `set("exits/...")` 创建 exit，不走 doors status。无标准 lock 命令。

## 决策

### 1. open/close 命令（标准模式，无定时关）

新增 `open`/`close` 全局命令（COMMAND_REGISTRY），对照 LPC `cmds/std/open.c`+`close.c`。`open` 调 `open_door` 开门，`close` 调 `close_door` 关门。

**保真点**：标准 open **无定时关**（对齐 LPC open.c），区别于 knock（gate.c 模式，独有 call_out 定时关）。两者开门副作用相同（`closed=False` + 同步对面），差异在 timer：open 不 schedule，knock schedule `door_close` EffectComp。这是两种 LPC 门模式的语义差异，greenfield 保留。

### 2. open_door / close_door 公开函数

[doors.py](../../engine/src/xkx/runtime/doors.py) 抽出公开函数（对照 LPC `room.c` open_door/close_door 方法）：

- `open_door(world, room_eid, direction) -> str`：开门副作用（`closed=False` + `_sync_other_side`），**不 schedule 定时关**。返回状态 `no_door`/`already_open`/`locked`/`ok`。消息由调用方组织（对齐 LPC open_door 做副作用返回 1/0，message_vision 在命令层）。
- `close_door(world, room_eid, direction) -> str`：关门副作用（`closed=True` + 同步 + `_remove_door_close_effect` 取消未到期定时关）。返回状态 `no_door`/`already_closed`/`ok`。
- `knock_door` 重构为调 `open_door` 开门（复用开门副作用 + locked 检查），成功后 remove 旧 + schedule 新 `door_close` EffectComp（保留 knock 独有定时关）。

### 3. LOCKED 位（独立 bool，非位掩码）

`DoorEntry` 加 `locked: bool = False`（[components.py](../../engine/src/xkx/runtime/components.py)），`DoorDef` 加 `locked: bool = False`（[layer0.py](../../engine/src/xkx/dsl/layer0.py)），`build_world` 透传（[world.py](../../engine/src/xkx/runtime/world.py)）。

**独立 bool 而非 LPC 位掩码 int**：当前全链路用 `closed: bool`，改位掩码 int 要改所有访问点，破坏面大。bool 可读性好 + 类型安全 + 序列化简单（ADR-0022）。spec 层 `DoorStatus` StrEnum 保留作文档，runtime 不对齐位掩码。

`open`/`knock` 命令检查 `door.locked` -> 提示"锁着，需要钥匙"。`go` 挡路：locked 门提示"锁着，需要钥匙"，非 locked 提示"关着，也许敲一敲(knock)或打开(open)会开"。

### 4. SMASHED 跳过（LPC 死代码）

SMASHED 位不做。LPC 全仓库无任何触发机制（无 smash 命令、无攻击门逻辑），做了是凭空发明规格，违反"LPC 是规格源"原则。

## 不做（范围边界）

- **SMASHED 位**（LPC 死代码）：见决策 4。
- **钥匙系统**：`locked` 字段就位，但钥匙匹配开锁后置（需场景 + 钥匙物品 + unlock 逻辑）。当前 locked 门只能提示"需要钥匙"，无法开锁。
- **动态 exit 模式**：标准 doors + open/close 已覆盖绝大多数场景。动态 exit（运行时 set/delete exits，关门时 exit 不存在）涉及 go/look/寻路/序列化/双向同步，风险高，后置。gate.c 的 family/incense 检查用 rules 层 valid_leave 表达即可。
- **open/close 按门名/id 匹配方向**：LPC open.c 支持按门名/id 解析方向，greenfield MVP 只接受方向（doors 无 id 字段），后置按需扩。
- **不修改 LPC 源**（只读规格）。

## 产出位置

- [runtime/doors.py](../../engine/src/xkx/runtime/doors.py)：`open_door` + `close_door` 公开函数 + `knock_door` 重构复用 `open_door`
- [runtime/commands.py](../../engine/src/xkx/runtime/commands.py)：`open`/`close` 命令 + `_adapter_open`/`_adapter_close` + COMMAND_REGISTRY + `go` 挡路提示（locked/非 locked 分支）
- [runtime/components.py](../../engine/src/xkx/runtime/components.py)：`DoorEntry.locked`
- [dsl/layer0.py](../../engine/src/xkx/dsl/layer0.py)：`DoorDef.locked`
- [runtime/world.py](../../engine/src/xkx/runtime/world.py)：`build_world` 透传 `locked`
- [tests/test_doors.py](../../engine/tests/test_doors.py)：+6 测试（open 开门 / close 关门 / open 无 timer / close 取消 knock timer / open 已开 / locked 挡路）

## 关联

- [ADR-0042](ADR-0042-door-state-machine.md)（门状态机基础，本 ADR 实施其后置的 open/close + LOCKED）
- [cmds/std/open.c](../../cmds/std/open.c) + [cmds/std/close.c](../../cmds/std/close.c) + [inherit/room/room.c](../../inherit/room/room.c) open_door/close_door（LPC 规格源，保真度基准）
- [include/room.h](../../include/room.h)（位掩码常量，LOCKED/SMASHED 死代码实证）
