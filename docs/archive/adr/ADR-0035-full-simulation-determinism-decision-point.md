# ADR-0035：全仿真确定性决策点评估（M3 收官）

- 状态：已通过（2026-07-14）
- 日期：2026-07-14
- 阶段：M3 Wave 4（M3-5 全仿真确定性决策点评估，M3 收官）
- 关联：[04](../xkx-arch/04-迁移路径与避坑清单.md) §三 M3（M3-5 全仿真确定性决策点）/ §六不做（全仿真确定性后置 M3）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 7（派生变更审计覆盖缺口）+ 专家 2 承重论断 2（combat-only 确定性是正确范围）/ [16-M3](../xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) §三 M3-5 / [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md)（combat 确定性边界）/ [ADR-0012](ADR-0012-performance-microbenchmark.md)（PYTHONHASHSEED=0 验证）/ [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)（Effect 一等公民）/ [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md)（dirty-flag + Effect 序列化）

## 背景

[04](../xkx-arch/04-迁移路径与避坑清单.md) §三 M3 任务表第 5 项 + [16-M3](../xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) §三 M3-5：M3 后评估是否将确定性从 combat-only 扩展到所有 System（全仿真确定性）。本 ADR 是该决策点评估，M3-5 明确"只评估不实施"（[16-M3](../xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) §一不做清单）。

**combat-only 确定性现状**（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) 已落地，阶段 1 T6）：

- [combat/rng.py](../../engine/src/xkx/combat/rng.py) `DeterministicRNG(seed)`（`random.Random(seed)`，非 hash），替换 `resolve_attack` 18 处 `random()`，同 seed + 同快照 -> 同输出。
- [combat/context.py](../../engine/src/xkx/combat/context.py) `CombatContext`/`CombatantSnapshot` 快照（战斗开始边界一次性拷贝，`resolve_attack` 只读不 mutate）。
- [combat/replay.py](../../engine/src/xkx/combat/replay.py) `replay(snapshot, seed, input_log)` 纯函数重放入口，不依赖运行时 ECS。
- [combat/system.py](../../engine/src/xkx/combat/system.py) `CombatSystem.tick/replay`，input log 按 `seq` 顺序记录攻击输入。
- 跨进程一致（PYTHONHASHSEED=0，[ADR-0012](ADR-0012-performance-microbenchmark.md) 已验证基础）。

**dissent 7**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五第 7 条，第 183 行）：

> 派生变更审计覆盖缺口（Q3）：System.update 的 mutation（战斗外 exp/jingli、condition 效果、heal）无 Command 级审计轨迹。战斗有副作用账本覆盖，其他 System 逐个决定审计粒度。

**专家 2 承重论断 2**（[05](../xkx-arch/05-第三轮专家对抗复审报告.md) 第 57 行）：

> 全仿真确定性扩展到所有 System 是阶段 1 的错误范围；combat-only 确定性才是正确范围且已是 combat-sim 等价性的前置。

本 ADR 复核该裁决在 M3 收官时点是否仍成立，并给出全仿真确定性的成本/收益评估 + 决策建议。

## 决策

### 1. 现状画像：System 逐个 + 随机源实测（本次调研）

**System 全貌**（7 个 System + CombatBridge，tick 驱动派生变更处理器，[systems.py](../../engine/src/xkx/runtime/systems.py) 基类）：

| System | tick 驱动 | 随机源 | 审计轨迹（dissent 7） | 确定性现状 |
|---|---|---|---|---|
| CombatSystem | 是（combat） | 18 处 -> DeterministicRNG seeded | Effect 账本（ledger 交织）+ input log | ✅ 确定性范围内（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md)） |
| HealSystem | 是 | **无**（[heal.py](../../engine/src/xkx/runtime/heal.py) 注释"完全确定性无 random"） | **直接 mutate**（`vitals.jing += rate`，无 ledger，仅 mark_dirty） | 纯计算，同状态同输出 |
| ConditionSystem | 是 | **无**（[conditions.py](../../engine/src/xkx/runtime/conditions.py) 注释"无 random"） | Effect 账本（`ConditionTickResult.effects` + ledger） | 纯计算触发 + 账本 apply |
| GovernanceSystem | 是（非均匀 next_tick） | **无**（death_stage EffectComp 时序驱动） | EffectComp（Effect 一等公民组件，可序列化） | 确定性时序 |
| StorageSystem | 周期 persist | 无 | 非游戏逻辑 mutation（持久化） | 不在确定性范围 |
| ConnectionSystem | 连接事件 | 无 | 非游戏逻辑 mutation（会话） | 不在确定性范围 |
| CombatBridge | combat 桥接 | 无 | 转发 CombatSystem | 复用 combat 确定性 |

**全代码库随机源实测**（`grep random` 全 `src/xkx/`，排除 DeterministicRNG）：

