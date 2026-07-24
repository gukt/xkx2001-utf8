# 03-engine-insights / ugc-surface — 题材包创作层最小表面

> 角色：引擎架构师 B。任务：思考题材包（UGC）创作层应暴露的最小表面--创作者如何定义武功/招式/Effect/死亡惩罚/复活点/装备数值，Effect/武功/死亡三轮回的创作面形状，哪些锁在 engine core，创作者门槛与护栏。
>
> 证据规则：每条结论标注来源。LPC 一手源码是唯一真相源（`feature/`、`inherit/`、`kungfu/`、`d/`）；`engine/src/openmud/` 模块仅作批判对照对象（不反向脑补）。ADR 仅作已定边界引用，不作真相源。本文不输出可直接落地的 engine 接口契约（brief §1.4），止步于设计输入层。

## 0. 总览：三条创作轨与一条信任边界

LPC 的战斗/Effect/死亡创作面天然分裂为三层，分别对应三种不同的创作门槛与信任级。新引擎的 UGC 创作面应沿这三层切，而非混在一个"DSL"里：

| 创作轨 | LPC 对应 | 创作门槛 | 信任级 | 引擎锁定项 |
|--------|----------|----------|--------|------------|
| **A 声明式数据轨** | `kungfu/skill/*.c` 的 `action` mapping 数组（`18-zhang.c:52-218` 每招 `force/damage/dodge/lvl/damage_type`）、`feature/damage.c:13-19` 的三类伤害枚举、`inherit/weapon/sword.c:12-22` 的 `weapon_prop/damage` + `flag` | 低（YAML） | UGC 可写 | 七步骨架 + AP/DP 结构 + 伤害类型白名单 |
| **B 受限钩子轨** | `inherit/skill/skill.c:142-157` `hit_ob`（武器涂毒挂 condition）、`kungfu/skill/18-zhang.c:241-291` `query_action`（动态招式选择）、`kungfu/condition/*.c` 的 `update_condition` daemon | 中（受限 Python） | 官方/题材包可信，**UGC 禁** | Effect 调度循环 + 死亡状态机纯函数 |
| **C 房间/区域流程轨** | `d/death/gate.c`（地府入口 `clear_condition`+`destruct` 物品）、`kungfu/condition/city_jail.c:9` `me->move`（effect 改位置） | 中（声明式 + 可信钩子） | 官方/题材包可信，UGC 禁可执行 | 房间改世界必须走窄 ctx（ADR-0012） |

信任边界由 [ADR-0005](../../../../docs/adr/0005-m3-ugc-loop-creation-surface.md) + [ADR-0012](../../../../docs/adr/0012-trusted-room-hooks-narrow-ctx.md) 定死：**UGC 内容包全程声明式数据（`yaml.safe_load`），禁止可执行逻辑；`--validate` 遇 UGC 钩子应失败**。`engine/src/openmud/pack.py:63-82` 的 `load_pack` 已经是这个边界的落地--manifest.yaml + scene.yaml 两文件，无脚本逃生舱。

## 1. 创作者需要声明什么（A 轨：声明式数据）

### 1.1 武功招式（SkillData + SkillMove）

LPC 真相源：`kungfu/skill/18-zhang.c:52-218` 的 `action` mapping 数组。每招是一个 mapping，字段集为：

- `action`（文案）、`dodge`、`parry`、`force`、`damage`、`lvl`（学习等级门槛）、`skill_name`、`damage_type`（`"瘀伤"`/`"劈伤"`/`"内伤"`/`"擦伤"`）、`weapon`（可选，如 `"掌缘"`/`"掌劲"`）。
- `valid_learn`（`18-zhang.c:222-231`）：前置条件（空手、`huntian-qigong >= 20`、`max_neili >= 100`）。
- `practice_skill`（`18-zhang.c:293-302`）：练习消耗（`jingli`/`neili`）。
- `query_action`（`18-zhang.c:241-291`）：动态招式选择--但这属于 B 轨（含 `random()`、`me->add("neili",-50)` 副作用），声明式数据轨只表达静态 `action` 数组。

引擎对照：`engine/src/openmud/skills.py:37-52` 的 `SkillData` frozen dataclass 已经把 LPC 的静态字段集翻译成声明式：

- `skill_id` / `skill_type`（对应 `inherit/skill/skill.c:40` 的 `type()` 返回 `"martial"`/`"knowledge"`）/ `level_req`（对应 `lvl` 门槛）/ `moves: tuple[SkillMove,...]`。
- `SkillMove`（`skills.py:24-34`）：`name/force/dodge/damage_type/damage/lvl/text` -- 与 LPC `action` 数组的字段一一对应（文案落 `text`，`damage_type` 用英文枚举 `"blunt"` 而非中文 `"瘀伤"`）。
- `practice_neili_cost/practice_jingli_cost/practice_exp_gain`（`skills.py:46-48`）：对应 LPC `practice_skill` 的消耗。
- `exp_thresholds`（`skills.py:49`）：升级经验表，LPC 是 `feature/skill.c:149-182` `improve_skill` 里 `learned[skill] > (skills[skill]+1)^2` 的隐式公式，新引擎改成显式表（创作者可声明任意曲线）。
- `learn_condition`（`skills.py:51`）：对应 LPC `valid_learn` 的前置，但用结构化 dict（`conditions.py` 的 `Gte` 节点形状，如 `m2_mvp_scene.yaml:628-631` 的 `gte: {field: con, value: 10}`）。

