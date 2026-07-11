# clone_npc_fa-e 标注表

- 文件路径: /Users/gukt/github/xkx2001-utf8/clone/npc/fa-e.c
- basename: clone_npc_fa-e
- 总语义单元数: 14
- 各层计数: 层0=5  层1=3  层2=0  层3=6
- 层3 项: 6 项（accept_fight 动态校验+通过分支 / chat / do_copy / do_recopy / do_clone / do_recover / auto_enable）

## 语义单元标注

| 语义单元 | 层 | 理由 |
|---|---|---|
| create() set_name/title/gender/age/long/attitude/generation/winner | 层0 | 纯数据声明，NPC 身份与描述 |
| create() set(str/con/int/dex 25/max_qi/eff_qi/qi 500/max_jing/jing 300/neili/max_neili 500/jiali 30/shen_type 0/combat_exp 400000/no_clean_up 1) | 层0 | 纯数据声明，NPC 属性 |
| create() set_skill(force/unarmed/sword/dodge/parry 各 90) | 层0 | 纯数据声明，技能等级 |
| create() set(weapon/armor) + carry_object(changjian)->wield() + carry_object(cloth)->wear() | 层0 | 纯数据声明+数据驱动装备装载 |
| create() restore() else 分支（set id/name + setup + 按存档 weapon/armor 重新 wield/wear） | 层0 | 存档恢复的数据声明 |
| init() set("no_get",1) + environment->set("winner",...) + add_action(recover/kill) | 层1 | 事件钩子：init 触发，设置标记+环境同步+注册命令 |
| do_kill(arg) deny "kill fae" -> write 不可对使者放肆 | 层1 | 命令拦截：arg=="fae" 时 deny + 消息（注释掉的卫兵群攻分支属层3，当前已注释禁用） |
| accept_fight(ob) deny 前置静态条件（shan_bangzhu/winner 命中/wiz/fighting） | 层1 | deny-wins 前置可用 any(谓词) 表达，分别返回不同 notify_fail 消息 |
| accept_fight(ob) 跨 NPC 动态校验 + 通过分支 | 层3 | find_living("mengzhu")/load_object + query("winner") 比对玩家 id（已是盟主 deny）+ find_living("shangshan")/load_object + 比对（已是赏善使者 deny）+ 通过分支多项 set 副作用+set_temp challenger，动态跨对象查询+批量副作用 |
| chat() 挑战判定主循环 | 层3 | is_fighting/present 状态机 + qi*100/max_qi 百分比计算 + call_out(do_copy,1) 闭包 + command(say/chat) 副作用，与 meng-zhu 同构 |
| do_copy(me,ob) 继承流程第 1 步 | 层3 | generation 递增 + chinese_number 拼接 title/short + ob->set_temp("apply/short") + call_out(do_clone,0) 闭包 |
| do_recopy(me,ob) recover 命令触发的重拷贝 | 层3 | 多分支 deny + 属性重写 + call_out(do_clone,0) 闭包 + write 消息 |
| do_clone(me,ob) 核心继承逻辑 | 层3 | 3 套 for 循环删除/拷贝 skills/skill_map/skill_prepare + for 循环遍历 all_inventory 析构/重新 wield/wear（含 is_unique/damage>50 过滤）+ query_entire_dbase 批量 set 20+ 属性 + clear_condition + save + environment->set winner |
| do_recover() 玩家状态复原 | 层3 | family 双重校验（family_name + enter_time）+ for 循环删除/拷贝 skills/maps + combat_exp/death_times/death_count 拷贝，循环+多分支（比 meng-zhu 简化，无 skill_learned 构建） |
| auto_enable()（来自 #include auto_enable.h） | 层3 | 插入排序 sorted_skills + 双重 for 遍历 weapon_types/unarmed_types + SKILL_D 动态查询 + map_skill/prepare_skill 副作用 + jiali 计算 |
| query_save_file() return SHIZHE | 层0 | 纯数据声明，存档路径常量（并入 create 存档恢复语义） |

## 备注

- 罚恶使者与盟主（meng-zhu.c）结构高度同构：同样的"挑战-继承-复原"机制 + call_out 闭包链（chat -> do_copy -> do_clone）+ dbase 全量拷贝循环。两者的差异主要在：(1) fa-e 的 accept_fight 多了跨 NPC 动态校验（find_living mengzhu/shangshan 查询当前盟主/赏善使者是否就是挑战者，防止一人兼任）；(2) fa-e 的 do_clone 中 combat_exp 直接拷贝（`me->set("combat_exp", hp_status["combat_exp"])`），而 meng-zhu 是 `*3/2`；(3) fa-e 的 do_recover 更简化（无 skill_learned 构建，combat_exp 直接 `*1` 拷贝 vs meng-zhu `*2/3`）。
- accept_fight 的 deny 前置可拆为两部分：静态条件（shan_bangzhu/winner 命中/wiz/fighting，可用谓词表达，层1）+ 动态跨 NPC 校验（find_living/load_object，层3）。转译中将静态部分提到层1 规则，动态部分标层3。通过分支（多项 set + set_temp challenger）同样层3。
- auto_enable.h 与 meng-zhu 共享同一个 #include，是 clone/npc/ 下挑战型 NPC 的通用技能自动映射逻辑。
- 注释掉的 do_kill 卫兵群攻逻辑（present "wei shi" + kill_ob 循环，3 个红衣武士）若启用则 do_kill 整体需升层3；当前已注释，do_kill 仍可层1。
