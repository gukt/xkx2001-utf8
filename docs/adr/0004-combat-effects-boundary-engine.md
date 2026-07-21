---
Status: accepted
---

# 战斗流程框架与效果生命周期机制归引擎，精确边界定稿

> **停机范围收窄（非改判归属）**：持续 Effect 生命周期仍属引擎职责，但**不是** M2/M3 停机必须兑现的不变量；见 [ADR-0007](0007-effect-lifecycle-deferred-from-m2-m3-stop.md)。

mvp-scope [02 号票](../../.scratch/mvp-scope/issues/02-engine-boundary-combat-effects.md)原为 9 票里唯一暂定挂起项，问"战斗结算流程框架"与"技能/效果生命周期机制"该归题材无关引擎还是题材包。经旧引擎 archive（`resolve_attack` 七步管线 + `ConditionSystem` + 已留 `register_condition` 注入点）、LPC 源码（`combatd.c do_attack` 七步 + `condition.c` heart_beat 调度）、架构拆解研究产出 A06/D05 三源互证，拍板：两者归引擎，精确边界为**引擎内嵌"七步顺序 + AP/DP 概率判定结构 + Effect 调度/衰减/移除机制"为不变量；题材包注入"每步具体数值/文案/钩子行为 + AP/DP 求值公式（PowerModel 策略）+ condition handler + 声明式 stacking_policy/EffectMode"**。这是"流程归引擎、数值归题材包"暂定倾向的精确落地，非改判，因此战斗/状态/技能/死亡轮回四子系统维持 MVP 必做归类不变。

## 考虑过的选项

用 `/design-an-interface` 生成三个 radical 不同的边界设计对比（完整对比与三源调研见 02 号票 Answer）：

- **极简数据驱动**（题材包零 Python，纯 YAML）：UGC 最友好，但跨题材弱（七步+AP/DP 绑武侠近战），且"对手若运功则伤害翻倍"这类条件分支逻辑表达不了，只能靠引擎新增固定钩子字段兜。
- **最大灵活/可替换骨架**（七步本身题材包定，引擎只剩四条护栏）：跨题材最强，但武侠（最常见情况）boilerplate 重，是浅模块（复杂度推给题材包未减少），前提是项目真要服务武侠之外题材，否则过度设计。
- **骨架固定+钩子策略注入**（七步顺序+AP/DP 结构引擎内嵌，每步内容/钩子题材包注入）：LPC 21 门派数十年 + 旧引擎 archive `register_condition` 注入点实证过的形状，深模块，接缝适中。**选定**。

最终方案以第三者为主体，grafting 第二者的 `PowerModel` 策略注入口--解决第三者自己指出的"`skill_power` 公式锁死武侠属性语义"裂缝：引擎不变量收窄为"AP/DP 结构 + `random(ap+dp)<dp` 概率判定"，公式题材包定。

## 影响

- 02 号票解除暂定挂起；战斗/状态/技能/死亡轮回四子系统归类（[08 号票](../../.scratch/mvp-scope/issues/08-subsystem-classification-research.md)，均 MVP 必做）维持不变，无需重评。
- M2 `/to-spec` 时，战斗/技能/状态/死亡轮回子系统按此接缝设计：`SkillBehavior` 钩子 Protocol（`hit_ob`/`hit_by`/`post_action` 等，多数招式只填 `SkillData` 数值不实现钩子）+ `EffectHandlerFn`（一个函数）+ 声明式 `StackingPolicy`（unique/refresh/stack/independent）/`EffectMode`（tick/wallclock）+ `PowerModel` 策略。
- Effect 生命周期（Module B）三设计高度趋同，直接采纳声明式 stacking 四枚举 + `INDEPENDENT` 逃生口 + tick/wallclock mode。
- 七步骨架不适用于非"AP/DP 概率"模型（回合制卡牌/实时动作）；若未来这类题材成为主线，需写新 ADR 放开"战斗流程归题材包"。
