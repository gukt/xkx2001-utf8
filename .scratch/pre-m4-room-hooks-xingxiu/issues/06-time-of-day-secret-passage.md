---
Status: resolved
---

# 06 — 机关 #6 时段耦合秘道

**What to build:** 挂一个"仅在特定时段（如白天）揭示隐藏出口"的官方房间钩子（玉室日光灵感）：时段判定复用既有的昼夜状态读取能力（`is_day`/`is_night`），出口揭示复用既有的「隐藏出口解锁后迁入可见出口」机制（`HiddenExits` → `Exits`），不新建平行的门/出口系统。非对应时段看不到、走不了该隐藏出口；到了对应时段该出口被揭示且可走。在 `xingxiu_mechanics.yaml` 追加对应验收房间。

对应 spec：US29–32；Testing S0/S1。

**Blocked by:** `01`（钩子协议/注册表/窄 `ctx`）。

- [x] 钩子挂在心跳或进房事件点，读取既有昼夜状态判定当前是否满足时段条件。
- [x] 满足条件时经 `ctx` 将出口从 `HiddenExits` 揭示迁入 `Exits`（复用既有揭示机制，不新建平行系统）；不满足条件时出口保持隐藏。
- [x] 非对应时段：`look`/`go` 均不可见/不可走该出口。对应时段：出口被揭示且可走。
- [x] `xingxiu_mechanics.yaml` 追加至少一条覆盖本机关的验收房间。
- [x] 测试（S0）：直调钩子在不同时段读取下的揭示/隐藏副作用。测试（S1）：命令层——非对应时段不可见不可走，对应时段可见可走。
- [x] `just test` 全绿。

## Comments

### 实现摘要（2026-07-22 Wave 4）

- **钩子**：`time_of_day_passage`（`TimeOfDayPassageHook`）；`on_enter` + `on_tick` 调 `_sync`
- **params**：
  ```yaml
  hooks:
    hook_id: time_of_day_passage
    params:
      direction: north   # 秘道方向（YAML 写成普通 exits，由钩子藏/揭）
      when: day          # day | night → ctx.is_day / ctx.is_night
  ```
- **状态**：`RoomFreeState.data.revealed`（bool）；首 sync 先 `hide_exit` 再按需 `reveal_exit`（经 HiddenExits 路径）；`attach_room_hooks` 对 tick 钩子冷启动跑一轮 `on_tick`
- **params.when**：仅 `day` | `night`，其它值 `ValueError`
- **切片房间**：`sunlit_room` ↔ `secret_tunnel`（`dig_base` 西北可达）
- **测试**：`engine/tests/test_xingxiu_mechanics_06.py`（S0/S1/S3）
