export const meta = {
  name: 'combat-effect-lifecycle-research',
  description: '多 Agent 并行调研「战斗与效果生命周期簇」= 战斗 + 状态/Effect + 死亡与轮回（LPC 考古 + 批判性对照现有 engine）',
  phases: [
    { title: 'Phase 1: 并行初稿' },
    { title: 'Phase 2: 红队对抗' },
    { title: 'Phase 3: 评审委员会汇总' },
  ],
};

const RESEARCH_DIR = '/home/gukt/github/xkx2001-utf8/.scratch/research/04-combat-effect-lifecycle';
const BRIEF_PATH = `${RESEARCH_DIR}/00-brief/brief.md`;
const REPO_ROOT = '/home/gukt/github/xkx2001-utf8';

const LPC_SOURCE_MAP = `LPC 一手源码关键指针（唯一真相源）：
- 战斗核心（命中->伤害）：feature/attack.c（258 行：enemy/killer 列表、fight_ob/is_fighting/is_killing、attack()、MAX_OPPONENT=4，调 S_COMBATD）、feature/damage.c（331 行：receive_damage(type,damage,who)/receive_wound(type,damage,who) 三类伤害 jing 精/qi 气/jingli 精力、set_temp("last_damage_from",who) 伤害来源、set_heart_beat(1)、ghost 标志、die()(:152)、reincarnate()(:255)、is_ghost()）、feature/skill.c（183 行：技能查询）、feature/team.c（127 行：组队）、feature/equip.c（140 行：装备）、inherit/char/char.c（heart_beat() 战斗循环：:101-113 remove_all_enemy/die/unconcious/attack，:107-113 昏迷 vs 死亡判定 living()）、inherit/char/trainee.c（NPC 战斗 AI：revive/biting/do_yao attack）、adm/daemons/combatd.c + s_combatd.c（战斗 daemon，命中/伤害结算核心）
- 状态/Effect 库（状态播报）：feature/condition.c（113 行：conditions mapping、update_condition() 由 heart_beat 驱动、CONDITION_D 外部 daemon 调用，每个 condition 是独立 daemon）、kungfu/condition/（~30+ condition 即 Effect 内容层：aphroclisiac 春药 / *_poison 各类毒 bt_poison/chilian_poison/hsf_poison/huadu_poison/insect_poison / *_damage 伤害 hanbing_damage/jiujian_qi_damage/juehu_damage/hyz_damage / drunk 醉 / blind 盲 / embedded 嵌入暗器 / *_jail 牢 city_jail/dali_jail/bonze_jail / bandaged 包扎）
- 死亡与轮回（死亡判定->复活）：feature/damage.c:die()/reincarnate()/ghost（死亡判定+鬼魂态+轮回复活）、d/death/（地府区 ~580 行：gate/gateway/hell/inn1/inn2/road1-3/noteroom/blkbot/block/death -- 玩家死后变鬼进入地府走轮回）、inherit/char/char.c heart_beat 中 die/unconcious 判定
- 武功/技能（命中来源与 effect 载体）：inherit/skill/（skill.c/skill2.c/force.c/temp.c 技能基类）、kungfu/skill/（大量武功：18-zhang 降龙十八掌 / 6mai-shenjian 六脉神剑 / beiming-shengong 北冥神功 / archery 射箭 / blade/sword/axe 各兵器招式）、kungfu/class/（门派武功集：baituo/dali/emei/gaibang/gumu/huashan/lingjiu/mingjiao/murong...）
- 装备（战斗数值）：inherit/weapon/（15 类 _sword/_blade/_axe/_bow/_club/_dagger/_fork/_halberd/_hammer/_hook/_pike/_staff/_stick/_whip + throwing）、inherit/armor/（armor/boots/cloth/finger/hands/head/neck/shield/surcoat/waist/wrists）
- 命令：cmds/std/（kill.c/fight.c/hit.c/forcekill.c/wield.c/unwield.c/wear.c/remove.c/eat.c）`;