**结论 1.1（武功招式创作面）**：A 轨暴露 `SkillData` + `SkillMove` 的全部字段给创作者，门槛是 YAML。引擎已建（`skills.py:151` `load_skills_from_mapping` 解析 `skills:` 段）。与 LPC 的差距是良性的：LPC 把静态数值（`action` 数组）与动态逻辑（`query_action` 函数）混在一个 `.c` 文件里，新引擎把它们拆成 A 轨（数据）与 B 轨（`SkillBehavior` 钩子），让 UGC 创作者只碰 A 轨就能配出绝大多数招式（ADR-0004："多数招式只填 SkillData 数值不实现钩子"）。

### 1.2 Effect（condition 内容层）--A 轨表达力边界

LPC 真相源：`feature/condition.c:79-85` `apply_condition(cnd, info)` -- info 是 `mixed`（任意值，通常是 int duration，但 `kungfu/condition/*.c` 各自解释它）。`kungfu/condition/` 下 30+ condition 的行为差异极大，**无法用单一声明式数据结构覆盖**：

| Effect 类别 | LPC 实例 | 声明式可表达？ |
|-------------|----------|----------------|
| 持续伤害（每 tick 掉血） | `bt_poison.c:33-34` `receive_wound("jing",damage/2)+receive_damage("jingli",damage/2)`；`hanbing_damage.c:23-24` `receive_damage("qi")+receive_wound("jing")` | **半可**：伤害类型+数值+周期可声明，但 decay 公式（`bt_poison.c:36-38` 按 `poison` 技能衰减 duration）不行 |
| 状态修改（改属性/标记） | `blind.c:30-31` `add_temp("apply/attack",-amount)`；`drunk.c:14` 触发 `unconcious()` | **不可**：副作用类型发散 |
| 移动/位置改变 | `city_jail.c:9` `me->move("/d/city/yamen")` + `:14` `set("startroom",...)` | **不可**：改世界副作用 |
| 社交/emote | `aphroclisiac.c:36-42` 扫描 `all_inventory(environment)` 发 emote | **不可**：交互逻辑 |
| 装备状态联动 | `embedded.c:17` `receive_wound("qi",3)` 出血 + `:22-26` NPC 自动 `remove` 嵌入物 | **不可**：条件分支 + 命令调用 |

引擎对照：`engine/src/openmud/conditions.py` 是**通用布尔求值器**（`Predicate`/`Equals`/`Gte`/`And`/`Or`/`Not`，`conditions.py:92-142`），**概念错位**于 LPC `condition.c` 的时效性 Effect 引擎。它当前只用于 `learn_condition` 门槏（`skills.py:51` + `m2_mvp_scene.yaml:628-631`），不是 Effect 生命周期系统。ADR-0004 设计的 `EffectHandlerFn` + 声明式 `StackingPolicy`/`EffectMode` **尚未实现**（ADR-0007 收窄：Effect 生命周期延期，停机范围不含）。

**结论 1.2（Effect 创作面现状）**：当前停机交付里 Effect 创作面**不存在**--UGC 创作者无法在 YAML 里声明持续伤害/中毒/盲等时效性 Effect。可声明的只有 `learn_condition`（用 `conditions.py` 的布尔节点）和 `SkillBehavior` 瞬时钩子（B 轨，UGC 禁）。这是诚实的缺口，不是遗漏：ADR-0007 明确"持续 Effect 生命周期不是 M2/M3 停机必须兑现的不变量"。Effect 创作面应在加固之后按 ADR-0004 的 `EffectHandlerFn`（一个函数）+ 声明式 `StackingPolicy`（unique/refresh/stack/independent）/`EffectMode`（tick/wallclock）设计--届时 A 轨可声明 stacking 策略与 mode，B 轨写 handler 函数体。

### 1.3 伤害类型与数值

LPC 真相源：`feature/damage.c:18-19` 与 `:44-45` 硬校验三类伤害：`jing`（精）/`qi`（气）/`jingli`（精力）。`receive_damage` 改当前值，`receive_wound` 改 `eff_` 上限（`damage.c:29-32` / `:53-61`）。`set_temp("last_damage_from",who)`（`damage.c:21`）记录伤害来源，用于死亡判定与 `killer_reward`。

