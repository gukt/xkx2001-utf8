# ADR-0018：ConditionHandler.on_tick 组合返回值契约

- 状态：草案（Wave 1 前置）
- 日期：2026-07-11
- 阶段：阶段 1 Wave 1 T1
- 关联：[04 §三](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 1 硬约束 / [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 7 / [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) Effect 一等公民 / [ADR-0011](ADR-0011-spec-conformance-checker.md) ledger 模式 / [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T1

## 背景

[04 §三](../xkx-arch/04-迁移路径与避坑清单.md) 阶段 1 硬约束："ConditionHandler.on_tick 返回组合结构契约落定"。

[05 §五](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent 7（派生变更审计覆盖缺口）：
- System.update 的 mutation（战斗外 exp/jingli、condition 效果、heal）无 Command 级审计轨迹
- 战斗有副作用账本覆盖，其他 System 逐个决定审计粒度

LPC condition 系统（`feature/condition.c`，113 行）：
- `update_condition()`：每 N tick（非均匀，5+random(10)）遍历所有条件，调用条件 daemon 的 `update_condition(this_object(), condition_info)`，返回 flag
- `apply_condition(cnd, info)`：应用条件（覆盖同名旧条件）
- `clear_one_condition(cnd)` / `clear_condition()`：清除
- `include/condition.h`：`CND_CONTINUE=1`（继续下次更新）/ `CND_NO_HEAL_UP=2`（阻止 heal_up）

[spec/layer_g_npc_ai.py](../../engine/src/xkx/spec/layer_g_npc_ai.py) heart_beat 步骤 7：tick 到 0 时 `update_condition()` 更新所有状态条件；非均匀 tick 衰减周期（5+random(10)）避免高频 CPU 开销。

combat 已有副作用账本模式（[ADR-0002](ADR-0002-resolve-attack-extraction.md) + [ADR-0011](ADR-0011-spec-conformance-checker.md)）：`resolve_attack` 返回 `CombatRoundResult`（messages + effects + ledger 交织），调用方 apply。ConditionHandler 需对齐此模式，使 condition 派生变更有审计轨迹。

## 决策

### 1. ConditionHandler 职责

ConditionHandler 是 condition 系统的核心，对应 LPC `feature/condition.c` 的 `update_condition()`：

- 管理实体上的持续 Effect（[ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) EffectComp 组件）
- 每 tick 检查哪些 EffectComp 到达 `next_tick`，触发其效果
- 返回组合结构（不直接 mutate 现场状态），由 ConditionSystem 统一 apply

### 2. on_tick 组合返回值契约

```python
@dataclass
class ConditionTickResult:
    """ConditionHandler.on_tick 的返回值（组合结构，不 mutate 现场状态）。"""
    effects: list[Effect]             # 即时副作用（DoT 扣血/heal 等），按触发顺序
    messages: list[str]               # 文本（毒发/醉倒等），按触发顺序
    condition_deltas: dict[str, int]  # {effect_id: 新剩余 duration}（衰减后）
    completed: list[str]              # 到期移除的 effect_id 列表
    flags: int = 0                    # LPC CND_NO_HEAL_UP(2) 等（跨 System 通信）
    ledger: list[LedgerEntry] = field(default_factory=list)  # 交织顺序（messages + effects）
```

**契约要点**：

1. **纯函数语义**：on_tick 只读 EffectComp 组件快照 + 当前 tick 编号，不 mutate 现场状态；所有变更产出为 Effect / condition_deltas / completed，由 ConditionSystem 统一 apply（对齐 combat 的 `resolve_attack -> apply_effects` 模式）
2. **交织顺序**：ledger 记录 messages 与 effects 的触发顺序（对齐 combat 的 `CombatRoundResult.ledger`，[ADR-0011](ADR-0011-spec-conformance-checker.md) 交织验证模式）
3. **组合而非单一返回值**：返回 `ConditionTickResult` 而非单 int（LPC 只返回 flag），因为 greenfield 需要完整审计轨迹（dissent 7）
4. **flags 跨 System 通信**：`CND_NO_HEAL_UP` 通过 flags 字段传递给 HealSystem（ConditionSystem 与 HealSystem 分离，但 condition 可阻止 heal）

### 3. 非均匀 tick 衰减

对齐 LPC 的 5+random(10) 非均匀周期（[spec/layer_g_npc_ai.py](../../engine/src/xkx/spec/layer_g_npc_ai.py)）：

- EffectComp 有 `tick_interval` + `next_tick` 字段（[ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)）
- ConditionHandler.on_tick 只处理 `next_tick <= current_tick` 的 EffectComp
- 触发后更新 `next_tick = current_tick + tick_interval`（tick_interval 可在创建时随机化，对齐 LPC 5+random(10)）
- **不每 tick 遍历所有 EffectComp**：ConditionSystem 维护 `next_tick` 最小堆（或有序结构），on_tick 只处理到期的（性能优化，1000 实体下避免全扫描）

**tick=1s 不变**（[CLAUDE.md](../../CLAUDE.md) 不变量）：全局 tick 仍是 1s，但 ConditionHandler 内部按 EffectComp 的 next_tick 非均匀触发，不是每 tick 都执行所有 condition。

### 4. 派生变更审计（dissent 7 落实）

dissent 7 要求"System.update 的 mutation 有审计轨迹"。ConditionHandler.on_tick 的组合返回值即审计轨迹：

- **effects 账本**：condition 扣血/heal 作为 Effect 记录，与 combat 即时 Effect 统一格式
- **condition_deltas**：duration 衰减记录（哪个 effect 衰减到多少）
- **completed**：到期移除记录
- **ledger 交织**：messages 与 effects 顺序可回放

ConditionSystem apply 后，`ConditionTickResult` 可归档到 audit_event（[04 §六](../xkx-arch/04-迁移路径与避坑清单.md) "高价值事件 audit_event"），形成 condition 派生变更的完整审计链。

**与其他 System 的审计粒度对齐**：
- combat：`CombatRoundResult.ledger`（已有，[ADR-0011](ADR-0011-spec-conformance-checker.md)）
- condition：`ConditionTickResult`（本 ADR）
- heal：HealSystem 返回类似结构（阶段 1 T1 后续补，复用 ConditionTickResult 模式）
- exp 增益（非战斗）：通过 Effect 账本记录（[ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) 即时 Effect）

## 不做（后置）

- **condition 具体类型实现**（蛇毒/醉/失明等）：阶段 1 T1 只定契约 + 框架，具体类型按 [08 §七](../xkx-arch/08-阶段-0-实施计划.md) "实现到时才补"
- **condition daemon 动态加载**：LPC `call_other(cnd_d, ...)` 的动态调度后置，阶段 1 condition 类型在代码中声明（非 UGC 可编辑，themed 治理可能部分平台级）
- **condition 优先级/覆盖规则**：同名 condition 覆盖（LPC `apply_condition` 覆盖旧条件）阶段 1 实现，复杂优先级后置
- **condition 可视化**：Entity Inspector 查看 EffectComp（[ADR-0013](ADR-0013-engine-toolchain-prd.md)），不单独建工具

## 关联

- [04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 1 硬约束（ConditionHandler.on_tick 返回组合结构契约落定）
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 7（派生变更审计覆盖缺口）：on_tick 组合返回值即审计轨迹
- [ADR-0002](ADR-0002-resolve-attack-extraction.md) + [ADR-0011](ADR-0011-spec-conformance-checker.md) combat 副作用账本模式（on_tick 对齐）
- [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) Effect 一等公民（持续 Effect 组件，on_tick 触发）
- [ADR-0014](ADR-0014-daemon-responsibility-redesign.md) ConditionSystem（ECS System 取代 daemon）
- [12](../xkx-arch/12-阶段1-核心循环实施计划.md) T1（ConditionHandler 契约落定）
- LPC 源：`feature/condition.c`（update_condition/apply_condition/clear_condition）/ `include/condition.h`（CND_CONTINUE/CND_NO_HEAL_UP）/ `inherit/char/char.c` heart_beat 步骤 7