const ENGINE_MODULES = `新引擎已建模块（批判对照对象，仅 engine-comparison 角色细读，其余角色需要时参考）：
- engine/src/openmud/combat.py(291 行) - CombatMoveSnapshot/CombatContext/CombatRoundResult/PowerModel 协议/DefaultWuxiaPowerModel/resolve_attack/_roll_opposed/hit_ob·hit_by·riposte·exp_gain·post_action 钩子
- engine/src/openmud/combat_system.py(324 行) - ON_BEFORE_COMBAT_ROUND/ON_COMBAT_ROUND/ON_COMBAT_END 事件/CombatSystem/try_engage/clear_engagement/resolve_one_strike/select_move/apply_combat_result/_on_combat_tick/_broadcast_round
- engine/src/openmud/conditions.py(257 行) - ConditionContext 协议/Predicate/Equals/Gte/And/Or/Not/evaluate（注意：这是通用布尔求值引擎，概念错位于 LPC condition.c 的时效性 Effect 引擎）
- engine/src/openmud/death.py(46 行) - DeathState 枚举(ALIVE/UNCONSCIOUS/DEAD)/next_death_state 两段式纯函数
- engine/src/openmud/death_flow.py(446 行) - ON_BEFORE_DEATH/ON_DEATH/ON_REVIVE/DeathPolicy/LootTable/掉落/货币&技能经验惩罚/复活房间/昏迷苏醒 tick
- engine/src/openmud/skills.py(317 行) - SkillMove/SkillData/SkillBehavior 协议/register_skill_behavior/DemoPoisonStrikeBehavior(毒击)/SilkRopeCaptureBehavior(擒拿)/load_skills_from_mapping
- 关联参考（不深调）：events.py(144 战斗事件)/tick.py(101 战斗 tick)/components.py(Combat/Unconscious/Dead/NoDeathZone 组件)/intent.py`;

const COMMON_TAIL = (outputPath) => `
证据要求：每条结论必须标注来源（LPC 文件路径 + 函数/对象名，或 engine 模块路径 + 行号/类名）。禁止凭空推断。
输出：使用 Write 工具写入文件 ${outputPath}（绝对路径）。
最终回复：只需确认文件已写入，并给出 3-5 句话摘要。不要在回复中重复文件全文。`;

// ============ Phase 1: 并行初稿（12 席）============
phase('Phase 1: 并行初稿');

