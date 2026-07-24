# 04 战斗与效果生命周期簇 —— Phase 1 + Phase 2 评审委员会最终报告

> 产出：评审委员会（玩法切片策划 + 引擎架构师 A + UGC 游戏专家 + 现代战斗玩法设计师 + 商业化与增长专家）
> 审阅对象：Phase 1 初稿（`01-raw-findings/`、`02-user-stories/`、`03-engine-insights/`、`06-engine-critique/`）与 Phase 2 红队报告（`04-redteam-review/`）
> 任务：统一文风、消除矛盾、对分歧裁决、生成最终设计输入报告
> 约束：不做行为等价验证；不输出可直接落地的 engine 代码或接口契约；止步设计输入层

---

## 执行摘要

本次调研聚焦「战斗系统（7）+ 状态/Effect 系统（31）+ 死亡与轮回（39）」三系统的耦合链：**命中 -> 伤害 -> 状态播报 -> 死亡判定 -> 复活**。通过对 LPC 一手源码、`engine/src/openmud/` 已建模块、以及 13 份 Phase 1 初稿与 6 份 Phase 2 红队报告的交叉审阅，评审委员会形成以下结论：

1. **conditions.py 概念错位是全场最关键的设计输入**。`engine/src/openmud/conditions.py` 是通用布尔求值器（用于门条件、物品限制、NPC 行为），与 LPC `feature/condition.c` 所代表的时效性 Effect 引擎同名不同物。新引擎必须**新建独立 Effect 引擎模块**（而非复用/扩展 `conditions.py`），否则「中毒持续掉血」「内伤发作」「盲/醉/牢」等武侠核心体验无法承载。

2. **Effect 引擎缺失是级联断点**。它同时导致：命中后无法挂持续状态、状态无法反向驱动伤害、死亡后无法清状态、UGC 创作者无法声明毒/灼烧/封印等差异化资产。这是后续 engine 设计的 P0 缺口。

3. **ghost/地府轮回不应完全下沉题材包**。虽然 `abstraction-options.md` 与 `ugc-surface.md` 主张 ghost/地府归题材包内容，但 `CLAUDE.md` 架构不变量第 4 条已把「死亡与轮回（39）」列为 MVP 必做，`gameplay-slices.md` 切片 5 也明确纳入「玩家死亡下地府走轮回」。裁决：**engine core 至少提供 Ghost 状态标记、`is_ghost()` 可见性规则、死亡区入口接缝与通用命令白名单机制；具体房间叙事与谜题下沉题材包**。

4. **战斗操作面不应从「自动普攻」全面转向「主动按键」**。LPC 已有 `perform`/`exert` 作为主动绝技/内功层（`cmds/skill/perform.c`、`cmds/skill/exert.c`）；普攻自动循环是文本 MUD 阅读式沉浸的载体。现代化方向应是**强化 perform/exert 的资源管理与策略深度**，而非把每一招都改成手动按键。

5. **死亡惩罚采用「单次保留重量 + 当日封顶/连续递减 + 复活保护期」**，不采用「默认轻惩罚」。完全轻惩罚会消解地府轮回的仪式感；完全重惩罚会劝退。`player-psychology.md` 提出的递减/封顶方案更可持续。

6. **防秒杀不依赖简单硬上限，而依赖缩放曲线控制**。硬上限（如单次伤害不超过 max_qi 的 60%）会名义上保留、实质上废弃 `eff_qi/eff_jing < 0` 的 wound 致死路径。应**废弃 LPC 的 `level^3/3` 立方缩放，改用多项式/对数缩放 + 命中率 cap**，保留高手碾压空间但避免一刀秒杀。

7. **围攻机制保留多对手概念，但 PvP 默认收紧**。`MAX_OPPONENT=4` 的注意力分散意图值得保留，但当前实现是「受害者反击上限」而非「攻击者上限」，4v1 对受害者是火力碾压。裁决：**core 支持 N 对手敌对列表，`MAX_OPPONENT` 可配置；PvP 默认降至 2，并同步加入围攻惩罚（防御递减或攻击者伤害递减）**。

8. **付费红线收紧**：付费加速技能升级、付费缩短昏迷苏醒时间（PvP）、付费 PvP 保护期按次售卖、付费保留 skill_map 等，均存在越线或公平性风险，应禁止或仅限全玩家订阅福利。

---

## 范围与方法

### 审阅范围

- **Phase 1 初稿**（13 份）：
  - 一手考古：`01-raw-findings/source-inventory.md`、`gameplay-slices.md`、`mechanisms.md`
  - User Stories：`02-user-stories/player-stories.md`、`system-stories.md`、`operator-stories.md`
  - 引擎/现代/商业/数值/心理/创作者视角：`03-engine-insights/abstraction-options.md`、`ugc-surface.md`、`modern-design-review.md`、`player-psychology.md`、`commercialization.md`、`performance-review.md`、`numerical-balance.md`、`creator-perspective.md`
  - engine 批判对照：`06-engine-critique/engine-comparison.md`
- **Phase 2 红队报告**（6 份）：`04-redteam-review/cross-check-report.md`、`modern-challenges.md`、`player-experience-risks.md`、`commercial-risks.md`、`performance-risks.md`、`numerical-risks.md`

### 方法

1. 以 LPC 一手源码为唯一真相源，所有结论均标注 `文件路径:函数/对象名`。
2. 对 Phase 1 各文件之间的矛盾点显式裁决，给出委员会立场与理由。
3. 对 Phase 2 红队每条质疑给出 `accept`（接受并纳入结论）、`reject`（驳回并说明理由）、`待澄清`（证据不足或需后续 spec 阶段决策）三类裁决。
4. 报告仅输出设计方向与输入，不输出接口契约、字段签名或可落地代码。

---

## 现状总览：四层脉络 + 耦合链

LPC 的战斗/Effect/死亡/武功四系统由 `inherit/char/char.c:heart_beat()` 统一 tick 驱动，形成完整耦合链。

### 1. 战斗层：命中 -> 伤害

