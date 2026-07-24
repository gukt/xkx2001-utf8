# 04 战斗与效果生命周期簇 — 红队横向交叉检查报告

> 角色：横向对比验证员（红队）。任务：交叉检查 Phase 1 各产出对「战斗 / Effect / 死亡 / 武功」实例与抽象方案的覆盖度，识别共用模式与特例，验证核心抽象是否完整串起耦合链，并对 engine-critique 的对照条目做二次核验。
> 证据来源：当前仓库 LPC 一手源码（`feature/`/`inherit/`/`adm/daemons/`/`kungfu/`/`d/death/`/`cmds/std/`/`include/`）与 `engine/src/openmud/` 已建模块。每条结论均标注具体文件路径 + 函数/类/行号。

---

## 检查方法

1. 以 `mechanisms.md` 的耦合链总览与 `abstraction-options.md` 的 6 个抽象子问题为基准。
2. 对照 6 个代表性玩法切片（`gameplay-slices.md`：普攻对砍、武功绝技、中毒持续、昏迷苏醒、死亡轮回、组队围攻）。
3. 逐条核验 `06-engine-critique/engine-comparison.md` 的对照结论是否遗漏或误判。
4. 裁决建议分三档：**确认**（与源码一致）、**推翻**（源码证据不支持）、**待澄清**（存在解释空间或需评审委员会裁定）。

---

## 1. 抽象方案对代表性实例的覆盖度

### 1.1 普攻对砍（kill / fight / hit 三档起手）

| 检查项 | 结论 | 裁决 | 证据 |
|--------|------|------|------|
| `enemy`/`killer` 双列表、fight/kill 语义差 | `mechanisms.md` §1.1 准确还原了 `feature/attack.c:15-16` 的双列表与 `fight_ob`/`kill_ob` 差异；`abstraction-options.md` §1 方向 B 建议 core 保留双语义敌对列表。 | 确认 | LPC `feature/attack.c:15-16`（`enemy`/`killer` 定义）、`:40-62`（`fight_ob`/`kill_ob`）；`cmds/std/fight.c:32-43`（切磋双向确认）；`cmds/std/kill.c:51-62`（生死搏单方成立）。 |
| `hit` 偷袭的特殊性 | `gameplay-slices.md` 切片 1 详细覆盖 `cmds/std/hit.c:88-98` 的单回合互击；但 `abstraction-options.md` 未明确 `hit` 是否应进 core 抽象，只讨论了 `try_engage`。 | 待澄清 | LPC `cmds/std/hit.c:45`（仅玩家间）、`:88-98`（`do_hit` 两次 `do_attack`）。 |
| `wimpy` 自动逃跑 | `system-stories.md` Story 1.1、`player-psychology.md` §4.4 覆盖；`abstraction-options.md` 未明确是否纳入 core。 | 待澄清 | LPC `inherit/char/char.c:124-130`（`env/wimpy` 触发 `GO_CMD->do_flee`）。 |
| `guarding` 与 riposte | `mechanisms.md` §2.2 覆盖 `combatd.c:837-842` guarding 与 `:766-779` riposte；`abstraction-options.md` 未单独抽象。 | 确认 | LPC `adm/daemons/combatd.c:766-779`、`:818-842`。 |

**红队点评**：普攻链路覆盖较完整，但 `hit`（偷袭）与 `wimpy`（自动逃跑）在抽象方案中位置不明确，存在「默认被 core 忽略」的风险。

### 1.2 武功绝技爆发（perform / exert / 招式动态生成）