引擎对照：`engine/src/openmud/combat.py:22-30` `CombatMoveSnapshot.damage_type: str = "blunt"` -- 伤害类型是**自由字符串**，未像 LPC 那样锁死三类。`combat.py:109-113` `DefaultWuxiaPowerModel.base_damage` 只区分"固定伤害（`move.damage`）"与"按 force 公式结算"两种，**没有 jing/qi/jingli 三类区分**。`components.py:460-468` `Vitals` 只有 `qi_current/qi_max` + `neili` + `jingli`，伤害只扣 `qi`（`combat_system.py:240` `vitals.qi_current = max(0, vitals.qi_current - result.damage)`），不扣 jing/jingli。

**结论 1.3（伤害类型创作面）**：A 轨应暴露的伤害类型是**引擎白名单**（题材无关的抽象伤害类目，如 `blunt`/`edged`/`internal`/`none`），而非 LPC 的 jing/qi/jingli 三类（那是武侠题材特定的资源轴）。`damage_type` 当前是自由字符串（`combat.py:28`）是个隐患：创作者可填任意值，引擎无法校验 stacking/抗性。建议白名单化（与 LPC `damage.c:18` 的 `error()` 校验同构，但类目题材无关）。LPC 的三类伤害对应的是"多资源轴伤害"这个更通用的机制--新引擎是否要支持多资源轴伤害（一刀扣 qi 也扣 jingli，如 `bt_poison.c:33-34` 同时 wound jing + damage jingli）是个待加固期决策，A 轨数值面应为此留扩展位但 MVP 不必实现。

### 1.4 死亡惩罚策略（DeathPolicy）

LPC 真相源：`feature/damage.c:190` `COMBAT_D->death_penalty(this_object())` -- 死亡惩罚委托给战斗 daemon（`adm/daemons/combatd.c`），惩罚内容在 daemon 里硬编码（非数据驱动）。`feature/skill.c:121-147` `skill_death_penalty()` -- 全技能降一级，`skill_map` 清空。`damage.c:184` `clear_condition()` -- 死亡清所有 Effect。`damage.c:246` `ghost = 1` -- 鬼魂态。

引擎对照：`engine/src/openmud/death_flow.py:77-87` `DeathPolicy` frozen dataclass 已经把死亡惩罚**数据驱动化**：

- `penalty_ratio: float = 0.1`（货币 + 技能经验按比例扣，`death_flow.py:291-305` `_apply_currency_penalty` / `_apply_skill_exp_penalty`）。
- `revive_room_key: str = "huashan_village"`（复活点，`death_flow.py:273-280` `_resolve_revive_room` 查 `world.room_ids`）。
- `drop_items: bool = True` / `drop_currency: bool = True`（掉落开关）。
- `unconscious_recovery_ticks: int` / `recovery_vitals_ratio: float`（昏迷苏醒参数）。
- `parse_death_policy`（`death_flow.py:118-137`）解析顶层 `death_policy:` 段，`m2_mvp_scene.yaml:665-667` 已用：`revive_room: huashan_birth` / `penalty_ratio: 0.1`。

**结论 1.4（死亡惩罚创作面）**：A 轨已暴露 `DeathPolicy` 全字段，创作者在 `death_policy:` 段声明。这是 LPC 没有的改进：LPC 的死亡惩罚散在 `combatd.c` daemon 与 `skill.c:skill_death_penalty` 硬代码里，题材包无法改；新引擎数据化后题材包可调比例/复活点/掉落开关/昏迷时长。但有两个 LPC 有而引擎缺的维度：(a) LPC 死亡清所有 condition（`damage.c:184`）--引擎无 Effect 系统所以无对应；(b) LPC 死亡触发地府流程（`damage.c:247-248` `move(DEATH_ROOM)` + `start_death`）--引擎只换位置 + 回满血（`death_flow.py:256-264`），无地府轮回叙事。地府轮回是否题材包可自定义见 §4。

### 1.5 复活点（_resolve_revive_room）

LPC 真相源：`feature/damage.c:247` `this_object()->move(DEATH_ROOM)` -- `DEATH_ROOM` 是 `include/login.h:23` 定义的 `"/d/death/gate.c"`，**全局硬编码**，不可题材包改。轮回后 `reincarnate()`（`damage.c:255-264`）回满血但**不换位置**（位置已在 die 里 move 到地府，轮回后从地府走回来）。LPC 的"复活点"其实是"地府入口"，不是" hometown 重生"。

引擎对照：`death_flow.py:273-280` `_resolve_revive_room(world, key)` -- 按 `DeathPolicy.revive_room_key` 查 `world.room_ids`，缺省回退第一个房间。这是**题材包可声明**的（`death_policy.revive_room`），比 LPC 灵活。

**结论 1.5（复活点创作面）**：A 轨已暴露，创作者在 `death_policy.revive_room` 填房间 key。注意引擎的复活语义与 LPC 不同：引擎是"死后原地掉落 + 移到 revive_room + 回满血"（`death_flow.py:244-264`），LPC 是"死后变鬼 + 进地府走流程 + 轮回复活"。引擎缺地府轮回这一段（见 §4）。