- **交战原语**：`feature/attack.c` 维护 `enemy[]`/`killer[]` 双列表，`fight_ob()` 入 `enemy`、`kill_ob()` 同时入 `killer`；`MAX_OPPONENT=4`（`attack.c:12`），`select_opponent()` 每 tick 从前 4 个敌人中随机选 1 个反击（`attack.c:79-88`）。
- **命中结算**：`adm/daemons/combatd.c:do_attack()` 七步流水线：选技能 -> 取招式 action mapping -> 算 AP/DP/PP -> 闪避/招架判定 -> 命中后伤害叠加 -> 施加伤害 -> 经验/反击/后处理（`combatd.c:340-780`）。
- **伤害类型**：三类伤害 `jing`（精）、`qi`（气）、`jingli`（精力）；`receive_damage()` 扣当前值，`receive_wound()` 扣 `eff_*` 上限（`feature/damage.c:13-66`）。
- **武功作为载体**：`feature/skill.c` 维护 `skills`/`learned`/`skill_map`/`skill_prepare`；`reset_action()` 按映射武功动态取 action mapping（`feature/attack.c:143-171`）；`perform`/`exert` 提供主动绝技/内功层（`cmds/skill/perform.c`、`cmds/skill/exert.c`）。

### 2. Effect 层：状态播报

- **引擎形态**：`feature/condition.c` 维护 `conditions` mapping，由 `heart_beat` 每 `5+random(10)` tick 调用 `update_condition()`；每个 condition 是独立外部 daemon（`/kungfu/condition/<name>.c`），返回 `CND_CONTINUE` 续命、否则移除（`condition.c:21-69`）。
- **内容层**：`kungfu/condition/` 下 72 个 daemon，覆盖毒、伤害、控制、牢狱、治疗、通缉等（`creator-perspective.md` §0）。
- **注入点**：武功 `hit_ob`、武器 `hit_ob`、药物 `feed_ob`、战斗奖励 `killer_reward` 等均可 `apply_condition()`。

### 3. 死亡判定层

- **两段式判定**：`char.c:100-104` `eff_qi<0 || eff_jing<0` -> 直接 `die()`（上限伤致死）；`char.c:108-115` `qi/jing/jingli<0` 且 `living()` -> `unconcious()`，已昏迷再负 -> `die()`。
- **昏迷副作用**：`feature/damage.c:unconcious()` 清零资源、`disable_player(" <昏迷不醒>")`、`block_msg/all=1` 屏蔽消息、`call_out("revive", random(100-con)+30)` 苏醒（`damage.c:105-135`）。
- **死亡副作用**：`die()` 清状态、造尸体、`death_penalty`（经验/潜能/存款/技能惩罚）、`killer_reward`（PK 计数/通缉）、变鬼进地府（`damage.c:152-253`）。

### 4. 复活/轮回层

- **鬼魂态**：`feature/damage.c:9-11` `ghost`/`is_ghost()`；`char.c:181-186` `visible()` 规则——鬼魂只对鬼魂或 `astral_vision` 可见。
- **地府流程**：`d/death/` 13 房间，`gate.c` 销毁物品/清状态/禁战，`gateway.c` 禁止回头，`road2.c` 迷雾循环，`inn1.c` 主动复活谜题，`wgargoyle.c` 白无常 55 秒自动复活（`gameplay-slices.md` 切片 5）。
- **复活**：`reincarnate()` 满血但不恢复经验/技能/善恶/潜能/存款（`damage.c:255-264`）。

### 5. 完整耦合链

```
kill/fight/hit 命令
  -> feature/attack.c 建立 enemy/killer
    -> char.c:heart_beat() 驱动 attack()
      -> combatd.c:do_attack() 命中结算
        -> receive_damage/receive_wound 扣血/扣上限
          -> 武功/武器 hit_ob 注入 Effect
            -> feature/condition.c:update_condition() 每 N tick 发作
              -> condition daemon 反向调用 receive_damage/receive_wound
                -> char.c:heart_beat() 检查 eff/qi/jing/jingli 负值
                  -> unconcious() / die()
                    -> death_penalty / killer_reward / make_corpse / ghost=1 / move(DEATH_ROOM)
                      -> d/death/ 地府流程 -> reincarnate() 复活
```

---

## 关键发现

### 发现 1：conditions.py 概念错位是新 engine 最大的设计债

- **证据**：`engine/src/openmud/conditions.py:1-22` 文档自述为「门条件 / 物品使用限制 / NPC 行为条件的共同条件子语言」；其节点为 `Predicate/Equals/Gte/And/Or/Not`（`:92-142`），`evaluate()` 返回 `bool`。
- **对照**：LPC `feature/condition.c:8` 的 `mapping conditions` + `:21-69` 的 `update_condition()` 是由 `heart_beat` 驱动、调用外部 daemon、可执行副作用（扣血/移动/改属性）的**时效性 Effect 引擎**。
- **结论**：两者仅共享「condition」一词，语义完全不同。`06-engine-critique/engine-comparison.md` 模块 3 将其列为「最严重负面遗漏」，评审委员会**确认**该判断。新引擎应新建 `effects.py` 类模块承载时效 Effect，`conditions.py` 应重命名或文档强标为「布尔门控谓词」。

### 发现 2：engine 战斗数值塌缩为单一 qi，丢失武侠纵深

- **证据**：LPC `feature/damage.c:13-66` 三类伤害 + `current/eff/max` 三层结构；engine `combat_system.py:240` 只写 `vitals.qi_current`，`components.py:460` 的 `Vitals` 无 `eff_*` 层。
- **影响**：「中毒耗精」「内伤降上限」「精力耗尽昏倒」等机制无法表达；`damage_type` 在 engine 中退化为文案标签。

### 发现 3：多对手围攻与 fight/kill 语义在 engine 中完全缺失

- **证据**：LPC `feature/attack.c:15-16` `enemy[]`/`killer[]`、`MAX_OPPONENT=4`；engine `components.py:692-698` `Engaged` 仅单 opponent，`combat_system.py:100-104` 拒绝第二对手。
- **影响**：MVP 场景「组队围攻」无引擎支撑；「切磋 vs 拼死」的社交意图区分也无法表达。

### 发现 4：ghost/地府轮回与 engine 现状存在 MVP 张力

