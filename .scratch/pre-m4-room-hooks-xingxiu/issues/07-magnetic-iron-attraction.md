---
Status: resolved
---

# 07 — 机关 #7 入室磁力吸铁

**What to build:** 挂一个"携带铁质物品进入时触发效果"的官方房间钩子（玉厅灵感）：钩子挂在进房事件点，扫描进房实体携带的物品是否命中约定的 `ItemTags`（如铁质标签），命中时触发磁力效果的可观察播报（本票只做到播报级效果，不强制卸除物品）。不携带命中物品进房间时无异常反应。在 `xingxiu_mechanics.yaml` 追加对应验收房间。

对应 spec：US33–35；Testing S0/S1。

**Blocked by:** `01`（钩子协议/注册表/窄 `ctx`）。

- [x] 钩子挂在进房事件点，读取触发实体背包内物品的既有 `ItemTags`，判定是否命中约定标签。
- [x] 命中标签：经 `ctx` 播报磁力效果消息（可观察、可测试）。未命中：无异常反应。
- [x] `xingxiu_mechanics.yaml` 追加至少一条覆盖本机关的验收房间。
- [x] 测试（S0）：直调钩子进房方法，断言命中/未命中标签时的播报差异。测试（S1）：命令层——携带命中标签物品进房收到播报；不携带无异常反应。
- [x] `just test` 全绿。

## Comments

### 实现摘要（2026-07-22 Wave 4）

- **钩子**：`magnetic_iron`（`MagneticIronHook`）；仅 `on_enter`
- **params**：
  ```yaml
  hooks:
    hook_id: magnetic_iron
    params:
      tag: iron   # ItemTags 须命中的标签
  ```
- **ctx 新方法**：`actor_has_item_tag(tag)` — 扫触发实体 `Container` + `ItemTags`（携带，非持刃谓词）
- **文案**：`message_actor(f"…带「{tag}」标记的器物…")`；经邮箱（S1 用 `drain_messages`）
- **不做**：强制卸除物品
- **切片**：`magnetic_hall`（`dig_base` 西南）；`items.iron_sword` 放在 `dig_base.objects`
- **测试**：`engine/tests/test_xingxiu_mechanics_07.py`（S0/S1/S3）
