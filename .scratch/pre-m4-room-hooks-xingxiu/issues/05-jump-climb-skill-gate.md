---
Status: resolved
---

# 05 — 机关 #5 jump/climb 技能门槛

**What to build:** 新增 `jump`/`climb` 命令动词，挂一个"需要达到某项技能等级才能通过"的官方房间钩子（白玉峰 jump、天路灵感）：技能等级判定复用既有的角色技能等级读取能力（`SkillLevels`），不新造判断逻辑。技能等级不够时尝试通过被拒绝并有清晰提示；技能等级够时可以正常通过。在 `xingxiu_mechanics.yaml` 追加对应验收房间。

对应 spec：US25–28；Testing S0/S1。

**Blocked by:** `01`（钩子协议/注册表/窄 `ctx`）。

- [x] 新增 `jump`/`climb` 命令动词，仅在挂了对应钩子的出口/方向生效；其余情况返回统一拒绝提示。
- [x] 钩子读取既有 `SkillLevels` 判定门槛，不新造技能等级判断逻辑。
- [x] 技能等级不够：拒绝通过并有清晰提示。技能等级够：正常通过（经 `ctx` 受限实体移动或既有 `go` 等价路径）。
- [x] `xingxiu_mechanics.yaml` 追加至少一条覆盖本机关的验收房间。
- [x] 测试（S0）：直调钩子门槛判定逻辑。测试（S1）：命令层——技能等级不足拒绝、达标放行。
- [x] `just test` 全绿。

## Comments

### 实现摘要（2026-07-22 Wave 3）

- **钩子**：`skill_gate`（`SkillGateHook`）；`on_jump` / `on_climb`；`params.verb` 必须匹配命令否则「这里不能这么做。」
- **命令**：`jump`/`climb`（别名 `跳`/`爬`）
- **ctx 新只读方法**：`actor_skill_level(skill_id)` → 读 `SkillLevels.levels[id].level`，缺省 0
- **params**：`verb` + `skill_id` + `min_level` + `direction`（文案预留）+ `target`；成功经 `ctx.move_entity`
- **验收房**：`cliff_edge`（jump / dodge≥50）/ `cliff_far`；`cliff_base`（climb / dodge≥30）/ `cliff_top`；切片玩家 `dodge: 50`
- **测试**：`engine/tests/test_xingxiu_mechanics_05.py`