- **证据**：`CLAUDE.md` 架构不变量第 4 条把「死亡与轮回（39）」列为 MVP 必做；`gameplay-slices.md` 切片 5 是「玩家死亡下地府走轮回」；但 `engine/src/openmud/death.py:13-18` 只有 `ALIVE/UNCONSCIOUS/DEAD` 三态，无 GHOST；`death_flow.py:256-264` 是直接传送复活。
- **委员会裁决**：core 提供 Ghost 状态与可见性规则 + 死亡区入口接缝；具体 room 叙事下沉题材包（详见下文「设计建议」）。

### 发现 5：LPC 数值设计存在多个崩坏点，新引擎不应继承

- **立方缩放**：`combatd.c:317` `power = level^3/3`，等级差 2 倍则 power 差 8 倍，高等级碾压低等级至命中率趋近 100%/0%。
- **伤害 6+ 层乘法叠加**：`combatd.c:519-631` 多层随机叠加，无硬上限，可一击必杀（`s_combatd.c:530-533` 原上限被注释）。
- **经验值概率减伤**：`combatd.c:636-641` 用 `combat_exp` 当第二防御属性，使老玩家凭时长获得生存优势，与「配装驱动」现代理念冲突。
- **Effect 强度不统一**：同样 duration=100，`bt_poison` 总伤约 1000，`hanbing_damage` 约 14000，差 14 倍（`numerical-risks.md` §3.1）。

### 发现 6：玩家体验惩罚导向过重，必须补保护机制

- **死亡惩罚六重叠加**：经验、潜能、存款、技能等级、善恶、物品销毁，无单日/连续死亡递减（`player-experience-risks.md` §2）。
- **中毒/被控无力感**：多数毒无低门槛解除路径，玩家只能等死；控制效果直接剥夺行动/社交权（`player-psychology.md` §3）。
- **PvP 霸凌温床**：`MAX_OPPONENT=4` 限制的是受害者反击数而非攻击者数；`hit` 偷袭不触发 pker 累积；复活点无保护期（`player-experience-risks.md` §4）。

### 发现 7：商业化支撑点数据基建严重缺失

- `SkillData`/`ItemTemplateKey` 无 `pack_id`/`creator_id`/`version`；
- `Currency` 无双货币类型；
- 战斗/死亡事件上下文无 `pack_id`；
- `SKILLS`/`_SKILL_BEHAVIORS` 是模块全局变量，未按 World 隔离（`commercial-risks.md` §4-5）。

---

## 三层 User Stories 汇总

### 玩家层（Player Stories）

| 编号 | 核心诉求 | 来源 | 关键验收点 |
|------|---------|------|-----------|
| US-1 | kill/fight/hit 三档起手控制战斗烈度 | `player-stories.md` US-1 | kill 单方成立、fight 双向同意、hit 仅限玩家间一招 |
| US-2 | perform/exert 施展武功绝技与内功 | US-2 | 需先 enable；成功后加 perform 冷却 condition；消耗 neili/jingli |
| US-3 | 被毒/状态折磨时有分级播报与毒抗减毒 | US-3 | 状态分轻/中/重；毒抗技能缩短 duration；condition 杀人有死因叙事 |
| US-4 | 醉酒/刺目/嵌入暗器等控制状态有恢复路径 | US-4 | 醉酒三段非线性曲线；刺目/嵌入可恢复/拔除；包扎慢修复 |
| US-5 | 昏迷后有苏醒希望但恐惧被补刀 | US-5 | 资源负值触发昏迷；昏迷可被 TYPE_QUICK 继续攻击；苏醒时间与 con 正相关 |
| US-6 | 死亡走地府轮回最终满血复活但承受惩罚 | US-6 | 死亡扣数值；地府禁战/清物品；白无常 55 秒自动复活；隐藏主动复活路径 |
| US-7 | 城内 PK 触发官府通缉与红名惩罚 | US-7 | 城市内杀人挂 killer condition；pker 累计过高禁止再 PK |
| US-8 | 组队跟随与多人围攻 | US-8 | 跟随队长移动；被围攻者每 tick 只反击前 4 人中随机 1 人；队长倒下溃散 |
| US-9 | 感知 NPC 自动开战原因 | US-9 | hatred/vendetta/aggressive/berserk 四类自动触发；NPC 不互咬 |
| US-10 | 装备武器护具配置 build | US-10 | 数值累加到 apply；双手/双持/副手盾槽位互斥；特殊护具命中回调 |
| US-11 | 打不过时自动/手动逃跑 | US-11 | wimpy 气血阈值自动 flee；逃跑清当前战斗但不清旧仇 |
| US-12 | 伤势双层模型与疗伤/包扎恢复 | US-12 | current vs eff 分层；战斗中回血减速；内功疗伤修 eff；包扎慢修复 |

### 系统/NPC 层（System Stories）

来源：`system-stories.md`

- **心跳循环**：`char.c:heart_beat` 每 tick 驱动战斗/死亡判定/condition 更新/回血；静止时关闭心跳节能。
- **Effect 引擎**：`condition.c:update_condition` 每 `5+random(10)` tick 遍历 conditions；daemon 懒加载/容错；返回 `CND_CONTINUE` 续命。
- **昏迷/苏醒**：`unconcious()` 注册 `call_out("revive", random(100-con)+30)`；苏醒时移出容器；安全区 `no_death` 降级为昏迷。
- **死亡流程**：`die()` 清状态、造尸体、死亡惩罚、击杀奖励、变鬼进地府；`reincarnate()` 满血。
- **NPC AI**：`npc.c:chat()` 自动 exert/recover/perform；`trainee.c` 驯兽跟随/咬人。
- **自动开战**：`attack.c:init()` 按 hatred/vendetta/aggressive 触发 `auto_fight`。

### 巫师/运营层（Operator Stories）

来源：`operator-stories.md`

- **配武功**：YAML 声明 `SkillData`/`SkillMove` 已支持；缺动态选招、perform 大招、多源 hit_ob/hit_by 钩子。
- **挂 Effect**：当前完全缺失——`conditions.py` 是布尔求值器，不是 Effect 引擎（US-W07 最高优先级缺口）。
- **调数值**：PowerModel 可整体替换，但 `DefaultWuxiaPowerModel` 调参空间不足；无数值沙盒/平衡校验。
- **设死亡惩罚**：`DeathPolicy` 已数据化，但缺分项惩罚、地府叙事流程、PK 后果、ghost 态。
- **装备**：`Equippable` 占位，无数值接入战斗，无 `stat_prop`/`cosmetic` 双槽。
- **商业埋点/归属**：`SkillData`/`ItemTemplateKey`/`DeathContext`/`CombatRoundResult` 均缺 `pack_id`/`creator_id`/`version`。