### 1.6 装备数值

LPC 真相源：`feature/equip.c:46-107` `wield()` -- `weapon_prop` mapping 聚合到 `owner->add_temp("apply/"+key, ...)`（`:100-102`），即装备数值是"加到临时 apply 缓冲"。`inherit/weapon/sword.c:12-22` `init_sword(damage, flag)` -- `weapon_prop/damage` + `flag | EDGED` + `skill_type:"sword"`。`inherit/weapon/sword.c:24-67` `hit_ob` -- 武器命中时可破坏护甲（`armor_prop` 递减、wreckage 状态机）--这是 B 轨副作用。

引擎对照：装备能力走 `CAPABILITIES` 注册表（`scene_loader.py:220-228` `_ITEM_KNOWN_FIELDS` 聚合各 spec 的 `known_fields`）。`m2_mvp_scene.yaml` 的物品用英文标识符 + 中文展示文案分离。

**结论 1.6（装备数值创作面）**：A 轨暴露装备数值字段（damage/armor 等）给创作者，走能力注册表透传。LPC 的"装备命中破坏护甲"（`sword.c:24-67`）属 B 轨副作用，A 轨不表达。装备作为 Effect 载体（`inherit/skill/skill.c:142-157` 武器涂毒 `apply_condition("snake_poison",...)`）也属 B 轨，需要 Effect 系统先就位（见 §2）。

## 2. Effect 创作面：condition.c 的 CONDITION_D daemon 模型如何暴露

### 2.1 LPC 的 daemon 模型

LPC 真相源：`feature/condition.c:36-62` -- 每个 condition 是一个**独立 daemon 对象**（`CONDITION_D(cnd[i])` 路径加载），`update_condition()` 在 heart_beat 里 `call_other(cnd_d, "update_condition", this_object(), conditions[cnd[i]])`（`:62`）调用 daemon 的 `update_condition(me, duration)`。daemon 返回 `CND_CONTINUE` 续命、返回 0 过期（`:63`）。每个 daemon 自行解释 `duration`、自行调 `receive_damage`/`receive_wound`/`apply_condition`/`move`/`unconcious` 等任意副作用。`apply_condition`（`:79-85`）不查重，由"施放者"负责（注释 `:73-77`）。

这是**最大灵活度的脚本模型**：每个 Effect 是一个完整可执行对象，能改任何世界状态。代价是 Effect 之间无统一 stacking 语义（每个 daemon 自己处理覆盖），且 daemon 可调任意副作用（包括 `die()`、`move`、`kill_ob`），无护栏。

### 2.2 新引擎应如何暴露（分层）

ADR-0004 已定边界：**引擎内嵌 Effect 调度/衰减/移除机制（不变量），题材包注入 `EffectHandlerFn`（一个函数）+ 声明式 `StackingPolicy`/`EffectMode`**。

分层暴露：

- **A 轨（UGC 可写，声明式）**：Effect 的**身份与策略**可声明--Effect id、伤害类型、周期（tick 数）、stacking 策略（`unique`/`refresh`/`stack`/`independent` 四枚举，ADR-0004）、mode（`tick`/`wallclock`）。这覆盖 LPC 里"每 tick 掉 X 点 jing 伤害、duration-1、duration<1 过期"这类**纯数值型持续伤害 Effect**（如 `bt_poison.c`、`hanbing_damage.c` 的数值部分）。
- **B 轨（官方/题材包可信，受限 Python）**：Effect 的**行为函数体**（`EffectHandlerFn`）--当 Effect 需要改世界副作用（`city_jail.c:9` move、`aphroclisiac.c:36` 扫描周围、`drunk.c:14` 触发昏迷、`blind.c:30` 改属性）时，A 轨表达不了，需 B 轨写函数。信任级同 `SkillBehavior`（ADR-0012：可信 Python 模块，UGC 禁）。
- **引擎锁定（不可碰）**：Effect 调度循环（对应 LPC `condition.c:21-69` `update_condition` 的遍历 + `CND_CONTINUE` 续命 + `map_delete` 过期逻辑）、stacking 合并算法、衰减/过期触发。这些是 ADR-0004 的"Effect 调度/衰减/移除机制"不变量。

**结论 2.2（Effect 创作面形状）**：LPC 的 `CONDITION_D` daemon 模型**不应原样暴露给 UGC**（每个 daemon 是全权可执行对象，无护栏，且 `apply_condition` 不查重导致 stacking 无语义）。应拆成 A 轨（声明式策略，覆盖纯数值型 Effect）+ B 轨（受限 handler 函数，覆盖副作用型 Effect）+ 引擎锁定的调度循环。当前引擎缺整个 Effect 系统（`conditions.py` 概念错位为布尔求值器，非 Effect 引擎；ADR-0007 延期），所以 Effect 创作面是**加固期 backlog**，不在 M2/M3 停机交付。

