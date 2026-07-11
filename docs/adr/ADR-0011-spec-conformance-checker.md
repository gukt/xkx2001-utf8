# ADR-0011：规格符合性检查器与实现状态映射

- 状态：已采纳（阶段 0 任务 3 路径 B）
- 日期：2026-07-11
- 阶段：0 任务 3（单元级行为规约）
- 关联：[ADR-0002](ADR-0002-resolve-attack-extraction.md)（S1 简化台账）/ [ADR-0010](ADR-0010-lpc-spec-extraction-methodology.md)（规格提取方法论）/ [04](../xkx-arch/04-迁移路径与避坑清单.md) §三任务 3 / [05](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent 3（do_attack 副作用交织不可分离）

## 背景

[04](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 0 任务 3 验收标准：

> | 单元级行为规约 | 从代码提取的输入输出契约 + hypothesis 属性测试 | greenfield 主门禁，不依赖运行 LPC |

任务 1 已产出 9 层规格（160 FunctionSpec，[ADR-0010](ADR-0010-lpc-spec-extraction-methodology.md)），但 9 层测试（599 tests）是**固定断言的结构验证**（order 连续、交织顺序、枚举完整），不是 hypothesis 属性测试。S1 的 `test_resolve_attack.py` 已有 7 个 hypothesis 属性测试（确定性、三分支、副作用账本），但**与层 E do_attack 规格无关联**--属性是手写的，不是从规格派生的。

任务 3 的核心价值：**把"实现应该满足什么属性"从手写断言变成从 FunctionSpec 派生**，使规格成为实现的行为等价验证基准（greenfield 主门禁）。

## 问题：resolve_attack 是 S1 简化版，不完全符合 do_attack 规格

[ADR-0002](ADR-0002-resolve-attack-extraction.md) 记录了 resolve_attack 相对 do_attack 的简化：

- skill_power 用简化公式（非完整 DamageFormula 三段式）
- hit_ob 仅 int 加成（非 string/int/mapping 三分支）
- hit_by 仅 int 覆盖（非 string/int/mapping 三分支）
- riposte 仅标记不递归
- reset_action / actions 招式映射后置
- hit_ob 回调链（武学/武器/空手）后置
- receive_damage/receive_wound 实际调用后置（resolve_attack 只产 Effect）
- post_action / wizard verbose / report_status / winner_msg 等后置

直接用 do_attack 完整规格验证 resolve_attack 会产生大量"违反"，但这些"违反"是已知简化（ADR-0002 记录），不是 bug。**需要一个机制自动区分"已知简化"与"真正违反规格"**，否则属性测试要么无法通过（全量规格），要么失去意义（只验手写属性）。

## 决策：impl_map + ConformanceChecker

### 1. 实现状态映射（impl_map）

独立文件 `engine/src/xkx/spec/impl_map.py`，记录 do_attack 规格条目的实现状态。**不污染规格源**（layer_e_combat.py 是纯 LPC 契约，不应包含 Python 实现状态）。

每条映射记录：
- `spec_ref`：规格条目引用（函数名 + 条目类型 + order/描述键）
- `status`：三状态之一
  - `implemented`：resolve_attack 已实现且符合规格，属性测试验证
  - `simplified`：resolve_attack 简化实现，验证简化版规格（附简化说明）
  - `postponed`：后置（riposte 递归 / 双武器 / 回调链等），跳过验证
- `adr_ref`：关联 ADR（简化/后置的理由来源）
- `note`：简化说明（simplified 时必填）

impl_map 只覆盖 do_attack（层 E 核心），不覆盖全部 26 个函数。理由：do_attack 是七步管线核心，resolve_attack 是其 S1 实现，这是"规格->属性测试"桥梁的首要验证点。其余函数（skill_power / receive_damage 等）的实现状态在阶段 2 实现时补充。

### 2. ConformanceChecker（符合性检查器）

`engine/src/xkx/combat/conformance.py`，输入 `CombatContext + CombatRoundResult`，对照 do_attack 规格 + impl_map 检查，输出 `ConformanceReport`。

检查范围（从 do_attack invariants + 关键 side_effects 派生，不覆盖全部 49 个 side_effects）：

检查分两层：ConformanceChecker 单次检查（8 项，验证单次 result 结构属性）+ 统计性属性测试（6 项，多次调用统计验证）。

**ConformanceChecker 单次检查（8 项，`check_conformance(ctx, result)`）：**

| 检查项 | 规格来源 | 状态 | 检查内容 |
|---|---|---|---|
| result_code 合法 | postconditions[0] | implemented | result_code in {HIT, DODGE, PARRY} |
| damage 非负 | postconditions[1] | implemented | result.damage >= 0 |
| 非命中时 damage=0 | side_effects 步骤3/4 return | implemented | RESULT_DODGE/PARRY 时 damage == 0 |
| effect target 合法 | side_effects target | implemented | effect.target_id in {attacker, victim} |
| 命中时有 DAMAGE | side_effects order=34 | implemented | RESULT_HIT 时 effects 含且仅含一条 KIND_DAMAGE |
| 闪避/招架无 DAMAGE | side_effects 步骤3/4 return | implemented | RESULT_DODGE/PARRY 时 effects 无 KIND_DAMAGE |
| 三层资源不变量 | invariants[0] | simplified | apply Effect 后 0<=qi<=eff_qi<=max_qi |
| 交织顺序 | invariants[1] | simplified | hit 分支 ledger 中 message 与 effect 非全分组 |

**统计性属性测试（6 项，hypothesis 多次调用）：**

| 检查项 | 规格来源 | 状态 | 检查内容 |
|---|---|---|---|
| 确定性 | determinism_note | implemented | 同 seed+快照 -> 同输出 |
| 三分支可达 | side_effects 步骤 3/4/5 | implemented | dodge/parry/hit 三分支 seed 遍历可达 |
| 闪避概率 | random_specs "闪避判定" | implemented | 闪避比例 ≈ dp/(ap+dp)（容差 0.1） |
| 招架概率 | random_specs "招架判定" | implemented | 招架条件概率 ≈ pp/(ap+pp)（容差 0.1） |
| ap/dp/pp >= 1 | invariants[2] | implemented | skill_power 返回值 >= 1 |
| TYPE_QUICK 减半 | invariants[3] | implemented | TYPE_QUICK damage <= TYPE_REGULAR damage（同 seed） |

输出 `ConformanceReport`：
- `passed`：通过的检查项
- `skipped`：跳过的检查项（postponed，附规格条目 + ADR 引用）
- `violations`：违反的检查项（附规格条目 + 实际值 + 期望）

### 3. 属性测试从规格派生

`engine/tests/test_conformance.py`，用 hypothesis 生成 `CombatContext`，调 `resolve_attack` + `ConformanceChecker`，断言 `violations` 为空。

核心属性：**对任意合法 CombatContext，resolve_attack 的输出不违反 do_attack 规格中 implemented/simplified 条目**。

与 S1 手写属性测试的区别：
- S1 `test_resolve_attack.py`：手写"damage >= 0"、"三分支可达"等断言
- 任务 3 `test_conformance.py`：从 do_attack 规格派生检查项，通过 ConformanceChecker 执行，规格演进时检查项自动跟进

### 4. Effect apply 辅助函数

三层资源不变量验证需要"应用 Effect 后"的快照。写一个 `apply_effects(snapshot, effects)` 辅助函数（纯函数，不依赖 runtime），把 Effect 应用到 CombatantSnapshot 副本上，然后检查 `0 <= qi <= eff_qi <= max_qi`。

## 不做

- **不覆盖全部 26 个函数**：只覆盖 do_attack（核心）。skill_power / receive_damage 等函数的实现状态在阶段 2 实现时补充 impl_map。
- **不写通用"从 FunctionSpec 自动派生属性测试"框架**：ConformanceChecker 是针对 do_attack 的手写检查器，不是通用框架。通用化在路径 A（9 层）或阶段 2 多函数时再评估。
- **不修改规格源**：impl_map 独立于 layer_e_combat.py，规格保持纯 LPC 契约。
- **不覆盖全部 49 个 side_effects**：只检查关键 side_effects（三分支 DAMAGE 约束、target 合法）。完整 49 个 side_effects 的检查在阶段 2 do_attack 完整实现时补充。
- **不引入运行时依赖**：ConformanceChecker 是测试期工具，不进运行时路径。

## 与路径 A（9 层规格一致性属性测试）的关系

路径 B 确立"规格->属性测试"的桥梁模式后，路径 A 用 agent teams 并行升级 9 层的结构验证测试（从固定断言到 hypothesis 生成）。路径 A 不需要 ConformanceChecker（无被测实现），验证规格模型自身一致性。两路径独立，路径 B 优先因其直接验证"规格可作为实现的行为等价验证基准"。

## 验收标准

- [x] impl_map.py 产出，do_attack 14 项检查条目三状态标注完整（12 implemented + 2 simplified）
- [x] conformance.py 产出，ConformanceChecker 单次检查 8 项
- [x] test_conformance.py 产出，13 个测试全绿（ConformanceChecker 单次 2 + 统计性 6 + impl_map 完整性 5）
- [x] CombatRoundResult 升级 ledger 字段（向后兼容，S1 7 tests 不回归）
- [x] 现有 599 tests 不回归（612 passed = 599 + 13）
- [x] ruff 全过
