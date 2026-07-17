# 现状分析·战斗与武功系统 (Combat & Martial Arts)

## 概述
XKX 战斗系统以 COMBAT_D(combatd.c) 为中央仲裁器，由 living 对象的 heart_beat 驱动回合制循环。核心 do_attack() 是一个 7 步管线：选技能→取招式 action→算 AP/DP 命中判定→PP 招架判定→伤害计算(基础伤害+加力 jiali+加精 jiajin+技能 hit_ob 钩子链)→施加伤害→给经验/反击。采用 AP/(AP+DP) 概率模型，skill_power=(level³/3+combat_exp)×属性系数×精力加成。生命系统为三层资源(qi/jing/jingli)+内力(neili)，每层有 current/eff_max/max 三档。技能是独立 LPC 对象，用 mapping *action 数据驱动招式，通过 map_skill 映射、perform(外功绝招)/exert(内功功能) 分发到子文件。19 门派各有 auto_perform AI 和专属属性加成，72 个 condition 守护进程按心跳 tick 衰减。

## 现有模式
- **heart_beat 驱动的回合制战斗循环**：char.c heart_beat() 为驱动器：每 tick 检查死亡/昏迷 -> busy 则 continue_action -> is_fighting 则 attack() -> NPC chat() -> 每 5-15 tick 执行 update_condition()+heal_up()。attack() 经 clean_up_enemy()+select_opponent()(最多 4 敌随机选一) 后调用 COMBAT_D->fight()
- **COMBAT_D 七步仲裁 do_attack 管线**：combatd.c do_attack() 七步：(0)选技能 (1)取 action 招式 (2)算 AP/DP (3)random(ap+dp)<dp 则闪避 (4)random(ap+pp)<pp 则招架 (5)命中则算伤害(apply/damage+技能+加力 jiali+hit_ob 钩子链+加精 jiajin-战斗经验减免-护甲) (6)receive_damage/receive_wound (7)给经验+反击判定(TYPE_RIPOSTE)
- **AP/(AP+DP) 概率模型与 skill_power 三次方**：skill_power=(level³/3+combat_exp)/30×属性系数(str攻/dex防)×jingli_bonus(50-150)。命中概率=AP/(AP+DP)，招架概率=PP/(AP+PP)。level 三次方导致高等级碾压
- **三层资源 + 双层生命系统**：qi(气/HP)、jing(精)、jingli(精力)、neili(内力)。每项有 current/eff_max(有效上限)/max(绝对上限) 三层：receive_damage 降 current，receive_wound 降 eff 上限，heal_up 分战斗/非战斗不同速率恢复，receive_curing 疗伤恢复 eff 上限
- **数据驱动 mapping *action 招式表**：每个武功是独立 LPC 对象，定义 mapping *action 数组(含 action 描述/force/dodge/damage/lvl/skill_name/damage_type)。query_action(me,weapon) 按技能等级用 NewRandom 加权选招。map_skill(base,advanced) 将基础类型映射到门派高级武功，prepare_skill 准备空手拳脚
- **perform/exert 绝招分发与 call_out 状态机**：perform(外功绝招): cmds/skill/perform.c -> SKILL_D->perform_action(me,arg) -> perform_action_file() 加载子目录 .c -> 调 perform(me,target)。exert(内功功能): exert.c -> exert_function() -> exert_function_file() -> 调 exert(me,target)。两者都返回值多态(string/int/mapping)与 hit_ob 钩子交互
- **condition 状态系统与 CND_CONTINUE 生命周期**：feature/condition.c：mapping conditions 存储。update_condition() 每 5-15 tick 遍历，对每个条件加载 CONDITION_D 守护进程调 update_condition(me,info)，返回 CND_CONTINUE(1)则保留否则删除。72 个 condition 文件覆盖毒/醉/盲/PK/怀孕/perform 冷却等
- **19 门派体系与人种属性挂钩**：kungfu/class/ 下 18 门派目录+misc。每门派有 auto_perform.h(NPC 战斗 AI，按武器/准备技能选绝招)。race/human.c 中 setup_human() 含十余分支 if-else，按门派+技能等级+年龄计算 max_qi/max_jing 专属加成(佛家养精/道家练气/星宿聚毒/丐帮死亡成长等)

