# 引擎架构师 A：战斗与效果生命周期簇 -> 题材无关 engine 抽象方案与可选方向

> 角色与范围：本文件是「引擎架构师 A」产出，把 LPC 一手考古出的通用机制映射到题材无关 engine 核心，**止步于设计输入层**（不输出最终接口契约，留给后续 `/to-spec` 决策）。证据来源优先级遵循总则 §4.2：LPC 源码为唯一真相源，`engine/src/openmud/` 仅作批判对照对象。每条结论标注来源（LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名）。
>
> 与同层文件的关系：机制抽象由 `01-raw-findings/mechanisms.md` 给出，UGC 创作面由 `ugc-surface.md` 给出，engine 逐项偏差由 `06-engine-critique/engine-comparison.md` 给出。本文件聚焦「该进 core 还是下沉题材包 / 有哪几条抽象路径」的**分叉决策输入**，不重复罗列偏差清单。
>
> 已接受硬约束（不重开）：ADR-0004「七步骨架 + AP/DP 结构 + Effect 调度/衰减/移除机制归引擎；PowerModel/condition handler/stacking policy 归题材包」；ADR-0007「完整 Effect 生命周期延期出 M2/M3 停机范围」；ADR-0001「不做行为等价」。本文件在 ADR-0004 边界内给出可选方向。

---

## 0. 一句话定位

LPC 战斗/Effect/死亡簇的耦合链是 **交战列表 -> heart_beat 驱动 attack -> COMBAT_D 七步结算 -> receive_damage/wound 三类两层伤害 -> update_condition 时效 Effect 播报 -> qi/jing 耗尽触发 unconcious/die 两段式 -> ghost 态进地府区走轮回 -> reincarnate 复活**（证据：`inherit/char/char.c:60-169` heart_beat 串起 attack/update_condition/die/unconcious；`feature/damage.c:13-66` receive_damage/wound；`feature/condition.c:21-69` update_condition；`feature/damage.c:105-264` unconcious/die/reincarnate）。映射到题材无关 engine 的核心问题是：**这条链里哪些是「任何有战斗的世界都需要的骨架」，哪些是「武侠/东方题材的内容贴纸」**。下文分 6 个子问题各给 2-3 个可选方向并比较权衡。

---

## 1. 交战/敌对关系作为 engine 核心原语的最小集

### 1.1 LPC 真相

- **双列表**：`feature/attack.c:15-16` 维护两条独立列表：`static object *enemy = ({})`（当前交战对象，`fight_ob` 加入）与 `static string *killer = ({})`（杀到底的目标 id，`kill_ob` 加入）。`is_fighting(ob)` 查 enemy、`is_killing(id)` 查 killer，是两个不同语义的谓词（attack.c:24-37）。
- **多对手上限**：`#define MAX_OPPONENT 4`（attack.c:12）；`select_opponent()` 用 `random(MAX_OPPONENT)` 从 enemy 列表随机挑一个出手（attack.c:79-88），即一个角色一回合只打一个但可同时被多达 4 个敌人围攻。
- **生命周期清理**：`clean_up_enemy()`（attack.c:64-75）按「对象失效 / 不在同房 / 非活且非 kill 目标」三条逐 tick 清理；`remove_all_enemy()` 通知对方停止但保留 killer（attack.c:112-123）；`remove_all_killer()` 才清 killer（attack.c:126-136）。**fight 与 kill 的清理策略不对称**：昏迷 `remove_all_enemy`、死亡 `remove_all_killer`（damage.c:120, 230）。
- **触发来源分流**：`init()`（attack.c:229-258）区分三类自动开战原因 `hatred`/`vendetta`/`aggressive`，调 `COMBAT_D->auto_fight(me, obj, type)`（combatd.c:852-962 各 `start_*` 实现：berserk/hatred/vendetta/aggressive，各自检查 `no_fight`/同房/living 后 `kill_ob` 或 `fight_ob`）。`no_fight` 房间标记在 `kill_ob` 入口拦截（attack.c:54）。
- **组队**：`feature/team.c:8` `leader`/`lord`/`team` 三字段；`follow_me`/`follow_path` 跟随逻辑（team.c:37-49），`dismiss_team` 解散（team.c:103-122）。组队与交战正交但 `dismiss_team` 在 die/unconcious 时被调（damage.c:124, 244）。

### 1.2 engine 现状对照

- `combat_system.py:692-699`（components.py）`Engaged` 组件**只存单个 opponent**，`try_engage`（combat_system.py:93-114）在已 Engaged 时直接拒绝：「你正在和其他人交战，分不开身」。**无 enemy/killer 双列表、无多对手、无 kill/fight 语义区分**。
- `_on_combat_tick`（combat_system.py:248-273）按 unordered pair 各出手一次，无 `select_opponent` 随机选择（双方确定性各打一下）。
- 无 `no_fight` 房间拦截（房间级 `RoomFlags.no_fight` 存在但 combat 路径未消费，components.py:559）。

