# ADR-0017：ECS SparseSet 选型 + Effect 一等公民组件设计

- 状态：草案（Wave 1 前置）
- 日期：2026-07-11
- 阶段：阶段 1 Wave 1 T1
- 关联：[04 §三](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 1 硬约束 / [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 7 / [ADR-0002](ADR-0002-resolve-attack-extraction.md) combat Effect / [ADR-0011](ADR-0011-spec-conformance-checker.md) ledger / [ADR-0014](ADR-0014-daemon-responsibility-redesign.md) System / [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T1

## 背景

阶段 1 T1（[12](../xkx-arch/12-阶段1-核心循环实施计划.md)）要求：
1. dict ECS 升级为 SparseSet（[runtime/ecs.py](../../engine/src/xkx/runtime/ecs.py) 现状是 dict 存储）
2. Effect 升级为一等公民组件（可序列化/可中断/可崩溃恢复，04 §三硬约束）
3. ConditionHandler.on_tick 组合返回值契约（[ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md)）

[04 §三](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 1 硬约束：
- Effect 必须可序列化、可中断、可崩溃恢复
- ConditionHandler.on_tick 返回组合结构契约落定

[05 §五](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent 7（派生变更审计覆盖缺口）：
- System.update 的 mutation（战斗外 exp/jingli、condition 效果、heal）无 Command 级审计轨迹
- 战斗有副作用账本覆盖，其他 System 逐个决定审计粒度

现状（阶段 -1 产出）：
- [combat/result.py](../../engine/src/xkx/combat/result.py) 的 Effect 是 combat-only pydantic 模型（6 种 kind：damage/wound/exp/potential/jingli/skill_improve），按交织顺序入 `CombatRoundResult.effects` 账本，apply 后不持久化
- [runtime/ecs.py](../../engine/src/xkx/runtime/ecs.py) 是 dict 存储（`entity_id -> {comp_type: comp}`），查询某类型所有组件需遍历全实体（O(total_entities)）

## 决策

### 1. SparseSet 选型（非 Archetype，非保留 dict）

ECS 存储从 dict 升级为 SparseSet：

- 每个组件类型一个 SparseSet（dense 数组存组件 + sparse 数组 `entity_id -> dense index`）
- 查询某类型所有组件：遍历 dense（O(count)）
- 查询某实体某组件：`sparse[eid] -> dense index`（O(1)）
- 添加/删除组件：O(1)
- API 对齐现有 `World`（create/query/attach/detach/entities_with/entities_in_room），调用方无感迁移

**不选 Archetype 的理由**：
1. 1000 实体规模下 SparseSet 查询足够快（[ADR-0012](ADR-0012-performance-microbenchmark.md) μs 基准已证 resolve_attack 25.9μs，SparseSet 查询开销在 μs 级）
2. Archetype 面向缓存友好的批量查询 + 大量实体（>10k），1000 实体 + tick=1s 不是瓶颈
3. Archetype 添加/删除组件需移动实体到另一个 archetype，Effect 频繁 attach/detach 开销大
4. [04 §六](../xkx-arch/04-迁移路径与避坑清单.md) "不过早抽象" + "GC 是非问题"；dict -> SparseSet 是平滑升级（API 不变），Archetype 是架构重写
5. 若 T10 压测发现查询瓶颈，再评估 Archetype（kill criteria 3/6 触发时的优化备选）

**不保留 dict 的理由**：dict 查询某类型所有组件需遍历全实体（O(total_entities)），1000 实体 + 多 System 每 tick 查询会放大开销；SparseSet 查询 O(count) 是必要优化。

### 2. Effect 一等公民组件设计

Effect 从 combat-only pydantic 模型升级为 ECS 一等公民组件，承载所有 System 的派生变更。

**两类 Effect**：

| 类型 | 来源 | apply 时机 | 持久化 |
|---|---|---|---|
| 即时 Effect | combat（`CombatRoundResult.effects`）/ quest 奖励 / exp 增益 | 立即 apply 到组件，不入 Effect 组件 | 不持久化（账本已记录） |
| 持续 Effect | condition（毒/醉/失明）/ buff（临时属性加成）/ DoT | 作为 Effect 组件 attach 到实体，每 tick 触发 | 持久化（存档含剩余 duration / next_tick） |

**持续 Effect 组件 schema 草案**（T1 实现时定 dataclass vs pydantic，与现有 [components.py](../../engine/src/xkx/runtime/components.py) dataclass 风格对齐）：

```python
@dataclass
class EffectComp:
    effect_id: str          # 唯一标识（存档/取消用）
    kind: str               # damage/wound/heal/buff/debuff/...（扩展 combat 6 种）
    target_id: int          # 作用实体
    source_id: int = 0      # 来源实体（施毒者/施法者）
    amount: int = 0         # 每 tick 数值（DoT 扣血量 / buff 加成）
    detail: str = ""        # 附加信息（damage_type / skill_id / condition_name）
    duration: int = 0       # 剩余 tick 数（0=永久，需显式取消）
    tick_interval: int = 1  # 触发间隔（非均匀 tick：LPC 5+random(10)）
    next_tick: int = 0      # 下次触发的 tick 编号
    flags: int = 0          # LPC CND_CONTINUE(1) / CND_NO_HEAL_UP(2)
```

**04 §三硬约束落实**：

- **可序列化**：EffectComp 作为 ECS 组件，随实体序列化为 JSON（T5 存档）；字段全部为基本类型（int/str），无闭包/函数引用
- **可中断**：`world.remove(eid, EffectComp)` 或按 `effect_id` 取消（对应 LPC `clear_one_condition`）；中断时记录审计 Effect（被取消的 effect_id）
- **可崩溃恢复**：EffectComp 持久化到存档（含 duration/next_tick），崩溃冷重启后从 checkpoint 恢复未完成 Effect 状态；恢复时 `next_tick` 对齐当前 tick 编号（跳过崩溃期间未执行的 tick，非补执行--补执行会破坏 combat 确定性）

### 3. Effect 与 combat 副作用账本的统一

combat 的 `CombatRoundResult.effects`（即时 Effect）与持续 Effect 组件统一为 Effect 概念，但 apply 路径不同：

- **即时 Effect**：CombatSystem 调 `resolve_attack` -> `CombatRoundResult.effects` -> `apply_effects`（[world.py](../../engine/src/xkx/runtime/world.py) 现有）立即 apply 到 Vitals/Skills 等组件，不创建 EffectComp
- **持续 Effect**：ConditionSystem / BuffSystem 的 `on_tick` 返回 Effect（kind=poison/buff 等）-> System 创建 EffectComp attach 到实体 -> 后续 tick 由 ConditionHandler.on_tick 触发（[ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md)）

**dissent 7 落实**：
- combat 即时 Effect 已有副作用账本（`CombatRoundResult.ledger`，[ADR-0011](ADR-0011-spec-conformance-checker.md) 交织验证）
- 持续 Effect 的派生变更（condition 扣血/heal）通过 ConditionHandler.on_tick 组合返回值记录（[ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md)），形成统一审计轨迹
- 其他 System（heal/exp 增益）逐个定审计粒度，默认通过 Effect 账本记录

## 不做（后置）

- **Archetype 查询缓存**：T10 压测发现瓶颈才评估（kill criteria 3/6 触发时）
- **Effect DAG 调度**：Effect 依赖图（A 触发 B）后置，阶段 1 Effect 独立触发
- **Effect 优先级排序**：同 tick 多 Effect 触发顺序后置（阶段 1 按 attach 顺序）
- **对象池化**：EffectComp 对象池后置（[ADR-0012](ADR-0012-performance-microbenchmark.md) 已测 GC 是非问题，T10 实测后决定，04 §六）
- **Effect 可视化/调试**：Entity Inspector 只读查看 EffectComp（[ADR-0013](ADR-0013-engine-toolchain-prd.md)），不单独建工具

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 7（派生变更审计覆盖缺口）：Effect 一等公民 + ConditionHandler.on_tick 账本（[ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md)）共同覆盖战斗外派生变更审计
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 1 硬约束（Effect 可序列化/可中断/可崩溃恢复）
- [ADR-0002](ADR-0002-resolve-attack-extraction.md) combat Effect（即时 Effect 的来源）
- [ADR-0011](ADR-0011-spec-conformance-checker.md) CombatRoundResult ledger（即时 Effect 交织验证）
- [ADR-0014](ADR-0014-daemon-responsibility-redesign.md) System 基类（Effect 由 System 创建/触发）
- [ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md) ConditionHandler.on_tick（持续 Effect 的触发契约）
- [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T1（ECS 骨架升级）/ T5（JSON 存档，Effect 崩溃恢复）/ T6（combat 确定性，即时 Effect）
- LPC 源：`feature/condition.c`（update_condition/apply_condition/clear_condition）/ `include/condition.h`（CND_CONTINUE/CND_NO_HEAL_UP）
