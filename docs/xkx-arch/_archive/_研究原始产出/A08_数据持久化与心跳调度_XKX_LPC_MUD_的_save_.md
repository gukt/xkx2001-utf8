# 现状分析·数据持久化与心跳调度（XKX/LPC MUD 的 save_object/d_base/heart_beat/call_out/reset/clean_up 体系）

## 概述
XKX 的持久化与调度完全依赖 MudOS 驱动原语：save_object 全量覆盖写 .o 文本快照（无历史、无并发、崩溃丢数据），dbase 内存 mapping 充当无 schema 的通用属性袋，heart_beat 是单进程粗粒度全局心跳（约 2 秒/tick），call_out（全库 3728 处）做非持久延迟调度，reset/clean_up 周期性重建房间与析构对象回收内存。整套机制单线程串行、不可水平扩展、定时器随对象析构而消失、状态与逻辑紧耦合，无法支撑分布式高并发与 UGC 平台需求。

## 现有模式
- **.o 文件快照持久化**：feature/save.c 的 save()/restore() 包装 MudOS efun save_object()/restore_object()，全量覆盖写入 .o 文本文件。每个对象实现 query_save_file() 决定路径（如 user.c 拼 /data/user/x/xyz、login.c 拼 /data/login/x/xyz、bboard 拼 /data/board/id）。inherit/save/data.c 提供 data_dir/data_file/user_data_dir（首字母分桶）和 assure_save_dir 的 mkdir -p。.o 内容是 LPC 序列化的 mapping（dbase/skills/skill_map），static 变量不持久化。245 个 .o 散落在 /data/{user,login,npc,board,job_system}/ 下。
- **dbase 无 schema 键值存储**：feature/dbase.c 是所有对象的通用属性袋：持久 mapping dbase + static mapping tmp_dbase（瞬态）。通过 set/query/add/delete 操作，支持 family/master_id 式斜杠嵌套路径（由 feature/treemap.c 的 _set/_query/_delete 递归遍历）。default_ob 让克隆继承母版默认值（原型模式）。query 可存储并 evaluate 函数值实现惰性属性。58 个对象 inherit F_SAVE。
- **heart_beat 全局单线程心跳**：MudOS 驱动对 set_heart_beat(1) 的对象周期性调用 heart_beat() apply（默认约 2 秒/tick）。inherit/char/char.c:60 heart_beat() 是角色主循环：attack() 战斗、tick 节流下 update_condition()、heal_up() 治疗、update_age() 年龄、idle 超时、频道限流、wimpy 逃跑、死亡/昏迷判定。空闲时 set_heart_beat(0) 关闭省 CPU（char.c:157），damage/attack/action 收到事件再 set_heart_beat(1) 唤醒。
- **call_out 定时器（非持久）**：全库 3728 处 call_out 调用 + 1335 处 remove_call_out，是唯一的延迟执行机制。典型用法：damage.c:134 call_out(revive, random(100-con)+30) 复活计时、user.c:134 call_out(user_dump, 900) 断线清理、login.c:11 call_out(time_out, 300) 登录超时、natured.c 自递归 call_out 维持昼夜循环。feature/action.c 的 start_call_out 封装让条件状态可安全自调度恢复。call_out 绑定在调度它的对象上，对象析构则定时器消失，且崩溃后全部丢失。
- **reset 周期重置**：MudOS 按 __TIME_TO_RESET__（约 15-30 分钟）周期性对已加载对象调用 reset() apply。inherit/room/room.c:76 reset() 重建房间物品：析构非角色/临时物，按 query(objects) mapping 重新 clone（make_inventory），对走失 NPC 调 return_home() 召回。clone/user/user.c:26 reset() 做潜力点恢复/盗贼衰减/战斗经验速率审计。
- **clean_up + 驱动 swap 回收**：feature/clean_up.c 的 clean_up() apply 在 __TIME_TO_CLEAN_UP__ 空闲后被驱动调用：若对象无 interactive 玩家在 deep_inventory 则 destruct 释放内存。no_clean_up 标志可豁免（母版默认加）。MudOS 驱动另有 __TIME_TO_SWAP__ 把不活跃对象的程序/状态换页到 __SWAP_FILE__ 磁盘，对 LPC 透明。本质是激进析构 + 驱动换页，无对象池。
- **事件驱动存档（非周期）**：cmds/usr/quit.c 在 quit 时 link_ob->save() + me->save()，damage.c die() 中 this_object()->save()，save 命令主动存档。无周期性自动存档守护进程，崩溃即丢失未保存进度。feature/autoload.c 的 save_autoload/restore_autoload 把身上装备序列化进 dbase 一起持久化。

## 痛点
- 无自动存档：玩家存档仅在 quit/death/save 命令触发，崩溃即丢未保存进度，玩家体验与数据安全差
- 持久化无历史/无审计：.o 是全量覆盖快照，无法回放、无法增量、无法查询变更，作弊与事故无法溯源
- 无并发支持：单进程 MudOS，save_object 直接写文件，无法横向扩展承载高并发，与目标分布式部署直接冲突
- heart_beat 单点瓶颈：所有战斗/治疗/条件/AI 挤在同一 2 秒 tick 单线程串行执行，tick 超时即 'Too long evaluation' 报错丢逻辑
- call_out 全量非持久：3728 处定时器绑定对象生命周期，对象析构或进程崩溃即静默丢失，复活/门关闭/昼夜循环等会错乱
- dbase 完全无 schema：set/query 路径是字符串约定，拼写错误静默失败，重构与多题材 DSL 化缺乏类型保障
- 对象生命周期粗暴：clean_up destruct 后靠 reset 重新 clone，状态恢复依赖 restore_object，逻辑实体与内存对象混淆，分布式部署难映射
- 昼夜循环靠自递归 call_out 链：natured.c 一次 miss 即整日时序错乱，无法跨实例对齐
- 战斗状态机分散在 heart_beat/attack/damage 多处 set_heart_beat 唤醒，崩溃后状态不一致难恢复