---

## 设计建议

### 1. Engine Core 方向

#### 1.1 交战/敌对关系原语

- **结论**：core 提供 N 对手敌对列表 + `fight`/`kill` 双语义 + 同房/living 清理规则 + 和平区拦截。
- **理由**：LPC `enemy[]`/`killer[]` 是战斗社交（围攻、守卫、结仇）的基础（`feature/attack.c:15-16`、`combatd.c:852-962`）。
- **可下沉题材包**：auto_fight 的具体原因（hatred/vendetta/aggressive/berserk）与组队 leader/lord 社交结构。
- **裁决差异**：`abstraction-options.md` §1 方向 B 已建议此路径，委员会**确认**并纳入最终结论。

#### 1.2 命中/伤害结算

- **结论**：保留七步骨架 + AP/DP 概率结构（ADR-0004）；伤害按 `damage_type` 路由到**命名资源池**；资源池至少支持 `current`/`max`，可选 `effective_cap`（eff 伤口层）。
- **理由**：LPC 三类伤害（jing/qi/jingli）与 wound 上限是武侠核心纵深；但题材无关化要求资源名可配置（科幻可加 shield/armor 池）。
- **裁决差异**：`abstraction-options.md` §2 方向 B 已建议此路径，委员会**确认**。
- **关键补充**：必须显式配置「哪些资源池耗尽触发昏迷/死亡」（红队 `cross-check-report.md` §2.2 质疑），避免把 jing/jingli 昏迷语义丢失。

#### 1.3 Effect 时效引擎

- **结论**：**新建独立 Effect 引擎模块**（不要复用 `conditions.py`）。形状为薄调度器 + 题材包 EffectHandler：
  - core 负责挂载/查询/移除 Effect 实例、tick 调度、stacking policy（unique/refresh/stack/independent）。
  - 题材包提供 EffectHandler 函数体，处理伤害/治疗/移动/改属性/触发昏迷等副作用。
- **A 轨（UGC 可写）**：声明式 schema 覆盖纯数值型持续伤害/治疗/属性修正（type/duration/tick_damage/tick_message/expire_action）。
- **B 轨（可信 Python）**：覆盖位移、社交 emote、装备联动、改世界状态等副作用，走白名单枚举（`move_to_room`/`deal_damage`/`clear_effect`）。
- **理由**：LPC 72 个 condition daemon 中大量含任意副作用（`city_jail.c:9` `move`、`embedded.c:23` 调 `remove` 命令、`aphroclisiac.c:35-43` 扫描房间），A 轨无法全部覆盖（红队 `cross-check-report.md` §2.1 质疑）。
- **裁决差异**：委员会**部分接受** `abstraction-options.md` §3 方向 C 的薄调度器思路，但**明确** A 轨只能覆盖毒/伤/属性修正等数值型 Effect，副作用型必须走 B 轨。

#### 1.4 死亡状态机与复活策略

- **结论**：保留 `death.py` 纯函数 `next_death_state`（ADR-0004/0007）；触发条件从单 qi 扩展为「任一关键资源耗尽」；把复活路径抽成可配置 `ReviveStrategy` 接缝。
- **Ghost 态**：core 提供 `Ghost` 组件 + `is_ghost()` 可见性规则 + 死亡区入口接缝 + 受限动词白名单；具体地府 room 叙事下沉题材包。
- **理由**：`CLAUDE.md` 架构不变量把死亡与轮回列为 MVP 必做；但 ghost 可见性、鬼域禁武等是任何「死亡区」都可能需要的通用机制。
- **裁决差异**：委员会**推翻** `modern-design-review.md` §4.3「地府/鬼魂态为题材包可选内容」的结论，改为「core 提供最小 ghost 机制 + 题材包填 room 内容」。

#### 1.5 武功招式调度

- **结论**：`SkillData`/`SkillMove` 声明式数据保留；`SkillBehavior` 扩展：
  - 增加 `choose_move(ctx) -> SkillMove` 可选钩子，允许题材包覆盖默认最高 force 选招策略（对应 LPC `query_action`）。
  - 明确 `hit_ob`/`post_action` 可调 EffectEngine.apply_effect，作为「招式挂持续 Effect」的官方路径。
  - 增加 `on_improve`/`on_death_penalty` 可选成长钩子（对应 LPC `skill_improved`/`skill_death_penalty`）。
- **理由**：LPC `18-zhang.c:241-291` 的 `query_action` 动态选招与 `sanhui` 三叠连击无法被静态 `SkillMove` 表达；但多数招式仍是纯数据。
- **裁决差异**：委员会**接受** `abstraction-options.md` §6 方向 B 的建议，但**待澄清** `choose_move` 返回值是否允许携带 `post_action` 等行为钩子（红队 `cross-check-report.md` §2.3 质疑）。

### 2. UGC 创作面方向

- **声明式数据轨扩大**：招式（`SkillData`/`SkillMove`）、死亡策略（`DeathPolicy`）、掉落表（`LootTable`）、门派技能池（`factions:`）已 YAML 化，继续扩展至 Effect 声明式 schema 与装备数值 schema。
- **Effect 创作面**：提供声明式 schema（type/duration/tick_damage/tick_message/expire_action/stack_rule/tags），让 UGC 创作者无需写 daemon 即可配毒/灼烧/冰冻等；副作用型仍走可信 B 轨。
- **装备双槽**：`Equippable` 明确分 `stat_prop`（数值，不可付费）与 `cosmetic`（外观，可付费），并接入战斗数值。
- **数值沙盒与平衡校验**：题材包加载时提供「一招在指定属性下的期望伤害/命中率/击杀回合」预览；对 DPS 异常、Effect 总伤过高、惩罚占比过大等告警。
- **资产归属字段**：`SkillData`/`ItemTemplateKey`/Effect handler/`LootTable` 追加 `pack_id`/`creator_id`/`version`，支撑创作者分成与埋点。

### 3. 现代化方向