| 检查项 | 结论 | 裁决 | 证据 |
|--------|------|------|------|
| `SkillData` + `SkillMove` 声明式数据 | `abstraction-options.md` §6 与 `ugc-surface.md` §1.1 确认覆盖 LPC `18-zhang.c:52-218` 的 `action` 数组静态字段。 | 确认 | LPC `kungfu/skill/18-zhang.c:52-218`；engine `engine/src/openmud/skills.py:23-53`。 |
| `perform` 大招概念 | `ugc-surface.md` §3.4、`creator-perspective.md` §2.1 明确指出 engine 无 `perform` 概念；`abstraction-options.md` §6 未将 `perform` 列为必补钩子。 | 推翻/待澄清 | LPC `kungfu/skill/18-zhang.c:304-307`（`perform_action_file`）；`cmds/skill/perform.c:65-69`（`SKILL_D(skill)->perform_action` + `apply_condition("perform", martial)`）。 |
| `query_action` 动态选招 | `abstraction-options.md` §6 方向 B 建议补 `choose_move` hook；`creator-perspective.md` §2.1 指出 engine `select_move` 固定选最高 force，无法表达 `18-zhang.c:241-291` 的条件分支。 | 确认 | LPC `kungfu/skill/18-zhang.c:241-291`（按 `sanhui`/force/neili 分档）；engine `engine/src/openmud/combat_system.py:198-224`（`select_move` 固定策略）。 |
| 多源 `hit_ob`/`hit_by` | `engine-comparison.md` §1.1c、§6.1b/d/g 确认 engine 单源塌缩；`abstraction-options.md` §6 未充分讨论需恢复 force/weapon/martial 三层钩子。 | 确认 | LPC `adm/daemons/combatd.c:473`（force `hit_ob`）、`:501`（martial `hit_ob`）、`:508`（weapon `hit_ob`）；engine `engine/src/openmud/combat.py:236-252`（唯一 `SkillBehavior.hit_ob`）。 |

**红队点评**：抽象方案对「纯数值招式」覆盖好，但对「绝技 perform」和「动态选招」两层抽象不足。`abstraction-options.md` 方向 B 的 `choose_move` hook 只能覆盖「选择招式」，难以覆盖 LPC `query_action` 返回的完整 mapping（含 `post_action` 闭包、按 force/neili 分档）。

### 1.3 中毒与持续状态（condition 时效引擎）

| 检查项 | 结论 | 裁决 | 证据 |
|--------|------|------|------|
| Effect 引擎核心抽象 | `abstraction-options.md` §3 方向 C 提出「薄调度器 + EffectHandler」；`ugc-surface.md` §2.2 将其拆为 A 轨声明式 + B 轨受限 Handler。 | 确认 | LPC `feature/condition.c:21-69`（`update_condition` 外部 daemon 调用）；`include/condition.h:5-6`（`CND_CONTINUE`/`CND_NO_HEAL_UP`）。 |
| `conditions.py` 概念错位 | 经直接阅读 `engine/src/openmud/conditions.py`（通用布尔求值器）与 `feature/condition.c`（时效 Effect 引擎），确认同名异物。 | 确认 | engine `engine/src/openmud/conditions.py:1-22`（docstring 自述用途）、`:92-142`（`Predicate`/`Equals`/`And`/`Or`/`Not`）；LPC `feature/condition.c:8`（`mapping conditions`）、`:21-69`（tick 驱动 daemon 调用）。 |
| A 轨声明式能否覆盖 72 个 condition | `creator-perspective.md` §0、§2.4 抽样显示大量 condition 含任意代码副作用（`move`、`do_remove`、扫描房间、改性别）。A 轨纯数值 schema 只能覆盖毒/伤等持续伤害型，无法覆盖位移/社交/控制型。 | 待澄清 | LPC `kungfu/condition/city_jail.c:9-14`（`me->move`）；`kungfu/condition/embedded.c:22-27`（调 `remove` 命令）；`kungfu/condition/aphroclisiac.c:35-43`（扫描房间发 emote）；`kungfu/condition/juehu_damage.c:53-58`（改性别）。 |
| `CND_NO_HEAL_UP` 预留未用 | `mechanisms.md` §3.2 正确指出全仓无 condition 返回该 flag；`engine-comparison.md` 未提及此点，非误判，但属可补充细节。 | 确认 | LPC `feature/condition.c:149`（检查 `cnd_flag & CND_NO_HEAL_UP`）；`include/condition.h:6`（`CND_NO_HEAL_UP=2`）；grep 全仓库无 condition 显式返回 2。 |