## 痛点
- combatd.c 与 s_combatd.c 是 95% 重复的孪生文件——s_combatd 是未完成的 SRPG 回合制原型(双手互博/自创连击/速度体现/阵法合击)，从未取代原系统却一直共存，维护负担翻倍
- do_attack 直接读写 dbase(my['jingli']-=my['jiajin']; my['combat_exp']+=1)——战斗逻辑与底层数据存储强耦合，无法独立测试或替换存储层
- 伤害公式满地魔法数字：/30、/10、/100、/3、/25、damage/3 减免循环等，无统一数值配置表，平衡调整需逐行改代码
- skill_power 用 level³/3 三次方增长——等级差被放大成数量级战力碾压，且 jingli_bonus 两个版本公式不一致(combatd 用 /20, s_combatd 用 /2)
- perform/exert 用 call_out(回调函数)实现持续效果(如韦陀伏魔剑的 checking 递归 call_out)——回调闭包捕获对象引用，无法序列化、无法跨进程迁移、对象销毁后悬空指针
- heart_beat 是单进程全局节拍，所有角色共享同一 tick 调度——无法分片到分布式节点，单点过载即全服卡顿
- 门派专属 max_qi/max_jing 加成硬编码在 race/human.c 的 if-else 链中(十余分支)——加门派需改种族代码，违反开闭原则
- damage_msg/eff_status_msg/status_msg 文案数组内嵌在战斗仲裁器中——国际化/换肤/A/B 测试无法进行
- perform/exert/hit_ob 的返回值多态(string|int|mapping)——调用方需对每种类型分支处理(combatd 中 5 层 if(stringp)/else if(intp)/else if(mapp) 嵌套)，脆弱且易漏分支
- select_opponent 仅随机选 4 个敌人之一——无仇恨表/无战术优先级，群战体验粗糙

## 应保留思想
- do_attack 七步管线是清晰的战斗心智模型：选技能->取招式->AP/DP 命中->PP 招架->伤害计算->施加伤害->奖励/反击，新引擎应保留这一管线分层
- AP/(AP+DP) 与 PP/(AP+PP) 的简单概率模型——双方数值都大于零故总有命中/被命中可能，无需复杂 RNG，适合服务端权威模拟
- 三层资源(qi/jing/jingli+neili) + 双层生命(current/eff_max/max)——精巧区分'疲劳'与'创伤'，给予战斗恢复策略深度，值得保留为数据模型
- 数据驱动的 mapping *action 招式表(force/dodge/damage/lvl/damage_type/skill_name)——这本质就是技能 DSL 的雏形，新架构可演进为 YAML/JSON 技能定义
- hit_ob/hit_by 钩子链——内功/武器/护甲/特殊轻功各自提供伤害修正回调，是可扩展的伤害管线设计，应保留为 Effect Pipeline
- map_skill/prepare_skill 间接层——基础技能类型到门派武功的运行时映射，让同一战斗引擎支持多门派，应保留为技能绑定机制
- condition 的 CND_CONTINUE 生命周期标志——状态守护进程自主决定存活/过期，是简洁的状态机协议，可演化为 Buff/Debuff 系统
- auto_perform 作为可插拔 NPC 战斗 AI 接口——门派通过 .h 文件注入战斗策略，是策略模式的良好实践，应保留为 NPC AI 挂载点
- combatd 中 do_attack 末尾的反击(riposte)递归调用——TYPE_REGULAR 未命中且 guarding 则对手反击，是战斗节奏的有机组成