const p1Agents = [
  {
    label: 'LPC源码考古员',
    prompt: `你是「战斗与效果生命周期簇」调研团队的 LPC 源码考古员。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

${ENGINE_MODULES}

任务：对战斗 / 状态Effect / 死亡与轮回 / 武功 四个子系统相关的 LPC 源码做完整盘点。
必须覆盖：
1. 总体分布（feature/attack.c/damage.c/condition.c/skill.c/team.c/equip.c 结构、inherit/char/char.c 与 trainee.c 的 heart_beat 战斗循环、combatd/s_combatd daemon、kungfu/condition/ 与 kungfu/skill/ 与 kungfu/class/ 内容层规模、d/death/ 地府区流程、inherit/weapon/ 与 inherit/armor/ 装备、cmds/std/ 战斗命令）。
2. 关键文件清单表（文件路径 + 行数 + 职责 + 关键函数/对象）。
3. 调用链与数据结构：attack.c 的 enemy/killer 列表与 attack() 调用链、damage.c 的 receive_damage/receive_wound 三类伤害与 die()/reincarnate()/ghost、condition.c 的 update_condition 与 CONDITION_D 调用、char.c heart_beat 的 attack/die/unconcious 调度、combatd 的命中/伤害结算、d/death/ 地府轮回流程、inherit/skill 与 kungfu/skill 的武功招式调度。
4. 关键回调与状态变量（enemy/killer/ghost/conditions/last_damage_from/heart_beat/DeathState 等）。
5. 待深入文件清单（值得后续细读的代表性文件）。
${COMMON_TAIL(`${RESEARCH_DIR}/01-raw-findings/source-inventory.md`)}`,
  },
  {
    label: '玩法切片策划',
    prompt: `你是「战斗与效果生命周期簇」调研团队的玩法切片策划。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

任务：从 LPC 源码中挑选 4-6 类代表性「战斗与效果生命周期」玩法，做成「玩家视角 + 数据流」切片。建议覆盖：
- 普攻对砍（kill/fight/hit 命令 -> attack.c attack() -> combatd 命中结算 -> damage.c receive_damage 三类伤害）
- 武功绝技爆发（perform/exert 武功招式 -> kungfu/skill 调度 -> 招式附带 Effect）
- 中毒/持续状态（kungfu/condition/*_poison -> condition.c update_condition heart_beat 周期结算 -> 状态播报）
- 昏迷与苏醒（char.c heart_beat unconcious 判定 -> 苏醒条件）
- 玩家死亡下地府走轮回（damage.c die()/ghost -> d/death/ 地府区 -> reincarnate 复活）
- 组队围攻（team.c + attack.c MAX_OPPONENT=4 多敌对）
每个切片：玩家操作步骤 + 背后数据流（涉及哪些文件/函数/状态）+ 体验要点。

同时产出玩家视角 User Stories（玩家在战斗/Effect/死亡中会做什么、遭遇什么）。
${COMMON_TAIL(`${RESEARCH_DIR}/01-raw-findings/gameplay-slices.md`)}
再额外用 Write 写入玩家故事：${RESEARCH_DIR}/02-user-stories/player-stories.md（同一 agent 写两个文件）。`,
  },
  {
    label: '战斗/效果机制设计师',
    prompt: `你是「战斗与效果生命周期簇」调研团队的战斗/效果机制设计师。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

任务：从 LPC 实现中抽象「战斗与效果生命周期簇」通用机制（不绑定具体武功/毒名内容）。至少覆盖：
- 交战与敌对：attack.c 的 enemy/killer 列表、fight_ob/is_fighting/is_killing、MAX_OPPONENT=4、team.c 组队。
- 命中与伤害结算：combatd/s_combatd 的命中判定、damage.c receive_damage/receive_wound 三类伤害（jing/qi/jingli）、last_damage_from 伤害来源、set_heart_beat 触发。
- Effect 时效引擎：condition.c 的 conditions mapping + update_condition() heart_beat 驱动 + CONDITION_D 外部 daemon 调用模型（每个 Effect 是独立 daemon）。
- 状态播报：Effect 触发/结算时的消息分发。
- 死亡两段式判定：char.c heart_beat 的 unconcious vs die 判定（living()）、damage.c die()/ghost/。
- 鬼魂与轮回：ghost 标志、d/death/ 地府区流程、reincarnate() 复活。
- 武功招式调度：inherit/skill + kungfu/skill 的招式作为命中与 effect 载体、kungfu/class 门派归属。
- 装备数值：inherit/weapon/inherit/armor 对战斗数值的影响。
对每个机制给出：LPC 出处 + 状态/数据结构 + 触发条件 + 与周边系统交互（尤其命中->伤害->状态播报->死亡判定->复活的耦合链）。

同时产出系统/NPC 自动触发视角 User Stories（heart_beat 战斗循环、Effect 周期结算、昏迷苏醒、地府轮回触发等自动行为）。
${COMMON_TAIL(`${RESEARCH_DIR}/01-raw-findings/mechanisms.md`)}
再额外用 Write 写入系统故事：${RESEARCH_DIR}/02-user-stories/system-stories.md。`,
  },
  {
    label: '引擎架构师A',
    prompt: `你是「战斗与效果生命周期簇」调研团队的引擎架构师 A。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

${ENGINE_MODULES}

任务：把「战斗与效果生命周期簇」通用机制映射到题材无关 engine 核心，输出抽象方案与可选方向（不输出最终接口契约，止步于设计输入）。覆盖：
- 交战/敌对关系作为 engine 核心原语的最小集（哪些必须进 core，哪些可下沉题材包）。
- 命中/伤害结算的抽象：PowerModel 协议（engine 已有 DefaultWuxiaPowerModel）的可扩展方向；三类伤害（jing/qi/jingli）如何题材无关化。
- Effect 时效引擎抽象：condition.c 的 update_condition + CONDITION_D daemon 模型如何映射（注意 engine conditions.py 是布尔求值引擎，概念错位，需提出 Effect 时效引擎的正确抽象位置）。
- 死亡两段式判定：death.py 的 next_death_state 纯函数 + death_flow.py 的掉落/惩罚/复活如何分层（纯判定 vs 副作用）。
- 鬼魂/地府轮回：是否进 engine core，还是题材包内容。
- 武功招式调度：skills.py 的 SkillBehavior 协议作为招式/effect 载体的抽象方向。
- 至少给出 2-3 个可选方向并比较权衡（不要只给一个"正确答案"）。
${COMMON_TAIL(`${RESEARCH_DIR}/03-engine-insights/abstraction-options.md`)}`,
  },
  {
    label: '引擎架构师B',
    prompt: `你是「战斗与效果生命周期簇」调研团队的引擎架构师 B。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

${ENGINE_MODULES}

任务：思考题材包（UGC）创作层应暴露的最小表面（创作者如何定义武功/招式/Effect/死亡惩罚/复活点）。覆盖：
- 创作者需要声明什么：武功招式（kungfu/skill）、Effect（kungfu/condition）、伤害类型与数值、死亡惩罚策略（death_flow DeathPolicy）、复活点（_resolve_revive_room）、装备数值。
- Effect 创作面：condition.c 的 CONDITION_D daemon 模型如何暴露给题材包创作者（声明式 Effect 定义 vs 受限脚本）。
- 武功创作面：SkillBehavior 协议如何让创作者挂招式行为（DemoPoisonStrikeBehavior/SilkRopeCaptureBehavior 是范例）。
- 死亡与轮回创作面：DeathPolicy/LootTable/惩罚比例/地府流程可否题材包自定义。
- 哪些应锁在 engine core 不让创作者碰（命中/伤害结算核心、Effect 调度循环、死亡状态机纯函数）。
- 创作者门槛与护栏（防止数值崩坏/无限 Effect 堆叠/死亡惩罚误配）。
${COMMON_TAIL(`${RESEARCH_DIR}/03-engine-insights/ugc-surface.md`)}`,
  },
  {
    label: 'UGC游戏专家',
    prompt: `你是「战斗与效果生命周期簇」调研团队的 UGC 游戏专家。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

${ENGINE_MODULES}

任务：从创作者视角审视「战斗与效果生命周期簇」可扩展性。覆盖：
- 创作者配武功/挂 Effect/调数值/设死亡惩罚 的工作流与痛点（LPC 当下是 kungfu/skill + kungfu/condition 各写 .c daemon，门槛高、易错）。
- 哪些机制适合暴露给题材包创作者，哪些应封装。
- 30+ Effect / 大量武功招式 的规模对创作工具的要求（Effect 编辑器/数值预览/平衡校验）。
- 创作者经济视角：武功/装备/Effect 作为题材包核心资产的可交易性（参考 CLAUDE.md 商业化支撑点）。
- 现有 engine 的 skills.py（SkillBehavior 协议）与 death_flow.py（DeathPolicy/LootTable）对创作者友好度的影响（仅评估，不深读实现）。

同时产出巫师/运营视角 User Stories（创作者如何配置与维护战斗/Effect/死亡内容）。
${COMMON_TAIL(`${RESEARCH_DIR}/03-engine-insights/creator-perspective.md`)}
再额外用 Write 写入运营故事：${RESEARCH_DIR}/02-user-stories/operator-stories.md。`,
  },
  {
    label: '现代战斗玩法设计师',
    prompt: `你是「战斗与效果生命周期簇」调研团队的现代战斗玩法设计师。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

任务：对标当前主流游戏（现代 MMO 战斗、动作战斗、手游回合/即时战斗、MOBA），评估 LPC 战斗机制的当代可玩性与过时风险。覆盖：
- 战斗节奏：LPC heart_beat tick 驱动 + MAX_OPPONENT=4 vs 现代战斗节奏/连击/手感。
- 命中与伤害：LPC combatd 命中结算 + 三类伤害 vs 现代伤害模型/暴击/格挡/闪避。
- Effect/状态：LPC condition 时效 Effect vs 现代状态/Buff/Debuff 系统；中毒/被控的体验。
- 死亡惩罚：LPC 死亡下地府走轮回 + 鬼魂态 vs 现代死亡惩罚设计（轻惩罚/复活点/保险）。
- 武功招式：LPC kungfu/skill 招式系统 vs 现代技能树/连招/技能槽。
- 哪些 LPC 机制值得保留（文本战斗的想象空间、武侠题材的招式感），哪些过时应现代化。
${COMMON_TAIL(`${RESEARCH_DIR}/03-engine-insights/modern-design-review.md`)}`,
  },
  {
    label: '玩家心理与留存专家',
    prompt: `你是「战斗与效果生命周期簇」调研团队的玩家心理与留存专家。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

任务：从动机心理学、留存曲线、心流节奏、社交压力等角度点评「战斗与效果生命周期簇」玩家体验。覆盖：
- 战斗挫败：命中率/伤害随机性/被秒杀的挫败与流失风险。
- 死亡惩罚焦虑：下地府走轮回/鬼魂态/掉落/经验惩罚 的累积压力。
- 中毒/被控无力感：持续掉血/被封印/被擒拿 的失控体验。
- 心流节奏：heart_beat tick 战斗节奏对沉浸与紧张感的作用。
- PvP 社交压力：组队围攻/门派敌对/抢怪 的社交触点与霸凌风险。
- 必须保护玩家的体验底线（建议机制，如免死区/保护期/反 PK 机制）。
${COMMON_TAIL(`${RESEARCH_DIR}/03-engine-insights/player-psychology.md`)}`,
  },
  {
    label: '商业化与增长专家',
    prompt: `你是「战斗与效果生命周期簇」调研团队的商业化与增长专家。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

任务：从付费设计、UGC 创作者经济、题材包消费、用户增长角度评估「战斗与效果生命周期簇」商业潜力。参考 CLAUDE.md 商业化支撑点（货币/账本、题材包资产元数据、消费埋点、世界实例隔离）与不 pay-to-win 红线。覆盖：
- 战斗付费点：武功/装备/复活/保护期付费潜力（必须标注 pay-to-win 红线，区分便利性付费与数值付费）。
- 武功/装备/Effect 作为题材包资产：归属与版本溯源、创作者分成。
- 死亡惩罚与商业化：掉落/惩罚是否可做付费减免（注意不越线）。
- 战斗数值埋点：可打点到题材包 ID 的支撑点。
- 哪些商业支撑点应在 engine 留位置（MVP 不实现但预留）。
${COMMON_TAIL(`${RESEARCH_DIR}/03-engine-insights/commercialization.md`)}`,
  },
  {
    label: '性能与可扩展性专家',
    prompt: `你是「战斗与效果生命周期簇」调研团队的性能与可扩展性专家。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

${ENGINE_MODULES}

任务：评估「战斗与效果生命周期簇」的性能与可扩展性维度。覆盖（单机 1000 在线 + 100 并发约束，见 CLAUDE.md）：
- 战斗 tick 并发：heart_beat 驱动所有 living 的 attack + condition update_condition，1000 在线时 tick 密度与开销；engine _on_combat_tick / _on_unconscious_tick 的开销。
- Effect 遍历：每个玩家挂多个 condition 时 update_condition 遍历 conditions mapping 的开销；30+ Effect daemon 调用密度。
- 全员战斗广播：combatd/_broadcast_round 战斗消息分发；多场战斗同时进行。
- 死亡流程开销：death_flow 掉落/惩罚/复活房间解析 在死亡峰值时的开销。
- set_heart_beat 机制：damage 触发 set_heart_beat(1) 的启停开销。
- 现有 engine（combat.py/combat_system.py/conditions.py/death_flow.py/skills.py）的性能隐患（仅评估方向，不深读）。
${COMMON_TAIL(`${RESEARCH_DIR}/03-engine-insights/performance-review.md`)}`,
  },
  {
    label: '数值平衡专家',
    prompt: `你是「战斗与效果生命周期簇」调研团队的数值平衡专家。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

${ENGINE_MODULES}

任务：从数值平衡角度评估「战斗与效果生命周期簇」。覆盖：
- 伤害公式：receive_damage/receive_wound 三类伤害（jing/qi/jingli）的数值模型；combatd 命中/伤害结算的数值链。
- 命中率/闪避/暴击：LPC 命中判定（attack/defense 对抗，engine _roll_opposed）的数值平衡。
- 数值缩放：武功等级/内功/装备 对伤害的缩放曲线；是否存在指数爆炸或边际递减。
- PvE vs PvP 平衡：MAX_OPPONENT=4 多敌对、组队围攻 的数值压力；玩家 vs NPC 的数值鸿沟。
- Effect 数值：中毒持续掉血/被封印/被擒拿 的强度与持续时间平衡。
- 死亡惩罚数值：掉落比例/货币&技能经验惩罚比例 的平衡（是否过苛或过轻）。
- 付费数值红线：哪些数值绝不能付费影响（pay-to-win 红线），哪些可做付费便利。
- engine PowerModel 协议（DefaultWuxiaPowerModel）的数值抽象是否支持题材包调参。
${COMMON_TAIL(`${RESEARCH_DIR}/03-engine-insights/numerical-balance.md`)}`,
  },
  {
    label: 'engine批判对照员',
    prompt: `你是「战斗与效果生命周期簇」调研团队的 engine 批判对照员（06-engine-critique 层）。先阅读调研总则：${BRIEF_PATH}

仓库根：${REPO_ROOT}。${LPC_SOURCE_MAP}

${ENGINE_MODULES}

任务：逐项对照「现有 engine 实现」与「LPC 原始设计」，标注偏差与遗漏。engine 模块仅作批判对照对象，不作反向脑补来源；LPC 才是真相源。
对以下每个 engine 模块，产出对照条目（LPC 设计 -> engine 现状 -> 偏差/遗漏 -> 风险/影响）：
1. combat.py vs feature/attack.c + damage.c + combatd.c：命中/伤害结算、PowerModel、三类伤害、hit_ob/hit_by/riposte/exp_gain 钩子对齐度？LPC enemy/killer 列表与 MAX_OPPONENT 有无？
2. combat_system.py vs LPC 战斗循环：交战(try_engage)/回合/事件(ON_BEFORE_COMBAT_ROUND 等)/tick 驱动(_on_combat_tick) 与 LPC heart_beat+attack 对齐度？
3. conditions.py vs feature/condition.c：**重点**--engine conditions.py 是通用布尔求值引擎（Equals/Gte/And/Or/evaluate），LPC condition.c 是时效性 Effect 引擎（update_condition heart_beat + CONDITION_D daemon）。这是概念错位，必须明确标注：LPC 的时效 Effect 引擎在 engine 缺失，还是被拆到别处（如 skills.py SkillBehavior / death_flow）？
4. death.py vs feature/damage.c die()/ghost：DeathState 两段式纯函数(ALIVE/UNCONSCIOUS/DEAD) 与 LPC die/unconcious/ghost 对齐度？LPC 鬼魂态/地府有无？
5. death_flow.py vs d/death/ + die/reincarnate：掉落/货币&技能经验惩罚/复活房间/昏迷苏醒 与 LPC 地府轮回/reincarnate 对齐度？LPC 地府流程有无？
6. skills.py vs inherit/skill + kungfu/skill：SkillBehavior 协议/register_skill_behavior/DemoPoisonStrikeBehavior/SilkRopeCaptureBehavior 与 LPC 武功招式调度对齐度？LPC kungfu/class 门派归属有无？
额外：标注 engine 相对 LPC 的「正面偏差」（engine 做得更好的地方）与「负面遗漏」（engine 缺失的能力，如时效 Effect 引擎/地府轮回/鬼魂态/门派武功归属）。
${COMMON_TAIL(`${RESEARCH_DIR}/06-engine-critique/engine-comparison.md`)}`,
  },
];

