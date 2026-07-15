# ADR-0043：drink 命令 + 厨房初始物品 + 持茶挡路

- 状态：已通过（2026-07-14）
- 日期：2026-07-14
- 阶段：M3 收官后技术债补缺口第 3 轮（C4 可玩性收尾）
- 关联：[ADR-0040](ADR-0040-layer1-ask-clearflag-spawnitems.md)（C4 xlama2 闭环，本 ADR 实施其后置项）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 3（层1 原语蠕变护栏）+ Q2（层1 唯一规则表示层）/ [d/xueshan/obj/buttertea.c](../../d/xueshan/obj/buttertea.c) do_drink / [d/xueshan/chufang.c](../../d/xueshan/chufang.c) valid_leave + set("objects")

## 背景

[ADR-0040](ADR-0040-layer1-ask-clearflag-spawnitems.md) 落地 xlama2 交互闭环（ask 设茶 + give 清茶+生茶），明确三项残留后置：buttertea drink 效果（无 drink 命令）/ 厨房 valid_leave 持茶挡路 / 厨房初始 buttertea。本 ADR 实施后置项，形成完整 take-drink-leave 闭环。

**LPC 规格源**（[d/xueshan/obj/buttertea.c](../../d/xueshan/obj/buttertea.c) + [d/xueshan/chufang.c](../../d/xueshan/chufang.c)）：

- `do_drink`（buttertea.c:33-96）：物品 `init()` 里 `add_action("do_drink","drink")` 自注册的局部命令。效果：`add("water",50)` + `add("food",30)` + `jing=min(eff_jing, jing+5)`；remaining=3 多次饮用，=0 时 `destruct`；fighting 时 `start_busy(2)`。
- `valid_leave`（chufang.c:28-36）：`if (dir=="west" && present("tea", me))` -> `notify_fail("别着急，喝完茶再走 !")` 挡路。
- `set("objects", buttertea:3)`（chufang.c:18-21）：厨房初始 3 杯酥油茶。

**LPC 与 greenfield 差异**：

- LPC drink 是物品 `add_action` 自注册的局部命令；greenfield 命令管线是全局 `COMMAND_REGISTRY`，无"物品自注册"机制。统一为全局 drink 命令 + ItemDef consumable 字段（比每物品特化更收敛）。
- LPC `_resolve_item_id` 等价（`present`）支持别名；greenfield `_resolve_item_id` 只匹配精确 id/中文名（与 `_find_npc_in_room` 支持别名不对称），drink tea 解析有 gap。
- LPC 路径 bug：xlama2.c accept_object 把 buttertea move 到 `/d/qilian/chufang`（不存在），greenfield 不照搬（ADR-0040 已用 `xueshan/chufang`）。

## 决策

### 1. 通用 drink 命令（ItemDef consumable 字段）

`ItemDef` 加消耗品字段 `drink_supply`/`food_supply`/`jing_recover`（默认 0 = 不可饮用）。`drink` 命令：resolve 物品 -> 查 consumable（全 0 拒"这东西不能喝"）-> `is_busy` 拒 -> 恢复 `water/food/jing`（jing clamp `eff_jing`）-> 从 Inventory 移除（set 语义，喝一次消失）。

通用而非 buttertea 特化：LPC 全库 20+ drink 物品共享 `do_drink` 模式，greenfield 全局命令 + ItemDef 字段是比"每物品特化"更收敛的抽象，与 take/drop/give 命令模式一致（resolve -> apply effect -> remove）。

### 2. item_registry 存完整 item dict

`item_registry` 从 `{id: name}` 扩为 `{id: dict}`（含 name/aliases/consumable），供 `_item_name`（取 name）/`_resolve_item_id`（匹配 name+aliases）/`drink`（查 consumable）共用。`_item_name` 向后兼容旧 str 结构。

### 3. _resolve_item_id 扩 aliases