## 应废弃设计
- s_combatd.c 重复副本——SRPG 原型未采用，与 combatd.c 95% 重复，应废弃
- damage.c.bk / damage_backup.c 备份文件——git 已做版本控制，应删除
- combatd.c 内嵌的 damage_msg/eff_status_msg/status_msg 消息数组——战斗逻辑与文案强耦合，应抽离为数据文件
- human.c setup_human() 中的门派专属加成 if-else 链——种族属性计算不应硬编码门派逻辑，应由门派数据声明
- do_attack 中直接读写 dbase(my['jingli']-=my['jiajin'])——应通过 CombatState 接口操作，禁止逻辑层直接改底层数据
- perform/exert 用 start_call_out(回调函数)实现持续效果——应改为 tick 调度的显式 Effect 对象，可序列化可中断
- attack.c 中 special_attack() 硬编码双使兵刃/辟邪剑/双手互博条件——应抽象为可配置的战斗修饰器
- NewRandom(int n,base,d) 加权随机——实现晦涩且仅少林武功使用，应替换为标准概率表配置

## 复杂度热点
- /adm/daemons/combatd.c 的 do_attack() 函数（约440行）——7步攻击流水线集中了技能选择、AP/DP/PP概率判定、伤害链式加成、hit_ob/hit_by钩子、护甲/闪避特殊效果、经验奖励、反击递归调用，是全系统最复杂的单一函数，且与 dbase 直接耦合
- /adm/daemons/race/human.c 的 setup_human()——门派专属 max_qi/max_jing 计算逻辑全部硬编码在种族 setup 中（佛/道/毒/古墓/灵鹫/明教等十余分支 if-else 嵌套，含年龄衰减、技能加成、死亡次数加成），是种族/门派耦合最严重的耦合点
- /kungfu/skill/damo-jian/weituo.c 等 perform 文件——通过 start_call_out 递归调用自身 checking() 维护持续效果状态（sl_weituo 计数器、apply/attack 临时加成与恢复），状态机隐式散布在多个 call_out 回调中，难以序列化与测试
- /inherit/skill/force.c 的 hit_ob()——内力对撞逻辑（myneili/yourneili 比较、负伤害反震、armor_vs_force 扣减）与返回值多态（string/int/mapping 三种返回类型）混合，调用方需在 combatd 中对返回值做类型分支处理
- skill_power() 公式的三次方增长（level³/3）——等级差异被放大成数量级战力差，直接决定 AP/DP/PP，是数值平衡的核心痛点且无配置化调节点

## 关键文件
- /home/gukt/github/xkx2001-utf8/adm/daemons/combatd.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/s_combatd.c
- /home/gukt/github/xkx2001-utf8/feature/attack.c
- /home/gukt/github/xkx2001-utf8/feature/damage.c
- /home/gukt/github/xkx2001-utf8/feature/condition.c
- /home/gukt/github/xkx2001-utf8/feature/skill.c
- /home/gukt/github/xkx2001-utf8/feature/action.c
- /home/gukt/github/xkx2001-utf8/inherit/char/char.c
- /home/gukt/github/xkx2001-utf8/inherit/skill/skill.c
- /home/gukt/github/xkx2001-utf8/inherit/skill/force.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/race/human.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/chard.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/weapond.c
- /home/gukt/github/xkx2001-utf8/kungfu/skill/damo-jian.c
- /home/gukt/github/xkx2001-utf8/kungfu/skill/damo-jian/weituo.c
- /home/gukt/github/xkx2001-utf8/kungfu/skill/hunyuan-yiqi.c
- /home/gukt/github/xkx2001-utf8/kungfu/skill/hunyuan-yiqi/jingang.c
- /home/gukt/github/xkx2001-utf8/kungfu/class/shaolin/auto_perform.h
- /home/gukt/github/xkx2001-utf8/cmds/skill/perform.c
- /home/gukt/github/xkx2001-utf8/cmds/skill/exert.c
- /home/gukt/github/xkx2001-utf8/include/combat.h
- /home/gukt/github/xkx2001-utf8/include/condition.h
- /home/gukt/github/xkx2001-utf8/kungfu/skill/dodge.c
- /home/gukt/github/xkx2001-utf8/kungfu/skill/parry.c