**红队点评**：Effect 抽象方案有「伪通用」风险——「薄调度器 + 声明式 A 轨」看似通用，实则只能拟合毒/伤等纯数值 DoT，对位移、社交、控制、装备联动等 72 condition 中的大量特例需要 B 轨受限代码兜底。若设计时默认 A 轨覆盖「大多数」，会低估 B 轨需求。

### 1.4 昏迷与苏醒

| 检查项 | 结论 | 裁决 | 证据 |
|--------|------|------|------|
| 两段式死亡判定 | `abstraction-options.md` §4 与 `engine-comparison.md` §4 均确认 engine `death.py:next_death_state` 正确抽象了两段式。 | 确认 | LPC `inherit/char/char.c:99-115`；engine `engine/src/openmud/death.py:21-43`。 |
| 苏醒与属性挂钩 | `abstraction-options.md` §4 建议把 `random(100-con)+30` 作为题材包可配参数；`engine-comparison.md` §4.1c 正确指出 engine 固定 tick 丢失 con 挂钩。 | 确认 | LPC `feature/damage.c:134`（`call_out("revive", random(100-con)+30)`）；engine `engine/src/openmud/death_flow.py:417-429`。 |
| `block_msg/all` 消息屏蔽 | `gameplay-slices.md` 切片 4 与 `player-stories.md` US-5 覆盖；`abstraction-options.md` 未讨论昏迷期间的消息屏蔽抽象。 | 待澄清 | LPC `feature/damage.c:131`（`set_temp("block_msg/all",1)`）、`:149`（`block_msg/all=0`）。 |

### 1.5 玩家死亡下地府走轮回

| 检查项 | 结论 | 裁决 | 证据 |
|--------|------|------|------|
| `ghost` 态与地府区 | `abstraction-options.md` §5 方向 A 主张 ghost/地府全归题材包，core 只留中间态接缝；`ugc-surface.md` §4.3 同此观点。 | 待澄清/部分推翻 | LPC `feature/damage.c:9-11`（`ghost`/`is_ghost`）、`:246-248`（`ghost=1` + `move(DEATH_ROOM)`）；`d/death/` 全目录；`inherit/char/char.c:181-186`（鬼魂可见性）。 |
| 与 brief 的 MVP 场景冲突 | `00-brief/brief.md` §2.1 明确把「死亡轮回」纳入范围，且 `gameplay-slices.md` 切片 5 是「玩家死亡下地府走轮回」。若 ghost/地府完全下沉题材包，core 无法保证该 MVP 场景一致实现。 | 待澄清 | `00-brief/brief.md` §2.1；`gameplay-slices.md` 切片 5。 |
| `start_death` 函数缺失 | `source-inventory.md` §2.7 与 `mechanisms.md` §6.2 正确指出 LPC 调用但无定义；`engine-comparison.md` §5.1a 未单独标出此点。 | 确认 | LPC `feature/damage.c:248`（`DEATH_ROOM->start_death(this)`）；grep 全仓库无 `start_death` 定义。 |
| 多复活触发点 | `gameplay-slices.md` 切片 5 覆盖白无常剧情（`d/death/npc/wgargoyle.c:51-71`）与 `inn1.c:67-83` 主动复活；抽象方案的「ReviveStrategy」未显式表达「多入口复活」。 | 待澄清 | LPC `d/death/npc/wgargoyle.c:51-71`；`d/death/inn1.c:67-83`；`d/death/npc/bgargoyle.c:73`。 |

**红队点评**：抽象方案将 ghost/地府完全下沉题材包，与 brief 把「死亡下地府走轮回」列为 MVP 必做场景存在张力。建议 core 至少保留 `Ghost` 状态标记、`is_ghost()` 可见性规则、死亡后进入可配置「死亡区入口」的通用机制，否则每个题材包都需从零复刻 ghost 语义。

### 1.6 组队围攻