- **战斗定位**：「半自动」——普攻自动循环 + `perform`/`exert` 主动绝技/内功 + 战斗外 build 配置。不追求动作游戏的逐键操作。
- **伤害管线正式化**：把 LPC 散落的 force/martial/weapon/armor/dodge 多层 `hit_ob`/`hit_by` 重构成有序 Damage Pipeline，统一返回结构（message/damage_bonus/applied_effects），消除 `stringp/intp/mapp` 多态判定的技术债。
- **Effect 强制叠加策略**：引擎层提供 stack/refresh/replace + 优先级 + source 归属 + dispellable 标志，不放给内容层。
- **CC 分类与韧性**：若做 PvP，必须引入硬控/软控分类 + tenacity + diminishing return（DR），防止无限连控。
- **复活策略可配**：地府轮回作为题材包可选叙事；引擎默认提供「复活点 + 轻惩罚」策略，但惩罚参数可配。

### 4. 数值平衡方向

- **替换立方缩放**：`skill_power` 改用多项式/对数缩放，保留成长曲线但控制上限；同时引入命中率 cap（如 5%~95%）。
- **收敛伤害层数**：从 LPC 的 6+ 层乘法叠加收敛到 2-3 层（基础伤害 + 暴击/伤口 + 减伤）。
- **保留两层伤害模型**：`damage` 扣 current、`wound` 扣 eff，制造轻伤/重伤区分。
- **废弃经验值概率减伤**：避免用时长当防御属性。
- **死亡惩罚模型**：分项可配（exp/potential/currency/skill_exp），但默认采用「单次保留重量 + 当日封顶/连续递减 + 复活保护期」；不采用单一 10% 统一比例。
- **防秒杀**：不采用简单硬上限，而通过缩放曲线 + 命中率 cap + wound 机制共同控制。

---

## Engine 对照结论

引用 `06-engine-critique/engine-comparison.md` 要点：

| 维度 | LPC 设计 | Engine 现状 | 委员会结论 |
|------|---------|------------|-----------|
| **Effect 引擎** | `feature/condition.c` 时效性 daemon 驱动（`kungfu/condition/` 72 个 daemon） | `conditions.py` 是布尔求值器，**完全缺失**时效 Effect 引擎 | 最严重负面遗漏；必须新建独立 Effect 模块 |
| **三类伤害** | `jing`/`qi`/`jingli` + `current`/`eff`/`max` 三层 | 只扣 `qi_current`，无 eff 层 | 塌缩为单层，丢失武侠纵深 |
| **多对手围攻** | `enemy[]`/`killer[]`、`MAX_OPPONENT=4` | `Engaged` 单 opponent，严格 1v1 | MVP 场景「组队围攻」无支撑 |
| **hit_ob 多源链** | force/martial/weapon/armor/dodge 多层 | 仅单一 `SkillBehavior.hit_ob` | 武功表达力受限，武器毒/内功特效无法分别接入 |
| **ghost/地府** | `ghost` 态 + `d/death/` 13 房间轮回 | 无 ghost，死亡直接传送复活 | 与 MVP 必做冲突；core 需提供最小 ghost 机制 |
| **DeathPolicy** | `combatd.c:death_penalty` 硬编码分项惩罚 | `DeathPolicy` YAML 数据驱动 | 方向正确，但缺分项配置与 ghost/地府接缝 |
| **SkillData** | LPC 武功是 `.c` daemon | YAML 纯数据 + 可选 `SkillBehavior` | 方向正确，利于 UGC；但缺动态选招/perform/成长钩子 |
| **PowerModel** | `s_combatd.c:skill_power` 硬编码 `level^3/3` | Protocol 可整体替换 | 方向正确；但默认模型维度不足，需扩展 |
| **事件/vetoable** | LPC 无前置否决点 | `ON_BEFORE_COMBAT_ROUND`/`ON_BEFORE_DEATH` 可否决 | engine 正面改进 |
| **纯函数化** | `do_attack` 直接改 victim dbase | `resolve_attack` 纯函数，apply 分离 | engine 正面改进，利于测试 |

**conditions.py 概念错位重点强调**：
- `conditions.py` 的 `Predicate/Equals/Gte/And/Or/Not` 解决的是「能不能」的静态布尔判定问题；
- LPC `condition.c` 解决的是「持续在身上发生什么」的时效副作用调度问题；
- 两者不应合并，否则会把 Effect 框架拖入理解 Predicate AST 的耦合，重蹈 LPC `condition` 一词多义覆辙。

---

## Phase 1 文件间矛盾裁决表