### 1.3 三个可选方向

**方向 A（最小核心：保持 1v1，多对手/kill 语义下沉题材包）**：core 只保留单 opponent `Engaged`。多对手围攻、kill/fight 区分、auto_fight 原因都交题材包用「多份 Engaged + 事件钩子」自建。
- 权衡：core 最小、ECS 形状不变；但 LPC 21 门派数十年实证「4 对手 + kill 列表」是战斗社交（围攻、守卫、结仇）的基础（combatd.c:852-962 四种 auto_fight 全靠双列表），下沉意味着每个题材包重写一遍，违反 ADR-0004「流程归引擎」精神。**不推荐**。

**方向 B（推荐：core 内嵌双语义敌对列表原语，原因下沉）**：core 提供「有向敌对关系」原语，支持 N 对手（上限可配），区分 `engaged`（战斗中，脱离即清）与 `hostile`（杀到底，跨脱离持久）两种标签。auto_fight 的**原因**（hatred/vendetta/aggressive/berserk）仍归题材包 hook（`ON_ENTER_ROOM` 事件里题材包决定是否建交战）。
- 权衡：匹配 LPC `enemy`/`killer` 双列表语义，围攻/守卫/结仇零特殊代码即可复用；`no_fight` 房间拦截归 core（是普适的「和平区」约束）。代价：core 多一个有向关系组件 + 清理规则。**推荐**。

**方向 C（最通用：core 提供「有向标签关系图」原语）**：core 提供 generic `DirectedRelation(label, target, cleanup_policy)`，fight/kill 只是两种 label，追随/follow/师徒也可复用。
- 权衡：跨子系统最复用（team.c 的 leader/lord 也是有向关系）；但战斗的清理规则（同房/living/kill 保留）是战斗特有的，强行抽象成通用图会让 cleanup_policy 字段爆炸。**过度设计，不推荐**。

### 1.4 结论输入

交战/敌对关系**必须进 core 的最小集**：N 对手敌对列表 + fight/kill 双语义 + 同房/living 清理规则 + 和平区拦截。**可下沉题材包**：auto_fight 的具体原因与文案（hatred/vendetta/aggressive），组队 leader/lord 社交结构（team.c 整体可作为题材包可选模块，但 die/unconcious 调 `dismiss_team` 的钩子点要留）。证据：attack.c:12,64-136；combatd.c:852-962；damage.c:120,244。

---

## 2. 命中/伤害结算抽象：PowerModel 可扩展方向 + 三类伤害题材无关化

### 2.1 LPC 真相

- **三类伤害**：`feature/damage.c:13-66` `receive_damage(type, damage, who)` 与 `receive_wound(type, damage, who)`，`type` 只能是 `jing`/`qi`/`jingli`（damage.c:18-19, 44-45 显式 error）。damage 减 `query(type)`（当前值），wound 减 `query("eff_"+type)`（有效上限），且 wound 会拉低当前值不超过新 eff（damage.c:53-61）。
- **两层资源模型**：每个资源有三态：`<type>`（当前）、`eff_<type>`（有效上限，受伤口影响）、`max_<type>`（硬上限）。`receive_heal`（damage.c:68-83）回复受 eff 约束；`receive_curing`（damage.c:85-103）回复 eff 本身受 max 约束。**这是「当前值 <= 有效上限 <= 硬上限」的三层资源**。
- **伤害来源归属**：`set_temp("last_damage_from", who)`（damage.c:21, 47）+ `set_temp("last_eff_damage_from", who->id)`（damage.c:26, 51）双重记录，后者专供 PKiller 判定（die() 用 `last_eff_damage_from` 写 PKILL_DATA 日志，damage.c:210-214）。
- **heal_up 自然恢复**：`heal_up()`（damage.c:270-331）按战斗中/非战斗两套回复速率（战斗中回复 = 非战斗的 ~1/3），且 `eff_*` 会缓慢自愈向 max 靠拢。
- **七步结算**：ADR-0004 已确认 `combatd.c` do_attack 七步与旧引擎 archive `resolve_attack` 七步互证，本文件不重述。

### 2.2 engine 现状对照