| 检查项 | 结论 | 裁决 | 证据 |
|--------|------|------|------|
| `MAX_OPPONENT=4` 与围攻 | `mechanisms.md` §1.2、`gameplay-slices.md` 切片 6 准确还原；`abstraction-options.md` §1 方向 B 建议 N 对手敌对列表 + fight/kill 双语义进 core。 | 确认 | LPC `feature/attack.c:12`（`MAX_OPPONENT=4`）、`:79-88`（`select_opponent`）；engine `engine/src/openmud/combat_system.py:100-104`（`Engaged` 单对手拒绝第二对手）。 |
| 组队只是跟随关系 | `gameplay-slices.md` 切片 6 与 `mechanisms.md` §1.5 正确指出 `feature/team.c` 无合击加成；`numerical-balance.md` §4.4 建议 MVP 若做组队需补战斗加成。 | 确认 | LPC `feature/team.c:28-49`（`follow_path`/`follow_me`）、`:103-122`（`dismiss_team`）。 |
| 队长倒下即溃散 | `gameplay-slices.md` 切片 6 覆盖；`abstraction-options.md` 未明确是否保留此规则。 | 待澄清 | LPC `feature/damage.c:124`（unconcious 调 `dismiss_team`）、`:244`（die 调 `dismiss_team`）。 |

---

## 2. 「伪通用」抽象识别

### 2.1 「EffectEngine 薄调度器 + 声明式 A 轨」可能只拟合了毒/伤两类

- **被质疑文件**：`abstraction-options.md` §3 方向 C、`ugc-surface.md` §2.2。
- **证据**：
  - LPC `kungfu/condition/` 实有 72 个 daemon（`creator-perspective.md` §0）。
  - 其中纯持续伤害型（`bt_poison`/`hanbing_damage`/`chilian_poison`）仅占一部分；
  - 位移型（`city_jail.c:9-14` `me->move`）、装备联动型（`embedded.c:22-27` 调 `remove` 命令）、社交型（`aphroclisiac.c:35-43` 扫描房间发 emote）、状态改造型（`juehu_damage.c:53-58` 改性别；`blind.c:28-34` 改 `apply/attack`/`apply/defense`）大量存在。
- **风险**：若 A 轨 YAML schema 只定义 `type/duration/tick_damage/tick_message/expire_action`（`ugc-surface.md` §2.2 建议），只能覆盖毒/伤。剩余类型必须落到 B 轨受限 Python，但 B 轨又不可被 UGC 使用（`ugc-surface.md` §0 信任边界）。
- **裁决**：**待澄清**——需要评审委员会明确 A 轨目标覆盖率，否则会出现「创作者配不出武侠核心状态」的空洞。

### 2.2 「命名资源池 + damage_type 路由」可能丢失 jing/jingli 的昏迷语义

- **被质疑文件**：`abstraction-options.md` §2 方向 B。
- **证据**：
  - LPC `feature/damage.c:18-19` 硬校验 `type ∈ {jing, qi, jingli}`；
  - `inherit/char/char.c:108` 中 `qi<0 || jing<0 || jingli<0` 任一即触发 `unconcious()`；
  - `feature/damage.c:255-264` `reincarnate()` 恢复 jing/qi/jingli/eff_jing/eff_qi/neili。
- **风险**：把 jing/qi/jingli 抽象为「命名资源池」后，必须额外声明「哪些池耗尽触发昏迷/死亡」。若只保留「血量池」语义，会丢失「精力耗尽昏倒」的武侠体验。
- **裁决**：**确认**存在风险，需在抽象中显式保留「关键资源耗尽触发状态转移」的配置。

### 2.3 `SkillBehavior.choose_move` 难以完整替代 LPC `query_action`