| 矛盾点 | 涉及文件 | 各文件立场 | 委员会裁决 | 理由 |
|--------|---------|-----------|-----------|------|
| ghost/地府进 core 还是下沉题材包 | `modern-design-review.md` §4.3 vs `abstraction-options.md` §5 vs `CLAUDE.md` 架构不变量 | modern-review：题材包可选；abstraction-options：core 只留中间态接缝；CLAUDE.md：死亡与轮回 MVP 必做 | **折中**：core 提供 Ghost 组件 + 可见性规则 + 死亡区入口接缝 + 受限动词白名单；具体 room 叙事与谜题下沉题材包 | 满足 MVP 必做底线，同时保留题材无关性 |
| 战中是否必须主动选招 | `modern-design-review.md` §5.3 vs `modern-challenges.md` §1.1 | modern-review：不主动选招是最大过时点，需改为主动按键；modern-challenges：perform/exert 已是主动面，普攻自动是文本 MUD 沉浸源 | **支持 modern-challenges**：保留自动普攻循环；强化 perform/exert 主动层 | 文本 MUD 核心竞争力是阅读与 build，不是 APM |
| 死亡惩罚默认轻重 | `modern-design-review.md` §4.3/§6.2 vs `player-psychology.md` §6.2 | modern-review：默认轻惩罚；player-psychology：递减与封顶 | **支持 player-psychology**：单次保留重量 + 当日封顶/连续递减 + 复活保护期 | 完全轻则死亡无意义，完全重则恶性循环 |
| 防秒杀硬上限 vs 保留 wound 机制 | `player-psychology.md` §6.4 vs `modern-design-review.md` §2.3/§6.1 | player-psychology：建议硬上限；modern-review：保留 wound 上限伤害 | **折中**：不采用简单硬上限，通过控制缩放曲线 + 命中率 cap + wound 机制防秒杀 | 硬上限会废弃 `eff<0` 致死路径 |
| MAX_OPPONENT=4 围攻限制 | `modern-design-review.md` §1.3/§6.1 vs `player-psychology.md` §6.7 | modern-review：保留注意力分散意图；player-psychology：PvP 限制 2v1 | **折中**：core 支持可配置 N 对手，PvP 默认 2，并加围攻惩罚 | 保留设计意图，但防止 PvP 霸凌 |
| use-based 技能成长 | `modern-design-review.md` §5.3 vs `modern-challenges.md` §1.2 | modern-review：争议大，建议加可分配点数；modern-challenges：保留 use-based 为默认 | **支持 modern-challenges**：保留 use-based 为默认，可分配点数作为题材包可选 | 无心理证据表明 use-based 是流失源；技能数上限已约束挂机 |
| 付费加速技能升级 | `commercialization.md` §1.2 vs `numerical-balance.md` §7.1 | commercialization：边界安全；numerical-balance：红线 | **支持 numerical-balance**：禁止付费加速技能等级成长 | 技能等级直接影响战斗胜负，加速等同于提前获得数值优势 |
| 付费 PvP 保护期 | `commercialization.md` §1.5 vs `player-psychology.md` §6.3 vs `commercial-risks.md` §6.1 | commercialization：边界安全；player-psychology：必须基础机制；commercial-risks：按次付费破坏公平 | **支持 commercial-risks**：PvP 保护期作为全玩家基础机制或订阅通用福利，不得按次付费 | 否则免费玩家成为付费玩家猎物 |
| Effect A 轨覆盖率 | `abstraction-options.md` §3 / `ugc-surface.md` §2.2 vs `cross-check-report.md` §2.1 / `numerical-risks.md` §3.4 | 前者：薄调度器 + A 轨声明式覆盖大部分；后者：A 轨只能拟合毒/伤，大量副作用型需 B 轨 | **支持后者**：A 轨仅覆盖数值型 Effect；副作用型走 B 轨受限 Python | 72 个 daemon 中位移/社交/控制/装备联动无法纯声明式表达 |

---

## 红队质疑裁决表

### Cross-check-report（横向交叉检查）

| 序号 | 质疑 | 裁决 | 理由 |
|------|------|------|------|
| 1 | `hit` 偷袭与 `wimpy` 自动逃跑在抽象方案中位置不明确 | **待澄清** | 两者确实是重要机制，但 `hit` 可视为 `try_engage` + 单回合约束的特例；`wimpy` 应进 core 但需后续 spec 确认事件点 |
| 2 | `perform` 大招概念在抽象方案中覆盖不足 | **accept** | `abstraction-options.md` §6 未将 perform 列为必补钩子；应在 `SkillBehavior` 或独立绝技层补 perform 概念 |
| 3 | `choose_move` 难以完整替代 `query_action`（无法携带 post_action 闭包） | **待澄清** | 需 spec 阶段明确 `choose_move` 返回值是否允许携带行为钩子；若只返回 `SkillMove` 则丢失动态招式能力 |
| 4 | A 轨声明式无法覆盖 72 个 condition 中的大量副作用型 | **accept** | A 轨只能拟合毒/伤等数值型 Effect；位移/社交/控制/装备联动需 B 轨 |
| 5 | `CND_NO_HEAL_UP` 预留未用 | **accept** | `mechanisms.md` 已确认全仓无实现；新引擎应补「中毒/重伤抑制回血」语义 |
| 6 | `block_msg/all` 昏迷消息屏蔽未在抽象中讨论 | **待澄清** | 属于昏迷态行为约束的一部分，建议纳入 Unconscious 组件行为规格，但不影响当前设计输入 |
| 7 | ghost/地府完全下沉题材包与 brief MVP 场景冲突 | **accept** | 委员会已裁决 core 需提供最小 ghost 机制 |
| 8 | `start_death` 函数缺失应单独标出 | **accept** | 虽是 LPC 无定义函数，但 engine 设计死亡区入口时应显式定义对应回调 |
| 9 | 多复活触发点未在 ReviveStrategy 中表达 | **待澄清** | 需 spec 阶段确认 ReviveStrategy 是否支持多入口（NPC 剧情/玩家主动/道具） |
| 10 | 队长倒下即溃散是否保留未明确 | **待澄清** | 属于组队战斗规则，建议默认保留 LPC 行为，但题材包可配置队长转移 |
| 11 | 伪通用：EffectEngine 薄调度器 + A 轨只能拟合毒/伤 | **accept** | 已纳入最终设计建议 |
| 12 | 命名资源池需显式声明「关键池耗尽触发昏迷」 | **accept** | 已纳入最终设计建议 |
| 13 | `s_combatd.c` Anubis 双手互博应作为 engine 潜在遗漏单独评估 | **待澄清** | brief 未明确排除，但 Anubis 是 prototype；建议作为 post-MVP 扩展点记录 |

### Modern-challenges（现代玩法挑战）

| 序号 | 质疑 | 裁决 | 理由 |
|------|------|------|------|
| 1 | 不主动选招不是最大过时点，perform/exert 已是主动面 | **accept** | 委员会已裁决保留自动普攻 + 强化 perform/exert |
| 2 | use-based 成长应保留为默认 | **accept** | 委员会已裁决保留 use-based，可分配点数为可选 |
| 3 | guard 是对峙张力，不应判为节奏断裂 | **accept** | guard 的武侠对峙叙事价值应保留；但应降低触发频率避免低力量玩家频繁空转 |
| 4 | Effect 稀释频率是性能设计，不应强制对齐普攻 | **accept** | 委员会已裁决保留 `5+random(10)` 稀释作为默认；题材包可配 |
| 5 | 默认轻惩罚会消解轮回叙事重量 | **accept** | 委员会已裁决采用「单次重量 + 当日封顶/连续递减」 |
| 6 | 死亡全清物品不应整体丢弃，应保留尸体掉落、去除地府二次销毁 | **accept** | 尸体掉落机制保留；地府 `gate.c` 二次销毁视为过度惩罚，可去除或题材包可选 |
| 7 | 地府/鬼魂态应作为引擎 MVP 能力实现 | **accept** | 委员会已裁决 core 提供最小 ghost 机制 |
| 8 | 鬼魂态不是独立可选机制，而是地府附属组件 | **accept** | 与 `ugc-surface.md` §4.3 结论一致 |
| 9 | LPC 地府是半成品，应重新设计而非保留精神 | **accept** | 白无常 55 秒强制等待、road3 未完成、隐藏复活无提示均应作为设计缺陷改进 |
| 10 | 防秒杀硬上限与保留 wound 机制二选一 | **accept** | 委员会已裁决通过缩放曲线 + 命中率 cap 控制，而非简单硬上限 |
| 11 | 围攻限制 2v1 与 MAX_OPPONENT 注意力分散意图冲突 | **accept** | 委员会已裁决可配置 N + PvP 默认 2 + 围攻惩罚 |

