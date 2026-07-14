# Done 归档 - 阶段 2（子系统 Wave 1-4, 2.1-2.7）

> 从 PROGRESS.md 归档于 2026-07-14。阶段 2 已完成条目的历史记录，按需检索。
> 当前活状态见 [PROGRESS.md](../../PROGRESS.md)。

## Done

- [x] **阶段 2 Wave 1 2.1 Query/索引层完成**（[ADR-0025](docs/adr/ADR-0025-query-index-layer.md) / [15](docs/xkx-arch/15-阶段2-子系统实施计划.md) §三 2.1）：
  - [ADR-0025](docs/adr/ADR-0025-query-index-layer.md) Query/索引层设计（Wave 1 前置）：query() 语义对齐 LPC F_DBASE 8 函数 + 未映射 key 三类区分（mapped/postponed/unknown，dissent 2 拼写错误不静默）+ 索引层线性扫描 + 后置 key 激活策略 + 映射表收敛（inspector.LPC_KEY_MAP 从 DBASE_KEY_MAP 派生）
  - [query.py](engine/src/xkx/runtime/query.py) 新建：8 函数（query/query_temp/set/set_temp/add/add_temp/delete/delete_temp，对照层 B 规格）+ 索引层（entities_with_family/entities_by_prototype/find_in_room/find_item）+ Identity/Position/Inventory 语义函数（id_match/short/move_to/environment/present_item/all_inventory）
  - [dbase_map.py](engine/src/xkx/runtime/dbase_map.py) 扩展：DbaseKeyError（SchemaError 子类）+ is_postponed + classify_key（三类区分）+ KeyClass Literal
  - [inspector.py](engine/src/xkx/runtime/inspector.py) 重构：LPC_KEY_MAP 从 DBASE_KEY_MAP + PATH_PREFIX_MAP + POSTPONED_KEYS 派生（删除 _LPC_ENTRIES 硬编码，单一信源收敛）；lpc_key_mapping 复用 classify_key + resolve_dbase_key
  - greenfield 简化台账 12 项（ADR-0025 §简化台账）：raw/evaluate/default_ob/完整 treemap 砍掉（LPC 特有）；short 状态修饰后置 2.5；move 负重级联后置 2.3；greenfield 不区分 dbase vs tmp_dbase（query/query_temp 行为一致）
  - [test_query.py](engine/tests/test_query.py) 66 tests：8 函数 + 三类处理 + 索引层 + 语义函数 + hypothesis 属性测试（路径前缀往返 + key 三类分类 + add 增量 + marks/ 往返）+ marks/ 自动创建
  - **实现 bug 修复**：query.py `def set` 覆盖内置 `set` 类型 -> `builtins.set`/`builtins.frozenset`（3 处 isinstance + 1 处 all_inventory 副本构造）
  - **1101 tests 全绿（+66），ruff 全过**；test_theme_neutrality + test_load_test 硬门禁持续通过
  - agent teams 并行：2 agent（inspector 重构 + test_query 编写），inspector 重构无回归，test_query 发现 set 覆盖 bug 后修复
  - 关联 dissent 2（query 语义不偏离 LPC F_DBASE）+ dissent 8（不新增组件，无序列化需求）

