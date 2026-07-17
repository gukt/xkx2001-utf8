# ADR-0003：CombatKernel 主题无关性重构（S2 非武侠验证驱动）

- 状态：已采纳（S2）
- 日期：2026-07-10
- 阶段：-1 切片 S2
- 关联 dissent：[05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 1（CombatKernel 抽象时机张力）

## 背景

[04](../xkx-arch/04-迁移路径与避坑清单.md) kill criteria 2 / 范围检查点 2 要求：用非武侠微场景跑在 CombatKernel 上，验证核心引擎未硬编码武侠语义（硬门禁，不通过则暂停做内核主题无关性重构）。[05](../xkx-arch/05-第三轮专家对抗复审报告.md) dissent 1 警示 CombatKernel 抽象时机张力--从武侠提取（保深度）与非武侠验证（保主题无关）可能冲突，提取的接口可能过窄锁死武侠语义，靠阶段 -1 非武侠微场景硬门禁兜底。

[ADR-0002](ADR-0002-resolve-attack-extraction.md) 声称已为 S2 留口："武器类型用枚举传入（unarmed/sword/blade），'经脉/内力'等武侠概念不进核心签名"。S2 实跑非武侠微场景时验证该留口是否够。

## S2 验证发现（S1 留口不足）

S1 代码审查 + 非武侠微场景实跑发现 3 个武侠硬编码点，正是 ADR-0002 声称留口却没留够的地方：

1. **`_select_attack_skill` 硬编码武器->技能映射**：`weapon in ("sword","blade")` 特判返回同名技能，其余武器 fallback 到 `unarmed`。非武侠武器（火枪 firearm / 戒尺 ruler）会错误地用徒手技能算 AP。
2. **`_WEAPON_LABEL` 硬编码武器->渲染标签映射**：`sword->剑`、`blade->刀`，非武侠武器 fallback "拳头"，消息出戏。
3. **`neili`/`max_neili` 进了 `CombatantSnapshot` 核心签名**：违反 ADR-0002 "经脉/内力不进核心签名"声明（`resolve_attack` 未使用，可安全移出）。

判定逻辑层（dodge/parry/hit 三分支、`skill_power` 公式、qi/jing/jingli 资源池、"dodge"/"parry" 技能名、limbs 部位、action_damage_type 默认"击伤"）审查结论为主题无关，不动。

## 决策（最小重构：映射外提到题材数据）

把"武器到技能/标签的映射"从**内核推断**改为**题材数据声明**，内核不再知道任何具体武器名：

- `CombatantSnapshot` / `CombatState` / `NpcDef` 加 `attack_skill: str = "unarmed"`（本回合招式所用技能 id）+ `weapon_label: str = "拳头"`（`$w` 占位符替换值），由题材数据声明（武侠官兵 `blade`/`刀`，海盗 `firearm`/`火枪`，监生 `ruler`/`戒尺`）。
- `resolve_attack` 删 `_select_attack_skill`（改读 `attacker.attack_skill`）、删 `_WEAPON_LABEL`（`_render` 改读 `attacker.weapon_label`）。
- `CombatantSnapshot` 删 `neili`/`max_neili`（移出核心签名；`Vitals` 组件保留，运行时数据不进战斗快照）。
- 删 `WEAPON_SWORD`/`WEAPON_BLADE` 常量（内核不再认识具体武侠武器），保留 `WEAPON_UNARMED` 作为通用徒手默认。

> 不引入武器系统（04 把武器系统规格后置到阶段 0）。只是把"招式用哪个技能、武器叫什么名"从 weapon 推断改为显式声明--这是主题无关性必需的，不是新复杂度。

## 非武侠验证

两个非武侠微场景跑在重构后的 CombatKernel + 运行时上，端到端 go（valid_leave）+ kill（resolve_attack）+ 确定性重放全通：

- **大航海**（`scenes/age_of_sail_micro/`）：火枪（firearm）海盗，`attr_lt` 智力门槛规则。
- **书院**（`scenes/academy_micro/`）：戒尺（ruler）监生，`present_npc` 看守规则（与武侠 `age_lt` / 大航海 `attr_lt` 形成谓词差异化）。

## 硬门禁自动化（防回归）

[04](../xkx-arch/04-迁移路径与避坑清单.md) 范围检查点 2 "核心引擎未硬编码武侠语义"在 `tests/test_theme_neutrality.py` 落为可回归断言：

- 非武侠 snapshot（firearm/ruler）跑 `resolve_attack`，断言消息含声明的 `weapon_label`、`skill_improve` effect 的 detail=声明的 `attack_skill`（证明走题材数据而非 fallback）。
- **`inspect.getsource(resolve_attack)` 断言模块源码不含 `"sword"`/`"blade"` 字符串字面量**--把"内核未硬编码武侠武器"变成代码级硬门禁。
- `CombatantSnapshot.model_fields` 断言不含 `neili`/`max_neili`。

44 tests 全绿（30 原有 + 5 大航海 + 4 书院 + 5 主题无关性），ruff 全过。

## 不做（范围边界）

- `qi`/`jing`/`jingli` 不重命名（ADR 未要求；拼音命名视为资源池 slot，语义通用）。
- `action_damage_type`/`action_message` 不外提到 `NpcDef`（属 S4 技能 action 描述，非主题无关性问题）。
- 武器系统规格（阶段 0）。
- riposte 递归 / hit_ob-hit_by mapping 分支（后续切片，[ADR-0002](ADR-0002-resolve-attack-extraction.md) 表已标）。

## 关联

- [05](../xkx-arch/05-第三轮专家对抗复审报告.md) §五 dissent 1（CombatKernel 抽象时机张力）--本 ADR 是其"非武侠验证"半的落地。
- [ADR-0002](ADR-0002-resolve-attack-extraction.md)（resolve_attack 提取，主题无关性留口）--本 ADR 细化并兑现其留口声明。
- [04](../xkx-arch/04-迁移路径与避坑清单.md) kill criteria 2 / 范围检查点 2 / 决策检查点"阶段 -1 -> 0"。
- [06](../xkx-arch/06-阶段-1-实施计划.md) S2。