- `combat.py:72-83` `PowerModel` 协议四方法（attack_power/defense_power/parry_power/base_damage）+ `DefaultWuxiaPowerModel`（combat.py:85-113）。**公式可整体替换**（ADR-0004 接缝正确）。
- `combat.py:33-56` `CombatContext` 只带 `attacker_qi_current`/`defender_qi_current` + neili，**无 jing、无 jingli、无 eff 层**。
- `components.py:459-468` `Vitals` 有 `qi_current`/`qi_max`/`neili_current`/`neili_max`/`jingli_current`/`jingli_max`，**无 eff_*（有效上限）层**，且 apply 路径只用 qi：`apply_combat_result`（combat_system.py:227-245）只 `vitals.qi_current -= result.damage`，`handle_vitals_depleted` 只判 `qi_current <= 0`（death_flow.py:180）。**三类伤害被压平成单一 qi 伤害，两层资源被压平成一层**。
- `CombatMoveSnapshot.damage_type`（combat.py:28）是字符串标签但**未参与路由**（resolve_attack 不按 type 分流到不同资源池）。
- **伤害来源归属缺失**：CombatRoundResult 不携带 attacker 归属给 receive 路径（apply 时靠 attacker 参数传入，但无 `last_damage_from` 持久记录供后续 PK 判定）。

### 2.3 三个可选方向

**方向 A（单资源 + PowerModel 全权：现状延续）**：core 只承认单一「血量」资源（qi），jing/jingli/eff 全交 PowerModel 用自定义属性计算。damage_type 仅文案标签。
- 权衡：core 最轻；但 LPC 的「jing 伤=神志、qi 伤=气血、jingli 伤=精力」是死亡判定的多触发源（char.c:108 `qi<0||jing<0||jingli<0` 三选一即昏迷），压成单 qi 会丢失「被毒伤 jing 致昏 vs 被打 qi 致昏」的语义区分，且 eff 伤口层（影响恢复上限）无法表达。**不推荐**。

**方向 B（推荐：core 提供「命名资源池 + 伤害按 type 路由」抽象，两层资源作为可选层）**：core 定义 Vitals 为「命名资源池集合」(name -> {current, effective_cap?, max})，`receive_damage(type,...)` 按 type 路由到对应池。PowerModel 仍算 raw 伤害数值，但「伤害打到哪个池」由 damage_type 决定（engine 路由）。effective_cap（eff 层）作为可选第二层，题材包声明哪些资源有伤口上限。
- 权衡：三类伤害题材无关化（题材包自定义资源名，如科幻题材可加 shield/armor 池，武侠填 jing/qi/jingli），死亡触发可声明「任一关键池耗尽即昏迷」。eff 层可选不强制。代价：Vitals 从平铺字段变 mapping，序列化稍重。**推荐**。

**方向 C（LPC 全忠实：core 内嵌 jing/qi/jingli + eff/max 三层为固定原语）**：core 固定三类资源与三层结构，题材包只能调数值不能改结构。
- 权衡：违反题材无关（仙侠/科幻资源语义不同）；ADR-0001 不做行为等价也不要求结构等价。**不推荐**。

### 2.4 结论输入

PowerModel 接缝（ADR-0004）方向正确，**保持公式可替换**。需要补的是：core 把「伤害按 damage_type 路由到命名资源池」做成**不变量**（不是题材包责任），资源池形状可配置（方向 B）。两层资源（current/effective/max）至少 current+max 必须进 core，effective_cap 作为可选伤口层。伤害来源归属（`last_damage_from` 等价）必须进 core（PK/击杀奖励依赖它，die/reincarnate 跨 tick 引用）。证据：damage.c:13-66, 270-331；char.c:108；combat_system.py:227-245。

---

## 3. Effect 时效引擎抽象：condition.c 模型映射 + conditions.py 概念错位的正确归位

### 3.1 LPC 真相（这是本簇最关键的设计输入）

- **数据结构**：`feature/condition.c:8` `mapping conditions`（condition_name -> opaque info），`apply_condition`/`query_condition`/`clear_condition`/`clear_all_condition`（condition.c:79-113）。info payload 不透明（bt_poison 用 int duration，drunk 用 int，bandaged 用 int，embedded 用 int，city_jail 用 int；可也用 mapping）。
- **时效驱动**：`update_condition()`（condition.c:21-69）由 `heart_beat` 调用（char.c:144 `cnd_flag = update_condition()`），但**不是每 tick**——char.c:141-142 `if( tick-- ) return; else tick = 5 + random(10)`，即 condition 每 5-15 个 heart_beat 才更新一次（节流）。
- **每 condition 是独立外部 daemon**：`CONDITION_D(cnd)`（condition.c:36）解析到 `/kungfu/condition/<name>.c`，调其 `update_condition(me, info)`（condition.c:62）。daemon 返回 flag：`CND_CONTINUE`(1)=继续、`0`=过期移除、可 OR `CND_NO_HEAL_UP`(2)=抑制自然恢复（include/condition.h:5-6）。返回 0 即 `map_delete`（condition.c:63）。
- **daemon 能做任何事**（这是关键）：bt_poison.c:33-34 调 `receive_wound("jing")`+`receive_damage("jingli")` 造伤害；bandaged.c:24 调 `receive_curing("qi")` 治疗；drunk.c:14 调 `unconcious()` 触发昏迷；city_jail.c:9 调 `me->move(...)` 移动玩家；blind.c:30-32 改 `apply/attack`/`apply/defense` 属性；embedded.c:22-24 调 `remove` 命令 + 查 qi 比例播报。**Effect 既是状态播报也是副作用入口**。
- **自我续期/衰减**：bt_poison.c:36-38 按 `query_skill("poison")` 衰减 duration；hanbing_damage.c:26-27 `apply_condition("hanbing_damage", duration-1)` 自减；drunk.c:32 `apply_condition("drunk", duration-1)`。**duration 逻辑在 daemon 内部，不在框架**。
- **死亡清空**：`die()` 调 `clear_condition()`（damage.c:184）；地府 gate.c:38 进鬼门关也 `clear_condition()`。

