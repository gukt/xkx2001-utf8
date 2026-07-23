---
Status: resolved
---

# 08 — C10 液体 / eat / drink

**What to build:** 房间新增 `resource.water: bool` 字段；`fill <容器>` 命令仅在所在房间 `resource.water` 为真时成功，为容器物品灌水，否则拒绝并提示（对齐「河边/井边才能打水」）；`drink <已灌装容器>` 产生一次性数值效果（如恢复部分 `jingli_current`）并消耗该次灌装；`eat <consumable>` 产生一次性数值效果并按既有 `Consumable.uses` 语义递减/耗尽销毁。这批效果全部是命令执行当次结算内的一次性数值变化，不接入、不模拟 Effect 完整持续生命周期（ADR-0007 停机范围不变）。

对应 spec：`.scratch/polishing/spec.md` §C10（User Stories 27–31；Implementation Decisions「C10」）。

**Blocked by:** None — 可立即开始。

- [x] `components.py`：新增房间 `RoomResources`（`water: bool` 至少；`grass: bool` 视既有坐骑喂食逻辑是否已用等价字段决定是否复用/新增，若未打通则本票不打通、在 GAP 台账注明留白）；物品侧液体容器字段（如 `liquid_container: true` + 灌装后置状态 `filled_liquid: <id>`，具体命名本票钉死并在 Comments 记录）。
- [x] `scene_loader.py`：房间 `resource: { water?: bool, grass?: bool }` 解析；物品模板液体容器相关字段解析。契约新增字段：`rooms.*.resource.water`（`rooms.*.resource.grass` 视上条决定是否随附）。
- [x] `commands.py`：新增 `fill`/`drink`/`eat` 命令动词。
  - `fill <容器>`：容器须是液体容器物品且在玩家背包/手中；房间 `resource.water` 为真才成功，否则拒绝并提示；成功后容器 `filled_liquid` 置为水。
  - `drink <容器>`：容器须已灌装；产生一次性恢复效果（具体数值本票钉死作为可调参数）；消耗掉本次灌装（容器变回未灌装态）。
  - `eat <consumable>`：产生一次性数值效果；按 `Consumable.uses` 递减，耗尽销毁（复用既有耗尽销毁路径，不新建平行销毁逻辑）。
- [x] 明确不做：醉酒/持续中毒/持续 buff 等任何跨 tick 持续状态——本票所有效果为当次结算内一次性数值变化。
- [x] `docs/gap-ledger.md`：把「液体灌装 / 饮用 / eat」行从「未支持」更新为「已支持」并指向新契约字段。
- [x] 新测试文件（`test_liquid_consumable.py`）：覆盖 `resource.water` 门槏（有/无水资源房间的 `fill` 成败）、灌装→饮用效果与耗尽、`eat` 效果与 `uses` 耗尽销毁。
- [x] `just test` 全绿。

## Comments

实现摘要（2026-07-23）：

- **房间**：`RoomResources(water: bool)`；YAML `resource: { water: true }`（经 ROOM_CAPABILITIES 解析）。**不**解析/暴露 `grass`（坐骑喂食未打通，GAP 注明留白）。
- **物品**：`LiquidContainer(filled_liquid: str | None)`；YAML `liquid_container: true`（可选顶层/`映射`内 `filled_liquid` 初值）。
- **命令**：`fill <容器>` / `drink <容器>` / `eat <食物>`；解析层走背包物品匹配（别名可用）。
- **恢复常量**：`DRINK_RESTORE_JINGLI=20`；`EAT_RESTORE_QI=15`；`EAT_RESTORE_JINGLI=10`（当次 cap 到 max）。
- **耗尽销毁**：`_consume_uses`——`uses -= 1`，`<=0` 时从容器 discard + `destroy_entity`（eat 专用入口；先前无现成路径）。
- **明确不做**：醉酒/持续 Effect；`resource.grass`。
