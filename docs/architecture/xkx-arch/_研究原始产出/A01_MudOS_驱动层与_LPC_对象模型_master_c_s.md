# 现状分析·MudOS 驱动层与 LPC 对象模型（master.c / simul_efun.c / config.xkx / globals.h / save.c）

## 概述
XKX 基于 MudOS 单进程驱动，master.c 是驱动与 mudlib 的唯一契约层，承担连接入口(connect)、启动预加载(epilog/preload)、崩溃/错误处理、全套 valid_*() 权限钩子、UID 分配与对象析构救助。对象采用 blueprint/clone 双层模型：蓝图(load_object)存默认数据，克隆(new)以 file_name#id 标识，通过 default_ob 原型回退共享只读属性。生命周期由 create/heart_beat/reset/clean_up/swap/destruct 五重驱动，eval cost(6亿)与资源上限(数组1.5万)防止单线程下的无限循环。simul_efun 作为全局单例覆写 destruct/write 等内核函数，注入 remove() 清理钩子与消息路由。全局寻址依赖 file_name 字符串与 find_object/call_other，对象间直接指针引用(this_object/environment)是分布式化的最大障碍。

## 现有模式
- **Master 对象作为中央授权与生命周期回调枢纽**：master.c 是驱动与 mudlib 的唯一契约层，承载连接入口(connect)、虚拟编译(compile_object)、崩溃处理(crash)、错误处理(error_handler)、启动预加载(epilog/preload)、全套权限校验(valid_shadow/override/seteuid/socket/object/write/read/link/save_binary/bind 等 13 个 valid_* 钩子)、UID 分配(get_root_uid/get_bb_uid/creator_file/domain_file/author_file)、环境析构救助(destruct_env_of)。驱动在关键点回调 master，master 再委托给 SECURITY_D 等守护进程。
- **eval cost 与资源限制作为单线程安全阀**：config.xkx 驱动配置：time to swap=120s、time to clean up=180s、time to reset=1800s、maximum evaluation cost=600000000、maximum array/mapping size=15000、maximum string length=200000、inherit chain size=30、object table size=1501。这些硬编码常量驱动对象生命周期与资源边界。
- **blueprint/clone 双层对象模型 + default_ob 原型回退**：load_object/call_other(file,'??') 加载蓝图(文件名无#后缀)；new()/clone_object() 生成克隆(文件名 file#number)。clonep() 区分二者，base_name() 去除#后缀。F_DBASE 的 default_ob 机制让克隆回退查询蓝图属性(原型模式)，set_default_object 时给蓝图 add('no_clean_up',1) 防止蓝图被清理。OBJ_DUMP 清晰展示了大量 #number 克隆引用一个蓝图。
- **simul_efun 覆写层 + efun:: 逃生舱**：simul_efun 是全局单例，通过 efun:: 前缀覆写驱动内置函数：destruct() 被覆写为先调 ob->remove(euid) 再 efun::destruct()，形成销毁前的清理钩子(F_MOVE::remove 卸装备/回滚负重/default_ob 计数)；write/printf 被覆写为经 message() 系统路由；log_file 带文件大小轮转；base_name 供全库使用。这是整个 mudlib 的隐式公共 API。
- **全局对象寻址三件套：file_name/find_object/call_other**：find_object(path)/call_other(path,func) 按文件名寻址并按需加载；set_living_name/find_living 走 living 哈希表；children(path) 查所有克隆；all_inventory/deep_inventory/environment 遍历容器树；users() 列所有交互玩家。file_name 既是身份也是寻址键，对象身份与代码路径强绑定。
- **五重生命周期 + heart_beat 驱动**：create()(初始化)→setup()(延迟配置，设 euid/启 heart_beat/CHAR_D 初始化)→heart_beat()(周期 tick 驱动战斗/治疗/状态/衰老，可 set_heart_beat(0) 熄灭以省 CPU)→reset()(房间每 30 分钟重生 NPC/物品)→clean_up()(3 分钟无交互的非蓝图无环境对象被 destruct)→swap()(2 分钟未用换出到 swapfile)→destruct→remove(euid)→销毁。玩家额外有 net_dead(断线)/reconnect(重连)/user_dump(超时踢出) 子生命周期。
- **save_object/.o 文件 + static 排除 + 分片路径持久化**：F_SAVE 提供 save()/restore() 委托 query_save_file() 取路径，调驱动原生 save_object/restore_object 序列化非 static 变量到 .o 文件。用户数据按首字母分片 /data/user/<c>/<id>.o 避免单目录爆炸。static 变量(enemy 列表/tmp_dbase/weight)不保存，对象引用恢复后变 0，靠 autoload 机制重建装备。
- **UID/euid + previous_object 隐式信任链**：master.c valid_seteuid 委托 SECURITY_D，valid_object 要求克隆必须继承 F_MOVE；simul_efun object.c 的 creator_file/domain_file/author_file 按路径(/adm,/d,/u,/clone)分配 UID；F_MOVE::remove 校验 previous_object 必须是 SIMUL_EFUN_OB 才允许调用；login.c 用 nomask 保护 set()。previous_object() 作为隐式调用者身份贯穿权限校验。

## 痛点
- 单进程单线程模型是最大瓶颈：MudOS 单线程顺序执行所有 heart_beat/call_other，一个慢对象会阻塞整个世界。eval cost 虽设到 6 亿(原 10 万)仍是全局预算，高并发时所有玩家共享一个执行流。Python 多进程/asyncio 可突破，但对象间的直接指针引用(this_object()/environment())无法跨进程，是分布式重构的核心障碍。
- 对象身份与文件路径强绑定：file_name 既是身份 ID 又是代码路径，克隆用 path#number 标识。一旦代码重构移动文件，所有存档的引用、autoload 路径、find_object 调用都会断裂。新架构需要稳定的实体 ID 解耦身份与实现。
- 同步 call_other 阻塞调用：所有对象间通信是同步函数调用，分布式改造时必须改为异步消息，但现有代码大量依赖同步返回值(如 move() 后立即检查 environment())，迁移面极大。
- heart_beat 是上帝方法：char.c 的 heart_beat() 一个函数处理战斗/治疗/状态/衰老/NPC 聊天/频道清理/熄火优化，耦合度过高，难以拆分为独立子系统并行化。
- 三套重叠的回收机制(swap/clean_up/reset)语义混乱且时间相近(swap 120s/clean_up 180s)，开发者需同时推理对象在何时被换出、何时被清理、何时被重置，容易写出 no_clean_up 标记博弈代码。
- previous_object() 隐式信任链难审计：权限校验依赖调用栈来源(previous_object/geteuid(previous_object))，这种隐式上下文在分布式异步环境下无法直接传递，需显式化调用上下文/能力令牌。
- simul_efun 覆写造成隐式控制流：destruct() 实际先调 remove()，write() 实际走 message()，新开发者读 LPC 代码看不到这些隐式行为，迁移到 Python 时容易遗漏这些关键钩子。
- 持久化模型脆弱：save_object 仅存非 static 变量到平文件 .o，对象引用变 0 靠 autoload 重建，崩溃时正在编辑/战斗的状态丢失。无事务、无版本迁移、无 schema 演进机制。
- make_data_dir 是悬空调用：inherit/save.c:31 调用 MASTER_OB->make_data_dir() 但 master.c 从未定义此函数(全库无定义)，save_data() 路径是死代码(注释 'I think this is never called')，说明保存子系统有未维护的腐化路径。

## 应保留思想
- blueprint/clone + default_ob 原型模式：blueprint 存只读默认配置，clone 仅存差异状态，查询时回退蓝图——新架构可用 Python dataclass + 原型工厂 + 数据库 JSON 字段实现，省内存且改蓝图即全局生效，非常适合 UGC 场景下大量相似场景对象
- Mixin/Feature 组合优于深层继承：F_DBASE/F_MOVE/F_ATTACK 等 feature 可按需混入——Python 用 mixin 类或组合注入保持此模式，避免继承爆炸，利于多题材(武侠/航海/书院)复用能力模块
- Daemon 单职责服务模式：COMBAT_D/CHAR_D/SECURITY_D 等抽离复杂逻辑到单例服务——天然映射到微服务，每个 daemon 可独立部署为 gRPC/HTTP 服务
- heart_beat 作为游戏 tick 抽象：set_heart_beat(1/0) 按需开关周期逻辑，和平时熄火省 CPU——映射到 asyncio 定时任务/事件循环 tick，保留按需调度的思想
- clean_up 作为 TTL 驱逐 + reset 作为定时重生：二者是现代缓存与定时任务的雏形——映射到 Redis TTL 键 + Celery/APScheduler 定时任务，语义清晰
- F_DBASE 路径式属性访问 + 函数值延迟 evaluate：set('family/master_name',...) 支持层级，query 时可 evaluate 函数——Python 可用嵌套 dict + property 描述符实现，灵活 schema 利于 UGC DSL 扩展
- UID/euid 能力模型雏形：valid_seteuid + creator_file 按路径分配权限——演进为基于角色/能力令牌的 RBAC，previous_object 隐式信任链显式化为调用上下文 token
- save_object static 排除 + autoload 重建：选择性持久化(排除临时态) + 按需重建引用——映射为 dataclass 字段标注 @persist/@transient + ORM 关系懒加载
- 房间分片持久化路径 /data/user/<首字母>/<id>.o——天然映射到数据库分片键或对象存储前缀，避免热点

## 应废弃设计
- 单进程单线程假设与直接对象指针(object 类型)引用——分布式架构必须替换为可序列化的实体引用(ID)+异步消息传递，object 指针不能跨进程
- swap 到本地 swapfile 的换出机制——现代架构用无状态 pod + 外部状态存储(Redis/DB)，对象按需从状态存储重建，无需本地换出文件
- eval cost 作为单线程执行预算——替换为每请求超时 + 资源配额(内存/CPU/调用深度) + 熔断器，分布式环境下需 per-tenant 资源隔离
- file_name 即对象身份的强绑定——新架构应解耦实体 ID 与代码路径，支持热重载与多版本共存(UGC 场景必需)
- simul_efun 隐式全局覆写(所有对象自动获得覆写后的 destruct/write)——Python 应显式 mixin 或依赖注入，避免魔法般的隐式行为替换
- call_other 的同步阻塞调用——分布式下替换为异步 RPC/消息总线，但需注意原有代码大量依赖同步返回值，迁移成本高
- 全局 mutable 单例守护进程(SECURITY_D/COMBAT_D 等)直接持有内存状态——迁移到独立服务后需处理状态外部化与并发一致性，或改为无状态+缓存
- inherit 链深度限制(30 层)与编译期混入——Python 用组合优于继承，避免深层继承链；DSL 层应是数据驱动配置而非代码继承
- max users:150 的硬编码并发上限——WebSocket+分布式应支持弹性扩缩，按 worker 分片连接

## 复杂度热点
- char.c 的 heart_beat() 是 170 行的上帝方法，混合战斗/治疗/状态/年龄/NPC 聊天/频道管理，是重构最复杂的单点，应拆分为独立子系统
- simul_efun 对 efun::destruct 的全局覆写制造了隐式控制流——destruct 会先调 remove(euid) 再真正销毁，remove 内部还做装备卸下/负重回滚/default_ob 引用计数，调用顺序极易出错（如 move.c:89 注释 'this_object might have been destructed after move_object'）
- 三套重叠的对象回收机制（swap/clean_up/reset）交互复杂：clean_up(180s) 与 swap(120s) 时间接近但语义不同，reset(1800s) 重新生成对象，理解一个对象在给定时刻为何存在/不存在需要同时推理三者
- dbase 的 query() 有三层间接：自身 dbase -> 路径拆解(_query) -> default_ob 回退 -> 函数值 evaluate(data, this_object)，追踪一个属性的真实来源困难
- master.c 的 valid_*() 权限矩阵分散在 13 个函数中，且部分委托 SECURITY_D、部分直接硬编码返回值（valid_read 恒返回 1，valid_socket 恒返回 1），安全策略不集中、难审计
- 全局唯一 mutable 单例守护进程（SECURITY_D/COMBAT_D/CHAR_D/LOGIN_D 等）在新架构分布式部署时一致性是难点——SECURITY_D 的 wiz_status 映射若多副本并发写会冲突，需外部状态存储+锁

## 关键文件
- /home/gukt/github/xkx2001-utf8/adm/single/master.c
- /home/gukt/github/xkx2001-utf8/adm/single/simul_efun.c
- /home/gukt/github/xkx2001-utf8/adm/simul_efun/object.c
- /home/gukt/github/xkx2001-utf8/adm/simul_efun/message.c
- /home/gukt/github/xkx2001-utf8/adm/simul_efun/file.c
- /home/gukt/github/xkx2001-utf8/adm/simul_efun/path.c
- /home/gukt/github/xkx2001-utf8/config.xkx
- /home/gukt/github/xkx2001-utf8/include/globals.h
- /home/gukt/github/xkx2001-utf8/inherit/save.c
- /home/gukt/github/xkx2001-utf8/inherit/save/data.c
- /home/gukt/github/xkx2001-utf8/inherit/save/existence.c
- /home/gukt/github/xkx2001-utf8/feature/move.c
- /home/gukt/github/xkx2001-utf8/feature/clean_up.c
- /home/gukt/github/xkx2001-utf8/feature/save.c
- /home/gukt/github/xkx2001-utf8/feature/dbase.c
- /home/gukt/github/xkx2001-utf8/feature/command.c
- /home/gukt/github/xkx2001-utf8/feature/condition.c
- /home/gukt/github/xkx2001-utf8/feature/action.c
- /home/gukt/github/xkx2001-utf8/feature/cloneable.c
- /home/gukt/github/xkx2001-utf8/feature/unique.c
- /home/gukt/github/xkx2001-utf8/inherit/char/char.c
- /home/gukt/github/xkx2001-utf8/inherit/room/room.c
- /home/gukt/github/xkx2001-utf8/clone/user/login.c
- /home/gukt/github/xkx2001-utf8/clone/user/user.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/logind.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/securityd.c
- /home/gukt/github/xkx2001-utf8/adm/daemons/virtuald.c
- /home/gukt/github/xkx2001-utf8/adm/etc/preload
- /home/gukt/github/xkx2001-utf8/OBJ_DUMP