### 3.2 engine 现状对照（概念错位核心证据）

- `conditions.py` **是通用布尔求值器**（Predicate/Equals/Gte/And/Or/Not，conditions.py:92-142），用途是「门条件 / 物品使用限制 / NPC 行为条件」的**静态门控**（conditions.py:1-22 docstring 自述），**无时效、无 tick 驱动、无副作用、无 duration**。它对应的是 LPC 散落各处的 `if(...)` 字符串比较的反例（conditions.py:6-8 自述），**完全不对应 LPC condition.c 的时效 Effect 引擎**。
- **命名碰撞 hazard**：两个 `condition` 同名但语义完全不同（LPC condition = 时效状态 Effect；engine conditions = 布尔门谓词）。06-engine-critique 与总则 §6 均已标红此点。
- engine **目前没有 Effect 时效引擎**（ADR-0007 明确延期出停机范围，但 ADR-0004 明确归属仍为引擎）。`SkillBehavior`（skills.py:59-67）的 `hit_ob`/`hit_by`/`post_action` 是**瞬时命中钩子**，不是持续 Effect（ADR-0007 术语：Effect ≠ SkillBehavior 瞬时副作用）。
- `DemoPoisonStrikeBehavior`（skills.py:87-102）示范「命中 +5 伤害 + 追加播报」是瞬时，**没有挂持续中毒 Effect**（注释自述「不实现完整 buff」）。

### 3.3 三个可选方向

**方向 A（双引擎并存：重命名 + 新建 EffectEngine）**：`conditions.py` 重命名为 `predicates.py`（或保留但文档强标「布尔门控，非 Effect」），新建 `effects.py` 承载时效 Effect 引擎。两个引擎职责正交：predicates 管「能不能」（门控），effects 管「持续在身上做什么」（时效）。
- 权衡：消除命名 hazard，职责最清晰；Effect 引擎可独立于战斗（drunk/city_jail 不是战斗 Effect）。代价：多一个模块。**推荐**。

**方向 B（统一：Effect 既管时效又内嵌谓词）**：一个 Effect 对象既有 `predicate`（激活条件）又有 `tick`（时效应用）。conditions.py 的布尔节点成为 Effect 的 stacking/refresh 规则求值器。
- 权衡：看似复用，实则**强行把两个语义不同的东西揉一起**：门控谓词是无状态纯查询（phase==night），Effect 是有状态时长衰减（duration-1）。揉一起会让 Effect 框架被迫理解 Predicate AST，增加耦合。**不推荐，重蹈 LPC condition 一词多义覆辙**。

**方向 C（推荐，与 A 互补：Effect 引擎是薄调度器，handler 全权）**：core 的 EffectEngine 只做三件事：(1) 挂载/查询/移除 Effect 实例（`apply_effect`/`query_effect`/`clear_effect`，对应 LPC apply/query/clear_condition）；(2) 每 tick 调度所有 Effect 的 `update` 回调（对应 LPC update_condition 的 heart_beat 驱动）；(3) 按 stacking policy 决定重复挂载行为（unique/refresh/stack/independent，ADR-0004 已定）。**Effect 的具体行为（造伤害/治疗/移动/改属性/触发昏迷）全在题材包提供的 EffectHandler 里**，core 不解释 info payload（对应 LPC daemon 不透明 info）。
- 权衡：精确镜像 LPC condition.c 的「框架只调度、daemon 全权」分层；ADR-0004 已拍板 `EffectHandlerFn`（一个函数）+ 声明式 `StackingPolicy`/`EffectMode`(tick/wallclock)。本方向是其抽象落点。**与 A 并列推荐（A 管命名归位，C 管引擎形状）**。

### 3.4 结论输入

