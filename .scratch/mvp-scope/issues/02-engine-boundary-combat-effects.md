Type: prototype
Status: resolved

## Question

"题材无关核心引擎"的能力边界怎么划--房间/出口/移动、命令解析分发、对象数据存储(dbase)、心跳调度、消息系统、存档持久化明显属于引擎;门派加成、武功具体数值、阴间叙事、文案明显属于题材包内容。中间不好归的两个:

1. **战斗结算的流程框架**(例如原 LPC "七步管线"这种流程结构)
2. **技能/条件效果系统的运行时机制**(Effect 的生命周期管理:如何叠加、如何过期、如何调度)

这两者算题材无关的引擎能力,还是题材包可以整体替换的内容?

## 暂定倾向(原,已拍板落地)

流程/运行机制(如何结算、如何调度 tick、效果如何叠加/过期)倾向归**引擎**--这样其他题材(仙侠/科幻)也能直接复用同一套战斗/效果引擎。具体公式、数值、技能名称、门派设定归**题材包**。

精确边界需要看点具体的东西才有感觉--2026-07-19 用 `/design-an-interface`(三源调研 + 三个 radical 不同的边界设计对比)推进,已拍板,见下文 Answer 与 [ADR-0004](../../../docs/adr/0004-combat-effects-boundary-engine.md)。

## Answer

**拍板(2026-07-19)**:战斗结算流程框架 + 技能/效果生命周期机制两者**归引擎**,精确边界定稿,暂定倾向("流程归引擎、数值归题材包")落地。详见 [ADR-0004](../../../docs/adr/0004-combat-effects-boundary-engine.md)。

### 精确边界

**引擎内嵌(题材包不可改的不变量)**:
- 七步顺序:选技能 -> 取招式 -> 算 AP/DP -> dodge 判定(`random(ap+dp)<dp`)-> parry 判定(`random(ap+pp)<pp`)-> 算伤害(hit_ob/hit_by 回调)-> inflict(receive_damage/wound)-> exp+riposte
- AP/DP 概率判定**结构**(具体公式不锁死,见下 PowerModel)
- Effect 调度/衰减/移除机制(挂 tick loop、duration 衰减、completed 移除)

**题材包注入(经注册表/Protocol)**:
- 每步具体数值/文案(`SkillData`)+ 钩子行为(`SkillBehavior` Protocol:`hit_ob`/`hit_by`/`post_action` 等,多数招式只填 `SkillData` 不实现钩子)
- AP/DP 求值公式(`PowerModel` 策略:引擎不变量收窄为"AP/DP 结构 + random 概率判定",公式题材包定,默认实现是武侠公式)
- condition handler(`EffectHandlerFn`,一个函数)+ 声明式 `StackingPolicy`(unique/refresh/stack/independent)/`EffectMode`(tick/wallclock)

### 三源证据(互证)

1. **LPC 源码**:`combatd.c do_attack()` 七步管线(21 门派数十年验证)+ `condition.c` heart_beat 调度 + daemon 自减 duration + CND_CONTINUE 标志。引擎层(`feature/`+`combatd.c`+`condition.h`)与题材内容层(`kungfu/skill/*`+`kungfu/condition/*`)**物理分离**,只靠宏和钩子签名耦合。
2. **旧引擎 archive**(`archive/engine-pre-m1-rewrite`):`resolve_attack(ctx: CombatContext) -> CombatRoundResult` 七步纯函数(副作用经 ledger 账本)+ `EffectComp` + `ConditionSystem.update`(tick 调度/衰减/移除)+ `CONDITION_HANDLERS` 注册表 + `register_condition(name, handler)` **注入点已留**,只是 12 个具体 handler 还硬编码在引擎(遗留耦合,非"流程归引擎"必然结果)。
3. **架构拆解研究产出 A06/D05**(`docs/archive/xkx-arch/_archive/_研究原始产出/`):明确命名"七步管线"并判断"新引擎应保留这一管线分层";D05 给出"流程/机制保留为引擎 vs 数值/文案/门派设定外提为题材包可配置"的详细边界表(剔除其分布式/WASM 技术选型,只取边界判断)。

### 设计对比(`/design-an-interface` 生成三个 radical 不同的边界方案)

- **极简数据驱动**(题材包零 Python,纯 YAML,接缝 1-2 个加载入口):UGC 最友好,但跨题材弱(七步+AP/DP 绑武侠近战),条件分支逻辑(如"对手若运功则伤害翻倍")表达不了,只能靠引擎新增固定钩子字段兜。
- **最大灵活/可替换骨架**(七步本身题材包定,引擎只剩四条护栏:存档可恢复/tick 可驱动/回合原子可观测/组件纯数据):跨题材最强,但武侠(最常见情况)boilerplate 重、浅模块(复杂度推给题材包未减)、前提是项目真要服务武侠之外题材否则过度设计。
- **骨架固定+钩子策略注入**(七步顺序+AP/DP 结构引擎内嵌,每步内容/钩子题材包注入):LPC + 旧引擎 archive 实证过的形状,深模块,接缝适中。**选定为主体**。

最终:以第三者为主体,grafting 第二者的 `PowerModel` 策略注入口--解决第三者自指的"`skill_power` 公式锁死武侠属性语义"裂缝(引擎不变量收窄为"AP/DP 结构 + `random(ap+dp)<dp` 概率判定",公式题材包定)。

### 后续影响

- 战斗/状态/技能/死亡轮回四子系统归类(08 号票,均 MVP 必做)**维持不变**,无需重评(本票确认暂定倾向,非改判)。
- M2 `/to-spec` 时按此接缝设计这四个子系统。
- 七步骨架不适用于非"AP/DP 概率"模型(回合制卡牌/实时动作);若未来这类题材成为主线,需写新 ADR 放开"战斗流程归题材包"。
