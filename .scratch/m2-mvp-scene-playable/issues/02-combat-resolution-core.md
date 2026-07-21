# 02 — 战斗结算核心：CombatContext + resolve_attack 七步管线 + PowerModel 策略

**What to build:** 落地 ADR-0004 拍板、spec Implementation Decisions「A1/A2」定义的战斗结算纯函数地基：`CombatContext`（参战双方只读快照：气血/内力/属性/当前招式候选数值，不是活引用）+ `resolve_attack(ctx: CombatContext, rng: Random) -> CombatRoundResult`（严格按七步顺序：选技能 -> 取招式 -> 算 AP/DP -> dodge 判定 `random(ap+dp)<dp` -> parry 判定 `random(ap+pp)<pp` -> 算伤害（`hit_ob`/`hit_by` 回调点，本票先留调用点，钩子实际生效见 16 号票）-> inflict -> exp+riposte（riposte 本 MVP 是 no-op，见 spec Out of Scope 最后一条））+ `PowerModel` Protocol（给定攻击者属性+招式 `force`/装备加成 -> AP；给定防御者属性+招式 `dodge` -> DP/PP）+ 默认实现 `DefaultWuxiaPowerModel`（纯数据系数，不追求 LPC 还原度，ADR-0001）+ `register_power_model`/`attach_power_model` 挂载模式（与 `attach_ai_system`/`attach_nature` 同构：纯内存运行时态，缺省用默认实现）。这是本 spec"最核心"的纯函数直测 seam（spec Testing Decisions 第一条）：不依赖 `World`/tick/命令管线，直接构造 `CombatContext` + seeded RNG 断言 `CombatRoundResult`。本票**不**接入真实 ECS 组件（`Vitals`/`BaseAttributes` 是 05 号票的产物）、**不**接入命令层（`attack`/`flee` 是 12 号票），`CombatContext` 的字段本票可以先用裸数值（如 `attacker_qi_current: int`）占位，12 号票再从真实组件构造它。

**Blocked by:** None — 纯算法层，无 ECS/YAML 依赖，可与 01/03/04 并行开工。

**Status:** ready-for-agent

- [ ] `CombatContext` 是 frozen dataclass 快照（参战双方气血/内力/属性/当前招式候选的只读数值），不含任何活组件引用。
- [ ] `resolve_attack(ctx, rng)` 严格实现七步（选技能 -> 取招式 -> AP/DP -> dodge -> parry -> 伤害 -> inflict -> exp+riposte no-op），返回结构化 `CombatRoundResult`（命中/闪避/招架/伤害数值/是否致命/招式名/文案片段）。
- [ ] AP/DP 判定结构是硬编码不变量：`random(ap+dp)<dp` 命中即闪避成功、`random(ap+pp)<pp` 命中即招架成功（对照 ADR-0004 已拍板形状，不重新论证）。
- [ ] `PowerModel` 是 `Protocol`（类型层可替换），`DefaultWuxiaPowerModel` 是一份自洽、可测试的默认实现：AP = 招式 `force` × (1 + 力量修正系数)，DP = 防御方敏捷 × 系数 + 招式 `dodge` 值（系数为可读常量，非玄学数字）。
- [ ] `register_power_model`/`attach_power_model` 与 `attach_ai_system` 同构：纯内存挂 `world`（如 `world.power_model`），幂等，缺省场景不挂时命令层用默认实现兜底（本票只做挂载点，`World.power_model` 字段本身可作为本票交付物，供 12 号票消费）。
- [ ] 纯函数直测：给定同一份 `CombatContext` + 同 seed 的 `Random` 两次求值，结果完全一致（确定性契约，不是"行为对齐 LPC"，ADR-0001）。
- [ ] 至少 3 组测试覆盖：必中（dp=0）、必闪（dp 极大）、固定伤害招式 vs 力量修正伤害招式的 AP 计算差异。
- [ ] `hit_ob`/`hit_by`/`post_action` 三个钩子调用点在 `resolve_attack` 内**留空实现占位**（本票招式不带任何 `SkillBehavior`，占位调用对 `CombatRoundResult` 无影响），供 16 号票接入真实钩子时只改调用点内部、不改 `resolve_attack` 签名。