Effect 时效引擎**必须进 core**（ADR-0004 已定归属），但实现延期（ADR-0007）。正确抽象位置是**新建独立模块（非 conditions.py）**，形状为薄调度器 + 题材包 EffectHandler（方向 C）。`conditions.py` 应重命名或文档强标为布尔门控，**不得作为 Effect 引擎承载点**——它是概念错位的根因。Effect 的 info payload 不透明（core 不解释），duration/衰减逻辑在 handler 内（LPC daemon 自减 duration 的模式保留）。死亡/进地府清 Effect 的钩子点（damage.c:184, gate.c:38）要留。证据：condition.c:8,21-69,79-113；include/condition.h:5-6；bt_poison.c:33-38；drunk.c:14；city_jail.c:9；blind.c:30-32；conditions.py:1-22,92-142；skills.py:87-102。

---

## 4. 死亡两段式判定：纯判定 vs 副作用分层

### 4.1 LPC 真相

- **两段式触发**（`inherit/char/char.c:99-115` heart_beat）：
  - 第一段（致命伤）：`eff_qi < 0 || eff_jing < 0` -> `remove_all_enemy(); die();`（char.c:100-104）。
  - 第二段（当前值耗尽）：`qi < 0 || jing < 0 || jingli < 0` -> `remove_all_enemy();` 然后 `if(living()) unconcious(); else if(disable_type=="昏迷不醒") die();`（char.c:108-115）。**即：存活时耗尽 -> 昏迷；已昏迷时再耗尽 -> 死亡**。
- **unconcious 副作用**（damage.c:105-135）：奖励击败者 `COMBAT_D->winner_reward`、`remove_all_enemy`、`interrupt_me`、`dismiss_team`、设 jing/qi/jingli=0、`disable_player("昏迷不醒")`、`call_out("revive", random(100-con)+30)` 定时苏醒。
- **die 副作用**（damage.c:152-253）：`no_death` 房间降级为 unconcious（damage.c:159-177）；`clear_condition` + 清 poisoner；`COMBAT_D->announce("dead")`；`death_penalty`（combatd.c:987-1025：combat_exp/behavior_exp/potential/balance/skill 死亡惩罚 + death_times++）；`killer_reward`（combatd.c:1027+）；造尸体 `CHAR_D->make_corpse`；`remove_all_killer`；玩家设 ghost=1 + `move(DEATH_ROOM)` + `DEATH_ROOM->start_death` + `MARRY_D->break_marriage`；NPC `destruct`。
- **reincarnate**（damage.c:255-264）：清 ghost、全资源回 max。**复活是多入口**：地府 NPC 白无常 `death_stage` 走完对话后调（wgargoyle.c:62,68）；小店 `do_stuff` 询问后调（inn1.c:77）；黑无常 bgargoyle.c:73。

### 4.2 engine 现状对照

- `death.py:21-43` `next_death_state` 纯函数：ALIVE/UNCONSCIOUS/DEAD 三态 + `in_no_death_zone` + `vitals_depleted`，**两段式逻辑正确**（存活耗尽->昏迷、已昏迷耗尽->死亡、免死区强制昏迷）。**这是好的纯判定层**。
- `death_flow.py` 副作用层：`DeathPolicy`（death_flow.py:77-86 penalty_ratio/revive_room_key/drop_items/drop_currency/unconscious_recovery_ticks/recovery_vitals_ratio）+ `LootTable`（NPC 掉落）+ `handle_vitals_depleted` 分流玩家/NPC（death_flow.py:171-185）。玩家死亡：掉落物品/货币/技能经验惩罚 + 移到 revive_room + 回满血 + `ON_REVIVE` 事件（death_flow.py:212-270）。**纯判定与副作用分层基本正确**。
- **偏差**：(1) 只判 qi_current<=0（death_flow.py:180），无 jing/jingli/eff 多触发源（char.c:100-115 三资源任一耗尽）；(2) **无 ghost 态**，死亡直接复活到 revive_room，跳过地府中间态；(3) unconscious 苏醒用固定 tick 倒计时（death_flow.py:417-429），无 LPC `random(100-con)+30` 的属性相关随机；(4) 无尸体对象（make_corpse）；(5) 无 PKILL 日志归属。

### 4.3 三个可选方向

**方向 A（保持现状分层，补多资源触发）**：`next_death_state` 纯函数保留，把触发条件从单 qi 扩展为「任一关键资源耗尽」（关键资源集合可配）。副作用层 death_flow 不变。
- 权衡：最小改动、纯/副作用分层不动；但 ghost/地府中间态仍缺（见 §5）。**作为基线可接受**。

**方向 B（推荐：三段分层 = 纯状态机 + 副作用策略 + 复活策略）**：在 A 基础上把「复活路径」从 death_flow 抽成可替换 `ReviveStrategy`：(a) 立即复活（现状，适合轻松题材）；(b) ghost 中间态 + 走 scripted zone（LPC 地府）；(c) 原地复活带 debuff。core 只定义「死亡 -> 终态 -> 复活策略入口」骨架，策略归题材包。
- 权衡：把 LPC 写死的「die 必走地府」变成可选策略，题材无关化（科幻题材可能无鬼魂概念）。纯判定（death.py）不变，副作用（death_flow）拆出复活策略接缝。**推荐**。

