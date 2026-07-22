---
Status: resolved
---

# 02 — 机关 #1 动态出口+时限崩塌 + 机关 #2 加载期 `random_of` 出口原语

**What to build:** 创建 `engine/data/xingxiu_mechanics.yaml`（官方单文件轨道，不带 `manifest.yaml`）。落地两条互不相同的「改出口」路径：（1）挂一个"挖洞开新出口、超时未完成则崩塌"的官方房间钩子（白玉峰灵感）——新增命令动词（如 `dig`）触发钩子经窄 `ctx` 新增出口并登记延时自查，超过时限该出口消失（复用 `01` 的心跳自查路径，不新建平行调度服务）；（2）新增出口层声明式小原语 `random_of`（岔路灵感）——加载期从候选目标里随机选定一个落地为普通出口，选定后运行时表现与静态出口完全一致，不进钩子注册表、不占用信任边界、无运行时副作用。

对应 spec：US10–16；Testing S0/S1/S2。

**Blocked by:** `01`（动态出口+崩塌需要钩子协议/注册表/窄 `ctx`；`random_of` 本身不依赖 `01`，但与机关 #1 共享本票创建的验收文件，一并交付）。

- [x] `dig` 类命令动词：仅在挂了对应钩子的房间生效；无关房间返回统一的「这里不能这么做」类拒绝提示（不是「未知命令」）。
- [x] 钩子：触发后经 `ctx.add_exit` 新增此前不存在的出口；经 `ctx.schedule` 登记延时自查；到期后经 `ctx.remove_exit`（或等价「崩塌」后果）使该出口消失。
- [x] 时限判定复用 `01` 落地的心跳自查路径，不新建平行的通用调度服务。
- [x] `random_of` 出口原语：房间 YAML 出口层新增字段，声明一组候选目标；加载期一次性选定，落地为普通出口；同一次运行内该出口结果固定；同一张地图重新加载后结果可能不同。
- [x] `xingxiu_mechanics.yaml` 内至少各有一条覆盖机关 #1、#2 的可玩验收路径。
- [x] 测试（S0）：直调钩子 `ctx` 断言新增出口与到期崩塌副作用。测试（S1）：`dig` 开出口→`go` 可走→到期后 `go` 不可走；`random_of` 出口加载后 `go` 结果与静态出口一致。测试（S2）：`xingxiu_mechanics.yaml` 加载成功；`random_of` 选定落地为普通出口（不带运行时随机副作用）。
- [x] `just test` 全绿。

## Comments

### 实现摘要（2026-07-22 Wave 2）

- **内置钩子**：`dig_collapse`（`DigCollapseHook`，`room_hooks.py`）；`clear_room_hooks` 后会重新挂上（同 `SkillBehavior` 内置模式）
- **命令**：`dig`——当前房有 `RoomHookBinding` 且钩子实现 `on_dig` 时生效；否则「这里不能这么做。」
- **params 形状**：
  ```yaml
  hooks:
    hook_id: dig_collapse
    params:
      direction: north      # 新出口方向
      target: dig_cave      # 目标房间键
      ttl_ticks: 3          # 挖开后存活 tick 数（绝对：due = world.tick + ttl）
  ```
- **文案**：挖开「你挖开了一个洞口。」；已挖「洞口已经挖开了。」；崩塌房间播报「洞口塌陷了！」
- **schedule key**：`dig_collapse`（`DigCollapseHook.SCHEDULE_KEY`）
- **`world.tick`**：`TickLoop.advance` 同步写入，供命令路径 `schedule` 登记绝对到期戳
- **`random_of` YAML**：
  ```yaml
  exits:
    north:
      random_of:
        - fork_left
        - fork_right
      aliases: [北]
  ```
  与 `to` 互斥；加载期 `rng.choice` 落地为普通 `Exit`；`load_scene(..., rng=)` 可注入
- **验收资产**：`engine/data/xingxiu_mechanics.yaml`；入口 `scenes.load_xingxiu_mechanics` / `XINGXIU_MECHANICS_PATH`
- **测试**：`engine/tests/test_xingxiu_mechanics_02.py`（S0/S1/S2）