| 位置 | 调用数 | 性质 | 确定性现状 |
|---|---|---|---|
| combat/resolve_attack | 18 | tick 内战斗 | ✅ DeterministicRNG seeded |
| runtime/account.py（天赋生成） | 3 | 角色创建一次性 | 系统 RNG（非 seeded） |
| runtime/race.py（属性生成） | 2 | 角色创建一次性 | **可注入 rng**（[race.py](../../engine/src/xkx/runtime/race.py) `setup_race(rng=)` 已支持，确定性测试范例） |
| runtime/title.py（稀有称谓） | 1 | 称谓查询时 | 系统 RNG |
| runtime/death.py（还阳延迟） | 1 | 死亡时一次性 | 系统 RNG |
| runtime/commands.py（learn 经验） | 1 | 练功命令时 | 系统 RNG |

**关键发现**：[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §决策1 假设的"范围外随机源"实测大多不存在：

- **NPC AI 决策**（[auto_fight.py](../../engine/src/xkx/runtime/auto_fight.py)）：**无 random**（确定性防御检查 + 回调分发，2.4 默认 no-op handler，具体战斗触发逻辑由题材数据注册）。
- **drop 掉落**：**未实现**（已知技术债，[commands.py](../../engine/src/xkx/runtime/commands.py) 无 drop）。
- **condition 触发**：**无 random**（ConditionSystem 注释明确）。

真正的范围外随机源只有 **command 路径 5 文件 8 处一次性随机**（角色创建/死亡/练功/称谓查询），全是外部意图触发的单次随机，非 tick mutation。

### 2. 成本评估（扩展到全仿真确定性）

| 成本项 | 评估 | 量级 |
|---|---|---|
| **seeded RNG 扩展面** | 仅 5 文件 8 处一次性随机需收口到 seeded RNG；race.py 已是注入 rng 范例。机械替换 + 种子链设计。 | 低 |
| **input log 扩展面** | 从"combat 内攻击序列"扩展到"所有外部意图 + 随机决策"；角色创建/死亡/练功/称谓查询的随机输入要进 input log + seed 链。input log schema 扩展 + 命令管线挂钩。 | 中 |
| **全量状态快照** | 从 `CombatContext`（combat 组件）扩展到全 ECS 组件 + 所有 System 状态；每 tick 全量快照（1000 实体 × 多组件），与 tick compute<100ms 预算 tension。 | 高 |
| **dissent 7 审计轨迹统一** | HealSystem 现直接 mutate（无 ledger），全仿真要 ledger 化；违背 dissent 7"逐个决定审计粒度"灵活性，强制所有 System mutation 走 Effect 账本。架构变更。 | 高 |
| **PYTHONHASHSEED=0 全局化** | 当前只 combat 需要（[ADR-0012](ADR-0012-performance-microbenchmark.md) 验证 combat 跨进程一致）；全仿真需全局 PYTHONHASHSEED=0（dict 迭代顺序确定）+ 禁 set 迭代。全局约束 + 全代码审查面。 | 中 |

**成本结构结论**：扩展全仿真的主要成本**不是 seeded RNG 扩展**（随机源极少，量级低），而是**全量状态快照 + dissent 7 审计轨迹统一 + PYTHONHASHSEED=0 全局化**（架构税，量级高）。

### 3. 收益评估

| 收益项 | 评估 | 价值 |
|---|---|---|
| **反作弊/数值审计** | combat-only 已覆盖最高频争议场景（战斗胜负/伤害）；全仿真扩展覆盖 heal/exp/condition，但这些争议价值低（自然恢复/经验增长争议少）。 | 中（边际递减） |
| **调试/bug 复现** | 全仿真可重放 -> 任意时刻状态可回溯；但 combat-only 已覆盖战斗 bug（最高频），heal/condition bug 可用日志 + 状态快照（非全仿真重放）定位。 | 中高 |
| **回放/观战** | 全仿真重放可做完整对局回放；但单机 demo 阶段无观战需求，后置外部玩家测试。 | 低（当前阶段） |

**收益结构结论**：全仿真收益主要在调试/bug 复现（中高），但 combat-only 已吃掉最高频的战斗 bug 价值；剩余 System（heal/condition 无 random）扩展确定性的边际收益低。

### 4. 决策建议：否决全仿真确定性实施，采纳 combat-only 为当前范围

**决策**：M3 收官时点，**否决全仿真确定性实施**，保持 [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) combat-only 确定性边界不变。保留"逐 System 按需纳入"的演进路径（部分采纳，非当前实施）。

**理由**：

1. **专家 2 承重论断 2 仍成立**：全仿真确定性扩展到所有 System 是错误范围，combat-only 确定性是正确范围且已是 combat-sim 等价性前置。M3-5 评估复核该裁决在 M3 收官时点无新证据推翻。
2. **成本高收益边际递减**：扩展成本主要是全量快照 + dissent 7 审计轨迹统一 + PYTHONHASHSEED=0 全局化（架构税，量级高），而 combat-only 已覆盖最高价值争议场景（战斗）。剩余 System（heal/condition）无 random，扩展确定性的边际收益低。
3. **dissent 7 主张"逐个决定审计粒度"**：全仿真强制统一审计粒度（所有 System 走 Effect 账本）违背该灵活性。正确做法是按需逐 System 纳入（如未来某 System 争议大，单独 ledger 化 + seeded）。当前 HealSystem 直接 mutate 是合理的"低审计粒度"选择（自然恢复无争议）。
4. **实测随机源画像支持该裁决**：tick 驱动 System 几乎都无 random（HealSystem/ConditionSystem/GovernanceSystem/auto_fight 全无 random），真正的范围外随机源只有 command 路径一次性随机（角色创建/死亡/练功），这些用"创建时记录 seed + 单次重放"即可（race.py 范式），不需要全仿真 input log 机制。
5. **触发条件后置**：全仿真确定性的真实触发条件是"分布式回放需求"（[04](../xkx-arch/04-迁移路径与避坑清单.md) §六：单进程达 80% 承载且 UGC 验证成立后引入分布式）或"反作弊/审计强需求"。单机 demo 阶段两者都不存在。

### 5. 演进路径（部分采纳，非当前实施）

全仿真确定性否决不等于永不考虑。保留以下按需演进路径，触发条件驱动（对齐 [04](../xkx-arch/04-迁移路径与避坑清单.md) §六"不做"清单的"附触发条件"原则）：

- **combat-only 确定性**：保持当前范围（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) 不变），不扩展。
- **command 路径一次性随机**（account/race/title/death/commands.learn）：未来若需角色创建/练功可复现（如反作弊审计玩家属性生成），按 race.py `setup_race(rng=)` 范式注入 seeded rng + 记录 seed 到存档（单次重放，非全仿真 input log）。race.py 已就位，其余 4 处待触发时补。
- **HealSystem/ConditionSystem**：保持直接 mutate + mark_dirty（dissent 7"逐个决定审计粒度"），不强制 ledger 化；若未来某 System 争议大（如 condition 触发概率被质疑），单独 ledger 化 + seeded。
- **PYTHONHASHSEED=0**：保持 combat 局部需求，不全局化（除非全仿真触发）。
- **全仿真确定性重新评估触发条件**（任一满足重新评估）：
  1. 分布式回放需求出现（单进程达 80% 承载 + UGC 验证成立，引入分布式后跨节点回放需要全仿真确定性）；
  2. 反作弊/数值审计强需求出现（外部玩家测试阶段，玩家属性生成/练功成长争议需要全链路可重放）；
  3. 完整对局观战/回放产品需求出现（外部玩家测试阶段，需要全仿真重放做观战）。