- [x] **阶段 2 Wave 2 2.2 Vitals/Heal/Condition 完成**（[15](docs/xkx-arch/15-阶段2-子系统实施计划.md) §三 2.2 / [ADR-0018](docs/adr/ADR-0018-conditionhandler-on-tick-contract.md) 契约演进）：
  - Vitals 扩展 eff_jing/water/food 字段（heal_up 恢复上限 + 饥饿/脱水门控，对照 feature/damage.c:270-331）+ dbase_map 激活（POSTPONED 移除 eff_jing/no_death，加 water/food）
  - [heal.py](engine/src/xkx/runtime/heal.py) HealSystem + heal_up 完整语义（jing/qi/eff_jing/eff_qi/jingli/neili 恢复 + 战斗 1/3 速率 + water/food 门控 + 三层不变量 0<=qi<=eff_qi<=max_qi + eff_jing 达上限后才涨 + 完全确定性无 random）
  - [death.py](engine/src/xkx/runtime/death.py) 死亡轮回 9 函数（die/unconcious/revive/reincarnate/death_penalty/killer_reward/make_corpse/announce/check_death，对照 layer_f 规格 + LPC 原文精确公式）：
    - check_death 双层触发（eff_qi<0 直接 die / qi<0 先 unconcious 昏迷中再触发 die）
    - die 主流程（no_death 房转 unconcious / 玩家 ghost=1 move DEATH_ROOM / NPC destruct）
    - death_penalty 三段扣减（combat_exp>5000 扣 amount+potential 半 / 20<exp<=5000 扣 20 / <=20 不扣，确定性）
    - killer_reward（killer condition 100 tick 城区 + pker +120 双玩家，PKS/MKS/shen 后置 2.5）
    - make_corpse（ghost 物品掉环境 / 正常生成尸体实体 + 物品转移，装备重穿后置 2.3）
  - [conditions.py](engine/src/xkx/runtime/conditions.py) 扩展：apply_condition/query_condition/clear_condition/clear_one_condition 运行时函数（对齐 LPC F_CONDITION，直接覆盖语义，叠加由调用方 query+delta）+ condition handler 注册机制 + 7 个具体类型（poisoned 壳/snake_poison DoT/drunk 分档 debuff/blind 静默/killer 计时器/pker 叠加/revive 苏醒）
    - **ADR-0018 契约演进**：condition_deltas/completed 改用 EffectComp 实体 eid（int）作 key（支持多 target 同名 condition 独立衰减，原 effect_id 假设全局唯一被 apply_condition 打破）
  - combat/result.py 加 5 个 Effect kind（KIND_HEAL/KIND_HEAL_JING/KIND_DAMAGE_JING/KIND_WOUND_JING/KIND_CLEAR_MARK，condition 驱动的恢复/扣减/标记清除）+ world.apply_effects 扩展
  - **2.2 范围控制**（收敛）：阴间剧情后置 2.6（die 玩家 ghost=1 move DEATH_ROOM 为止）/ break_marriage/log_file/谣言后置 M3 / skill_death_penalty 简化 stub（所有技能 -1，真实 learned 公式后置 2.3）/ PKS/MKS/shen 后置 2.5 TitleComp / winner_reward stub / make_corpse 装备重穿后置 2.3
  - **确定性**：death_penalty/killer_reward 无 random（对齐 LPC）；unconcious 的 revive 延时 random(100-con)+30 用系统 RNG（非 combat 确定性范围）
  - 测试：[test_heal.py](engine/tests/test_heal.py) 16 + [test_condition_types.py](engine/tests/test_condition_types.py) 21 + [test_death.py](engine/tests/test_death.py) 21（含 hypothesis 三层不变量 + 多 target 同名 condition 独立衰减 + death_penalty 确定性）
  - **1159 tests 全绿（+58），ruff 全过**；test_theme_neutrality + test_load_test 硬门禁持续通过
  - 关联 dissent 8（新组件可序列化，Vitals 扩展字段全基本类型）+ dissent 7（condition handler 交织账本，ConditionTickResult ledger）+ ADR-0018 契约演进（effect_eid key）

