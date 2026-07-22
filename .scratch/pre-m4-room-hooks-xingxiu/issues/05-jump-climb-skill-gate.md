---
Status: ready-for-agent
---

# 05 — 机关 #5 jump/climb 技能门槛

**What to build:** 新增 `jump`/`climb` 命令动词，挂一个"需要达到某项技能等级才能通过"的官方房间钩子（白玉峰 jump、天路灵感）：技能等级判定复用既有的角色技能等级读取能力（`SkillLevels`），不新造判断逻辑。技能等级不够时尝试通过被拒绝并有清晰提示；技能等级够时可以正常通过。在 `xingxiu_mechanics.yaml` 追加对应验收房间。

对应 spec：US25–28；Testing S0/S1。

**Blocked by:** `01`（钩子协议/注册表/窄 `ctx`）。

- [ ] 新增 `jump`/`climb` 命令动词，仅在挂了对应钩子的出口/方向生效；其余情况返回统一拒绝提示。
- [ ] 钩子读取既有 `SkillLevels` 判定门槛，不新造技能等级判断逻辑。
- [ ] 技能等级不够：拒绝通过并有清晰提示。技能等级够：正常通过（经 `ctx` 受限实体移动或既有 `go` 等价路径）。
- [ ] `xingxiu_mechanics.yaml` 追加至少一条覆盖本机关的验收房间。
- [ ] 测试（S0）：直调钩子门槛判定逻辑。测试（S1）：命令层——技能等级不足拒绝、达标放行。
- [ ] `just test` 全绿。

## Comments

