# ADR-0040：层1 规则扩充（ask 事件 + clear_flag action + spawn_items 物品生成）

- 状态：已通过（2026-07-14）
- 日期：2026-07-14
- 阶段：M3 收官后技术债补缺口（C4 可玩性）
- 关联：[CLAUDE.md](../../CLAUDE.md) 开发规范（层1 原语蠕变护栏）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 3（层1 原语蠕变风险）+ Q2 裁决（层1 是唯一规则表示层，薄求值子模块不命名"引擎"）/ [04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 2 / [ADR-0006](ADR-0006-accept-object-event.md)（accept_object + set_flag）/ [ADR-0016](ADR-0016-layer1-second-batch-predicates.md)（层1 第二批扩充）

## 背景

**C4 xlama2 交互闭环**（[d/xueshan/npc/xlama2.c](../../d/xueshan/npc/xlama2.c) 实证）需要三类层1 当前不支持的副作用：

- **ask 副作用**（ask_tea）：`ask 小喇嘛 about 酥油茶` -> `set_temp("marks/茶", 1)` 给玩家。层1 当前 ask 无规则机制（[commands.py](../../engine/src/xkx/runtime/commands.py) `ask()` 只查 `inquiry` 字典返回字符串，无副作用）。
- **clear_flag**（accept_object）：`give 小喇嘛 酥油` -> `delete_temp("marks/茶")`。层1 当前 `ACTION` 仅 `deny`/`allow`/`set_flag`（[layer1.py](../../engine/src/xkx/dsl/layer1.py) L51-53），无 `clear_flag`。
- **物品生成**（accept_object）：`give 小喇嘛 酥油` -> `new("buttertea")->move(厨房)` 生成酥油茶到房间。层1 当前 `AcceptObjectResult` 只有 `accepted`/`set_flag`/`message`（L160-166），无物品生成副作用。

**LPC 规格源**（[d/xueshan/npc/xlama2.c](../../d/xueshan/npc/xlama2.c)）：

- `inquiry` 映射 `(: ask_tea :)` 函数指针：ask 既 say 消息又 `set_temp("marks/茶",1)`（消息与副作用交织在函数内）。
- `accept_object(who, ob)`：酥油 -> `delete_temp("marks/茶")` + `new("buttertea")->move` 生成 3 个酥油茶到厨房 + return 1。

**dissent 3**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 3 条）：层1 是唯一规则表示层，原语蠕变风险需 KPI + 判定标准护栏，扩充需 ADR。本 ADR 即本次扩充的护栏记录。

## 决策

### 1. EVENT_ASK 规则（ask 副作用，方案 a：规则驱动）

新增 `EVENT_ASK = "ask"` 事件 + `evaluate_ask` 首匹配求值。`EventRule` 加 `topic` 字段（ask 事件的 topic 绑定，对照 LPC inquiry topic）。`ask()` 命中 `inquiry[topic]` 后求值 ask 规则执行 `set_flag` 副作用。

**方案选择**（a 规则驱动 vs b 扩展 inquiry 结构体）：

- 方案 a（采纳）：新增 EVENT_ASK 规则，与 accept_object 规则架构统一，复用 `Marks`/`has_flag`/`npc_id` 绑定。inquiry 保持 `dict[str, str]`（纯消息），副作用独立存 ask 规则。改动收敛（仅 layer1 + commands，不动 NpcDef/NpcBehavior）。
- 方案 b（否决）：扩展 inquiry 值为结构体（message + action + flag），改 NpcDef/NpcBehavior/layer0/layer1。改动面大，且把"消息"与"副作用"耦合进 NPC 数据（违反层1 是唯一规则表示层）。

**LPC 函数指针 vs greenfield 分离**：LPC `inquiry` 映射函数指针（消息 + 副作用交织在函数内）。greenfield 分离：`inquiry` 字典存消息文本（层0 数据），ask 规则存副作用（层1 规则）。ask 规则 `message` 非空则覆盖 inquiry 消息，否则走 inquiry 字典文本。这是"层1 管规则副作用，层0 管数据消息"分层的延续。

### 2. ACTION_CLEAR_FLAG（清除标记）

新增 `ACTION_CLEAR_FLAG = "clear_flag"` action（对照 LPC `delete_temp("marks/X")`）。`AcceptObjectResult` 加 `clear_flag` 字段，`evaluate_accept_object` 加 CLEAR_FLAG 分支（接受物品 + 清标记 + 透传 spawn_items）。`give()` 执行 `marks.flags.discard(clear_flag)`。

### 3. spawn_items 物品生成副作用

`EventRule` 加 `spawn_items: list[SpawnItem]` 字段（`SpawnItem`: item_id + room_id + count）。accept_object 规则命中后，`give()` 对每个 spawn_item 找目标房间 RoomComp，`room.items.add(item_id)`（对照 LPC `new(obj)->move(room)`）。`AcceptObjectResult` 透传 `spawn_items`。

### 4. set 语义简化（数量后置）

greenfield `RoomComp.items` 是 `set[str]`（无数量，S5a 简化）。LPC 生成 3 个 buttertea，greenfield set 语义简化为生成 1 个（有/无语义，`count>0` 即 `add` 一次）。`SpawnItem.count` 字段保留对齐 LPC 数量声明，但运行时 set 语义下不生效（数量后置，需扩 RoomComp.items 为 dict[str,int] 时再启用）。

## dissent 3 护栏（层1 原语蠕变边界）

本次扩充范围与护栏：

- **不加新谓词**：`Predicate` 叶子集不变（dissent 3 核心护栏是谓词蠕变）。本次扩充是 action 副作用扩展（clear_flag）+ 新事件（ask）+ 新副作用类型（spawn_items），均非谓词。
- **ask 事件复用现有绑定**：复用 `npc_id` 绑定 + 新增 `topic` 绑定（topic 是 ask 事件的核心维度，必要新增，对照 LPC inquiry topic）。
- **spawn_items 是副作用非谓词**：物品生成是 action 的副作用输出，不进入谓词求值，不扩展谓词集。
- **仍受"扩充需 ADR"约束**：本 ADR 记录扩充理由 + 范围 + 边界，后续层1 扩充仍需 ADR（dissent 3 护栏不放松）。

## 不做（范围边界）

- **不加新谓词**（dissent 3 护栏）：本次不扩 `Predicate` 叶子集。
- **不改 inquiry 为结构体**（方案 b 否决）：inquiry 保持 `dict[str, str]`，副作用走 ask 规则。
- **spawn_items 不支持数量**：set 语义简化，`count` 字段保留但不生效，数量后置。
- **buttertea drink 效果后置**：C4 只需物品存在 + 可 take，drink 命令后置（无 drink 命令）。
- **厨房 valid_leave（持茶挡路）后置**：LPC `present("tea",me)` 持茶挡路，greenfield 无 drink 语义意义不大，后置。
- **厨房初始 buttertea 后置**：LPC `set("objects", buttertea:3)`，C4 闭环靠 give 生成，初始物品后置。
- **不修改 LPC 源**（只读规格）。

## 产出位置

- [dsl/layer1.py](../../engine/src/xkx/dsl/layer1.py)：`EVENT_ASK` + `ACTION_CLEAR_FLAG` + `SpawnItem` model + `EventRule.topic`/`spawn_items` + `AcceptObjectResult.clear_flag`/`spawn_items` + `EvalContext.ask_topic` + `evaluate_ask` + `AskResult`
- [runtime/commands.py](../../engine/src/xkx/runtime/commands.py)：`ask()` set_flag 副作用 + `give()` clear_flag/spawn_items 副作用
- [scenes/xueshan_micro/items.yaml](../../engine/scenes/xueshan_micro/items.yaml)：`suyou`（酥油）+ `buttertea`（酥油茶）
- [scenes/xueshan_micro/rules.yaml](../../engine/scenes/xueshan_micro/rules.yaml)：xlama2 ask 规则（set_flag 茶）+ accept_object 规则（clear_flag 茶 + spawn buttertea 到厨房）
- [tests/test_xueshan_e2e.py](../../engine/tests/test_xueshan_e2e.py)：xlama2 闭环测试（ask 设茶 -> give 清茶+生茶 -> take 酥油茶）+ `_game` helper 补 item_registry 接入

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 3（层1 原语蠕变风险）+ Q2 裁决（层1 唯一规则表示层）-- 本 ADR 护栏依据
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 2（按规格实现子系统）
- [ADR-0006](ADR-0006-accept-object-event.md)（accept_object + set_flag，本 ADR 扩 clear_flag + spawn_items 的基础）
- [ADR-0016](ADR-0016-layer1-second-batch-predicates.md)（层1 第二批扩充，本 ADR 延续"扩充需 ADR"护栏）
- [d/xueshan/npc/xlama2.c](../../d/xueshan/npc/xlama2.c) / [d/xueshan/obj/suyou.c](../../d/xueshan/obj/suyou.c) / [d/xueshan/obj/buttertea.c](../../d/xueshan/obj/buttertea.c)（LPC 规格源，保真度基准）