**方向 C（core 最小：只管「耗尽->终态」转移，所有副作用归题材包）**：core 只留 next_death_state，掉落/惩罚/复活全交题材包 hook。
- 权衡：看似最题材无关，但「掉落/惩罚/复活」是任何有死亡的游戏都需要的骨架（ADR-0004 精神：流程归引擎），全下沉等于每个题材包重写。**不推荐**。

### 4.4 结论输入

death.py 纯函数 + death_flow.py 副作用的**分层方向正确**，保持。需补：(1) 多资源触发（不止 qi）；(2) 把复活路径抽成 ReviveStrategy 接缝（方向 B），让 ghost/地府成为策略之一而非硬编码；(3) unconscious 苏醒倒计时支持属性相关随机（LPC random(100-con)+30 的 con 依赖是题材包可配参数）。证据：char.c:99-115；damage.c:105-135,152-253,255-264；combatd.c:987-1025；death.py:21-43；death_flow.py:171-270,417-429。

---

## 5. 鬼魂/地府轮回：engine core 还是题材包内容

### 5.1 LPC 真相

- **ghost 态机制**：`feature/damage.c:9` `int ghost = 0`，`is_ghost()`（damage.c:11）。die() 设 ghost=1（damage.c:246），reincarnate() 清 ghost（damage.c:257）。可见性：`inherit/char/char.c:181-186` `visible()` 规则——ghost 只对其他 ghost 或有 `astral_vision` 的实体可见。
- **地府区是脚本化内容**：`d/death/` 13 房间（gate 鬼门关/gateway 酆都城门/road1-3/inn1/inn2/hell/block/blkbot/death/noteroom）+ NPC（白无常 wgargoyle/黑无常 bgargoyle）。流程：die() move 到 DEATH_ROOM（damage.c:247）-> `start_death` -> 白无常 `death_stage` 用 `call_out` 30s+5s 间隔播 6 段对话 -> `reincarnate()` + move 到 REVIVE_ROOM（wgargoyle.c:48-71）。`no_fight` 全区（gate.c:21 等）。自杀被禁（gate.c:50-55 "你还死着呢"）。进鬼门关 `clear_condition` + 销毁物品（gate.c:32-38）。
- **轮回多入口**：白无常对话走完（wgargoyle.c:62）、小店询问"回家"（inn1.c:67-83 do_stuff）、黑无常（bgargoyle.c:73）。**复活路径不唯一**，是脚本化选择。
- **地府区 ~580 行全是题材内容**（对话、房间描述、NPC 行为、物品销毁规则、no_fight 标记），无通用机制不可替代部分。

### 5.2 engine 现状对照

- **无 ghost 态**：death_flow.py 死亡直接 `remove Dead` + 移到 revive_room + 回满血（death_flow.py:251-270），无中间鬼魂阶段。`Dead` 组件（components.py:519）是瞬时 marker，处理完即移除。
- 无可见性规则、无 ghost-only 命令限制、无 scripted zone walk。

### 5.3 三个可选方向

**方向 A（推荐：ghost 全归题材包，core 只提供「死亡中间态」钩子）**：core 不内嵌 ghost 概念。死亡流程在「终态 -> 复活」之间留一个**可选中间态接缝**（ReviveStrategy，见 §4 方向 B）：题材包可选择「立即复活」或「进入 ghost 态 + 走 scripted zone」。ghost 的可见性规则、命令限制、物品销毁全是题材包 zone 内容。
- 权衡：题材无关（科幻题材无鬼魂，直接立即复活）；core 不背「鬼魂」这个东方概念。地府区作为题材包的一个 scripted zone（房间+NPC+对话），用现有 room/NPC 机制承载，**不需要 core 特殊支持**。**推荐**。

**方向 B（core 内嵌 ghost 状态机：ghost flag + 可见性规则 + 受限动词）**：core 提供 Ghost 组件 + visible 规则 + blocked verbs（对应 LPC is_ghost/astral_vision/可见性）。题材包只填 zone 内容。
- 权衡：LPC 忠实，但「鬼魂可见性」「astral_vision」是东方题材特有概念（仙侠有魂魄，科幻没有），进 core 违反题材无关。**不推荐**。

**方向 C（core 提供通用「受限中间态」原语，ghost 是实例）**：core 提供 `IntermediateState`（受限动词集 + 可见性过滤 + 持续条件），ghost/petrified/囚禁都是实例。
- 权衡：比 B 通用，但「可见性过滤」本质是「某实体对某观察者不可见」，这属于更通用的感知系统（visible 规则 char.c:171-187 整体），不应塞进死亡簇。**过度设计，不推荐**。