`_resolve_item_id` 扩展匹配物品 aliases（`item_registry[iid].aliases`），对齐 `_find_npc_in_room` 的别名解析，修复 drink/take/give 别名解析 gap（drink tea -> buttertea）。惠及 take/give（需回归，已验证不回归）。

### 4. 厨房初始 buttertea（set 语义 1 杯）

`rooms.yaml` chufang 加 `items: [buttertea]`（1 杯，set 语义简化，LPC 3 杯数量后置需扩 RoomComp.items 为 dict）。

### 5. 厨房 valid_leave 持茶挡路（零代码，纯规则）

`rules.yaml` 加 `xueshan_chufang_tea_block` 规则：`event=valid_leave` + `dir=west` + `condition=has_item(buttertea)` + `action=deny`。layer1 `has_item` 谓词已支持（ADR-0005），零代码。LPC 按 alias "tea" 匹配，greenfield 按 item_id "buttertea" 匹配（buttertea 唯一，语义等价）。

## 不做（范围边界）

- **remaining 多次饮用**：set 语义喝一次即消失（对齐 ADR-0040 set 语义简化）。LPC 一杯喝 3 次后置（需扩 Inventory.items 为 dict[str,int]）。
- **water 上限检查**：Vitals 无 `max_water` 字段，LPC `max_water_capacity()` "喝太多"拒省略。
- **fighting start_busy(2)**：drink 在战斗中 start_busy 后置（busy EffectComp 接入）。
- **value 清零**：greenfield 物品无 value 字段，不适用。
- **数量 3**：RoomComp.items 是 set，初始 1 杯。dict 化后置。
- **不加新层1 谓词**（dissent 3 护栏）：valid_leave 持茶挡路复用已有 `has_item` 谓词，零代码扩充。
- **不修改 LPC 源**（只读规格）。

## 产出位置

- [dsl/layer0.py](../../engine/src/xkx/dsl/layer0.py)：`ItemDef.drink_supply`/`food_supply`/`jing_recover`
- [runtime/commands.py](../../engine/src/xkx/runtime/commands.py)：`drink` 命令 + `_adapter_drink` + COMMAND_REGISTRY + `_item_name`/`_resolve_item_id` 适配 dict + 扩 aliases + `item_registry` 类型注解
- [cli.py](../../engine/src/xkx/cli.py)：`item_registry` 存完整 dict
- [scenes/xueshan_micro/items.yaml](../../engine/scenes/xueshan_micro/items.yaml)：buttertea consumable 字段
- [scenes/xueshan_micro/rooms.yaml](../../engine/scenes/xueshan_micro/rooms.yaml)：chufang 初始 `items: [buttertea]`
- [scenes/xueshan_micro/rules.yaml](../../engine/scenes/xueshan_micro/rules.yaml)：`xueshan_chufang_tea_block` valid_leave 规则
- [tests/test_xueshan_e2e.py](../../engine/tests/test_xueshan_e2e.py)：+4 测试（drink 恢复+消耗 / 不可喝拒 / 持茶挡路闭环 / 别名解析）+ _game helper item_registry 改完整 dict
- [tests/test_m3_playtest.py](../../engine/tests/test_m3_playtest.py) + [tests/test_s5_playtest.py](../../engine/tests/test_s5_playtest.py)：_game helper item_registry 改完整 dict（一致性）

## 关联

- [ADR-0040](ADR-0040-layer1-ask-clearflag-spawnitems.md)（C4 xlama2 闭环，本 ADR 实施其后置的 drink/初始物品/持茶挡路）
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 3（层1 原语蠕变护栏--持茶挡路复用 has_item 零代码，不扩谓词）
- [d/xueshan/obj/buttertea.c](../../d/xueshan/obj/buttertea.c) do_drink / [d/xueshan/chufang.c](../../d/xueshan/chufang.c) valid_leave + set("objects")（LPC 规格源，保真度基准）