await parallel(p1Agents.map(a => () => agent(a.prompt, {
  label: a.label,
  phase: 'Phase 1: 并行初稿',
  effort: 'high',
})));

log('Phase 1 初稿完成（12 席）');

// ============ Phase 2: 红队对抗（6 路）============
phase('Phase 2: 红队对抗');

const P1_OUTPUTS = `Phase 1 已产出文件（请先 Read 这些文件再质疑）：
- ${RESEARCH_DIR}/01-raw-findings/source-inventory.md
- ${RESEARCH_DIR}/01-raw-findings/gameplay-slices.md
- ${RESEARCH_DIR}/01-raw-findings/mechanisms.md
- ${RESEARCH_DIR}/02-user-stories/player-stories.md
- ${RESEARCH_DIR}/02-user-stories/system-stories.md
- ${RESEARCH_DIR}/02-user-stories/operator-stories.md
- ${RESEARCH_DIR}/03-engine-insights/abstraction-options.md
- ${RESEARCH_DIR}/03-engine-insights/ugc-surface.md
- ${RESEARCH_DIR}/03-engine-insights/modern-design-review.md
- ${RESEARCH_DIR}/03-engine-insights/player-psychology.md
- ${RESEARCH_DIR}/03-engine-insights/commercialization.md
- ${RESEARCH_DIR}/03-engine-insights/performance-review.md
- ${RESEARCH_DIR}/03-engine-insights/numerical-balance.md
- ${RESEARCH_DIR}/03-engine-insights/creator-perspective.md
- ${RESEARCH_DIR}/06-engine-critique/engine-comparison.md`;