### 5.4 结论输入

**鬼魂/地府轮回不进 engine core**，全归题材包内容。core 只需在死亡流程留「中间态 -> 复活」的可选接缝（ReviveStrategy，§4 方向 B），让题材包能选择「立即复活」或「走中间态 zone」。地府区本身用现有 room/NPC/scripted 机制承载，不需 core 特殊原语。证据：damage.c:9-11,246-249,257；char.c:181-186；d/death/ 全目录；wgargoyle.c:48-71；inn1.c:67-83；death_flow.py:251-270（无 ghost）。

---

## 6. 武功招式调度：SkillBehavior 协议作为招式/effect 载体的抽象方向

### 6.1 LPC 真相

- **技能 = 数据 + 行为 daemon**：`feature/skill.c` 维护 `skills`(等级)/`learned`(经验)/`skill_map`(映射)/`skill_prepare`(备选)（skill.c:9-12）。`reset_action()`（attack.c:143-171）按 `query_skill_mapped(type)` 调 `SKILL_D(skill)->query_action(me, ob)` **运行时返回招式 action mapping**（force/dodge/damage/type）——**招式内容由 skill daemon 动态生成，不是静态表**。
- **技能 daemon 回调面**：`query_action`（返回招式数值，attack.c:163-165）、`skill_improved`（升级回调，skill.c:180 `SKILL_D(skill)->skill_improved(this_object())`）。`improve_skill`（skill.c:149-182）管升级，`skill_death_penalty`（skill.c:121-147）管死亡掉级。
- **招式作为 effect 载体**：技能命中后 `apply_condition` 挂 Effect（如 `kungfu/skill/pixie-jian/cimu.c` 挂 blind、`xingxiu-duzhang.c` 挂 poison）。**招式 -> 命中 -> 挂 Effect** 是三段链，Effect 挂载点在 skill daemon 的命中逻辑里（非 COMBAT_D 框架）。
- **备选/双手**：`query_skill_prepare`（attack.c:150）支持双手互博/双兵器，`action_flag` 切换（attack.c:156）。

### 6.2 engine 现状对照

- `skills.py:36-53` `SkillData`（声明式：skill_type/level_req/moves/practice/exp_thresholds/learn_condition）+ `SkillMove`（name/force/dodge/damage_type/damage/lvl/text）。**招式是静态数据元组**，无 daemon 动态生成。
- `skills.py:59-67` `SkillBehavior` 协议三钩子 `hit_ob`/`hit_by`/`post_action`，**仅命中时触发**。`register_skill_behavior`（skills.py:70-72）按 skill_id 注册。
- `combat_system.py:198-224` `select_move` **引擎默认选最高 force 且等级达标的招式**，题材包无法自定义选择策略（LPC 是 skill daemon 的 query_action 决定）。
- **缺失**：(1) 无 `query_action` 等价的「动态招式生成」钩子（LPC 招式可随情境变）；(2) 无 `skill_improved` 升级回调；(3) `SkillBehavior` 不能挂持续 Effect（hit_ob 返回 int/str/None 是瞬时，DemoPoisonStrikeBehavior 注释自述不实现 buff）；(4) 无 `skill_death_penalty` 死亡掉级接缝（engine 用 death_flow 的统一 penalty_ratio，非按技能）。

### 6.3 三个可选方向

**方向 A（保持现状：SkillBehavior 仅瞬时命中钩子，Effect 挂载走 EffectEngine）**：招式命中后想挂毒，在 `hit_ob`/`post_action` 里调 EffectEngine 的 `apply_effect`（§3 方向 C）。SkillBehavior 不扩展。
- 权衡：职责清晰——SkillBehavior 管瞬时、EffectEngine 管持续；但 `select_move` 硬编码最高 force，题材包无法自定义招式选择 AI（LPC query_action 的灵活性丢失）。**作为 Effect 载体的接缝是对的，但选择策略要松绑**。

**方向 B（推荐：SkillBehavior 扩展选择钩子 + Effect 挂载点，但不过度）**：(1) 加 `choose_move(ctx) -> SkillMove` 可选钩子（题材包可覆盖默认最高 force 选择，对应 LPC query_action 的动态生成）；(2) `hit_ob` 明确允许调 EffectEngine.apply_effect（作为「招式命中挂 Effect」的官方路径，非瞬时副作用）；(3) 加 `on_improve`/`on_death_penalty` 可选成长钩子（对应 skill_improved/skill_death_penalty）。
- 权衡：补齐 LPC skill daemon 的三个核心回调面（query_action/skill_improved/skill_death_penalty），让招式选择可题材化、Effect 挂载有官方入口、成长可钩。多数招式仍只填 SkillData 数值不实现钩子（ADR-0004 原则不变）。**推荐**。

