# 现状分析·Feature/Mixin 继承体系分析 (LPC 多继承 + feature 混入架构)

## 概述
XKX 的 feature 系统是静态多重继承混入架构。/feature/ 下约18个 F_ 模块通过 inherit 语句组合（char.c=18个、item.c=5个、room.c=2个）。F_DBASE 是中央数据注册表，提供 dbase（持久）+ tmp_dbase（瞬时）两层 mapping，经 F_TREEMAP 支持 '/' 路径访问，并带 default_ob 原型回退。tmp_dbase 的 "apply/" 命名空间实现修饰符堆叠（装备写入属性增量，getter 聚合基础值+修饰符），已具备 ECS 组件聚合雏形。无状态守护进程（COMBAT_D/CHAR_D/SKILL_D/CONDITION_D）以实体引用为参数调用，形态近似 ECS System。char.c.heart_beat() 是每实体独立更新循环，编排 attack/update_condition/heal_up。整体是 ECS 邻近但非真 ECS：feature 绑定数据+行为、组合为编译期静态、数据内嵌于对象、this_object() 动态分派制造隐式耦合。

## 现有模式
- **静态多重继承混入组合**：通过 inherit 语句静态组合 F_ 宏指向的 /feature/*.c；按对象类型组合不同 feature 集：room=2(item)、item=5、char=18、user=CHARACTER+2。宏定义见 include/globals.h。
- **F_DBASE 中央键值注册表**：dbase(持久化)+tmp_dbase(瞬时) 两层 mapping；set/query/add/delete 经 F_TREEMAP 支持 '/' 路径遍历；default_ob 单级原型回退；query() 对 functionp 自动 evaluate(惰性计算)。约145文件 inherit F_DBASE。
- **apply/ 修饰符堆叠**：tmp_dbase 的 'apply/' 命名空间实现修饰符堆叠：装备 wear() 把 armor_prop 累加进 apply，属性查询 query_str()=query('str')+query_temp('apply/strength')+技能加成。全库 2563 处 apply/ 引用，是 ECS 式组件聚合的雏形。
- **Daemon-as-System 守护进程即系统**：COMBAT_D/CHAR_D/SKILL_D/CONDITION_D 等无状态守护进程以实体引用为参数调用，如 COMBAT_D->fight(attacker,opponent)、CONDITION_D(cnd)->update_condition(obj,info)，与 ECS System 形态一致。
- **每实体 heart_beat 调度**：char.c.heart_beat() 作为每个实体独立的心跳，编排 attack()/update_condition()/heal_up()/continue_action()，而非全局系统调度。
- **this_object() 动态分派耦合**：feature 间不显式 import，而通过 this_object()->method() 动态分派(仅 feature 目录内 71 处)，依赖由组合类(char.c)的 inherit 顺序隐式保证，松耦合但无显式契约。

## 痛点
- 静态组合：feature 在编译期经 inherit 固定，无法运行时挂载/卸载组件，限制了 UGC 多题材动态实体的灵活性
- 隐式耦合：this_object()->method() 隐藏 feature 间依赖，无显式接口契约，重构与静态分析困难
- 数据与行为捆绑：feature 混合状态与逻辑，难以独立序列化/迁移/分片，阻碍分布式部署
- 命名扁平化风险：18 个 feature 方法被压平到单一对象命名空间，靠 nomask 与人工消歧，易冲突
- 无全局系统调度器：每实体独立 heart_beat，难以批处理/并行化/跨进程分布式调度
- 无类型字符串键：query('xxx') 散落 8400 文件，键名无类型检查，易拼写错误且无法静态校验
- finance.c 硬编码 present('gold_money') 查找，与 clone/money 路径紧耦合
- default_ob 仅单级回退，缺乏真正的原型/深克隆机制

## 应保留思想
- F_DBASE 路径式访问('/')已是灵活的文档模型，可平滑映射到 NoSQL/组件存储
- apply/ 修饰符堆叠即 ECS 组件聚合雏形，保留为 Buff/Equipment 组件基础
- Daemon-as-System 模式(无状态、实体引用参数)直接兼容 ECS System
- 永久/瞬时两层数据分离(dbase/tmp_dbase)利于持久化 vs 易失状态区分
- query() 对 functionp 自动 evaluate = 惰性/计算型组件，值得保留
- SKILL_D(name)/CONDITION_D(name) 插件模型 = 数据驱动行为注册表，天然适配 DSL/UGC

## 应废弃设计
- 静态 inherit 编译期组合 -> 替换为运行时 Component 注册表(attach/detach)，支持动态组合与多题材实体
- 每对象 heart_beat 独立心跳 -> 替换为全局 System 调度器(批处理/可并行/可分布式分片)
- this_object()->method() 动态分派 -> 替换为显式 System(entity, components) 调用，消除隐式契约
- 扁平 feature 方法命名空间 -> 替换为带命名空间的 Component 类型(AttackComponent/SkillComponent...)
- 散落全库的字符串键 query('xxx') -> 替换为类型化 Component schema，杜绝拼写错误与无检查访问
- finance.c present('gold_money') 硬编码货币对象查找 -> 替换为 Wallet 组件，解耦货币实现
- name.c short() 内联 12+ 状态源展示逻辑 -> 拆分为 DisplayName 系统统一聚合
- default_ob 单级回退原型 -> 升级为完整原型/深克隆或 ECS 模板实体机制

## 复杂度热点
- /feature/damage.c (332行): die()/unconcious()/heal_up() 编排 6+ feature 与 COMBAT_D/CHAR_D/MARRY_D，逻辑高度纠缠，单文件耦合最重
- /inherit/char/char.c heart_beat(): 约110行的 god-method，同时耦合 attack/update_condition/heal_up/team/action/is_busy，是系统级热点
- /feature/attack.c reset_action(): 通过 this_object() 与闭包桥接 F_ATTACK/F_SKILL/F_EQUIP/SKILL_D，动态分派链最深
- /feature/name.c short(): 聚合 12+ 状态源（colorname/nick/title/ghost/netdead/in_input/in_edit/idle/disable_type/condition），展示类方法过载
- /feature/skill.c: skills/learned/skill_map/skill_prepare 四张映射互引用 + 改进惩罚计算，技能子系统内部复杂度高
- /feature/condition.c update_condition(): 运行时加载外部 CONDITION_D 守护进程的容错循环，影响心跳稳定性

## 关键文件
- /home/gukt/github/xkx2001-utf8/include/globals.h
- /home/gukt/github/xkx2001-utf8/include/dbase.h
- /home/gukt/github/xkx2001-utf8/feature/dbase.c
- /home/gukt/github/xkx2001-utf8/feature/treemap.c
- /home/gukt/github/xkx2001-utf8/feature/attack.c
- /home/gukt/github/xkx2001-utf8/feature/skill.c
- /home/gukt/github/xkx2001-utf8/feature/damage.c
- /home/gukt/github/xkx2001-utf8/feature/attribute.c
- /home/gukt/github/xkx2001-utf8/feature/name.c
- /home/gukt/github/xkx2001-utf8/feature/condition.c
- /home/gukt/github/xkx2001-utf8/feature/message.c
- /home/gukt/github/xkx2001-utf8/feature/team.c
- /home/gukt/github/xkx2001-utf8/feature/finance.c
- /home/gukt/github/xkx2001-utf8/feature/move.c
- /home/gukt/github/xkx2001-utf8/inherit/char/char.c
- /home/gukt/github/xkx2001-utf8/inherit/char/npc.c
- /home/gukt/github/xkx2001-utf8/inherit/room/room.c
- /home/gukt/github/xkx2001-utf8/inherit/item/item.c
- /home/gukt/github/xkx2001-utf8/clone/user/user.c
- /home/gukt/github/xkx2001-utf8/feature/equip.c