### 2.3 engine conditions.py 概念错位（批判）

`engine/src/openmud/conditions.py` 是"通用布尔条件表达式求值器"（`Predicate`/`Equals`/`Gte`/`And`/`Or`/`Not`，`conditions.py:92-142`，`MAX_DEPTH=32` 守卫 `:167`）。它对应的是 LPC 里"门槏/物品使用限制/NPC 行为条件"这类**静态判定**，不是 `condition.c` 的**时效性 Effect**。命名同名导致概念错位（brief §6 关键约束已点名）。它当前唯一消费者是 `skills.py:51` `learn_condition`（`m2_mvp_scene.yaml:628-631` 的 `gte` 节点）。Effect 系统应**新建模块**（如 `effects.py`），不要复用 `conditions.py` 的名字与结构--两者是不同关注点（静态布尔判定 vs 时效性副作用调度）。

## 3. 武功创作面：SkillBehavior 协议如何让创作者挂招式行为

### 3.1 LPC 的招式行为接入点

LPC 真相源：招式行为的接入点散在多处，且**数据与逻辑混合**：

- `inherit/skill/skill.c:142-157` `hit_ob(me,victim,damage_bonus,factor)` -- 武器/技能命中钩子，可挂毒（`apply_condition("snake_poison",...)` `:147`）、改仇恨（`victim->kill_ob(me)` `:151-152`）。
- `kungfu/skill/18-zhang.c:241-291` `query_action(me,weapon)` -- 动态选招，含 `random()`、`me->add("neili",-50)` 副作用、`post_action` 钩子引用（`:264` `(: sanhui :)`）。
- `kungfu/skill/18-zhang.c:316-320` `sanhui(me,victim,weapon,damage)` -- `post_action` 实现，改 `me->delete_temp("sanhui")`。
- `feature/attack.c:143-171` `reset_action()` -- 把 `actions` 设为 `(: call_other, SKILL_D(skill), "query_action", me, ob :)`（`:163`），即招式内容由 skill daemon 动态提供。
- `inherit/weapon/sword.c:24-67` `hit_ob` -- 武器命中破坏护甲。

### 3.2 引擎的 SkillBehavior 协议（已建，B 轨范例）

引擎对照：`engine/src/openmud/skills.py:60-68` `SkillBehavior` Protocol -- 三个钩子：

- `hit_ob(ctx: CombatContext, damage: int) -> int | str | None`（`:63`）-- 命中后；返回 int 改伤害、str 追加播报、None 不改。
- `hit_by(ctx: CombatContext) -> str | None`（`:65`）-- 被击中；返回播报。
- `post_action(ctx: CombatContext) -> str | None`（`:67`）-- 收尾；只追加播报，**不得改本回合伤害**（`combat.py:274` 注释 + M3-hardening-03）。

`combat.py:236-278` 的 `_invoke_hit_ob`/`_invoke_hit_by`/`_invoke_post_action` 是调用点。两个范例行为：

- `DemoPoisonStrikeBehavior`（`skills.py:87-102`）：命中 +5 伤害 + "毒素渗入伤口！"播报。对应 LPC 的瞬时伤害加成型 `hit_ob`。
- `SilkRopeCaptureBehavior`（`skills.py:105-137`）：命中后 `relocate_entity` 把防御方拽入捕获房。对应 LPC `city_jail.c:9` `me->move` 这类改位置副作用，但**走窄 API**（`relocate_entity`，非直接摸 World）--这是 ADR-0012 窄 ctx 精神的预演。

注册：`register_skill_behavior(skill_id, behavior)`（`skills.py:70-72`），按 skill_id 查表（`combat.py:227-233` `_behavior_for`）。

### 3.3 创作面形状

**结论 3.3（武功行为创作面）**：

- **A 轨（UGC 可写）**：`SkillData` + `SkillMove` 的纯数值（force/dodge/damage/damage_type/lvl）--覆盖 LPC `action` 数组的静态字段。多数招式到此为止（ADR-0004："多数招式只填 SkillData 数值不实现钩子"）。
- **B 轨（官方/题材包可信，UGC 禁）**：实现 `SkillBehavior` 协议的 Python 类，注册到 `_SKILL_BEHAVIORS`。覆盖 LPC 的 `hit_ob`/`query_action`/`post_action`/`sanhui` 等动态逻辑。三个钩子（`hit_ob`/`hit_by`/`post_action`）比 LPC 的散落接入点更规整：LPC 的 `hit_ob` 既能改伤害又能挂 condition 又能改仇恨（`inherit/skill/skill.c:142-157` 全干），引擎拆成"改伤害（hit_ob 返回 int）/追加播报（hit_ob 返回 str, hit_by, post_action）/改世界（hit_ob 内调窄 API 如 relocate）"三档语义更清晰。
- **引擎锁定**：七步结算管线（`combat.py:132-216` `resolve_attack`：选技能->取招式->AP/DP->dodge->parry->算伤害+钩子->inflict）、AP/DP 概率结构（`combat.py:219-224` `_roll_opposed`：`random(ap+dp)<dp`）、PowerModel 调用顺序。这些是 ADR-0004 的不变量。

