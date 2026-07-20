# 18 - 物品能力组件化（C1）

**What to build:** 新增正交可选组件 `Stackable`（amount + base_weight/unit）、`Valuable`（value）、`Equippable`（占位 slot + apply 钩子引用）、`Consumable`（占位），按需挂载而非大而全 Item。场景 YAML 可声明这些能力；`Equippable`/`Consumable` M1 只占位不实现效果。为 M2 战斗装备/经济/消耗干净接入。

**Blocked by:** None - 可立即开始（组件定义 + loader，不依赖 B）。

**Status:** resolved（2026-07-20 re-pass：验收复核 + 补存档/声明式/take-drop 测试）

- [x] 存在 `Stackable` / `Valuable` / `Equippable` / `Consumable` 组件（后两者可为占位）
- [x] 场景 YAML 物品可声明对应字段并正确挂载
- [x] 未声明能力的物品不挂这些组件（按需挂载）
- [x] 组件字段为声明式数据（无闭包）；进存档语义正确（amount 等可变字段可恢复）
- [x] 现有 take/drop 对无新组件物品行为不变
- [x] 现有测试全绿（不回归）

## Comments

### 2026-07-20 re-pass

- 复核既有实现：`components.py` 四组件 + `scene_loader._attach_item_capabilities` + `save` codecs 均已齐；Weight 双路径未改（归 C7）。
- AC 缺口在测试侧：补 `TestCapabilityComponents` 4 条——YAML 未声明不挂载、字段声明式（含 `apply_hook` 字符串引用）、`amount`/`uses` save/restore、plain 物品 take/drop 不回归。
- 实现无改动。`TestCapabilityComponents` 6 绿；`test_items_extension.py` 22 绿；`test_commands` take/drop 相关 14 绿。
