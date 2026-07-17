# ADR-0002：resolve_attack 纯函数提取（从 do_attack 七步）

- 状态：已采纳（S1 最小版）
- 日期：2026-07-10
- 阶段：-1 切片 S1

## 背景

[04](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 -1 要求垂直切片"跑在 resolve_attack 纯函数 + stub 运行时"。LPC 源码中 `resolve_attack` 不存在（`grep` 零命中），需从 `adm/daemons/combatd.c:340` 的 `do_attack` 七步管线重构提取。[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 警示：七步副作用交织不可分离、18 处 `random` 须 seeded、CombatKernel 抽象时机张力。

## 决策（S1 最小版）

从 `do_attack` 七步提取 `resolve_attack(ctx: CombatContext) -> CombatRoundResult` 纯函数：

- **三分支**：dodge（步 3）/ parry（步 4）/ hit（步 5-7）。`DeterministicRNG` 替换 18 处 `random`。
- **副作用账本**：所有 mutate（damage/wound/exp/jingli/skill_improve）产出为 `Effect`，按"文本与状态交织真实顺序"入 `CombatRoundResult.effects`，**显式否定"先算后 apply"**。调用方（`apply_effects`）按账本顺序 apply 到组件。
- **CombatContext 快照边界**：战斗开始对双方组件一次性快照，`resolve_attack` 只读快照、不 mutate 现场状态。
- **确定性**：同 seed + 同快照 -> 同输出（hypothesis 验证，7 tests 通过）。

## S1 简化（后续补全）

| 简化项 | S1 | 补全时机 |
|---|---|---|
| hit_ob / hit_by 回调 | 仅 int 加成/覆盖 | S2/S3（mapping 分支：result+damage） |
| riposte 递归 | 仅标记不递归 | S2（子回合交织） |
| skill_power 公式 | level³/3 + 属性（简化） | 阶段 0（DamageFormula 三段式管线规格提取） |
| 武器类型 | unarmed/sword/blade 最小集 | 阶段 0（武器系统规格） |
| 技能 action 描述 | 固定招式 | S4（SkillData YAML） |
| combat_exp 防御折减 | 限 5 次循环 | 阶段 0 校准 |

## 不硬编码武侠（CombatKernel 主题无关性留口）

`resolve_attack` 接口不嵌武侠语义：武器类型用枚举传入（unarmed/sword/blade），"经脉/内力"等武侠概念不进核心签名。为 S2 非武侠微场景验证留口（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent 1）。但 S1 不实跑非武侠。

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 1（CombatKernel 抽象时机）、dissent（七步副作用交织）、18 处 random。
- [01](../xkx-arch/01-目标架构与子系统设计.md) 子系统 5（resolve_attack 纯函数 + 副作用账本 + seeded RNG）。
- [04](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 -1 验收（resolve_attack 提取成功且与未来引擎同源）。
- LPC 源：`adm/daemons/combatd.c:340` do_attack、`feature/damage.c` receive_damage/receive_wound。