- **被质疑文件**：`abstraction-options.md` §6 方向 B。
- **证据**：
  - LPC `kungfu/skill/18-zhang.c:241-291` 的 `query_action` 返回的 mapping 含 `action` 文案、`dodge`/`parry`/`force`/`damage`、`damage_type`、`weapon`、`post_action`（`:264` 的 `(: sanhui :)` 闭包），并随 `sanhui` temp、`force` 技能、`neili`/`jiali` 动态变化。
  - engine `SkillMove`（`engine/src/openmud/skills.py:23-33`）是静态数据元组，无 `post_action` 闭包字段。
- **风险**：`choose_move` 若只返回 `SkillMove`，无法表达「选中此招后附带 `post_action` 闭包」；若返回完整行为对象，则与「多数招式只填 SkillData」的声明式目标冲突。
- **裁决**：**待澄清**——需在 spec 阶段明确 `choose_move` 返回值是否允许携带行为钩子。

### 2.4 「ReviveStrategy 中间态」可能过度简化 LPC 地府流程

- **被质疑文件**：`abstraction-options.md` §4 方向 B、§5 方向 A。
- **证据**：
  - LPC 地府区含 `gate.c`（销毁物品 + `clear_condition` + `no_fight` + 禁 suicide）、`gateway.c`（单向禁回头）、`road2.c`（迷雾循环）、`inn1.c`（ask 谜题触发 `reincarnate`）、`hell.c`/`blkbot.c`（命令白名单隔离）、`wgargoyle.c`/`bgargoyle.c`（NPC 剧情触发复活）。
  - 这些不是单一「中间态」，而是包含房间流程、可见性过滤、物品销毁、多入口复活、犯罪隔离的区域系统。
- **风险**：抽象为「中间态 -> 复活策略」可能让题材包重复实现 ghost 可见性、命令白名单、区域 no_fight 等通用机制。
- **裁决**：**待澄清**。

---

## 3. 耦合链「命中 -> 伤害 -> 状态播报 -> 死亡判定 -> 复活」完整性检查

| 链路环节 | LPC 实现 | engine 现状 | 是否被抽象完整串起 | 裁决 |
|----------|----------|-------------|-------------------|------|
| **命中 -> 伤害** | `combatd.c:do_attack` 七步结算；4 层 `hit_ob` + 2 层 `hit_by` 可改伤害/挂 Effect（`:473-603`）。 | `combat.py:resolve_attack` 七步结构保留，但仅 1 层 `SkillBehavior.hit_ob`（`:236-252`）；weapon/armor/force/martial 多层注入缺失。 | 否。`hit_ob` 多源链断裂。 | 确认 |
| **伤害 -> 状态播报** | `damage_msg`/`report_status`/`announce` 多层播报（`combatd.c:68-255`、`damage.c:132/187`）。 | `CombatRoundResult.message_fragments`（`combat.py:60-69`）结构化但无 `damage_type` 分级文案、无 per-skill 闪架文案。 | 否。播报维度塌缩。 | 确认 |
| **伤害 -> 死亡判定** | `receive_damage`/`receive_wound` 扣值后 `heart_beat` 检查 `eff_qi/eff_jing<0`、`qi/jing/jingli<0`（`char.c:100-115`）。 | `combat_system.py:apply_combat_result` 直接判 `qi_current<=0`（`combat_system.py:235-245`）；无 eff/jing/jingli 多触发源。 | 否。多资源触发缺失。 | 确认 |
| **状态播报 -> 死亡判定** | `report_status` 后下一 tick `heart_beat` 判定；昏迷后再受致命伤才死（两段式）。 | `next_death_state` 纯函数正确抽象两段式（`death.py:21-43`），但触发源单一。 | 部分。判定逻辑抽象正确，触发源不足。 | 待澄清 |
| **Effect -> 伤害/死亡** | condition daemon 内部调 `receive_damage`/`receive_wound`（`bt_poison.c:33-34`），点亮 heart_beat 后触发死亡判定。 | engine 无 Effect 引擎，`conditions.py` 无法驱动伤害。 | 否。链路在 engine 完全断裂。 | 确认 |
| **死亡 -> 清 Effect** | `die()` 调 `clear_condition()`（`damage.c:184`）；`gate.c:init` 再清一次（`gate.c:38`）。 | 无 Effect 可清。 | 否。即使未来建 Effect 引擎，death_flow 也需补 `clear_effect`。 | 确认 |
| **死亡 -> 复活** | `ghost=1` + `move(DEATH_ROOM)` + 地府流程 + `reincarnate()` 回满（`damage.c:246-264`）。 | 直接传送到 `revive_room` + 回满血（`death_flow.py:256-264`）；无 ghost/地府中间态。 | 否。中间态断裂。 | 确认 |
| **复活 -> 世界状态** | `reincarnate()` 恢复 jing/qi/eff_jing/eff_qi/jingli/neili 到 max（`damage.c:255-264`）；不恢复 exp/skill/shen/potential/balance。 | `death_flow.py:260-264` 恢复 qi/neili/jingli，不恢复 exp/skill。 | 部分。缺少 eff 层与 ghost 态清理。 | 待澄清 |