**LPC 的 `query_action` 动态选招（`18-zhang.c:241-291`）引擎未覆盖**：引擎的 `select_move`（`combat_system.py:198-224`）是"选最高 force 且等级达标的招式"的固定策略，不允许技能自己定义选招逻辑（如 LPC 的"neili>1000 时出特殊三连"）。这是创作面的一个缺口：动态选招属 B 轨，但 `SkillBehavior` 协议当前没有"选招"钩子。是否补是个设计决策（LPC 的 `query_action` 是招式内容供给方，与 `SkillBehavior` 的命中后副作用是不同切面）。

## 4. 死亡与轮回创作面：DeathPolicy/LootTable/地府流程可否题材包自定义

### 4.1 死亡惩罚与掉落（A 轨，已建）

见 §1.4。`DeathPolicy`（`death_flow.py:77-87`）+ `LootTable`（`death_flow.py:89-97`：`currency_min/max`、`item_template_keys`、`kill_exp`）均数据驱动，`parse_death_policy`/`parse_loot_table` 解析 YAML。NPC 的 `loot:` 段（`scene_loader.py:1149-1151`，`m2_mvp_scene.yaml:603-609`）可声明掉落。这部分题材包可自定义。

### 4.2 死亡状态机（引擎锁定）

LPC 真相源：`inherit/char/char.c:99-114` heart_beat 里两段式判定--`eff_qi<0||eff_jing<0` 直接 die（`:100-103`）；`qi<0||jing<0||jingli<0` 时若 `living()` 则 unconcious、若已昏迷则 die（`:108-114`）。`feature/damage.c:159` `environment()->query("no_death")` -- 免死区只昏迷不死亡。

引擎对照：`engine/src/openmud/death.py:21-43` `next_death_state(current, in_no_death_zone, vitals_depleted)` 纯函数 -- 两段式（存活->昏迷->死亡，免死区只到昏迷）。`death_flow.py:188-210` `_handle_player_depleted` 调用它。`NoDeathZone` 组件（`components.py:524`）标记房间。

**结论 4.2**：死亡状态机（`next_death_state` 纯函数 + `DeathState` 枚举）锁在 engine core，题材包不可改状态转移规则。题材包可改的是：**触发死亡后的后果**（惩罚比例/掉落/复活点，via `DeathPolicy`）+ **是否免死**（via `NoDeathZone` 房间标记）。这与 LPC 一致（LPC 的 `char.c:100-114` 也是硬代码状态机，`no_death` 房间标记是数据）。

### 4.3 地府轮回流程（题材包可自定义程度）

LPC 真相源：`feature/damage.c:246-249` -- 玩家死后 `ghost=1`、`move(DEATH_ROOM)`（`/d/death/gate.c`，`include/login.h:23`）、`DEATH_ROOM->start_death(this_object())`。`d/death/gate.c:32-38` `init()` -- 进地府时 `destruct` 所有物品 + `clear_condition()`。地府是一系列房间（`gate`/`gateway`/`hell`/`inn1`/`inn2`/`road1-3`/`blkbot`/`block`/`death`，见 `d/death/` 目录），玩家变鬼后走流程轮回。`damage.c:255-264` `reincarnate()` -- 回满血、`ghost=0`。

引擎对照：`death_flow.py:212-270` `_execute_player_death` -- 掉落 + 惩罚 + 移到 `revive_room` + 回满血 + `ON_REVIVE` 事件。**无地府流程、无 ghost 态、无轮回叙事**。死亡是"原地掉落 -> 移到复活点 -> 回满血"一步完成。

**结论 4.3（地府创作面）**：

- **当前引擎不支持地府轮回流程**，且 ADR-0007 不要求停机实现。LPC 的地府是一个**区域级叙事流程**（一系列房间 + `clear_condition` + `destruct` 物品 + `start_death` 脚本），不是死亡状态机的一部分。
- 若未来要支持地府，创作面应走 **C 轨（房间/区域流程轨）**：地府房间用声明式 YAML 建（exits/objects/no_fight 标记，如 `gate.c:21` `set("no_fight",1)`），地府的"进关清物品/清 condition"逻辑走**可信房间钩子**（ADR-0012 窄 ctx，官方/题材包可信，UGC 禁）--对应 `gate.c:32-38` `init()` 的 `destruct`+`clear_condition`。死亡触发"移到地府入口"可由 `DeathPolicy.revive_room_key` 指向地府入口房实现（当前已支持），但"走完地府流程才轮回"需要房间钩子链 + 一个"轮回出口"机制（当前无）。
- **ghost 态**（`damage.c:9` `ghost`/`is_ghost()`）当前引擎无对应组件，且 ADR-0007 不要求。ghost 态是地府叙事的一部分，应在地府流程设计时一并考虑，不单独建。