- [x] **阶段 2 Wave 2 2.3 Attribute/Skill/Equipment 完成**（[15](docs/xkx-arch/15-阶段2-子系统实施计划.md) §三 2.3 / [ADR-0026](docs/adr/ADR-0026-modifier-stack-and-skill-layers.md) + 实现期细化 6 项）：
  - [equipment.py](engine/src/xkx/runtime/equipment.py) 新建：wield/wear/unequip（对照 [equip.c](feature/equip.c)，prop 注入/反向扣减 + 槽位 flag TWO_HANDED/SECONDARY + reset_action 更新 CombatState）+ is_equipped/total_weight/add_encumbrance
  - Equipment 组件（weapon/secondary_weapon/armors + per-slot prop 副本 weapon_props/secondary_weapon_props/armor_props + encumbrance/max_encumbrance，可序列化）
  - Skills 扩展 apply_speed/skill_map/skill_prepare/learned（learned 衔接 skill_death_penalty 真实公式）
  - [query.py](engine/src/xkx/runtime/query.py) query_skill 三层叠加（apply/{skill} + levels/2 + skill_map，对照 [skill.c:94-109](feature/skill.c)）+ effective_apply/effective_skill_level
  - dbase_map 激活 apply_speed/weight/encumbrance + apply/ 前缀分发（APPLY_SUBPATH_MAP）+ equipped 语义 key（SEMANTIC_KEY_MAP）+ POSTPONED 移除 equipped/apply
  - ModifierStack 三类叠加（永久基础值 levels + 临时修正 apply_* + 装备加成注入 apply_* 标量，对照 LPC query 链）
  - [death.py](engine/src/xkx/runtime/death.py) 衔接 2.2 stub：make_corpse 装备重穿（unequip 所有 + 装备物品转移尸体）+ skill_death_penalty 真实 learned 公式（[skill.c:121-147](feature/skill.c)，修正 LPC learned 覆盖 bug）
  - CombatantSnapshot 加 apply_speed（快照边界，resolve_attack 不变，ADR-0023 第 4 项定稿）
  - **ADR-0026 实现期细化 6 项**：Skills 加 learned / Equipment per-slot prop 副本 / equipped 语义 key（非 DBASE_KEY_MAP）/ apply 未知子路径读返回 0 / skill_death_penalty 修正 LPC 覆盖 bug / wield 不自动算重量
  - 测试 [test_modifier_stack.py](engine/tests/test_modifier_stack.py) 36 tests（Equipment + ModifierStack + query_skill + apply 前缀 + equipped 语义 + death 衔接 + hypothesis 三类叠加交换律/unequip 回归 condition-only + 主题无关性）
  - **1196 tests 全绿（+37），ruff 全过**；test_theme_neutrality + test_load_test 硬门禁持续通过
  - 关联 dissent 3（三类叠加语义明确 + apply_* 不落入层1 DSL）+ 专家 3 承重（技能三层 levels+skill_map）+ dissent 8（Equipment 可序列化）+ dissent 7（per-slot prop 副本来源可追溯）

- [x] **阶段 2 Wave 2 2.5 TitleSystem 称谓完成**（[15](docs/xkx-arch/15-阶段2-子系统实施计划.md) §三 2.5 / [ADR-0028](docs/adr/ADR-0028-rank-d-spec-and-pronoun-context.md)）：
  - [title.py](engine/src/xkx/runtime/title.py) 新建：RANK_D 7 函数无状态纯函数（query_rank/respect/rude/self/self_rude/query_close/query_self_close，对照 [rankd.c](adm/daemons/rankd.c) 行 8-651 精确对齐）+ 5 张可注入 class 表（CLASS_RANK/RESPECT/RUDE/SELF/SELF_RUDE_TABLE）+ WIZHOOD_TITLES + set/reset_class_tables + query_wizhood 钩子
  - 求值顺序不变量：is_ghost 最先(行19) -> wizhood 优先(行60-78) -> PKS>100 且 PKS>MKS(行80) -> class 注入表(行85-318) -> shen 阈值分级(行147-316，正降序/负升序/default 平民) -> rank_info 四键覆盖优先(行327/411/468/520)
  - **主题中立**（ADR-0028 开放问题 2 裁决）：核心引擎不硬编码武侠门派职业字面量（bonze/taoist 等），class 分支表数据从题材包注入，test_theme_neutrality 硬门禁 grep 无武侠字面量
  - [pronoun.py](engine/src/xkx/runtime/pronoun.py) 扩展：PronounContext frozen dataclass slots 10 字段（name_me/you + pronoun_me/you + close/close_rev + respect/respect_rev + self/self_rude）+ PronounService 7 函数委托 + build_context（$C/$c 角色互换 viewer 翻转：close=query_close(speaker,target)/close_rev=query_close(target,speaker)）+ render（10 占位符 $N/$n/$P/$p/$C/$c/$R/$r/$S/$s 替换）+ build_context_for_system（System tick viewer=speaker 回退，决策 4）+ visible 补 is_ghost 判定 + 可见性门控（不可见时 $n/$p/$C/$c/$R/$r 退化避免泄露隐身目标）
  - TitleComp 第 14 组件（13 字段：title/nickname/shen/rank_info 四键/pks/mks/char_class/dali_rank/family_rank/is_ghost，可序列化 ADR-0022）+ dbase_map 激活 7 key（title/nickname/shen/PKS/MKS/class/rank）+ 2 路径前缀分发（rank_info->四字段，dali->dali_rank）
  - [query.py](engine/src/xkx/runtime/query.py) short 状态修饰：short(world, eid, *, raw=False)，严格按 [name.c](feature/name.c) 行 99-147 顺序（打坐/吐纳/静坐提前 return -> title/nickname 前缀 -> 鬼气前缀 -> 断线/昏迷尾部），raw=True 纯函数
  - [spec/layer_h_daemons.py](engine/src/xkx/spec/layer_h_daemons.py) 补 RANK_D 7 函数 FunctionSpec（行号精确 + 不变量完整 + this_player 依赖标注 + cross_layer_refs 19->24），LAYER_SPEC.function_specs 26->33
  - [world.py](engine/src/xkx/runtime/world.py) spawn 衔接：_spawn_npc/spawn_player 加 TitleComp() 默认实例
  - **agent teams 3 路并行**：批次 0 单 agent 根依赖（TitleComp+dbase_map+schema）-> 批次 1 三路并行（A: title.py+pronoun.py+spawn，B: spec FunctionSpec，C: query.py short，改不同文件无冲突）-> 批次 2 单 agent test_title.py 107 tests
  - **穿插 ADR-0016** 层1 谓词扩充 8 类（独立 dsl 层，后台并行，不碰 runtime）
  - 测试 [test_title.py](engine/tests/test_title.py) 107 tests：7 函数行为等价（gender/class/shen/PKS/age/wizhood/ghost 全分支）+ PronounContext 10 变量（$C/$c 翻转 + 可见性门控 + System 回退）+ TitleComp 序列化往返 + short 集成 + PKS 称号 + 5 hypothesis 属性测试（rank_info 覆盖 + query_close 辈分 + is_ghost 短路）
  - **1339 tests 全绿（+143：107 test_title + 12 test_query short + 24 其他适配），ruff 全过**；test_theme_neutrality + test_load_test 硬门禁持续通过
  - 关联 dissent 6（PronounContext viewer 显式传参 + $C/$c 翻转实证专家 3 承重论断 2）+ dissent 8（TitleComp 可序列化）+ dissent 3（class 分支表数据非层1 谓词，主题中立）

