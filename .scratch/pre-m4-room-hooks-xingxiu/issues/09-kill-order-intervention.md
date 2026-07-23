---
Status: resolved
---

# 09 — 机关 #9 杀令介入（简化）

**What to build:** 挂一个"满足条件时触发一次简化的敌意介入"的官方房间钩子（日月洞灵感，简化版）：条件判定复用既有的阵营组件读取能力（`Faction`），不建通缉状态机/多阵营声望系统。满足条件（如特定阵营玩家进房）时触发一次可观察的介入事件（经 `ctx` 播报 + 可选经既有战斗触发路径 `try_engage` 介入）；用房间自由状态记一个"本次在场期间是否已触发"的标记位，避免重复触发。在 `xingxiu_mechanics.yaml` 追加对应验收房间。

对应 spec：US40–42；Testing S0/S1。

**Blocked by:** `01`（钩子协议/注册表/窄 `ctx`）。

- [x] 钩子挂在进房事件点，读取触发实体的既有 `Faction` 组件判定条件。
- [x] 满足条件且本次未触发过（房间自由状态标记位）：经 `ctx` 播报介入事件；可选经既有战斗触发路径引发一次遭遇。
- [x] 不建通缉/声望持久状态；标记位仅服务"同一次进房只介入一次"的防重复触发，随进房/离房周期重置（具体重置时机按实现决定，记入 Comments）。
- [x] `xingxiu_mechanics.yaml` 追加至少一条覆盖本机关的验收房间。
- [x] 测试（S0）：直调钩子条件判定与标记位防重复触发逻辑。测试（S1）：命令层——满足条件进房触发一次可观察介入；同次在场再次尝试不重复触发。
- [x] `just test` 全绿。

## Comments

### 实现摘要（2026-07-22 Wave 5）

- **钩子**：`kill_order`（`KillOrderHook`）；`on_enter` + `on_leave`
- **params**：
  ```yaml
  hooks:
    hook_id: kill_order
    params:
      faction: shaolin      # 触发 Faction.faction_id
      npc: cave_guard       # 可选；在场则 try_engage(npc, actor)
  ```
- **ctx 方法**（Wave 5 与 08 同批）：`actor_faction_id` / `find_npc_in_room` / `try_engage`
- **标记位**：房间自由状态 `triggered=True`；**重置时机**：`on_leave` 仅 `pop("triggered")`（保留同房其他自由状态键；离房后下次进房可再介入）
- **切片**：`sun_moon_cave`（`dig_base` 经 `cave`）；`npcs.cave_guard`；顶层 `factions.shaolin`；`player.faction: shaolin`（切片自洽可玩）
- **测试**：`engine/tests/test_xingxiu_mechanics_09.py`