**红队结论**：耦合链在 LPC 中由 `heart_beat` 单线程完整串起；抽象方案在概念层面覆盖了各环节，但 engine 当前实现存在 4 处硬断点：Effect 引擎缺失、`hit_ob` 多源塌缩、多资源死亡触发缺失、ghost/地府中间态缺失。其中 Effect 引擎缺失是级联断点——它同时导致「命中 -> 挂状态 -> 持续伤害 -> 死亡 -> 清状态」全链路无法跑通。

---

## 4. `engine-comparison.md` 对照条目二次核验

| engine-comparison 结论 | 红队核验 | 裁决 | 补充证据 |
|------------------------|----------|------|----------|
| **conditions.py 概念错位是核心发现** | 经直接阅读 `engine/src/openmud/conditions.py`（纯布尔求值器）与 `feature/condition.c`（时效 Effect 引擎），确认同名异物。 | 确认 | engine `conditions.py:1-22` docstring 自述用途；LPC `feature/condition.c:21-69` `update_condition` 驱动 daemon。 |
| **ghost 态 + 地府轮回缺失是 MVP 场景断层** | 确认 engine 无 ghost（`death.py:13-18` 仅 ALIVE/UNCONSCIOUS/DEAD）。但 `abstraction-options.md` §5 主张地府归题材包，与 brief MVP 场景存在张力。 | 确认 + 待澄清 | brief §2.1 纳入「死亡轮回」；LPC `d/death/` 13 房间。 |
| **多对手围攻缺失** | 确认 `Engaged` 单对手（`components.py:692-698`），`try_engage` 拒绝第二对手。 | 确认 | engine `engine/src/openmud/combat_system.py:100-104`。 |
| **三类伤害塌缩为一类** | 确认 engine 只扣 `qi_current`（`combat_system.py:240`），无 jing/jingli/eff 层。 | 确认 | LPC `feature/damage.c:13-66`；engine `engine/src/openmud/components.py:460-468` `Vitals`。 |
| **hit_ob 多源塌缩为单源 + 不挂 Effect** | 确认 engine 仅 `SkillBehavior.hit_ob`（`combat.py:236`），无 force/weapon/martial/armor/dodge 链；`DemoPoisonStrikeBehavior` 只加 5 伤害不挂毒。 | 确认 | LPC `inherit/skill/skill.c:142-157`（基类默认挂 `snake_poison`）；engine `engine/src/openmud/skills.py:87-102`。 |
| **门派武功归属缺失** | 确认 `SkillData` 无 faction 字段；但 `components.py:681` 已存在 `Faction` 组件，只是未与技能关联。 | 确认 + 补充 | LPC `kungfu/class/` 19 门派；engine `engine/src/openmud/components.py:681` `Faction`、skills.py:36-53 `SkillData`。 |
| **NPC 主动 aggro 缺失** | 确认 `combat_system.py:6` 注释说明暂缓。 | 确认 | LPC `feature/attack.c:229-258` + `adm/daemons/combatd.c:852-962`。 |
| **战斗中回血（heal_up）缺失** | 确认 engine 无 `heal_up` tick。 | 确认 | LPC `feature/damage.c:270-331`。 |
| **wimpy 自动逃跑缺失** | 确认 engine 无 wimpy。 | 确认 | LPC `inherit/char/char.c:124-130`。 |
| **技能在用中成长缺失** | 确认 engine 只在击杀给 exp（`death_flow.py:398-408`）。 | 确认 | LPC `adm/daemons/combatd.c:450`（闪避成长）、`:615`（招架成长）、`:698-702`（命中成长）。 |
| **combat_exp 削伤/成长缺失** | 确认 engine 无 `combat_exp` 轴。 | 确认 | LPC `adm/daemons/combatd.c:636-641`（防御衰减）、`:386/432/600-609`（成长）。 |
| **上限伤致死路径缺失** | 确认 engine 无 `eff_qi`/`eff_jing` 概念。 | 确认 | LPC `inherit/char/char.c:100-104`。 |
| **死亡清状态缺失** | 确认因无 Effect 引擎。 | 确认 | LPC `feature/damage.c:184`；`d/death/gate.c:38`。 |
| **尸体对象缺失** | 确认 engine 裸掉物品。 | 确认 | LPC `feature/damage.c:227-228` `CHAR_D->make_corpse`。 |
| **死亡日志/PKILL 缺失** | 确认 engine 无日志。 | 确认 | LPC `feature/damage.c:209-224`。 |
| **unconcious 苏醒与根骨挂钩缺失** | 确认 engine 固定 tick。 | 确认 | LPC `feature/damage.c:134`；engine `death_flow.py:417-429`。 |
| **is_busy/continue_action/yield 缺失** | 确认 engine 无 busy/让招概念。 | 确认 | LPC `inherit/char/char.c:118-121`（busy）、`feature/attack.c:217`（yield）。 |
| **`s_combatd.c` / Anubis 双手互博差异讨论不足** | `source-inventory.md` §1.3 与 `mechanisms.md` §2.1 明确两套 combatd 并存；`engine-comparison.md` 仅在模块 1 开头与 §1.1 表格中提及，未作为独立遗漏项评估 engine 是否需支持 Anubis 分支。 | 补充 | LPC `adm/daemons/s_combatd.c:247-287`（`anubis_attack`）；`feature/attack.c:197-206`（`stand/anubis` temp 调用 `S_COMBAT_D`）。 |
| **`start_death` 函数缺失** | 确认 `engine-comparison.md` 未单独标出，但 `source-inventory.md` §2.7 与 `mechanisms.md` §6.2 已指出。 | 确认 | LPC `feature/damage.c:248`；grep 全仓库无定义。 |