- [x] **穿插 ADR-0016 层1 谓词扩充第二批完成**（[ADR-0016](docs/adr/ADR-0016-layer1-predicate-expansion-batch2.md) 8 类缺口，2.5 推进期间后台并行）：
  - [layer1.py](engine/src/xkx/dsl/layer1.py) 扩展 8 类谓词（attr_eq / is_wizard / has_item 扩展 item_category+item_name / has_flag 扩展 source=temp / derived_state / status_eq+same_object+mud_age_lt / has_inquiry+attr_in / command 事件钩子）
  - [spec/layer_c_command.py](engine/src/xkx/spec/layer_c_command.py) 命令 deny 规格补充（kill.c 7 条 + ask.c 分支）
  - 测试 [test_layer1_predicates_batch2.py](engine/tests/test_layer1_predicates_batch2.py) 24 tests passed
  - 护栏遵守：不引入 attr_gt/le/ge、不引入 has_item_count、derived_state 统一抽象、command 仅前置 deny
  - **全量 1339 tests 含 ADR-0016 24 tests，ruff 全过**；独立 dsl 层不碰 runtime/components（与 2.5/2.6 无文件冲突）
  - agent 最终 task-notification 未到，基于文件状态（layer1.py 25 处谓词 + 24 tests passed + 24 分钟无改）确认实质完成
  - 关联 dissent 3（层1 原语蠕变护栏，8 类均有 LPC 实证）