## 应保留思想
- query_save_file() 多态钩子模式：对象自决其持久化路径，新架构可演进为按实体 ID 分片寻址的存储抽象
- dbase 的斜杠路径嵌套 + default_ob 原型继承：天然映射到嵌套结构体 + 模板克隆（proto/prototype）模式，利于 DSL 配置派生实体
- persist 持久层与 temp 瞬态层分离（dbase vs tmp_dbase，static 修饰）：是状态存储 vs 运行期缓存的清晰边界，新架构应保留此分层
- heart_beat 的自适应节流：空闲 set_heart_beat(0) 关闭、事件驱动 set_heart_beat(1) 唤醒——映射到现代事件驱动仿真步进（仅活跃实体 tick）
- tick 节流（char.c 用 tick=5+random(10) 降低 condition 更新频率）：值得保留的非均匀调度思想，低成本高频 tick + 低频重计算
- autoload 装备序列化模式：物品随玩家存档的引用重建机制，可演进为实体引用的快照/投影
- call_out 的 remove_call_out 取消语义：延迟任务的撤销能力，新调度器必须保留（如取消复活/关门计时）
- clean_up 的环境感知回收：检查 deep_inventory 是否有玩家再决定销毁，映射到带活跃度感知的缓存逐出策略
- default_ob 链 + query 回溯查找：与原型继承一脉相承，适合 UGC 平台让用户基于模板派生自定义场景实体

## 应废弃设计
- save_object/restore_object 全量覆盖式 .o 文件 I/O：无版本/无并发/无崩溃保护，应替换为事件溯源 + 快照
- call_out 单进程非持久定时器：崩溃即丢、绑定对象生命周期、不可分布式调度，应替换为持久化分布式调度器
- set_heart_beat 单一全局粗粒度 tick 把战斗/治疗/条件/年龄/空闲混做一谈：应拆分为解耦的子系统仿真步进
- clean_up 通过 destruct 释放内存、再用时重新 clone/restore 的破坏式对象生命周期：应改为逻辑实体 + 缓存逐出/回填
- room reset() 内联的 make_inventory 硬编码 repop 逻辑：应外提为世界重生服务读取 spawn 配置
- previous_object()/geteuid 安全模型：迁移到分布式 actor 后需重设计基于身份/令牌的鉴权
- assure_save_dir 里手写的逐级 mkdir 循环：现代文件系统/对象存储 API 取代
- auto_fight 内联在 attack.c init() 的紧耦合敌意判定：应事件化/规则化以便支持多题材

## 复杂度热点
- clone/user/user.c:26 reset() 把游戏统计与年龄结算混入 reset 周期，职责不清
- inherit/char/char.c:60 heart_beat() 单函数承载战斗/治疗/条件/年龄/空闲/聊天限流/自动逃跑/死亡判断 8 类逻辑
- feature/condition.c update_condition() 通过 call_other 动态加载外部 condition daemon，失败时在心跳内删条件，热路径脆弱
- feature/dbase.c query() 可存储并 evaluate 函数值（闭包/lazy），状态可执行化使序列化与跨进程迁移复杂化
- inherit/room/room.c:76 reset() 重建逻辑含 make_inventory/return_home/多 clone 检测，是 NPC 复制 bug 高发区
- adm/daemons/natured.c 昼夜循环靠自递归 call_out 链维持，单次 miss 即整日时序错乱
- feature/damage.c die()/unconcious()/revive() 跨多个 call_out 与 set_heart_beat 状态机，是崩溃后状态不一致的高危路径
- feature/action.c:62 start_call_out 安全检查基于 previous_object/euid，迁移到分布式调度器后需重设计鉴权模型

## 关键文件
- /home/gukt/github/xkx2001-utf8/feature/save.c
- /home/gukt/github/xkx2001-utf8/feature/dbase.c
- /home/gukt/github/xkx2001-utf8/feature/treemap.c
- /home/gukt/github/xkx2001-utf8/feature/clean_up.c
- /home/gukt/github/xkx2001-utf8/feature/condition.c
- /home/gukt/github/xkx2001-utf8/feature/damage.c
- /home/gukt/github/xkx2001-utf8/feature/attack.c
- /home/gukt/github/xkx2001-utf8/feature/action.c
- /home/gukt/github/xkx2001-utf8/feature/autoload.c
- /home/gukt/github/xkx2001-utf8/inherit/char/char.c
- /home/gukt/github/xkx2001-utf8/inherit/room/room.c
- /home/gukt/github/xkx2001-utf8/inherit/save/data.c
- /home/gukt/github/xkx2001-utf8/inherit/save/existence.c
- /home/gukt/github/xkx2001-utf8/clone/user/user.c
- /home/gukt/github/xkx2001-utf8/clone/user/login.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/natured.c
- /home/gukt/github/xkx2001-utf8/adm/single/master.c
- /home/gukt/github/xkx2001-utf8/cmds/usr/quit.c
- /home/gukt/github/xkx2001-utf8/include/runtime_config.h
- /home/gukt/github/xkx2001-utf8/include/globals.h
- /home/gukt/github/xkx2001-utf8/include/user.h
- /home/gukt/github/xkx2001-utf8/data/npc/meng-zhu.o