**红队结论**：`engine-comparison.md` 的对照条目整体准确，无重大误判。需补充的主要是：
1. `conditions.py` 概念错位之外，应强调 A 轨声明式 Effect 无法覆盖 72 condition 中的大量副作用型；
2. ghost/地府缺失不仅是 engine 现状描述，还与 brief 的 MVP 场景存在架构边界张力；
3. `s_combatd.c` 的 Anubis 双手互博原型应作为 engine 潜在遗漏单独评估。

---

## 5. 综合裁决与遗留问题

### 5.1 关键裁决

| 序号 | 问题 | 裁决 |
|------|------|------|
| 1 | `abstraction-options.md` 是否覆盖了全部 6 个代表性玩法切片？ | **基本覆盖，但武功绝技的 `perform` 大招层、死亡轮回的 ghost/地府层覆盖不足。** |
| 2 | 是否存在「伪通用」抽象？ | **是。** EffectEngine 薄调度器 + A 轨声明式只能拟合毒/伤两类；命名资源池需额外声明「关键池耗尽触发昏迷」；`choose_move` 难以完整替代 `query_action`；ReviveStrategy 可能过度简化地府流程。 |
| 3 | 命中->伤害->状态播报->死亡判定->复活链是否完整？ | **概念层完整，但 engine 实现层存在 4 处硬断点：Effect 引擎缺失、`hit_ob` 多源塌缩、多资源死亡触发缺失、ghost/地府中间态缺失。** |
| 4 | `engine-comparison.md` 的对照条目是否遗漏或误判？ | **无重大误判。** 核心发现（conditions.py 概念错位、ghost/地府缺失、围攻缺失、三类伤害塌缩、门派归属缺失）均经核对确认；需补充 A 轨 Effect 覆盖范围、地府与 MVP 场景的张力、`s_combatd.c` Anubis 分支评估。 |