const p2Agents = [
  {
    label: '红队:横向对比验证',
    prompt: `你是红队的横向对比验证员。先阅读调研总则：${BRIEF_PATH}

${P1_OUTPUTS}

任务：交叉检查各战斗/Effect/死亡/武功实现与各抽象方案，找出共用模式与特例，验证核心抽象的覆盖度。重点：
- 抽象方案（abstraction-options / mechanisms）是否覆盖了所有代表性实例（普攻对砍/武功绝技/中毒持续/昏迷苏醒/死亡轮回/组队围攻）？
- 是否存在「伪通用」（抽象看似通用但实际只拟合了某一两类玩法）？
- 命中->伤害->状态播报->死亡判定->复活 的耦合链是否被抽象完整串起？有无断点？
- engine-critique 的对照条目（尤其 conditions.py 概念错位、地府轮回缺失、门派武功归属）有无遗漏或误判？
每条质疑必须具体，引用被质疑的文件与段落（文件路径 + 小节/行）。给出「确认/推翻/待澄清」裁决建议。
${COMMON_TAIL(`${RESEARCH_DIR}/04-redteam-review/cross-check-report.md`)}`,
  },
  {
    label: '红队:现代玩法挑战',
    prompt: `你是红队的现代玩法挑战者。先阅读调研总则：${BRIEF_PATH}

${P1_OUTPUTS}

任务：对 LPC「战斗与效果生命周期簇」机制与现代设计评审（modern-design-review）的结论提出尖锐质疑。重点：
- modern-design-review 是否过度现代化、丢弃了文本 MUD 武侠战斗的核心沉浸价值（招式想象空间/文字战斗节奏）？
- tick 驱动战斗现代化 的建议是否会破坏战斗紧张感与可读性？
- 死亡惩罚现代化（轻惩罚/复活点）是否会丢失 LPC 死亡的重量感与轮回叙事？
- 保留 LPC 某些机制（如地府轮回/鬼魂态）的论证是否充分？真的值得现代化吗？
- 玩家心理与留存结论是否与现代玩法建议矛盾？
每条质疑引用被质疑文件与段落。给出裁决建议。
${COMMON_TAIL(`${RESEARCH_DIR}/04-redteam-review/modern-challenges.md`)}`,
  },
  {
    label: '红队:体验风险挑战',
    prompt: `你是红队的玩家体验风险挑战者。先阅读调研总则：${BRIEF_PATH}

${P1_OUTPUTS}

任务：识别「战斗与效果生命周期簇」玩家流失点与必须的保护机制。重点：
- 战斗挫败/被秒杀/命中率随机性 的流失风险有多严重？player-psychology 的评估是否乐观？
- 死亡惩罚焦虑（下地府走轮回/掉落/经验惩罚）的累积压力是否被低估？
- 中毒/被控无力感（持续掉血/被封印/被擒拿无法行动）的失控体验是否被忽视？
- PvP 社交压力（组队围攻/门派敌对/抢怪霸凌）的流失风险？
- 哪些保护机制是「必须」的（免死区/保护期/反 PK/反秒杀），不是可选？给出优先级。
每条质疑引用被质疑文件与段落。
${COMMON_TAIL(`${RESEARCH_DIR}/04-redteam-review/player-experience-risks.md`)}`,
  },
  {
    label: '红队:商业化风险挑战',
    prompt: `你是红队的商业化风险挑战者。先阅读调研总则：${BRIEF_PATH}

${P1_OUTPUTS}

任务：识别「战斗与效果生命周期簇」的经济风险与 pay-to-win 陷阱。重点：
- 战斗付费点（武功/装备/复活/保护期付费）是否会越线成 pay-to-win？商业化的红线在哪？便利性付费 vs 数值付费 的边界是否清晰？
- 武功/装备/Effect 作为题材包资产 的归属/版本/分成 模型有无漏洞？
- 死亡惩罚付费减免（如付费保装备/付费少掉经验）是否越线？
- 数值平衡专家（numerical-balance）的付费数值红线结论是否被商业化方案遵守？有无矛盾？
- 现有 engine 留的商业支撑点位置是否足够？有无遗漏（如战斗数值埋点）？
每条质疑引用被质疑文件与段落。
${COMMON_TAIL(`${RESEARCH_DIR}/04-redteam-review/commercial-risks.md`)}`,
  },
  {
    label: '红队:性能风险挑战',
    prompt: `你是红队的性能风险挑战者。先阅读调研总则：${BRIEF_PATH}

${P1_OUTPUTS}

任务：识别「战斗与效果生命周期簇」的性能瓶颈与可扩展性风险。重点：
- 战斗 tick 并发（heart_beat 驱动所有 living 的 attack + condition update_condition）在 1000 在线时的开销是否被低估？
- Effect 遍历（每玩家多 condition + 30+ daemon 调用）的峰值开销；engine _on_combat_tick/_on_unconscious_tick 密度。
- 全员战斗广播（combatd/_broadcast_round）在多场战斗同时进行时的开销。
- 死亡流程（death_flow 掉落/惩罚/复活房间解析）在死亡峰值时的开销。
- set_heart_beat 启停机制的开销；现有 engine 模块的潜在性能反模式（对照 engine-comparison）。
每条质疑引用被质疑文件与段落。给出量化量级估计。
${COMMON_TAIL(`${RESEARCH_DIR}/04-redteam-review/performance-risks.md`)}`,
  },
  {
    label: '红队:数值平衡风险挑战',
    prompt: `你是红队的数值平衡风险挑战者。先阅读调研总则：${BRIEF_PATH}

${P1_OUTPUTS}

任务：识别「战斗与效果生命周期簇」的数值平衡风险与可利用漏洞。重点：
- 伤害公式/命中率/数值缩放 是否存在可被利用的崩坏点（指数爆炸/无限堆叠/边界值）？
- PvE vs PvP 数值鸿沟：MAX_OPPONENT=4 多敌对/组队围攻 的数值压力是否平衡？有无被围秒的风险？
- Effect 数值（中毒持续掉血/被封印/被擒拿）的强度与持续时间 是否存在 OP 或废招？
- 死亡惩罚数值（掉落比例/货币&技能经验惩罚比例）是否过苛（逼退新手）或过轻（无威慑）？
- 付费数值红线 是否清晰可执行？有无灰色地带（如付费影响命中率/暴击）？
- engine PowerModel 协议的数值抽象是否足够支持题材包调参与平衡？有无缺失维度？
每条质疑引用被质疑文件与段落（尤其 numerical-balance.md 与 mechanisms.md）。给出量化或反例。
${COMMON_TAIL(`${RESEARCH_DIR}/04-redteam-review/numerical-risks.md`)}`,
  },
];