### 4.4 死亡事件钩子（B 轨）

引擎已暴露三个事件点：`ON_BEFORE_DEATH`（可否决，`death_flow.py:224-236` `run_vetoable`，否决则转昏迷）、`ON_DEATH`、`ON_REVIVE`（`death_flow.py:43-45`）。这些是题材包/官方可信钩子的挂载点（B 轨），可用来实现"死亡触发剧情/任务/婚姻解除"等副作用（对应 LPC `damage.c:249` `MARRY_D->break_marriage` / `:250` `break_relation`）。UGC 禁挂。

## 5. 哪些锁在 engine core 不让创作者碰

汇总锁定项（创作者无论 A/B/C 轨都不可改）：

1. **七步战斗结算骨架**（`combat.py:132-216` `resolve_attack`）：选技能->取招式->AP/DP->dodge->parry->算伤害+钩子->inflict。ADR-0004 不变量。
2. **AP/DP 概率判定结构**（`combat.py:219-224` `_roll_opposed`：`random(ap+dp)<dp`）。ADR-0004 不变量。题材包可改的是 AP/DP 的**求值公式**（via `PowerModel` 策略，`combat.py:72-83`），不是判定结构本身。
3. **伤害结算核心**（`combat_system.py:227-245` `apply_combat_result`：写 Vitals + 触发死亡分流）。题材包不可直接改气血/内力数值，只能通过 `hit_ob` 返回 int 改本回合伤害。
4. **死亡状态机纯函数**（`death.py:21-43` `next_death_state`）。题材包不可改两段式转移规则。
5. **Effect 调度循环**（对应 LPC `condition.c:21-69` `update_condition` 的遍历/续命/过期）。ADR-0004 不变量。当前未实现（ADR-0007），实现后锁定。
6. **交战调度**（`combat_system.py:248-273` `_on_combat_tick`：遍历 Engaged 对、双向各出手一次）。对应 LPC `inherit/char/char.c:117-132` heart_beat 的 attack 循环 + `feature/attack.c:79-88` `select_opponent`。题材包不可改战斗 tick 调度。
7. **昏迷态行为约束**（`death_flow.py:48-74` `UNCONSCIOUS_BLOCKED_VERBS`：昏迷禁 go/attack/kill/flee 等 21 个动词）。对应 LPC `damage.c:127` `disable_player(" <昏迷不醒>")`。题材包不可放宽。
8. **全局注册表重建**（`skills.py:151-173` `load_skills_from_mapping`/`replace_skills_registry`：每次 `load_scene` 清空重建 SKILLS）。对应 LPC `feature/skill.c` 的全局 `skills` mapping。防止两次加载污染。

**PowerModel 是唯一允许题材包整体替换的"准核心"**（`combat.py:72-83` Protocol + `attach_power_model`/`register_power_model` `:119-129`）：题材包可提供自己的 `attack_power`/`defense_power`/`parry_power`/`base_damage` 求值公式（ADR-0004 grafting 的第二选项）。但这是 B 轨可信 Python，UGC 禁。默认 `DefaultWuxiaPowerModel`（`combat.py:85-113`）自洽可测，不追求 LPC 还原。

## 6. 创作者门槛与护栏

### 6.1 数值崩坏护栏

LPC 真相源：`feature/skill.c:166-168` -- `spi = 30`（学习技能数上限），`sizeof(learned) > spi` 时 `amount /= sizeof(learned)-spi`（学太多技能经验惩罚）。`feature/damage.c:17` `if(damage<0) error(...)` -- 伤害负值硬错。`:18-19` 伤害类型白名单校验。`inherit/char/char.c:124-130` wimpy_ratio 逃跑阈值。

引擎对照：`skills.py:284-302` `_require_int` -- 字段缺失/非数字抛 `SceneLoadError`。`combat.py:99-100` `attack_power` `max(0, int(raw))` -- AP 下限 0。`combat.py:109-113` `base_damage` `max(1, ...)` 下限 1。但**无全局数值上限校验**（创作者可填 `force: 999999`）。

**结论 6.1（数值护栏缺口）**：当前护栏只有"下限 0/1"与"类型校验"，无上限/比例校验。建议加固期补：(a) `force`/`damage` 软上限告警（`--validate` 时提示超常值，不硬拒）；(b) `penalty_ratio` 钳到 `[0,1]`（`death_flow.py:127` 当前直接 `float()`，无范围校验--创作者填 `penalty_ratio: 2.0` 会扣 200% 货币导致负数，`_apply_currency_penalty:296` `max(0,...)` 兜了底但静默）；(c) `recovery_vitals_ratio` 同理钳 `[0,1]`。

### 6.2 无限 Effect 堆叠护栏（Effect 系统就位后）