**方向 C（Skill = SkillData + 完整 SkillScript 对象，引擎只调度）**：每技能一个行为对象，包含 select/apply/improve/growth/death_penalty 全套，引擎只按协议调。
- 权衡：最灵活但最重；LPC 的 skill daemon 确实是完整对象，但 21 门派大量招式只有数值无行为（attack.c:166-169 无 mapped skill 时走 weapon/default_actions），全对象化 boilerplate 过重。**不推荐**。

### 6.4 结论输入

SkillBehavior 作为「招式 -> 命中 -> Effect 载体」的**接缝方向正确**，但需补：(1) 招式选择钩子（`choose_move`，让题材包可覆盖默认最高 force，对应 LPC query_action）；(2) 明确 `hit_ob`/`post_action` 调 EffectEngine.apply_effect 是「招式挂持续 Effect」的官方路径（不是瞬时副作用）；(3) 成长钩子 `on_improve`/`on_death_penalty`（对应 skill_improved/skill_death_penalty）。Effect 载体身份由 EffectEngine（§3）承担，SkillBehavior 只负责「何时挂、挂什么」的触发，不承载 Effect 时效本身。证据：attack.c:143-171；skill.c:121-182；combat_system.py:198-224；skills.py:59-102。

---

## 7. 汇总：core 必做 / 下沉题材包 划线表

| 子系统 | 进 core（不变量/原语） | 下沉题材包（策略/内容） | 关键证据 |
|---|---|---|---|
| 交战/敌对 | N 对手敌对列表 + fight/kill 双语义 + 同房/living 清理 + 和平区拦截 + 伤害来源归属 | auto_fight 原因（hatred/vendetta/aggressive）+ 组队 leader/lord 社交 | attack.c:12,64-136; combatd.c:852-962 |
| 命中/伤害 | 七步骨架 + AP/DP 结构（ADR-0004 已定）+ 伤害按 damage_type 路由到命名资源池 + 资源 current/max（eff 可选） | PowerModel 公式 + 资源池命名/数量 + 具体伤害数值/文案 | damage.c:13-66; combat.py:72-113 |
| Effect 时效 | EffectEngine 薄调度器（apply/query/clear + tick 驱动 + stacking policy）+ 死亡/进地府清 Effect 钩子点 | EffectHandler 具体行为（伤害/治疗/移动/改属性/触发昏迷）+ info payload 语义 + duration 衰减逻辑 | condition.c:8,21-69; ADR-0004/0007 |
| 死亡判定 | next_death_state 纯函数（多资源触发）+ DeathPolicy 数据形状 + 玩家/NPC 分流 | 死亡惩罚具体数值 + 掉落表 + 复活路径（ReviveStrategy） | char.c:99-115; death.py:21-43; death_flow.py:77-270 |
| 鬼魂/地府 | **不进 core**，只留「中间态 -> 复活」可选接缝 | ghost 可见性 + 地府 zone 内容 + 轮回对话脚本 + 物品销毁 | damage.c:9-11,246-249; d/death/; wgargoyle.c:48-71 |
| 武功招式 | SkillData 声明式数据 + SkillBehavior 钩子接缝（含 choose_move/on_improve/on_death_penalty）+ select_move 默认实现 | 具体招式数值/文案 + 自定义选择策略 + 成长公式 + Effect 挂载触发 | attack.c:143-171; skill.c:121-182; skills.py:36-102 |

## 8. 未决问题（留后续决策）

1. **资源池形状**：方向 B 的「命名资源池 mapping」vs 现状「平铺字段 Vitals」的序列化/性能影响需 spec 阶段实测（1000 在线峰值下 Effect 遍历 + 多资源池序列化开销，见 performance-review）。
2. **EffectEngine 节流**：LPC 每 5-15 tick 才 update_condition（char.c:141-142），engine 是否复用 tick 节流还是每 tick 全量遍历 Effect？性能与 Effect 密度的权衡（见 performance-risks）。
3. **ReviveStrategy 接缝形状**：是「策略对象」还是「事件钩子序列」？death_flow 已有 `ON_BEFORE_DEATH`/`ON_DEATH`/`ON_REVIVE` 事件点（death_flow.py:43-45），可能事件已够，无需新策略对象——需与 §4 方向 B 对齐验证。
4. **conditions.py 重命名**：重命名为 predicates.py 会触大范围 import 改动（components.py:761-765 已引用），需评估迁移成本 vs 文档强标的 hazard 残留。

---

> 本文件止步于设计输入。所有「接口契约/字段签名/类名」均留 `/to-spec` 阶段决策。证据来源：LPC 源码（feature/、inherit/、adm/daemons/、kungfu/、d/death/、include/）+ engine 模块（combat.py/combat_system.py/conditions.py/death.py/death_flow.py/skills.py/components.py/events.py/tick.py）+ ADR-0004/0007。