await parallel(p2Agents.map(a => () => agent(a.prompt, {
  label: a.label,
  phase: 'Phase 2: 红队对抗',
  effort: 'high',
})));

log('Phase 2 红队对抗完成（6 路）');

// ============ Phase 3: 评审委员会汇总（1 个 xhigh agent）============
phase('Phase 3: 评审委员会汇总');

const ALL_OUTPUTS = `${P1_OUTPUTS}
- ${RESEARCH_DIR}/04-redteam-review/cross-check-report.md
- ${RESEARCH_DIR}/04-redteam-review/modern-challenges.md
- ${RESEARCH_DIR}/04-redteam-review/player-experience-risks.md
- ${RESEARCH_DIR}/04-redteam-review/commercial-risks.md
- ${RESEARCH_DIR}/04-redteam-review/performance-risks.md
- ${RESEARCH_DIR}/04-redteam-review/numerical-risks.md`;

const synthesisPrompt = `你是「战斗与效果生命周期簇」调研的评审委员会（5 人：玩法切片策划 + 引擎架构师 A + UGC 游戏专家 + 现代战斗玩法设计师 + 商业化与增长专家）。先阅读调研总则：${BRIEF_PATH}

${ALL_OUTPUTS}

任务：审阅 Phase 1 初稿与 Phase 2 红队报告，统一文风、消除矛盾、对分歧做裁决，生成最终报告。
要求：
1. 先 Read 上述所有文件（若某文件缺失/为空，在报告中标注「补全失败」并跳过，不要伪造内容）。
2. 使用 Write 写入：${RESEARCH_DIR}/05-synthesis/final-report.md
3. 报告结构：执行摘要 -> 范围与方法 -> 现状总览（战斗/Effect/死亡与轮回/武功 四层脉络 + 命中->伤害->状态播报->死亡判定->复活 耦合链）-> 关键发现 -> 三层 User Stories 汇总 -> 设计建议（分 engine core / UGC 创作面 / 现代化方向 / 数值平衡）-> engine 对照结论（引用 06-engine-critique 要点，突出 conditions.py 概念错位）-> 红队质疑裁决表（逐条 accept/reject/待澄清 + 理由）-> 未决问题 -> 附录（文件清单）。
4. 统一中文文风；对 Phase 1 各文件之间的矛盾点显式裁决；对红队每条质疑给出 accept/reject/待澄清 裁决。
5. 不输出可直接落地的 engine 代码或接口契约（止步设计输入）。
6. 最终回复只需确认 final-report.md 已写入 + 5-8 句话执行摘要。`;

await agent(synthesisPrompt, {
  label: '评审委员会汇总',
  phase: 'Phase 3: 评审委员会汇总',
  effort: 'xhigh',
});

log('Phase 3 评审委员会汇总完成');

return { status: 'completed', researchDir: RESEARCH_DIR };