LPC 真相源：`feature/condition.c:79-85` `apply_condition` **不查重**（注释 `:73-77`："It is condition giver's responsibility to check"）--施放者负责查重，否则同 key 直接覆盖（`conditions[cnd] = info`）。所以 LPC 不会"无限堆叠同一 condition"（mapping key 覆盖），但会"不同 key 的 condition 无限叠加"（30+ condition 全挂上，heart_beat 开销爆）。`condition.c:18-19` 注释警告"don't make player got too much this kind of conditions or you might got lots of 'Too long evaluation' error"。

**结论 6.2（Effect 堆叠护栏）**：ADR-0004 的声明式 `StackingPolicy`（unique/refresh/stack/independent）就是为解决这个问题--`unique` 同 key 不叠加、`refresh` 刷新 duration、`stack` 累加、`independent` 各自独立。引擎锁定 stacking 合并算法（§5 第 5 项）。护栏应含：(a) 每实体 Effect 数量上限（对应 LPC 的"too much conditions"警告，硬上限而非软警告）；(b) `independent` 是逃生口但应有计数上限（ADR-0004 已留 `INDEPENDENT` 逃生口）。这些在 Effect 系统设计时定，当前 backlog。

### 6.3 死亡惩罚误配护栏

`death_flow.py:127` `penalty_ratio` 无范围校验（见 §6.1）。`death_flow.py:273-280` `_resolve_revive_room` 缺省回退第一个房间（`death_flow.py:278-279`）--若创作者填了不存在的 `revive_room` key，玩家会复活到"第一个房间"而非报错，**静默兜底是隐患**。

**结论 6.3**：建议 `--validate` 校验 `revive_room` key 必须存在于 `room_ids`（当前 `load_scene` 时不校验死亡策略引用的房间是否存在）。`drop_items`/`drop_currency` 是 bool 无误配风险。`unconscious_recovery_ticks` 应有下限（>=1，否则昏迷即醒，等于无昏迷态）。

### 6.4 信任边界护栏（UGC 禁可执行）

`pack.py:63-82` `load_pack` 用 `yaml.safe_load`（`pack.py:107`）--UGC 包天然不能携带可执行逻辑。`scene_loader.py:210` `hooks` 字段标注"官方轨专属；内容包轨见 `_attach_room_hook_binding` 拒绝"。ADR-0012 定 `--validate` 遇 UGC 钩子应失败。这是最强的护栏：UGC 创作者根本无法碰 B/C 轨，只能写 A 轨数据，数值崩坏是可恢复的（改 YAML 重载），不会造成安全/状态损坏。

### 6.5 创作者门槛分层

| 轨 | 谁来写 | 工具 | 门槛 |
|----|--------|------|------|
| A（数据） | UGC 创作者 / Agent 以文本创作者身份 | YAML + `--validate` 秒级反馈 | 低 |
| B（受限钩子） | 官方 / 题材包维护者 | 受限 Python（`SkillBehavior`/`EffectHandlerFn`/`PowerModel`） | 中，需懂协议 |
| C（房间流程） | 官方 / 题材包维护者 | 窄 ctx Python（`add_exit`/`remove_exit`/`schedule`/`message_*`） | 中，需懂 ctx API |

ADR-0006 已判编辑器/Web 平台是 post-MVP 独立产品，引擎只留"内容包加载/校验契约 + 运行时护栏"。`--validate`（`m3 spec` C1 块，user story 10-12）是创作者的核心反馈通道，复用 `load_pack` 同一份校验代码（不写第二套），失败消息与真实启动一致。

## 7. 待决问题（留给后续票据）

1. **动态选招钩子**：LPC `query_action`（`18-zhang.c:241-291`）允许技能自定选招逻辑（neili 阈值触发特殊招）。引擎 `select_move`（`combat_system.py:198-224`）是固定策略。是否在 `SkillBehavior` 加"选招"钩子？属 B 轨。
2. **多资源轴伤害**：LPC `bt_poison.c:33-34` 同时 wound jing + damage jingli。引擎只扣 qi。是否支持一刀扣多资源？影响 `CombatMoveSnapshot.damage_type` 与 `apply_combat_result`。
3. **Effect 系统模块归属与命名**：`conditions.py` 概念错位（布尔求值器），Effect 系统应新建模块（如 `effects.py`），不要复用名与结构。ADR-0004 已定 `EffectHandlerFn`/`StackingPolicy`/`EffectMode` 形状，ADR-0007 延期到加固后。
4. **地府轮回流程**：当前无。若要做，走 C 轨（房间钩子链 + 轮回出口）+ ghost 态组件。是否做是题材包需求驱动（武侠题材包可能想要地府，科幻题材包可能想要"克隆重生"）。
5. **伤害类型白名单**：`damage_type` 当前自由字符串（`combat.py:28`），建议白名单化（题材无关类目），便于抗性/stacking 校验。
6. **`revive_room` 存在性校验**：`--validate` 应校验 key 存在（当前静默回退第一个房间）。