- [x] **阶段 2 Wave 2 2.6 WorldGovernanceSystem 完成**（[15](docs/xkx-arch/15-阶段2-子系统实施计划.md) §三 2.6 / [ADR-0029](docs/adr/ADR-0029-world-governance-system.md)）：
  - [governance.py](engine/src/xkx/runtime/governance.py) 新建（~590 行）：GovernanceSystem 平台级 fail-closed System（独立遍历 effect_id="death_stage" EffectComp，非均匀 tick，不混入 ConditionSystem on_tick）+ 阴间死亡轮回（enter_underworld gate.c 物品销毁 + 启动 death_stage EffectComp 首延 30 秒 5 段每段 5 秒 / death_stage_handler 纯函数 / reincarnate_at 主路径丢弃物品 + 隐藏路径不丢弃）+ 法院通缉（apply_wanted/query_wanted + WANTED_REGIONS 四区域 city/xa/dl/bj 统一为 WantedCondition）+ 审判收监（proceed_sentencing PKS 分级 99/74/49=>500/300/200 + 累犯加重 city_jail>4=>600 + 穿琵琶骨 + 经验转移上限 3000 + bribe_clear_wanted 受贿销案）+ 监狱（release_from_jail + JAIL_ROOMS city_jail/dali_jail/bonze_jail）
  - **2.2 已完成使阴间闭环可做完整**（ADR-0029 决策 6 原计划只做骨架，但 2.2 death.py die/reincarnate/make_corpse 已就绪）：[death.py](engine/src/xkx/runtime/death.py) die() 衔接调 enter_underworld（加 tick 参数 + 延迟 import 规避循环依赖）+ check_death 透传 tick + [engine.py](engine/src/xkx/runtime/engine.py) GovernanceSystem 注册
  - [conditions.py](engine/src/xkx/runtime/conditions.py) 扩展：3 jail handler（city_jail/dali_jail/bonze_jail 到期衔接 release_from_jail，延迟 import governance）+ JAIL_CONDITIONS 集合
  - **累犯加重 bug 修复**：proceed_sentencing 原 clear_condition 在 query_condition("city_jail") 之前致累犯分支死代码（LPC kexiu.c:229 顺序相反），修复为 clear 前先查 existing_jail，累犯加重生效
  - 3 个开放问题按 ADR-0029 倾向裁决：death_stage 归 GovernanceSystem 独立遍历（开放问题 1）/ 通缉衰减归 ConditionSystem（开放问题 2）/ 阴间位置 room_id 常量（开放问题 3）
  - 测试 [test_governance.py](engine/tests/test_governance.py) 77 tests（1263 行）：A 平台 fail-closed 边界 + B 阴间完整闭环（die->gate.c 销毁->5 段->还阳主/隐藏）+ C gate.c 物品销毁副作用顺序 + D death_stage 崩溃恢复 + E 黑无常 is_ghost + F 法院通缉四区域 + G 审判收监 PKS 分级 + H 受贿销案 + I 监狱释放 + J 可序列化 + K hypothesis 3 属性（通缉衰减/量刑单调/PKS>99 恒 500）+ L test_theme_neutrality 硬门禁
  - **1421 tests 全绿（+82：test_governance 77 + test_death +5 衔接），ruff 全过**；test_theme_neutrality + test_load_test 硬门禁持续通过
  - 关联 dissent 5（themed 治理平台级 fail-closed Python 不入 UGC 规则层）+ dissent 10（5 灵魂系统只含 2 代表性元素，276 文件武林大会/vote/intermud 后置 M3）+ dissent 5 延伸（call_out 翻译为 EffectComp，GovernanceSystem 自有 handler）

