# clone_npc_meng-zhu 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/clone/npc/meng-zhu.c
- basename: clone_npc_meng-zhu
- 总语义单元数: 15
- 各层计数: 层0=4  层1=3  层2=0  层3=8
- 层3 项: 8 项（accept_fight 通过分支 / chat / do_copy / do_recopy / do_clone / do_recover / auto_enable / init 的 add_action 注册部分边界）

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set_name/title/gender/age/long/attitude/generation/winner | 层0 | 纯数据声明，NPC 身份与描述 |
| create() set(str/con/int/dex/max_qi/qi/max_jing/jing/neili/max_neili/jiali/shen_type/combat_exp/no_clean_up) | 层0 | 纯数据声明，NPC 属性 |
| create() set_skill(force/unarmed/sword/dodge/parry 各 100) + set(weapon/armor) | 层0 | 纯数据声明，技能等级与装备路径 |
| create() restore() else 分支（set id/name + setup + 按存档 weapon/armor 重新 wield/wear） | 层0 | 存档恢复的数据声明；按 query 值 carry_object 是数据驱动装载 |
| init() set("no_get",1) + environment->set("winner",...) + add_action(recover/kill) | 层1 | 事件钩子：init 触发，设置标记+环境同步+注册命令，可用谓词+注册表达 |
| do_kill(arg) deny "kill mengzhu" -> write 不可对盟主放肆 | 层1 | 命令拦截：arg=="mengzhu" 时 deny + 消息，condition->action 可表达（注释掉的卫兵群攻分支属层3，但当前已注释禁用） |
| accept_fight(ob) deny 前置条件（winner 命中/wiz_level/is_fighting/shan_bangzhu） | 层1 | deny-wins 前置可用 any(谓词) 表达，分别返回不同 notify_fail 消息 |
| accept_fight(ob) 通过分支（me->set eff_qi/qi/jing/jingli/neili = max + set_temp challenger） | 层3 | 通过分支需多项 set 副作用 + set_temp 状态写入，超出 condition->action 谓词表达力，需逃生舱 |
| chat() 挑战判定主循环 | 层3 | is_fighting/present 状态机 + qi*100/max_qi 百分比计算 + call_out(do_copy,1) 闭包 + command(say/chat) 文本与副作用交织，图灵完备状态机 |
| do_copy(me,ob) 继承流程第 1 步 | 层3 | generation 递增 + chinese_number 拼接 title/short + ob->set_temp("apply/short") + call_out(do_clone,0) 闭包，状态机式继承 |
| do_recopy(me,ob) recover 命令触发的重拷贝 | 层3 | 多分支 deny（winner 校验 + is_killing/is_fighting） + 属性重写 + call_out(do_clone,0) 闭包 |
| do_clone(me,ob) 核心继承逻辑 | 层3 | 3 套 for 循环删除/拷贝 skills/skill_map/skill_prepare mapping + for 循环遍历 all_inventory 析构/重新 wield/wear（含 is_unique/damage>50 过滤） + query_entire_dbase 批量 set 20+ 属性 + clear_condition + save + environment->set winner，循环+批量副作用+闭包 |
| do_recover() 玩家状态复原 | 层3 | family 双重校验（family_name + enter_time） + for 循环删除/拷贝 skills/maps + skill_learned mapping 构建 + combat_exp 计算 + log_file，循环+多分支+状态机 |
| auto_enable()（来自 #include auto_enable.h） | 层3 | 插入排序 sorted_skills + 双重 for 遍历 weapon_types/unarmed_types + SKILL_D(skill)->valid_enable 动态查询 + map_skill/prepare_skill 副作用 + jiali 计算，排序算法+循环+动态派发 |
| query_save_file() return MENGZHU | 层0 | 纯数据声明，存档路径常量（并入 create 存档恢复语义） |

## 备注

- 盟主 NPC 是"挑战-继承"机制的核心：玩家击败盟主后，盟主 NPC 拷贝玩家的 skills/stats/装备，并标记 winner=玩家 id，实现"代代相传"。整套机制依赖 call_out 闭包链（chat -> do_copy -> do_clone）+ dbase 全量拷贝循环，无法用层1 谓词或层2 对话树表达，必须层3。
- accept_fight 是典型的"deny-wins 前置可层1 + 通过分支需层3"的混合体：deny 前置用 any(谓词) 表达，但通过分支的多项属性重置 + set_temp challenger 超出谓词表达力。转译中将 deny 前置提到层1 规则，通过分支标层3。
- auto_enable.h 是 clone/npc/ 下多个 NPC 共享的 #include，含插入排序+双重循环+SKILL_D 动态派发，本身就是一个层3 单元，在 meng-zhu / fa-e 等文件中均引用。
- 注释掉的 do_kill 卫兵群攻逻辑（present "wei shi" + kill_ob 循环）若启用则 do_kill 整体需升层3；当前已注释，do_kill 仍可层1。