> 三条触发条件均与"外部玩家测试"或"分布式"分界线对齐（[04](../xkx-arch/04-迁移路径与避坑清单.md) §三后置阶段表），M3 内部 demo 阶段不触发。

## 不做（范围边界）

- **不做全仿真确定性实施**：本 ADR 是评估 + 决策，不实施（[16-M3](../xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) §一 M3-5"只评估不实施"）。combat-only 确定性仍是当前范围（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md)）。
- **不改 combat 确定性边界**：[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) 决策 1（combat-only 边界）不变，不扩展到 heal/exp/condition。
- **不强制所有 System ledger 化**：HealSystem 直接 mutate 保持现状（dissent 7"逐个决定审计粒度"），不因全仿真评估而提前统一。
- **不全局化 PYTHONHASHSEED=0**：保持 combat 局部需求（[ADR-0012](ADR-0012-performance-microbenchmark.md)），全仿真触发时才全局化。
- **不补 command 路径 seeded rng（当前）**：race.py 已支持注入 rng 作为范例，其余 4 处（account/title/death/commands.learn）待触发条件出现时补，不提前批量改造（收敛优先于完备）。
- **不写独立评估报告文档**：评估内容本 ADR 自包含（System 画像 + 成本收益矩阵 + 决策），不另起 arch 文档（PROGRESS.md 体量纪律 + 收敛优先）。

## 产出位置

- 本 ADR（[ADR-0035](ADR-0035-full-simulation-determinism-decision-point.md)）：评估 + 决策 + 演进路径，自包含。
- [PROGRESS.md](../../PROGRESS.md)：M3-5 完成 + M3 收官状态更新。
- 代码无变更（评估任务，不实施）。

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 7（第 183 行）：派生变更审计覆盖缺口，"其他 System 逐个决定审计粒度"--本 ADR 决策 4 理由 3 的依据。
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) 专家 2 承重论断 2（第 57 行）：combat-only 确定性是正确范围--本 ADR 复核仍成立。
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §三 M3（M3-5 决策点）/ §六不做（全仿真确定性后置 M3）/ §三后置阶段表（全仿真确定性触发条件：M3 后独立决策点）。
- [16-M3](../xkx-arch/16-M3-单题材武侠可玩demo实施计划.md) §三 M3-5（本任务）/ §一不做（M3-5 只评估不实施）。
- [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md)（combat 确定性边界，本 ADR 的范围基线，决策不变）。
- [ADR-0012](ADR-0012-performance-microbenchmark.md)（PYTHONHASHSEED=0 跨进程一致性，combat 确定性基础）。
- [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)（Effect 一等公民组件，GovernanceSystem/ConditionSystem 账本模式的基类）。
- [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md)（dirty-flag + Effect 序列化，HealSystem mark_dirty 的来源）。