### Player-experience-risks（玩家体验风险）

| 序号 | 质疑 | 裁决 | 理由 |
|------|------|------|------|
| 1 | 命中率模型对弱者接近 100% miss，严重度被低估 | **accept** | 立方缩放 + 无 cap 确实让高低等级交互失衡；应引入命中率 cap |
| 2 | 伤害无硬上限导致秒杀，严重度被低估 | **部分 accept** | 认同秒杀风险极高，但解决方案是缩放曲线 + 命中率 cap，而非简单硬上限 |
| 3 | wimpy 默认关闭使新手失去逃生阀，新手保护期应扩展为必须 | **accept** | 委员会已纳入最终建议：扩展新手保护期 + 默认低阈值 wimpy |
| 4 | 死亡惩罚六重叠加且无封顶/递减，是核心弃游机制 | **accept** | 委员会已裁决采用递减/封顶 |
| 5 | 物品全销毁是劝退级惩罚 | **accept** | 保留尸体掉落，去除/可选化地府二次销毁 |
| 6 | 中毒/被控后缺乏可执行解除路径，应作为 P0 风险 | **accept** | 必须保证每种负面 Effect 至少一条普通玩家可执行解除路径 |
| 7 | `CND_NO_HEAL_UP` 预留未用，应补上抑制回血 | **accept** | 新引擎 Effect 应支持抑制自然回血标记 |
| 8 | MAX_OPPONENT=4 是霸凌温床而非平衡阀 | **accept** | 委员会已裁决可配置 N + PvP 收紧 + 围攻惩罚 |
| 9 | PvP 保护期、复活保护期、反 PK 累积必须实现 | **accept** | 委员会已纳入最终建议 |
| 10 | 战斗信息默认应精简 | **accept** | 默认开启精简战斗描述 + 结构化状态条 |

### Commercial-risks（商业化风险）

| 序号 | 质疑 | 裁决 | 理由 |
|------|------|------|------|
| 1 | 付费加速技能升级与数值红线矛盾，应禁止 | **accept** | 委员会已裁决禁止 |
| 2 | 付费保留 skill_map 是 skill_death_penalty 副作用的一部分，应改为订阅/全玩家福利 | **accept** | 同意其边界模糊；若提供，应为全玩家通用 |
| 3 | shen/阵营损失付费保留过宽，可能影响门派/任务/战斗准入 | **accept** | 阵营影响 NPC 态度与 berserk 触发，不应简单判为可付费保留 |
| 4 | `DeathPolicy.penalty_ratio` 单一比例无法表达 LPC 分项惩罚，也限制合规付费设计 | **accept** | 建议扩展为分项可配（exp/potential/currency/skill_exp） |
| 5 | 付费跳地府迷宫虽为便利，但降低了死亡惩罚整体痛感，不应 premium 独占 | **accept** | 可作为订阅/全玩家福利，不得按次付费 |
| 6 | engine 温和死亡惩罚若被题材包改回 LPC 重惩罚，会放大 pay-to-win 风险 | **accept** | 需在题材包审核/validate 层监控惩罚模型 |
| 7 | engine 无法区分数值件与外观件，留下付费装备越线后门 | **accept** | 必须补 `stat_prop`/`cosmetic` 双槽 schema |
| 8 | 坐骑 speed 双用途陷阱，engine 必须拆分移动/战斗 speed | **accept** | 已纳入最终建议 |
| 9 | 付费缩短昏迷苏醒时间在 PvP 中是生存能力加成 | **accept** | 仅限非 PvP 场景或全玩家福利 |
| 10 | Effect 引擎缺失是商业化最高优先级结构性缺口 | **accept** | 已列为 P0 |
| 11 | 武功/装备/Effect 均缺少创作者归属字段 | **accept** | 已纳入最终建议 |
| 12 | `SKILLS` 全局注册表未按 World 隔离 | **accept** | 已纳入最终建议 |
| 13 | `Currency` 无双货币类型 | **accept** | 已纳入最终建议 |
| 14 | 事件上下文无 `pack_id`，无法落地埋点 | **accept** | 已纳入最终建议 |
| 15 | 无 `LedgerEntry` 账本抽象 | **accept** | 已纳入最终建议 |
| 16 | PvP 保护期按次付费会破坏公平生态 | **accept** | 已裁决作为基础机制或订阅福利 |
| 17 | 付费查看对手数值可能放大霸凌 | **部分 accept** | 可存在，但需限制不可查看低等级/新手玩家 |
| 18 | 便利性付费在立方缩放体系下会系统性滑向 pay-to-win | **accept** | 必须废弃立方缩放与 combat_exp 防御衰减 |

### Performance-risks（性能风险）

