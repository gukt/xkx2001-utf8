---
Status: resolved
---

# 06 — B8 客店三件套（sleep + hotel + rent_paid + 睡房拦练功）

**What to build:** 新增 `sleep` 命令：默认允许在房间睡觉，除非该房间 `RoomFlags.no_sleep_room` 为真（沿用既有已声明但 inert 的字段，本票起消费之）；房间字段 `hotel: true` 表示该房需先付房钱（`rent_paid`）才能 `sleep`；新增专门 `pay` 命令（如 `pay 小二`），对 `hotel: true` 房间内的目标 NPC 付固定房钱后置位玩家侧 `rent_paid` 状态；离开客店房间（`on_leave_room` 事件）清除 `rent_paid`（不允许「付一次钱、无限次回来睡」）；睡房（本票判定：`hotel: true` 或声明了等价「睡房」语义的房间——具体判定范围见下方开放子决策的钉死方案）默认拦 `practice`，实现方式独立于 `LibraryRoom` 检查（`_cmd_practice` 新增并列分支，不共用 `LibraryRoom` 组件）。

对应 spec：`.scratch/polishing/spec.md` §B8（User Stories 21–24；Implementation Decisions「B8」）；LPC 出处 [session-qa-provenance-2026-07-23.md](../../polishing-candidate-review/session-qa-provenance-2026-07-23.md) Q6。

**已钉死的开放子决策**（架构师拍板，不留白进 `/implement`）：

1. **`sleep_room` 极性**：沿用现有 `RoomFlags.no_sleep_room`（默认允许睡，显式关闭）——不新增正向 `sleep_room` 字段。理由：避免两个极性相反字段并存造成的语义混淆；`no_sleep_room` 已声明但 inert，本票是其「转正」的天然落点。
2. **付费动词**：新增专门 `pay` 命令，不复用 `buy`/`give`——`ShopInventory` 的 `buy`/`sell` 是具体商品条目模型，不适合表达「向 NPC 付一笔固定房钱换取房间服务」这种抽象交易。
3. **睡房拦练功**：独立实现（`_cmd_practice` 新增判定分支），不复用 `LibraryRoom` 组件本体——语义上「睡房」与「藏书房」是两类不同房间标记，即使实现模式（房间存在即拦）一致，也不应共用同一组件。

- [x] `components.py`：新增 `HotelRoom`（`hotel: bool` 或等价存在性标记）与玩家侧 `RentPaid`（或等价布尔状态组件，挂在玩家实体上，表示「当前已付本次入住房钱」）。
- [x] `scene_loader.py`：房间字段 `hotel: bool`（默认 false）解析；契约新增字段 `rooms.*.hotel`。
- [x] `commands.py`：新增 `sleep` 命令——`RoomFlags.no_sleep_room` 为真则拒绝；房间 `hotel: true` 且玩家未 `rent_paid` 则要求先付钱；否则成功（具体睡觉产生的状态恢复/剧情效果范围留实现票钉死，至少给出成功提示文案）。
- [x] `commands.py`：新增 `pay` 命令（如 `pay <npc>`）——目标 NPC 须同房；房间须 `hotel: true`；扣玩家银两（固定房钱数值留实现票钉死作为可调参数）；成功后玩家侧置 `rent_paid` 真。
- [x] 事件订阅：复用既有 `on_leave_room` 事件点，玩家离开 `hotel: true` 房间时清除其 `rent_paid`（不新增 hook 协议方法）。
- [x] `commands.py::_cmd_practice`：新增判定分支——房间挂 `HotelRoom`（或达成本票选定的「睡房」判定条件）即拦 `practice`，与既有 `LibraryRoom` 检查并列但不共用组件。
- [x] `docs/creator-contract-v0.md`：补写 `rooms.*.hotel` 字段。
- [x] `engine/data/m2_mvp_scene.yaml`：`yangzhou_kedian` 房补 `hotel: true`（该场景已有 `kedian_waiter` NPC，作为 `pay` 目标）。
- [x] 新测试文件（`test_hotel.py`）：覆盖 `sleep` 允许/`no_sleep_room` 拒绝、`hotel` 未付款拒绝、`pay` 后允许 `sleep`、离房清 `rent_paid`（复入需重付）、睡房拦 `practice`。
- [x] `just test` 全绿。

## Comments

实现摘要（2026-07-23）：

- **组件**：`HotelRoom`（房间 marker，YAML `hotel: true`）；`RentPaid`（玩家运行时 marker，进存档）。
- **命令**：`sleep`（无参）；`pay <npc>`（解析层同 ask 的 NPC 实体匹配）。
- **房钱**：`HOTEL_RENT_COST = 10`（银两，命名常量）。
- **睡觉效果**：拉满 `qi_current` / `jingli_current`（`neili` 不变）；文案「你舒服地睡了一觉，精神好多了。」
- **离房清租**：`hotel.attach_hotel_rent` 订阅 `on_leave_room`，离开挂 `HotelRoom` 的房时移除 `RentPaid`。
- **拦练功**：`_cmd_practice` 在 `LibraryRoom` 分支旁新增 `HotelRoom` 分支（文案「这里是客店，还是别练功了。」）。
- **官方范本**：`yangzhou_kedian` 已标 `hotel: true`，`kedian_waiter`（店小二/小二）为 `pay` 目标。
