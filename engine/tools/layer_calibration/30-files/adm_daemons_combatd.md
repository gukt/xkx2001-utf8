# adm_daemons_combatd 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/adm/daemons/combatd.c
- basename: adm_daemons_combatd
- 总语义单元数: 14
- 各层计数: 层0=6  层1=0  层2=0  层3=9
- 引擎侧/内容侧: 引擎侧（消息表文本可由题材包扩展，但 daemon 逻辑是平台代码）
- 层3 项: 有（9 项）

## 语义单元标注

| 语义单元 | 层 | 引擎侧/内容侧 | 理由 |
|---|---|---|---|
| guard_msg 数组（5 条防御姿态消息） | 层0 | 内容侧可扩展 | 纯数据声明，随机消息池 |
| catch_hunt_human/beast/bird_msg 数组（7/3/3 条） | 层0 | 内容侧可扩展 | 纯数据声明，按 race 分类的追敌消息池 |
| winner_msg / winner_animal_msg 数组（6/3 条） | 层0 | 内容侧可扩展 | 纯数据声明，胜利消息池 |
| damage_msg 分级文本表（8 类型 + default，6-7 档分级） | 层0 | 内容侧可扩展 | 纯数据声明，伤害类型+伤害值 -> 描述文本的二维查表 |
| eff_status_msg 分级文本表（11 档百分比） | 层0 | 内容侧可扩展 | 纯数据声明，eff_qi 百分比 -> 伤势描述查表 |
| status_msg 分级文本表（10 档百分比） | 层0 | 内容侧可扩展 | 纯数据声明，qi 百分比 -> 疲惫度描述查表 |
| create() seteuid + set name/id | 层3 | 引擎侧 | daemon 对象生命周期初始化 |
| damage_msg(damage, type) 伤害描述生成 | 层3 | 引擎侧 | 按 type switch + damage 分级 if-else 链查表，虽查表数据已层0，但分支调度逻辑是层3 |
| eff_status_msg(ratio) / status_msg(ratio) 伤势描述生成 | 层3 | 引擎侧 | ratio 分级 if-else 链查表，分支调度逻辑 |
| report_status(ob, effective) 状态报告 | 层3 | 引擎侧 | 计算 ratio + 调 eff/status_msg + message_vision 输出，含计算与副作用 |
| skill_power(ob, skill, usage) 战斗力算法 | 层3 | 引擎侧 | level^3/3 + jingli_bonus + str/dex 加成 + is_fighting 修正 + 封顶，纯算法 |
| do_attack(me, victim, weapon, attack_type) 七步管线 | 层3 | 引擎侧 | combat 确定性核心：七步副作用交织不可分离（CLAUDE.md 不变量），29+ 处 random()，riposte 递归，hit_ob/hit_by 多层回调，属层3 平台代码 |
| fight(me, victim) heart_beat 入口 | 层3 | 引擎侧 | 状态机：victim busy/unconcious -> TYPE_QUICK、主动性 random 判定 -> TYPE_REGULAR、双武器/辟邪剑/双手互博二次攻击、guarding 防御 |
| auto_fight + start_berserk/hatred/vendetta/aggressive | 层3 | 引擎侧 | 自动战斗状态机：NPC-NPC 排除、looking_for_trouble 防重复、call_out 延迟、start_berserk neili vs shen 随机判定、start_hatred 按 race 分消息 |
| announce(ob, event) / winner_reward / death_penalty / killer_reward | 层3 | 引擎侧 | 死亡/昏迷消息分发 + 击杀奖励 + 死亡惩罚算法（多属性计算+条件分支+持久化）+ killer_reward（race 决定 mode + free_rider 判定 + condition 追加 + 频道广播） |

## 备注

- combatd 按 ADR-0014 演进为 CombatSystem（ECS System，tick 驱动），是 6 个 ECS System 之一。本文件是本批中最大的层3 文件。
- 6 个消息表（层0）可由题材包（wuxia Theme）扩展，但 damage_msg/eff_status_msg 的分级阈值与伤害类型分类是 combat 核心数据，应与 CombatKernel 一起从武侠提取、用非武侠验证（CLAUDE.md 不变量）。
- do_attack 七步管线的 SideEffect.order 已在 layer_e_combat.py 完整提取（49 个 SideEffect），是 combat 确定性的核心。29+ 处 random() 全部提取为 RandomSpec，combat 确定性范围=combat-only（全仿真后置 M3）。
- 本文件无层1/层2 成分：combat 逻辑是状态机+算法+递归，无法用谓词或对话树表达。
- death_penalty/killer_reward 涉及层 F（死亡轮回）的调用点，但定义在 combatd.c 中，按 ADR-0014 仍属 CombatSystem 职责范围。
- 已有规格：layer_e_combat.py 提取了 skill_power/do_attack/damage_msg/eff_status_msg/report_status/fight/auto_fight/death_penalty 等 FunctionSpec，本标注表的层归属与规格一致。
