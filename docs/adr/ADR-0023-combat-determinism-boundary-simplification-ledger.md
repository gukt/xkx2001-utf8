# ADR-0023：combat 确定性边界 + 简化台账补全策略

- 状态：草案（Wave 2 T6 前置）
- 日期：2026-07-11
- 阶段：阶段 1 Wave 2 T6
- 关联：[04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 1（M1-6 combat 确定性）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 1（CombatKernel 抽象时机张力）+ 专家 2 承重论断 2（combat-only 确定性）/ [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T6 / [ADR-0002](ADR-0002-resolve-attack-extraction.md)（简化台账 6 项）/ [ADR-0003](ADR-0003-combatkernel-theme-neutrality.md)（主题无关性）/ [ADR-0011](ADR-0011-spec-conformance-checker.md)（ConformanceChecker 8 项）/ [ADR-0012](ADR-0012-performance-microbenchmark.md)（PYTHONHASHSEED=0 已验证）

## 背景

[12](../xkx-arch/12-阶段1-核心循环实施计划.md) T6 任务卡（第 198-210 行）：resolve_attack 纯函数扩展为单 tick 快照 + input log 可重放（combat 范围）；补全 [ADR-0002](ADR-0002-resolve-attack-extraction.md) 简化台账。验收三件：combat 范围确定性重放通过 + ConformanceChecker 8 项检查通过 + ADR-0002 简化台账 6 项补全。

**现有资产（阶段 -1/0 已产出，T6 在此基础上扩展）**：

- [combat/resolve_attack.py](../../engine/src/xkx/combat/resolve_attack.py) 纯函数七步管线，`DeterministicRNG` 收口 `combatd.c` `do_attack` 31 处 `random()`（实现侧 16 处 rng 调用：rand×13/choice×1/chance×1/derive_seed×1；精确口径见 [rng.py](../../engine/src/xkx/combat/rng.py) docstring），同 seed+同快照->同输出（hypothesis 验证，[ADR-0002](ADR-0002-resolve-attack-extraction.md)）。
- [combat/context.py](../../engine/src/xkx/combat/context.py) `CombatContext`/`CombatantSnapshot` 快照（战斗开始边界一次性拷贝，`resolve_attack` 只读不 mutate 现场）。
- [combat/result.py](../../engine/src/xkx/combat/result.py) `CombatRoundResult` + `ledger`（message/effect 按交织真实顺序记录，`apply_effects` 按账本顺序 apply）。
- [combat/rng.py](../../engine/src/xkx/combat/rng.py) `DeterministicRNG`（`random.Random(seed)`，非 hash，PYTHONHASHSEED 不影响）。
- [combat/conformance.py](../../engine/src/xkx/combat/conformance.py) 8 项单次检查 + impl_map 三状态过滤（[ADR-0011](ADR-0011-spec-conformance-checker.md)）。
- [tests/test_theme_neutrality.py](../../engine/tests/test_theme_neutrality.py) 非武侠硬门禁（火枪/戒尺走题材数据声明 + `inspect.getsource` 断言无 sword/blade 字面量 + `neili` 不进核心签名，[ADR-0003](ADR-0003-combatkernel-theme-neutrality.md)）。
- [ADR-0012](ADR-0012-performance-microbenchmark.md) PYTHONHASHSEED=0 跨进程一致性已验证（combat 确定性基础，阶段 1 里程碑前置）。

**dissent 1 的承重张力**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 1 条 + Q1 最强反论第 121-123 行）：

> CombatKernel 抽象时机张力：从武侠提取（保深度）与非武侠验证（保主题无关）可能冲突--武侠深度尚未完整实现时，提取的接口可能过窄（锁死武侠语义）或过宽（平庸化）。靠阶段 -1 非武侠微场景硬门禁兜底。

> 最强反论："真正的承重问题是'CombatKernel 从武侠提取（保深度）与用非武侠微场景验证主题无关（保可移植）的张力'，这个张力不解决，三层边界无论静态还是热插拔都会落空。"

T6 同时承担"补全武侠深度"（简化台账 6 项）与"验证主题无关持续不回归"（test_theme_neutrality），正是 dissent 1 张力的实施期爆发点。本 ADR 必须给出该张力的 T6 级应对。

**专家 2 承重论断 2**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) 第 57 行）：

> 全仿真确定性扩展到所有 System 是阶段 1 的错误范围；combat-only 确定性才是正确范围且已是 combat-sim 等价性的前置。

本 ADR 落地该裁决：combat 确定性的范围是 combat-only，不扩展到 tick 驱动的其他 System（heal/exp/condition/effect），全仿真确定性后置 M3。

## 决策

### 1. combat-only 确定性边界（专家 2 承重论断 2 落地）

**确定性范围内**（T6 产出，同 seed + 同快照 + 同 input log -> 同输出）：

| 范围内要素 | 来源 | 可重放保证 |
|---|---|---|
| `CombatContext` 快照 | 战斗开始边界一次性拷贝双方组件（[context.py](../../engine/src/xkx/combat/context.py)） | 快照不可变，序列化可恢复 |
| `seed` | `DeterministicRNG(seed)`（[rng.py](../../engine/src/xkx/combat/rng.py)），`random.Random` 非 hash | [ADR-0012](ADR-0012-performance-microbenchmark.md) PYTHONHASHSEED=0 跨进程已验证 |
| combat 内输入（input log） | 战斗期间玩家/NPC 的命令输入按序记录（kill/flee/wield 等） | 按序重放，确定性不变 |
| `resolve_attack` 输出 | `CombatRoundResult`（含 ledger 交织顺序，[result.py](../../engine/src/xkx/combat/result.py)） | 纯函数，同输入同输出 |
| `apply_effects` 顺序 | 按 `ledger` 顺序 apply 到 ECS 组件 | 顺序由 `resolve_attack` 决定，非调用方重排 |

**确定性范围外（后置 M3，T6 明确不做）**：

| 范围外要素 | 后置理由 |
|---|---|
| tick 驱动的其他 System（heal_up/exp/condition/effect 更新） | System.update 的 mutation 无 Command 级审计轨迹（dissent 7，[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 7 条），combat-only 确定性是正确范围（专家 2 承重论断 2） |
| 非 combat 的随机源（NPC AI 决策、drop 掉落、condition 触发） | 不进 `DeterministicRNG` seed 链，T6 不覆盖 |
| 全仿真状态快照（所有 ECS 组件 + 所有 System 状态） | 全仿真确定性后置 M3（[04](../xkx-arch/04-迁移路径与避坑清单.md) §六不做 + CLAUDE.md 不变量） |
| 跨 tick 的 combat 重放（多回合连续回放） | T6 只做单 tick 快照 + input log 重放，多 tick 连续回放由 T8 Combat Replay Viewer（[12](../xkx-arch/12-阶段1-核心循环实施计划.md) T8）扩展 |

**边界红线**：CombatSystem 的 tick 驱动 mutation 中，只有 `resolve_attack` + `apply_effects` 链路在确定性范围内（可重放）；heal_up/exp/condition 等 System 的 tick mutation 不在确定性范围内（不进 input log、不进 seed 链）。若 T6 实现中发现需要把 heal/exp 也纳入确定性重放才能通过验收，即触发范围蠕变，须回退并补 ADR 记录（对应专家 2 承重论断 2 的"错误范围"判定）。

### 2. CombatSystem 设计（tick 驱动，调 resolve_attack + apply_effects）

CombatSystem 是 T1 System 基类（[ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)）的具体实现，职责承重决策如下（不穷尽每个方法）：

- **tick 驱动**：每 tick（tick=1s 非均匀，CLAUDE.md 不变量）遍历有 `CombatState` 组件且 `enemies` 非空的实体，调 `fight()` 语义（[spec/layer_e_combat.py](../../engine/src/xkx/spec/layer_e_combat.py) `_fight`/`_attack`）选对手 -> 调 `resolve_attack` -> `apply_effects`。
- **快照边界**：调 `resolve_attack` 前从 ECS 组件构建 `CombatContext` 快照（战斗开始边界一次性拷贝），`resolve_attack` 只读快照不 mutate 现场，`apply_effects` 按账本顺序写回 ECS 组件。保留 [ADR-0002](ADR-0002-resolve-attack-extraction.md) 的"快照边界 + 纯函数"架构不变。
- **input log 记录**：战斗期间的玩家命令输入（kill/flee/wield 等改变战斗状态的命令）按序记录到 input log；NPC AI 的战斗决策（select_opponent/auto_fight 触发）也按序记录，因 NPC 决策也影响 combat 输出确定性。input log 是 combat 范围内输入的有序序列，非全仿真状态。
- **确定性重放入口**：提供 `replay(snapshot, seed, input_log) -> list[CombatRoundResult]` 纯函数入口，供 T8 Combat Replay Viewer（[12](../xkx-arch/12-阶段1-核心循环实施计划.md) T8）+ T9 combat-sim（T9）消费。重放不依赖运行时 ECS，只依赖快照 + seed + input log。
- **不套 Command 模式**：CombatSystem 的 tick mutation 不走 8 段命令管线（[ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md) 已定 Command 仅覆盖外部意图），System tick 派生变更不经 Command（CLAUDE.md 不变量 + 专家 2 承重论断 4）。

> CombatSystem 的具体方法签名（update/replay/record_input 等）由 T6 实现期定，本 ADR 只锁定承重决策：tick 驱动 + 快照边界 + input log + 确定性重放入口 + 不套 Command。收敛优先于完备，不提前穷举。

### 3. 单 tick 快照 + input log 可重放（确定性重放协议）

**单 tick 快照**：`CombatContext`（[context.py](../../engine/src/xkx/combat/context.py)）+ 战斗相关的全局状态快照（双方 `CombatState.enemies`/`killer` 列表、`CombatState` 的 `guarding`/`action_flag` temp、当前武器/技能映射）。快照在 tick 开始边界构建，tick 内 `resolve_attack` 可多次调用（双武器/riposte 递归），每次调用读同一快照的不可变副本 + 各自的 seed 推进。

**input log**：战斗内输入按序记录的有序序列。每条记录含：

- 输入类型（玩家命令 / NPC AI 决策 / riposte 递归触发）
- 输入内容（命令名 + 参数 / 决策结果 / 递归调用参数）
- 输入时序（tick 内的相对顺序）

**重放协议**：`replay(snapshot, seed, input_log)` 按序消费 input log，每条输入驱动一次 `resolve_attack`（或等价语义），seed 链按调用顺序推进（同 `DeterministicRNG` 实例的 `rand` 调用顺序）。同 snapshot + 同 seed + 同 input_log -> 同 `list[CombatRoundResult]` 输出，跨进程一致（PYTHONHASHSEED=0，[ADR-0012](ADR-0012-performance-microbenchmark.md) 已验证基础）。

> 单 tick 快照不等于全仿真快照。全仿真快照（所有 ECS 组件 + 所有 System 状态）后置 M3。T6 的快照只覆盖 combat 相关组件 + combat 相关 temp，足够支撑 combat 范围重放即可。

### 4. 简化台账补全策略（ADR-0002 §S1 简化 6 项）

[ADR-0002](ADR-0002-resolve-attack-extraction.md) §S1 简化台账 6 项，T6 逐一补全。每项标注是否保持七步交织（CLAUDE.md 不变量：do_attack 七步文本与副作用交织不可分离，不得"先算后 apply"）。

| 简化项 | S1 现状 | T6 补全策略 | 保持七步交织 |
|---|---|---|---|
| **hit_ob/hit_by mapping 分支** | 仅 int 加成（`hit_ob_bonus`）/ int 覆盖（`hit_by_override`），[context.py](../../engine/src/xkx/combat/context.py) 第 73-75 行 | 补 mapping 分支：`hit_ob`/`hit_by` 返回 mapping 时，mapping 中的 `result`（追加文本）入 ledger 为 `LEDGER_MESSAGE`、`damage`（伤害修正）入 ledger 为 `KIND_DAMAGE` 副作用，按规格 [layer_e_combat.py](../../engine/src/xkx/spec/layer_e_combat.py) side_effects order=23/25/26/32/33 的交织顺序入账本。`hit_ob`/`hit_by` 回调签名保持主题无关（入参为快照 + damage_bonus，返回 `str`/`int`/`mapping`），回调实现由题材数据声明（武侠武学/非武侠武器各自的回调逻辑），内核只定义返回类型分发。 | 是（mapping 的 result 文本与 damage 修正按规格 order 交织入账本，不批量 apply） |
| **riposte 递归** | 仅标记 `riposte_triggered=False` 不递归（[resolve_attack.py](../../engine/src/xkx/combat/resolve_attack.py) 第 158-159 行） | 补子回合交织：riposte 触发时（TYPE_REGULAR + damage<1 + victim guarding，规格 side_effects order=48-49），递归调 `resolve_attack(victim, me, weapon, TYPE_QUICK/TYPE_RIPOSTE)`，子回合的 `CombatRoundResult` 嵌入父回合 ledger 的对应 order 位置（非独立账本），形成"父回合文本 -> 子回合文本+副作用 -> 父回合后续"的交织序列。递归深度限制（防死循环，LPC 无显式限制但实际由 guarding temp 消耗自然终止）。 | 是（子回合整体嵌入父回合 ledger 的交织位置，不分离） |
| **武器类型完整集** | unarmed 最小集（[ADR-0003](ADR-0003-combatkernel-theme-neutrality.md) 已删 sword/blade 硬编码，改题材数据声明） | 不在内核枚举武器类型（保持 [ADR-0003](ADR-0003-combatkernel-theme-neutrality.md) 主题无关），`attack_skill`/`weapon_label` 由题材数据声明。T6 补的是"武器到技能/标签映射"的题材数据载体（SkillData/WeaponData 声明结构），非内核武器枚举。武侠武器（sword/blade/whip 等）与非武侠武器（firearm/ruler 等）平等走同一声明路径。 | 不适用（武器类型不进七步管线逻辑，只影响 `attack_skill` 取值与 `$w` 渲染） |
| **skill_power 公式** | 简化版 `level³/3 + 属性 + apply`（[resolve_attack.py](../../engine/src/xkx/combat/resolve_attack.py) 第 42-52 行） | 补 LPC 完整公式（规格 [layer_e_combat.py](../../engine/src/xkx/spec/layer_e_combat.py) `_skill_power` invariants）：`power = (level³)/3`，`level = query_skill(skill) + apply 修正`，`jingli_bonus = 50 + jingli/(max_jingli+1)*50`（上限 150），ATTACK 用 str 加成、DEFENSE 用 dex 加成，`is_fighting()` 时 DEFENSE 额外乘 `(100 + fight/dodge/10) / 100`。低技能时（level<1）用 `combat_exp/20 * (jingli_bonus/10)` 经验补偿。公式是纯计算函数，不产副作用，但 `is_fighting()` 依赖战斗状态（快照内可判定）。 | 不适用（skill_power 是纯计算，不产 message/effect，不影响交织） |
| **combat_exp 防御折减** | 限 5 次循环（[resolve_attack.py](../../engine/src/xkx/combat/resolve_attack.py) 第 127-134 行） | 补 LPC 完整循环（规格 side_effects order=31）：`while(random(defense_factor) > me.combat_exp) { damage -= damage/3; defense_factor /= 2; }`。S1 的 5 次上限改为 LPC 的 `defense_factor` 折半自然终止（`defense_factor` 初始值由 victim 属性决定，折半到 0 即停）。`defense_factor` 初始值与 victim `con_` 相关（S1 用 `victim.con_*10+100`，T6 校准为 LPC 实际公式）。每次循环消耗一次 `rng.rand(defense_factor)`，seed 链推进与 LPC 一致。 | 是（循环内 damage 修正是状态变更，按循环顺序入账本为 KIND_DAMAGE 的多次修正，不批量 apply） |
| **技能 action 描述** | 固定招式（`action_message` 从快照取，[context.py](../../engine/src/xkx/combat/context.py) 第 66 行） | 补 SkillData 载体：招式描述（`action`/`dodge`/`parry`/`damage`/`force`/`damage_type`/`post_action`）由 SkillData 声明（题材数据，武侠武学/非武侠武器各自的招式表），快照从 SkillData 取值而非固定。SkillData 结构主题无关（字段通用），具体招式内容由题材数据填充。`post_action` 回调（规格 side_effects order=47）按 functionp 语义在七步后处理阶段调用，返回值入 ledger。 | 是（招式描述文本在步骤 1 入 ledger 为 MESSAGE，`post_action` 副作用在步骤后处理入 ledger，按规格 order 交织） |

**补全顺序与 ConformanceChecker 联动**：6 项补全后，[conformance.py](../../engine/src/xkx/combat/conformance.py) 的 8 项检查中 `three_layer_resource_invariant`（simplified）与 `interleaving_order`（simplified）应升级为 implemented（因 riposte 递归 + hit_ob/hit_by mapping 补全后交织顺序更完整可验证）。impl_map（[ADR-0011](ADR-0011-spec-conformance-checker.md)）相应条目状态从 simplified -> implemented，ConformanceChecker 8 项检查全通过（无 violation，postponed 条目仍跳过）。

> s_combatd 阵法合击、perform/exert 完整实现、condition 具体状态类型不在 6 项简化台账内，仍后置（[ADR-0002](ADR-0002-resolve-attack-extraction.md) + [spec/layer_e_combat.py](../../engine/src/xkx/spec/layer_e_combat.py) 模块注释已标）。T6 不补这些。

### 5. test_theme_neutrality 硬门禁兜底 dissent 1 张力

dissent 1 的张力在 T6 的具体爆发点：补全简化台账（尤其 hit_ob/hit_by mapping、riposte 递归、skill_power 完整公式）时，可能无意中把武侠语义（武学回调链、武侠技能名、武侠资源池）锁进内核接口，导致"从武侠提取"过窄（锁死武侠语义）或"非武侠验证"失败（主题无关性回归）。

**T6 应对**（[ADR-0003](ADR-0003-combatkernel-theme-neutrality.md) 已立的硬门禁，T6 补全时必须持续通过）：

- **test_theme_neutrality 持续通过**：T6 补全 6 项简化台账的每一项后，[tests/test_theme_neutrality.py](../../engine/tests/test_theme_neutrality.py) 的 5 个断言必须全绿：
  - 非武侠 snapshot（firearm/ruler）跑 `resolve_attack`，武器->技能/标签映射走题材数据声明（不 fallback 到武侠默认）。
  - `inspect.getsource(resolve_attack)` 不含 `"sword"`/`"blade"` 字符串字面量（防回归硬门禁）。
  - `CombatantSnapshot.model_fields` 不含 `neili`/`max_neili`（内力不进核心签名）。
- **补全时的主题无关性检查点**：
  - hit_ob/hit_by mapping 分支：回调签名保持主题无关（入参为快照 + damage_bonus，返回 `str`/`int`/`mapping`），回调实现由题材数据声明，内核只做返回类型分发。若内核出现 `if skill == "force"` 或 `if weapon == "sword"` 等武侠特判，即触发 dissent 1 的"过窄"风险，须外提到题材数据。
  - riposte 递归：递归调用 `resolve_attack` 的参数（victim/me/weapon/attack_type）主题无关，riposte 触发条件（TYPE_REGULAR + damage<1 + guarding）不绑武侠语义。若 riposte 触发依赖武侠特有 skill（如"辟邪剑"），须外提到题材数据的回调。
  - skill_power 完整公式：`is_fighting()` 依赖战斗状态（快照内可判定，主题无关），`jingli_bonus`/`combat_exp` 补偿是通用资源池逻辑（不绑武侠）。若公式出现"经脉"/"穴位"等武侠概念，须外提到题材数据修饰链。
  - 技能 action 描述：SkillData 结构字段通用（`action`/`dodge`/`parry`/`damage`/`force`/`damage_type`/`post_action`），具体招式内容由题材数据填充。内核不解释招式名（如"试探"/"横扫"），只做 `$N`/`$n`/`$w`/`$l` 占位符替换。
- **dissent 1 张力的 T6 级裁决**：补全简化台账（保武侠深度）与 test_theme_neutrality 持续通过（保主题无关）的张力，靠"内核定义通用接口 + 题材数据声明武侠/非武侠具体值"的分层解决。内核接口（`resolve_attack` 签名、`CombatantSnapshot` 字段、Effect 类型、ledger 交织顺序）保持主题无关；武侠深度（武学回调链、门派技能表、武侠资源池语义）由题材数据声明，不进内核。这正是 [ADR-0003](ADR-0003-combatkernel-theme-neutrality.md) "映射外提到题材数据"模式的 T6 延续。

> 若 T6 补全某项时 test_theme_neutrality 回归（如内核出现武侠字面量、neili 进核心签名、非武侠 snapshot 走 fallback），即触发 dissent 1 的"过窄"风险，须暂停补全、先做主题无关性重构（外提到题材数据），再继续。这是 dissent 1 "靠阶段 -1 非武侠微场景硬门禁兜底"的 T6 实施期落地。

## 不做（范围边界）

- **不做全仿真确定性**：combat-only 确定性是正确范围（专家 2 承重论断 2），全仿真确定性后置 M3（[04](../xkx-arch/04-迁移路径与避坑清单.md) §六不做 + CLAUDE.md 不变量）。tick 驱动的其他 System（heal/exp/condition/effect）不进确定性重放。
- **不做跨 tick 连续重放**：T6 只做单 tick 快照 + input log 重放，多 tick 连续回放由 T8 Combat Replay Viewer 扩展（[12](../xkx-arch/12-阶段1-核心循环实施计划.md) T8）。
- **不做 s_combatd 阵法合击 / perform/exert 完整实现 / condition 具体状态类型**：不在 ADR-0002 简化台账 6 项内，仍后置（[spec/layer_e_combat.py](../../engine/src/xkx/spec/layer_e_combat.py) 模块注释已标）。
- **不做 CombatSystem 方法签名穷举**：本 ADR 只锁定承重决策（tick 驱动 + 快照边界 + input log + 确定性重放入口 + 不套 Command），具体方法签名由 T6 实现期定（收敛优先于完备）。
- **不做武器系统完整规格**：武器到技能/标签映射由题材数据声明（[ADR-0003](ADR-0003-combatkernel-theme-neutrality.md) 已定），T6 补的是 SkillData/WeaponData 声明结构，非内核武器枚举。武器系统完整规格后置阶段 0/2（[ADR-0002](ADR-0002-resolve-attack-extraction.md) §S1 简化表）。
- **不修改 LPC 源**（只读规格）。
- **不破坏七步交织**：6 项简化台账补全时，message 与 effect 按规格 side_effects order 交织入 ledger，不得"先算后 apply"（CLAUDE.md 不变量 + [05](../xkx-arch/05-第三轮专家对抗复审报告.md) 专家 3 承重论断 1）。
- **不扩展 ConformanceChecker 范围**：8 项检查不变，只升级 simplified -> implemented 状态（impl_map 相应条目），不新增检查项（[ADR-0011](ADR-0011-spec-conformance-checker.md) 范围）。

## 产出位置

- [combat/resolve_attack.py](../../engine/src/xkx/combat/resolve_attack.py)：补全 6 项简化台账（hit_ob/hit_by mapping 分支 + riposte 递归 + skill_power 完整公式 + combat_exp 防御折减完整循环 + SkillData 取招式描述）
- [combat/context.py](../../engine/src/xkx/combat/context.py)：`CombatantSnapshot` 扩展 hit_ob/hit_by 回调载体（mapping 分支）+ SkillData 引用
- [combat/result.py](../../engine/src/xkx/combat/result.py)：`CombatRoundResult` 扩展 riposte 子回合嵌入（ledger 嵌套）
- [combat/system.py](../../engine/src/xkx/combat/system.py)（新）：`CombatSystem`（tick 驱动 + 快照构建 + input log 记录 + apply_effects + replay 入口）
- [combat/replay.py](../../engine/src/xkx/combat/replay.py)（新）：`replay(snapshot, seed, input_log)` 纯函数重放入口
- [spec/impl_map.py](../../engine/src/xkx/spec/impl_map.py)：`three_layer_resource_invariant`/`interleaving_order` 状态 simplified -> implemented
- [tests/test_combat_system.py](../../engine/tests/test_combat_system.py)（新）：CombatSystem tick 驱动 + 确定性重放测试
- [tests/test_simplification_ledger.py](../../engine/tests/test_simplification_ledger.py)（新）：6 项简化台账补全的回归测试（含主题无关性断言）
- [tests/test_theme_neutrality.py](../../engine/tests/test_theme_neutrality.py)：持续通过（T6 补全后不回归）

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 1（CombatKernel 抽象时机张力）：T6 补全简化台账时 test_theme_neutrality 硬门禁兜底"从武侠提取（保深度）与非武侠验证（保主题无关）"的张力
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) 专家 2 承重论断 2（第 57 行）：combat-only 确定性是正确范围，全仿真确定性扩展到所有 System 是阶段 1 的错误范围
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) 专家 3 承重论断 1（第 69 行）：do_attack 七步文本与副作用交织不可分离（6 项补全须保持交织）
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 1（M1-6 combat 确定性）/ §六不做（全仿真确定性后置 M3）
- [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T6（本任务）/ T8（Combat Replay Viewer，多 tick 回放扩展）/ T9（combat-sim，确定性重放消费方）
- [ADR-0002](ADR-0002-resolve-attack-extraction.md)（resolve_attack 提取，S1 简化台账 6 项的来源）
- [ADR-0003](ADR-0003-combatkernel-theme-neutrality.md)（CombatKernel 主题无关性，test_theme_neutrality 硬门禁的来源）
- [ADR-0011](ADR-0011-spec-conformance-checker.md)（ConformanceChecker 8 项检查 + impl_map 三状态）
- [ADR-0012](ADR-0012-performance-microbenchmark.md)（PYTHONHASHSEED=0 跨进程一致性已验证，combat 确定性基础）
- [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)（T1 System 基类 + Effect 一等公民组件，CombatSystem 的基类）
- [ADR-0020](ADR-0020-command-pipeline-actioncontext-capability.md)（Command 仅覆盖外部意图，CombatSystem tick mutation 不走 Command）
- [spec/layer_e_combat.py](../../engine/src/xkx/spec/layer_e_combat.py)（do_attack 七步 + 31 处 random + 三层资源不变量 + skill_power 公式，T6 补全的规格基准）
