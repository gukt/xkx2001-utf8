# ADR-0027：call_out -> Effect 翻译 + 阵法合击 CombatModifier + golden trace diff 协议

- 状态：草案（Wave 3 2.4 Combat 前置）
- 日期：2026-07-12
- 阶段：阶段 2 Wave 3 2.4
- 关联：[04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 2 Combat 迁移专项（call_out 144 处 + s_combatd 阵法合击 + golden trace）/ [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 1（CombatKernel 抽象时机）+ dissent 4（基线测试）+ dissent 7（派生变更审计）/ [15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.4 / [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md)（combat-only 确定性 + 简化台账 6 项，已实现）/ [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)（Effect 一等公民）/ [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md)（Effect 崩溃恢复）/ [ADR-0003](ADR-0003-combatkernel-theme-neutrality.md)（主题无关性）/ [ADR-0009](ADR-0009-original-driver-runnable.md)（driver 可运行，golden trace 定点辅助）

## 背景

[15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.4 任务卡（第 136-149 行）：补全阶段 1 T6 剩余项 + 行为等价验证 + 文本体验流 diff。验收：ConformanceChecker 8 项全通过 + golden trace diff 无语义差异 + 文本体验流 diff 可接受。

[04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 2 Combat 迁移专项列出三项 ADR-0023 未触及的承重决策：

1. **闭包型 call_out（144 处）翻译为 Effect**（[04](../xkx-arch/04-迁移路径与避坑清单.md) 第 178 行）
2. **s_combatd.c 阵法合击规格 -> CombatModifier**（[04](../xkx-arch/04-迁移路径与避坑清单.md) 第 179 行）
3. **数值回归基线（golden trace 对比）+ 文本体验流 diff**（[04](../xkx-arch/04-迁移路径与避坑清单.md) 第 180-181 行）

**ADR-0023 已覆盖 vs 未触及**（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §不做 第 127 行明确）：

- ✅ ADR-0023 已覆盖：combat-only 确定性边界 + CombatSystem 设计 + 单 tick 快照 + input log 重放协议 + 简化台账 6 项（hit_ob/hit_by mapping / riposte 递归 / 武器类型 / skill_power / combat_exp 防御折减 / 技能 action）
- ❌ ADR-0023 明确不做（本 ADR 承接）：s_combatd 阵法合击、perform/exert 完整实现、condition 具体状态类型、**call_out 翻译**（ADR-0023 未提及，因 T6 范围只到单 tick resolve_attack，不触及跨 tick 延迟调用）

**LPC 源码勘察事实**（本 ADR 决策的实证基础）：

| 主题 | LPC 事实 | 文件/行号 |
|---|---|---|
| call_out 典型样本 1 | `call_out("revive", random(100-query("con"))+30)` -- 昏迷后延迟苏醒（30-129 秒，可被 die 的 remove_call_out 取消） | [feature/damage.c:134](../../feature/damage.c#L134) |
| call_out 典型样本 2 | `remove_call_out("revive")` -- die/unconcious 时取消延迟唤醒 | [feature/damage.c:139,174](../../feature/damage.c#L139) |
| call_out 典型样本 3 | `call_out("start_"+type, 0, me, obj)` -- auto_fight 延迟 0 秒启动（给 victim 逃脱机会，异步执行 start_berserk/hatred/vendetta/aggressive） | [adm/daemons/combatd.c:866](../../adm/daemons/combatd.c#L866) |
| s_combatd.c 真实职责 | combatd 的"带 damage_msg 文本"副本（damage_msg/eff_status_msg/status_msg 消息函数 + fight/auto_fight/reward 系列），**非阵法合击** | [adm/daemons/s_combatd.c](../../adm/daemons/s_combatd.c) 974 行 |
| 阵法合击入口 | `special_attack(opponent)` 检查 `query_temp("stand/anubis")` 阵法标记，命中则调 `S_COMBAT_D->fight(ob, opponent)` 走阵法战斗 | [feature/attack.c:197-206](../../feature/attack.c#L197) |
| 阵法合击具体逻辑 | kungfu/skill/ 题材脚本：pozhen.c（破阵）/ buzhen.c（布阵）/ heji.c（合击，双武器 perform）/ dagou.c / youshen-zhang.c + kungfu/class/quanzhen/zhao.c | [kungfu/skill/](../../kungfu/skill/) |
| golden trace baseline | 已录制 combat_huashan 14 回合（玩家 vs 凌逍），概率统计 dodge 26.67%/hit 73.33%/parry 0% | [engine/tools/golden_trace/baseline/](../../engine/tools/golden_trace/baseline/) |

**三项 dissent 在 2.4 的爆发点**：

- **dissent 1**（CombatKernel 抽象时机张力）：call_out 翻译 + 阵法合击接口设计时，可能把武侠语义（阵法名/anubis 标记/武侠 call_out 回调链）锁进内核。靠 test_theme_neutrality 硬门禁兜底（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §决策 5 已立，本 ADR 延续）。
- **dissent 4**（基线测试）：golden trace 是行为等价验证的基准。driver 可运行（[ADR-0009](ADR-0009-original-driver-runnable.md)）使定点录制可行，但 golden trace 定位为**辅助验证**非主线门禁（主线是单元级行为规约 + ConformanceChecker）。
- **dissent 7**（派生变更审计）：call_out 翻译为 Effect 后，跨 tick 的延迟副作用必须有审计轨迹。EffectComp ledger（[ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md) ConditionTickResult）+ combat ledger（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §决策 3）已奠定交织账本基础，本 ADR 明确 call_out 翻译如何接入。

## 决策

### 1. call_out -> EffectComp 翻译策略（dissent 1/7）

#### 1.1 翻译范围：combat 直接相关，非全库 144 处

[04](../xkx-arch/04-迁移路径与避坑清单.md) "144 处"是全库 combat 相关 call_out 的统计上界。2.4 按"实现到时才补"原则（[08](../xkx-arch/08-阶段-0-实施计划.md) §七），只翻译 combat 核心路径直接相关的闭包型 call_out：

| call_out 样本 | 翻译为 | 2.4 处置 |
|---|---|---|
| `damage.c:134` `call_out("revive", random(100-con)+30)` | EffectComp（condition=revive，duration=系统 RNG 采样值，target=eid） | ✅ 翻译（2.2 death.py revive 已用系统 RNG，2.4 衔接 EffectComp 化） |
| `damage.c:139,174` `remove_call_out("revive")` | EffectComp 中断（标记 cancelled/completed） | ✅ 翻译（2.2 已有 clear_condition 语义，2.4 确认 EffectComp 中断契约） |
| `combatd.c:866` `call_out("start_"+type, 0, me, obj)` | EffectComp（condition=start_berserk/hatred/vendetta/aggressive，duration=0，target=victim eid）或同步执行 | ✅ 翻译（auto_fight 延迟启动，2.4 定 duration 语义） |
| `s_combatd.c:762` 同上（s_combatd 是 combatd 副本） | 同上（greenfield 不保留 s_combatd 副本，统一走 combatd 路径） | ✅ 合并 |
| NPC AI chat call_out（heart_beat 随机对话延迟） | EffectComp | ⏸ 后置（layer G NPC AI，2.4 不触及，M3 补） |
| 门派脚本 call_out（kungfu/ perform/exert 延迟） | EffectComp | ⏸ 后置（2.7 门派切割 / M3） |
| condition 定时 call_out（蛇毒周期等） | EffectComp | ✅ 2.2 已做（condition handler 机制，[ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md)） |

**范围红线**：2.4 翻译 revive + start_ + remove_call_out 三类核心（约 10 处），其余后置。若实现中发现 combat 行为等价验证需要更多 call_out 翻译，按"实现到时才补"逐个补，不批量穷尽。

#### 1.2 闭包型 call_out -> EffectComp 翻译契约

LPC `call_out(func, delay, args)` 的语义三要素：**延迟执行**（delay 秒后调 func）+ **可取消**（remove_call_out）+ **闭包参数**（args 绑定调用时现场）。翻译为 EffectComp：

| LPC 语义 | EffectComp 字段/机制 | 已有基础 |
|---|---|---|
| 延迟 delay 秒 | `duration`（tick 数，delay/tick_interval） | [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) EffectComp |
| 可取消 remove_call_out | EffectComp 中断（ConditionSystem clear / EffectComp cancelled 标记） | [ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md) + 2.2 clear_condition |
| 闭包参数 args | EffectComp 载荷字段（condition_kind + target_id + source_id + 参数） | [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md) EffectComp 可序列化 |
| 崩溃恢复 | duration 不衰减（时间冻结）+ next_tick 对齐 + 悬空 target_id 跳过 | [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md) §Effect 崩溃恢复 |
| 审计轨迹（dissent 7） | EffectComp on_tick 产 ConditionTickResult ledger（effects/messages/condition_deltas/completed/flags/ledger 交织） | [ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md) |

**revive 翻译示例**（damage.c:134）：

- LPC：`call_out("revive", random(100-query("con"))+30)` -- 昏迷后 30-129 秒苏醒
- greenfield：`EffectComp(condition="revive", target_id=eid, duration=系统RNG.randint(30, 129), source_id=eid)`
- `random(100-con)+30` 的 RNG：**系统 RNG 非 DeterministicRNG**（revive 属 ConditionSystem 范畴，不在 combat-only 确定性边界内，[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §决策 1 已定边界）
- `remove_call_out("revive")`（die 时）：`clear_condition(world, eid, "revive")` -- 2.2 已实现

**start_ 翻译示例**（combatd.c:866）：

- LPC：`call_out("start_"+type, 0, me, obj)` -- auto_fight 延迟 0 秒启动（给 victim 逃脱机会）
- greenfield 决策：`duration=0` 的 EffectComp（下一 tick 执行 start_* 逻辑）**或**同步执行 start_* 逻辑（greenfield 无 call_out 异步语义，start_* 的"给 victim 逃脱机会"语义改为"下一 tick 检查 me/environment 仍有效才执行"，对齐 LPC start_berserk 开头的 `if (!me || !obj) return` 防御）
- **2.4 倾向同步执行 + 防御检查**：LPC `call_out(..., 0, ...)` 延迟 0 秒本质是"异步推迟到当前 heart_beat 结束"，greenfield 单线程 tick 内同步调 start_* 逻辑 + 防御检查（me/obj/environment 有效性）行为等价，且避免 duration=0 EffectComp 的语义复杂度。若行为等价验证发现差异（如 victim 需在"当前 tick 结束前"溜走），改为 duration=1 EffectComp。

#### 1.3 主题无关性（dissent 1 兜底）

call_out 翻译的 EffectComp 字段主题无关（condition_kind/target_id/duration/source_id 通用）。revive/start_berserk/start_hatred 等条件名是**通用战斗语义**（非武侠特有），不进 test_theme_neutrality 的字面量黑名单。若实现中出现武侠特有 call_out（如"点穴"/"封经"），须外提到题材数据的 condition 声明，内核只做通用 EffectComp 分发。

### 2. s_combatd 阵法合击 CombatModifier 接口（dissent 1）

#### 2.1 关键事实：阵法合击是题材内容，非 combat 内核

LPC 源码勘察确认：

- `s_combatd.c` **不是阵法合击**，是 combatd 的"带 damage_msg 文本"副本（[adm/daemons/s_combatd.c](../../adm/daemons/s_combatd.c) 974 行，函数列表：damage_msg/eff_status_msg/status_msg + fight/auto_fight/winner_reward/death_penalty/killer_reward）。greenfield 不保留 s_combatd 副本，damage_msg 文本生成走 SkillData/damage_type 声明（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §决策 4 第 6 项 SkillData 载体已定）。
- 阵法合击入口：[feature/attack.c:197](../../feature/attack.c#L197) `special_attack(opponent)`，检查 `query_temp("stand/anubis")` 阵法标记，命中则调 `S_COMBAT_D->fight(ob, opponent)` 走阵法战斗路径。
- 具体阵法逻辑在 [kungfu/skill/](../../kungfu/skill/) 题材脚本：pozhen.c（破阵）/ buzhen.c（布阵）/ heji.c（合击，双武器 perform）/ dagou.c / youshen-zhang.c + [kungfu/class/quanzhen/zhao.c](../../kungfu/class/quanzhen/zhao.c)。

**裁决**：阵法合击是**题材内容**（kungfu/skill/ 武学脚本），走 SkillData/FormationData 声明，不进 combat 内核。这与 [ADR-0003](ADR-0003-combatkernel-theme-neutrality.md) 主题无关性 + [15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.7 门派切割边界一致：kungfu/class + kungfu/skill 是题材包资产，核心引擎不硬编码。

#### 2.2 CombatModifier 通用接口（主题无关）

CombatModifier 是"题材数据注入 combat 内核做攻击修正"的**声明式载体**（类似 [HitCallbackResult](../../engine/src/xkx/combat/context.py)/[SkillData](../../engine/src/xkx/combat/context.py)），内核只做分发，具体阵法逻辑由题材数据声明：

```python
# combat/modifier.py（新建，主题无关）
@dataclass(frozen=True, slots=True)
class CombatModifier:
    """阵法/合击等多人协同攻击修正的声明式载体（题材数据注入）。"""
    modifier_type: str          # "formation" / "formation_break" / "combined_attack"
    participants: tuple[int, ...]  # 参与者 eid 列表（主题无关，int）
    attack_modifier: int        # ap 修正（加成/惩罚）
    defense_modifier: int       # dp 修正
    message: str                # 阵法文本（含 $N/$n 占位符，PronounContext 渲染）
    post_action: str | None     # 回调名（题材数据声明的 post_action，内核不解释）
```

**内核职责**（主题无关，只做分发）：

- CombatSystem tick 中，调 `resolve_attack` 前检查参战双方的"阵法标记"（Marks/stand/* 或独立 FormationComp）。
- 若命中阵法标记，从题材数据查 CombatModifier，注入 `resolve_attack` 的 `CombatContext` 快照（ap/dp 修正 + message + post_action）。
- `resolve_attack` 只读 CombatModifier 做数值修正 + message 入 ledger（按交织顺序），**不解释阵法名/阵法逻辑**。
- post_action 回调按 [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §决策 4 第 6 项 SkillData post_action 语义（order=47，声明式副作用入 ledger）。

**题材数据职责**（武侠/非武侠平等走同一声明路径）：

- 武侠阵法：kungfu/skill/ 的 pozhen/buzhen/heji 翻译为 FormationData 声明（modifier_type + participants + 修正值 + message + post_action 回调）。
- 非武侠题材：若未来非武侠题材有"协同攻击"（如大航海的"舷炮齐射"），走同一 CombatModifier 接口。

#### 2.3 special_attack 调用点翻译

[feature/attack.c:208-227](../../feature/attack.c#L208) `attack()` 函数（heart_beat 每 tick 调用）：

```c
int attack() {
    opponent = select_opponent();
    if (objectp(opponent)) {
        if (!(special_attack(opponent)))       // 阵法合击检查
            COMBAT_D->fight(this_object(), opponent);  // 普通战斗
        return 1;
    }
}
```

greenfield 翻译（CombatSystem tick）：

- `select_opponent` -> CombatSystem 选对手（已有，[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §决策 2）
- `special_attack(opponent)` -> CombatSystem 调 `resolve_attack` 前检查阵法标记（Marks/stand/* 或 FormationComp），命中则注入 CombatModifier
- `COMBAT_D->fight` -> `resolve_attack`（七步管线）

**阵法标记载体**：`stand/anubis` 是 LPC `set_temp("stand/anubis", 1)` 的 temp 标记。greenfield 用 **Marks 组件**（`marks/stand/anubis`，[ADR-0006](ADR-0006-accept-object-inquiry-set-flag.md) 已立 Marks 组件）或独立 FormationComp。2.4 倾向 Marks（轻量，复用已有组件），若阵法状态复杂（多字段）再升 FormationComp。

#### 2.4 2.4 范围：只定接口 + 调用点，不实现具体阵法

| 2.4 做 | 2.4 不做（后置） |
|---|---|
| CombatModifier 声明式载体（主题无关字段） | 具体阵法逻辑（pozhen/buzhen/heji 翻译为 FormationData） |
| CombatSystem special_attack 调用点（检查阵法标记 -> 注入 CombatModifier） | kungfu/skill/ 武学脚本转译 |
| CombatModifier 注入 resolve_attack 的快照路径（ap/dp 修正 + message + post_action） | perform/exert 命令完整实现（后置 M3） |
| test_theme_neutrality 扩展（内核无"阵法"/"合击"/"anubis"字面量） | 阵法标记的题材数据填充（2.7 门派切割） |

**后置理由**：阵法合击的具体实现依赖 kungfu/skill/ 武学脚本转译，属 2.7 门派切割 + M3 范围。2.4 只定"内核如何接受题材数据注入阵法修正"的接口，确保 2.7 门派切割时阵法内容可干净剥离为题材包资产（[04](../xkx-arch/04-迁移路径与避坑清单.md) §五检查点 8 硬门禁）。

### 3. golden trace 录制/diff 协议（dissent 4）

#### 3.1 定位：定点辅助验证，非主线门禁

**主线门禁**（行为等价验证的权威）：

1. 单元级行为规约（[spec/layer_e_combat.py](../../engine/src/xkx/spec/layer_e_combat.py) 26 函数 + 49 副作用 order + 31 random 概率模型）
2. ConformanceChecker 8 项（[ADR-0011](ADR-0011-spec-conformance-checker.md)）
3. combat-sim 确定性重放（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §决策 3，replay 纯函数）

**golden trace 定位**（[ADR-0009](ADR-0009-original-driver-runnable.md) 定点辅助）：

- 仅在"难以从代码静态推断"处定点录制运行时行为，提升行为等价验证置信度
- 不录全量命令流（8412 文件不可穷尽，[ADR-0009](ADR-0009-original-driver-runnable.md)）
- baseline 已录制（[engine/tools/golden_trace/baseline/](../../engine/tools/golden_trace/baseline/)），14 回合 do_attack 七步文本 + 概率统计

#### 3.2 diff 协议三层

golden trace diff 分三层，对照 LPC baseline 与 greenfield resolve_attack 输出：

| 层 | diff 对象 | 方法 | 容差 | 依据 |
|---|---|---|---|---|
| **L1 概率分布 diff** | dodge/hit/parry 频率 | 多次采样取分布，对照 layer_e 31 处 random 概率模型（dp/(ap+dp)/pp/(ap+pp)/1-d-p） | 卡方检验或区间匹配（非逐字，因 LPC random() 每次不同） | [spec/layer_e_combat.py](../../engine/src/xkx/spec/layer_e_combat.py) RandomSpec |
| **L2 文本结构 diff** | do_attack 七步文本结构 | 按回合分隔 + ANSI 剥离 + 七步结构匹配（取招式/AP-DP/闪避/招架/伤害/状态/行为） | 伤害描述分类映射（瘀青/瘀伤/肿 -> greenfield damage 区间），非逐字 | [README §八](../../engine/tools/golden_trace/README.md) 七步文本结构实测 |
| **L3 语义 diff** | 占位符渲染 | $N/$n/$w/$l 占位符对照 PronounContext 渲染（2.5 已落地） | 文本表述差异标记（如 $C/$c 角色互换） | [ADR-0028](ADR-0028-rank-d-spec-and-pronoun-context.md) PronounContext |

**L1 概率分布 diff 细节**（dissent 4 核心）：

- baseline 概率（14 回合，n=15）：dodge 26.67% / hit 73.33% / parry 0%
- greenfield 用同属性 CombatantSnapshot + 多 seed 采样（如 1000 次 resolve_attack），统计 dodge/hit/parry 频率
- 对照 layer_e 概率模型：dodge_p = dp/(ap+dp)，parry_p = pp/(ap+pp)，hit_p = 1-d-p
- **判定**：greenfield 采样分布与 LPC 概率模型理论值一致（卡方检验 p>0.05 或区间匹配），且与 baseline 实测分布不显著偏离。baseline 样本小（n=15），主要对照理论模型，baseline 实测作参考。
- **2.4 实施期补充**：wield 武器 + 找弱 NPC（monkey combat_exp 30）补 30+ 回合提升置信度（[README §十一](../../engine/tools/golden_trace/README.md) 计划）

**L2 文本结构 diff 细节**：

- 按回合分隔：combat heart_beat 1 回合/秒，按"攻击动作行"切分回合
- ANSI 剥离：raw 保留 ANSI，clean 已剥离（[baseline/combat_huashan_clean.txt](../../engine/tools/golden_trace/baseline/combat_huashan_clean.txt)）
- 七步结构匹配：每回合 7 步文本（取招式 / AP-DP / 闪避 / 招架 / 伤害 / 状态 / 行为），逐步对照 greenfield resolve_attack ledger 的 message 输出
- 伤害描述分类映射：LPC 伤害文本是描述性（瘀青/瘀伤/肿/轻伤/重伤），非数值；greenfield damage 输出按区间映射到描述分类（[s_combatd.c damage_msg](../../adm/daemons/s_combatd.c) 行 71-168 的 damage 区间 -> 描述文本）

#### 3.3 diff 工具

新建 [engine/tools/golden_trace/diff.py](../../engine/tools/golden_trace/diff.py)（2.4 实施期）：

- 消费 baseline（combat_huashan_clean.txt + combat_stats.json）+ greenfield resolve_attack 输出（同属性 CombatantSnapshot + 多 seed 采样）
- 三层 diff 报告：L1 概率分布对照 + L2 七步文本结构 diff + L3 占位符渲染 diff
- CLI：`python -m tools.golden_trace.diff --baseline baseline/ --greenfield <combat_sim_json>`
- 非侵入：只消费 ledger 与 baseline，不修改 combat 内核（对齐 [ADR-0013](ADR-0013-engine-toolchain-prd.md) Combat Replay Viewer 非侵入设计）

#### 3.4 diff 判定标准

| 层 | 通过标准 | 不通过应对 |
|---|---|---|
| L1 概率分布 | greenfield 采样分布与 LPC 概率模型理论值一致（卡方 p>0.05 或区间匹配） | 先查 seed 链/RNG 推进顺序是否与 LPC 一致 -> 修 -> 仍不通过触发 2.4 kill criteria |
| L2 文本结构 | 七步结构匹配 + 伤害描述分类映射一致（非逐字） | 先查 SkillData 招式表/damage_msg 映射 -> 补 -> 语义差异可接受则标记通过 |
| L3 语义 | 占位符渲染与 PronounContext 一致 | 查 PronounContext 求值（2.5 已落地，回归则修 pronoun.py） |

**2.4 kill criteria**（[15](../xkx-arch/15-阶段2-子系统实施计划.md) §七）：golden trace diff 有语义差异 + ConformanceChecker 不通过 -> 先补全 combat-sim 简化台账 -> 仍失败暂停 Combat 迁移，回退 T6 状态。

## 不做（范围边界）

- **不做全库 144 处 call_out 穷尽翻译**：2.4 只翻译 combat 核心路径（revive + start_ + remove_call_out，约 10 处），NPC AI chat / 门派脚本 / condition 定时后置（按"实现到时才补"原则）。
- **不做 s_combatd 副本保留**：s_combatd 是 combatd 的带文本副本，greenfield 统一走 combatd 路径 + SkillData/damage_msg 声明，不保留 s_combatd 副本。
- **不做阵法合击具体实现**：2.4 只定 CombatModifier 接口 + special_attack 调用点，具体阵法（pozhen/buzhen/heji）后置 2.7 门派切割 / M3。
- **不做 perform/exert 完整实现**：后置 M3（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §不做）。
- **不做 golden trace 全量录制**：定点辅助（combat 七步 + 概率统计），不录全量命令流（[ADR-0009](ADR-0009-original-driver-runnable.md)）。
- **不做 golden trace 作为主线门禁**：主线门禁是单元级行为规约 + ConformanceChecker + combat-sim，golden trace 是辅助验证（[ADR-0009](ADR-0009-original-driver-runnable.md)）。
- **不做跨 tick 连续重放的 golden trace diff**：2.4 diff 基于单回合采样 + 概率分布，多 tick 连续回放 diff 后置（T8 Combat Replay Viewer 扩展，[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §决策 2）。
- **不修改 LPC 源**（只读规格）。
- **不破坏七步交织**：call_out 翻译为 EffectComp 后，延迟副作用按 EffectComp on_tick 的 ConditionTickResult ledger 交织（[ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md)），combat 内 resolve_attack 的 message/effect 仍按 [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) ledger 交织，不得"先算后 apply"。
- **不扩展 combat-only 确定性边界**：call_out 翻译的 EffectComp（revive/start_）属 ConditionSystem 范畴，不进 combat-only 确定性重放（[ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md) §决策 1 边界红线）。

## 产出位置

- [engine/src/xkx/combat/modifier.py](../../engine/src/xkx/combat/modifier.py)（新）：CombatModifier 声明式载体（主题无关字段）
- [engine/src/xkx/combat/system.py](../../engine/src/xkx/combat/system.py)：CombatSystem 扩展 special_attack 调用点（检查阵法标记 -> 注入 CombatModifier）+ call_out 翻译衔接（revive/start_ EffectComp 化）
- [engine/src/xkx/runtime/death.py](../../engine/src/xkx/runtime/death.py)：revive call_out -> EffectComp 翻译（衔接 2.2 death.py，确认 EffectComp 中断契约）
- [engine/src/xkx/runtime/conditions.py](../../engine/src/xkx/runtime/conditions.py)：start_berserk/hatred/vendetta/aggressive condition handler（auto_fight 延迟启动 EffectComp 化）
- [engine/tools/golden_trace/diff.py](../../engine/tools/golden_trace/diff.py)（新）：三层 diff 工具（L1 概率分布 + L2 文本结构 + L3 语义）
- [engine/tests/test_combat_modifier.py](../../engine/tests/test_combat_modifier.py)（新）：CombatModifier 接口 + special_attack 调用点 + 主题无关性断言
- [engine/tests/test_callout_translation.py](../../engine/tests/test_callout_translation.py)（新）：revive/start_ call_out -> EffectComp 翻译 + 崩溃恢复 + 中断契约
- [engine/tests/test_golden_trace_diff.py](../../engine/tests/test_golden_trace_diff.py)（新）：三层 diff 协议测试（概率分布 + 文本结构 + 语义）
- [engine/tests/test_theme_neutrality.py](../../engine/tests/test_theme_neutrality.py)：扩展阵法/合击/anubis 字面量黑名单
- [engine/src/xkx/spec/impl_map.py](../../engine/src/xkx/spec/impl_map.py)：call_out 翻译 + 阵法合击接口条目标注（2.4 范围 implemented，具体阵法后置）

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 1（CombatKernel 抽象时机张力）：call_out 翻译 + 阵法合击接口设计时 test_theme_neutrality 硬门禁兜底"从武侠提取（保深度）与非武侠验证（保主题无关）"的张力
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 4（基线测试）：golden trace diff 协议落地"driver 可运行使定点录制可行"，定位辅助验证非主线门禁
- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 7（派生变更审计）：call_out 翻译为 EffectComp 后跨 tick 延迟副作用的审计轨迹（ConditionTickResult ledger + combat ledger 交织）
- [04](../xkx-arch/04-迁移路径与避坑清单.md) §三阶段 2 Combat 迁移专项（call_out 144 处 + s_combatd 阵法合击 + golden trace）/ §四 kill criteria（2.4 行为等价失败）
- [15](../xkx-arch/15-阶段2-子系统实施计划.md) §三 2.4（本任务）/ §七 kill criteria 触发条件
- [ADR-0023](ADR-0023-combat-determinism-boundary-simplification-ledger.md)（combat-only 确定性 + 简化台账 6 项，本 ADR 承接其"不做"项）
- [ADR-0017](ADR-0017-ecs-sparse-set-effect-component.md)（Effect 一等公民组件，call_out 翻译的载体）
- [ADR-0018](ADR-0018-conditionhandler-on-tick-contract.md)（ConditionTickResult ledger，call_out 翻译的审计轨迹）
- [ADR-0022](ADR-0022-json-save-crash-recovery-dirty-flag.md)（Effect 崩溃恢复，call_out 翻译的崩溃安全）
- [ADR-0003](ADR-0003-combatkernel-theme-neutrality.md)（主题无关性，阵法合击接口设计的硬门禁来源）
- [ADR-0009](ADR-0009-original-driver-runnable.md)（driver 可运行，golden trace 定点辅助的可行性基础）
- [ADR-0011](ADR-0011-spec-conformance-checker.md)（ConformanceChecker 8 项，golden trace diff 的主线门禁对照）
- [ADR-0028](ADR-0028-rank-d-spec-and-pronoun-context.md)（PronounContext，golden trace L3 语义 diff 的渲染基础）
- [spec/layer_e_combat.py](../../engine/src/xkx/spec/layer_e_combat.py)（do_attack 七步 + 31 random 概率模型，golden trace L1 概率 diff 的理论基准）
- [engine/tools/golden_trace/README.md](../../engine/tools/golden_trace/README.md)（golden trace 录制方法 + diff 建议框架）