| 序号 | 质疑 | 裁决 | 理由 |
|------|------|------|------|
| 1 | LPC 在线玩家无法关闭心跳，节能机制在在线维度几乎无效 | **accept** | 1000 在线玩家常驻 heart_beat 列表，单线程遍历是主要瓶颈 |
| 2 | `do_attack` 次数估算偏低（双手互博/riposte） | **accept** | 实际峰值约 850 次/tick，而非 300+ |
| 3 | `message_vision` 在热门房间放大严重 | **accept** | 50 对象房间 + 10 场战斗可达 1500 条消息投递/tick |
| 4 | `update_condition` 递归触发伤害+广播被低估 | **accept** | 每个 daemon 内部可能触发 receive_damage/wound + 多次 message |
| 5 | engine 命令驱动 tick 是能力缺失而非性能优势 | **accept** | 必须改为时间驱动 tick 才能支撑实时战斗 |
| 6 | `entities_in_room` 全局扫描是最严重隐患 | **accept** | 50 场战斗每 tick 约 30 万次 Position 查找；必须加 room -> entities 反向索引 |
| 7 | `entities_with` set 拷贝带来 GC 压力 | **accept** | 每 tick 创建大量临时 set；应改用 keys 视图或反向索引 |
| 8 | engine 无 `set_heart_beat` 等效节能 | **accept** | 改时间驱动后需维护活跃实体集合 |
| 9 | `_spawn_loot_item` CAPABILITIES 遍历在死亡峰值累积 | **accept** | AOE/团战大量 NPC 死亡时掉落物创建开销显著 |
| 10 | Effect 引擎缺失导致性能风险不可见 | **accept** | 补建后必须建立性能基线测试 |

### Numerical-risks（数值风险）

| 序号 | 质疑 | 裁决 | 理由 |
|------|------|------|------|
| 1 | `skill_power` 立方缩放必然崩坏 | **accept** | 高等级对低等级命中率趋近确定；必须替换 |
| 2 | 伤害 6+ 层乘法叠加可秒杀 | **accept** | 应收敛层数并控制缩放 |
| 3 | `DefaultWuxiaPowerModel` 线性公式自身也有边界崩坏风险 | **accept** | 系数微调可大幅改变平衡；需加护栏与更多可调参数 |
| 4 | MAX_OPPONENT=4 攻击者与防御者不对称 | **accept** | 需加围攻惩罚 |
| 5 | NPC combat_exp 对玩家碾压 | **accept** | 应控制 PvE 数值鸿沟弹性 |
| 6 | 三种毒总伤差 14 倍，需统一 Effect 强度框架 | **accept** | 新引擎应建立 `damage_per_tick = base + duration * coefficient` 模型 |
| 7 | `juehu_damage` 对低等级角色毁灭性 | **accept** | 需统一 CC 强度分级与恢复模型 |
| 8 | 醉酒阈值附近跳变极端 | **accept** | 需平滑阈值设计 |
| 9 | 技能 -1 级死亡惩罚过苛 | **accept** | engine 扣经验更合理，但需分项可配 |
| 10 | engine 单一 10% 惩罚过轻 | **accept** | 需分项 + 当日封顶/连续递减 |
| 11 | `death_times` 阈值逻辑反向 | **accept** | 应重新设计为随次数递增保护而非门槛递增 |
| 12 | 付费红线缺乏技术护栏 | **accept** | 需 Currency 双货币、资产归属、惩罚白名单 |
| 13 | PowerModel 缺失 5 个关键维度 | **accept** | 需扩展 `CombatContext` 与 Protocol 方法 |

---

## 未决问题

以下问题超出本次调研范围，需后续 `/to-spec` 或专项票据决策：

1. **Effect 引擎模块命名与边界**：新建模块是否命名为 `effects.py`？与 `events.py`/`tick.py` 的调度关系如何？A 轨 schema 的具体字段集合？
2. **`choose_move` 返回值形态**：是否允许返回携带 `post_action`/动态文案的完整招式对象？如何与「多数招式只填 SkillData」目标平衡？
3. **多资源耗尽触发昏迷/死亡的配置语法**：是在 `World` 配置中声明关键资源池，还是题材包声明？
4. **Anubis/双手互博机制**：`s_combatd.c:247-287` 的 `anubis_attack` 是否纳入 MVP？若纳入，以何种形式？
5. **ReviveStrategy 多入口设计**：NPC 剧情触发、玩家主动触发、道具触发、任务触发的统一接口形态。
6. **围攻惩罚的具体数学模型**：防御递减公式、攻击者伤害递减公式、与 `MAX_OPPONENT` 的配置联动。
7. **数值缩放默认函数**：多项式/对数的具体参数、命中率 cap 上下限、是否作为 `DefaultWuxiaPowerModel` 的可选参数暴露。
8. **双货币与账本抽象的落地方案**：`Currency.currency_type` 枚举、`LedgerEntry` 结构、与 `DeathPolicy`/`ShopEntry` 的集成。
9. **`conditions.py` 重命名迁移成本**：是否重命名为 `predicates.py`？影响 `components.py:761-765` 等引用，需评估迁移成本 vs 文档强标。
10. **性能基线测试方案**：1000 在线/30% 参战/人均 3 condition 场景下，单 tick 耗时、GC 频率、广播扫描次数的基准与止损线。

---

## 附录：文件清单

### Phase 1 初稿

- `00-brief/brief.md`：调研总则
- `01-raw-findings/source-inventory.md`：LPC 源码考古清单
- `01-raw-findings/gameplay-slices.md`：6 个代表性玩法切片
- `01-raw-findings/mechanisms.md`：通用机制抽象
- `02-user-stories/player-stories.md`：玩家层 User Stories
- `02-user-stories/system-stories.md`：系统/NPC 层 User Stories
- `02-user-stories/operator-stories.md`：巫师/运营层 User Stories
- `03-engine-insights/abstraction-options.md`：题材无关 engine 抽象方案
- `03-engine-insights/ugc-surface.md`：题材包创作层最小表面
- `03-engine-insights/modern-design-review.md`：现代战斗玩法评审
- `03-engine-insights/player-psychology.md`：玩家心理与留存
- `03-engine-insights/commercialization.md`：商业化与增长评估
- `03-engine-insights/performance-review.md`：性能与可扩展性
- `03-engine-insights/numerical-balance.md`：数值平衡评估
- `03-engine-insights/creator-perspective.md`：创作者视角可扩展性
- `06-engine-critique/engine-comparison.md`：engine 批判对照报告

### Phase 2 红队报告

- `04-redteam-review/cross-check-report.md`：横向交叉检查
- `04-redteam-review/modern-challenges.md`：现代玩法挑战
- `04-redteam-review/player-experience-risks.md`：玩家体验风险
- `04-redteam-review/commercial-risks.md`：商业化风险
- `04-redteam-review/performance-risks.md`：性能风险
- `04-redteam-review/numerical-risks.md`：数值平衡风险

### 本报告

- `05-synthesis/final-report.md`：评审委员会最终报告（本文件）