### 5.2 建议移交评审委员会裁决的未决问题

1. **ghost/地府到底进不进 core？** `abstraction-options.md` §5 与 brief §2.1 的 MVP 场景存在冲突，需委员会拍板：是保留为题材包内容，还是 core 至少提供 `Ghost` 状态与可见性规则？
2. **A 轨 Effect 声明式目标覆盖率是多少？** 若要求 UGC 创作者能在 YAML 里配出武侠核心状态（毒/点穴/内伤/醉酒/致盲），A 轨 schema 需扩展哪些字段？B 轨受限 Python 的边界在哪里？
3. **`choose_move` hook 的返回值形态**：是只返回 `SkillMove` 静态数据，还是允许返回携带 `post_action`/动态文案的完整招式对象？
4. **多资源耗尽触发昏迷/死亡的通用配置**：是否把「jing/qi/jingli 任一耗尽触发昏迷」作为 core 默认规则，还是完全下沉题材包？
5. **Anubis/双手互博机制是否纳入 MVP？** 若 brief 未明确排除，`s_combatd.c:247-287` 的 `anubis_attack` 应作为潜在 engine 扩展点记录。

---

## 6. 证据索引速查

### LPC 一手源码
- 战斗循环：`inherit/char/char.c:60-169`（`heart_beat`）、`feature/attack.c:12,79-88,208`（`MAX_OPPONENT`/`select_opponent`/`attack`）。
- 命中伤害：`adm/daemons/combatd.c:340-780`（`do_attack`）、`:288-333`（`skill_power`）、`:636-641`（combat_exp 防御衰减）。
- Effect 引擎：`feature/condition.c:8,21-69,79-85`；`include/condition.h:5-6`；`kungfu/condition/bt_poison.c:7-42`。
- 昏迷/死亡：`feature/damage.c:105-264`（`unconcious`/`die`/`reincarnate`）；`inherit/char/char.c:99-115`（两段式判定）。
- 地府：`d/death/gate.c:26-48`；`d/death/inn1.c:67-83`；`d/death/npc/wgargoyle.c:51-71`；`include/login.h:23`。
- 武功：`kungfu/skill/18-zhang.c:52-218,241-291,304-307`；`inherit/skill/skill.c:142-157`。
- 组队：`feature/team.c:28-49,103-122`。

### engine 模块
- `engine/src/openmud/conditions.py`（布尔求值器，非 Effect 引擎）。
- `engine/src/openmud/combat.py:72-113`（`PowerModel`/`DefaultWuxiaPowerModel`）、`:132-216`（`resolve_attack`）、`:236-252`（单源 `hit_ob`）。
- `engine/src/openmud/combat_system.py:100-104`（`Engaged` 单对手）、`:198-224`（`select_move`）、`:235-245`（`apply_combat_result` 只判 `qi_current`）。
- `engine/src/openmud/death.py:13-43`（`DeathState` 无 GHOST / `next_death_state`）。
- `engine/src/openmud/death_flow.py:77-86`（`DeathPolicy`）、`:256-264`（直接复活）、`:417-429`（固定 tick 苏醒）。
- `engine/src/openmud/skills.py:23-53`（`SkillMove`/`SkillData`）、`:59-67`（`SkillBehavior`）、`:87-102`（`DemoPoisonStrikeBehavior` 不挂毒）。
- `engine/src/openmud/components.py:460-468`（`Vitals` 无 eff 层）、`:681`（`Faction` 未连技能）、`:692-698`（`Engaged` 单对手）。