- [x] **ADR-0027 产出（2.4 Combat 前置）**（[ADR-0027](docs/adr/ADR-0027-combat-callout-formation-golden-trace.md)）：
  - 覆盖 ADR-0023 未触及的 3 项承重决策：call_out -> Effect 翻译（dissent 1/7）+ s_combatd 阵法合击 CombatModifier（dissent 1）+ golden trace 录制/diff 协议（dissent 4）
  - **call_out 翻译**：2.4 只翻译 combat 核心路径（revive + start_ + remove_call_out 约 10 处），非全库 144 处穷尽；闭包型 call_out -> EffectComp（duration + 可中断 + 崩溃恢复 + 参数载荷），复用 ADR-0017 EffectComp + ADR-0022 崩溃恢复 + ADR-0018 ledger；revive 的 `random(100-con)+30` 用系统 RNG（非 combat 确定性范围）；start_ 延迟 0 秒倾向同步执行 + 防御检查
  - **阵法合击关键发现**：`s_combatd.c` 是 combatd 的"带 damage_msg 文本"副本（**非阵法**）；真正阵法入口是 [feature/attack.c:197](feature/attack.c#L197) `special_attack` 检查 `stand/anubis` 标记 -> `S_COMBAT_D->fight`，具体阵法在 [kungfu/skill/](kungfu/skill/) 题材脚本（pozhen/buzhen/heji）
  - **CombatModifier 主题无关接口**：阵法合击是题材内容（kungfu/skill/），走 SkillData/FormationData 声明不进内核；CombatModifier 声明式载体（modifier_type/participants/attack_modifier/defense_modifier/message/post_action）内核只做分发；2.4 只定接口 + special_attack 调用点，具体阵法后置 2.7/M3
  - **golden trace diff 三层协议**：L1 概率分布 diff（多次采样对照 layer_e 31 处 random 概率模型，卡方检验非逐字）+ L2 文本结构 diff（七步结构 + ANSI 剥离 + 伤害描述分类映射）+ L3 语义 diff（占位符对照 PronounContext）；定位辅助验证非主线门禁（主线是单元级行为规约 + ConformanceChecker + combat-sim）；diff 工具 [engine/tools/golden_trace/diff.py](engine/tools/golden_trace/diff.py) 新建
  - LPC 源码勘察：combatd.c call_out 1 处（行 866 start_ 延迟）+ damage.c call_out 3 处（revive 延迟 + remove_call_out）+ attack.c special_attack 阵法入口 + kungfu/skill/ 阵法脚本
  - 待用户评审，评审通过启动 2.4 编码

- [x] **阶段 2 Wave 3 2.4 Combat 编码完成**（[ADR-0027](docs/adr/ADR-0027-combat-callout-formation-golden-trace.md) 落地 / [15](docs/xkx-arch/15-阶段2-子系统实施计划.md) §三 2.4）：
  - **call_out -> Effect 翻译**（ADR-0027 §1）：revive + remove_call_out 2.2 已完成（EffectComp 化），2.4 补测试 + 文档化中断契约；start_* 同步执行 + 5 防御检查（[auto_fight.py](engine/src/xkx/runtime/auto_fight.py) 新建，§1.2 决策同步执行非 duration=0 EffectComp；具体 fight 逻辑 kill_ob/fight_ob 后置 M3 NPC AI）。实现期细化：start_* 放 runtime/auto_fight.py（非 conditions.py，因同步执行不用 EffectComp）
  - **CombatModifier 协同修正接口**（ADR-0027 §2）：[modifier.py](engine/src/xkx/combat/modifier.py) 新建 frozen dataclass 主题无关字段 + CombatantSnapshot 加 formation_modifier 字段（快照边界注入）+ [system.py](engine/src/xkx/combat/system.py) CombatSystem.tick special_attack 调用点（只读 formation_modifier，ap/dp 修正 + message + post_action 透传）。实现期细化：阵法标记检查移到快照构建边界（combat 包自包含不查 Marks，runtime 层 CombatBridge 后置整合）；具体阵法逻辑（pozhen/buzhen/heji）后置 2.7/M3
  - **golden trace diff 三层协议**（ADR-0027 §3）：[diff.py](engine/tools/golden_trace/diff.py) 新建 L1 概率分布 diff（边际概率链 + 卡方检验）+ L2 文本结构 diff（七步结构 + ANSI 剥离 + 伤害分类映射）+ L3 语义 diff（占位符 PronounContext 渲染）+ CLI + DiffReport；非侵入设计（只消费 ledger + baseline）
  - **关键发现**：LPC 概率模型 `parry_p=pp/(ap+pp)` 是理论公式，resolve_attack 顺序判定（dodge 成功则 return）需用边际概率链 `P(parry)=(1-dodge_p)*pp/(ap+pp)` 匹配实际行为，卡方 p=0.069>0.05 通过
  - **主题无关硬门禁**：test_theme_neutrality 扩展阵法/合击/anubis/sword/blade 字面量黑名单（扫描 modifier.py + system.py + auto_fight.py）；impl_map 加 COMBAT_EXTENSION_IMPL_MAP 3 条 implemented 标注（callout_revive/start_translation + formation_modifier_interface）
  - agent teams 2 批次 4 agent：批次 1 三路并行（A modifier.py + 13 tests / B auto_fight.py + 23 tests / C diff.py + 49 tests，改不同文件无冲突）+ 批次 2 串行（D system.py special_attack + 7 tests / E theme_neutrality 扩展 + impl_map 标注自做）
  - 测试：[test_combat_modifier.py](engine/tests/test_combat_modifier.py) 20（13 接口 + 7 special_attack）+ [test_callout_translation.py](engine/tests/test_callout_translation.py) 23 + [test_golden_trace_diff.py](engine/tests/test_golden_trace_diff.py) 49 = 92 新测试
  - **1514 tests 全绿（+93），ruff 全过**；test_theme_neutrality + test_load_test 硬门禁持续通过；golden trace diff CLI 端到端三层全 PASS
  - 关联 dissent 1（CombatKernel 主题无关，阵法合击题材内容不进内核）+ dissent 4（golden trace diff 定位辅助验证非主线门禁）+ dissent 7（call_out 翻译 EffectComp 审计轨迹）

- [x] **阶段 2 Wave 4 2.7 门派切割完成**（[ADR-0030](docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md) 落地 / [15](docs/xkx-arch/15-阶段2-子系统实施计划.md) §三 2.7）：
  - **race 层剥离**（决策 1）：[race.py](engine/src/xkx/runtime/race.py) RaceProfile 数据声明 + setup_race 纯函数（年龄分层 max_jing/max_qi/max_jingli 公式 + 70 岁衰减 + max_potential/max_encumbrance/weight，公式参数从 profile 读取不硬编码门派名）+ [family.py](engine/src/xkx/runtime/family.py) FamilyBonus 声明式载体 + apply_family_bonuses 分发函数（family_name 字符串匹配 + 条件检查 + 公式计算，不认识具体门派名）
  - **ThemeConfig 房间路径外提**（决策 2）：[theme.py](engine/src/xkx/runtime/theme.py) ThemeConfig（start_room/death_room/revive_room/jail_rooms + default 非武侠/wuxia 武侠）+ [world.py](engine/src/xkx/runtime/world.py) build_world 加 theme_config 参数 + governance.py/death.py/cli.py 改读 world.theme_config（源码无武侠房间路径字面量）
  - **dbase key 兼容层保真让步豁免**（决策 3）：dbase_map.py 的 "dali/rank" + TitleComp.dali_rank 字段名保留（LPC dbase key 兼容，类比 ADR-0003 qi/jing 拼音保留），test_theme_neutrality 硬门禁豁免
  - **test_theme_neutrality 扩展收官硬门禁**（决策 4）：扫描范围扩展到 governance/death/cli/race/family，黑名单加门派名（武当/少林/峨嵋/华山/丐帮/桃花/古墓/灵鹫/星宿/白驼/明教/雪山派/血刀/大理段/全真）+ 武侠房间路径（shaolin//dali//xueshan//huashan//wudang//emei/），+4 tests
  - **1-2 门派验证**（决策 5）：武当派保气标准加成（FamilyBonus 标准载体）+ 海盗帮派航行加成（非武侠 FamilyBonus 边界验证）
  - **Vitals 补 eff_jingli**（2.2 遗漏补全）：LPC human.c 行 212/404 引用 eff_jingli，2.2 扩展 eff_jing 漏了 eff_jingli，2.7 补全 + dbase_map 激活
  - **spec 层规格补充**（开放问题 1）：[layer_h_race.py](engine/src/xkx/spec/layer_h_race.py) setup_race + apply_family_bonuses 最小 FunctionSpec 契约（不穷尽 13 门派公式）+ [test_spec_race.py](engine/tests/test_spec_race.py) 41 tests
  - **max_jingli 下限保护**：con<14 时 (con-14) 为负致 max_jingli 为负（LPC 边界 bug），加 max_jingli = max(max_jingli, 1) 下限保护（对照 human.c 行 417 setup_char 兜底）
  - agent teams 3 路并行：A race.py+family.py+test / B theme.py+world/governance/death/cli 改 / C spec 层；A+C 完成后修复 B 的 test 适配 + test_theme_neutrality 扩展
  - **1598 tests 全绿（+84：80 test_race_family + 41 test_spec_race + 4 test_theme_neutrality 扩展 - 适配调整），ruff 全过**；test_theme_neutrality + test_load_test 硬门禁持续通过
  - 关联 dissent 1（CombatKernel 主题无关性延伸：race 层 + 门派加成是 combat 之外的主题无关性收官）+ dissent 5（themed 治理，门派内容是题材包资产非治理逻辑）+ dissent 10（平台特性范围过载，只切割不全量迁移）

